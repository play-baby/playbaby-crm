from django.urls import path
from . import views

urlpatterns = [
    path('', views.ProductListView.as_view(), name='product_list'),
    path('add/', views.ProductCreateView.as_view(), name='product_add'),
    path('<int:pk>/', views.ProductDetailView.as_view(), name='product_detail'),
    path('<int:pk>/edit/', views.ProductUpdateView.as_view(), name='product_edit'),
    path('<int:pk>/delete/', views.ProductDeleteView.as_view(), name='product_delete'),
    path('export/csv/', views.export_products_csv, name='product_export_csv'),
    path('export/xlsx/', views.export_products_xlsx, name='product_export_xlsx'),
    path('import/', views.import_products, name='product_import'),
]
