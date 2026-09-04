from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("categoria/<slug:slug>/", views.category_products, name="category_products"),
    path("producto/<slug:slug>/", views.product_detail, name="product_detail"),
    path("buscar/", views.search_products, name="search_products"),
    path("asistente/", views.ollama_chat, name="ollama_chat"),
    path("cart/", views.cart_view, name="cart"),
    path("cart/add/<int:product_id>/", views.add_to_cart, name="add_to_cart"),
    path("cart/update/<int:product_id>/", views.update_cart, name="update_cart"),
    path("cart/remove/<int:product_id>/", views.remove_from_cart, name="remove_from_cart"),
    path("cart/clear/", views.clear_cart, name="clear_cart"),
    path("checkout/whatsapp/", views.whatsapp_checkout, name="whatsapp_checkout"),
    path("cuenta/registrar/", views.register_view, name="register"),
    path("cuenta/login/", views.CustomerLoginView.as_view(), name="login"),
    path("cuenta/logout/", views.CustomerLogoutView.as_view(), name="logout"),
    path("cuenta/", views.profile_view, name="profile"),
    path("admin-dashboard/", views.admin_dashboard, name="admin_dashboard"),
    path("admin-productos/", views.admin_products, name="admin_products"),
    path("admin-productos/editar/<int:product_id>/", views.admin_edit_product, name="admin_edit_product"),
    path("admin-productos/eliminar/<int:product_id>/", views.admin_delete_product, name="admin_delete_product"),
    path("admin-productos/publicar/<int:product_id>/", views.admin_publish_product, name="admin_publish_product"),
]
