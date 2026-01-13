from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.exceptions import NotFound
from users.permissions import IsVendor, IsVerifiedVendor, IsCustomer
from .models import Service, ServiceVariant
from .serializers import ServiceSerializer, ServiceVariantSerializer


class ListCreateServiceView(generics.ListCreateAPIView):
    """
    List all services (public) or create a new service (vendor).
    
    GET /api/services/ - Public, list all services
    POST /api/services/ - Vendor only, create service
    """
    
    serializer_class = ServiceSerializer
    
    def get_permissions(self):
        """
        Allow GET for everyone, POST for verified vendors only.
        """
        if self.request.method == 'GET':
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated(), IsVerifiedVendor()]
    
    def get_queryset(self):
        """Return all services for GET, empty for POST."""
        if self.request.method == 'GET':
            return Service.objects.all()
        return Service.objects.none()
    
    def list(self, request, *args, **kwargs):
        """List services with custom response."""
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        
        return Response(
            {
                'success': True,
                'message': 'Services retrieved successfully',
                'data': serializer.data
            },
            status=status.HTTP_200_OK
        )
    
    def create(self, request, *args, **kwargs):
        """Create service with custom response."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        service = serializer.save(vendor=request.user.vendorprofile)
        
        response_serializer = ServiceSerializer(service)
        return Response(
            {
                'success': True,
                'message': 'Service created successfully',
                'data': response_serializer.data
            },
            status=status.HTTP_201_CREATED
        )


class RetrieveUpdateDeleteServiceView(generics.RetrieveAPIView, generics.UpdateAPIView, generics.DestroyAPIView):
    """
    Retrieve, update, or delete a service.
    
    GET /api/services/{id}/ - Public, retrieve service details
    PATCH /api/services/{id}/ - Vendor only, update own service
    DELETE /api/services/{id}/ - Vendor only, delete own service
    """
    
    serializer_class = ServiceSerializer
    lookup_field = 'id'
    http_method_names = ['get', 'patch', 'delete', 'options', 'head']
    
    def get_permissions(self):
        """Allow GET for everyone, PATCH/DELETE for verified vendors only."""
        if self.request.method == 'GET':
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated(), IsVerifiedVendor()]
    
    def get_queryset(self):
        """Return all services for GET, vendor's services for PATCH/DELETE."""
        if self.request.method == 'GET':
            return Service.objects.all()
        return Service.objects.filter(vendor=self.request.user.vendorprofile)
    
    def retrieve(self, request, *args, **kwargs):
        """Retrieve service with custom response."""
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        
        return Response(
            {
                'success': True,
                'message': 'Service retrieved successfully',
                'data': serializer.data
            },
            status=status.HTTP_200_OK
        )
    
    def partial_update(self, request, *args, **kwargs):
        """Update service with custom response."""
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        
        response_serializer = ServiceSerializer(instance)
        return Response(
            {
                'success': True,
                'message': 'Service updated successfully',
                'data': response_serializer.data
            },
            status=status.HTTP_200_OK
        )
    
    def destroy(self, request, *args, **kwargs):
        """Delete service with custom response."""
        instance = self.get_object()
        self.perform_destroy(instance)
        
        return Response(
            {
                'success': True,
                'message': 'Service deleted successfully'
            },
            status=status.HTTP_204_NO_CONTENT
        )


class ListCreateServiceVariantView(generics.ListCreateAPIView):
    """
    List all service variants for a specific service or create a new variant.
    
    GET /api/services/{id}/variants/ - Public, list variants
    POST /api/services/{id}/variants/ - Vendor only, create variant
    """
    
    serializer_class = ServiceVariantSerializer
    
    def get_permissions(self):
        """Allow GET for everyone, POST for verified vendors only."""
        if self.request.method == 'GET':
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated(), IsVerifiedVendor()]
    
    def get_queryset(self):
        """Return service variants for the specified service."""
        service_id = self.kwargs['id']
        return ServiceVariant.objects.filter(service__id=service_id)
    
    def list(self, request, *args, **kwargs):
        """List service variants with custom response."""
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        
        return Response(
            {
                'success': True,
                'message': 'Service variants retrieved successfully',
                'data': serializer.data
            },
            status=status.HTTP_200_OK
        )
    
    def create(self, request, *args, **kwargs):
        """Create service variant with custom response."""
        service_id = self.kwargs['id']
        
        # Verify vendor owns this service
        try:
            service = Service.objects.get(id=service_id, vendor=request.user.vendorprofile)
        except Service.DoesNotExist:
            return Response(
                {
                    'success': False,
                    'message': 'Service not found or you do not own this service',
                    'data': None
                },
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        service_variant = serializer.save(service_id=service_id)
        
        response_serializer = ServiceVariantSerializer(service_variant)
        return Response(
            {
                'success': True,
                'message': 'Service variant created successfully',
                'data': response_serializer.data
            },
            status=status.HTTP_201_CREATED
        )


class ListVendorServicesView(generics.ListAPIView):
    """
    List all services of the authenticated verified vendor.
    
    GET /api/services/my/
    """
    
    serializer_class = ServiceSerializer
    permission_classes = [permissions.IsAuthenticated, IsVerifiedVendor]
    
    def get_queryset(self):
        """Return services owned by the authenticated vendor."""
        return Service.objects.filter(vendor=self.request.user.vendorprofile)
    
    def list(self, request, *args, **kwargs):
        """List vendor services with custom response."""
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        
        return Response(
            {
                'success': True,
                'message': 'Your services retrieved successfully',
                'data': serializer.data
            },
            status=status.HTTP_200_OK
        )


class UpdateDeleteServiceVariantView(generics.UpdateAPIView, generics.DestroyAPIView):
    """
    Update or delete a service variant owned by the authenticated verified vendor.
    
    PATCH /api/variants/{id}/
    DELETE /api/variants/{id}/
    """
    
    serializer_class = ServiceVariantSerializer
    permission_classes = [permissions.IsAuthenticated, IsVerifiedVendor]
    lookup_field = 'id'
    http_method_names = ['patch', 'delete', 'options', 'head']
    
    def get_queryset(self):
        """Return service variants owned by the authenticated vendor."""
        return ServiceVariant.objects.filter(service__vendor=self.request.user.vendorprofile)
    
    def partial_update(self, request, *args, **kwargs):
        """Update service variant with custom response."""
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        
        response_serializer = ServiceVariantSerializer(instance)
        return Response(
            {
                'success': True,
                'message': 'Service variant updated successfully',
                'data': response_serializer.data
            },
            status=status.HTTP_200_OK
        )
    
    def destroy(self, request, *args, **kwargs):
        """Delete service variant with custom response."""
        instance = self.get_object()
        self.perform_destroy(instance)
        
        return Response(
            {
                'success': True,
                'message': 'Service variant deleted successfully'
            },
            status=status.HTTP_204_NO_CONTENT
        )


class ServiceVariantAvailabilityView(generics.RetrieveAPIView):
    """
    Get availability status of a specific service variant (requires customer role).
    
    GET /api/variants/{id}/availability/
    """
    
    queryset = ServiceVariant.objects.all()
    serializer_class = ServiceVariantSerializer
    permission_classes = [permissions.IsAuthenticated, IsCustomer]
    lookup_field = 'id'
    
    def retrieve(self, request, *args, **kwargs):
        """Retrieve variant availability with custom response."""
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        
        return Response(
            {
                'success': True,
                'message': 'Service variant availability retrieved successfully',
                'data': {
                    **serializer.data,
                    'is_available': instance.stock > 0,
                    'available_stock': instance.stock
                }
            },
            status=status.HTTP_200_OK
        )