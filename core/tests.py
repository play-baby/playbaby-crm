from django.test import TestCase
from django.core.cache import cache
from django.contrib.auth.models import Group
from core.models import SiteSetting, RoleLanding, InvoiceTemplate


class SiteSettingTest(TestCase):
    def setUp(self):
        cache.clear()
        SiteSetting.objects.all().delete()

    def test_singleton_always_pk_1(self):
        s1 = SiteSetting.get()
        s2 = SiteSetting.get()
        self.assertEqual(s1.pk, 1)
        self.assertEqual(s2.pk, 1)

    def test_get_or_creates(self):
        SiteSetting.objects.all().delete()
        cache.clear()
        obj = SiteSetting.get()
        self.assertEqual(SiteSetting.objects.count(), 1)

    def test_save_keeps_pk_1(self):
        obj = SiteSetting.get()
        obj.save()
        self.assertEqual(obj.pk, 1)

    def test_delete_is_noop(self):
        obj = SiteSetting.get()
        obj.delete()
        self.assertEqual(SiteSetting.objects.count(), 1)

    def test_cache_used_on_get(self):
        cache.clear()
        SiteSetting.get()
        self.assertIsNotNone(cache.get('site_setting'))


class RoleLandingTest(TestCase):
    def setUp(self):
        # Use unique name to avoid collision with migration-created groups
        self.group = Group.objects.create(name='_test_role_group')

    def test_create_role_landing(self):
        rl = RoleLanding.objects.create(group=self.group, landing_page='home', dashboard_blocked=False)
        self.assertEqual(rl.group.name, '_test_role_group')
        self.assertEqual(rl.landing_page, 'home')

    def test_str(self):
        rl = RoleLanding.objects.create(group=self.group, landing_page='invoice_list')
        self.assertIn('invoice_list', str(rl))

    def test_cascade_delete(self):
        RoleLanding.objects.all().delete()
        rl = RoleLanding.objects.create(group=self.group)
        self.group.delete()
        self.assertEqual(RoleLanding.objects.count(), 0)


class InvoiceTemplateTest(TestCase):
    def setUp(self):
        cache.clear()
        InvoiceTemplate.objects.all().delete()

    def test_singleton_always_pk_1(self):
        t1 = InvoiceTemplate.get()
        t2 = InvoiceTemplate.get()
        self.assertEqual(t1.pk, 1)
        self.assertEqual(t2.pk, 1)

    def test_default_values(self):
        t = InvoiceTemplate.get()
        self.assertEqual(t.primary_color, '#dc143c')
        self.assertEqual(t.phone_font_size, 11)
        self.assertEqual(t.phone_color, '#888888')
        self.assertEqual(t.footer_message, 'شكراً لتسوقكم معنا')

    def test_save_and_get_populates_cache(self):
        t = InvoiceTemplate.get()
        t.primary_color = '#000000'
        t.save()

        InvoiceTemplate.get()
        cached = cache.get('invoice_template')
        self.assertIsNotNone(cached)
        self.assertEqual(cached.primary_color, '#000000')

    def test_delete_is_noop(self):
        InvoiceTemplate.objects.all().delete()
        cache.clear()
        t = InvoiceTemplate.get()
        t.delete()
        self.assertEqual(InvoiceTemplate.objects.count(), 1)
