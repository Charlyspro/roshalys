import datetime
from zoneinfo import ZoneInfo

from django.utils import timezone

from store import config
from store.models import StoreConfig, StoreHours

DAY_NAMES = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]


def _local_now(now=None):
    if now is None:
        now = timezone.now()
    if now.tzinfo is None or now.utcoffset() is None:
        now = timezone.make_aware(now, timezone.get_current_timezone())
    return now.astimezone(ZoneInfo(config.BUSINESS_TIMEZONE))


def is_force_open():
    return StoreConfig.get_solo().force_open


def get_schedule():
    return {hours.day: hours for hours in StoreHours.objects.all()}


def is_open(now=None):
    local = _local_now(now)
    if is_force_open():
        return True
    rows = get_schedule()
    current = local.time()

    row = rows.get(local.weekday())
    if row is not None and not row.is_closed and row.open_time is not None:
        if row.close_time is None:
            if current >= row.open_time:
                return True
        elif row.close_time > row.open_time:
            if row.open_time <= current < row.close_time:
                return True
        elif current >= row.open_time or current < row.close_time:
            return True

    prev = rows.get((local.weekday() - 1) % 7)
    if prev is not None and not prev.is_closed and prev.open_time is not None and prev.close_time is not None:
        if prev.close_time < prev.open_time and current < prev.close_time:
            return True

    return False


def _next_open_instant(local, max_days=8):
    rows = get_schedule()
    for days_ahead in range(max_days + 1):
        row = rows.get((local.weekday() + days_ahead) % 7)
        if row is None or row.is_closed or row.open_time is None:
            continue
        candidate = local + datetime.timedelta(days=days_ahead)
        instant = candidate.replace(
            hour=row.open_time.hour,
            minute=row.open_time.minute,
            second=0,
            microsecond=0,
        )
        if instant > local:
            return instant
    return None


def seconds_until_open(now=None):
    local = _local_now(now)
    if is_open(local):
        return 0
    instant = _next_open_instant(local)
    if instant is None:
        return None
    return int((instant - local).total_seconds())


def next_open_info(now=None):
    local = _local_now(now)
    instant = _next_open_instant(local)
    if instant is None:
        return {"exists": False, "label": None, "time": None, "weekday": None}
    if instant.date() == local.date():
        prefix = "Hoy"
    elif instant.date() == (local + datetime.timedelta(days=1)).date():
        prefix = "Mañana"
    else:
        prefix = DAY_NAMES[instant.weekday()]
    return {
        "exists": True,
        "label": f"{prefix} a las {instant:%H:%M}",
        "time": f"{instant:%H:%M}",
        "weekday": DAY_NAMES[instant.weekday()],
    }


def _days_label(days):
    if not days:
        return ""
    seq = sorted(days)
    ranges = []
    start = prev = seq[0]
    for day in seq[1:]:
        if day == prev + 1:
            prev = day
        else:
            ranges.append((start, prev))
            start = prev = day
    ranges.append((start, prev))
    labels = []
    for first, last in ranges:
        if first == last:
            labels.append(DAY_NAMES[first])
        else:
            labels.append(f"{DAY_NAMES[first]} a {DAY_NAMES[last]}")
    return ", ".join(labels)


def schedule_summary():
    rows = list(StoreHours.objects.order_by("day"))
    if not rows:
        return "Consulte nuestro horario"
    groups = []
    current = None
    for row in rows:
        if row.is_closed or row.open_time is None or row.close_time is None:
            if current is not None:
                groups.append(current)
                current = None
            continue
        fmt = f"{row.open_time:%H:%M}–{row.close_time:%H:%M}"
        if current is not None and current["fmt"] == fmt:
            current["days"].append(row.day)
        else:
            if current is not None:
                groups.append(current)
            current = {"fmt": fmt, "days": [row.day]}
    if current is not None:
        groups.append(current)

    parts = [f"{_days_label(group['days'])}: {group['fmt']} h" for group in groups]

    closed_days = [row.day for row in rows if row.is_closed or row.open_time is None]
    if closed_days:
        parts.append(f"{_days_label(closed_days)}: cerrado")

    return " · ".join(parts) or "Consulte nuestro horario"


def delivery_window(now=None):
    """Ventana fija de envíos a domicilio (StoreConfig.delivery_from/to).

    Devuelve {"active": bool, "hours_text": str, "resume_label": str|None}.
    - force_open: el negocio está entregando, la ventana no se aplica.
    - Si la tienda está cerrada tampoco hay domicilio (nadie entrega).
    """
    cfg = StoreConfig.get_solo()
    start, end = cfg.delivery_from, cfg.delivery_to
    hours_text = f"{start:%H:%M} a {end:%H:%M}"

    if cfg.force_open:
        return {"active": True, "hours_text": hours_text, "resume_label": None}

    local = _local_now(now)
    if not is_open(local):
        return {
            "active": False,
            "hours_text": hours_text,
            "resume_label": _next_delivery_label(next_open_info(local), start),
        }

    current = local.time()
    if end > start:
        within = start <= current < end
    else:
        within = current >= start or current < end

    return {
        "active": within,
        "hours_text": hours_text,
        "resume_label": None if within else _next_delivery_label(next_open_info(local), start),
    }


def _next_delivery_label(info, delivery_from):
    if not info.get("exists"):
        return "en nuestro próximo día de entrega"
    prefix = info["label"].rsplit(" a las", 1)[0]
    return f"{prefix} a las {delivery_from:%H:%M}"