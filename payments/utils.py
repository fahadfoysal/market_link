"""Stripe payment integration utilities."""

import os
import logging
import hashlib
import hmac
import json
import stripe

logger = logging.getLogger(__name__)

# Initialize Stripe
stripe.api_key = os.getenv('STRIPE_SECRET_KEY', 'sk_test_dummy')


def create_stripe_payment_intent(order):
    """
    Create a Stripe Payment Intent for an order.
    
    Args:
        order: RepairOrder instance
    
    Returns:
        str: Stripe client secret or None on error
    """
    try:
        intent = stripe.PaymentIntent.create(
            amount=int(order.total_amount * 100),  # Amount in cents
            currency='usd',
            metadata={
                'order_id': str(order.id),
                'customer_email': order.customer.email,
                'vendor_name': order.vendor.business_name,
            },
            description=f"Repair Order {order.id}",
        )
        
        # Store the payment intent ID in the order
        order.stripe_payment_intent_id = intent.id
        order.payment_method = 'stripe'
        order.save(update_fields=['stripe_payment_intent_id', 'payment_method'])
        
        logger.info(f"Created Stripe payment intent {intent.id} for order {order.id}")
        return intent.client_secret
    
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error creating payment intent for order {order.id}: {str(e)}")
        return None


def verify_stripe_webhook_signature(request):
    """
    Verify Stripe webhook signature.
    
    Args:
        request: Django HTTP request with webhook payload
    
    Returns:
        dict: Parsed webhook event or None if verification fails
    """
    webhook_secret = os.getenv('STRIPE_WEBHOOK_SECRET', '')
    
    if not webhook_secret:
        logger.error("STRIPE_WEBHOOK_SECRET not configured")
        return None
    
    try:
        signature = request.META.get('HTTP_STRIPE_SIGNATURE', '')
        payload = request.body
        
        event = stripe.Webhook.construct_event(
            payload, signature, webhook_secret
        )
        return event
    except ValueError as e:
        logger.error(f"Invalid webhook payload: {str(e)}")
        return None
    except stripe.error.SignatureVerificationError as e:
        logger.error(f"Webhook signature verification failed: {str(e)}")
        return None


def handle_payment_intent_succeeded(event):
    """
    Handle Stripe payment.intent.succeeded event.
    
    Args:
        event: Stripe webhook event
    
    Returns:
        tuple: (success: bool, message: str, order_id: UUID or None)
    """
    from orders.models import RepairOrder
    from payments.models import PaymentEvent
    from django.utils import timezone
    from django.db import transaction
    
    intent = event['data']['object']
    order_id = intent['metadata'].get('order_id')
    event_id = event['id']
    
    if not order_id:
        logger.error(f"Webhook event {event_id} missing order_id in metadata")
        return False, "Missing order_id in metadata", None
    
    try:
        order = RepairOrder.objects.get(id=order_id)
    except RepairOrder.DoesNotExist:
        logger.error(f"Webhook references non-existent order {order_id}")
        return False, f"Order {order_id} not found", None
    
    # Check if payment event already processed (idempotency)
    if PaymentEvent.objects.filter(event_id=event_id).exists():
        logger.warning(f"Webhook event {event_id} already processed")
        return True, "Event already processed", order_id
    
    # Verify amount matches
    amount_cents = int(order.total_amount * 100)
    if intent['amount'] != amount_cents:
        logger.error(
            f"Amount mismatch for order {order_id}: "
            f"expected {amount_cents}, got {intent['amount']}"
        )
        
        # Record the failed payment event
        PaymentEvent.objects.create(
            event_id=event_id,
            order=order,
            event_type='payment.failed',
            amount=intent['amount'] / 100,
            status='failed',
            payload=intent,
            error_message='Amount mismatch'
        )
        
        return False, "Payment amount does not match order total", order_id
    
    # Mark order as paid
    try:
        with transaction.atomic():
            order.mark_as_paid()
            
            # Record the successful payment event
            PaymentEvent.objects.create(
                event_id=event_id,
                order=order,
                event_type='payment.success',
                amount=order.total_amount,
                status='processed',
                payload=intent,
                processed_at=timezone.now()
            )
            
            logger.info(f"Order {order_id} marked as paid from webhook {event_id}")
            
            # Enqueue background job to send invoice and start processing
            from payments.tasks import send_invoice_and_start_processing
            send_invoice_and_start_processing.delay(str(order_id))
        
        return True, "Payment processed successfully", order_id
    
    except Exception as e:
        logger.error(f"Error processing payment for order {order_id}: {str(e)}")
        return False, f"Error processing payment: {str(e)}", order_id
