from django.shortcuts import render

# Create your views here.
def sales_list(request):
    return render(request, "sales/list.html")