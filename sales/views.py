from decimal import Decimal
from django.contrib import messages
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.http import HttpResponse

import json
from inventory.models import Item

from collections import defaultdict

from .forms import SaleForm, SaleItemFormSet, PaymentForm
from .models import Sale, SaleItem
from .services import (
    compute_sale_totals,
    apply_sale_stock_movements_on_create,
    apply_sale_stock_movements_on_edit,
    build_qty_by_item_from_formset,
    validate_no_negative_stock
)

# Create your views here.
def sales_list(request):
    q = request.GET.get("q", "").strip()
    status = request.GET.get("status", "").strip()

    sales = Sale.objects.select_related("customer").all()

    if status:
        sales = sales.filter(status=status)

    if q:
        sales = sales.filter(
            Q(customer__name__icontains=q) |
            Q(pk__icontains=q)
        )

    return render(request, "sales/list.html", {"sales": sales, "q": q, "status": status})


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


def sale_edit(request, pk: int):
    sale = get_object_or_404(Sale, pk=pk)

    # Capture old lines BEFORE any changes, so we can reverse stock
    old_lines = list(
        sale.items.values("item_id", "quantity")
    )

    form = SaleForm(request.POST or None, instance=sale)
    formset = SaleItemFormSet(request.POST or None, instance=sale)

    if request.method == "POST" and form.is_valid() and formset.is_valid():
        try:
            with transaction.atomic():

                sale = form.save()
                formset.save()

                # Build extra availability from old lines (because we are about to reverse them)
                old_qty_by_item = defaultdict(int)
                for ol in old_lines:
                    old_qty_by_item[ol["item_id"]] += int(ol["quantity"])
                
                # Validate against current stock + old quantities
                qty_by_item = build_qty_by_item_from_formset(formset)
                validate_no_negative_stock(qty_by_item, extra_available_by_item=old_qty_by_item)



                # recompute totals
                compute_sale_totals(sale)

                # reverse old stock and apply new stock
                apply_sale_stock_movements_on_edit(sale, old_lines)

            messages.success(request, f"Sale #{sale.pk} updated.")
            return redirect("sales:detail", pk=sale.pk)
        
        except ValueError as e:
            messages.error(request, str(e))
    
    price_map_json=json.dumps({
            str(i.id): str(i.sell_price)
            for i in Item.objects.all().only("id", "sell_price")
    })

    return render(request, "sales/sale_form.html", {
        "mode": "edit",
        "sale": sale,
        "form": form,
        "formset": formset,
        "price_map_json": price_map_json,
    })


def sale_detail(request, pk: int):
    sale = get_object_or_404(Sale.objects.select_related("customer"), pk=pk)
    items = sale.items.select_related("item").all()
    payments = sale.payments.all()
    payment_form = PaymentForm()

    return render(request, "sales/detail.html", {
        "sale": sale,
        "items": items,
        "payments": payments,
        "payment_form": payment_form,
    })


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