from django.contrib import admin
from .models import Customer

@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ['name', 'phone', 'total_amount', 'last_purchase_date', 'created_at']
    search_fields = ['name', 'phone']
    list_filter = ['created_at']
