from django.urls import path
from . import views

urlpatterns = [
    path('', views.InvoiceListView.as_view(), name='invoice_list'),
    path('add/', views.InvoiceCreateView.as_view(), name='invoice_add'),
    path('<int:pk>/', views.InvoiceDetailView.as_view(), name='invoice_detail'),
    path('<int:pk>/print/', views.InvoicePrintView.as_view(), name='invoice_print'),
    path('<int:pk>/edit/', views.InvoiceUpdateView.as_view(), name='invoice_edit'),
    path('<int:pk>/delete/', views.InvoiceDeleteView.as_view(), name='invoice_delete'),
    path('api/product/', views.get_product_json, name='invoice_product_json'),
    path('<int:pk>/update-status/', views.update_invoice_status, name='update_invoice_status'),
    path('<int:pk>/cancel/', views.cancel_invoice, name='cancel_invoice'),
    path('export/csv/', views.export_invoices_csv, name='invoice_export_csv'),
    path('export/xlsx/', views.export_invoices_xlsx, name='invoice_export_xlsx'),
    path('import/', views.import_invoices, name='invoice_import'),
    # Settings: Invoice Statuses
    path('settings/status/', views.InvoiceStatusListView.as_view(), name='invoice_status_list'),
    path('settings/status/add/', views.InvoiceStatusCreateView.as_view(), name='invoice_status_add'),
    path('settings/status/<int:pk>/edit/', views.InvoiceStatusUpdateView.as_view(), name='invoice_status_edit'),
    path('settings/status/<int:pk>/delete/', views.InvoiceStatusDeleteView.as_view(), name='invoice_status_delete'),
    # Settings: Invoice Template Design
    path('settings/template/', views.InvoiceTemplateUpdateView.as_view(), name='invoice_template_edit'),
    # Settings: Payment Methods
    path('settings/payment/', views.PaymentMethodListView.as_view(), name='payment_method_list'),
    path('settings/payment/add/', views.PaymentMethodCreateView.as_view(), name='payment_method_add'),
    path('settings/payment/<int:pk>/edit/', views.PaymentMethodUpdateView.as_view(), name='payment_method_edit'),
    path('settings/payment/<int:pk>/delete/', views.PaymentMethodDeleteView.as_view(), name='payment_method_delete'),
    # Notifications
    path('notifications/', views.notification_list, name='notification_list'),
    path('notifications/<int:pk>/read/', views.notification_mark_read, name='notification_mark_read'),
    path('notifications/read-all/', views.notification_mark_all_read, name='notification_mark_all_read'),
    # Shipping availability
    path('<int:pk>/confirm-availability/', views.confirm_availability, name='confirm_availability'),
    path('<int:pk>/approve-revision/', views.approve_revision, name='approve_revision'),
]
