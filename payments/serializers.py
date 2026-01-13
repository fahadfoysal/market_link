from rest_framework import serializers
from .models import PaymentEvent


class PaymentEventSerializer(serializers.ModelSerializer):
    """Serializer for payment events."""
    
    class Meta:
        model = PaymentEvent
        fields = ['id', 'event_id', 'order', 'event_type', 'amount', 'status', 'processed_at']
        read_only_fields = fields


class StripeWebhookSerializer(serializers.Serializer):
    """Serializer for validating Stripe webhook payloads."""
    
    # This is a pass-through serializer since Stripe payloads are complex
    # The actual validation happens in the view via signature verification
    pass
