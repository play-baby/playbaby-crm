from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DetailView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.contrib import messages
from django.db.models import Sum
from .models import Customer
from .forms import CustomerForm
from utils import export_csv, export_xlsx, import_csv, import_xlsx
from lingerie_crm.roles import SalesRequiredMixin, OwnerRequiredMixin, is_sales, is_owner

SORT_MAP_CUSTOMER = {
    'name': 'name',
    'phone': 'phone',
    'total_amount': 'total_amount',
    'last_purchase': 'last_purchase_date',
    'created_at': 'created_at',
}

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
        sort = self.request.GET.get('sort', '')
        dir = self.request.GET.get('dir', '')
        if sort in SORT_MAP_CUSTOMER:
            field = SORT_MAP_CUSTOMER[sort]
            if dir == 'desc':
                field = '-' + field
            qs = qs.order_by(field)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['search'] = self.request.GET.get('search', '')
        ctx['sort'] = self.request.GET.get('sort', '')
        ctx['dir'] = self.request.GET.get('dir', '')
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
        from invoices.models import Invoice
        ctx['invoices'] = Invoice.objects.filter(customer=self.object).select_related('status', 'payment_method').order_by('-date')[:20]
        ctx['total_paid_invoices'] = ctx['invoices'].aggregate(Sum('paid_amount'))['paid_amount__sum'] or 0
        ctx['total_invoices_amount'] = ctx['invoices'].aggregate(Sum('total_amount'))['total_amount__sum'] or 0
        ctx['remaining_balance'] = ctx['total_invoices_amount'] - ctx['total_paid_invoices']
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
            from utils import _validate_file_upload
            _validate_file_upload(file)
            if fmt == 'csv':
                count = import_csv(file, Customer, CUSTOMER_FIELD_MAP)
            else:
                count = import_xlsx(file, Customer, CUSTOMER_FIELD_MAP)
            messages.success(request, f'تم استيراد {count} عميل بنجاح')
        except Exception as e:
            messages.error(request, f'خطأ في الاستيراد: {e}')
    return redirect('customer_list')
