import logging
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.views.decorators.csrf import csrf_exempt
from .utils import verify_stripe_webhook_signature, handle_payment_intent_succeeded

logger = logging.getLogger(__name__)


@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
def stripe_webhook_view(request):
    """
    Handle Stripe webhook POST requests.
    
    POST /api/webhooks/payment/
    
    This endpoint:
    1. Validates the webhook signature using STRIPE_WEBHOOK_SECRET
    2. Checks if the event was already processed (idempotency)
    3. Verifies payment amount matches order total
    4. Marks order as paid and enqueues background job
    
    Idempotency Implementation:
    - Each webhook event has a unique event_id
    - We store processed events in PaymentEvent model
    - Duplicate events are rejected with 200 OK (idempotent)
    
    Returns:
        200 OK for valid webhooks (whether new or duplicate)
        400 Bad Request for invalid signatures/payloads
    """
    
    # Verify signature
    event = verify_stripe_webhook_signature(request)
    if not event:
        logger.warning("Webhook signature verification failed")
        return Response(
            {
                'success': False,
                'message': 'Webhook signature verification failed'
            },
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Route to appropriate handler based on event type
    event_type = event.get('type', '')
    
    if event_type == 'payment_intent.succeeded':
        success, message, order_id = handle_payment_intent_succeeded(event)
        
        if success:
            return Response(
                {
                    'success': True,
                    'message': message,
                    'order_id': str(order_id) if order_id else None
                },
                status=status.HTTP_200_OK
            )
        else:
            return Response(
                {
                    'success': False,
                    'message': message,
                    'order_id': str(order_id) if order_id else None
                },
                status=status.HTTP_400_BAD_REQUEST
            )
    
    elif event_type == 'payment_intent.payment_failed':
        logger.warning(f"Payment failed webhook received: {event.get('id')}")
        # Could implement order failure logic here
        return Response(
            {
                'success': True,
                'message': 'Payment failure event received'
            },
            status=status.HTTP_200_OK
        )
    
    else:
        # Unknown event type - still return 200 OK for Stripe
        logger.info(f"Received unhandled webhook event type: {event_type}")
        return Response(
            {
                'success': True,
                'message': f'Event type {event_type} received (unhandled)'
            },
            status=status.HTTP_200_OK
        )
