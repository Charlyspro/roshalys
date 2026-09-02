from decouple import config

SITE_NAME = config("STORE_NAME", default="ROSHALYS")
LOGO_TEXT = config("STORE_LOGO", default="ROSHALYS")
CURRENCY = config("STORE_CURRENCY", default="USD")
ADMIN_EMAIL = config("ADMIN_EMAIL", default="admin@roshalys.local")
WHATSAPP_NUMBERS = [
    number.strip()
    for number in config(
        "WHATSAPP_NUMBERS",
        default="",
    ).split(",")
    if number.strip()
]
PRIMARY_COLOR = config("PRIMARY_COLOR", default="#0f766e")
SECONDARY_COLOR = config("SECONDARY_COLOR", default="#f59e0b")
BACKGROUND_COLOR = config("BACKGROUND_COLOR", default="#f8fafc")
TEXT_COLOR = config("TEXT_COLOR", default="#1f2937")
BUTTON_COLOR = config("BUTTON_COLOR", default="#0f766e")

WHATSAPP_MESSAGE_TEMPLATE = (
    "Hola, quiero realizar el pedido #{order_number}:\n"
    "Cliente: {customer}\n"
    "{items}\n"
    "{delivery}\n"
    "Total: {total}"
)
