from django.db import models
from django.core.cache import cache

class SiteSetting(models.Model):
    logo = models.ImageField('شعار الموقع', upload_to='logo/', blank=True, null=True)

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


class InvoiceTemplate(models.Model):
    primary_color = models.CharField('اللون الأساسي', max_length=7, default='#dc143c')
    company_name_color = models.CharField('لون اسم الشركة', max_length=7, default='#dc143c')
    show_logo = models.BooleanField('إظهار الشعار', default=True)
    show_footer = models.BooleanField('إظهار التذييل', default=True)
    footer_message = models.CharField('رسالة التذييل', max_length=200, default='شكراً لتسوقكم معنا')
    invoice_title = models.CharField('عنوان الفاتورة', max_length=50, default='فاتورة')
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
