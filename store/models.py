import uuid
from pathlib import Path

import datetime

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.text import slugify

ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def validate_image_file(file):
    if file is None:
        return
    ext = Path(file.name).suffix.lower()
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValidationError("Formato no permitido. Usa JPG, JPEG, PNG o WEBP.")
    if hasattr(file, "size") and file.size > 2 * 1024 * 1024:
        raise ValidationError("La imagen es demasiado grande. Máximo 2 MB.")


def product_image_upload_path(instance, filename):
    extension = Path(filename).suffix.lower()
    safe_name = slugify(instance.product.name or "producto")
    return f"products/{safe_name}/{uuid.uuid4().hex}{extension}"


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Categoría"
        verbose_name_plural = "Categorías"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Product(models.Model):
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="products")
    name = models.CharField(max_length=180)
    slug = models.SlugField(max_length=220, unique=True)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stock = models.PositiveIntegerField(default=0)
    image = models.ImageField(upload_to="products/", blank=True, null=True)
    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_featured", "name"]
        verbose_name = "Producto"
        verbose_name_plural = "Productos"

    def clean(self):
        if self.image:
            validate_image_file(self.image)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    @property
    def available(self):
        return self.stock > 0

    def get_main_image(self):
        if self.image:
            return self.image.url
        return "/static/images/placeholder-product.svg"


class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="gallery")
    image = models.ImageField(upload_to=product_image_upload_path)
    alt_text = models.CharField(max_length=150, blank=True)
    is_primary = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["is_primary", "created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["product"],
                condition=models.Q(is_primary=True),
                name="one_primary_image_per_product",
            ),
        ]
        verbose_name = "Imagen del producto"
        verbose_name_plural = "Imágenes del producto"

    def clean(self):
        validate_image_file(self.image)

    def __str__(self):
        return f"{self.product.name} - {self.image.name}"


class Order(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pendiente"),
        ("confirmed", "Confirmado"),
        ("preparing", "Preparando"),
        ("ready", "Listo"),
        ("shipped", "Enviado"),
        ("delivered", "Entregado"),
        ("cancelled", "Cancelado"),
    ]
    DELIVERY_CHOICES = [
        ("pickup", "Retiro en local"),
        ("delivery", "Envío a domicilio"),
    ]

    customer_name = models.CharField(max_length=150)
    customer_phone = models.CharField(max_length=50, blank=True)
    customer_email = models.EmailField(blank=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="orders")
    checkout_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    delivery_option = models.CharField(max_length=20, choices=DELIVERY_CHOICES, default="pickup")
    delivery_zone = models.ForeignKey(
        "DeliveryZone",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="orders"
    )
    delivery_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    delivery_address = models.TextField(blank=True)
    delivery_notes = models.TextField(blank=True)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Pedido"
        verbose_name_plural = "Pedidos"

    def __str__(self):
        return f"Pedido #{self.pk} - {self.customer_name}"


class DeliveryZone(models.Model):
    name = models.CharField(max_length=150, unique=True)
    description = models.TextField(blank=True)
    cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["cost"]
        verbose_name = "Zona de entrega"
        verbose_name_plural = "Zonas de entrega"

    def __str__(self):
        return f"{self.name} (${self.cost})"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    product_name = models.CharField(max_length=180, blank=True)
    quantity = models.PositiveIntegerField(default=1)
    price = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        verbose_name = "Item del pedido"
        verbose_name_plural = "Items del pedido"

    def save(self, *args, **kwargs):
        if not self.product_name and self.product_id:
            self.product_name = self.product.name
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.product_name or self.product.name} x {self.quantity}"

    @property
    def line_total(self):
        return self.price * self.quantity


class StoreConfig(models.Model):
    force_open = models.BooleanField(
        default=False,
        help_text="Marca para forzar la tienda abierta (emergencias, ferias, etc.)",
        verbose_name="Forzar tienda abierta",
    )
    delivery_from = models.TimeField(
        default=datetime.time(9, 0),
        help_text="Hora de inicio de los envíos a domicilio (fija cada día)",
        verbose_name="Domicilios: desde",
    )
    delivery_to = models.TimeField(
        default=datetime.time(18, 0),
        help_text="Hora de fin de los envíos a domicilio (fija cada día)",
        verbose_name="Domicilios: hasta",
    )

    class Meta:
        verbose_name = "Configuración de la tienda"
        verbose_name_plural = "Configuración de la tienda"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1, defaults={"force_open": False})
        return obj

    def __str__(self):
        return "Configuración de la tienda"


class StoreHours(models.Model):
    DAY_CHOICES = [
        (0, "Lunes"),
        (1, "Martes"),
        (2, "Miércoles"),
        (3, "Jueves"),
        (4, "Viernes"),
        (5, "Sábado"),
        (6, "Domingo"),
    ]

    day = models.PositiveSmallIntegerField(choices=DAY_CHOICES, unique=True, verbose_name="Día")
    open_time = models.TimeField(null=True, blank=True, verbose_name="Apertura")
    close_time = models.TimeField(null=True, blank=True, verbose_name="Cierre")
    is_closed = models.BooleanField(default=False, verbose_name="Cerrado")

    class Meta:
        ordering = ["day"]
        verbose_name = "Horario"
        verbose_name_plural = "Horarios"

    def __str__(self):
        if self.is_closed or self.open_time is None:
            return f"{self.get_day_display()} — Cerrado"
        return f"{self.get_day_display()} · {self.open_time:%H:%M}–{self.close_time:%H:%M}"


class DailyStats(models.Model):
    date = models.DateField(unique=True, verbose_name="Fecha")
    views = models.PositiveIntegerField(default=0, verbose_name="Visitas")
    visitors = models.PositiveIntegerField(default=0, verbose_name="Visitantes únicos")
    seen_keys = models.TextField(
        default="[]",
        help_text="Identificadores anónimos de visitantes ya contados en el día (JSON).",
        verbose_name="Visitantes contados",
    )

    class Meta:
        ordering = ["-date"]
        verbose_name = "Estadística de visitas"
        verbose_name_plural = "Estadísticas de visitas"

    def __str__(self):
        return self.date.isoformat()


class VisitorCountry(models.Model):
    ip_hash = models.CharField(max_length=64, unique=True, verbose_name="Visitante (hash)")
    country_code = models.CharField(max_length=2, blank=True, default="", verbose_name="País (ISO)")
    resolved_at = models.DateTimeField(auto_now=True, verbose_name="Detectado")

    class Meta:
        verbose_name = "País del visitante"
        verbose_name_plural = "Países de visitantes"

    def __str__(self):
        return self.country_code or "desconocido"


class Feedback(models.Model):
    RATING_CHOICES = [
        (1, "Me gusta"),
        (-1, "No me gusta"),
    ]
    rating = models.SmallIntegerField(choices=RATING_CHOICES, verbose_name="Voto")
    country_code = models.CharField(max_length=2, blank=True, default="", verbose_name="País (ISO)")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Fecha")

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Opinión del visitante"
        verbose_name_plural = "Opiniones de visitantes"

    def __str__(self):
        return self.get_rating_display()
