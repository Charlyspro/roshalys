"""
WSGI config for roshalys project.

It exposes the WSGI callable as module-level variables named ``application``
(estándar) y ``app`` (entrypoint de Wasmer Edge).

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/wsgi/
"""

import os
import sys

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "roshalys.settings")

import roshalys.cookie_patch  # noqa: F401  (corrige Set-Cookie con espacio inicial)

application = get_wsgi_application()


def _migrate_on_boot():
    # Wasmer ejecuta `migrate` en el job `after_deploy` contra una BD efímera;
    # este respaldo garantiza que el esquema llegue a la BD persistente del
    # runtime al arrancar el proceso WSGI.
    # Nunca se ejecuta en comandos de gestión incompatibles (test, migrate,
    # makemigrations, shell, collectstatic, etc.), solo al arrancar un servidor.
    args = " ".join(sys.argv).lower()
    if not args:
        return
    if any(tok in args for tok in ("test", " migrate", " makemigrations", "shell", "collectstatic",
                                   "flush", "loaddata", "dumpdata", "createsuperuser", "whatsapp",
                                   "seed")):
        return
    # El runtime deja el executeable del servidor (p. ej. `/opt/venv/.../uvicorn`)
    # en `sys.argv[0]`, así que se detecta por substring y no por igualdad exacta.
    if not any(server in args for server in ("uvicorn", "gunicorn", "hypercorn", "daphne")):
        return
    try:
        from django.core import management
        management.call_command("migrate", interactive=False, verbosity=0)
    except Exception:
        pass


_migrate_on_boot()

# Wasmer Edge espera la variable `app` como entrypoint WSGI.
app = application
