from django.db import models
from django.urls import reverse

class Category(models.Model):
    name = models.CharField('اسم التصنيف', max_length=100)

    class Meta:
        verbose_name = 'تصنيف'
        verbose_name_plural = 'التصنيفات'
        ordering = ['name']

    def __str__(self):
        return self.name

class Product(models.Model):
    name = models.CharField('اسم المنتج', max_length=200)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='التصنيف')
    description = models.TextField('الوصف', blank=True, null=True)
    price = models.DecimalField('السعر', max_digits=10, decimal_places=2)
    cost = models.DecimalField('التكلفة', max_digits=10, decimal_places=2, blank=True, null=True)
    quantity = models.IntegerField('الكمية', default=0)
    image = models.ImageField('صورة', upload_to='products/', blank=True, null=True)
    created_at = models.DateTimeField('تاريخ الإضافة', auto_now_add=True)
    updated_at = models.DateTimeField('آخر تحديث', auto_now=True)

    class Meta:
        verbose_name = 'منتج'
        verbose_name_plural = 'المنتجات'
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('product_detail', args=[str(self.id)])
