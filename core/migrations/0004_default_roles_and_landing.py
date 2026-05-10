from django.db import migrations


def create_default_groups_and_landing(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    RoleLanding = apps.get_model('core', 'RoleLanding')

    for group_name, landing_page, dashboard_blocked in [
        ('sales', 'customer_list', True),
        ('shipping', 'customer_list', True),
        ('owner', '', False),
    ]:
        group, _ = Group.objects.get_or_create(name=group_name)
        RoleLanding.objects.get_or_create(
            group=group,
            defaults={
                'landing_page': landing_page,
                'dashboard_blocked': dashboard_blocked,
            }
        )


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0003_rolelanding'),
    ]

    operations = [
        migrations.RunPython(create_default_groups_and_landing),
    ]
