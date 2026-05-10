from django.contrib import admin
from .models import Invoice, InvoiceItem, InvoiceStatus, PaymentMethod, InvoiceStatusLog, Notification

admin.site.register(InvoiceStatus)
admin.site.register(PaymentMethod)
admin.site.register(InvoiceStatusLog)


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['invoice', 'sender', 'recipient', 'notification_type', 'is_read', 'created_at']
    list_filter = ['notification_type', 'is_read', 'created_at']
    search_fields = ['invoice__invoice_number', 'recipient__username']

class InvoiceItemInline(admin.TabularInline):
    model = InvoiceItem
    extra = 1

@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    inlines = [InvoiceItemInline]
    list_display = ['invoice_number', 'customer', 'date', 'total_amount', 'discount_percent', 'status', 'payment_method']
