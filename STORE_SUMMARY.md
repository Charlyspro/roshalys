# ROSHALYS — RESUMEN DE TIENDA PARA AGENTES

> **Punto de entrada para futuros agentes.** Este documento describe el estado ACTUAL de la tienda.
> Complementa y actualiza a `README.md` (setup/instalación) y `REDESIGN_SUMMARY.md` (histórico del rediseño,
> que ya NO refleja los colores actuales). El envío a domicilio depende del subtotal mínimo `DELIVERY_MIN_TOTAL` (por defecto `$1000`)
> y de una **ventana de horario de domicilio** (por defecto 09:00–18:00, configurable en `StoreConfig`).

---

## 1. QUÉ ES

ROSHALYS es una **tienda online MVP** de moda/estética con la marca **"Elegancia Moderna"**. Desarrollada en **Django 5.2 LTS** y desplegada en **Wasmer Edge** (WebAssembly / Python WASIX, entrada WSGI + MySQL persistente).

- **Web de producción:** https://roshalys.wasmer.app
- **Admin de producción:** https://roshalys.wasmer.app/admin/
- **Owner Wasmer / CLI:** `charlyspro771` · App: `roshalys`
- **Moneda:** dólar estadounidense (`$`)

Dos audiencias:
1. **Clientes** → compran en `https://roshalys.wasmer.app` (carrito + pedido por WhatsApp).
2. **Administración** → Django Admin (`/admin/`) y un dashboard público de staff en `/admin-dashboard/`.

---

## 2. STACK Y ESTRUCTURA

- **Backend:** Django 5.2 LTS, Python 3.13 (remoto) / 3.10+ (local)
- **Base de datos:** SQLite local (`db.sqlite3`) · **MySQL persistente** en producción (Wasmer inyecta `DB_HOST/DB_NAME/DB_USER/DB_PASSWORD/DB_PORT`; se activa con `DATABASE_ENGINE=mysql`)
- **Frontend:** Django templates + CSS propio en `store/static/css/styles.css` (diseño con variables CSS).

```
roshalys/            # Config principal de Django (wsgi.py expone `app` + `application`)
store/               # App principal: models, views, forms, urls, templates, static
  models.py          # Category, Product, ProductImage, Order, OrderItem, DeliveryZone
  forms.py           # DeliveryForm, CustomerProfileForm, ProductAdminForm, ProductImageAdminForm
  views.py           # home, category/product/search, cart, checkout (whatsapp), cuentas, admin CRUD
  context_processors.py  # expone whatsapp_number, whatsapp_link, store_name, colores a todos los templates
  static/css/styles.css  # CSS de la tienda (clientes)
  static/css/admin.css   # CSS del panel admin
  templates/store/   # Templates de clientes (home, category, product_detail, cart, checkout_delivery, etc.)
templates/admin/     # base_site.html, login.html (skin del Django Admin)
media/               # Imágenes subidas por el admin
staticfiles/         # Estáticos compilados (collectstatic) — se regenera en cada deploy
.env / .env.example  # Config local (NO subir .env a git/Wasmer)
app.yaml             # Config de despliegue Wasmer
```

---

## 3. FLUJO DE COMPRA DEL CLIENTE

1. **Inicio** `/` → carrusel de "Lo más vendido", **"Compra por categoría"** (chips), favoritos, catálogo.
2. **Navegación:** menú desplegable de categorías; barra inferior móvil con **Inicio · Buscar · Carrito · WhatsApp · Cuenta**.
3. **Producto** → **Agregar al carrito** (por POST, campo `cart` en sesión, no usa cookies permanentes).
4. **Carrito** `/cart/` → ver/modificar cantidades, eliminar.
5. **Checkout** → **`/checkout/whatsapp/`** = la pantalla "Datos de entrega".
   - Formulario `DeliveryForm` (información personal + opción de entrega).
   - **Opción "Recoger en el local"** → sólo pide datos personales.
   - **Opción "Envío a domicilio"** → **muestra condicionalmente "Zona de entrega"** (bloque `#delivery-fields`), dirección e indicaciones (JS en `checkout_delivery.html`). Costo de entrega se calcula desde `DeliveryZone.cost`.
   - **Nota: NO se pide correo electrónico al cliente** (campo `customer_email`, `required=False`, excluido del template).
6. **Resumen** → botón/WhatsApp genera el pedido con el número real de WhatsApp (ver §5) y lo envía por `wa.me`.

---

## 4. MODELOS CLAVE (resumen)

- **Category** (`name`, `slug`, `is_active`)
- **Product** (`name`, `slug`, `price`, `stock`, `is_active`, `category`, `description`, imagen principal + `ProductImage`)
- **Order / OrderItem** — pedido: cliente, dirección, notas, `delivery_cost`, `delivery_zone`, `checkout_token`, `status`
- **DeliveryZone** (`name`, `cost`, `is_active`) — zonas de entrega y su costo.

---

## 5. WHATSAPP

- **Números configurados** (en `.env`, `.env.example` y `app.yaml`):
  `WHATSAPP_NUMBERS=5354279546,5355502491`
  - Primer número (principal): **+5354279546** · Segundo: **+5355502491** (ambos código de país +53, Cuba).
- El `context_processor` expone `whatsapp_number` y `whatsapp_link` a **todos** los templates.
- Hay un **botón flotante "Escríbenos"** (verde, SVG oficial de WhatsApp) en `base.html` (`#wa-float-btn` / `.wa-float-btn`), que en móvil se coloca `bottom: 76px` para no tapar la barra inferior.
- Requisito de negocio: los enlaces `wa.me/` **nunca** deben quedar vacíos; se corrigen si faltan.

---

## 6. DISEÑO (COLORES ACTUALES) — IMPORTANTE

La paleta actual es **"Elegancia Moderna" con tonos cálidos y tenues** (cambiada recientemente desde el negro `#111827` / dorado `#D4AF37` original).

**Tienda** (`store/static/css/styles.css`, variables `:root`):
| Variable | Color | Uso |
|---|---|---|
| `--primary` | `#3A6B54` (verde esmeralda tenue) | botones de acción, contador carrito, enlaces |
| `--primary-strong` | `#2F5A45` | hover de botones |
| `--secondary` | `#D99A6C` (ámbar/coral cálido) | acentos, enlaces al hover |
| `--text` | `#2F3B36` (grafito cálido) | texto principal |
| `--bg` | `#FDFCFA` (crema) | fondo base cálido |
| `--border` | `#E7E5DF` | bordes |

**Admin** (`store/static/css/admin.css`): misma paleta (verde esmeralda + ámbar) en toda la parte administrativa y login.

> ⚠️ En `store/config.py` existen variables `.env` `PRIMARY_COLOR`/`SECONDARY_COLOR`/`BUTTON_COLOR` (defaults teal/ámbar) expuestas vía `context_processor`, pero **NO se usan en el template/CSS** — el diseño real se controla por las variables CSS de `styles.css`/`admin.css`. Para cambiar colores reales, editar los archivos CSS, no el `.env`.

---

## 7. ACCESOS / CREDENCIALES

- **Admin:** usuario local de prueba `admin` / `admin123` (CAMBIAR en un entorno real).
- **Dashboard de staff:** `/admin-dashboard/` (requiere login de staff).
- **Panel público de gestión de productos:** `/admin-productos/` (CRUD rápido: editar, eliminar, publicar `is_active`).

---

## 8. WORKFLOW DE DESARROLLO Y DEPLOY

### Tests
```bash
python manage.py test store        # suite completa · actualmente 52 tests, todos en verde
python manage.py makemigrations --check   # verifica que no haya migraciones pendientes
```

### Deploy a Wasmer
```bash
wasmer deploy --build-remote
```
- El token de API de Wasmer está guardado de forma persistente (no hace falta variable de entorno).
- El build hace `collectstatic`; el job `after_deploy` ejecuta `migrate` (Normalmente OK; un aviso de "Post-deployment job did not complete" es inofensivo si no hay migraciones pendientes).
- Verificar en https://roshalys.wasmer.app tras cada deploy.

### Pasos generales tras hacer un cambio
1. Editar archivos (templates, CSS, vistas, modelos).
2. `python manage.py test store` (y `makemigrations --check` si se tocaron modelos).
3. `wasmer deploy --build-remote`.
4. Verificar en producción.

---

## 9. CAMBIOS RECIENTES (para tener contexto de sesiones previas)

- **Formulario de entrega:** se eliminó "Correo electrónico" de la pantalla "Datos de entrega"; la **"Zona de entrega"** ahora aparece **sólo cuando el cliente elige "Envío a domicilio"** (dejó de duplicarse en info personal). Archivo: `store/templates/store/checkout_delivery.html`.
- **Colores:** tienda y admin pasaron de negro `#111827` + dorado `#D4AF37` a **verde esmeralda tenue `#3A6B54` + ámbar/coral `#D99A6C`** con fondos crema. Archivos: `css/styles.css` y `css/admin.css`.
- **Centrado / uniformidad:** la barra "Compra por categoría" quedó **centrada** y con ajuste de línea (`justify-content: center` + `flex-wrap`); la **barra inferior móvil** quedó con reparto uniforme (`space-evenly`, `width:100%`, centrada).
- **Menú de categorías:** dropdown con puente `::after` + `:focus-within` para que no desaparezca al mover el cursor.
- **Botón flotante de WhatsApp** "Escríbenos" y corrección de enlaces `wa.me/` vacíos en footer y barra móvil.
- **Horario Abierto/Cerrado:** mientras la tienda está cerrada, **todo el sitio público** (salvo `/admin/`, estáticos y la propia `/cerrado/`) redirige a una **pantalla "Estamos cerrados"** con cuenta regresiva en vivo y botón de WhatsApp. Configurado desde el admin:
  - `store/models.py` → `StoreHours` (horario por día, editable en bloque) y `StoreConfig` (1 fila, con **`force_open`** para emergencias).
  - `store/hours.py` (lógica `is_open`, `seconds_until_open`, `next_open_info`, `schedule_summary`), `store/middleware.py` (`StoreClosedMiddleware`) y `store/templates/store/closed.html`.
  - Zona horaria del negocio: `BUSINESS_TIMEZONE` (env), default `America/Havana`. Default de horario: Lun–Vie 9:00–18:00 · Sáb 9:00–13:00 · Dom cerrado (ajustar en admin). Migraciones **0010**.
- **Horario de domicilio (regla fija):** los **domicilios** solo se admiten dentro de una ventana de `StoreConfig.delivery_from`/`delivery_to` (default **09:00–18:00**, configurable en admin). Regla elegida por el cliente (**Opción 3**):
  - El checkout muestra "Domicilios: de 09:00 a 18:00" en la tarjeta de entrega.
  - Fuera de esa ventana **NO se bloquea el pedido**: se muestra un aviso ("tu pedido se entregará al día siguiente") y se exige marcar una **casilla de aceptación**; si no se marca, se rechaza con mensaje de error.
  - Al aceptar, el pedido se crea y se añade la nota "Entrega fuera del horario de domicilio: se entregará al día siguiente.".
  - La recogida en tienda (`pickup`) nunca se bloquea. `force_open` en `StoreConfig` también activa la ventana de domicilio.
  - Implementación: `store/hours.py` → `delivery_window()`, `store/views.py` (validación POST + contexto), `store/templates/store/checkout_delivery.html` (fila `#delivery-late-row` + JS), `store/forms.py` (`accept_delivery_late`). Migración **0012**.
- **Migraciones en producción:** en Wasmer, `migrate` dentro del build toca una BD efímera y el job de deploy no es fiable; las migraciones a la MySQL persistente se aplican con `_migrate_on_boot()` en `roshalys/wsgi.py` al arrancar la app (guardado contra `test`/`migrate`/`makemigrations` en `sys.argv`). `app.yaml` también tiene un job `after_deploy` con `python manage.py migrate --noinput`.
- **Contador de visitas (privado):** cuenta **visitas** (cada página pública 200) y **visitantes únicos por día** (hash IP+UA, sin guardar IPs). No cuenta admin, estáticos ni usuarios staff. Se ve en `/admin-dashboard/` ("Visitas hoy", "Visitantes únicos hoy", totales) y como modelo `DailyStats` en el admin (solo lectura). Implementación: `store/visits.py`, `VisitCounterMiddleware`, migración **0013**.
- **Acceso admin:** usuario `admin`; la contraseña la fija el secret Wasmer `ADMIN_BOOTSTRAP_PASSWORD` en el arranque (migración **0011**; sin secret no se crea/actualiza). Ver `CONTINUAR.md` §10.
- **Widget de países + me gusta (portada):** al **terminar el listado de productos** de la portada hay un panel en vivo con las **banderas + número acumulado por país** (máx. 6, ordenados por cantidad): al pulsar **👍 Me gusta / 👎 No me gusta** aparece la bandera del país de la persona y, si ya existe, **el número se suma**. El país se detecta **desde el navegador** (`https://ipwho.is/` por CORS, sin clave; en Wasmer el servidor NO ve la IP real del cliente) y se envía con el voto a `POST /feedback/`; refresco automático cada 30s vía `GET /visitors-countries/`. País guardado en `Feedback.country_code`, cache `VisitorCountry` como fallback. Banderas por CDN `flagcdn.com`. Los totales de opiniones (👍/👎) solo se ven en `/admin-dashboard/`. Migraciones **0014** y **0015**.

---

## 10. OBSERVACIONES ÚTILES PARA AGENTES

- **El usuario es no-técnico** y prefiere comunicarse en **español**. Hacer los cambios por él y explicárselo de forma simple; a veces prefiere que primero se le propongan los cambios y él confirme.
- Sin pagos online: el cobro/flujo final es **carrito + WhatsApp**.
- `styles_old.css` es un respaldo del rediseño (no se usa).
- El `collectstatic` avisa de archivos duplicados (p. ej. `css/styles.css` y `images/*`) que se ignoran — es normal, no es un error.
- Antes de editar modelos, revisar migraciones; la BD de producción es MySQL persistente.

---

**Estado:** ACTUALIZADO · Deploy más reciente OK en https://roshalys.wasmer.app · Tests **86/86 OK**
