"""
Seed script: loads sample data for testing
Run: python manage.py shell < seed_data.py
"""
import os, sys, django
sys.path.insert(0, os.path.dirname(__file__))
os.chdir(os.path.dirname(__file__))
os.environ['DJANGO_SETTINGS_MODULE'] = 'lingerie_crm.settings'
django.setup()

from django.contrib.auth.models import User
from customers.models import Customer
from products.models import Category, Product
from invoices.models import Invoice, InvoiceItem
from datetime import date, timedelta
import random

# Create admin if not exists
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'admin@playbaby.com', 'playbaby123456')
    print('✅ Admin user created')

# Create categories
cat_names = ['لانجري', 'بيبي دول', 'نومة', 'ملابس داخلية', 'بدلات نوم', 'اكسسوارات']
cats = {}
for name in cat_names:
    cat, _ = Category.objects.get_or_create(name=name)
    cats[name] = cat
print(f'[OK] {len(cats)} categories created')

# Create products
product_data = [
    ('طقم لانجري دانتيل أحمر', 'لانجري', 350, 180, 25),
    ('طقم لانجري دانتيل أسود', 'لانجري', 350, 180, 20),
    ('طقم لانجري دانتيل وردي', 'لانجري', 370, 190, 15),
    ('بيبي دول قصير أحمر', 'بيبي دول', 220, 110, 30),
    ('بيبي دول قصير أسود', 'بيبي دول', 220, 110, 25),
    ('بيبي دول طويل دانتيل', 'بيبي دول', 280, 140, 18),
    ('نومة صيفي قصيرة', 'نومة', 180, 90, 40),
    ('نومة شتوي طويلة', 'نومة', 250, 125, 22),
    ('نومة دانتيل مثيرة', 'نومة', 300, 150, 12),
    ('ملابس داخلية قطن (أبيض)', 'ملابس داخلية', 80, 40, 100),
    ('ملابس داخلية قطن (أسود)', 'ملابس داخلية', 80, 40, 90),
    ('ملابس داخلية دانتيل (أحمر)', 'ملابس داخلية', 120, 60, 55),
    ('بدلة نوم حرير أسود', 'بدلات نوم', 450, 230, 10),
    ('بدلة نوم حرير أحمر', 'بدلات نوم', 450, 230, 8),
    ('روب حمام فاخر', 'بدلات نوم', 380, 190, 15),
    ('حمالة مع دانتيل', 'اكسسوارات', 65, 30, 50),
    ('دانتيل كتف', 'اكسسوارات', 45, 20, 60),
    ('عصابة رأس دانتيل', 'اكسسوارات', 35, 15, 75),
]

products_created = []
for name, cat_name, price, cost, qty in product_data:
    p, _ = Product.objects.get_or_create(
        name=name,
        defaults={
            'category': cats[cat_name],
            'price': price,
            'cost': cost,
            'quantity': qty,
            'description': f'{name} - منتج فاخر عالي الجودة'
        }
    )
    products_created.append(p)
print(f'[OK] {len(products_created)} products created')

# Create customers
customer_data = [
    ('سارة أحمد', '01001234567', 1500, 'القاهرة - مدينة نصر'),
    ('مريم علي', '01119876543', 2800, 'الجيزة - الدقي'),
    ('نورا حسن', '01223456789', 950, 'الإسكندرية - سموحة'),
    ('دينا محمود', '01534567890', 4200, 'القاهرة - المعادي'),
    ('هاجر عمر', '01045678901', 1800, 'الجيزة - الشيخ زايد'),
    ('ليلى خالد', '01156789012', 3200, 'القاهرة - التجمع'),
    ('ياسمين كريم', '01267890123', 750, 'الإسكندرية - محطة الرمل'),
    ('ندى سمير', '01078901234', 5100, 'الجيزة - المهندسين'),
    ('رنا عبدالله', '01189012345', 1200, 'القاهرة - شبرا'),
    ('أسماء طارق', '01290123456', 2600, 'الجيزة - فيصل'),
]

customers = []
for name, phone, amount, address in customer_data:
    c, _ = Customer.objects.get_or_create(
        phone=phone,
        defaults={
            'name': name,
            'address': address,
            'total_amount': amount,
            'notes': 'عميل مميز' if amount > 2000 else '',
        }
    )
    customers.append(c)
print(f'[OK] {len(customers)} customers created')

# Create invoices with items
invoice_count = 0
for i in range(15):
    invoice_num = f'INV-{i+1:03d}'
    if Invoice.objects.filter(invoice_number=invoice_num).exists():
        continue
    customer = random.choice(customers)
    inv_date = date.today() - timedelta(days=random.randint(0, 60))
    num_items = random.randint(1, 4)
    selected = random.sample(products_created, min(num_items, len(products_created)))
    inv = Invoice.objects.create(
        invoice_number=invoice_num,
        customer=customer,
        date=inv_date,
        paid_amount=0,
        notes=''
    )
    total = 0
    for p in selected:
        qty = random.randint(1, 3)
        item_total = qty * p.price
        InvoiceItem.objects.create(
            invoice=inv,
            product=p,
            product_name=p.name,
            quantity=qty,
            unit_price=p.price,
            total=item_total
        )
        total += item_total
    inv.total_amount = total
    inv.paid_amount = random.choice([0, total // 2, total])
    inv.save(update_fields=['total_amount', 'paid_amount'])
    invoice_count += 1

print(f'[OK] {invoice_count} invoices created with items')

# Update customer totals from invoices
from django.db.models import Sum
for c in customers:
    total = Invoice.objects.filter(customer=c).aggregate(Sum('total_amount'))['total_amount__sum'] or 0
    Customer.objects.filter(pk=c.pk).update(total_amount=total)

print(f'[OK] Customer totals recalculated')
print(f'\n[SUMMARY]')
print(f'   Categories: {Category.objects.count()}')
print(f'   Products:   {Product.objects.count()}')
print(f'   Customers:  {Customer.objects.count()}')
print(f'   Invoices:   {Invoice.objects.count()}')
print(f'   Items:      {InvoiceItem.objects.count()}')
print(f'\n[DONE] Sample data loaded successfully!')
