from django.shortcuts import render

# Create your views here.
def customers_list(request):
    return render(request, "customers/list.html")