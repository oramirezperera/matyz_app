from django.conf import settings
from django.contrib import messages
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from .forms import ItemForm, StockMovementForm
from .models import Item, StockMovement


DEFAULT_LOW_STOCK = 5  # Later: make this configurable in a Settings table


def items_list(request):
    q = request.GET.get("q", "").strip()
    only_active = request.GET.get("active", "1")  # default active only
    category_id = request.GET.get("category", "").strip()

    items = Item.objects.all().select_related("category")

    if only_active == "1":
        items = items.filter(is_active=True)

    if category_id:
        items = items.filter(category_id=category_id)

    if q:
        items = items.filter(
            Q(name__icontains=q) |
            Q(sku__icontains=q) |
            Q(brand__icontains=q) |
            Q(vendor__icontains=q)
        )

    # NOTE: current_stock is computed property (per-row query if used in template).
    # For list views, we compute via aggregation in one query:
    items = items.annotate(stock=Sum("movements__quantity_change")).order_by("name")

    return render(request, "inventory/items_list.html", {
        "items": items,
        "q": q,
        "only_active": only_active,
        "category_id": category_id,
    })


def item_create(request):
    form = ItemForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        item = form.save()
        messages.success(request, f"Item created: {item.name}")
        return redirect("inventory:item_detail", pk=item.pk)
    return render(request, "inventory/item_form.html", {"form": form, "mode": "create"})


def item_edit(request, pk: int):
    item = get_object_or_404(Item, pk=pk)
    form = ItemForm(request.POST or None, instance=item)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Item updated.")
        return redirect("inventory:item_detail", pk=item.pk)
    return render(request, "inventory/item_form.html", {"form": form, "mode": "edit", "item": item})


def item_detail(request, pk: int):
    item = get_object_or_404(Item.objects.select_related("category"), pk=pk)
    movements = item.movements.select_related("created_by").all()[:50]
    current_stock = item.current_stock
    threshold = item.threshold(DEFAULT_LOW_STOCK)

    return render(request, "inventory/item_detail.html", {
        "item": item,
        "movements": movements,
        "current_stock": current_stock,
        "threshold": threshold,
        "default_threshold": DEFAULT_LOW_STOCK,
    })


def movement_create(request, pk: int):
    item = get_object_or_404(Item, pk=pk)

    form = StockMovementForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        movement: StockMovement = form.save(commit=False)
        movement.item = item
        movement.created_by = request.user if request.user.is_authenticated else None
        movement.save()
        messages.success(request, "Stock movement recorded.")
        return redirect("inventory:item_detail", pk=item.pk)

    return render(request, "inventory/movement_form.html", {
        "item": item,
        "form": form,
    })


def low_stock(request):
    # We need aggregated stock in one query
    items = (
        Item.objects.filter(is_active=True)
        .select_related("category")
        .annotate(stock=Sum("movements__quantity_change"))
        .order_by("name")
    )

    # Filter in Python because threshold is per-item (may be null)
    low = []
    for it in items:
        stock = int(it.stock or 0)
        threshold = it.low_stock_threshold if it.low_stock_threshold is not None else DEFAULT_LOW_STOCK
        if stock <= threshold:
            low.append((it, stock, threshold))

    return render(request, "inventory/low_stock.html", {"rows": low, "default_threshold": DEFAULT_LOW_STOCK})