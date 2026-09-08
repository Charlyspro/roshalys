from pathlib import Path

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.core.validators import RegexValidator

from store.models import ALLOWED_IMAGE_EXTENSIONS, DeliveryZone, Order, Product, ProductImage


def validate_upload_image(file):
    if not file:
        return
    ext = Path(file.name).suffix.lower()
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise forms.ValidationError("Formato no permitido. Usa JPG, JPEG, PNG o WEBP.")
    if hasattr(file, "size") and file.size > 2 * 1024 * 1024:
        raise forms.ValidationError("La imagen es demasiado grande. Máximo 2 MB.")


class ProductAdminForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = [
            "category",
            "name",
            "slug",
            "description",
            "price",
            "stock",
            "image",
            "is_active",
            "is_featured",
        ]

    def clean_image(self):
        image = self.cleaned_data.get("image")
        validate_upload_image(image)
        return image


class ProductImageAdminForm(forms.ModelForm):
    class Meta:
        model = ProductImage
        fields = ["product", "image", "alt_text", "is_primary"]

    def clean_image(self):
        image = self.cleaned_data.get("image")
        validate_upload_image(image)
        return image


class CustomerRegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ["username", "email", "password1", "password2"]

    def clean_email(self):
        email = self.cleaned_data.get("email")
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("Ya existe una cuenta con este correo.")
        return email


class CustomerProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["first_name", "last_name", "email"]
        widgets = {
            "first_name": forms.TextInput(attrs={"placeholder": "Nombre"}),
            "last_name": forms.TextInput(attrs={"placeholder": "Apellido"}),
            "email": forms.EmailInput(attrs={"placeholder": "Correo"}),
        }

    def clean_email(self):
        email = self.cleaned_data["email"]
        if User.objects.filter(email=email).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Ya existe una cuenta con este correo.")
        return email


class DeliveryForm(forms.Form):
    DELIVERY_CHOICES = [
        ("pickup", "Recoger en el local"),
        ("delivery", "Envío a domicilio"),
    ]

    delivery_option = forms.ChoiceField(
        choices=DELIVERY_CHOICES,
        widget=forms.RadioSelect,
        label="¿Cómo querés recibir tu pedido?",
    )
    delivery_zone = forms.ModelChoiceField(
        queryset=DeliveryZone.objects.filter(is_active=True),
        required=False,
        label="Zona de entrega",
        empty_label="Selecciona tu zona",
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    customer_name = forms.CharField(max_length=150, label="Nombre")
    customer_phone = forms.CharField(
        max_length=50,
        required=False,
        label="Teléfono",
        validators=[RegexValidator(r"^[0-9+() .-]{6,50}$", "Ingresá un teléfono válido.")],
    )
    customer_email = forms.EmailField(required=False, label="Correo electrónico")
    checkout_token = forms.UUIDField(widget=forms.HiddenInput)
    delivery_address = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "Calle, número, piso, depto, barrio, ciudad"}),
        label="Dirección de entrega",
    )
    delivery_notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 2, "placeholder": "Instrucciones adicionales (opcional)"}),
        label="Indicaciones",
    )
    accept_delivery_late = forms.BooleanField(
        required=False,
        label="Entiendo y acepto que el envío se realizará al día siguiente, en el horario de domicilio.",
    )

    def clean(self):
        cleaned_data = super().clean()
        if not cleaned_data.get("customer_name", "").strip():
            self.add_error("customer_name", "Ingresá tu nombre.")
        if cleaned_data.get("delivery_option") == "delivery":
            if not cleaned_data.get("delivery_address"):
                raise forms.ValidationError("Si elegís envío a domicilio, ingresá tu dirección.")
            if not cleaned_data.get("delivery_zone"):
                raise forms.ValidationError("Si elegís envío a domicilio, selecciona tu zona.")
        return cleaned_data
