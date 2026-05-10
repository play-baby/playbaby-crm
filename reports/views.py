import json
from datetime import timedelta
from calendar import month_name
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db.models import Sum, Count, F, ExpressionWrapper, DecimalField, Avg
from invoices.models import Invoice, InvoiceItem, InvoiceStatusLog
from products.models import Product, Category
from customers.models import Customer
from lingerie_crm.roles import is_owner

MONTH_NAMES_AR = {
    1: 'يناير', 2: 'فبراير', 3: 'مارس', 4: 'أبريل',
    5: 'مايو', 6: 'يونيو', 7: 'يوليو', 8: 'أغسطس',
    9: 'سبتمبر', 10: 'أكتوبر', 11: 'نوفمبر', 12: 'ديسمبر',
}


def _owner_or_admin(user):
    return user.is_authenticated and (is_owner(user) or user.is_superuser)


@login_required
def revenue_report(request):
    if not _owner_or_admin(request.user):
        return render(request, 'reports/_blocked.html')
    today = timezone.now().date()
    year = int(request.GET.get('year', today.year))
    months_data = []
    for m in range(1, 13):
        qs = Invoice.objects.filter(date__year=year, date__month=m)
        total = qs.aggregate(t=Sum('total_amount'))['t'] or 0
        paid = qs.aggregate(t=Sum('paid_amount'))['t'] or 0
        count = qs.count()
        months_data.append({
            'month_num': m,
            'month_name': MONTH_NAMES_AR[m],
            'revenue': float(total),
            'paid': float(paid),
            'count': count,
        })
    total_revenue = sum(m['revenue'] for m in months_data)
    total_paid = sum(m['paid'] for m in months_data)
    total_invoices = sum(m['count'] for m in months_data)
    available_years = range(2023, today.year + 2)
    return render(request, 'reports/revenue.html', {
        'page_title': 'تقرير الإيرادات',
        'months_data': months_data,
        'months_json': json.dumps([m['month_name'] for m in months_data]),
        'revenue_json': json.dumps([m['revenue'] for m in months_data]),
        'paid_json': json.dumps([m['paid'] for m in months_data]),
        'counts_json': json.dumps([m['count'] for m in months_data]),
        'total_revenue': total_revenue,
        'total_paid': total_paid,
        'total_invoices': total_invoices,
        'selected_year': year,
        'available_years': available_years,
    })


@login_required
def products_report(request):
    if not _owner_or_admin(request.user):
        return render(request, 'reports/_blocked.html')
    top_products = (
        InvoiceItem.objects.values('product_name', 'product_id')
        .annotate(
            total_qty=Sum('quantity'),
            total_rev=Sum('total'),
            invoice_count=Count('invoice', distinct=True),
        )
        .order_by('-total_qty')[:50]
    )
    total_qty_all = sum(p['total_qty'] for p in top_products)
    total_rev_all = sum(p['total_rev'] for p in top_products)
    category_dist = (
        InvoiceItem.objects.filter(product__category__isnull=False)
        .values('product__category__name')
        .annotate(total=Sum('total'), count=Count('id'))
        .order_by('-total')
    )
    cat_labels = [c['product__category__name'] for c in category_dist]
    cat_values = [float(c['total']) for c in category_dist]
    cat_counts = [c['count'] for c in category_dist]
    return render(request, 'reports/products.html', {
        'page_title': 'تقرير المنتجات',
        'top_products': top_products,
        'total_qty_all': total_qty_all,
        'total_rev_all': total_rev_all,
        'cat_labels_json': json.dumps(cat_labels),
        'cat_values_json': json.dumps(cat_values),
        'cat_counts_json': json.dumps(cat_counts),
    })


@login_required
def customers_report(request):
    if not _owner_or_admin(request.user):
        return render(request, 'reports/_blocked.html')
    top_customers = Customer.objects.filter(total_amount__gt=0).order_by('-total_amount')[:50]
    total_customers = Customer.objects.count()
    customers_with_purchases = Customer.objects.filter(total_amount__gt=0).count()
    return render(request, 'reports/customers.html', {
        'page_title': 'تقرير العملاء',
        'top_customers': top_customers,
        'total_customers': total_customers,
        'customers_with_purchases': customers_with_purchases,
    })


@login_required
def status_distribution_report(request):
    if not _owner_or_admin(request.user):
        return render(request, 'reports/_blocked.html')
    status_dist = (
        Invoice.objects.filter(status__isnull=False)
        .values('status__name', 'status__color')
        .annotate(count=Count('id'), total=Sum('total_amount'))
        .order_by('-count')
    )
    cancelled_count = Invoice.objects.filter(is_cancelled=True).count()
    cancelled_total = Invoice.objects.filter(is_cancelled=True).aggregate(t=Sum('total_amount'))['t'] or 0
    revision_dist = (
        Invoice.objects.exclude(revision_status='pending_shipping')
        .values('revision_status')
        .annotate(count=Count('id'))
        .order_by('-count')
    )
    revision_labels_map = {
        'shipping_confirmed': 'تم تأكيد الشحن',
        'pending_approval': 'بانتظار الموافقة',
        'approved': 'تمت الموافقة',
        'rejected': 'مرفوض',
    }
    revision_data = []
    for r in revision_dist:
        revision_data.append({
            'status': revision_labels_map.get(r['revision_status'], r['revision_status']),
            'count': r['count'],
        })
    return render(request, 'reports/status_distribution.html', {
        'page_title': 'توزيع حالات الفواتير',
        'status_dist': status_dist,
        'status_labels_json': json.dumps([s['status__name'] for s in status_dist]),
        'status_counts_json': json.dumps([s['count'] for s in status_dist]),
        'status_colors_json': json.dumps([s['status__color'] for s in status_dist]),
        'status_revenue_json': json.dumps([float(s['total']) for s in status_dist]),
        'cancelled_count': cancelled_count,
        'cancelled_total': cancelled_total,
        'revision_data': revision_data,
    })


@login_required
def collection_report(request):
    if not _owner_or_admin(request.user):
        return render(request, 'reports/_blocked.html')
    today = timezone.now().date()
    year = int(request.GET.get('year', today.year))
    all_qs = Invoice.objects.filter(is_cancelled=False)
    collected = all_qs.filter(is_collected=True)
    uncollected = all_qs.filter(is_collected=False)
    total_collected_amount = collected.aggregate(t=Sum('total_amount'))['t'] or 0
    total_collected_paid = collected.aggregate(t=Sum('paid_amount'))['t'] or 0
    total_uncollected_amount = uncollected.aggregate(t=Sum('total_amount'))['t'] or 0
    total_uncollected_paid = uncollected.aggregate(t=Sum('paid_amount'))['t'] or 0
    collected_count = collected.count()
    uncollected_count = uncollected.count()
    months_data = []
    for m in range(1, 13):
        qs = collected.filter(collected_at__year=year, collected_at__month=m)
        total = qs.aggregate(t=Sum('total_amount'))['t'] or 0
        paid = qs.aggregate(t=Sum('paid_amount'))['t'] or 0
        count = qs.count()
        months_data.append({
            'month_num': m,
            'month_name': MONTH_NAMES_AR[m],
            'total_amount': float(total),
            'paid_amount': float(paid),
            'count': count,
        })
    collector_data = (
        collected.values('collected_by__username')
        .annotate(count=Count('id'), total=Sum('total_amount'), paid=Sum('paid_amount'))
        .order_by('-total')
    )
    r = total_collected_amount + total_uncollected_amount
    collection_rate = round(total_collected_amount / r * 100, 1) if r else 0
    return render(request, 'reports/collection.html', {
        'page_title': 'تقرير التحصيل',
        'months_data': months_data,
        'months_json': json.dumps([m['month_name'] for m in months_data]),
        'collected_amounts_json': json.dumps([m['total_amount'] for m in months_data]),
        'collected_paid_json': json.dumps([m['paid_amount'] for m in months_data]),
        'collected_counts_json': json.dumps([m['count'] for m in months_data]),
        'total_collected_amount': total_collected_amount,
        'total_collected_paid': total_collected_paid,
        'total_uncollected_amount': total_uncollected_amount,
        'total_uncollected_paid': total_uncollected_paid,
        'collected_count': collected_count,
        'uncollected_count': uncollected_count,
        'collection_rate': collection_rate,
        'collector_data': collector_data,
        'selected_year': year,
        'available_years': range(2023, today.year + 2),
    })


@login_required
def shipping_performance_report(request):
    if not _owner_or_admin(request.user):
        return render(request, 'reports/_blocked.html')
    today = timezone.now().date()
    logs = InvoiceStatusLog.objects.filter(
        to_status__isnull=False,
        from_status__isnull=False,
    ).select_related('invoice', 'to_status', 'from_status', 'changed_by').order_by('-changed_at')[:200]
    shipping_logs = []
    for log in logs:
        if log.changed_by and log.changed_by.groups.filter(name='shipping').exists():
            shipping_logs.append(log)
    total_shipped = len(shipping_logs)
    by_shipper = {}
    for log in shipping_logs:
        name = log.changed_by.username if log.changed_by else 'غير معروف'
        by_shipper.setdefault(name, {'count': 0, 'invoices': set()})
        by_shipper[name]['count'] += 1
        by_shipper[name]['invoices'].add(log.invoice_id)
    shipper_stats = [
        {'name': name, 'actions': data['count'], 'invoices': len(data['invoices'])}
        for name, data in sorted(by_shipper.items(), key=lambda x: -x[1]['count'])
    ]
    pending_confirm = Invoice.objects.filter(
        revision_status='pending_shipping',
        is_cancelled=False,
    ).count()
    confirmed = Invoice.objects.filter(
        revision_status__in=['shipping_confirmed', 'pending_approval', 'approved'],
        is_cancelled=False,
    ).count()
    return render(request, 'reports/shipping_performance.html', {
        'page_title': 'أداء الشحن',
        'total_shipped': total_shipped,
        'shipper_stats': shipper_stats,
        'pending_confirm': pending_confirm,
        'confirmed': confirmed,
    })
