from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import Sum, F
from django.shortcuts import render
from django.utils import timezone

from inventory.models import Item
from sales.models import Sale, SaleItem, Payment
from customers.models import Customer


DEFAULT_LOW_STOCK = 5  # later we’ll move this into a Settings table


@login_required
def dashboard(request):
    now = timezone.now()
    today = timezone.localdate()

    # --- Low stock count ---
    # Stock is aggregated; threshold is per-item so we finalize in Python.
    items = (
        Item.objects.filter(is_active=True)
        .annotate(stock=Sum("movements__quantity_change"))
        .only("id", "low_stock_threshold", "is_active")
    )

    low_stock_count = 0
    for it in items:
        stock = int(it.stock or 0)
        threshold = it.low_stock_threshold if it.low_stock_threshold is not None else DEFAULT_LOW_STOCK
        if stock <= threshold:
            low_stock_count += 1

    # --- Sales today ---
    sales_today = Sale.objects.filter(created_at__date=today)
    sales_today_count = sales_today.count()
    sales_today_total = sales_today.aggregate(s=Sum("total"))["s"] or Decimal("0.00")

    # --- Outstanding debt (all-time) ---
    # Total owed = total sales - total payments (simple + accurate)
    total_sales = Sale.objects.aggregate(s=Sum("total"))["s"] or Decimal("0.00")
    total_paid = Payment.objects.aggregate(s=Sum("amount"))["s"] or Decimal("0.00")
    outstanding_debt = total_sales - total_paid

    # --- Best sellers (last 30 days) ---
    start_30 = now - timedelta(days=30)
    best_sellers = (
        SaleItem.objects
        .filter(sale__created_at__gte=start_30)
        .values("item__id", "item__name", "item__sku")
        .annotate(
            qty=Sum("quantity"),
            revenue=Sum("line_total"),
        )
        .order_by("-qty")[:10]
    )

    # --- Best customers (last 90 days) ---
    start_90 = now - timedelta(days=90)

    # spent by customer (ignore walk-ins)
    spent_rows = (
        Sale.objects.filter(created_at__gte=start_90, customer__isnull=False)
        .values("customer_id")
        .annotate(spent=Sum("total"))
    )
    spent_map = {r["customer_id"]: (r["spent"] or Decimal("0.00")) for r in spent_rows}

    # paid by customer (same window, based on payment time)
    paid_rows = (
        Payment.objects.filter(created_at__gte=start_90, sale__customer__isnull=False)
        .values("sale__customer_id")
        .annotate(paid=Sum("amount"))
    )
    paid_map = {r["sale__customer_id"]: (r["paid"] or Decimal("0.00")) for r in paid_rows}

    customer_ids = list(spent_map.keys())
    customers = Customer.objects.filter(id__in=customer_ids, is_active=True).only("id", "name")

    best_customers = []
    for c in customers:
        spent = spent_map.get(c.id, Decimal("0.00"))
        paid = paid_map.get(c.id, Decimal("0.00"))
        balance = spent - paid
        best_customers.append({
            "customer": c,
            "spent": spent,
            "paid": paid,
            "balance": balance,
        })

    best_customers.sort(key=lambda x: x["spent"], reverse=True)
    best_customers = best_customers[:10]

    return render(request, "core/dashboard.html", {
        "low_stock_count": low_stock_count,
        "sales_today_count": sales_today_count,
        "sales_today_total": sales_today_total,
        "outstanding_debt": outstanding_debt,
        "best_sellers": best_sellers,
        "best_customers": best_customers,
    })