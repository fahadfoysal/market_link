from django.urls import path
from .views import stripe_webhook_view

app_name = 'payments'

urlpatterns = [
    # Stripe webhook endpoint
    path('webhooks/payment/', stripe_webhook_view, name='stripe-webhook'),
]
