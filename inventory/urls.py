from django.urls import path
from . import views

app_name = "inventory"

urlpatterns = [
    path("items/", views.items_list, name="items"),
    path("items/new/", views.item_create, name="item_create"),
    path("items/<int:pk>/", views.item_detail, name="item_detail"),
    path("items/<int:pk>/edit/", views.item_edit, name="item_edit"),
    path("items/<int:pk>/movement/new/", views.movement_create, name="movement_create"),
    path("low-stock/", views.low_stock, name="low_stock"),
]
