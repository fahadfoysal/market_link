"""Background tasks using Celery."""

import logging
from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings

logger = logging.getLogger(__name__)


@shared_task
def send_invoice_and_start_processing(order_id):
    """
    Send invoice email to customer and mark order as processing.
    
    This task runs asynchronously after payment is confirmed.
    
    Args:
        order_id: UUID of the RepairOrder
    """
    from orders.models import RepairOrder
    
    try:
        order = RepairOrder.objects.get(id=order_id)
        
        # Send invoice email
        subject = f"Invoice for Repair Order {order.id}"
        message = f"""
        Dear {order.customer.get_full_name() or order.customer.email},
        
        Thank you for your order. Your repair order {order.id} has been confirmed.
        
        Service: {order.variant.service.name} - {order.variant.name}
        Vendor: {order.vendor.business_name}
        Amount: ${order.total_amount}
        Estimated Time: {order.variant.estimated_minutes} minutes
        
        Your repair will begin shortly.
        
        Best regards,
        MarketLink Team
        """
        
        try:
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [order.customer.email],
                fail_silently=False,
            )
            logger.info(f"Invoice sent for order {order_id}")
        except Exception as e:
            logger.error(f"Failed to send invoice for order {order_id}: {str(e)}")
        
        # Mark order as processing
        order.status = RepairOrder.Status.PROCESSING
        order.save(update_fields=['status', 'updated_at'])
        
        logger.info(f"Order {order_id} marked as processing")
        return True
    
    except RepairOrder.DoesNotExist:
        logger.error(f"Order {order_id} not found")
        return False
    except Exception as e:
        logger.error(f"Error processing order {order_id}: {str(e)}")
        return False
