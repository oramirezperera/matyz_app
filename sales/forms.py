from django import forms
from django.forms import inlineformset_factory
from .models import Sale, SaleItem, Payment

class SaleForm(forms.ModelForm):
    class Meta:
        model = Sale
        fields = ["customer", "notes"]
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 3}),
        }


class SaleItemForm(forms.ModelForm):
    class Meta:
        model = SaleItem
        fields = ["item", "quantity", "unit_price"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Allow leaving it empty filling it from item.sell_price
        self.fields["unit_price"].required = False

    def clean(self):
        cleaned = super().clean()
        item = cleaned.get("item")
        unit_price = cleaned.get("unit_price")

        #If unit price omitted, use the item's sell_price
        if item and (unit_price is None or unit_price == ""):
            cleaned["unit_price"] = item.sell_price
        
        return cleaned

    def clean_quantity(self):
        q = self.cleaned_data["quantity"]
        if q <= 0:
            raise forms.ValidationError("Quantity must be greater than 0.")
        return q


SaleItemFormSet = inlineformset_factory(
    Sale,
    SaleItem,
    form=SaleItemForm,
    extra=1,
    can_delete=True,
)


class PaymentForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = ["amount", "method", "note"]

    def clean_amount(self):
        amt = self.cleaned_data["amount"]
        if amt <= 0:
            raise forms.ValidationError("Payment must be greater than 0.")
        return amt