from django import forms
from .models import Customer

class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = ["name", "phone", "email", "instagram_handle", "notes"]
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 3}),
        }