from django.urls import path
from .views import (
    CreateRepairOrderView,
    ListCustomerOrdersView,
    ListVendorOrdersView,
    RetrieveOrderView
)

app_name = 'orders'

urlpatterns = [
    # Create repair order
    path('', CreateRepairOrderView.as_view(), name='create-order'),
    
    # Customer views
    path('my/', ListCustomerOrdersView.as_view(), name='customer-orders'),
    
    # Vendor views
    path('vendor/', ListVendorOrdersView.as_view(), name='vendor-orders'),
    
    # Order details
    path('<uuid:id>/', RetrieveOrderView.as_view(), name='order-detail'),
]
