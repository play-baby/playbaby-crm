from django.contrib import admin
from .models import Invoice, InvoiceItem, InvoiceStatus, PaymentMethod, InvoiceStatusLog

admin.site.register(InvoiceStatus)
admin.site.register(PaymentMethod)
admin.site.register(InvoiceStatusLog)

class InvoiceItemInline(admin.TabularInline):
    model = InvoiceItem
    extra = 1

@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    inlines = [InvoiceItemInline]
    list_display = ['invoice_number', 'customer', 'date', 'total_amount', 'discount_percent', 'status', 'payment_method']
