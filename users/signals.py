from django.db.models.signals import post_save
from django.dispatch import receiver
from users.models import User
from .models import VendorProfile


@receiver(post_save, sender=User)
def create_vendor_profile(sender, instance, created, **kwargs):
    """Signal to create a VendorProfile when a new vendor user is created."""
    if created and instance.is_vendor:
        VendorProfile.objects.create(user=instance)