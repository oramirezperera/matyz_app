from django.db import models
from django.db.models import Sum
from django.utils import timezone

# Create your models here.
class Sale(models.Model):
    class Status(models.TextChoices):
        PAID = "PAID", "Paid"
        PARTIAL = "PARTIAL", "Partial"
        UNPAID = "UNPAID", "Unpaid"

    customer = models.ForeignKey(
        "customers.Customer",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales",
    )
    notes = models.TextField(blank=True, default="")

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    # Stored totals for historical integrity (don’t recompute from current Item price)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    status = models.CharField(max_length=10, choices=Status.choices, default=Status.UNPAID)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["created_at"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"Sale #{self.pk}"

    @property
    def paid_amount(self):
        agg = self.payments.aggregate(total=Sum("amount"))
        return agg["total"] or 0

    @property
    def balance(self):
        return self.total - self.paid_amount

    def refresh_status(self, save=True):
        paid = self.paid_amount
        if paid >= self.total and self.total > 0:
            self.status = self.Status.PAID
        elif 0 < paid < self.total:
            self.status = self.Status.PARTIAL
        else:
            self.status = self.Status.UNPAID
        if save:
            self.save(update_fields=["status", "updated_at"])


class SaleItem(models.Model):
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name="items")
    item = models.ForeignKey("inventory.Item", on_delete=models.PROTECT, related_name="sale_items")

    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)  # snapshot at sale time
    line_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)  # stored snapshot

    class Meta:
        indexes = [
            models.Index(fields=["sale"]),
            models.Index(fields=["item"]),
        ]

    def __str__(self):
        return f"{self.quantity} x {self.item} (Sale #{self.sale_id})"


class Payment(models.Model):
    class Method(models.TextChoices):
        CASH = "CASH", "Cash"
        CARD = "CARD", "Card"
        TRANSFER = "TRANSFER", "Transfer"
        OTHER = "OTHER", "Other"

    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name="payments")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    method = models.CharField(max_length=20, choices=Method.choices, default=Method.CASH)
    note = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["sale", "created_at"])]

    def __str__(self):
        return f"{self.amount} for Sale #{self.sale_id}"