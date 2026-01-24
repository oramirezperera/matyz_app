from decimal import Decimal
from django.db import transaction

from inventory.models import StockMovement
from .models import Sale, SaleItem

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