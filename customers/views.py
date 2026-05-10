from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DetailView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.contrib import messages
from .models import Customer
from .forms import CustomerForm
from utils import export_csv, export_xlsx, import_csv, import_xlsx
from lingerie_crm.roles import SalesRequiredMixin, OwnerRequiredMixin, is_sales, is_owner

class CustomerListView(LoginRequiredMixin, ListView):
    model = Customer
    template_name = 'customers/customer_list.html'
    context_object_name = 'customers'
    paginate_by = 20

    def get_queryset(self):
        qs = super().get_queryset()
        search = self.request.GET.get('search', '')
        if search:
            qs = qs.filter(name__icontains=search) | qs.filter(phone__icontains=search)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['search'] = self.request.GET.get('search', '')
        ctx['page_title'] = 'قائمة العملاء'
        return ctx

class CustomerCreateView(SalesRequiredMixin, CreateView):
    model = Customer
    form_class = CustomerForm
    template_name = 'customers/customer_form.html'
    success_url = reverse_lazy('customer_list')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['page_title'] = 'إضافة عميل جديد'
        return ctx

class CustomerUpdateView(SalesRequiredMixin, UpdateView):
    model = Customer
    form_class = CustomerForm
    template_name = 'customers/customer_form.html'
    success_url = reverse_lazy('customer_list')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['page_title'] = 'تعديل بيانات العميل'
        return ctx

class CustomerDetailView(LoginRequiredMixin, DetailView):
    model = Customer
    template_name = 'customers/customer_detail.html'
    context_object_name = 'customer'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['page_title'] = self.object.name
        return ctx

class CustomerDeleteView(OwnerRequiredMixin, DeleteView):
    model = Customer
    template_name = 'customers/customer_confirm_delete.html'
    success_url = reverse_lazy('customer_list')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['page_title'] = 'حذف عميل'
        ctx['is_owner'] = True
        ctx['is_sales'] = True
        ctx['is_shipping'] = False
        return ctx

# --- Import / Export ---
CUSTOMER_FIELDS = [
    Customer._meta.get_field('name'),
    Customer._meta.get_field('phone'),
    Customer._meta.get_field('email'),
    Customer._meta.get_field('address'),
    Customer._meta.get_field('total_amount'),
    Customer._meta.get_field('notes'),
]

CUSTOMER_FIELD_MAP = {
    'الاسم': 'name',
    'رقم الهاتف': 'phone',
    'البريد الإلكتروني': 'email',
    'العنوان': 'address',
    'إجمالي المشتريات': 'total_amount',
    'ملاحظات': 'notes',
}

@login_required
def export_customers_csv(request):
    if not (is_sales(request.user) or is_owner(request.user)):
        messages.error(request, 'ليس لديك صلاحية')
        return redirect('home')
    return export_csv(Customer, CUSTOMER_FIELDS, 'العملاء')

@login_required
def export_customers_xlsx(request):
    if not (is_sales(request.user) or is_owner(request.user)):
        messages.error(request, 'ليس لديك صلاحية')
        return redirect('home')
    return export_xlsx(Customer, CUSTOMER_FIELDS, 'العملاء')

@login_required
def import_customers(request):
    if not (is_sales(request.user) or is_owner(request.user)):
        messages.error(request, 'ليس لديك صلاحية')
        return redirect('home')
    if request.method == 'POST' and request.FILES.get('file'):
        file = request.FILES['file']
        fmt = request.POST.get('format', 'csv')
        try:
            if fmt == 'csv':
                count = import_csv(file, Customer, CUSTOMER_FIELD_MAP)
            else:
                count = import_xlsx(file, Customer, CUSTOMER_FIELD_MAP)
            messages.success(request, f'تم استيراد {count} عميل بنجاح')
        except Exception as e:
            messages.error(request, f'خطأ في الاستيراد: {e}')
    return redirect('customer_list')
