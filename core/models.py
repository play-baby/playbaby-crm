from django.db import models
from django.core.cache import cache
from django.contrib.auth.models import Group

class SiteSetting(models.Model):
    logo = models.ImageField('شعار الموقع', upload_to='logo/', blank=True, null=True)
    website = models.URLField('الموقع الإلكتروني', blank=True, null=True, help_text='مثال: https://playbaby.com')

    class Meta:
        verbose_name = 'إعدادات الموقع'
        verbose_name_plural = 'إعدادات الموقع'

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)
        cache.delete('site_setting')

    def delete(self, *args, **kwargs):
        pass

    @classmethod
    def get(cls):
        obj = cache.get('site_setting')
        if not obj:
            obj, _ = cls.objects.get_or_create(pk=1)
            cache.set('site_setting', obj, 3600)
        return obj

    def __str__(self):
        return 'إعدادات الموقع'


class RoleLanding(models.Model):
    group = models.OneToOneField(Group, on_delete=models.CASCADE, verbose_name='المجموعة')
    landing_page = models.CharField('صفحة الهبوط', max_length=100, blank=True,
                                     help_text='اسم مسار URL (مثال: customer_list)')
    dashboard_blocked = models.BooleanField('حظر لوحة التحكم', default=False,
                                             help_text='عند التفعيل، يتم توجيه المستخدم بعيداً عن لوحة التحكم')

    class Meta:
        verbose_name = 'إعدادات المجموعة'
        verbose_name_plural = 'إعدادات المجموعات'

    def __str__(self):
        return f'{self.group.name}: {self.landing_page or "الافتراضية"}'


class InvoiceTemplate(models.Model):
    primary_color = models.CharField('اللون الأساسي', max_length=7, default='#dc143c')
    company_name_color = models.CharField('لون اسم الشركة', max_length=7, default='#dc143c')
    show_logo = models.BooleanField('إظهار الشعار', default=True)
    show_footer = models.BooleanField('إظهار التذييل', default=True)
    footer_message = models.CharField('رسالة التذييل', max_length=200, default='شكراً لتسوقكم معنا')
    invoice_title = models.CharField('عنوان الفاتورة', max_length=50, default='فاتورة')
    phone = models.CharField('رقم الهاتف', max_length=30, blank=True, null=True, help_text='رقم الهاتف الظاهر أسفل اسم الشركة')
    font_family = models.CharField('الخط', max_length=50, default='Tajawal')
    header_size = models.IntegerField('حجم اسم الشركة', default=20)
    border_style = models.CharField('نمط الحدود', max_length=20, default='solid',
                                     choices=[('solid', 'Solid'), ('dashed', 'Dashed'), ('dotted', 'Dotted')])
    custom_css = models.TextField('CSS مخصص', blank=True, null=True,
                                   help_text='كود CSS إضافي لتخصيص تصميم الفاتورة')

    class Meta:
        verbose_name = 'تصميم الفاتورة'
        verbose_name_plural = 'تصميم الفاتورة'

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)
        cache.delete('invoice_template')

    def delete(self, *args, **kwargs):
        pass

    @classmethod
    def get(cls):
        obj = cache.get('invoice_template')
        if not obj:
            obj, _ = cls.objects.get_or_create(pk=1)
            cache.set('invoice_template', obj, 3600)
        return obj

    def __str__(self):
        return 'تصميم الفاتورة'
