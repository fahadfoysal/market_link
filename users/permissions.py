from rest_framework.permissions import BasePermission, SAFE_METHODS

# Base Permissions

class IsAuthenticatedAndActive(BasePermission):
    """
    Allows access only to authenticated and active users.
    """

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.is_active
        )


class HasRole(BasePermission):
    """
    Base class for role-based permissions.
    """
    allowed_roles = []

    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and request.user.role in self.allowed_roles
        )


# Role-Based Permissions

class IsCustomer(HasRole):
    """Allows access only to customers."""
    allowed_roles = ["CUSTOMER"]


class IsVendor(HasRole):
    """Allows access only to vendors."""
    allowed_roles = ["VENDOR"]


class IsAdmin(HasRole):
    """Allows access only to admins."""
    allowed_roles = ["ADMIN"]


# Vendor-Specific Permissions

class IsVerifiedVendor(BasePermission):
    """
    Vendor must:
    - be authenticated
    - have vendor role
    - have an active VendorProfile
    """

    def has_permission(self, request, view):
        user = request.user

        return (
            user.is_authenticated
            and user.role == "VENDOR"
            and hasattr(user, "vendorprofile")
            and user.vendorprofile.is_active
        )


# Object-Level Permissions

class IsOwnerOrReadOnly(BasePermission):
    """
    Object-level permission to allow only owners to edit objects.
    Read-only access for everyone else.
    Assumes the object has a `user` field.
    """

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        return obj.user == request.user


class IsOwner(BasePermission):
    """
    Object-level permission to allow only owners (no read-only access).
    Assumes the object has a `user` attribute.
    """
    
    def has_object_permission(self, request, view, obj):
        return obj.user == request.user


class IsVendorOwner(BasePermission):
    """
    Vendor can only access objects belonging to their vendor profile.
    Assumes object has a `vendor` FK and vendor has a `user` FK.
    """
    
    def has_permission(self, request, view):
        """Check if user is authenticated and is a vendor."""
        return (
            request.user.is_authenticated
            and request.user.role == "VENDOR"
        )

    def has_object_permission(self, request, view, obj):
        """Check if vendor owns the object."""
        return obj.vendor.user == request.user
    

# Combined Permissions

class IsCustomerOrVendor(HasRole):
    """Allows access to both customers and vendors."""
    allowed_roles = ["CUSTOMER", "VENDOR"]


class IsVendorOrAdmin(HasRole):
    """Allows access to vendors and admins."""
    allowed_roles = ["VENDOR", "ADMIN"]

