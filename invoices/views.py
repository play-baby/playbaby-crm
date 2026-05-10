from django.urls import reverse_lazy, reverse
from django.views.generic import ListView, DetailView, DeleteView, TemplateView
from django.views.generic.edit import CreateView, UpdateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.shortcuts import redirect, render, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse
from django.utils.timezone import now, make_aware
from datetime import datetime
from decimal import Decimal
from django.db.models import Sum, Q
from django.db.utils import OperationalError
from .models import Invoice, InvoiceItem, InvoiceStatus, InvoiceStatusLog, PaymentMethod, Notification, Payment
from .forms import InvoiceForm, InvoiceItemFormSet, InvoiceStatusForm, PaymentMethodForm, InvoiceTemplateForm, PaymentForm
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
        # Compute revised total preview for sales approval screen
        invoice = self.object
        revised_items_total = Decimal('0')
        for item in invoice.items.all():
            qty = item.confirmed_quantity if item.confirmed_quantity is not None else item.quantity
            line_total = qty * item.unit_price
            dp = item.discount_percent or Decimal('0')
            line_net = line_total * (Decimal('1') - dp / Decimal('100'))
            revised_items_total += line_net
        inv_dp = invoice.discount_percent or Decimal('0')
        ctx['revised_total_preview'] = revised_items_total * (Decimal('1') - inv_dp / Decimal('100'))
        # Payments (safety: table may not exist if migration hasn't been applied)
        try:
            ctx['payments'] = invoice.payments.select_related('created_by', 'payment_method').all()
        except OperationalError:
            ctx['payments'] = []
        ctx['payment_form'] = PaymentForm()
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
        collected = request.POST.get('is_collected')
        old_status_id = invoice.status_id
        was_collected = invoice.is_collected
        if status_id:
            new_status = get_object_or_404(InvoiceStatus, pk=status_id)
            if invoice.status and new_status.order <= invoice.status.order:
                if not is_owner(request.user):
                    messages.error(request, 'لا يمكن الرجوع إلى حالة سابقة')
                    return redirect('invoice_detail', pk=pk)
            invoice.status_id = status_id
        if payment_id:
            invoice.payment_method_id = payment_id
        # Handle collection checkbox
        collected_date_str = request.POST.get('collected_date', '').strip()
        if collected == 'on':
            invoice.is_collected = True
            if collected_date_str:
                naive_date = datetime.strptime(collected_date_str, '%Y-%m-%d')
                invoice.collected_at = make_aware(naive_date)
            else:
                invoice.collected_at = now()
            invoice.collected_by = request.user
        else:
            if invoice.is_collected and (invoice.collected_by == request.user or invoice.collected_by is None):
                invoice.is_collected = False
                invoice.collected_at = None
                invoice.collected_by = None
        invoice._changed_by = request.user
        invoice.save()
        UserModel = get_user_model()
        recipients = UserModel.objects.filter(
            groups__name__in=['shipping', 'sales', 'owner']
        ).exclude(pk=request.user.pk).distinct()
        for user in recipients:
            if status_id and str(status_id) != str(old_status_id):
                Notification.objects.create(
                    invoice=invoice,
                    sender=request.user,
                    recipient=user,
                    notification_type='status_updated',
                    message=f'تم تحديث حالة الفاتورة {invoice.invoice_number} إلى {new_status.name}'
                )
            elif collected == 'on' and not was_collected:
                Notification.objects.create(
                    invoice=invoice,
                    sender=request.user,
                    recipient=user,
                    notification_type='collected',
                    message=f'تم تحصيل الفاتورة {invoice.invoice_number} بالكامل'
                )
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
        UserModel = get_user_model()
        recipients = UserModel.objects.filter(
            groups__name__in=['shipping', 'sales', 'owner']
        ).exclude(pk=request.user.pk).distinct()
        for user in recipients:
            Notification.objects.create(
                invoice=invoice,
                sender=request.user,
                recipient=user,
                notification_type='cancelled',
                message=f'تم إلغاء الفاتورة {invoice.invoice_number} — السبب: {reason[:100]}'
            )
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


# ═══════════════════════════════════════════════
# COLLECTION CONFIRMATION
# ═══════════════════════════════════════════════

@login_required
def confirm_collection(request, pk):
    if not (is_sales(request.user) or is_owner(request.user)):
        messages.error(request, 'ليس لديك صلاحية')
        return redirect('home')
    invoice = get_object_or_404(Invoice, pk=pk)
    if invoice.is_cancelled:
        messages.error(request, 'لا يمكن تحصيل فاتورة ملغية')
        return redirect('invoice_detail', pk=pk)
    if request.method == 'POST':
        if request.POST.get('confirm') == 'yes':
            invoice.is_collected = True
            invoice.collected_at = now()
            invoice.collected_by = request.user
            invoice.save(update_fields=['is_collected', 'collected_at', 'collected_by'])
            UserModel = get_user_model()
            recipients = UserModel.objects.filter(
                groups__name__in=['shipping', 'sales', 'owner']
            ).exclude(pk=request.user.pk).distinct()
            for user in recipients:
                Notification.objects.create(
                    invoice=invoice,
                    sender=request.user,
                    recipient=user,
                    notification_type='collected',
                    message=f'تم تحصيل الفاتورة {invoice.invoice_number} بالكامل'
                )
            messages.success(request, 'تم تأكيد التحصيل بنجاح')
        elif request.POST.get('reverse') == 'yes':
            invoice.is_collected = False
            invoice.collected_at = None
            invoice.collected_by = None
            invoice.save(update_fields=['is_collected', 'collected_at', 'collected_by'])
            messages.success(request, 'تم إلغاء تأكيد التحصيل')
    return redirect('invoice_detail', pk=pk)


# ═══════════════════════════════════════════════
# CUSTOMER BALANCES (أرصدة العملاء)
# ═══════════════════════════════════════════════

class CustomerBalanceView(LoginRequiredMixin, ListView):
    model = Invoice
    template_name = 'invoices/customer_balances.html'
    context_object_name = 'invoices'
    paginate_by = 20

    def get_queryset(self):
        qs = Invoice.objects.select_related('customer', 'status', 'payment_method')
        cust_id = self.request.GET.get('customer')
        if cust_id:
            qs = qs.filter(customer_id=cust_id)
        search = self.request.GET.get('search', '')
        if search:
            qs = qs.filter(invoice_number__icontains=search) | qs.filter(customer__name__icontains=search)
        return qs.order_by('-date')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['page_title'] = 'أرصدة العملاء'
        ctx['search'] = self.request.GET.get('search', '')
        from customers.models import Customer
        # Aggregate per-customer balances
        all_customers = Customer.objects.filter(
            pk__in=Invoice.objects.values_list('customer', flat=True).distinct()
        )
        balance_data = []
        for c in all_customers:
            invs = Invoice.objects.filter(customer=c)
            total_amt = invs.aggregate(Sum('total_amount'))['total_amount__sum'] or 0
            total_paid = invs.aggregate(Sum('paid_amount'))['paid_amount__sum'] or 0
            balance_data.append({
                'customer': c,
                'invoice_count': invs.count(),
                'total_amount': total_amt,
                'paid_amount': total_paid,
                'remaining': total_amt - total_paid,
            })
        balance_data.sort(key=lambda x: x['remaining'], reverse=True)
        ctx['balance_data'] = balance_data
        ctx['grand_total'] = sum(b['total_amount'] for b in balance_data)
        ctx['grand_paid'] = sum(b['paid_amount'] for b in balance_data)
        ctx['grand_remaining'] = sum(b['remaining'] for b in balance_data)
        ctx['selected_customer'] = self.request.GET.get('customer', '')
        return ctx


# ═══════════════════════════════════════════════
# NOTIFICATION VIEWS
# ═══════════════════════════════════════════════

@login_required
def notification_list(request):
    notifications = Notification.objects.filter(recipient=request.user)
    unread_count = notifications.filter(is_read=False).count()
    return render(request, 'invoices/notification_list.html', {
        'notifications': notifications,
        'unread_count': unread_count,
    })


@login_required
def notification_mark_read(request, pk):
    notification = get_object_or_404(Notification, pk=pk, recipient=request.user)
    notification.is_read = True
    notification.save(update_fields=['is_read'])
    return redirect('invoice_detail', pk=notification.invoice_id)


@login_required
def notification_mark_all_read(request):
    Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
    messages.success(request, 'تم تحديد الكل كمقروء')
    return redirect('notification_list')


# ═══════════════════════════════════════════════
# PAYMENT (INSTALLMENTS)
# ═══════════════════════════════════════════════

@login_required
def add_payment(request, pk):
    if not (is_sales(request.user) or is_owner(request.user)):
        messages.error(request, 'ليس لديك صلاحية')
        return redirect('home')
    invoice = get_object_or_404(Invoice, pk=pk)
    if request.method == 'POST':
        form = PaymentForm(request.POST)
        if form.is_valid():
            payment = form.save(commit=False)
            payment.invoice = invoice
            payment.created_by = request.user
            payment.save()
            # Notify relevant users about the new payment
            UserModel = get_user_model()
            recipients = UserModel.objects.filter(
                groups__name__in=['shipping', 'sales', 'owner']
            ).exclude(pk=request.user.pk).distinct()
            for user in recipients:
                Notification.objects.create(
                    invoice=invoice,
                    sender=request.user,
                    recipient=user,
                    notification_type='new_payment',
                    message=f'تمت إضافة دفعة جديدة ({payment.amount} ج.م) للفاتورة {invoice.invoice_number}'
                )
            messages.success(request, f'تمت إضافة الدفعة ({payment.amount} ج.م) بنجاح')
        else:
            messages.error(request, 'خطأ في إضافة الدفعة')
    return redirect('invoice_detail', pk=pk)


# ═══════════════════════════════════════════════
# SHIPPING AVAILABILITY CONFIRMATION
# ═══════════════════════════════════════════════

@login_required
def confirm_availability(request, pk):
    if not (is_shipping(request.user) or is_owner(request.user)):
        messages.error(request, 'ليس لديك صلاحية')
        return redirect('home')
    invoice = get_object_or_404(Invoice, pk=pk)
    if invoice.is_cancelled:
        messages.error(request, 'لا يمكن تعديل فاتورة ملغية')
        return redirect('invoice_detail', pk=pk)
    if invoice.revision_status != 'pending_shipping':
        messages.error(request, 'تم تأكيد التوفر مسبقاً لهذه الفاتورة')
        return redirect('invoice_detail', pk=pk)
    if request.method == 'POST':
        any_partial = False
        for key, value in request.POST.items():
            if key.startswith('qty_'):
                item_id = key.split('_')[1]
                try:
                    item = invoice.items.get(pk=item_id)
                    is_not_available = request.POST.get(f'not_available_{item_id}') == 'on'
                    if is_not_available:
                        confirmed = 0
                    else:
                        confirmed = int(value)
                    if confirmed < 0:
                        continue
                    if confirmed < item.quantity:
                        any_partial = True
                    item.confirmed_quantity = confirmed
                    item.save(update_fields=['confirmed_quantity'])
                except (InvoiceItem.DoesNotExist, ValueError, IndexError):
                    continue
        invoice.revision_status = 'shipping_confirmed'
        invoice.save(update_fields=['revision_status'])
        if any_partial:
            invoice.revision_status = 'pending_approval'
            invoice.save(update_fields=['revision_status'])
        if invoice.created_by:
            Notification.objects.create(
                invoice=invoice,
                sender=request.user,
                recipient=invoice.created_by,
                notification_type='needs_approval' if any_partial else 'availability_confirmed',
                message=f'تم تأكيد توفر المنتجات للفاتورة {invoice.invoice_number}'
            )
        messages.success(request, 'تم تأكيد التوفر بنجاح')
    return redirect('invoice_detail', pk=pk)


@login_required
def approve_revision(request, pk):
    if not (is_sales(request.user) or is_owner(request.user)):
        messages.error(request, 'ليس لديك صلاحية')
        return redirect('home')
    invoice = get_object_or_404(Invoice, pk=pk)
    action = request.POST.get('action', '')
    UserModel = get_user_model()
    if action == 'approve':
        invoice.revision_status = 'approved'
        invoice.save(update_fields=['revision_status'])
        for item in invoice.items.all():
            if item.confirmed_quantity is not None:
                if item.confirmed_quantity == 0:
                    item.delete()
                else:
                    item.quantity = item.confirmed_quantity
                    item.total = item.quantity * item.unit_price
                    item.confirmed_quantity = None
                    item.save(update_fields=['quantity', 'total', 'confirmed_quantity'])
        invoice.refresh_from_db()
        invoice.recalculate_total()
        for user in UserModel.objects.filter(groups__name='shipping'):
            Notification.objects.create(
                invoice=invoice,
                sender=request.user,
                recipient=user,
                notification_type='revision_approved',
                message=f'تمت الموافقة على مراجعة الفاتورة {invoice.invoice_number}'
            )
        messages.success(request, 'تمت الموافقة على المراجعة')
    elif action == 'reject':
        invoice.revision_status = 'rejected'
        invoice.save(update_fields=['revision_status'])
        UserModel = get_user_model()
        for user in UserModel.objects.filter(groups__name='shipping'):
            Notification.objects.create(
                invoice=invoice,
                sender=request.user,
                recipient=user,
                notification_type='revision_rejected',
                message=f'تم رفض مراجعة الفاتورة {invoice.invoice_number}'
            )
        messages.warning(request, 'تم رفض المراجعة')
    return redirect('invoice_detail', pk=pk)
