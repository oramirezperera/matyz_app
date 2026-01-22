from django.contrib import admin
from .models import Category, Item, StockMovement

# Register your models here.
@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active")
    search_fields = ("name",)
    list_filter = ("is_active",)


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = ("name", "sku", "category", "sell_price", "is_active")
    search_fields = ("name", "sku", "brand", "vendor")
    list_filter = ("is_active", "category")
    ordering = ("name",)


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ("created_at", "item", "movement_type", "quantity_change", "created_by", "sale_id")
    search_fields = ("item__name", "item__sku", "note")
    list_filter = ("movement_type", "created_at")
    autocomplete_fields = ("item",)