# MarketLink Backend Implementation

A multi-vendor marketplace backend API built with Django and Django REST Framework, supporting vendors offering repair services with variant-priced bookings, customer orders, and Stripe-based payment processing.

## Project Overview

MarketLink connects local repair shops with vehicle owners. This implementation includes:
- **User Management**: JWT-based authentication with role-based access (Customer, Vendor, Admin)
- **Vendor Profiles**: Business registration and management
- **Services & Variants**: Service catalog with multiple pricing tiers and stock management
- **Repair Orders**: Customer booking with concurrent stock reservation
- **Payment Processing**: Stripe integration with webhook-based confirmation
- **Concurrency Control**: Redis-based distributed locking for stock safety

## Architecture & Design Decisions

### 1. Authentication & Authorization
- **JWT Token-Based Auth**: Using `djangorestframework-simplejwt`
- **Role-Based Access Control**: Three user roles (CUSTOMER, VENDOR, ADMIN)
- **Custom Permission Classes**: Granular permissions for endpoints
  - `IsCustomer`: Only customers can create orders
  - `IsVerifiedVendor`: Only verified vendors can manage services
  - `IsOwner`: Users can only see their own orders

### 2. Concurrency & Stock Management

**Problem Statement**: Multiple customers booking simultaneously for limited stock.

**Solution**: Redis-based distributed locking with atomic stock decrement.

**Implementation**:
```python
# Location: orders/utils.py
def try_reserve_stock(variant_id, timeout=30):
    """
    Atomically reserve stock using Redis:
    1. Acquire lock: cache.add(lock_key, lock_id, timeout=30)
    2. Read stock: ServiceVariant.objects.select_for_update().get(...)
    3. Decrement: variant.stock -= 1; variant.save()
    4. Release lock: cache.delete(lock_key)
    
    Benefits:
    - Prevents race condition between check and decrement
    - select_for_update() ensures atomic DB-level locking
    - Redis lock prevents multiple processes acquiring DB lock
    - Timeout ensures abandoned locks are cleaned up
    """
```

**Race Condition Prevention**:
- Customer A and B both check stock > 0 ✓
- Customer A acquires Redis lock, Customer B waits
- Customer A: SELECT FOR UPDATE + decrement stock to 0 + release lock
- Customer B: Acquires lock, reads stock = 0, declines booking

**Why This Approach?**:
- Redis lock is fast and distributed (works across servers)
- DB-level SELECT FOR UPDATE provides ultimate safety
- Timeout prevents deadlocks from crashed processes
- Cost-effective compared to distributed transaction systems

### 3. Order & Payment Flow

```
Customer → POST /api/orders/
     ↓
Create RepairOrder (status=pending)
Reserve stock (Redis lock + atomic decrement)
Create Stripe Checkout Session
Return order_id + payment_url (Stripe Checkout URL)
     ↓
Customer → Opens payment_url in browser
     ↓
Stripe Checkout Page (Hosted by Stripe)
Customer enters card details
     ↓
Payment Complete → Stripe redirects to /api/orders/{id}/success/
Payment Cancelled → Stripe redirects to /api/orders/{id}/cancel/
     ↓
Stripe webhook → POST /api/webhooks/payment/
     ↓
Verify signature (STRIPE_WEBHOOK_SECRET)
Check idempotency (event_id in PaymentEvent)
Backfill stripe_payment_intent_id if missing
Mark order as paid + Enqueue background job
     ↓
Background task: Send invoice + Mark processing
```

### 4. Webhook Idempotency

**Problem**: Webhook might be delivered multiple times (network issues, retries).

**Solution**: Idempotent webhook handler.

**Implementation**:
```python
# Location: payments/utils.py
def handle_payment_intent_succeeded(event):
    event_id = event['id']
    
    # Check if already processed
    if PaymentEvent.objects.filter(event_id=event_id).exists():
        return True, "Event already processed", order_id  # Return success
    
    # Verify amount matches
    if intent['amount'] != amount_cents:
        # Record failed payment event
        PaymentEvent.objects.create(
            event_id=event_id,
            status='failed',
            error_message='Amount mismatch'
        )
        return False, "Payment amount does not match"
    
    # Process payment atomically
    with transaction.atomic():
        order.mark_as_paid()
        PaymentEvent.objects.create(
            event_id=event_id,
            status='processed'
        )
```

**Why This Works**:
- `event_id` is unique per Webhook event (provided by Stripe)
- First request: Creates PaymentEvent + marks order paid
- Duplicate request: Finds existing event, returns success (idempotent)
- Amount verification prevents webhook tampering

### 5. Payment Gateway Choice

**Integration**: Stripe Checkout Sessions

**Why Stripe Checkout**:
- Hosted payment page (no frontend required)
- PCI DSS compliant (Stripe handles all card data)
- Industry standard for SaaS/marketplace
- Excellent webhook system for payment confirmation
- Works globally with multiple payment methods
- Handles 3D Secure and SCA compliance automatically
- Clear documentation and SDKs

**Flow**:
1. Backend creates Checkout Session: `stripe.checkout.Session.create()`
2. Returns `payment_url` (Checkout page URL) to customer
3. Customer opens URL and completes payment on Stripe's hosted page
4. Stripe redirects to success/cancel URL based on payment result
5. Stripe sends `payment_intent.succeeded` webhook to `/api/webhooks/payment/`
6. Backend processes webhook + marks order paid
7. Background job sends invoice email

**Key Features**:
- No frontend code needed - just redirect to `payment_url`
- Automatic metadata attachment to payment intent for webhook reconciliation
- Idempotent webhook processing prevents double-charging
- Amount verification ensures payment matches order total

### 6. Background Tasks

**Task**: Send invoice email + mark order as processing.

**Implementation**: Celery (optional) + Django signals

```python
# Location: payments/tasks.py
@shared_task
def send_invoice_and_start_processing(order_id):
    """Send invoice and transition order to processing status."""
    # Email implementation with custom invoice template
    # Update order status to PROCESSING
    # This runs async after payment confirmation
```

**Why Async**:
- Email delivery shouldn't block API response
- Can retry on failure
- Can be scaled independently
- Improves user experience

## Database Schema

### Core Models

```
User (AbstractBaseUser)
├── id (UUID, PK)
├── email (unique)
├── role (CUSTOMER | VENDOR | ADMIN)
├── is_active, is_staff

VendorProfile (OneToOne → User)
├── id (UUID, PK)
├── user (OneToOne)
├── business_name
├── address
├── is_active

Service
├── id (UUID, PK)
├── vendor (FK → VendorProfile)
├── name
├── created_at, updated_at

ServiceVariant
├── id (UUID, PK)
├── service (FK → Service)
├── name (Basic, Premium, Express)
├── price
├── estimated_minutes
├── stock (concurrent bookings)
├── created_at, updated_at

RepairOrder
├── id (UUID, PK)
├── customer (FK → User)
├── vendor (FK → VendorProfile)
├── variant (FK → ServiceVariant)
├── total_amount
├── status (pending, paid, processing, completed, failed, cancelled)
├── payment_method (stripe)
├── stripe_payment_intent_id (unique)
├── created_at, updated_at
├── Indexes: (customer, status), (vendor, status)

PaymentEvent (Idempotency Log)
├── id (UUID, PK)
├── event_id (unique, from Stripe)
├── order (FK → RepairOrder)
├── event_type (payment.success, payment.failed)
├── amount
├── status (pending, processed, failed)
├── payload (JSON, raw webhook)
├── processed_at
├── error_message
├── created_at
├── Indexes: (event_id), (order, status)
```

## API Endpoints

### User & Auth
```
POST   /api/users/register/          - Create account
POST   /api/users/login/             - Get JWT tokens
POST   /api/users/logout/            - Blacklist token
GET    /api/users/profile/           - Get profile
PATCH  /api/users/profile/           - Update profile
POST   /api/users/token/refresh/     - Refresh access token
```

### Vendor Profile
```
POST   /api/vendors/profile/         - Create vendor profile
GET    /api/vendors/profile/         - Get vendor profile
PATCH  /api/vendors/profile/         - Update vendor profile
```

### Services
```
GET    /api/services/                - List all services (public)
POST   /api/services/                - Create service (vendor)
GET    /api/services/my/             - My services (vendor)
GET    /api/services/{id}/           - Service details (public)
PATCH  /api/services/{id}/           - Update service (vendor, owner)
DELETE /api/services/{id}/           - Delete service (vendor, owner)
GET    /api/services/{id}/variants/  - Service variants (public)
POST   /api/services/{id}/variants/  - Create variant (vendor, owner)
PATCH  /api/services/variants/{id}/  - Update variant (vendor, owner)
DELETE /api/services/variants/{id}/  - Delete variant (vendor, owner)
GET    /api/services/variants/{id}/availability/ - Check stock (customer)
```

### Orders
```
POST   /api/orders/                  - Create order (customer)
GET    /api/orders/my/               - My orders (customer)
GET    /api/orders/vendor/           - Vendor's orders (vendor)
GET    /api/orders/{id}/             - Order details (customer or vendor)
GET    /api/orders/{id}/success/     - Payment success redirect (public)
GET    /api/orders/{id}/cancel/      - Payment cancel redirect (public)
```

### Payments
```
POST   /api/webhooks/payment/        - Stripe webhook (public)
```

## Setup & Installation

### Prerequisites
- Python 3.12+
- Redis (for caching and locks)
- PostgreSQL (recommended for production)

### Environment Variables
```bash
# .env file
SECRET_KEY=your-django-secret-key
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Stripe (get from https://dashboard.stripe.com/)
STRIPE_PUBLIC_KEY=pk_test_...
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...

# Email (optional)
DEFAULT_FROM_EMAIL=noreply@marketlink.local
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend

# Redis (optional, for Celery tasks)
CELERY_BROKER_URL=redis://127.0.0.1:6379/0
CELERY_RESULT_BACKEND=redis://127.0.0.1:6379/0

# Database (optional, defaults to SQLite)
DB_ENGINE=django.db.backends.sqlite3
DB_NAME=db.sqlite3
# For PostgreSQL:
# DB_ENGINE=django.db.backends.postgresql
# DB_NAME=marketlink
# DB_USER=postgres
# DB_PASSWORD=your_password
# DB_HOST=localhost
# DB_PORT=5432
```

### Installation Steps
```bash
# Clone and setup
git clone <repo>
cd market_link
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
pip install python-dotenv  # For loading .env file

# Create .env file
cp .env.example .env  # Or create manually with variables above

# Create database
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Run server
python manage.py runserver

# Run Celery (optional, for background tasks)
celery -A market_link worker -l info
```

### Stripe Webhook Setup (Development)

For local testing, use Stripe CLI to forward webhooks:

```bash
# Install Stripe CLI (https://stripe.com/docs/stripe-cli)
brew install stripe/stripe-cli/stripe  # macOS
# Or download from https://github.com/stripe/stripe-cli/releases

# Login to Stripe
stripe login

# Forward webhooks to local server
stripe listen --forward-to localhost:8000/api/webhooks/payment/

# Copy the webhook secret (whsec_...) to your .env file
# STRIPE_WEBHOOK_SECRET=whsec_...

# Test webhook
stripe trigger payment_intent.succeeded
```

### Using ngrok for External Testing

```bash
# Install ngrok (https://ngrok.com/)
ngrok http 8000

# Add ngrok URL to ALLOWED_HOSTS in .env
ALLOWED_HOSTS=localhost,127.0.0.1,your-ngrok-domain.ngrok-free.dev

# Add to Django settings.py CSRF_TRUSTED_ORIGINS
CSRF_TRUSTED_ORIGINS = [
    'https://your-ngrok-domain.ngrok-free.dev',
    'http://localhost:8000',
]

# Use ngrok URL for Stripe webhook endpoint:
# https://your-ngrok-domain.ngrok-free.dev/api/webhooks/payment/
```

## Testing

### Create Test Vendor
```bash
curl -X POST http://localhost:8000/api/users/register/ \
  -H "Content-Type: application/json" \
  -d '{
    "email": "vendor@example.com",
    "password": "SecurePassword123!",
    "first_name": "John",
    "last_name": "Vendor",
    "role": "VENDOR"
  }'

# Login and get token
curl -X POST http://localhost:8000/api/users/login/ \
  -H "Content-Type: application/json" \
  -d '{
    "email": "vendor@example.com",
    "password": "SecurePassword123!"
  }'

# Create vendor profile
curl -X POST http://localhost:8000/api/vendors/profile/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "business_name": "John's Auto Repair",
    "address": "123 Main St, Springfield"
  }'
```

### Create Test Service
```bash
curl -X POST http://localhost:8000/api/services/ \
  -H "Authorization: Bearer <vendor_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Oil Change"
  }'

# Add variant
curl -X POST http://localhost:8000/api/services/<service_id>/variants/ \
  -H "Authorization: Bearer <vendor_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Standard Oil Change",
    "price": "29.99",
    "estimated_minutes": 15,
    "stock": 5
  }'
```

### Test Order & Payment Flow
```bash
# Create customer
# (Similar to vendor creation, but role=CUSTOMER)

# Create order
curl -X POST http://localhost:8000/api/orders/ \
  -H "Authorization: Bearer <customer_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "variant_id": "<variant_uuid>"
  }'

# Response:
{
  "success": true,
  "message": "Repair order created successfully. Proceed to payment.",
  "data": {
    "id": "8dc6c845-56c0-4f60-b2a7-5e733e48eb36",
    "customer_email": "customer@example.com",
    "vendor_name": "John's Auto Repair",
    "variant": {
      "id": "...",
      "name": "Standard Oil Change",
      "price": "29.99",
      "stock": 4
    },
    "total_amount": "29.99",
    "status": "pending",
    "payment_method": "stripe",
    "payment_url": "https://checkout.stripe.com/pay/cs_test_a1B2c3D4...",
    "created_at": "2026-01-13T15:30:00Z",
    "updated_at": "2026-01-13T15:30:00Z"
  }
}

# Open payment_url in browser to complete payment
# User enters test card: 4242 4242 4242 4242

# After payment success, Stripe redirects to:
# http://localhost:8000/api/orders/{order_id}/success/

# Stripe webhook automatically processes payment:
# POST /api/webhooks/payment/ (sent by Stripe)
# Order status changes: pending → paid

# Check order status
curl -X GET http://localhost:8000/api/orders/my/ \
  -H "Authorization: Bearer <customer_token>"
```

**Stripe Test Cards**:
```
Success: 4242 4242 4242 4242 (any future expiry, any CVC)
Decline: 4000 0000 0000 0002
Requires Auth: 4000 0027 6000 3184 (3D Secure)
```

## Business Rules & Edge Cases

### Stock Management
1. **Double Booking Prevention**: Redis lock ensures only one process can decrement simultaneously
2. **Stock Refund**: If payment fails, stock is NOT automatically refunded (manual intervention required)
3. **Overselling Prevention**: Check `stock > 0` before acquiring lock

### Order Status Flow
```
pending → (payment_received) → paid → processing → completed
       → (payment_failed) → cancelled
```

### Vendor Verification
- Vendors must create profile before offering services
- Only verified vendors (with profile) can create services
- Orders reference both customer and vendor for easy filtering

### Concurrent Access Patterns
| Scenario | Implementation |
|----------|-----------------|
| 2 customers booking simultaneously | Redis lock serializes stock decrements |
| Webhook delivered twice | event_id uniqueness prevents double processing |
| Vendor modifies service during booking | FK with PROTECT prevents deletion |
| Payment webhook before order created | Validates order exists before processing |

## Security Considerations

1. **Webhook Signature Verification**: All Stripe webhooks signed with STRIPE_WEBHOOK_SECRET
2. **CSRF Protection**: Django CSRF middleware on all POST/PATCH/DELETE (disabled for webhooks)
3. **Rate Limiting**: Not implemented (can add django-ratelimit if needed)
4. **JWT Token Expiry**: Access token expires in 1 hour
5. **Token Blacklist**: Logout adds token to blacklist
6. **PII**: Payment processing delegated to Stripe (no card data in DB)

## Performance Optimizations

1. **Database Indexes**: (customer, status), (vendor, status), event_id
2. **Select Related**: Serializers use `select_related()` for FK resolution
3. **Redis Caching**: Stock locks cached in Redis (sub-millisecond access)
4. **Async Email**: Background tasks prevent email delays
5. **Connection Pooling**: Django database connection pooling

## Monitoring & Logging

```python
# Enable structured logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {'class': 'logging.StreamHandler'},
    },
    'loggers': {
        'orders.utils': {'level': 'INFO'},
        'payments.utils': {'level': 'INFO'},
    },
}
```

Key log points:
- Stock reservation attempts
- Payment event processing
- Webhook verification failures
- Order status transitions

## Known Limitations & Future Work

1. **Celery Dependency**: Background tasks currently use @shared_task but require Celery setup
   - **Alternative**: Use Django signals or scheduled tasks
   - **Solution**: Install `celery` and `redis`, set CELERY_BROKER_URL

2. **Payment Refunds**: Not implemented (requires separate endpoint)
   - **Future**: POST /api/orders/{id}/refund/

3. **Order Cancellation**: Status transition not automated
   - **Future**: Allow customers to cancel pending orders with stock refund

4. **Pagination**: List endpoints don't paginate
   - **Future**: Implement cursor-based pagination for large result sets

5. **Rate Limiting**: No protection against brute-force attacks
   - **Future**: Add django-ratelimit or DRF throttling

6. **Audit Logging**: No audit trail for payment changes
   - **Future**: Implement django-audit-log

7. **Stripe Checkout Session Expiry**: Sessions expire after 24 hours
   - **Current**: payment_url becomes invalid after 24h
   - **Future**: Add endpoint to regenerate payment URL for pending orders

8. **Stock Refund on Payment Failure**: Currently requires manual intervention
   - **Future**: Implement automatic stock refund after payment timeout/failure

## Deployment Notes

### Production Checklist
```bash
# Environment
DEBUG=False
ALLOWED_HOSTS=yourdomain.com
SECRET_KEY=<use strong random key>

# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'marketlink',
        'USER': 'postgres',
        'PASSWORD': '<secure>',
        'HOST': 'db.example.com',
    }
}

# Cache/Redis
CACHES['default']['LOCATION'] = 'redis://cache.example.com:6379/1'

# Email
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.sendgrid.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'apikey'
EMAIL_HOST_PASSWORD = '<sendgrid-key>'

# Stripe
STRIPE_SECRET_KEY = 'sk_live_...'
STRIPE_WEBHOOK_SECRET = 'whsec_live_...'
```

### Running with Gunicorn
```bash
gunicorn market_link.wsgi:application \
  --workers 4 \
  --threads 2 \
  --worker-class gthread \
  --bind 0.0.0.0:8000
```

## Support & Contact

For issues or questions, refer to the inline code documentation or create an issue in the repository.
