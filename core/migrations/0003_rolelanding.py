from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
        ('core', '0002_invoicetemplate'),
    ]

    operations = [
        migrations.CreateModel(
            name='RoleLanding',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('landing_page', models.CharField(blank=True, help_text='اسم مسار URL (مثال: customer_list)', max_length=100, verbose_name='صفحة الهبوط')),
                ('dashboard_blocked', models.BooleanField(default=False, help_text='عند التفعيل، يتم توجيه المستخدم بعيداً عن لوحة التحكم', verbose_name='حظر لوحة التحكم')),
                ('group', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to='auth.group', verbose_name='المجموعة')),
            ],
            options={
                'verbose_name': 'إعدادات المجموعة',
                'verbose_name_plural': 'إعدادات المجموعات',
            },
        ),
    ]
