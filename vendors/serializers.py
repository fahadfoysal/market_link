from rest_framework import serializers
from .models import VendorProfile
from users.serializers import UserSerializer


class VendorProfileSerializer(serializers.ModelSerializer):
    """Serializer for vendor profile."""
    
    user = UserSerializer(read_only=True)
    
    class Meta:
        model = VendorProfile
        fields = ['id', 'user', 'business_name', 'address', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'user', 'created_at', 'updated_at']


class VendorProfileCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating vendor profile."""
    
    class Meta:
        model = VendorProfile
        fields = ['business_name', 'address']
    
    def validate(self, attrs):
        """Validate that user doesn't already have a vendor profile."""
        user = self.context['request'].user
        if VendorProfile.objects.filter(user=user).exists():
            raise serializers.ValidationError("Vendor profile already exists for this user.")
        return attrs
    
    def create(self, validated_data):
        """Create vendor profile for authenticated user."""
        user = self.context['request'].user
        vendor_profile = VendorProfile.objects.create(user=user, **validated_data)
        return vendor_profile


class VendorProfileUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating vendor profile."""
    
    class Meta:
        model = VendorProfile
        fields = ['business_name', 'address', 'is_active']