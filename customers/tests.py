from django.test import TestCase
from customers.models import Customer


class CustomerModelTest(TestCase):
    def test_create_customer(self):
        c = Customer.objects.create(
            name='سارة أحمد',
            phone='01001234567',
            address='القاهرة',
            total_amount=1500,
        )
        self.assertEqual(str(c), 'سارة أحمد')
        self.assertEqual(c.phone, '01001234567')

    def test_defaults(self):
        c = Customer.objects.create(name='test', phone='000')
        self.assertEqual(c.total_amount, 0)

    def test_customer_update_total_amount(self):
        c = Customer.objects.create(name='test', phone='000')
        c.total_amount = 5000
        c.save()
        c.refresh_from_db()
        self.assertEqual(c.total_amount, 5000)
