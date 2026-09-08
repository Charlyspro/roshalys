# ROSHALYS

ROSHALYS es una tienda online MVP desarrollada con Django, SQLite y una arquitectura sencilla para facilitar mantenimiento y despliegue posterior en hosting.

> **📋 Para desarrolladores/agentes:** consulta **[STORE_SUMMARY.md](STORE_SUMMARY.md)** — resumen actual de la tienda (estructura, flujo de compra, colores actuales, despliegue y cambios recientes).

> **⚠️ Versión Wasmer Edge**: esta copia ha sido adaptada para desplegarse en [Wasmer Edge](https://wasmer.io) usando la detección automática de proyectos Django (Python/USD en el borde). Consulta la sección [Despliegue en Wasmer Edge](#despliegue-en-wasmer-edge) más abajo.

## Requisitos

- Python 3.10+
- Django 5.2 LTS
- SQLite
- Navegador web moderno

## Instalación

1. Clona o descarga el proyecto.
2. Crea un entorno virtual:
   python -m venv .venv
3. Activa el entorno:
   .venv\Scripts\activate
4. Instala dependencias:
   python -m pip install --upgrade pip
   python -m pip install django pillow python-decouple
5. Copia `.env.example` a `.env` y ajusta los valores.

## Configuración

Archivo de configuración principal:

- `.env.example`
- `.env`

Valores principales:

- STORE_NAME: nombre de la tienda.
- WHATSAPP_NUMBERS: números separados por coma.
- STORE_CURRENCY: moneda.
- PRIMARY_COLOR, SECONDARY_COLOR, BACKGROUND_COLOR, TEXT_COLOR, BUTTON_COLOR: esquema visual.
- ADMIN_EMAIL: correo administrativo.

## Ejecución local

1. Crea la base de datos:
   python manage.py migrate
2. Crea un usuario administrador:
   python manage.py createsuperuser
3. Carga productos de ejemplo:
   python manage.py seed_store
4. Ejecuta el servidor:
   python manage.py runserver
5. Abre la tienda en http://127.0.0.1:8000/
6. Abre el panel administrativo en http://127.0.0.1:8000/admin/

## Usuario administrador

- Usuario local de prueba: `admin`
- Contraseña local de prueba: `admin123`
- Cambia esta contraseña al desplegar o antes de usarlo en un entorno real.
- La administración del catálogo se maneja desde Django Admin.
- El dashboard público está disponible en `/admin-dashboard/` con login de staff.

## Estructura del proyecto

- `roshalys/`: configuración principal de Django.
- `store/`: app principal con modelos, vistas, plantillas y estáticos.
- `media/`: imágenes cargadas por el administrador.
- `staticfiles/`: archivos estáticos compilados.
- `.env`: variables de entorno locales.

## Cómo agregar productos

1. Accede a `/admin/`.
2. Crea o edita una categoría.
3. Crea un producto en el módulo correspondiente.
4. Suba la imagen principal y opcionalmente más imágenes.
5. Guarda y publícalo activando la opción `is_active`.

## Cómo cambiar WhatsApp

Edite el archivo `.env` y cambie la variable `WHATSAPP_NUMBERS`:

WHATSAPP_NUMBERS=54279546,55502491

Se recomienda dejar el código internacional fuera del valor base para permitir su adición posterior.

## Cómo cambiar precios

Desde `/admin/` edita el producto y actualiza el campo de precio.

## Cómo cambiar colores

Ajusta los valores siguientes en `.env`:

- PRIMARY_COLOR
- SECONDARY_COLOR
- BACKGROUND_COLOR
- TEXT_COLOR
- BUTTON_COLOR

## Backup de la base de datos

La base de datos local es SQLite y se guarda en `db.sqlite3`.

Para hacer una copia de seguridad:

cp db.sqlite3 db.sqlite3.backup

## Preparación para hosting

1. Configura un servidor con Python y un entorno virtual.
2. Instala las dependencias.
3. Usa una base de datos persistente (MySQL/MariaDB o SQLite si el hosting lo permite).
4. Ajusta `ALLOWED_HOSTS`, `DEBUG=False` y variables de entorno para producción.
5. Ejecuta `python manage.py collectstatic`.
6. Configura el servicio web para servir Django.

## Notas del MVP

- Sin pagos online.
- El flujo final es carrito + WhatsApp.
- El administrador puede gestionar productos y categorías desde Django Admin.
- El envío a domicilio está disponible para cualquier pedido cuyo subtotal alcance el mínimo configurado (`DELIVERY_MIN_TOTAL`, por defecto `$1000`), sin restricciones por producto.

## Auditoría y Logging

El sistema registra automáticamente eventos importantes:

- **Creación, edición y eliminación de productos** → `logs/audit.log`
- **Órdenes creadas** → `logs/audit.log`
- **Cambios de stock** → `logs/tienda.log`

### Ver logs

```bash
# Últimas 20 líneas del log de auditoría
tail -20 logs/audit.log

# Todos los logs
less logs/tienda.log
```

### Configurar nivel de log

Edita `.env` con `LOG_LEVEL`:

```env
LOG_LEVEL=DEBUG    # Muy detallado (desarrollo)
LOG_LEVEL=INFO     # Normal (producción)
LOG_LEVEL=WARNING  # Solo advertencias y errores
```

## Tests Unitarios

Ejecuta 40+ tests para verificar funcionalidad:

```bash
python manage.py test store
```

Tests disponibles:

- ✅ Modelos (Product, Category, Order, DeliveryZone)
- ✅ Carrito de compras (agregar, actualizar, remover)
- ✅ Checkout y órdenes
- ✅ Búsqueda y categorías
- ✅ Administración de productos (CRUD)
- ✅ Cálculo de costos de envío
- ✅ Autenticación y permisos

## Despliegue en Wasmer Edge

Esta copia está adaptada para ejecutarse en **Wasmer Edge** (WebAssembly / Python WASIX). Wasmer detecta automáticamente el proyecto como aplicación Django por la presencia de `manage.py` y elimina `requirements.txt`/`pyproject.toml`.

### Adaptaciones aplicadas

- **`roshalys/wsgi.py`**: expone la variable `app` como entrypoint WSGI (además de `application`).
- **`roshalys/settings.py`**: `WSGI_APPLICATION = "roshalys.wsgi.app"` y `ALLOWED_HOSTS` incluye `.wasmer.app`.
- **`requirements.txt` / `pyproject.toml`**: versiones compatibles con WASIX (Django 5.2.x LTS, `mysqlclient`).
- **`settings.py`**: soporte para `DATABASE_ENGINE=mysql` (base de datos persistente de Wasmer).
- **`Procfile`**: `gunicorn roshalys.wsgi:app`.

### Despliegue

1. Sube el proyecto a un repositorio de GitHub (los secretos de `.env` **no** deben subirse; configura las variables en el dashboard de Wasmer).
2. En [wasmer.io](https://wasmer.io), crea una app y conecta el repositorio, o desde CLI:
   ```bash
   wasmer login
   wasmer deploy
   ```
3. Wasmer detectará Django, creará una **base de datos MySQL persistente** e inyectará automáticamente las variables `DB_HOST`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_PORT`.
4. En el dashboard establece como variable de entorno:
   ```
   DATABASE_ENGINE=mysql
   SECRET_KEY=<clave-secreta-larga>
   DEBUG=False
   ALLOWED_HOSTS=localhost,127.0.0.1,0.0.0.0,.wasmer.app
   ```
5. Aplica las migraciones durante el build y recoge estáticos:
   ```bash
   python manage.py migrate
   python manage.py collectstatic --no-input
   ```
   (Wasmer ejecuta migraciones automáticamente en proyectos Django.)
6. Accede a `https://<tu-app>.wasmer.app`.

### Base de datos persistente

En producción Wasmer inyecta automáticamente una **MySQL** (persistente). El `settings.py` usa esas variables cuando `DATABASE_ENGINE=mysql`. Para desarrollo local sigue usándose SQLite (`db.sqlite3`) sin cambios.
