from django.db import models
from django.conf import settings
from django.db.models import F
from django.urls import reverse
from django.db.models.signals import pre_save, post_save, post_delete
from django.dispatch import receiver
from customers.models import Customer
from products.models import Product

class InvoiceStatus(models.Model):
    name = models.CharField('الاسم', max_length=100)
    order = models.IntegerField('الترتيب', default=0)
    color = models.CharField('اللون', max_length=7, default='#6c757d', help_text='مثال: #28a745')

    class Meta:
        verbose_name = 'حالة الطلب'
        verbose_name_plural = 'حالات الطلبات'
        ordering = ['order']

    def __str__(self):
        return self.name


class PaymentMethod(models.Model):
    name = models.CharField('الاسم', max_length=100)

    class Meta:
        verbose_name = 'طريقة دفع'
        verbose_name_plural = 'طرق الدفع'
        ordering = ['name']

    def __str__(self):
        return self.name


class Invoice(models.Model):
    invoice_number = models.CharField('رقم الفاتورة', max_length=50, unique=True)
    customer = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='العميل')
    date = models.DateField('التاريخ')
    total_amount = models.DecimalField('الإجمالي', max_digits=12, decimal_places=2, default=0)
    paid_amount = models.DecimalField('المدفوع', max_digits=12, decimal_places=2, default=0)
    discount_percent = models.DecimalField('خصم على الفاتورة %', max_digits=5, decimal_places=2, default=0)
    status = models.ForeignKey(InvoiceStatus, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='حالة الطلب')
    payment_method = models.ForeignKey(PaymentMethod, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='طريقة الدفع')
    notes = models.TextField('ملاحظات', blank=True, null=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='تم بواسطة')
    created_at = models.DateTimeField('تاريخ الإنشاء', auto_now_add=True)

    class Meta:
        verbose_name = 'فاتورة'
        verbose_name_plural = 'الفواتير'
        ordering = ['-date']

    def __str__(self):
        name = self.customer.name if self.customer else '---'
        return f'{self.invoice_number} - {name}'

    def get_absolute_url(self):
        return reverse('invoice_detail', args=[str(self.id)])

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.paid_amount and self.total_amount and self.paid_amount > self.total_amount:
            raise ValidationError({'paid_amount': f'المبلغ المدفوع ({self.paid_amount}) لا يمكن أن يتجاوز الإجمالي ({self.total_amount})'})

    def save(self, *args, **kwargs):
        if self.paid_amount > self.total_amount:
            self.paid_amount = self.total_amount
        super().save(*args, **kwargs)

    @property
    def remaining_amount(self):
        return self.total_amount - self.paid_amount

    @property
    def subtotal(self):
        return self.items.aggregate(models.Sum('total'))['total__sum'] or 0

    @property
    def items_net_total(self):
        return sum(item.line_net for item in self.items.all())

    @property
    def net_total(self):
        return self.items_net_total * (1 - (self.discount_percent or 0) / 100)

    @property
    def invoice_discount_amount(self):
        return self.items_net_total * ((self.discount_percent or 0) / 100)

    def recalculate_total(self):
        self.total_amount = self.net_total
        self.save(update_fields=['total_amount'])

    @staticmethod
    def generate_invoice_number():
        last = Invoice.objects.order_by('-id').first()
        if last:
            try:
                num = int(last.invoice_number.replace('INV-', '')) + 1
            except ValueError:
                num = Invoice.objects.count() + 1
        else:
            num = 1
        return f'INV-{num:04d}'


class InvoiceItem(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='items', verbose_name='الفاتورة')
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='المنتج')
    product_name = models.CharField('اسم المنتج', max_length=200)
    quantity = models.IntegerField('الكمية', default=1)
    unit_price = models.DecimalField('سعر الوحدة', max_digits=10, decimal_places=2)
    total = models.DecimalField('الإجمالي', max_digits=10, decimal_places=2)
    discount_percent = models.DecimalField('خصم %', max_digits=5, decimal_places=2, default=0)

    class Meta:
        verbose_name = 'عنصر فاتورة'
        verbose_name_plural = 'عناصر الفاتورة'

    def __str__(self):
        return f'{self.product_name} x {self.quantity}'

    def save(self, *args, **kwargs):
        self.total = self.quantity * self.unit_price
        super().save(*args, **kwargs)

    @property
    def line_net(self):
        return self.total * (1 - (self.discount_percent or 0) / 100)


@receiver(post_save, sender=Invoice)
@receiver(post_delete, sender=Invoice)
def update_customer_total(sender, instance, **kwargs):
    if instance.customer:
        total = Invoice.objects.filter(customer=instance.customer).aggregate(
            models.Sum('total_amount'))['total_amount__sum'] or 0
        Customer.objects.filter(pk=instance.customer.pk).update(total_amount=total)


# --- Stock management: deduct on invoice item save, restore on delete ---
@receiver(pre_save, sender=InvoiceItem)
def capture_old_item(sender, instance, **kwargs):
    if instance.pk:
        old = InvoiceItem.objects.get(pk=instance.pk)
        instance._old_qty = old.quantity
        instance._old_product_id = old.product_id
    else:
        instance._old_qty = 0
        instance._old_product_id = None


@receiver(post_save, sender=InvoiceItem)
def update_stock_on_save(sender, instance, created, **kwargs):
    old_qty = getattr(instance, '_old_qty', 0)
    old_pid = getattr(instance, '_old_product_id', None)
    new_pid = instance.product_id
    new_qty = instance.quantity

    if new_pid and old_pid and old_pid != new_pid:
        # Product changed: restore old, deduct new
        if old_pid:
            Product.objects.filter(pk=old_pid).update(quantity=F('quantity') + old_qty)
        Product.objects.filter(pk=new_pid).update(quantity=F('quantity') - new_qty)
    elif new_pid and old_qty > 0:
        # Same product, quantity changed
        diff = old_qty - new_qty
        if diff != 0:
            Product.objects.filter(pk=new_pid).update(quantity=F('quantity') + diff)
    elif new_pid:
        # New item
        Product.objects.filter(pk=new_pid).update(quantity=F('quantity') - new_qty)
    elif old_pid:
        # Product unset, restore old stock
        Product.objects.filter(pk=old_pid).update(quantity=F('quantity') + old_qty)


@receiver(post_delete, sender=InvoiceItem)
def restore_stock_on_delete(sender, instance, **kwargs):
    if instance.product_id:
        Product.objects.filter(pk=instance.product_id).update(
            quantity=F('quantity') + instance.quantity
        )
