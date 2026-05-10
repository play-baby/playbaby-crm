from decimal import Decimal
from django.db import models
from django.conf import settings
from django.db.models import F
from django.urls import reverse
from django.db.models.signals import pre_save, post_save, post_delete
from django.dispatch import receiver
from django.contrib.auth.models import Group, User
from customers.models import Customer
from products.models import Product

class InvoiceStatus(models.Model):
    name = models.CharField('الاسم', max_length=100)
    order = models.IntegerField('الترتيب', default=0)
    color = models.CharField('اللون', max_length=7, default='#6c757d', help_text='مثال: #28a745')
    allowed_groups = models.ManyToManyField(Group, blank=True, verbose_name='المجموعات المسموحة')

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
    is_cancelled = models.BooleanField('ملغي', default=False)
    cancelled_at = models.DateTimeField('تاريخ الإلغاء', null=True, blank=True)
    cancel_reason = models.TextField('سبب الإلغاء', blank=True, null=True)
    revision_status = models.CharField('حالة المراجعة', max_length=20, default='pending_shipping',
        choices=[
            ('pending_shipping', 'بانتظار تأكيد الشحن'),
            ('shipping_confirmed', 'تم تأكيد الشحن'),
            ('pending_approval', 'بانتظار موافقة المبيعات'),
            ('approved', 'تمت الموافقة'),
            ('rejected', 'مرفوض'),
        ])

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
        return self.items.aggregate(models.Sum('total'))['total__sum'] or Decimal('0')

    @property
    def items_net_total(self):
        items = self.items.all()
        if not items:
            return Decimal('0')
        total = Decimal('0')
        for item in items:
            total += item.line_net
        return total

    @property
    def net_total(self):
        dp = self.discount_percent or Decimal('0')
        return self.items_net_total * (Decimal('1') - dp / Decimal('100'))

    @property
    def item_discount_amount(self):
        return self.subtotal - self.items_net_total

    @property
    def invoice_discount_amount(self):
        dp = self.discount_percent or Decimal('0')
        return self.items_net_total * (dp / Decimal('100'))

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
    confirmed_quantity = models.IntegerField('الكمية المؤكدة', null=True, blank=True, help_text='تؤكد من قبل الشحن')
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
        dp = self.discount_percent or Decimal('0')
        return self.total * (Decimal('1') - dp / Decimal('100'))


class InvoiceStatusLog(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='status_logs', verbose_name='الفاتورة')
    from_status = models.ForeignKey(InvoiceStatus, on_delete=models.SET_NULL, null=True, blank=True, related_name='+', verbose_name='من حالة')
    to_status = models.ForeignKey(InvoiceStatus, on_delete=models.SET_NULL, null=True, blank=True, related_name='+', verbose_name='إلى حالة')
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='تم بواسطة')
    changed_at = models.DateTimeField('تاريخ التغيير', auto_now_add=True)

    class Meta:
        verbose_name = 'سجل حالة الطلب'
        verbose_name_plural = 'سجل حالات الطلبات'
        ordering = ['-changed_at']

    def __str__(self):
        return f'{self.invoice}: {self.from_status} \u2192 {self.to_status}'


class Notification(models.Model):
    NOTIFICATION_TYPES = [
        ('new_invoice', 'فاتورة جديدة'),
        ('availability_confirmed', 'تم تأكيد التوفر'),
        ('revision_approved', 'تمت الموافقة على المراجعة'),
        ('revision_rejected', 'تم رفض المراجعة'),
        ('needs_approval', 'بانتظار الموافقة'),
    ]
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='notifications', verbose_name='الفاتورة')
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='sent_notifications', verbose_name='المرسل')
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='received_notifications', verbose_name='المستلم')
    notification_type = models.CharField('النوع', max_length=30, choices=NOTIFICATION_TYPES)
    message = models.TextField('الرسالة', blank=True)
    is_read = models.BooleanField('مقروء', default=False)
    created_at = models.DateTimeField('تاريخ الإنشاء', auto_now_add=True)

    class Meta:
        verbose_name = 'إشعار'
        verbose_name_plural = 'الإشعارات'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.get_notification_type_display()} - {self.invoice.invoice_number}'


@receiver(post_save, sender=Invoice)
def notify_shipping_on_new_invoice(sender, instance, created, **kwargs):
    """Auto-notify shipping group when a new invoice is created by sales."""
    if created and instance.created_by:
        from django.contrib.auth.models import Group as AuthGroup
        try:
            shipping_group = AuthGroup.objects.get(name='shipping')
            for user in shipping_group.user_set.all():
                Notification.objects.create(
                    invoice=instance,
                    sender=instance.created_by,
                    recipient=user,
                    notification_type='new_invoice',
                    message=f'فاتورة جديدة {instance.invoice_number} من {instance.created_by.username}'
                )
        except AuthGroup.DoesNotExist:
            pass


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


@receiver(pre_save, sender=Invoice)
def capture_old_status(sender, instance, **kwargs):
    if instance.pk:
        old = Invoice.objects.get(pk=instance.pk)
        instance._old_status_id = old.status_id
    else:
        instance._old_status_id = None


@receiver(post_save, sender=Invoice)
def log_status_change(sender, instance, created, **kwargs):
    if not created:
        old_status_id = getattr(instance, '_old_status_id', None)
        if old_status_id != instance.status_id:
            InvoiceStatusLog.objects.create(
                invoice=instance,
                from_status_id=old_status_id,
                to_status=instance.status,
                changed_by=getattr(instance, '_changed_by', None),
            )
