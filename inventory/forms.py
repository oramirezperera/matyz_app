from django import forms
from .models import Item, Category, StockMovement


class ItemForm(forms.ModelForm):
    class Meta:
        model = Item
        fields = [
            "name", "sku", "category",
            "cost_price", "sell_price",
            "brand", "vendor",
            "low_stock_threshold",
            "is_active",
            "notes",
        ]
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 3}),
        }


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ["name", "is_active"]


class StockMovementForm(forms.ModelForm):
    class Meta:
        model = StockMovement
        fields = ["movement_type", "quantity_change", "note"]

    def clean_quantity_change(self):
        q = self.cleaned_data["quantity_change"]
        if q == 0:
            raise forms.ValidationError("Quantity change cannot be 0.")
        return q