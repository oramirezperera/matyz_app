from django.urls import path
from . import views

app_name = "inventory"

urlpatterns = [
    path("items/", views.items_list, name="items"),
    path("low-stock/", views.low_stock, name="low_stock"),
]
