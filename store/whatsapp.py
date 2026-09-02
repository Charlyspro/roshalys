from urllib.parse import quote

SITE_NAME_MESSAGES = {
    "confirmed": {
        "short": "Confirmado",
        "subject_part": "confirmado",
    },
    "preparing": {
        "short": "En preparación",
        "subject_part": "en preparación",
    },
    "ready": {
        "short": "Listo",
        "subject_part": "listo para retirar",
    },
    "shipped": {
        "short": "Enviado",
        "subject_part": "enviado",
    },
    "delivered": {
        "short": "Entregado",
        "subject_part": "entregado",
    },
    "cancelled": {
        "short": "Cancelado",
        "subject_part": "cancelado",
    },
}


def build_status_message(order, status_key, site_name="ROSHALYS"):
    """Arma el mensaje de WhatsApp para el cliente según el estado del pedido."""
    cfg = SITE_NAME_MESSAGES.get(status_key)
    if cfg is None:
        return ""

    messages = {
        "confirmed": (
            f"Hola {order.customer_name}! Tu pedido #{order.pk} fue *confirmado*. "
            f"Estamos preparando todo para vos. ¡Gracias por comprar en {site_name}!"
        ),
        "preparing": (
            f"Hola {order.customer_name}! Tu pedido #{order.pk} está *en preparación*. "
            f"Te avisamos cuando esté listo. ¡Gracias!"
        ),
        "ready": (
            f"Hola {order.customer_name}! Tu pedido #{order.pk} está *listo para retirar*. "
            f"Pasá a buscarlo. Total: ${order.total:.2f}. ¡Te esperamos en {site_name}!"
        ),
        "shipped": (
            f"Hola {order.customer_name}! Tu pedido #{order.pk} fue *enviado*. "
            f"Te estará llegando pronto. ¡Gracias por elegirnos!"
        ),
        "delivered": (
            f"Hola {order.customer_name}! Tu pedido #{order.pk} fue *entregado*. "
            f"¡Esperamos que lo disfrutes! Gracias por comprar en {site_name}."
        ),
        "cancelled": (
            f"Hola {order.customer_name}! Lamentablemente tu pedido #{order.pk} fue *cancelado*. "
            f"Ante cualquier consulta escribinos. Disculpá las molestias."
        ),
    }
    return messages.get(status_key, "")


def wa_link_for(order, status_key, site_name="ROSHALYS"):
    """Devuelve la URL wa.me para avisar al cliente del estado de su pedido."""
    number = (order.customer_phone or "").strip().lstrip("+").replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    if not number:
        return ""
    message = build_status_message(order, status_key, site_name)
    return f"https://wa.me/{number}?text={quote(message)}"


def build_product_message(product, site_name="ROSHALYS", product_url=""):
    """Compone el mensaje para publicar un producto (nombre, precio y enlace)."""
    lines = [f"*{product.name}*", f"Precio: ${product.price:.2f}"]
    if product_url:
        lines.append(f"Ver en {site_name}: {product_url}")
    return "\n".join(lines)


def product_wa_link(product, number, site_name="ROSHALYS", product_url=""):
    """Devuelve la URL wa.me con el mensaje del producto pre-cargado."""
    if not number:
        return ""
    number = str(number).strip().lstrip("+").replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    message = build_product_message(product, site_name, product_url)
    return f"https://wa.me/{number}?text={quote(message)}"
