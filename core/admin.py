from django.contrib import admin
from .models import SiteSetting, InvoiceTemplate

@admin.register(SiteSetting)
class SiteSettingAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False if SiteSetting.objects.exists() else True

    def has_delete_permission(self, request, obj=None):
        return False

@admin.register(InvoiceTemplate)
class InvoiceTemplateAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False if InvoiceTemplate.objects.exists() else True

    def has_delete_permission(self, request, obj=None):
        return False
