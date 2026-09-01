from decimal import Decimal
import logging
import uuid

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from store import config
from store.forms import CustomerProfileForm, CustomerRegistrationForm, DeliveryForm, ProductAdminForm
from store.models import Category, DeliveryZone, Order, OrderItem, Product, ProductDeliveryConfig

# Loggers
logger = logging.getLogger("store")
audit_logger = logging.getLogger("store.audit")


def _cart(request):
    return request.session.get("cart", {})


def _save_cart(request, cart):
    request.session["cart"] = cart
    request.session.modified = True


def _parse_quantity(value):
    try:
        quantity = int(value)
    except (TypeError, ValueError):
        return None
    return quantity if quantity > 0 else None


def _cart_items(request):
    cart = _cart(request)
    items = []
    total = Decimal("0.00")
    for product_id, qty in cart.items():
        product = Product.objects.filter(pk=product_id, is_active=True).first()
        if product is None:
            continue
        quantity = _parse_quantity(qty)
        if quantity is None:
            continue
        quantity = min(quantity, product.stock)
        if quantity <= 0:
            continue
        line_total = product.price * quantity
        total += line_total
        items.append({
            "product": product,
            "quantity": quantity,
            "line_total": line_total,
        })
    return items, total


def _calculate_delivery_cost(request, delivery_option, delivery_zone=None):
    """
    Calcula el costo de domicilio basado en la opción de entrega y la zona.
    Retorna (costo, mensaje_error o None)
    """
    if delivery_option != "delivery":
        return Decimal("0.00"), None
    
    if not delivery_zone:
        return None, "Zona de entrega no seleccionada"
    
    items, _ = _cart_items(request)
    total_quantity = sum(item["quantity"] for item in items)
    
    # Validar que todos los productos permitan domicilio
    for item in items:
        product = item["product"]
        delivery_config = ProductDeliveryConfig.objects.filter(product=product).first()
        
        if delivery_config is None:
            return None, f"El producto '{product.name}' no tiene configurada la entrega a domicilio"
        
        if not delivery_config.allow_delivery:
            return None, f"El producto '{product.name}' no permite envío a domicilio"
        
        if total_quantity < delivery_config.min_quantity_for_delivery:
            return None, f"Cantidad mínima para domicilio: {delivery_config.min_quantity_for_delivery} productos"
    
    # Retornar el costo de la zona
    return delivery_zone.cost, None


def _best_sellers(limit=3):
    totals = (
        OrderItem.objects.values("product_id")
        .annotate(total=Sum("quantity"))
        .order_by("-total")
    )
    total_by_id = {row["product_id"]: row["total"] for row in totals}
    products = list(Product.objects.filter(pk__in=total_by_id.keys(), is_active=True))
    products.sort(key=lambda p: total_by_id[p.pk], reverse=True)
    if len(products) < limit:
        used_ids = {p.pk for p in products}
        for product in Product.objects.filter(is_active=True).exclude(pk__in=used_ids).order_by("-is_featured", "name"):
            if len(products) >= limit:
                break
            products.append(product)
    return products[:limit]


def home(request):
    categories = Category.objects.filter(is_active=True)
    featured_products = Product.objects.filter(is_active=True, is_featured=True)[:8]
    best_sellers = _best_sellers(3)
    all_products = Product.objects.filter(is_active=True)
    paginator = Paginator(all_products, 12)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)
    return render(request, "store/home.html", {
        "categories": categories,
        "featured_products": featured_products,
        "best_sellers": best_sellers,
        "page_obj": page_obj,
        "page_title": "Inicio",
    })


def category_products(request, slug):
    category = get_object_or_404(Category, slug=slug, is_active=True)
    products = Product.objects.filter(category=category, is_active=True)
    paginator = Paginator(products, 12)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)
    return render(request, "store/category.html", {
        "category": category,
        "page_obj": page_obj,
        "categories": Category.objects.filter(is_active=True),
        "page_title": category.name,
    })


def search_products(request):
    query = request.GET.get("q", "").strip()
    products = Product.objects.filter(is_active=True)
    if query:
        products = products.filter(
            Q(name__icontains=query)
            | Q(description__icontains=query)
            | Q(category__name__icontains=query)
        )
    paginator = Paginator(products, 12)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)
    return render(request, "store/search.html", {
        "page_obj": page_obj,
        "query": query,
        "categories": Category.objects.filter(is_active=True),
        "page_title": "Buscar",
    })


def product_detail(request, slug):
    product = get_object_or_404(Product, slug=slug, is_active=True)
    gallery = product.gallery.all()
    related = Product.objects.filter(category=product.category, is_active=True).exclude(pk=product.pk)[:4]
    return render(request, "store/product_detail.html", {
        "product": product,
        "gallery": gallery,
        "related": related,
        "page_title": product.name,
    })


def add_to_cart(request, product_id):
    if request.method == "POST":
        product = get_object_or_404(Product, pk=product_id, is_active=True)
        quantity = _parse_quantity(request.POST.get("quantity", 1))
        if quantity is None:
            messages.error(request, "La cantidad debe ser un número entero positivo.")
            return redirect(request.META.get("HTTP_REFERER", reverse("store:home")))
        if product.stock <= 0:
            messages.warning(request, "Este producto no tiene stock disponible.")
            return redirect(request.META.get("HTTP_REFERER", reverse("store:home")))
        cart = _cart(request)
        current = cart.get(str(product.id), 0)
        new_quantity = current + quantity
        if new_quantity > product.stock:
            new_quantity = product.stock
        cart[str(product.id)] = new_quantity
        _save_cart(request, cart)
        messages.success(request, f"{product.name} agregado al carrito.")
    return redirect(request.META.get("HTTP_REFERER", reverse("store:home")))


def update_cart(request, product_id):
    if request.method == "POST":
        quantity = _parse_quantity(request.POST.get("quantity"))
        product = get_object_or_404(Product, pk=product_id, is_active=True)
        cart = _cart(request)
        if quantity is None:
            cart.pop(str(product.id), None)
            messages.error(request, "La cantidad debe ser un número entero positivo.")
        else:
            if product.stock <= 0:
                cart.pop(str(product.id), None)
                messages.warning(request, "El producto ya no tiene stock disponible.")
            else:
                cart[str(product.id)] = min(quantity, product.stock)
                if quantity > product.stock:
                    messages.warning(request, "La cantidad se ajustó al stock disponible.")
        _save_cart(request, cart)
    return redirect("store:cart")


def remove_from_cart(request, product_id):
    if request.method == "POST":
        cart = _cart(request)
        cart.pop(str(product_id), None)
        _save_cart(request, cart)
        messages.info(request, "Producto eliminado del carrito.")
    return redirect("store:cart")


def clear_cart(request):
    if request.method == "POST":
        _save_cart(request, {})
        messages.info(request, "Carrito vaciado.")
    return redirect("store:cart")


def cart_view(request):
    items, total = _cart_items(request)
    return render(request, "store/cart.html", {
        "items": items,
        "total": total,
        "categories": Category.objects.filter(is_active=True),
        "page_title": "Carrito",
    })


def whatsapp_checkout(request):
    items, total = _cart_items(request)
    if not items:
        messages.warning(request, "Tu carrito está vacío.")
        return redirect("store:cart")

    if request.method == "POST":
        form = DeliveryForm(request.POST)
        if form.is_valid():
            checkout_token = form.cleaned_data["checkout_token"]
            delivery_option = form.cleaned_data["delivery_option"]
            delivery_zone = form.cleaned_data.get("delivery_zone")
            
            # Calcular costo de domicilio
            delivery_cost, delivery_error = _calculate_delivery_cost(request, delivery_option, delivery_zone)
            if delivery_error:
                messages.error(request, delivery_error)
            else:
                try:
                    with transaction.atomic():
                        existing_order = Order.objects.filter(checkout_token=checkout_token).first()
                        if existing_order:
                            order = existing_order
                        else:
                            cart = _cart(request)
                            product_ids = [int(product_id) for product_id in cart if str(product_id).isdigit()]
                            locked_products = Product.objects.select_for_update().filter(
                                pk__in=product_ids, is_active=True
                            )
                            products_by_id = {str(product.pk): product for product in locked_products}
                            order_lines = []
                            order_total = Decimal("0.00")
                            for product_id, raw_quantity in cart.items():
                                product = products_by_id.get(str(product_id))
                                quantity = _parse_quantity(raw_quantity)
                                if product is None or quantity is None or quantity > product.stock:
                                    raise ValueError("Uno o más productos ya no están disponibles en la cantidad solicitada.")
                                order_lines.append((product, quantity))
                                order_total += product.price * quantity
                            if not order_lines:
                                raise ValueError("El carrito está vacío.")

                            # Agregar costo de domicilio al total
                            order_total += delivery_cost

                            order = Order.objects.create(
                                user=request.user if request.user.is_authenticated else None,
                                checkout_token=checkout_token,
                                customer_name=form.cleaned_data["customer_name"].strip(),
                                customer_phone=form.cleaned_data.get("customer_phone", "").strip(),
                                customer_email=form.cleaned_data.get("customer_email", "").strip(),
                                delivery_option=delivery_option,
                                delivery_zone=delivery_zone,
                                delivery_cost=delivery_cost,
                                delivery_address=form.cleaned_data.get("delivery_address", "").strip(),
                                delivery_notes=form.cleaned_data.get("delivery_notes", "").strip(),
                                total=order_total,
                                notes="Pedido generado desde la tienda online.",
                            )
                            # Logging de auditoría
                            audit_logger.info(
                                f"Orden creada #{order.pk}: Cliente={order.customer_name}, "
                                f"Total=${order.total:.2f}, Entrega={delivery_option}, "
                                f"Items={len(order_lines)}"
                            )
                            
                            for product, quantity in order_lines:
                                Product.objects.filter(pk=product.pk).update(stock=product.stock - quantity)
                                OrderItem.objects.create(
                                    order=order,
                                    product=product,
                                    product_name=product.name,
                                    quantity=quantity,
                                    price=product.price,
                                )
                                # Logging de stock
                                logger.info(
                                    f"Stock actualizado: {product.name} "
                                    f"(ID={product.pk}), Cantidad: {quantity}, "
                                    f"Stock anterior: {product.stock}, "
                                    f"Stock nuevo: {product.stock - quantity}"
                                )
                    _save_cart(request, {})
                    return _render_whatsapp_order(request, order)
                except ValueError as error:
                    messages.error(request, str(error))
                except IntegrityError:
                    order = Order.objects.get(checkout_token=checkout_token)
                    return _render_whatsapp_order(request, order)
    else:
        form = DeliveryForm(initial={
            "checkout_token": uuid.uuid4(),
            "customer_name": request.user.get_full_name() if request.user.is_authenticated else "",
            "customer_email": request.user.email if request.user.is_authenticated else "",
        })

    return render(request, "store/checkout_delivery.html", {
        "form": form,
        "items": items,
        "total": total,
        "delivery_zones": DeliveryZone.objects.filter(is_active=True),
        "page_title": "Datos de entrega",
    })


def _render_whatsapp_order(request, order):
    items = [{"product": item.product, "product_name": item.product_name or item.product.name,
              "quantity": item.quantity, "line_total": item.line_total}
             for item in order.items.select_related("product")]
    delivery_text = "\nEnvío a domicilio:\n" + order.delivery_address if order.delivery_option == "delivery" else "\nRetiro en local"
    if order.delivery_notes and order.delivery_option == "delivery":
        delivery_text += f"\nIndicaciones: {order.delivery_notes}"
    item_lines = [f"{item['product_name']} x {item['quantity']} - ${item['line_total']:.2f}" for item in items]
    message = config.WHATSAPP_MESSAGE_TEMPLATE.format(
        order_number=order.pk,
        customer=order.customer_name,
        phone=order.customer_phone,
        items="\n".join(item_lines),
        total=f"${order.total:.2f}",
        delivery=delivery_text,
    )
    return render(request, "store/whatsapp_checkout.html", {
        "message": message, "numbers": config.WHATSAPP_NUMBERS, "items": items,
        "total": order.total, "order": order, "page_title": "Pedido por WhatsApp",
    })


def register_view(request):
    if request.user.is_authenticated:
        return redirect("store:home")
    if request.method == "POST":
        form = CustomerRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Cuenta creada exitosamente.")
            return redirect("store:home")
    else:
        form = CustomerRegistrationForm()
    return render(request, "store/register.html", {"form": form, "page_title": "Crear cuenta"})


class CustomerLoginView(LoginView):
    template_name = "store/login.html"
    redirect_authenticated_user = True

    def get_success_url(self):
        return reverse("store:home")


class CustomerLogoutView(LogoutView):
    next_page = "store:home"
    http_method_names = ["get", "post", "options"]

    def get(self, request, *args, **kwargs):
        return self.post(request, *args, **kwargs)


@login_required
def profile_view(request):
    if request.method == "POST":
        form = CustomerProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Perfil actualizado.")
            return redirect("store:profile")
    else:
        form = CustomerProfileForm(instance=request.user)
    orders = Order.objects.filter(user=request.user).prefetch_related("items")
    return render(request, "store/profile.html", {
        "form": form,
        "orders": orders,
        "page_title": "Mi cuenta",
    })


@staff_member_required
@login_required
def admin_dashboard(request):
    context = {
        "products_count": Product.objects.count(),
        "active_products": Product.objects.filter(is_active=True).count(),
        "categories_count": Category.objects.count(),
        "featured_count": Product.objects.filter(is_featured=True).count(),
        "orders_count": Order.objects.count(),
        "pending_orders": Order.objects.filter(status="pending").count(),
        "recent_products": Product.objects.order_by("-created_at")[:5],
        "page_title": "Dashboard",
    }
    return render(request, "store/admin_dashboard.html", context)


@staff_member_required
@login_required
def admin_products(request):
    if request.method == "POST":
        product_id = request.POST.get("product_id")
        if product_id:
            # Editar producto existente
            product = get_object_or_404(Product, pk=product_id)
            form = ProductAdminForm(request.POST, request.FILES, instance=product)
        else:
            # Crear nuevo producto
            form = ProductAdminForm(request.POST, request.FILES)
        
        if form.is_valid():
            product = form.save()
            # Asegurar que el producto tenga configuración de entrega
            ProductDeliveryConfig.objects.get_or_create(product=product)
            # Logging de auditoría
            if product_id:
                audit_logger.info(
                    f"Producto actualizado: {product.name} (ID={product.pk}), "
                    f"Precio=${product.price:.2f}, Stock={product.stock}, "
                    f"Activo={product.is_active}, Destacado={product.is_featured}"
                )
            else:
                audit_logger.info(
                    f"Producto creado: {product.name} (ID={product.pk}), "
                    f"Precio=${product.price:.2f}, Stock={product.stock}, "
                    f"Usuario={request.user.username}"
                )
            messages.success(request, f"Producto '{product.name}' guardado exitosamente.")
            return redirect("store:admin_products")
    else:
        form = ProductAdminForm()
    
    return render(request, "store/admin_products.html", {
        "products": Product.objects.select_related("category").all(),
        "form": form,
        "categories": Category.objects.all(),
        "page_title": "Productos",
    })


@staff_member_required
@login_required
def admin_edit_product(request, product_id):
    product = get_object_or_404(Product, pk=product_id)
    
    if request.method == "POST":
        form = ProductAdminForm(request.POST, request.FILES, instance=product)
        if form.is_valid():
            form.save()
            ProductDeliveryConfig.objects.get_or_create(product=product)
            messages.success(request, f"Producto '{product.name}' actualizado exitosamente.")
            return redirect("store:admin_products")
    else:
        form = ProductAdminForm(instance=product)
    
    return render(request, "store/admin_products.html", {
        "products": Product.objects.select_related("category").all(),
        "form": form,
        "categories": Category.objects.all(),
        "page_title": "Productos",
    })


@staff_member_required
@login_required
def admin_delete_product(request, product_id):
    product = get_object_or_404(Product, pk=product_id)
    product_name = product.name
    product_price = product.price
    product_id_val = product.id
    
    if request.method == "POST" or request.GET.get("confirm") == "true":
        product.delete()
        # Logging de auditoría
        audit_logger.info(
            f"Producto eliminado: {product_name} (ID={product_id_val}), "
            f"Precio=${product_price:.2f}, Usuario={request.user.username}"
        )
        messages.success(request, f"Producto '{product_name}' eliminado exitosamente.")
    
    return redirect("store:admin_products")
