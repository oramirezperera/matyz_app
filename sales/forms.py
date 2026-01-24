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