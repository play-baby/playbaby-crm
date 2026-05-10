from django import forms
from .models import Customer

class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = ['name', 'phone', 'email', 'address', 'notes', 'total_amount', 'image', 'last_purchase_date']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'أدخل اسم العميل'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'أدخل رقم الهاتف'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'example@mail.com'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'أدخل العنوان'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'ملاحظات إضافية'}),
            'total_amount': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'إجمالي المشتريات'}),
            'last_purchase_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'image': forms.FileInput(attrs={'class': 'form-control-file'}),
        }
        labels = {
            'name': 'الاسم',
            'phone': 'رقم الهاتف',
            'email': 'البريد الإلكتروني',
            'address': 'العنوان',
            'notes': 'ملاحظات',
            'total_amount': 'إجمالي المشتريات',
            'image': 'صورة العميل',
            'last_purchase_date': 'آخر تاريخ شراء',
        }
