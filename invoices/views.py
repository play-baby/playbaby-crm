from django.urls import reverse_lazy, reverse
from django.views.generic import ListView, DetailView, DeleteView, TemplateView
from django.views.generic.edit import CreateView, UpdateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse
from django.utils.timezone import now
from .models import Invoice, InvoiceItem, InvoiceStatus, InvoiceStatusLog, PaymentMethod
from .forms import InvoiceForm, InvoiceItemFormSet, InvoiceStatusForm, PaymentMethodForm, InvoiceTemplateForm
from core.models import InvoiceTemplate
from products.models import Product
from utils import export_csv, export_xlsx, import_csv, import_xlsx
from lingerie_crm.roles import SalesRequiredMixin, ShippingRequiredMixin, OwnerRequiredMixin, is_sales, is_owner, is_shipping

SORT_MAP_INVOICE = {
    'invoice_number': 'invoice_number',
    'customer': 'customer__name',
    'date': 'date',
    'status': 'status__order',
    'payment_method': 'payment_method__name',
    'total_amount': 'total_amount',
    'paid_amount': 'paid_amount',
    'remaining': 'remaining_amount',
    'created_by': 'created_by__username',
}

class InvoiceListView(LoginRequiredMixin, ListView):
    model = Invoice
    template_name = 'invoices/invoice_list.html'
    context_object_name = 'invoices'
    paginate_by = 20

    def get_queryset(self):
        qs = super().get_queryset().select_related('created_by', 'customer', 'status', 'payment_method')
        search = self.request.GET.get('search', '')
        if search:
            qs = qs.filter(invoice_number__icontains=search) | qs.filter(customer__name__icontains=search)
        sort = self.request.GET.get('sort', '')
        dir = self.request.GET.get('dir', '')
        if sort in SORT_MAP_INVOICE:
            field = SORT_MAP_INVOICE[sort]
            if dir == 'desc':
                field = '-' + field
            qs = qs.order_by(field)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['search'] = self.request.GET.get('search', '')
        ctx['sort'] = self.request.GET.get('sort', '')
        ctx['dir'] = self.request.GET.get('dir', '')
        ctx['page_title'] = 'قائمة الفواتير'
        return ctx

class InvoiceCreateView(SalesRequiredMixin, CreateView):
    model = Invoice
    form_class = InvoiceForm
    template_name = 'invoices/invoice_form.html'
    success_url = reverse_lazy('invoice_list')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['page_title'] = 'إنشاء فاتورة جديدة'
        ctx['products'] = Product.objects.all()
        if self.request.POST:
            ctx['item_formset'] = InvoiceItemFormSet(self.request.POST)
        else:
            ctx['item_formset'] = InvoiceItemFormSet()
        # Status checkboxes for create (all unchecked, available based on permissions)
        user = self.request.user
        user_group_names = set(user.groups.values_list('name', flat=True))
        is_owner_user = is_owner(user)
        all_statuses = InvoiceStatus.objects.exclude(name='ملغي').order_by('order')
        checkboxes = []
        for s in all_statuses:
            allowed_group_names = set(s.allowed_groups.values_list('name', flat=True))
            user_has_perm = is_owner_user or bool(user_group_names & allowed_group_names)
            checkboxes.append({
                'id': s.id, 'name': s.name, 'color': s.color,
                'checked': False, 'disabled': not user_has_perm,
            })
        ctx['status_checkboxes'] = checkboxes
        return ctx

    def _apply_status_checkboxes(self):
        status_ids = self.request.POST.getlist('status_check')
        if not status_ids:
            return
        user = self.request.user
        user_group_names = set(user.groups.values_list('name', flat=True))
        is_owner_user = is_owner(user)
        all_statuses = InvoiceStatus.objects.exclude(name='ملغي').order_by('order')
        highest_new = None
        for s in all_statuses:
            if str(s.id) in status_ids:
                allowed_group_names = set(s.allowed_groups.values_list('name', flat=True))
                if is_owner_user or (user_group_names & allowed_group_names):
                    if not highest_new or s.order > highest_new.order:
                        highest_new = s
        if highest_new:
            self.object.status = highest_new
            self.object._changed_by = self.request.user
            self.object.save(update_fields=['status'])

    def form_valid(self, form):
        ctx = self.get_context_data()
        formset = ctx['item_formset']
        if formset.is_valid():
            self.object = form.save()
            self.object.created_by = self.request.user
            self.object.save(update_fields=['created_by'])
            self._apply_status_checkboxes()
            formset.instance = self.object
            formset.save()
            self.object.recalculate_total()
            if self.object.paid_amount > self.object.total_amount:
                self.object.paid_amount = self.object.total_amount
                self.object.save(update_fields=['paid_amount'])
            messages.success(self.request, f'تم إنشاء الفاتورة {self.object.invoice_number} بنجاح')
            return redirect(self.success_url)
        return self.render_to_response(self.get_context_data(form=form))

class InvoiceUpdateView(LoginRequiredMixin, UpdateView):
    model = Invoice
    form_class = InvoiceForm
    template_name = 'invoices/invoice_form.html'
    success_url = reverse_lazy('invoice_list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['page_title'] = 'تعديل الفاتورة'
        ctx['products'] = Product.objects.all()
        if self.request.POST:
            ctx['item_formset'] = InvoiceItemFormSet(self.request.POST, instance=self.object)
        else:
            ctx['item_formset'] = InvoiceItemFormSet(instance=self.object)
        # Build status checkboxes
        user = self.request.user
        user_group_names = set(user.groups.values_list('name', flat=True))
        is_owner_user = is_owner(user)
        all_statuses = InvoiceStatus.objects.exclude(name='ملغي').order_by('order')
        current_order = self.object.status.order if self.object.status else -1
        checkboxes = []
        for s in all_statuses:
            already_done = s.order <= current_order
            allowed_group_names = set(s.allowed_groups.values_list('name', flat=True))
            user_has_perm = is_owner_user or bool(user_group_names & allowed_group_names)
            checkboxes.append({
                'id': s.id, 'name': s.name, 'color': s.color,
                'checked': already_done, 'disabled': not user_has_perm or already_done,
            })
        ctx['status_checkboxes'] = checkboxes
        return ctx

    def _apply_status_checkboxes(self):
        status_ids = self.request.POST.getlist('status_check')
        if not status_ids:
            return None
        user = self.request.user
        user_group_names = set(user.groups.values_list('name', flat=True))
        is_owner_user = is_owner(user)
        all_statuses = InvoiceStatus.objects.exclude(name='ملغي').order_by('order')
        current_order = self.object.status.order if self.object.status else -1
        highest_new = None
        for s in all_statuses:
            if str(s.id) in status_ids and s.order > current_order:
                allowed_group_names = set(s.allowed_groups.values_list('name', flat=True))
                if is_owner_user or (user_group_names & allowed_group_names):
                    if not highest_new or s.order > highest_new.order:
                        highest_new = s
        if highest_new:
            self.object.status = highest_new
            self.object._changed_by = user
            self.object.save(update_fields=['status'])
        return highest_new

    def form_valid(self, form):
        user = self.request.user
        form.instance._changed_by = user
        if is_shipping(user) and not (is_sales(user) or is_owner(user)):
            form.instance.invoice_number = Invoice.objects.get(pk=self.object.pk).invoice_number
            form.instance.customer = Invoice.objects.get(pk=self.object.pk).customer
            form.instance.date = Invoice.objects.get(pk=self.object.pk).date
            form.instance.total_amount = Invoice.objects.get(pk=self.object.pk).total_amount
            form.instance.notes = Invoice.objects.get(pk=self.object.pk).notes
            self.object = form.save()
            self._apply_status_checkboxes()
            messages.success(self.request, f'تم تعديل الفاتورة {self.object.invoice_number} بنجاح')
            return redirect(self.success_url)
        ctx = self.get_context_data()
        formset = ctx['item_formset']
        if formset.is_valid():
            self.object = form.save()
            self._apply_status_checkboxes()
            formset.instance = self.object
            formset.save()
            self.object.recalculate_total()
            messages.success(self.request, f'تم تعديل الفاتورة {self.object.invoice_number} بنجاح')
            return redirect(self.success_url)
        return self.render_to_response(self.get_context_data(form=form))

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not (is_sales(request.user) or is_shipping(request.user) or is_owner(request.user)):
            messages.error(request, 'ليس لديك صلاحية للوصول إلى هذه الصفحة')
            return redirect('home')
        return super().dispatch(request, *args, **kwargs)

class InvoiceDetailView(LoginRequiredMixin, DetailView):
    model = Invoice
    template_name = 'invoices/invoice_detail.html'
    context_object_name = 'invoice'

    def get_queryset(self):
        return super().get_queryset().select_related('created_by')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['page_title'] = f'فاتورة {self.object.invoice_number}'
        ctx['statuses'] = InvoiceStatus.objects.exclude(name='ملغي')
        ctx['all_statuses'] = InvoiceStatus.objects.exclude(name='ملغي').order_by('order')
        ctx['status_logs'] = self.object.status_logs.select_related('changed_by', 'from_status', 'to_status')[:20]
        ctx['payment_methods'] = PaymentMethod.objects.all()
        if self.object.status:
            ctx['forward_statuses'] = InvoiceStatus.objects.exclude(name='ملغي').filter(order__gt=self.object.status.order)
        else:
            ctx['forward_statuses'] = InvoiceStatus.objects.exclude(name='ملغي')
        return ctx

class InvoicePrintView(LoginRequiredMixin, DetailView):
    model = Invoice
    template_name = 'invoices/invoice_print.html'
    context_object_name = 'invoice'

    def get_queryset(self):
        return super().get_queryset().select_related('created_by')

class InvoiceDeleteView(OwnerRequiredMixin, DeleteView):
    model = Invoice
    template_name = 'invoices/invoice_confirm_delete.html'
    success_url = reverse_lazy('invoice_list')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['page_title'] = 'حذف الفاتورة'
        return ctx

# --- API: Get product details for inline items ---
@login_required
def get_product_json(request):
    pid = request.GET.get('id')
    if pid:
        try:
            p = Product.objects.get(pk=pid)
            return JsonResponse({'name': p.name, 'price': str(p.price)})
        except Product.DoesNotExist:
            pass
    return JsonResponse({}, status=404)

# --- Quick status update for Shipper ---
@login_required
def update_invoice_status(request, pk):
    if not (is_shipping(request.user) or is_owner(request.user)):
        messages.error(request, 'ليس لديك صلاحية')
        return redirect('home')
    invoice = get_object_or_404(Invoice, pk=pk)
    if invoice.is_cancelled:
        messages.error(request, 'لا يمكن تعديل حالة طلب ملغي')
        return redirect('invoice_detail', pk=pk)
    if request.method == 'POST':
        status_id = request.POST.get('status')
        payment_id = request.POST.get('payment_method')
        paid_amount = request.POST.get('paid_amount')
        if status_id:
            new_status = get_object_or_404(InvoiceStatus, pk=status_id)
            if invoice.status and new_status.order <= invoice.status.order:
                if not is_owner(request.user):
                    messages.error(request, 'لا يمكن الرجوع إلى حالة سابقة')
                    return redirect('invoice_detail', pk=pk)
            invoice.status_id = status_id
        if payment_id:
            invoice.payment_method_id = payment_id
        if paid_amount is not None and paid_amount != '':
            try:
                invoice.paid_amount = float(paid_amount)
            except ValueError:
                pass
        invoice._changed_by = request.user
        invoice.save()
        messages.success(request, f'تم تحديث حالة الفاتورة {invoice.invoice_number} بنجاح')
    return redirect('invoice_detail', pk=pk)


# --- Cancel invoice ---
@login_required
def cancel_invoice(request, pk):
    if not (is_sales(request.user) or is_owner(request.user)):
        messages.error(request, 'ليس لديك صلاحية')
        return redirect('home')
    invoice = get_object_or_404(Invoice, pk=pk)
    if invoice.is_cancelled:
        messages.error(request, 'الفاتورة ملغية بالفعل')
        return redirect('invoice_detail', pk=pk)
    if request.method == 'POST':
        reason = request.POST.get('cancel_reason', '').strip()
        if not reason:
            messages.error(request, 'يرجى إدخال سبب الإلغاء')
            return redirect('invoice_detail', pk=pk)
        invoice.is_cancelled = True
        invoice.cancelled_at = now()
        invoice.cancel_reason = reason
        invoice._changed_by = request.user
        invoice.save()
        messages.success(request, f'تم إلغاء الفاتورة {invoice.invoice_number}')
    return redirect('invoice_detail', pk=pk)

# --- Settings: Invoice Statuses ---
class InvoiceStatusListView(OwnerRequiredMixin, ListView):
    model = InvoiceStatus
    template_name = 'invoices/settings_list.html'
    context_object_name = 'items'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['page_title'] = 'حالات الفواتير'
        ctx['settings_type'] = 'status'
        ctx['create_url'] = reverse_lazy('invoice_status_add')
        return ctx

class InvoiceStatusCreateView(OwnerRequiredMixin, CreateView):
    model = InvoiceStatus
    form_class = InvoiceStatusForm
    template_name = 'invoices/settings_form.html'
    success_url = reverse_lazy('invoice_status_list')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['page_title'] = 'إضافة حالة جديدة'
        return ctx

class InvoiceStatusUpdateView(OwnerRequiredMixin, UpdateView):
    model = InvoiceStatus
    form_class = InvoiceStatusForm
    template_name = 'invoices/settings_form.html'
    success_url = reverse_lazy('invoice_status_list')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['page_title'] = 'تعديل الحالة'
        return ctx

class InvoiceStatusDeleteView(OwnerRequiredMixin, DeleteView):
    model = InvoiceStatus
    template_name = 'invoices/settings_confirm_delete.html'
    success_url = reverse_lazy('invoice_status_list')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['page_title'] = 'حذف الحالة'
        return ctx

# --- Settings: Payment Methods ---
class PaymentMethodListView(OwnerRequiredMixin, ListView):
    model = PaymentMethod
    template_name = 'invoices/settings_list.html'
    context_object_name = 'items'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['page_title'] = 'طرق الدفع'
        ctx['settings_type'] = 'payment'
        ctx['create_url'] = reverse_lazy('payment_method_add')
        return ctx

class PaymentMethodCreateView(OwnerRequiredMixin, CreateView):
    model = PaymentMethod
    form_class = PaymentMethodForm
    template_name = 'invoices/settings_form.html'
    success_url = reverse_lazy('payment_method_list')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['page_title'] = 'إضافة طريقة دفع جديدة'
        return ctx

class PaymentMethodUpdateView(OwnerRequiredMixin, UpdateView):
    model = PaymentMethod
    form_class = PaymentMethodForm
    template_name = 'invoices/settings_form.html'
    success_url = reverse_lazy('payment_method_list')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['page_title'] = 'تعديل طريقة الدفع'
        return ctx

class PaymentMethodDeleteView(OwnerRequiredMixin, DeleteView):
    model = PaymentMethod
    template_name = 'invoices/settings_confirm_delete.html'
    success_url = reverse_lazy('payment_method_list')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['page_title'] = 'حذف طريقة الدفع'
        return ctx

# --- Import / Export ---
INVOICE_FIELDS = [
    Invoice._meta.get_field('invoice_number'),
    Invoice._meta.get_field('customer'),
    Invoice._meta.get_field('date'),
    Invoice._meta.get_field('total_amount'),
    Invoice._meta.get_field('paid_amount'),
    Invoice._meta.get_field('notes'),
]

INVOICE_FIELD_MAP = {
    'رقم الفاتورة': 'invoice_number',
    'العميل': 'customer',
    'التاريخ': 'date',
    'الإجمالي': 'total_amount',
    'المدفوع': 'paid_amount',
    'ملاحظات': 'notes',
}

@login_required
def export_invoices_csv(request):
    if not (is_sales(request.user) or is_owner(request.user)):
        messages.error(request, 'ليس لديك صلاحية')
        return redirect('home')
    return export_csv(Invoice, INVOICE_FIELDS, 'الفواتير')

@login_required
def export_invoices_xlsx(request):
    if not (is_sales(request.user) or is_owner(request.user)):
        messages.error(request, 'ليس لديك صلاحية')
        return redirect('home')
    return export_xlsx(Invoice, INVOICE_FIELDS, 'الفواتير')

@login_required
def import_invoices(request):
    if not (is_sales(request.user) or is_owner(request.user)):
        messages.error(request, 'ليس لديك صلاحية')
        return redirect('home')
    if request.method == 'POST' and request.FILES.get('file'):
        file = request.FILES['file']
        fmt = request.POST.get('format', 'csv')
        try:
            if fmt == 'csv':
                count = import_csv(file, Invoice, INVOICE_FIELD_MAP)
            else:
                count = import_xlsx(file, Invoice, INVOICE_FIELD_MAP)
            messages.success(request, f'تم استيراد {count} فاتورة بنجاح')
        except Exception as e:
            messages.error(request, f'خطأ في الاستيراد: {e}')
    return redirect('invoice_list')


class InvoiceTemplateUpdateView(LoginRequiredMixin, OwnerRequiredMixin, UpdateView):
    model = InvoiceTemplate
    form_class = InvoiceTemplateForm
    template_name = 'invoices/invoice_template_form.html'

    def get_object(self, queryset=None):
        return InvoiceTemplate.get()

    def get_success_url(self):
        return reverse('invoice_template_edit')

    def form_valid(self, form):
        resp = super().form_valid(form)
        messages.success(self.request, 'تم حفظ تصميم الفاتورة بنجاح')
        return resp
