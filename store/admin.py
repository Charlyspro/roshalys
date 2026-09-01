from django.contrib import admin
from django.http import HttpResponse
from django.template.response import TemplateResponse

from store.forms import ProductAdminForm, ProductImageAdminForm
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User

from store.models import Category, DeliveryZone, Order, OrderItem, Product, ProductDeliveryConfig, ProductImage
from store.config import SITE_NAME
from store.whatsapp import wa_link_for

admin.site.unregister(User)
admin.site.register(User, UserAdmin)


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    form = ProductImageAdminForm
    extra = 1
    fields = ("image", "alt_text", "is_primary")


class ProductDeliveryConfigInline(admin.StackedInline):
    model = ProductDeliveryConfig
    extra = 0
    fields = ("allow_delivery", "min_quantity_for_delivery")


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    form = ProductAdminForm
    list_display = ("name", "category", "price", "stock", "is_active", "is_featured")
    list_filter = ("is_active", "is_featured", "category")
    search_fields = ("name", "description")
    prepopulated_fields = {"slug": ("name",)}
    inlines = [ProductImageInline, ProductDeliveryConfigInline]
    fieldsets = (
        (None, {"fields": ("category", "name", "slug", "description")}),
        ("Precio y stock", {"fields": ("price", "stock", "is_active", "is_featured")}),
        ("Imagen principal", {"fields": ("image",)}),
    )


@admin.register(ProductImage)
class ProductImageAdmin(admin.ModelAdmin):
    form = ProductImageAdminForm
    list_display = ("product", "is_primary", "image")
    list_filter = ("is_primary",)
    search_fields = ("product__name", "alt_text")


@admin.register(DeliveryZone)
class DeliveryZoneAdmin(admin.ModelAdmin):
    list_display = ("name", "cost", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "description")
    fieldsets = (
        (None, {"fields": ("name", "description")}),
        ("Costo", {"fields": ("cost",)}),
        ("Estado", {"fields": ("is_active",)}),
    )


@admin.register(ProductDeliveryConfig)
class ProductDeliveryConfigAdmin(admin.ModelAdmin):
    list_display = ("product", "allow_delivery", "min_quantity_for_delivery")
    list_filter = ("allow_delivery",)
    search_fields = ("product__name",)
    fieldsets = (
        (None, {"fields": ("product",)}),
        ("Configuración de domicilio", {"fields": ("allow_delivery", "min_quantity_for_delivery")}),
    )


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ("product", "quantity", "price")


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "customer_name", "customer_phone", "customer_email", "status", "delivery_option", "delivery_zone", "delivery_cost", "total", "created_at")
    list_filter = ("status", "delivery_option", "delivery_zone", "created_at")
    search_fields = ("customer_name", "customer_phone", "customer_email")
    ordering = ("-created_at",)
    autocomplete_fields = ("user",)
    date_hierarchy = "created_at"
    readonly_fields = ("total", "delivery_cost", "created_at", "updated_at", "checkout_token")
    inlines = [OrderItemInline]
    actions = ["marcar_confirmado", "marcar_preparando", "marcar_listo", "marcar_enviado", "marcar_entregado", "marcar_cancelado"]
    fieldsets = (
        ("Información del cliente", {"fields": ("customer_name", "customer_phone", "customer_email", "user")}),
        ("Estado del pedido", {"fields": ("status", "checkout_token")}),
        ("Envío", {"fields": ("delivery_option", "delivery_zone", "delivery_cost", "delivery_address", "delivery_notes")}),
        ("Resumen", {"fields": ("total", "notes")}),
        ("Auditoría", {"fields": ("created_at", "updated_at")}),
    )

    @admin.action(description="Marcar como Confirmado")
    def marcar_confirmado(self, request, queryset):
        return self._apply_status_action(request, queryset, "confirmed", "Confirmado")

    @admin.action(description="Marcar como En preparación")
    def marcar_preparando(self, request, queryset):
        return self._apply_status_action(request, queryset, "preparing", "En preparación")

    @admin.action(description="Marcar como Listo")
    def marcar_listo(self, request, queryset):
        return self._apply_status_action(request, queryset, "ready", "Listo")

    @admin.action(description="Marcar como Enviado")
    def marcar_enviado(self, request, queryset):
        return self._apply_status_action(request, queryset, "shipped", "Enviado")

    @admin.action(description="Marcar como Entregado")
    def marcar_entregado(self, request, queryset):
        return self._apply_status_action(request, queryset, "delivered", "Entregado")

    @admin.action(description="Marcar como Cancelado")
    def marcar_cancelado(self, request, queryset):
        return self._apply_status_action(request, queryset, "cancelled", "Cancelado")

    def _apply_status_action(self, request, queryset, status_key, label):
        changed = queryset.exclude(status=status_key).update(status=status_key)
        self.message_user(request, f"{changed} pedido(s) marcado(s) como {label}.")

        orders = list(queryset.order_by("id"))
        links = []
        for order in orders:
            links.append({
                "order": order,
                "customer_phone": order.customer_phone,
                "wa_link": wa_link_for(order, status_key, SITE_NAME),
            })
        return TemplateResponse(request, "admin/order_status_action.html", {
            "title": f"Avisar por WhatsApp: {label}",
            "status_label": label,
            "status_key": status_key,
            "links": links,
            "opts": self.model._meta,
        })
