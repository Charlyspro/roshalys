from . import config


def _clean_wa_number(number):
    return str(number or "").strip().lstrip("+").replace(" ", "").replace("-", "").replace("(", "").replace(")", "")


def store_settings(request):
    cart = request.session.get("cart", {})
    cart_count = sum(int(qty) for qty in cart.values() if int(qty) > 0)

    whatsapp_number = _clean_wa_number(config.WHATSAPP_NUMBERS[0]) if config.WHATSAPP_NUMBERS else ""

    return {
        "store_name": config.SITE_NAME,
        "store_logo": config.LOGO_TEXT,
        "store_currency": config.CURRENCY,
        "admin_email": config.ADMIN_EMAIL,
        "cart_count": cart_count,
        "whatsapp_number": whatsapp_number,
        "whatsapp_link": f"https://wa.me/{whatsapp_number}" if whatsapp_number else "https://wa.me/",
        "ollama_enabled": config.OLLAMA_ENABLED,
    }
