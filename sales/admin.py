from django.contrib import admin
from .models import Sale, SaleItem, Payment

# Register your models here.
class SaleItemInline(admin.TabularInline):
    model = SaleItem
    extra = 0

class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 0

@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ("id", "customer", "total", "status", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("id", "customer__name")
    inlines = [SaleItemInline, PaymentInline]