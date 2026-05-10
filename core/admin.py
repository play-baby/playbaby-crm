from django.contrib import admin
from django.contrib.auth.models import Group
from django.shortcuts import redirect
from django.urls import reverse
from django.contrib import messages
from .models import SiteSetting, InvoiceTemplate, RoleLanding

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


@admin.register(RoleLanding)
class RoleLandingAdmin(admin.ModelAdmin):
    list_display = ('group', 'landing_page', 'dashboard_blocked')
    list_editable = ('landing_page', 'dashboard_blocked')

    def has_add_permission(self, request):
        return False if RoleLanding.objects.count() >= Group.objects.count() else True

    def changelist_view(self, request, extra_context=None):
        for group in Group.objects.all():
            RoleLanding.objects.get_or_create(group=group)
        return super().changelist_view(request, extra_context=extra_context)
