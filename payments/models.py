import uuid
from django.db import models


class PaymentEvent(models.Model):
    """Model to store payment event information for webhook idempotency."""
    
    class WebhookStatus(models.TextChoices):
        PENDING = 'pending', 'Pending'
        PROCESSED = 'processed', 'Processed'
        FAILED = 'failed', 'Failed'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event_id = models.CharField(max_length=255, unique=True, db_index=True)
    order = models.ForeignKey('orders.RepairOrder', on_delete=models.CASCADE, related_name='payment_events')
    event_type = models.CharField(max_length=50, default='payment.success', help_text="e.g., payment.success, payment.failed")
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    status = models.CharField(max_length=20, choices=WebhookStatus.choices, default=WebhookStatus.PENDING)
    payload = models.JSONField(default=dict, help_text="Raw webhook payload")
    processed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['event_id']),
            models.Index(fields=['order', 'status']),
        ]

    def __str__(self):
        return f"PaymentEvent {self.event_id} - {self.status}"
