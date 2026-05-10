from datetime import datetime
from core.models import SiteSetting, InvoiceTemplate
from lingerie_crm.roles import is_owner, is_sales, is_shipping

def site_settings(request):
    setting = SiteSetting.get()
    tmpl = InvoiceTemplate.get()
    user = request.user
    return {
        'site_name': 'Play Baby Lingerie',
        'site_short_name': 'Play Baby CRM',
        'current_year': datetime.now().year,
        'site_logo': setting.logo.url if setting and setting.logo else None,
        'site_website': setting.website if setting and setting.website else None,
        'is_owner': user.is_authenticated and (is_owner(user) or user.is_superuser),
        'is_sales': user.is_authenticated and (is_sales(user) or is_owner(user) or user.is_superuser),
        'is_shipping': user.is_authenticated and is_shipping(user) and not is_owner(user) and not user.is_superuser,
        'invoice_template': tmpl,
    }
