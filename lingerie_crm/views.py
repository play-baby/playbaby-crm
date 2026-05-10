from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from datetime import timedelta
import calendar
from customers.models import Customer
from products.models import Product
from invoices.models import Invoice, InvoiceItem
from django.db.models import Sum, F, ExpressionWrapper, DecimalField, Count
from lingerie_crm.roles import is_owner

@login_required
def dashboard(request):
    is_owner_user = is_owner(request.user)
    today = timezone.now().date()
    first_of_month = today.replace(day=1)

    # ── Overview Counts ──
    customers_count = Customer.objects.count()
    products_count = Product.objects.count()
    invoices_count = Invoice.objects.count()
    total_revenue = Invoice.objects.aggregate(total=Sum('total_amount'))['total'] or 0
    total_paid = Invoice.objects.aggregate(total=Sum('paid_amount'))['total'] or 0
    low_stock = Product.objects.filter(quantity__lt=10).count()
    out_of_stock = Product.objects.filter(quantity=0).count()

    # ── Today / Week / Month KPIs ──
    today_invoices = Invoice.objects.filter(date=today)
    today_revenue = today_invoices.aggregate(t=Sum('total_amount'))['t'] or 0
    today_count = today_invoices.count()

    week_start = today - timedelta(days=today.weekday())
    week_invoices = Invoice.objects.filter(date__gte=week_start)
    week_revenue = week_invoices.aggregate(t=Sum('total_amount'))['t'] or 0
    week_count = week_invoices.count()

    month_invoices = Invoice.objects.filter(date__gte=first_of_month)
    month_revenue = month_invoices.aggregate(t=Sum('total_amount'))['t'] or 0

    # ── Monthly Revenue (last 6 months) ──
    months_data = []
    for i in range(5, -1, -1):
        m = today.month - i
        y = today.year
        while m < 1:
            m += 12
            y -= 1
        month_total = Invoice.objects.filter(
            date__year=y, date__month=m
        ).aggregate(t=Sum('total_amount'))['t'] or 0
        month_paid = Invoice.objects.filter(
            date__year=y, date__month=m
        ).aggregate(t=Sum('paid_amount'))['t'] or 0
        months_data.append({
            'label': calendar.month_name[m][:3],
            'revenue': float(month_total),
            'paid': float(month_paid),
        })

    monthly_labels = [m['label'] for m in months_data]
    monthly_revenue = [m['revenue'] for m in months_data]
    monthly_paid = [m['paid'] for m in months_data]

    # ── Top 5 Products ──
    top_products = (
        InvoiceItem.objects.values('product_name')
        .annotate(total_qty=Sum('quantity'), total_rev=Sum('total'))
        .order_by('-total_qty')[:5]
    )

    # ── Top 5 Customers ──
    top_customers = Customer.objects.filter(total_amount__gt=0).order_by('-total_amount')[:5]

    # ── Payment Method Distribution ──
    payment_dist = (
        Invoice.objects.filter(payment_method__isnull=False)
        .values('payment_method__name')
        .annotate(total=Sum('total_amount'))
        .order_by('-total')
    )
    payment_labels = [p['payment_method__name'] for p in payment_dist]
    payment_values = [float(p['total']) for p in payment_dist]

    # ── Invoice Status Distribution ──
    status_dist = (
        Invoice.objects.filter(status__isnull=False)
        .values('status__name', 'status__color')
        .annotate(count=Count('id'))
        .order_by('-count')
    )
    status_labels = [s['status__name'] for s in status_dist]
    status_counts = [s['count'] for s in status_dist]
    status_colors = [s['status__color'] for s in status_dist]

    # ── Latest Activity ──
    recent_invoices = Invoice.objects.select_related('customer', 'created_by').order_by('-created_at')[:8]

    # ── Low Stock Products ──
    low_stock_products = Product.objects.filter(quantity__lt=10).order_by('quantity')[:10]

    context = {
        'customers_count': customers_count,
        'products_count': products_count,
        'invoices_count': invoices_count,
        'total_revenue': total_revenue,
        'total_paid': total_paid,
        'outstanding': total_revenue - total_paid,
        'low_stock': low_stock,
        'out_of_stock': out_of_stock,
        'page_title': 'لوحة التحكم',
        # KPIs
        'today_revenue': today_revenue,
        'today_count': today_count,
        'week_revenue': week_revenue,
        'week_count': week_count,
        'month_revenue': month_revenue,
        # Charts
        'monthly_labels': monthly_labels,
        'monthly_revenue': monthly_revenue,
        'monthly_paid': monthly_paid,
        'top_products': list(top_products),
        'top_customers': top_customers,
        'payment_labels': payment_labels,
        'payment_values': payment_values,
        'status_labels': status_labels,
        'status_counts': status_counts,
        'status_colors': status_colors,
        'recent_invoices': recent_invoices,
        'low_stock_products': low_stock_products,
    }

    if is_owner_user:
        unpaid_invoices_count = Invoice.objects.filter(
            paid_amount__lt=F('total_amount')
        ).count() if total_revenue > 0 else 0

        profit = InvoiceItem.objects.filter(
            product__cost__isnull=False
        ).aggregate(
            total_profit=Sum(
                ExpressionWrapper(
                    F('unit_price') - F('product__cost'),
                    output_field=DecimalField(max_digits=10, decimal_places=2)
                ) * F('quantity')
            )
        )['total_profit'] or 0

        revenue_with_cost = InvoiceItem.objects.filter(
            product__cost__isnull=False
        ).aggregate(
            total_rev=Sum(
                ExpressionWrapper(
                    F('unit_price'),
                    output_field=DecimalField(max_digits=10, decimal_places=2)
                ) * F('quantity')
            )
        )['total_rev'] or 0

        total_cost = InvoiceItem.objects.filter(
            product__cost__isnull=False
        ).aggregate(
            total_c=Sum(
                ExpressionWrapper(
                    F('product__cost'),
                    output_field=DecimalField(max_digits=10, decimal_places=2)
                ) * F('quantity')
            )
        )['total_c'] or 0

        if revenue_with_cost > 0:
            profit_margin = (profit / revenue_with_cost) * 100
        else:
            profit_margin = 0

        context['unpaid_invoices_count'] = unpaid_invoices_count
        context['profit'] = profit
        context['total_cost'] = total_cost
        context['profit_margin'] = profit_margin

    return render(request, 'dashboard.html', context)
