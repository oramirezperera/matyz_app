from django.urls import path
from . import views

app_name = "sales"

urlpatterns = [
    path("", views.sales_list, name="list"),
    path("new/", views.sale_create, name="create"),
    path("<int:pk>/", views.sale_detail, name="detail"),
    path("<int:pk>/edit/", views.sale_edit, name="edit"),
    path("<int:pk>/payment/", views.payment_create, name="payment_create"),

    # HTMX: add a new line item row
    path("htmx/sale-item-row/", views.htmx_sale_item_row, name="htmx_sale_item_row"),
]