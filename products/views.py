from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DetailView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.contrib import messages
from .models import Product
from .forms import ProductForm
from utils import export_csv, export_xlsx, import_csv, import_xlsx
from lingerie_crm.roles import SalesRequiredMixin, OwnerRequiredMixin, is_sales, is_owner

class ProductListView(LoginRequiredMixin, ListView):
    model = Product
    template_name = 'products/product_list.html'
    context_object_name = 'products'
    paginate_by = 20

    def get_queryset(self):
        qs = super().get_queryset()
        search = self.request.GET.get('search', '')
        if search:
            qs = qs.filter(name__icontains=search)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['search'] = self.request.GET.get('search', '')
        ctx['page_title'] = 'قائمة المنتجات'
        ctx['is_sales'] = is_sales(self.request.user) or is_owner(self.request.user)
        return ctx

class ProductCreateView(SalesRequiredMixin, CreateView):
    model = Product
    form_class = ProductForm
    template_name = 'products/product_form.html'
    success_url = reverse_lazy('product_list')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['page_title'] = 'إضافة منتج جديد'
        return ctx

class ProductUpdateView(SalesRequiredMixin, UpdateView):
    model = Product
    form_class = ProductForm
    template_name = 'products/product_form.html'
    success_url = reverse_lazy('product_list')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['page_title'] = 'تعديل المنتج'
        return ctx

class ProductDetailView(LoginRequiredMixin, DetailView):
    model = Product
    template_name = 'products/product_detail.html'
    context_object_name = 'product'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['page_title'] = self.object.name
        ctx['is_sales'] = is_sales(self.request.user) or is_owner(self.request.user)
        return ctx

class ProductDeleteView(OwnerRequiredMixin, DeleteView):
    model = Product
    template_name = 'products/product_confirm_delete.html'
    success_url = reverse_lazy('product_list')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['page_title'] = 'حذف منتج'
        ctx['is_owner'] = True
        ctx['is_sales'] = True
        ctx['is_shipping'] = False
        return ctx

# --- Import / Export ---
PRODUCT_FIELDS = [
    Product._meta.get_field('name'),
    Product._meta.get_field('category'),
    Product._meta.get_field('price'),
    Product._meta.get_field('cost'),
    Product._meta.get_field('quantity'),
    Product._meta.get_field('description'),
]

PRODUCT_FIELD_MAP = {
    'اسم المنتج': 'name',
    'التصنيف': 'category',
    'السعر': 'price',
    'التكلفة': 'cost',
    'الكمية': 'quantity',
    'الوصف': 'description',
}

@login_required
def export_products_csv(request):
    if not (is_sales(request.user) or is_owner(request.user)):
        messages.error(request, 'ليس لديك صلاحية')
        return redirect('home')
    return export_csv(Product, PRODUCT_FIELDS, 'المنتجات')

@login_required
def export_products_xlsx(request):
    if not (is_sales(request.user) or is_owner(request.user)):
        messages.error(request, 'ليس لديك صلاحية')
        return redirect('home')
    return export_xlsx(Product, PRODUCT_FIELDS, 'المنتجات')

@login_required
def import_products(request):
    if not (is_sales(request.user) or is_owner(request.user)):
        messages.error(request, 'ليس لديك صلاحية')
        return redirect('home')
    if request.method == 'POST' and request.FILES.get('file'):
        file = request.FILES['file']
        fmt = request.POST.get('format', 'csv')
        try:
            if fmt == 'csv':
                count = import_csv(file, Product, PRODUCT_FIELD_MAP)
            else:
                count = import_xlsx(file, Product, PRODUCT_FIELD_MAP)
            messages.success(request, f'تم استيراد {count} منتج بنجاح')
        except Exception as e:
            messages.error(request, f'خطأ في الاستيراد: {e}')
    return redirect('product_list')
