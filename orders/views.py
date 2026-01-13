from rest_framework import generics, permissions, status
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from users.permissions import IsCustomer, IsVerifiedVendor
from .models import RepairOrder
from .serializers import RepairOrderCreateSerializer, RepairOrderListSerializer, RepairOrderDetailSerializer


class CreateRepairOrderView(generics.CreateAPIView):
    """
    Create a new repair order.
    
    POST /api/orders/ - Customers only
    
    This endpoint:
    1. Validates the service variant exists and has stock
    2. Atomically reserves stock using Redis lock
    3. Creates a pending repair order
    4. Returns payment details for checkout
    """
    
    serializer_class = RepairOrderCreateSerializer
    permission_classes = [permissions.IsAuthenticated, IsCustomer]
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context
    
    def create(self, request, *args, **kwargs):
        """Create order with custom response."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order = serializer.save()
        
        response_serializer = RepairOrderDetailSerializer(order, context={'request': request})
        return Response(
            {
                'success': True,
                'message': 'Repair order created successfully. Proceed to payment.',
                'data': response_serializer.data
            },
            status=status.HTTP_201_CREATED
        )


class ListCustomerOrdersView(generics.ListAPIView):
    """
    List all repair orders for the authenticated customer.
    
    GET /api/orders/my/ - Customers only
    """
    
    serializer_class = RepairOrderListSerializer
    permission_classes = [permissions.IsAuthenticated, IsCustomer]
    
    def get_queryset(self):
        """Return only orders for the authenticated customer."""
        return RepairOrder.objects.filter(customer=self.request.user)
    
    def list(self, request, *args, **kwargs):
        """List customer orders with custom response."""
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        
        return Response(
            {
                'success': True,
                'message': 'Orders retrieved successfully',
                'data': serializer.data
            },
            status=status.HTTP_200_OK
        )


class ListVendorOrdersView(generics.ListAPIView):
    """
    List all repair orders for the authenticated vendor's services.
    
    GET /api/orders/vendor/ - Vendors only
    """
    
    serializer_class = RepairOrderListSerializer
    permission_classes = [permissions.IsAuthenticated, IsVerifiedVendor]
    
    def get_queryset(self):
        """Return only orders for the authenticated vendor's services."""
        return RepairOrder.objects.filter(vendor=self.request.user.vendorprofile)
    
    def list(self, request, *args, **kwargs):
        """List vendor orders with custom response."""
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        
        return Response(
            {
                'success': True,
                'message': 'Vendor orders retrieved successfully',
                'data': serializer.data
            },
            status=status.HTTP_200_OK
        )


class RetrieveOrderView(generics.RetrieveAPIView):
    """
    Retrieve details of a specific repair order.
    
    GET /api/orders/{id}/ - Authenticated users
    
    Customers can only see their own orders.
    Vendors can only see orders for their services.
    """
    
    serializer_class = RepairOrderDetailSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'id'
    queryset = RepairOrder.objects.all()
    
    def get_object(self):
        """Get order with permission check."""
        obj = super().get_object()
        
        # Check permissions
        if self.request.user.role == 'CUSTOMER':
            if obj.customer != self.request.user:
                self.permission_denied(self.request)
        elif self.request.user.role == 'VENDOR':
            if obj.vendor != self.request.user.vendorprofile:
                self.permission_denied(self.request)
        
        return obj
    
    def retrieve(self, request, *args, **kwargs):
        """Retrieve order with custom response."""
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        
        return Response(
            {
                'success': True,
                'message': 'Order retrieved successfully',
                'data': serializer.data
            },
            status=status.HTTP_200_OK
        )


class PaymentSuccessView(generics.GenericAPIView):
    """Return a simple success response after Stripe redirects back."""

    permission_classes = [permissions.AllowAny]
    lookup_field = 'id'
    queryset = RepairOrder.objects.all()

    def get(self, request, *args, **kwargs):
        order = get_object_or_404(RepairOrder, id=self.kwargs['id'])
        return Response(
            {
                'success': True,
                'message': 'Payment successful. Your order is being processed.',
                'data': {
                    'order_id': str(order.id),
                    'status': order.status,
                },
            },
            status=status.HTTP_200_OK,
        )


class PaymentCancelView(generics.GenericAPIView):
    """Return a simple cancelled response after Stripe redirects back."""

    permission_classes = [permissions.AllowAny]
    lookup_field = 'id'
    queryset = RepairOrder.objects.all()

    def get(self, request, *args, **kwargs):
        order = get_object_or_404(RepairOrder, id=self.kwargs['id'])
        return Response(
            {
                'success': False,
                'message': 'Payment was cancelled. Your order is still pending.',
                'data': {
                    'order_id': str(order.id),
                    'status': order.status,
                },
            },
            status=status.HTTP_200_OK,
        )
