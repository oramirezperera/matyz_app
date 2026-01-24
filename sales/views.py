from decimal import Decimal
from django.contrib import messages
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.http import HttpResponse

from .forms import SaleForm, SaleItemFormSet, PaymentForm
from .models import Sale, SaleItem
from .services import (
    compute_sale_totals,
    apply_sale_stock_movements_on_create,
    apply_sale_stock_movements_on_edit,
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
        sale = form.save()
        formset.instance = sale
        formset.save()

        # totals + stock movements
        compute_sale_totals(sale)
        apply_sale_stock_movements_on_create(sale)

        messages.success(request, f"Sale #{sale.pk} created.")
        return redirect("sales:detail", pk=sale.pk)

    return render(request, "sales/sale_form.html", {
        "mode": "create",
        "form": form,
        "formset": formset,
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
        sale = form.save()
        formset.save()

        # recompute totals
        compute_sale_totals(sale)

        # reverse old stock and apply new stock
        apply_sale_stock_movements_on_edit(sale, old_lines)

        messages.success(request, f"Sale #{sale.pk} updated.")
        return redirect("sales:detail", pk=sale.pk)

    return render(request, "sales/sale_form.html", {
        "mode": "edit",
        "sale": sale,
        "form": form,
        "formset": formset,
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