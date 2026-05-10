from django.test import TestCase
from products.models import Category, Product


class CategoryTest(TestCase):
    def test_create_category(self):
        cat = Category.objects.create(name='لانجري')
        self.assertEqual(str(cat), 'لانجري')


class ProductTest(TestCase):
    def setUp(self):
        self.cat = Category.objects.create(name='لانجري')

    def test_create_product(self):
        p = Product.objects.create(
            name='طقم لانجري أحمر',
            category=self.cat,
            price=350,
            cost=180,
            quantity=25,
        )
        self.assertEqual(str(p), 'طقم لانجري أحمر')
        self.assertEqual(p.quantity, 25)

    def test_default_quantity(self):
        p = Product.objects.create(name='test', category=self.cat, price=100)
        self.assertEqual(p.quantity, 0)
