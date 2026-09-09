"""
ASGI config for roshalys project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/asgi/
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "roshalys.settings")

import roshalys.cookie_patch  # noqa: F401  (corrige Set-Cookie con espacio inicial)

application = get_asgi_application()
