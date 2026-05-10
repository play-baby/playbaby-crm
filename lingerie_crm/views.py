from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from customers.models import Customer
from products.models import Product
from invoices.models import Invoice, InvoiceItem
from django.db.models import Sum, F, ExpressionWrapper, DecimalField
from lingerie_crm.roles import is_owner

@login_required
def dashboard(request):
    is_owner_user = is_owner(request.user)

    customers_count = Customer.objects.count()
    products_count = Product.objects.count()
    invoices_count = Invoice.objects.count()
    total_revenue = Invoice.objects.aggregate(total=Sum('total_amount'))['total'] or 0
    total_paid = Invoice.objects.aggregate(total=Sum('paid_amount'))['total'] or 0
    low_stock = Product.objects.filter(quantity__lt=10).count()
    latest_customers = Customer.objects.order_by('-created_at')[:5]
    latest_invoices = Invoice.objects.order_by('-created_at')[:5]

    context = {
        'customers_count': customers_count,
        'products_count': products_count,
        'invoices_count': invoices_count,
        'total_revenue': total_revenue,
        'total_paid': total_paid,
        'outstanding': total_revenue - total_paid,
        'low_stock': low_stock,
        'latest_customers': latest_customers,
        'latest_invoices': latest_invoices,
        'page_title': 'لوحة التحكم',
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
