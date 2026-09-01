from . import config


def store_settings(request):
    cart = request.session.get("cart", {})
    cart_count = sum(int(qty) for qty in cart.values() if int(qty) > 0)

    return {
        "store_name": config.SITE_NAME,
        "store_logo": config.LOGO_TEXT,
        "store_currency": config.CURRENCY,
        "admin_email": config.ADMIN_EMAIL,
        "whatsapp_numbers": config.WHATSAPP_NUMBERS,
        "primary_color": config.PRIMARY_COLOR,
        "secondary_color": config.SECONDARY_COLOR,
        "background_color": config.BACKGROUND_COLOR,
        "text_color": config.TEXT_COLOR,
        "button_color": config.BUTTON_COLOR,
        "cart_count": cart_count,
    }
