from django.shortcuts import render

# Create your views here.

def items_list(request):
    return render(request, "inventory/items.html")

def low_stock(request):
    return render(request, "inventory/low_stock.html")