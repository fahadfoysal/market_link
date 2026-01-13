from django.urls import path
from .views import (
    VendorProfileCreateView,
    VendorProfileRetrieveView,
    VendorProfileUpdateView
)

app_name = 'vendors'

urlpatterns = [
    path('vendors/profile/', VendorProfileCreateView.as_view(), name='vendor-profile-create'),
    path('vendors/profile/me/', VendorProfileRetrieveView.as_view(), name='vendor-profile-retrieve'),
    path('vendors/profile/me/update/', VendorProfileUpdateView.as_view(), name='vendor-profile-update'),
]
