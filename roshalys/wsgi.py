"""
WSGI config for roshalys project.

It exposes the WSGI callable as module-level variables named ``application``
(estándar) y ``app`` (entrypoint de Wasmer Edge).

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "roshalys.settings")

import roshalys.cookie_patch  # noqa: F401  (corrige Set-Cookie con espacio inicial)

application = get_wsgi_application()

# Wasmer Edge espera la variable `app` como entrypoint WSGI.
app = application
