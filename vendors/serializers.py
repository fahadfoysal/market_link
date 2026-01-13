from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import VendorProfile

User = get_user_model()

class VendorProfileSerializer(serializers.ModelSerializer):
    """Serializer for VendorProfile model."""
    
    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())
    
    class Meta:
        model = VendorProfile
        fields = ('id', 'user', 'business_name', 'address', 'is_active', 'created_at', 'updated_at')
        read_only_fields = ('id', 'created_at', 'updated_at')