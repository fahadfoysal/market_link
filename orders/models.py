import uuid
from django.db import models
from django.core.exceptions import ValidationError

class RepairOrder(models.Model):
    """Model representing a repair order in the marketplace."""

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        PAID = 'paid', 'Paid'
        PROCESSING = 'processing', 'Processing'
        COMPLETED = 'completed', 'Completed'
        FAILED = 'failed', 'Failed'
        CANCELLED = 'cancelled', 'Cancelled'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey('users.User', on_delete=models.CASCADE, related_name='repair_orders')
    vendor = models.ForeignKey('vendors.VendorProfile', on_delete=models.CASCADE, related_name='repair_orders')
    variant = models.ForeignKey('services.ServiceVariant', on_delete=models.PROTECT, related_name='repair_orders')
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    payment_method = models.CharField(max_length=50, null=True, blank=True, help_text="e.g., stripe")
    stripe_payment_intent_id = models.CharField(max_length=255, null=True, blank=True, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['customer', 'status']),
            models.Index(fields=['vendor', 'status']),
        ]

    def __str__(self):
        return f"RepairOrder {self.id} - {self.status}"
    
    def can_be_paid(self):
        """Check if order can be marked as paid."""
        return self.status == self.Status.PENDING
    
    def mark_as_paid(self):
        """Mark order as paid."""
        if not self.can_be_paid():
            raise ValidationError(f"Order cannot be marked as paid. Current status: {self.status}")
        self.status = self.Status.PAID
        self.save(update_fields=['status', 'updated_at'])
