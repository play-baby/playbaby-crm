from django.db import models
from django.urls import reverse

class Customer(models.Model):
    name = models.CharField('الاسم', max_length=200)
    phone = models.CharField('رقم الهاتف', max_length=20)
    email = models.EmailField('البريد الإلكتروني', blank=True, null=True)
    address = models.TextField('العنوان', blank=True, null=True)
    notes = models.TextField('ملاحظات', blank=True, null=True)
    total_amount = models.DecimalField('إجمالي المشتريات', max_digits=12, decimal_places=2, default=0)
    image = models.ImageField('صورة', upload_to='customers/', blank=True, null=True)
    last_purchase_date = models.DateField('آخر تاريخ شراء', blank=True, null=True)
    created_at = models.DateTimeField('تاريخ الإضافة', auto_now_add=True)
    updated_at = models.DateTimeField('آخر تحديث', auto_now=True)

    class Meta:
        verbose_name = 'عميل'
        verbose_name_plural = 'العملاء'
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('customer_detail', args=[str(self.id)])
