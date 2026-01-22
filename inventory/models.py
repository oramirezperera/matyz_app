from django.db import models

# Create your models here.
from django.conf import settings
from django.db import models
from django.db.models import Sum
from django.utils import timezone


class Category(models.Model):
    name = models.CharField(max_length=80, unique=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Item(models.Model):
    name = models.CharField(max_length=160)
    sku = models.CharField(max_length=64, unique=True)
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="items", null=True, blank=True)

    # Pricing
    cost_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    sell_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    # Optional metadata
    brand = models.CharField(max_length=80, blank=True, default="")
    vendor = models.CharField(max_length=120, blank=True, default="")
    notes = models.TextField(blank=True, default="")

    # Low stock
    low_stock_threshold = models.PositiveIntegerField(null=True, blank=True)  # if null -> use global default
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["sku"]),
            models.Index(fields=["name"]),
            models.Index(fields=["is_active"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.sku})"

    @property
    def current_stock(self) -> int:
        """
        Stock is derived from movements. For v1, we calculate on the fly.
        Later we can cache this safely if needed.
        """
        agg = self.movements.aggregate(total=Sum("quantity_change"))
        return int(agg["total"] or 0)

    def threshold(self, default_threshold: int) -> int:
        return self.low_stock_threshold if self.low_stock_threshold is not None else default_threshold


class StockMovement(models.Model):
    class MovementType(models.TextChoices):
        RESTOCK = "RESTOCK", "Restock"
        SALE = "SALE", "Sale"
        ADJUSTMENT = "ADJUSTMENT", "Adjustment"
        RETURN = "RETURN", "Return"

    item = models.ForeignKey(Item, on_delete=models.PROTECT, related_name="movements")
    movement_type = models.CharField(max_length=20, choices=MovementType.choices)
    quantity_change = models.IntegerField(help_text="Positive adds stock, negative removes stock.")
    note = models.CharField(max_length=255, blank=True, default="")

    # Link to sale later (nullable so inventory app doesn’t depend on sales app yet)
    sale_id = models.IntegerField(null=True, blank=True)

    created_at = models.DateTimeField(default=timezone.now)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="stock_movements",
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["movement_type"]),
            models.Index(fields=["created_at"]),
            models.Index(fields=["sale_id"]),
        ]

    def __str__(self):
        return f"{self.movement_type} {self.quantity_change} for {self.item}"
