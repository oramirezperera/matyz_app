from decimal import Decimal
from django.db import transaction
from django.db.models import Sum

from inventory.models import StockMovement, Item
from .models import Sale, SaleItem
from collections import defaultdict


def compute_sale_totals(sale: Sale):
    subtotal = Decimal("0.00")
    for si in sale.items.all():
        si.line_total = (si.unit_price * si.quantity)
        si.save(update_fields=["line_total"])
        subtotal += si.line_total
    sale.subtotal = subtotal
    sale.total = subtotal  # later: discounts/tax/shipping can be added
    sale.save(update_fields=["subtotal", "total", "updated_at"])
    sale.refresh_status(save=True)

@transaction.atomic
def apply_sale_stock_movements_on_create(sale: Sale):
    # Create SALE movements: negative quantities
    for si in sale.items.select_related("item").all():
        StockMovement.objects.create(
            item=si.item,
            movement_type=StockMovement.MovementType.SALE,
            quantity_change=-int(si.quantity),
            note=f"Sale #{sale.pk}",
            sale_id=sale.pk,
        )


@transaction.atomic
def apply_sale_stock_movements_on_edit(sale: Sale, old_lines: list[dict]):
    """
    old_lines: list of dicts: {"item_id": int, "quantity": int}
    We reverse old items (positive adjustment), then apply new SALE movements.
    This preserves audit history without deleting anything.
    """
    # Reverse old
    for ol in old_lines:
        StockMovement.objects.create(
            item_id=ol["item_id"],
            movement_type=StockMovement.MovementType.ADJUSTMENT,
            quantity_change=int(ol["quantity"]),  # add back
            note=f"Reversal for edited Sale #{sale.pk}",
            sale_id=sale.pk,
        )

    # Apply new
    apply_sale_stock_movements_on_create(sale)

def build_qty_by_item_from_formset(formset):
    """
    Returns {item_id: total_qty} for all non-deleted rows.
    """
    qty_by_item = defaultdict(int)
    for f in formset.forms:
        if not hasattr(f, "cleaned_data"):
            continue
        cd = f.cleaned_data
        if not cd or cd.get("DELETE"):
            continue
        item = cd.get("item")
        qty = cd.get("quantity") or 0
        if item and qty:
            qty_by_item[item.id] += int(qty)
    return qty_by_item


def validate_no_negative_stock(qty_by_item, extra_available_by_item=None):
    """
    qty_by_item: {item_id: qty_to_sell}
    extra_available_by_item: {item_id: qty_to_add_back} used during edit (old sale quantities)
    Raises ValueError with human-readable message if any item would go negative.
    """
    extra_available_by_item = extra_available_by_item or {}
    item_ids = list(qty_by_item.keys())

    # Fetch current stocks in one go
    items = (
        Item.objects.filter(id__in=item_ids)
        .annotate(stock=Sum("movements__quantity_change"))
        .only("id", "name", "sku")
    )

    info = {}
    for it in items:
        info[it.id] = (it.name, it.sku, int(it.stock or 0))

    errors = []
    for item_id, qty_needed in qty_by_item.items():
        name, sku, current = info.get(item_id, ("(Unknown item)", "(no sku)", 0))
        extra = int(extra_available_by_item.get(item_id, 0))
        available = current + extra

        if available - qty_needed < 0:
            errors.append((sku, name, available, qty_needed))

    if errors:
        lines = [
            f"{sku} ({name}) — available {available}, needed {needed}"
            for sku, name, available, needed in errors
        ]
        raise ValueError("Insufficient stock for:\n- " + "\n- ".join(lines))