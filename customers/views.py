from decimal import Decimal
from django.contrib import messages
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, redirect, render

from .forms import CustomerForm
from .models import Customer
from sales.models import Sale, Payment

# Create your views here.
def customers_list(request):
    q = request.GET.get("q", "").strip()

    customers = Customer.objects.all()

    if q:
        customers = customers.filter(
            Q(name__icontains=q) |
            Q(phone__icontains=q) |
            Q(email__icontains=q) |
            Q(instagram_handle__icontains=q)
        )

    customers = customers.order_by("name")

    return render(request, "customers/list.html", {
        "customers": customers,
        "q": q,
    })


def customer_create(request):
    form = CustomerForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        customer = form.save()
        messages.success(request, "Customer Created")
        return redirect("customers:detail", pk=customer.pk)
    return render(request, "customers/form.html", {"form": form, "mode":"create"})


def customer_edit(request, pk: int):
    customer = get_object_or_404(Customer, pk=pk)
    form = CustomerForm(request.POST or None, instance=customer)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Customer updated")
        return redirect("customers:detail", pk=customer.pk)
    return render(request, "customers/form.html", {"form": form, "mode":"edit", "customer":customer})


def customer_detail(request, pk: int):
    customer = get_object_or_404(Customer, pk=pk)

    sales = (
        Sale.objects.filter(customer=customer)
        .prefetch_related("payments")
        .order_by("-created_at")
    )

    total_spent = Sale.objects.filter(customer=customer).aggregate(s=Sum("total"))["s"] or Decimal("0.00")
    total_paid = Payment.objects.filter(sale__customer=customer).aggregate(s=Sum("amount"))["s"] or Decimal("0.00")
    outstanding = total_spent - total_paid

    return render(request, "customers/detail.html", {
        "customer": customer,
        "sales": sales,
        "total_spent": total_spent,
        "total_paid": total_paid,
        "outstanding": outstanding,
    })
