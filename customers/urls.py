from django.urls import path
from . import views

urlpatterns = [
    path('', views.CustomerListView.as_view(), name='customer_list'),
    path('add/', views.CustomerCreateView.as_view(), name='customer_add'),
    path('<int:pk>/', views.CustomerDetailView.as_view(), name='customer_detail'),
    path('<int:pk>/edit/', views.CustomerUpdateView.as_view(), name='customer_edit'),
    path('<int:pk>/delete/', views.CustomerDeleteView.as_view(), name='customer_delete'),
    path('export/csv/', views.export_customers_csv, name='customer_export_csv'),
    path('export/xlsx/', views.export_customers_xlsx, name='customer_export_xlsx'),
    path('import/', views.import_customers, name='customer_import'),
]
