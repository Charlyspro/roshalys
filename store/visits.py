import hashlib
import ipaddress
import json
import logging
from urllib.error import URLError
from urllib.request import Request, urlopen

from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.db.models import Count, Sum

from store.hours import _local_now
from store.models import DailyStats, Feedback, VisitorCountry

logger = logging.getLogger("store")

EXCLUDE_EXACT = ("/robots.txt", "/sitemap.xml", "/feedback/", "/visitors-countries/")
EXCLUDE_PREFIXES = (
    "/admin/",
    "/static/",
    "/media/",
    "/admin-dashboard/",
    "/admin-productos/",
    "/asistente/",
)

# Nombres de países comunes (para tooltip); si no está, se usa el código ISO.
COUNTRY_NAMES = {
    "AR": "Argentina", "BO": "Bolivia", "BR": "Brasil", "CA": "Canadá", "CL": "Chile",
    "CO": "Colombia", "CR": "Costa Rica", "CU": "Cuba", "DO": "Rep. Dominicana",
    "EC": "Ecuador", "ES": "España", "GT": "Guatemala", "HN": "Honduras",
    "MX": "México", "NI": "Nicaragua", "PA": "Panamá", "PE": "Perú",
    "PR": "Puerto Rico", "PY": "Paraguay", "SV": "El Salvador", "US": "Estados Unidos",
    "UY": "Uruguay", "VE": "Venezuela", "DE": "Alemania", "FR": "Francia",
    "GB": "Reino Unido", "IT": "Italia", "PT": "Portugal", "RU": "Rusia",
    "CN": "China", "JP": "Japón", "IN": "India",
}


def _should_count(path):
    if path in EXCLUDE_EXACT:
        return False
    return not any(path.startswith(prefix) for prefix in EXCLUDE_PREFIXES)


def _visitor_key(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    ip = (forwarded.split(",")[0].strip() if forwarded else "") or request.META.get("REMOTE_ADDR", "")
    user_agent = request.META.get("HTTP_USER_AGENT", "")[:128]
    return hashlib.sha256(f"{ip}|{user_agent}".encode("utf-8")).hexdigest()


def record_visit(request):
    if not _should_count(request.path):
        return
    today = _local_now().date()
    key = _visitor_key(request)
    ip = _client_ip(request)
    with transaction.atomic():
        row, _created = DailyStats.objects.get_or_create(
            date=today,
            defaults={"views": 0, "visitors": 0, "seen_keys": "[]"},
        )
        try:
            locked = DailyStats.objects.select_for_update().get(pk=row.pk)
        except ObjectDoesNotExist:
            locked = row
        seen = json.loads(locked.seen_keys or "[]")
        if key not in seen:
            seen.append(key)
            locked.visitors += 1
            locked.seen_keys = json.dumps(seen)
            _resolve_country(key, ip)
        locked.views += 1
        locked.save()


def _client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


def _resolve_country(key, ip):
    try:
        vc = VisitorCountry.objects.get(ip_hash=key)
        return vc.country_code
    except ObjectDoesNotExist:
        pass
    code = _geo_lookup(ip)
    VisitorCountry.objects.update_or_create(ip_hash=key, defaults={"country_code": code})
    return code


def _geo_lookup(ip):
    if not ip:
        logger.info("GeoIP: sin IP")
        return ""
    try:
        if not ipaddress.ip_address(ip).is_global:
            logger.info("GeoIP %s: IP no global, se omite", ip)
            return ""
    except ValueError:
        return ""
    try:
        req = Request("https://ipwho.is/" + ip, headers={"User-Agent": "roshalys/1.0"})
        with urlopen(req, timeout=4) as response:
            data = json.loads(response.read().decode("utf-8"))
        if not data.get("success"):
            logger.info("GeoIP %s no exitoso: %s", ip, json.dumps(data)[:160])
            return ""
        code = data.get("country_code", "") or ""
        logger.info("GeoIP %s -> %s", ip, code)
        return code
    except (OSError, URLError, ValueError, json.JSONDecodeError) as error:
        logger.warning("GeoIP no disponible para %s: %s", ip, error)
        return ""



def visits_summary():
    today = _local_now().date()
    totals = DailyStats.objects.aggregate(
        total_views=Sum("views"),
        total_visitors=Sum("visitors"),
    )
    try:
        day = DailyStats.objects.get(date=today)
    except ObjectDoesNotExist:
        day = None
    return {
        "today_views": day.views if day else 0,
        "today_visitors": day.visitors if day else 0,
        "total_views": totals["total_views"] or 0,
        "total_visitors": totals["total_visitors"] or 0,
    }


def country_votes():
    """Contador de banderas en vivo: países ordenados por número de opiniones."""
    rows = (
        Feedback.objects.exclude(country_code="")
        .values("country_code")
        .annotate(total=Count("id"))
        .order_by("-total", "country_code")[:6]
    )
    return [
        {"code": row["country_code"], "name": COUNTRY_NAMES.get(row["country_code"], row["country_code"]), "count": row["total"]}
        for row in rows
    ]