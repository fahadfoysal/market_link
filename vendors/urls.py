from django.urls import path
from .views import (
    VendorProfileCreateView,
    VendorProfileRetrieveView,
    VendorProfileUpdateView
)

app_name = 'vendors'

urlpatterns = [
    path('profile/', VendorProfileCreateView.as_view(), name='vendor-profile-create'),
    path('profile/me/', VendorProfileRetrieveView.as_view(), name='vendor-profile-retrieve'),
    path('profile/me/update/', VendorProfileUpdateView.as_view(), name='vendor-profile-update'),
]
