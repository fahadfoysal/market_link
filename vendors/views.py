from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.exceptions import NotFound
from users.permissions import IsVendor
from .models import VendorProfile
from .serializers import (
    VendorProfileSerializer,
    VendorProfileCreateSerializer,
    VendorProfileUpdateSerializer
)


class VendorProfileCreateView(generics.CreateAPIView):
    """
    Create vendor profile for authenticated vendor user.
    
    POST /api/vendors/profile/
    """
    
    serializer_class = VendorProfileCreateSerializer
    permission_classes = [permissions.IsAuthenticated, IsVendor]
    
    def create(self, request, *args, **kwargs):
        """Create vendor profile with custom response."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        vendor_profile = serializer.save()
        
        # Return full profile details with success message
        response_serializer = VendorProfileSerializer(vendor_profile)
        return Response(
            {
                'success': True,
                'message': 'Vendor profile created successfully',
                'data': response_serializer.data
            },
            status=status.HTTP_201_CREATED
        )


class VendorProfileRetrieveView(generics.RetrieveAPIView):
    """
    Retrieve vendor profile for authenticated vendor user.
    
    GET /api/vendors/profile/
    """
    
    serializer_class = VendorProfileSerializer
    permission_classes = [permissions.IsAuthenticated, IsVendor]
    
    def get_object(self):
        """Get vendor profile for the authenticated user."""
        try:
            return VendorProfile.objects.get(user=self.request.user)
        except VendorProfile.DoesNotExist:
            raise NotFound({
                'success': False,
                'message': 'Vendor profile not found. Please create one first.',
                'data': None
            })
    
    def retrieve(self, request, *args, **kwargs):
        """Retrieve vendor profile with custom response."""
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        
        return Response(
            {
                'success': True,
                'message': 'Vendor profile retrieved successfully',
                'data': serializer.data
            },
            status=status.HTTP_200_OK
        )


class VendorProfileUpdateView(generics.UpdateAPIView):
    """
    Update vendor profile for authenticated vendor user.
    
    PATCH /api/vendors/profile/
    PUT /api/vendors/profile/
    """
    
    serializer_class = VendorProfileUpdateSerializer
    permission_classes = [permissions.IsAuthenticated, IsVendor]
    http_method_names = ['patch', 'put', 'options', 'head']
    
    def get_object(self):
        """Get vendor profile for the authenticated user."""
        try:
            return VendorProfile.objects.get(user=self.request.user)
        except VendorProfile.DoesNotExist:
            raise NotFound({
                'success': False,
                'message': 'Vendor profile not found. Please create one first.',
                'data': None
            })
    
    def update(self, request, *args, **kwargs):
        """Update vendor profile with custom response."""
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        
        # Return full profile details with success message
        response_serializer = VendorProfileSerializer(instance)
        return Response(
            {
                'success': True,
                'message': 'Vendor profile updated successfully',
                'data': response_serializer.data
            },
            status=status.HTTP_200_OK
        )
    
    def partial_update(self, request, *args, **kwargs):
        """Handle PATCH requests."""
        kwargs['partial'] = True
        return self.update(request, *args, **kwargs)