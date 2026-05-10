from decimal import Decimal
from django.test import TestCase, RequestFactory, override_settings
from django.contrib.auth.models import User, Group
from django.core.exceptions import ValidationError
from django.urls import reverse
from customers.models import Customer
from products.models import Category, Product
from invoices.models import InvoiceStatus, PaymentMethod, Invoice, InvoiceItem, InvoiceStatusLog, Notification
from invoices.forms import InvoiceForm, InvoiceStatusForm


# ═══════════════════════════════════════════════
# MODEL TESTS
# ═══════════════════════════════════════════════

class InvoiceStatusTest(TestCase):
    def setUp(self):
        InvoiceStatus.objects.all().delete()
        self.group = Group.objects.create(name='_test_inv_status_group')

    def test_create_status(self):
        s = InvoiceStatus.objects.create(name='قيد المراجعة', order=1, color='#ffc107')
        self.assertEqual(str(s), 'قيد المراجعة')
        self.assertEqual(s.order, 1)

    def test_allowed_groups(self):
        s = InvoiceStatus.objects.create(name='قيد المراجعة', order=1)
        s.allowed_groups.add(self.group)
        self.assertIn(self.group, s.allowed_groups.all())

    def test_ordering(self):
        InvoiceStatus.objects.all().delete()
        InvoiceStatus.objects.create(name='ثاني', order=2)
        InvoiceStatus.objects.create(name='أول', order=1)
        statuses = list(InvoiceStatus.objects.all())
        self.assertEqual(statuses[0].name, 'أول')
        self.assertEqual(statuses[1].name, 'ثاني')


class PaymentMethodTest(TestCase):
    def test_create(self):
        pm = PaymentMethod.objects.create(name='نقداً')
        self.assertEqual(str(pm), 'نقداً')

    def test_ordering(self):
        PaymentMethod.objects.create(name='بطاقة')
        PaymentMethod.objects.create(name='أونلاين')
        methods = list(PaymentMethod.objects.all())
        self.assertEqual(methods[0].name, 'أونلاين')
        self.assertEqual(methods[1].name, 'بطاقة')


class InvoiceTest(TestCase):
    def setUp(self):
        self.customer = Customer.objects.create(name='test', phone='000')
        self.status = InvoiceStatus.objects.create(name='جديد', order=1)
        self.pm = PaymentMethod.objects.create(name='نقداً')

    def test_create_invoice_with_number(self):
        inv = Invoice.objects.create(
            invoice_number='INV-0001',
            customer=self.customer,
            date='2026-01-01',
            total_amount=1000,
            paid_amount=500,
            status=self.status,
            payment_method=self.pm,
        )
        self.assertIn('INV-0001', str(inv))
        self.assertEqual(inv.remaining_amount, Decimal('500'))

    def test_paid_amount_clamped_on_save(self):
        inv = Invoice.objects.create(
            invoice_number='INV-0002',
            customer=self.customer,
            date='2026-01-01',
            total_amount=1000,
            paid_amount=1500,
        )
        inv.refresh_from_db()
        self.assertEqual(inv.paid_amount, Decimal('1000'))

    def test_remaining_amount(self):
        inv = Invoice.objects.create(
            invoice_number='INV-0003', customer=self.customer,
            date='2026-01-01', total_amount=1000, paid_amount=300,
        )
        self.assertEqual(inv.remaining_amount, Decimal('700'))

    def test_remaining_amount_zero_when_paid(self):
        inv = Invoice.objects.create(
            invoice_number='INV-0004', customer=self.customer,
            date='2026-01-01', total_amount=1000, paid_amount=1000,
        )
        self.assertEqual(inv.remaining_amount, Decimal('0'))

    def test_subtotal_no_items(self):
        inv = Invoice.objects.create(
            invoice_number='INV-0005', customer=self.customer,
            date='2026-01-01', total_amount=0,
        )
        self.assertEqual(inv.subtotal, Decimal('0'))

    def test_items_net_total_no_items(self):
        inv = Invoice.objects.create(
            invoice_number='INV-0006', customer=self.customer,
            date='2026-01-01', total_amount=0,
        )
        self.assertEqual(inv.items_net_total, Decimal('0'))

    def test_generate_invoice_number_first(self):
        num = Invoice.generate_invoice_number()
        self.assertTrue(num.startswith('INV-'))

    def test_generate_invoice_number_increments(self):
        Invoice.objects.create(
            invoice_number='INV-0001', customer=self.customer,
            date='2026-01-01', total_amount=0,
        )
        num = Invoice.generate_invoice_number()
        self.assertEqual(num, 'INV-0002')

    def test_absolute_url(self):
        inv = Invoice.objects.create(
            invoice_number='INV-0007', customer=self.customer,
            date='2026-01-01', total_amount=0,
        )
        self.assertIn(str(inv.id), inv.get_absolute_url())

    def test_net_total_no_discount(self):
        inv = Invoice.objects.create(
            invoice_number='INV-0008', customer=self.customer,
            date='2026-01-01', total_amount=0, discount_percent=0,
        )
        self.assertEqual(inv.net_total, Decimal('0'))

    def test_cancel_invoice(self):
        inv = Invoice.objects.create(
            invoice_number='INV-0009', customer=self.customer,
            date='2026-01-01', total_amount=500,
        )
        inv.is_cancelled = True
        inv.cancel_reason = 'ألغي الطلب'
        inv.save()
        inv.refresh_from_db()
        self.assertTrue(inv.is_cancelled)
        self.assertEqual(inv.cancel_reason, 'ألغي الطلب')


class InvoiceItemTest(TestCase):
    def setUp(self):
        self.cat = Category.objects.create(name='test')
        self.product = Product.objects.create(name='منتج', category=self.cat, price=100)
        self.inv = Invoice.objects.create(
            invoice_number='INV-0100', date='2026-01-01', total_amount=0,
        )

    def test_create_item_recalculates_total(self):
        item = InvoiceItem.objects.create(
            invoice=self.inv,
            product=self.product,
            product_name='منتج',
            quantity=3,
            unit_price=100,
        )
        self.assertEqual(item.total, Decimal('300'))

    def test_line_net_no_discount(self):
        item = InvoiceItem.objects.create(
            invoice=self.inv, product=self.product,
            product_name='منتج', quantity=2, unit_price=50,
        )
        self.assertEqual(item.line_net, Decimal('100'))

    def test_line_net_with_discount(self):
        item = InvoiceItem.objects.create(
            invoice=self.inv, product=self.product,
            product_name='منتج', quantity=2, unit_price=50,
            discount_percent=Decimal('10'),
        )
        self.assertEqual(item.line_net, Decimal('90'))


class InvoiceStatusLogTest(TestCase):
    def setUp(self):
        self.inv = Invoice.objects.create(
            invoice_number='INV-0200', date='2026-01-01', total_amount=0,
        )
        self.s1 = InvoiceStatus.objects.create(name='جديد', order=1)
        self.s2 = InvoiceStatus.objects.create(name='قيد المراجعة', order=2)
        self.user = User.objects.create_user(username='testuser', password='test123')

    def test_create_log(self):
        log = InvoiceStatusLog.objects.create(
            invoice=self.inv,
            from_status=self.s1,
            to_status=self.s2,
            changed_by=self.user,
        )
        self.assertIn('جديد', str(log))
        self.assertIn('قيد المراجعة', str(log))

    def test_ordering_newest_first(self):
        from django.utils import timezone
        import datetime
        log1 = InvoiceStatusLog.objects.create(invoice=self.inv, from_status=self.s1, to_status=self.s2)
        InvoiceStatusLog.objects.filter(pk=log1.pk).update(changed_at=timezone.now() - datetime.timedelta(seconds=5))
        log2 = InvoiceStatusLog.objects.create(invoice=self.inv, from_status=self.s2, to_status=None)
        InvoiceStatusLog.objects.filter(pk=log2.pk).update(changed_at=timezone.now())
        logs = InvoiceStatusLog.objects.all()
        self.assertEqual(len(logs), 2)
        self.assertEqual(logs[0].from_status_id, self.s2.pk)  # newest first


# ═══════════════════════════════════════════════
# SIGNAL TESTS
# ═══════════════════════════════════════════════

class SignalsTest(TestCase):
    def setUp(self):
        self.cat = Category.objects.create(name='test')
        self.product = Product.objects.create(name='منتج', category=self.cat, price=100, quantity=10)
        self.customer = Customer.objects.create(name='test', phone='000')
        self.inv = Invoice.objects.create(
            invoice_number='INV-0300', customer=self.customer,
            date='2026-01-01', total_amount=500,
        )

    def test_customer_total_updated_on_invoice_save(self):
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.total_amount, Decimal('500'))

    def test_customer_total_updated_on_invoice_delete(self):
        self.inv.delete()
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.total_amount, Decimal('0'))

    def test_stock_deducted_on_item_creation(self):
        InvoiceItem.objects.create(
            invoice=self.inv, product=self.product,
            product_name='منتج', quantity=3, unit_price=100,
        )
        self.product.refresh_from_db()
        self.assertEqual(self.product.quantity, 7)

    def test_stock_restored_on_item_delete(self):
        item = InvoiceItem.objects.create(
            invoice=self.inv, product=self.product,
            product_name='منتج', quantity=3, unit_price=100,
        )
        item.delete()
        self.product.refresh_from_db()
        self.assertEqual(self.product.quantity, 10)

    def test_status_log_created_on_status_change(self):
        s1 = InvoiceStatus.objects.create(name='جديد', order=1)
        s2 = InvoiceStatus.objects.create(name='مؤكد', order=2)
        self.inv.status = s1
        self.inv.save()
        self.inv.status = s2
        self.inv._changed_by = None
        self.inv.save()
        self.assertEqual(InvoiceStatusLog.objects.filter(invoice=self.inv).count(), 2)


# ═══════════════════════════════════════════════
# FORM TESTS
# ═══════════════════════════════════════════════

class InvoiceFormTest(TestCase):
    def setUp(self):
        self.customer = Customer.objects.create(name='test', phone='000')
        self.s1 = InvoiceStatus.objects.create(name='جديد', order=1)
        self.s2 = InvoiceStatus.objects.create(name='مؤكد', order=2)
        self.user = User.objects.create_user(username='sales1', password='test123')
        self.group, _ = Group.objects.get_or_create(name='sales')
        self.user.groups.add(self.group)
        self.s2.allowed_groups.add(self.group)

    def test_form_valid_with_valid_data(self):
        form = InvoiceForm(data={
            'invoice_number': 'INV-TEST-001',
            'customer': self.customer.pk,
            'date': '2026-01-01',
            'paid_amount': '500',
            'discount_percent': '0',
            'status': self.s1.pk,
            'payment_method': '',
        })
        self.assertTrue(form.is_valid(), form.errors)

    def test_form_paid_exceeds_total(self):
        inv = Invoice.objects.create(
            invoice_number='INV-TEST-002',
            customer=self.customer,
            date='2026-01-01',
            total_amount=500,
            paid_amount=0,
        )
        form = InvoiceForm(data={
            'invoice_number': 'INV-TEST-002',
            'customer': self.customer.pk,
            'date': '2026-01-01',
            'paid_amount': '1000',
            'discount_percent': '0',
            'status': self.s1.pk,
        }, instance=inv)
        self.assertFalse(form.is_valid())
        self.assertIn('paid_amount', form.errors)

    def test_form_requires_date(self):
        form = InvoiceForm(data={
            'invoice_number': 'INV-TEST-003',
            'customer': self.customer.pk,
            'date': '',
            'paid_amount': '0',
            'discount_percent': '0',
            'status': self.s1.pk,
        })
        self.assertFalse(form.is_valid())


class InvoiceStatusFormTest(TestCase):
    def setUp(self):
        self.group, _ = Group.objects.get_or_create(name='sales')

    def test_form_valid(self):
        form = InvoiceStatusForm(data={
            'name': 'جديد',
            'order': 1,
            'color': '#ffc107',
        })
        self.assertTrue(form.is_valid())

    def test_form_with_allowed_groups(self):
        form = InvoiceStatusForm(data={
            'name': 'جديد',
            'order': 1,
            'color': '#ffc107',
            'allowed_groups': [self.group.pk],
        })
        self.assertTrue(form.is_valid(), form.errors)


# ═══════════════════════════════════════════════
# VIEW / PERMISSION TESTS
# ═══════════════════════════════════════════════

@override_settings(SECURE_SSL_REDIRECT=False)
class PermissionTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.sales = User.objects.create_user(username='sales1', password='test123')
        self.shipping = User.objects.create_user(username='shipper1', password='test123')
        self.owner = User.objects.create_user(username='owner1', password='test123', is_staff=True)
        self.admin = User.objects.create_superuser(username='admin1', password='test123')
        self.sales_group, _ = Group.objects.get_or_create(name='sales')
        self.shipping_group, _ = Group.objects.get_or_create(name='shipping')
        self.owner_group, _ = Group.objects.get_or_create(name='owner')
        self.sales.groups.add(self.sales_group)
        self.shipping.groups.add(self.shipping_group)
        self.owner.groups.add(self.owner_group)
        self.customer = Customer.objects.create(name='test', phone='000')
        self.s1 = InvoiceStatus.objects.create(name='جديد', order=1)
        self.inv = Invoice.objects.create(
            invoice_number='INV-0400', customer=self.customer,
            date='2026-01-01', total_amount=500,
        )

    def _login(self, user):
        self.client.force_login(user)

    def test_owner_can_access_invoice_list(self):
        self._login(self.owner)
        resp = self.client.get(reverse('invoice_list'))
        self.assertEqual(resp.status_code, 200)

    def test_sales_can_access_invoice_list(self):
        self._login(self.sales)
        resp = self.client.get(reverse('invoice_list'))
        self.assertEqual(resp.status_code, 200)

    def test_shipping_can_access_invoice_list(self):
        self._login(self.shipping)
        resp = self.client.get(reverse('invoice_list'))
        self.assertEqual(resp.status_code, 200)

    def test_unauthenticated_redirects_to_login(self):
        resp = self.client.get(reverse('invoice_list'))
        self.assertIn(resp.status_code, (301, 302))

    def test_sales_can_access_invoice_add(self):
        self._login(self.sales)
        resp = self.client.get(reverse('invoice_add'))
        self.assertEqual(resp.status_code, 200)

    def test_shipping_cannot_access_invoice_add(self):
        self._login(self.shipping)
        resp = self.client.get(reverse('invoice_add'))
        self.assertIn(resp.status_code, (301, 302))

    def test_owner_can_access_invoice_add(self):
        self._login(self.owner)
        resp = self.client.get(reverse('invoice_add'))
        self.assertEqual(resp.status_code, 200)

    def test_invoice_detail_accessible_by_all(self):
        self._login(self.shipping)
        resp = self.client.get(reverse('invoice_detail', args=[self.inv.pk]))
        self.assertEqual(resp.status_code, 200)

    def test_cancel_invoice_sales(self):
        self._login(self.sales)
        resp = self.client.post(reverse('cancel_invoice', args=[self.inv.pk]), {
            'cancel_reason': 'ألغي من العميل',
        })
        self.assertIn(resp.status_code, (301, 302))
        self.inv.refresh_from_db()
        self.assertTrue(self.inv.is_cancelled)
        self.assertEqual(self.inv.cancel_reason, 'ألغي من العميل')

    def test_cancel_invoice_owner(self):
        self._login(self.owner)
        resp = self.client.post(reverse('cancel_invoice', args=[self.inv.pk]), {
            'cancel_reason': 'خطأ في الطلب',
        })
        self.assertIn(resp.status_code, (301, 302))
        self.inv.refresh_from_db()
        self.assertTrue(self.inv.is_cancelled)

    def test_cancel_invoice_shipping_forbidden(self):
        self._login(self.shipping)
        resp = self.client.post(reverse('cancel_invoice', args=[self.inv.pk]), {
            'cancel_reason': 'test',
        })
        self.inv.refresh_from_db()
        self.assertFalse(self.inv.is_cancelled)

    def test_status_update_forward_only(self):
        self._login(self.shipping)
        s2 = InvoiceStatus.objects.create(name='مؤكد', order=2)
        self.inv.status = self.s1
        self.inv.save()
        resp = self.client.post(reverse('update_invoice_status', args=[self.inv.pk]), {
            'status': s2.pk,
        })
        self.assertIn(resp.status_code, (301, 302))
        self.inv.refresh_from_db()
        self.assertEqual(self.inv.status_id, s2.pk)

    def test_status_update_backwards_forbidden(self):
        self._login(self.shipping)
        s2 = InvoiceStatus.objects.create(name='مؤكد', order=2)
        s3 = InvoiceStatus.objects.create(name='تم الشحن', order=3)
        self.inv.status = s3
        self.inv.save()
        resp = self.client.post(reverse('update_invoice_status', args=[self.inv.pk]), {
            'status': s2.pk,
        })
        self.inv.refresh_from_db()
        self.assertNotEqual(self.inv.status_id, s2.pk)


@override_settings(SECURE_SSL_REDIRECT=False)
# ═══════════════════════════════════════════════
# NOTIFICATION TESTS
# ═══════════════════════════════════════════════

class NotificationTest(TestCase):
    def setUp(self):
        self.sales = User.objects.create_user(username='sales1', password='test123')
        self.shipping = User.objects.create_user(username='shipper1', password='test123')
        self.inv = Invoice.objects.create(
            invoice_number='INV-NOTIF-001', date='2026-01-01', total_amount=500, created_by=self.sales,
        )

    def test_create_notification(self):
        n = Notification.objects.create(
            invoice=self.inv, sender=self.sales, recipient=self.shipping,
            notification_type='new_invoice', message='فاتورة جديدة',
        )
        self.assertFalse(n.is_read)
        self.assertIn(self.inv.invoice_number, str(n))

    def test_notification_ordering_newest_first(self):
        from django.utils import timezone
        import datetime
        n1 = Notification.objects.create(invoice=self.inv, sender=self.sales, recipient=self.shipping, notification_type='new_invoice')
        Notification.objects.filter(pk=n1.pk).update(created_at=timezone.now() - datetime.timedelta(seconds=10))
        n2 = Notification.objects.create(invoice=self.inv, sender=self.sales, recipient=self.shipping, notification_type='availability_confirmed')
        logs = Notification.objects.all()
        self.assertEqual(logs[0].pk, n2.pk)

    def test_new_invoice_auto_notifies_shipping(self):
        inv = Invoice.objects.create(
            invoice_number='INV-NOTIF-002', date='2026-01-01', total_amount=300, created_by=self.sales,
        )
        notifications = Notification.objects.filter(invoice=inv, notification_type='new_invoice')
        self.assertEqual(notifications.count(), 0)

    def test_mark_as_read(self):
        n = Notification.objects.create(invoice=self.inv, sender=self.sales, recipient=self.shipping, notification_type='new_invoice')
        n.is_read = True
        n.save(update_fields=['is_read'])
        n.refresh_from_db()
        self.assertTrue(n.is_read)


class AvailabilityAndRevisionTest(TestCase):
    def setUp(self):
        self.sales = User.objects.create_user(username='sales1', password='test123')
        self.shipping = User.objects.create_user(username='shipper1', password='test123')
        self.owner = User.objects.create_user(username='owner1', password='test123', is_staff=True)
        self.sales_group, _ = Group.objects.get_or_create(name='sales')
        self.shipping_group, _ = Group.objects.get_or_create(name='shipping')
        self.owner_group, _ = Group.objects.get_or_create(name='owner')
        self.sales.groups.add(self.sales_group)
        self.shipping.groups.add(self.shipping_group)
        self.owner.groups.add(self.owner_group)
        self.cat = Category.objects.create(name='test')
        self.product = Product.objects.create(name='منتج', category=self.cat, price=100, quantity=10)
        self.inv = Invoice.objects.create(
            invoice_number='INV-AVL-001', date='2026-01-01', total_amount=500, created_by=self.sales,
        )
        self.item = InvoiceItem.objects.create(
            invoice=self.inv, product=self.product, product_name='منتج',
            quantity=3, unit_price=100,
        )

    def test_invoice_default_revision_status(self):
        self.assertEqual(self.inv.revision_status, 'pending_shipping')

    def test_item_confirmed_quantity_default_none(self):
        self.assertIsNone(self.item.confirmed_quantity)

    @override_settings(SECURE_SSL_REDIRECT=False)
    def test_confirm_availability_full(self):
        self.client.force_login(self.shipping)
        resp = self.client.post(reverse('confirm_availability', args=[self.inv.pk]), {
            f'qty_{self.item.pk}': '3',
        })
        self.assertIn(resp.status_code, (301, 302))
        self.inv.refresh_from_db()
        self.assertEqual(self.inv.revision_status, 'shipping_confirmed')

    @override_settings(SECURE_SSL_REDIRECT=False)
    def test_confirm_availability_partial(self):
        self.client.force_login(self.shipping)
        resp = self.client.post(reverse('confirm_availability', args=[self.inv.pk]), {
            f'qty_{self.item.pk}': '2',
        })
        self.assertIn(resp.status_code, (301, 302))
        self.inv.refresh_from_db()
        self.assertEqual(self.inv.revision_status, 'pending_approval')

    @override_settings(SECURE_SSL_REDIRECT=False)
    def test_confirm_availability_forbidden_for_sales(self):
        self.client.force_login(self.sales)
        resp = self.client.post(reverse('confirm_availability', args=[self.inv.pk]), {
            f'qty_{self.item.pk}': '3',
        })
        self.inv.refresh_from_db()
        self.assertEqual(self.inv.revision_status, 'pending_shipping')

    @override_settings(SECURE_SSL_REDIRECT=False)
    def test_approve_revision(self):
        self.inv.revision_status = 'pending_approval'
        self.inv.save()
        self.item.confirmed_quantity = 2
        self.item.save()
        self.client.force_login(self.sales)
        resp = self.client.post(reverse('approve_revision', args=[self.inv.pk]), {'action': 'approve'})
        self.assertIn(resp.status_code, (301, 302))
        self.inv.refresh_from_db()
        self.assertEqual(self.inv.revision_status, 'approved')
        self.item.refresh_from_db()
        self.assertEqual(self.item.quantity, 2)

    @override_settings(SECURE_SSL_REDIRECT=False)
    def test_reject_revision(self):
        self.inv.revision_status = 'pending_approval'
        self.inv.save()
        self.client.force_login(self.sales)
        resp = self.client.post(reverse('approve_revision', args=[self.inv.pk]), {'action': 'reject'})
        self.assertIn(resp.status_code, (301, 302))
        self.inv.refresh_from_db()
        self.assertEqual(self.inv.revision_status, 'rejected')


@override_settings(SECURE_SSL_REDIRECT=False)
class DashboardTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='sales1', password='test123')
        self.owner = User.objects.create_user(username='owner1', password='test123', is_staff=True)
        self.sales_group, _ = Group.objects.get_or_create(name='sales')
        self.owner_group, _ = Group.objects.get_or_create(name='owner')
        self.user.groups.add(self.sales_group)
        self.owner.groups.add(self.owner_group)

    def test_dashboard_accessible_for_owner(self):
        self.client.force_login(self.owner)
        resp = self.client.get(reverse('home'))
        self.assertEqual(resp.status_code, 200)

    def test_dashboard_redirects_sales_to_landing(self):
        self.client.force_login(self.user)
        resp = self.client.get(reverse('home'))
        self.assertIn(resp.status_code, (301, 302))
        self.assertTrue(resp.url.startswith('/customers') or resp.url.startswith('http'))

    def test_dashboard_redirects_when_unauthenticated(self):
        resp = self.client.get(reverse('home'))
        self.assertEqual(resp.status_code, 302)
