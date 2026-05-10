from django import forms
from django.forms import inlineformset_factory
from .models import Invoice, InvoiceItem, InvoiceStatus, PaymentMethod
from core.models import InvoiceTemplate
from lingerie_crm.roles import is_shipping

class InvoiceForm(forms.ModelForm):
    class Meta:
        model = Invoice
        fields = ['invoice_number', 'customer', 'date', 'status', 'payment_method', 'paid_amount', 'discount_percent', 'notes']
        widgets = {
            'invoice_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'مثال: INV-001'}),
            'customer': forms.Select(attrs={'class': 'form-control'}),
            'date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
            'payment_method': forms.Select(attrs={'class': 'form-control'}),
            'paid_amount': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '0.00'}),
            'discount_percent': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '0', 'min': '0', 'max': '100', 'step': '0.01'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'ملاحظات...'}),
        }
        labels = {
            'invoice_number': 'رقم الفاتورة',
            'customer': 'العميل',
            'date': 'التاريخ',
            'status': 'حالة الطلب',
            'payment_method': 'طريقة الدفع',
            'paid_amount': 'المدفوع',
            'discount_percent': 'خصم %',
            'notes': 'ملاحظات',
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if not kwargs.get('data') and not kwargs.get('instance'):
            self.fields['invoice_number'].initial = Invoice.generate_invoice_number()
        if user and is_shipping(user):
            for fname in ['invoice_number', 'customer', 'date', 'notes']:
                self.fields[fname].disabled = True
            self.fields['paid_amount'].label = 'المبلغ المدفوع'
            self.fields['status'].required = False
            self.fields['payment_method'].required = False

    def clean_paid_amount(self):
        paid = self.cleaned_data.get('paid_amount')
        if paid is not None and paid < 0:
            raise forms.ValidationError('المبلغ المدفوع لا يمكن أن يكون سالباً')
        if paid is not None and self.instance and self.instance.pk and paid > self.instance.total_amount:
            raise forms.ValidationError(f'المبلغ المدفوع ({paid}) لا يمكن أن يتجاوز الإجمالي ({self.instance.total_amount})')
        return paid

    def clean(self):
        cleaned_data = super().clean()
        if self.instance and self.instance.pk:
            paid = cleaned_data.get('paid_amount')
            if paid is None:
                paid = self.instance.paid_amount
            if paid > self.instance.total_amount:
                self.add_error('paid_amount', f'المبلغ المدفوع ({paid}) لا يمكن أن يتجاوز الإجمالي ({self.instance.total_amount})')
        return cleaned_data


class InvoiceStatusForm(forms.ModelForm):
    class Meta:
        model = InvoiceStatus
        fields = ['name', 'order', 'color']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'مثال: قيد الانتظار'}),
            'order': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'color': forms.TextInput(attrs={'class': 'form-control', 'type': 'color'}),
        }
        labels = {
            'name': 'الاسم',
            'order': 'الترتيب',
            'color': 'اللون',
        }


class PaymentMethodForm(forms.ModelForm):
    class Meta:
        model = PaymentMethod
        fields = ['name']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'مثال: نقداً'}),
        }
        labels = {
            'name': 'الاسم',
        }

class InvoiceItemForm(forms.ModelForm):
    class Meta:
        model = InvoiceItem
        fields = ['product', 'product_name', 'quantity', 'unit_price', 'discount_percent', 'total']
        widgets = {
            'product': forms.Select(attrs={
                'class': 'form-control product-select',
                'onchange': 'onProductChange(this)',
            }),
            'product_name': forms.TextInput(attrs={
                'class': 'form-control product-name',
                'placeholder': 'اسم المنتج',
            }),
            'quantity': forms.NumberInput(attrs={
                'class': 'form-control item-qty',
                'placeholder': '1',
                'min': '1',
                'oninput': 'calcRow(this)',
            }),
            'unit_price': forms.NumberInput(attrs={
                'class': 'form-control item-price',
                'placeholder': '0.00',
                'min': '0',
                'step': '0.01',
                'oninput': 'calcRow(this)',
            }),
            'discount_percent': forms.NumberInput(attrs={
                'class': 'form-control item-discount',
                'placeholder': '0',
                'min': '0',
                'max': '100',
                'step': '0.01',
                'oninput': 'calcRow(this)',
            }),
            'total': forms.NumberInput(attrs={
                'class': 'form-control item-total',
                'readonly': True,
            }),
        }

    def clean_quantity(self):
        qty = self.cleaned_data.get('quantity')
        if qty and qty < 1:
            raise forms.ValidationError('الكمية يجب أن تكون 1 على الأقل')
        return qty

    def clean_unit_price(self):
        price = self.cleaned_data.get('unit_price')
        if price and price < 0:
            raise forms.ValidationError('السعر لا يمكن أن يكون سالباً')
        return price

class BaseInvoiceItemFormSet(forms.BaseInlineFormSet):
    def clean(self):
        super().clean()
        for form in self.forms:
            if not form.cleaned_data or form.cleaned_data.get('DELETE'):
                continue
            product = form.cleaned_data.get('product')
            quantity = form.cleaned_data.get('quantity')
            if product and quantity:
                if not form.instance.pk:
                    if quantity > product.quantity:
                        raise forms.ValidationError(
                            f'الكمية المطلوبة من "{product.name}" ({quantity}) تتجاوز المخزون ({product.quantity})'
                        )
                else:
                    old_qty = InvoiceItem.objects.get(pk=form.instance.pk).quantity
                    available = product.quantity + old_qty
                    if quantity > available:
                        raise forms.ValidationError(
                            f'الكمية المطلوبة من "{product.name}" ({quantity}) تتجاوز المخزون المتاح ({available})'
                        )


InvoiceItemFormSet = inlineformset_factory(
    Invoice, InvoiceItem,
    form=InvoiceItemForm,
    formset=BaseInvoiceItemFormSet,
    extra=1,
    can_delete=True,
    min_num=1,
    validate_min=True,
)


class InvoiceTemplateForm(forms.ModelForm):
    class Meta:
        model = InvoiceTemplate
        fields = '__all__'
        widgets = {
            'primary_color': forms.TextInput(attrs={'class': 'form-control', 'type': 'color'}),
            'company_name_color': forms.TextInput(attrs={'class': 'form-control', 'type': 'color'}),
            'footer_message': forms.TextInput(attrs={'class': 'form-control'}),
            'invoice_title': forms.TextInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'مثال: 01234567890'}),
            'header_size': forms.NumberInput(attrs={'class': 'form-control', 'min': '14', 'max': '40'}),
            'custom_css': forms.Textarea(attrs={'class': 'form-control', 'rows': 8, 'dir': 'ltr', 'style': 'font-family:monospace;'}),
        }
