from django.shortcuts import redirect
from django.urls import reverse
from core.models import RoleLanding
from lingerie_crm.roles import is_owner


class LandingPageMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated and request.path == reverse('home'):
            user_groups = request.user.groups.all()
            if not is_owner(request.user) and not request.user.is_superuser:
                for group in user_groups:
                    try:
                        rl = RoleLanding.objects.get(group=group)
                        if rl.dashboard_blocked:
                            dest = rl.landing_page or 'customer_list'
                            return redirect(dest)
                        if rl.landing_page:
                            return redirect(rl.landing_page)
                    except RoleLanding.DoesNotExist:
                        pass
        return self.get_response(request)
