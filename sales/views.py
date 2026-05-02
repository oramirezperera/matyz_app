from decimal import Decimal
from django.contrib import messages
from django.db import transaction
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.http import HttpResponse
from datetime import datetime, time
from django.utils.timezone import make_aware
from customers.models import Customer
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from core.permissions import is_manager


import json
from inventory.models import Item

from collections import defaultdict

from .forms import SaleForm, SaleItemFormSet, PaymentForm
from .models import Sale, SaleItem, Payment, SaleAuditLog
from .services import (
    compute_sale_totals,
    apply_sale_stock_movements_on_create,
    apply_sale_stock_movements_on_edit,
    build_qty_by_item_from_formset,
    validate_no_negative_stock
)

# Create your views here.
@login_required
def sales_list(request):
   
    q = request.GET.get("q", "").strip()
    status = request.GET.get("status", "").strip()
    customer_id = request.GET.get("customer", "").strip()
    date_from = request.GET.get("from", "").strip()
    date_to = request.GET.get("to", "").strip()
    with_balance = request.GET.get("with_balance", "").strip()  # "1" means only unpaid/partial effectively

    sales = Sale.objects.select_related("customer").all()

    if status:
        sales = sales.filter(status=status)

    if customer_id:
        sales = sales.filter(customer_id=customer_id)

    if q:
        # If q is numeric, allow searching by sale id
        if q.isdigit():
            sales = sales.filter(Q(pk=int(q)) | Q(customer__name__icontains=q))
        else:
            sales = sales.filter(customer__name__icontains=q)

    # Date range (inclusive)
    # Expect YYYY-MM-DD from input type="date"
    try:
        if date_from:
            dt = make_aware(datetime.combine(datetime.strptime(date_from, "%Y-%m-%d").date(), time.min))
            sales = sales.filter(created_at__gte=dt)
        if date_to:
            dt = make_aware(datetime.combine(datetime.strptime(date_to, "%Y-%m-%d").date(), time.max))
            sales = sales.filter(created_at__lte=dt)
    except ValueError:
        # If user types invalid date, ignore filters rather than crash
        pass

    # Optional “with balance” filter: total - paid > 0
    # We can’t do sale.balance directly in SQL because it’s a property,
    # so we filter by statuses that imply balance, and we can also compute for display.
    if with_balance == "1":
        sales = sales.exclude(status=Sale.Status.PAID)

    customers = Customer.objects.filter(is_active=True).order_by("name")

    return render(request, "sales/list.html", {
        "sales": sales,
        "customers": customers,
        "q": q,
        "status": status,
        "customer_id": customer_id,
        "date_from": date_from,
        "date_to": date_to,
        "with_balance": with_balance,
    })


@login_required
def sale_create(request):
    sale = Sale()
    form = SaleForm(request.POST or None, instance=sale)
    formset = SaleItemFormSet(request.POST or None, instance=sale)

    if request.method == "POST" and form.is_valid() and formset.is_valid():
        try:
            with transaction.atomic():
                sale = form.save()
                formset.instance = sale
                formset.save()
                
                # validate stock before applying movements
                qty_by_item = build_qty_by_item_from_formset(formset)
                validate_no_negative_stock(qty_by_item)

                compute_sale_totals(sale)
                apply_sale_stock_movements_on_create(sale)

            messages.success(request, f"Sale #{sale.pk} created.")
            return redirect("sales:detail", pk=sale.pk)

        except ValueError as e:
            messages.error(request, str(e))

    price_map_json=json.dumps({
            str(i.id): str(i.sell_price)
            for i in Item.objects.all().only("id", "sell_price")
    })

    return render(request, "sales/sale_form.html", {
        "mode": "create",
        "form": form,
        "formset": formset,
        "price_map_json": price_map_json,        
    })


@login_required
def sale_edit(request, pk: int):

    sale = get_object_or_404(Sale, pk=pk)
    has_payments = sale.payments.exists()

    # If it has payments, only Managers/Admins can edit
    if has_payments and not is_manager(request.user):
        raise PermissionDenied("Only Managers can edit sales that already have payments.")

    # Capture old lines + old totals BEFORE changes
    old_lines = list(sale.items.values("item_id", "quantity"))
    old_total = sale.total

    form = SaleForm(request.POST or None, instance=sale)
    formset = SaleItemFormSet(request.POST or None, instance=sale)

    if request.method == "POST" and form.is_valid() and formset.is_valid():
        try:
            with transaction.atomic():
                sale = form.save()
                formset.save()

                # Validate stock (your existing no-negative-stock logic)
                old_qty_by_item = defaultdict(int)
                for ol in old_lines:
                    old_qty_by_item[ol["item_id"]] += int(ol["quantity"])

                qty_by_item = build_qty_by_item_from_formset(formset)
                validate_no_negative_stock(qty_by_item, extra_available_by_item=old_qty_by_item)

                # Totals + stock movements
                compute_sale_totals(sale)
                apply_sale_stock_movements_on_edit(sale, old_lines)

                # ✅ Audit log if sale had payments OR if manager edited (we log only when payments exist)
                if has_payments:
                    SaleAuditLog.objects.create(
                        sale=sale,
                        actor=request.user,
                        had_payments=True,
                        old_total=old_total,
                        new_total=sale.total,
                        note=(
                            "Sale edited after payments existed.\n"
                            f"Old total: {old_total}\n"
                            f"New total: {sale.total}"
                        ),
                    )

            messages.success(request, f"Sale #{sale.pk} updated.")
            return redirect("sales:detail", pk=sale.pk)

        except ValueError as e:
            messages.error(request, str(e))

    # ✅ show warning banner on GET if payments exist
    if has_payments:
        messages.warning(
            request,
            "Warning: this sale already has payments. Editing it changes accounting history. "
            "An audit record will be created."
        )

    return render(request, "sales/sale_form.html", {
        "mode": "edit",
        "sale": sale,
        "form": form,
        "formset": formset,
        "has_payments": has_payments,
    })


@login_required
def sale_detail(request, pk: int):
    sale = get_object_or_404(Sale.objects.select_related("customer"), pk=pk)
    items = sale.items.select_related("item").all()
    payments = sale.payments.all()
    payment_form = PaymentForm()
    audit_logs = sale.audit_logs.select_related("actor").all()[:20]

    return render(request, "sales/detail.html", {
        "sale": sale,
        "items": items,
        "payments": payments,
        "payment_form": payment_form,
        "audit_logs": audit_logs,
    })


@login_required
def payment_create(request, pk: int):
    sale = get_object_or_404(Sale, pk=pk)
    form = PaymentForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        p = form.save(commit=False)
        p.sale = sale
        p.save()
        sale.refresh_status(save=True)
        messages.success(request, "Payment added.")
    else:
        messages.error(request, "Payment could not be added.")

    return redirect("sales:detail", pk=sale.pk)


@login_required
def htmx_sale_item_row(request):
    """
    Returns an extra empty form row for the SaleItem formset.
    Used when clicking “+ Add item” without reloading.
    """
    # create an unbound formset with 1 extra row, and render only the last row
    dummy_sale = Sale()
    formset = SaleItemFormSet(instance=dummy_sale)
    # last form is the extra one
    html = render_to_string("sales/partials/sale_item_row.html", {"f": formset.forms[-1]})
    return HttpResponse(html)


@login_required
def debts_view(request):
    # 1) Sales with debt (UNPAID or PARTIAL)
    debt_sales = (
        Sale.objects.select_related("customer")
        .exclude(status=Sale.Status.PAID)
        .order_by("-created_at")
    )

    # 2) Debt totals by customer (spent - paid)
    # We compute in two queries to avoid join-multiplication.
    spent_by_customer = dict(
        Sale.objects.exclude(customer__isnull=True)
        .values_list("customer_id")
        .annotate(spent=Sum("total"))
        .values_list("customer_id", "spent")
    )

    paid_by_customer = dict(
        Payment.objects.exclude(sale__customer__isnull=True)
        .values_list("sale__customer_id")
        .annotate(paid=Sum("amount"))
        .values_list("sale__customer_id", "paid")
    )

    # Build customer debt rows
    customer_ids = set(spent_by_customer.keys()) | set(paid_by_customer.keys())
    customers = Customer.objects.filter(id__in=customer_ids, is_active=True)

    rows = []
    for c in customers:
        spent = spent_by_customer.get(c.id, Decimal("0.00")) or Decimal("0.00")
        paid = paid_by_customer.get(c.id, Decimal("0.00")) or Decimal("0.00")
        balance = spent - paid
        if balance > 0:
            rows.append({
                "customer": c,
                "spent": spent,
                "paid": paid,
                "balance": balance,
            })

    rows.sort(key=lambda r: r["balance"], reverse=True)

    total_outstanding = sum((r["balance"] for r in rows), Decimal("0.00"))

    return render(request, "sales/debts.html", {
        "customer_rows": rows,
        "debt_sales": debt_sales,
        "total_outstanding": total_outstanding,
    })