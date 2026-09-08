from django.contrib import admin
from django.http import HttpResponse
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils.html import format_html

from store.forms import ProductAdminForm, ProductImageAdminForm
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User

from store.models import Category, DailyStats, DeliveryZone, Feedback, Order, OrderItem, Product, ProductImage, StoreConfig, StoreHours
from store.config import SITE_NAME
from store.whatsapp import wa_link_for

admin.site.unregister(User)
admin.site.register(User, UserAdmin)


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    form = ProductImageAdminForm
    extra = 1
    fields = ("image", "alt_text", "is_primary")


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    form = ProductAdminForm
    list_display = ("name", "category", "price", "stock", "is_active", "is_featured", "wa_publish")
    list_filter = ("is_active", "is_featured", "category")
    search_fields = ("name", "description")
    prepopulated_fields = {"slug": ("name",)}
    inlines = [ProductImageInline]
    fieldsets = (
        (None, {"fields": ("category", "name", "slug", "description")}),
        ("Precio y stock", {"fields": ("price", "stock", "is_active", "is_featured")}),
        ("Imagen principal", {"fields": ("image",)}),
    )

    @admin.display(description="WhatsApp")
    def wa_publish(self, obj):
        url = reverse("store:admin_publish_product", args=[obj.pk])
        return format_html(
            '<a class="button" href="{}" target="_blank" rel="noreferrer">Publicar</a>', url
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


@admin.register(StoreConfig)
class StoreConfigAdmin(admin.ModelAdmin):
    fields = ("force_open", "delivery_from", "delivery_to")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_queryset(self, request):
        return super().get_queryset(request).filter(pk=1)


@admin.register(StoreHours)
class StoreHoursAdmin(admin.ModelAdmin):
    list_display = ("get_day_label", "open_time", "close_time", "is_closed")
    list_editable = ("open_time", "close_time", "is_closed")
    list_display_links = None
    ordering = ("day",)
    list_per_page = 10

    @admin.display(description="Día")
    def get_day_label(self, obj):
        return obj.get_day_display()


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ("product", "quantity", "price")


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "customer_name", "customer_email", "status", "delivery_option", "delivery_zone", "delivery_cost", "total", "created_at")
    list_filter = ("status", "delivery_option", "delivery_zone", "created_at")
    search_fields = ("customer_name", "customer_email")
    ordering = ("-created_at",)
    autocomplete_fields = ("user",)
    date_hierarchy = "created_at"
    readonly_fields = ("total", "delivery_cost", "created_at", "updated_at", "checkout_token")
    inlines = [OrderItemInline]
    actions = ["marcar_confirmado", "marcar_preparando", "marcar_listo", "marcar_enviado", "marcar_entregado", "marcar_cancelado"]
    fieldsets = (
        ("Información del cliente", {"fields": ("customer_name", "customer_email", "user")}),
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
                "wa_link": wa_link_for(order, status_key, SITE_NAME),
            })
        return TemplateResponse(request, "admin/order_status_action.html", {
            "title": f"Avisar por WhatsApp: {label}",
            "status_label": label,
            "status_key": status_key,
            "links": links,
            "opts": self.model._meta,
        })


@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ("get_rating_display", "created_at")
    ordering = ("-created_at",)
    actions = None

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(DailyStats)
class DailyStatsAdmin(admin.ModelAdmin):
    list_display = ("date", "views", "visitors")
    list_display_links = ("date",)
    ordering = ("-date",)
    actions = None

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False
