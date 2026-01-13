from django.urls import path
from .views import (
    # Public and vendor service endpoints
    ListCreateServiceView,
    RetrieveUpdateDeleteServiceView,
    ListCreateServiceVariantView,
    # Vendor service management
    ListVendorServicesView,
    UpdateDeleteServiceVariantView,
    # Customer views
    ServiceVariantAvailabilityView
)

app_name = 'services'

urlpatterns = [
    # More specific paths first (to prevent <uuid:id> from catching them)
    path('my/', ListVendorServicesView.as_view(), name='vendor-services'),
    path('variants/<uuid:id>/availability/', ServiceVariantAvailabilityView.as_view(), name='variant-availability'),
    path('variants/<uuid:id>/', UpdateDeleteServiceVariantView.as_view(), name='variant-update-delete'),
    
    # Service variant operations (GET list + POST create combined)
    path('<uuid:id>/variants/', ListCreateServiceVariantView.as_view(), name='service-variants'),
    
    # Single service operations (GET/PATCH/DELETE combined)
    path('<uuid:id>/', RetrieveUpdateDeleteServiceView.as_view(), name='service-detail'),
    
    # Base service endpoints (list all + create)
    path('', ListCreateServiceView.as_view(), name='service-list-create'),
]
