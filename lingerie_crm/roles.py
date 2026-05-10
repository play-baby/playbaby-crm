from django.contrib.auth.mixins import AccessMixin
from django.contrib import messages
from django.shortcuts import redirect

SALES_GROUP = 'sales'
SHIPPING_GROUP = 'shipping'
OWNER_GROUP = 'owner'

def is_sales(user):
    return user.is_authenticated and user.groups.filter(name=SALES_GROUP).exists()

def is_shipping(user):
    return user.is_authenticated and user.groups.filter(name=SHIPPING_GROUP).exists()

def is_owner(user):
    return user.is_authenticated and user.groups.filter(name=OWNER_GROUP).exists()

def is_any_role(user):
    return user.is_authenticated and user.groups.filter(name__in=[SALES_GROUP, SHIPPING_GROUP, OWNER_GROUP]).exists()

class SalesRequiredMixin(AccessMixin):
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not (is_sales(request.user) or is_owner(request.user)):
            messages.error(request, 'ليس لديك صلاحية للوصول إلى هذه الصفحة')
            return redirect('home')
        return super().dispatch(request, *args, **kwargs)

class ShippingRequiredMixin(AccessMixin):
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not (is_shipping(request.user) or is_sales(request.user) or is_owner(request.user)):
            messages.error(request, 'ليس لديك صلاحية للوصول إلى هذه الصفحة')
            return redirect('home')
        return super().dispatch(request, *args, **kwargs)

class OwnerRequiredMixin(AccessMixin):
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not is_owner(request.user):
            messages.error(request, 'ليس لديك صلاحية للوصول إلى هذه الصفحة')
            return redirect('home')
        return super().dispatch(request, *args, **kwargs)
