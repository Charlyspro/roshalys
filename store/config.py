from decimal import Decimal

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

DELIVERY_MIN_TOTAL = config("DELIVERY_MIN_TOTAL", default="1000", cast=Decimal)

BUSINESS_TIMEZONE = config("BUSINESS_TIMEZONE", default="America/Havana")

OLLAMA_ENABLED = config("OLLAMA_ENABLED", default=False, cast=bool)
OLLAMA_URL = config("OLLAMA_URL", default="http://127.0.0.1:11434")
OLLAMA_MODEL = config("OLLAMA_MODEL", default="gemma4:latest")
OLLAMA_TIMEOUT = config("OLLAMA_TIMEOUT", default=45, cast=int)

WHATSAPP_MESSAGE_TEMPLATE = (
    "Hola, quiero realizar el pedido #{order_number}:\n"
    "Cliente: {customer}\n"
    "{items}\n"
    "{delivery}\n"
    "Total: {total}"
)
