# CONTINUAR.md — Tienda ROSHALYS (Django en Wasmer)

Documento de handoff. Léelo completo antes de tocar nada.

## 1. Estado actual (verificado 2026-09-07)

- Proyecto de referencia para cambios futuros: **`C:\SITIO WEP`** (repositorio git).
- Sitio EN VIVO: **https://roshalys.wasmer.app** (app `da_nQgIotrUxGMe`, owner `charlyspro771`).
  - El alias `roshalys-charlyspro771.wasmer.app` responde 400; NO usar.
- 8 categorías activas, 35 productos activos. Sitemap con 8 URLs de categoría (slugs normalizados en minúsculas).
- Slugs de categoría NORMALIZADOS con la migración `store/migrations/0009_normalize_category_slugs.py`.
  - La categoría que se llamaba "Cocina" ahora es `condimentos-y-cocina`. `/categoria/Cocina/` da 404 (correcto).
  - Cualquier slug no canónico se auto-corrige con 301 en `store/views.py` (`category_products`), además de `slugify(name)` + update.
- Home con: grid `categories-grid` (9 tiles: "Ver todos · 35 productos" + 8 categorías con conteo) y catálogo completo sin paginación (39 tarjetas). Badge "Agotado"/`.sold-out-badge` en tarjetas con stock 0.
- Tests: **53/53 OK** con el venv local.
- Git: `C:\SITIO WEP` está en HEAD `9a6f921` con los cambios de sincronización SIN commitear (estado en `git status`). Commitear cuando el usuario lo pida.

## 2. Entornos

- Proyecto fuente/edición: `C:\SITIO WEP`
  - Venv de tests: `C:\SITIO WEP\.venv-1\Scripts\python.exe` (Django 5.2.17).
- Staging de deploy (crea/recrea cuando necesites): `C:\Users\CHARLY~1\AppData\Local\Temp\opencode\roshalys-final`
  - Es una COPIA del proyecto SIN `.venv*`, `IMAGENES`, `logs`, `media`, `staticfiles`, `secrets`, `.git`, `db.sqlite3`, `.env`, `.pyc`.

## 3. Cómo recrear el staging de deploy

Desde PowerShell (adapta rutas si cambian):

```powershell
$src = "C:\SITIO WEP"
$dst = "C:\Users\CHARLY~1\AppData\Local\Temp\opencode\roshalys-final"
if (Test-Path $dst) { Remove-Item $dst -Recurse -Force }
robocopy $src $dst /E /XD .venv .venv-1 IMAGENES logs media staticfiles secrets .git .opencode /XF *.pyc db.sqlite3 .env .env.example /NFL /NDL /NJH /NJS /NP
if ($LASTEXITCODE -ge 8) { throw "robocopy falló" }
```

Si apareciera `DELIVERY_CONFIG.md` en el staging, borrarlo; está obsoleto.

## 4. Tests (antes de desplegar)

```powershell
& "C:\SITIO WEP\.venv-1\Scripts\python.exe" manage.py test store
```

## 5. Desplegar

Desde el staging (los cambios deben estar en `C:\SITIO WEP` y copiarse al staging primero):

```powershell
wasmer deploy --build-remote --bump --no-validate --non-interactive
```

- `after_deploy` (job en `app.yaml`) corre `python manage.py migrate` — las migraciones SÍ se aplican en Wasmer; verificar en los logs tras el deploy.
- `app.yaml`: start `uvicorn roshalys.wsgi:app --interface=wsgi --host 0.0.0.0 --port $PORT`; apploca InstaBoot (`wasmer.io/version: 7.4.0`). Para purgar InstaBoot tras fallos de visto: comando `wasmer app deploy ... ` o volver a hacer bump (usar el flujo normal de deploy).

## 6. Verificación post-deploy (siempre)

Comparar hash SHA-256 de los bytes servidos vs locales (los hashes actuales sirven de referencia):

```powershell
$local = (Get-FileHash "C:\SITIO WEP\store\static\css\styles.css" -Algorithm SHA256).Hash
curl.exe -sL -o C:\Users\CHARLY~1\AppData\Local\Temp\opencode\chk.css https://roshalys.wasmer.app/static/css/styles.css
(Get-FileHash C:\Users\CHARLY~1\AppData\Local\Temp\opencode\chk.css -Algorithm SHA256).Hash -eq $local
```

- styles.css esperado: `7C91AB91B2D9918146ABFD7B55EC7F46E13080196F5A41B4CAB10845761ED0DD`
- admin.css esperado: `E7B45E80EE541BEFAA8D7AD1388FB9DC0048420C4D2BC81AE40740ABFE1BBF09`

Endpoints a comprobar tras cada deploy:

- `GET /` -> 200, contiene `categories-grid` y `Ver todos`
- `GET /categoria/condimentos-y-cocina/` -> 200
- `GET /categoria/Cocina/` -> 404
- `GET /sitemap.xml` -> 200, 8 URLs `categoria/`
- `GET /robots.txt` -> 200

## 7. Notas / trampas conocidas

- El badge "Agotado" (`sold-out-badge`) solo aparece en el HTML renderizado si HAY un producto con stock 0 en esa vista; no usarlo como único chequeo.
- Al comprobar strings con curl.exe: usar `Get-Content -Raw` + `.Contains()`; `.Contains()` sobre el ARRAY devuelto por curl da falsos negativos.
- `staticfiles` no se versiona en el repo; Wasmer hace collectstatic en el build. Los CSS se editan en `store/static/css/`.
- No tocar `db.sqlite3`/`.env` ni subirlos.
- `store/migrations/0008_delete_productdeliveryconfig.py` eliminó el modelo de config de entrega (era la causa de `DELIVERY_CONFIG.md`).

## 8. HORARIO ABIERTO/CERRADO (nuevo, 2026-09-08)

- Mientras la tienda está cerrada, **todo el sitio público** (menos `/admin/`, `/static/`, `/media/` y la propia `/cerrado/`) redirige por middleware (`store/middleware.py`) a la pantalla `store/templates/store/closed.html`: logo, "Estamos cerrados", horario, **cuenta regresiva en vivo** ("Abrimos en Xh Ym") y botón de WhatsApp.
- Config **Admin**: `StoreHours` (7 filas L..D, editable en bloque en la lista) y `StoreConfig` (una fila, checkbox **"Forzar tienda abierta"** para emergencias). Modelos en `store/models.py::221`, migración **0010**.
- Lógica: `store/hours.py` (`is_open`, `seconds_until_open`, `next_open_info`, `schedule_summary`). Zona horaria del negocio: env `BUSINESS_TIMEZONE`, default **`America/Havana`** (`store/config.py`). Soporta tramos nocturnos (cierre < apertura).
- Default sembrado: Lun–Vie 9:00–18:00 · Sáb 9:00–13:00 · Dom cerrado → ajustar por admin (la pantalla cerró en vivo esa misma tarde).
- Tests: `StoreHoursTests` + `StoreClosedMiddlewareTests` (66 en total).

## 9. IMPORTANTE — MIGRACIONES EN WASMER (hallazgo)

- El `migrate` que imprime el deploy es el del **build** (BD efímera) — **NO llega a la MySQL persistente**. El job `after_deploy` con el comando genérico `after_deploy` falla silenciosamente. Por eso el esquema persistente quedó congelado tras la **0007** y las 0008/0009/0010 nunca aplicaban de verdad.
- Solución aplicada: **`roshalys/wsgi.py::_migrate_on_boot()`** ejecuta `manage.py migrate` al arrancar el WSGI contra la BD del runtime (seguro: guardado por `sys.argv`, usa `interactive=False`; MySQL serializa con advisory lock). Además, `app.yaml` ahora pide el job `after_deploy` → `python manage.py migrate --noinput`.
- **Al crear una migración:** tests locales OK → deploy → verificar en vivo (p. ej. tabla nueva o `/categoria/...`). No confiar en el log del build.

## 10. ADMIN Y CONTRASEÑA

- Usuario admin: **admin**. La migración **0011** (`store/migrations/0011_reset_admin_password.py`) fija su contraseña desde el secreto `ADMIN_BOOTSTRAP_PASSWORD` de Wasmer (igual que la 0007). Se aplicó en el deploy del 2026-09-08.
- Cambiar la contraseña: en el admin, /admin/ (menú superior "Cambiar contraseña"). Para resetearla sin acceso: `wasmer app secret update ADMIN_BOOTSTRAP_PASSWORD <nueva>` y re-desplegar (NO re-aplica la 0011 si ya corrió; para forzar, crear migración 0012 igualando el patrón).
- Los secretos de la app (SECRET_KEY, DB_*, ADMIN_BOOTSTRAP_PASSWORD) se gestionan con `wasmer app secret ...`; las variables normales están en `app.yaml`.
- La pantalla de cerrado incluye un enlace discreto "Acceso admin" abajo.

## 11. VENTANA DE DOMICILIO 9:00–18:00 (2026-09-08)

- La tienda puede estar abierta más horas (las define el usuario en admin), pero los **domicilios** solo se admiten entre `StoreConfig.delivery_from` y `delivery_to` (default **09:00–18:00**, editables en el admin, una sola fila `StoreConfig`).
- Decisión del usuario: **Opción 3 — aviso + casilla de aceptación** (NO se bloquea el pedido fuera del horario):
  - El checkout muestra en la tarjeta de entrega "Domicilios: de 09:00 a 18:00".
  - Fuera de la ventana: aviso ámbar + checkbox obligatorio "Entiendo y acepto..."; si se elige domicilio sin marcar la casilla → mensaje de error y no se crea el pedido.
  - Si acepta → el pedido se crea con la nota "Entrega fuera del horario de domicilio: se entregará al día siguiente."
  - `pickup` nunca se bloquea. `force_open` activa también la ventana de domicilio. Soporta tramos nocturnos.
- Código: `store/hours.py::delivery_window()` (usa `next_open_info` → claves `exists`/`label`), `store/forms.py` (`accept_delivery_late`), `store/views.py` (validación + contexto `delivery_window`), `store/templates/store/checkout_delivery.html` (fila `#delivery-late-row` + JS `deliveryOpen`). Migración **0012**.
- Admin: `StoreConfigAdmin.fields = ("force_open", "delivery_from", "delivery_to")`.
- Tests: `DeliveryWindowTests` (6) → **72/72 OK** (la clase `DeliveryAndCostCalculationTests` parchea `store.hours._local_now` al lunes 15:00 para ser determinista; los tests nuevos usan POST `add_to_cart`, NO `session["cart"]` manual — el patrón de sesión manual no persiste en este repo y provoca `302 /cart/`).
- Estado: **DESPLEGADO y verificado en vivo (2026-09-08 ~03:05 UTC)**: el checkout sirve el cartel "Domicilios: de 09:00 a 18:00" y, fuera de la ventana (tienda abierta), el aviso + casilla `accept_delivery_late`. Migración 0012 aplicada en la BD persistente.

## 12. CONTADOR DE VISITAS (2026-09-08)

- Eligen del usuario: **privado (solo panel admin)** y **ambas métricas** (visitas totales + visitantes únicos por día).
- Modelo `DailyStats` (una fila por día: `date` único, `views`, `visitors`, `seen_keys` JSON con hashes de visitante para no duplicar únicos). Migración **0013**.
- `store/visits.py`: `record_visit()` (contar por página) y `visits_summary()` (hoy + totales). El "día" usa la zona horaria del negocio (`_local_now()` de `hours.py`).
- Middleware `VisitCounterMiddleware` (tras `StoreClosedMiddleware`, registrado en settings): cuenta solo respuestas **200** de páginas públicas, **no** cuenta `/admin*`, `/admin-dashboard*`, `/admin-productos*`, `/static*`, `/media*`, `/asistente/`, `/robots.txt`, `/sitemap.xml`, **ni** a usuarios staff.
- Visitante único: hash SHA-256 de (IP de `X-Forwarded-For`/`REMOTE_ADDR` + User-Agent) — sin guardar IPs crudas.
- Dónde se ve: tarjetas "Visitas hoy / Visitantes únicos hoy / Visitas totales / Visitantes únicos totales" en `/admin-dashboard/`, y modelo `DailyStats` en el Django admin (solo lectura, lista por fecha).
- Tests: `VisitCounterTests` (5) → **77 en total**.
- Ojo (trampa de hora real ya corregida): `StoreClosedMiddlewareTests` y `DeliveryAndCostCalculationTests` fijan el reloj (`_local_now`) a horas fijas porque la tienda real cambia el resultado según la hora del día (esta suite fallaba de tarde y pasaba de noche).

## 13. WIDGET DE PAÍSES + ME GUSTA/NO ME GUSTA (2026-09-08)

- Decisiones del usuario (2ª iteración): el panel **no va al final de la página**: se inserta **justo al terminar el listado de productos** (`home.html`, sección `.visits-panel` después de `#catalog`). Debe funcionar **en tiempo real como un contador**: al pulsar 👍/👎 aparece la **bandera del país de la persona** con su **número**; si la bandera ya existe, **se suma 1 al número**.
- Detección de país: **geolocalización desde el navegador** (llamada CORS a `https://ipwho.is/` sin clave, en `home.html` → `fetchCountry()`; fallback a país vacío tras 4s si falla o no hay red). El código de país se envía con el voto (`POST /feedback/` con `country`). El servidor lo valida (2 letras) y si no viene, intenta `store/visits.py::_resolve_country()` (cache `VisitorCountry` por hash de visitante). OJO: en Wasmer **no se puede resolver la IP del cliente en el servidor** (el edge no reenvía `X-Forwarded-For`, el runtime no tiene CA certs: `<urlopen error CERTIFICATE_VERIFY_FAILED>`); por eso la detección es client-side. Además `_geo_lookup()` omite IPs no globales (loopback/privadas) para no meter 4s de timeout por visitante nuevo.
- Contador de banderas: nuevo modelo de datos = el propio `Feedback` ahora guarda `country_code`. `store/visits.py::country_votes()` agrupa los votos con país conocido (orden por total, top 6) y devuelve `[{code, name, count}]`. **Los números SÍ se muestran en público** (cambió la decisión previa de "privado" para el conteo de banderas; las opiniones 👍/👎 globales siguen visibles solo en `/admin-dashboard/` y en el admin).
- En vivo / AJAX:
  - `POST /feedback/` responde `{ok, countries}` con el contador actualizado (incluida la bandera del votante recién resuelta por su navegador).
  - `GET /visitors-countries/` devuelve `{countries}` (JSON, `cache: 'no-store'`) para refresco periódico cada 30s.
  - JS en `home.html`: `renderFlags(list)` reconstruye las banderas (imagen de `flagcdn.com` + badge `.visits-flag-count` con el número); al votar esconde el form y muestra "¡Gracias por tu opinión!".
  - `/feedback/` y `/visitors-countries/` están en `EXCLUDE_EXACT` del middleware de visitas (no inflan el contador).
- Migraciones: **0014** (`Feedback` + `VisitorCountry`), **0015** (`Feedback.country_code`).
- Tests: `VisitorFeedbackTests` (10) → **86 en total** (el de geo parchea `store.visits._geo_lookup`; los POSTs con el Client de Django no exigen token CSRF; el suite mantiene `store.middleware.is_open=True` globalmente).
- NOTA: la suite pasa con o sin internet; la geolocalización real la hace el navegador en producción. El "día" de banderas NO se usa: el contador es **acumulativo** (todas las opiniones con país conocido), no por día.