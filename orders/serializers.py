from rest_framework import serializers
from .models import RepairOrder
from services.models import ServiceVariant
from services.serializers import ServiceVariantSerializer


class RepairOrderCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating a repair order."""
    
    variant_id = serializers.UUIDField(write_only=True)
    
    class Meta:
        model = RepairOrder
        fields = ['variant_id']
    
    def validate_variant_id(self, value):
        """Validate that the variant exists and has stock."""
        try:
            variant = ServiceVariant.objects.get(id=value)
        except ServiceVariant.DoesNotExist:
            raise serializers.ValidationError(f"ServiceVariant with id {value} does not exist.")
        
        if variant.stock <= 0:
            raise serializers.ValidationError("This service variant is out of stock.")
        
        return value
    
    def create(self, validated_data):
        """Create a repair order with concurrent stock management."""
        from django.core.exceptions import ValidationError
        from .utils import try_reserve_stock
        
        variant_id = validated_data.pop('variant_id')
        variant = ServiceVariant.objects.get(id=variant_id)
        customer = self.context['request'].user
        
        # Reserve stock using Redis lock for concurrency safety
        if not try_reserve_stock(variant.id):
            raise ValidationError("Service variant is no longer available (stock exhausted).")
        
        order = RepairOrder.objects.create(
            customer=customer,
            vendor=variant.service.vendor,
            variant=variant,
            total_amount=variant.price,
            status=RepairOrder.Status.PENDING
        )
        return order


class RepairOrderListSerializer(serializers.ModelSerializer):
    """Serializer for listing repair orders."""
    
    variant = ServiceVariantSerializer(read_only=True)
    customer_email = serializers.CharField(source='customer.email', read_only=True)
    vendor_name = serializers.CharField(source='vendor.business_name', read_only=True)
    
    class Meta:
        model = RepairOrder
        fields = [
            'id', 'customer_email', 'vendor_name', 'variant', 
            'total_amount', 'status', 'payment_method', 'created_at', 'updated_at'
        ]
        read_only_fields = fields


class RepairOrderDetailSerializer(serializers.ModelSerializer):
    """Serializer for order details."""
    
    variant = ServiceVariantSerializer(read_only=True)
    customer_email = serializers.CharField(source='customer.email', read_only=True)
    vendor_name = serializers.CharField(source='vendor.business_name', read_only=True)
    payment_url = serializers.SerializerMethodField()
    
    class Meta:
        model = RepairOrder
        fields = [
            'id', 'customer_email', 'vendor_name', 'variant', 
            'total_amount', 'status', 'payment_method', 'payment_url',
            'created_at', 'updated_at'
        ]
        read_only_fields = fields
    
    def get_payment_url(self, obj):
        """Return payment URL if order is pending payment."""
        if obj.status == RepairOrder.Status.PENDING:
            from payments.utils import create_stripe_payment_intent
            try:
                payment_url = create_stripe_payment_intent(obj)
                return payment_url
            except Exception:
                return None
        return None
