from django.urls import path
from . import views

app_name = 'reports'

urlpatterns = [
    path('revenue/', views.revenue_report, name='report_revenue'),
    path('products/', views.products_report, name='report_products'),
    path('customers/', views.customers_report, name='report_customers'),
    path('status/', views.status_distribution_report, name='report_status'),
    path('shipping/', views.shipping_performance_report, name='report_shipping'),
    path('collection/', views.collection_report, name='report_collection'),
]
