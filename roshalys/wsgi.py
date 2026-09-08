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


def _migrate_on_boot():
    # Wasmer ejecuta `migrate` durante el build contra una BD efímera; este
    # respaldo garantiza que el esquema llegue a la BD persistente del runtime.
    try:
        import sys
        if "test" in sys.argv or "migrate" in sys.argv or "makemigrations" in sys.argv:
            return
        from django.core import management
        management.call_command("migrate", interactive=False, verbosity=0)
    except Exception:
        pass


_migrate_on_boot()

# Wasmer Edge espera la variable `app` como entrypoint WSGI.
app = application
