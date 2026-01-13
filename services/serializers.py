from rest_framework import serializers
from .models import Service, ServiceVariant
from vendors.serializers import VendorProfileSerializer


class ServiceVariantSerializer(serializers.ModelSerializer):
    """Serializer for ServiceVariant model."""
    
    class Meta:
        model = ServiceVariant
        fields = ['id', 'service', 'name', 'price', 'estimated_minutes', 'stock', 'created_at', 'updated_at']
        read_only_fields = ['service']


class ServiceSerializer(serializers.ModelSerializer):
    """Serializer for Service model."""
    
    variants = ServiceVariantSerializer(many=True, read_only=True, source='servicevariant_set')
    vendor = VendorProfileSerializer(read_only=True)
    
    class Meta:
        model = Service
        fields = ['id', 'vendor', 'name', 'created_at', 'updated_at', 'variants']