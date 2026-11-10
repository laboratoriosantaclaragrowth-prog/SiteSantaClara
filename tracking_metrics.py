import json
from collections import Counter
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from tracking_supabase import TrackingUnavailable


UNKNOWN = "Não identificado"
PERIODS = {"hoje": "Hoje", "7d": "Últimos 7 dias", "30d": "Últimos 30 dias",
           "mes": "Este mês", "todos": "Todo o histórico"}
try:
    SAO_PAULO = ZoneInfo("America/Sao_Paulo")
except ZoneInfoNotFoundError:
    # Windows without tzdata. The site's records start after daylight saving ended.
    SAO_PAULO = timezone(timedelta(hours=-3))


def period_start(period):
    if period == "todos":
        return ""
    today = datetime.now(SAO_PAULO).replace(hour=0, minute=0, second=0, microsecond=0)
    if period == "mes":
        start = today.replace(day=1)
    else:
        start = today - timedelta(days={"hoje": 0, "7d": 6, "30d": 29}[period])
    return start.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def summarize(rows):
    """Summarize page-view rows (created, session, data) in one pass."""
    visitors = set()
    sessions = set()
    hours = [0] * 24
    devices = Counter()
    cities = Counter()
    neighborhoods = Counter()
    views = identified_views = 0

    for created, session, raw in rows:
        data = json.loads(raw) if isinstance(raw, str) else raw
        views += 1
        if visitor := data.get("visitor_id"):
            visitors.add(visitor)
            identified_views += 1
        if session:
            sessions.add(session)
        timestamp = datetime.fromisoformat(created)
        hours[timestamp.astimezone(SAO_PAULO).hour] += 1
        devices[data.get("device") or UNKNOWN] += 1
        cities[data.get("city") or UNKNOWN] += 1
        neighborhoods[data.get("neighborhood") or UNKNOWN] += 1

    return {
        "views": views,
        "identified_views": identified_views,
        "visitors": len(visitors),
        "sessions": len(sessions),
        "hours": hours,
        "devices": dict(devices),
        "cities": dict(cities),
        "neighborhoods": dict(neighborhoods),
    }


def projected_views(db, since=""):
    """Fallback before the RPC is installed. Fetch only page-view metadata."""
    params = {
        "select": "id,created,session,visitor_id:data->>visitor_id,device:data->>device,city:data->>city,neighborhood:data->>neighborhood",
        "kind": "eq.page_view",
        "order": "id.asc",
        "limit": 500,
        "created": f"lte.{datetime.now(timezone.utc).isoformat()}",
    }
    if since:
        upper = params.pop("created")
        params["and"] = f"(created.gte.{since},created.{upper})"
    while rows := db.request(params):
        for row in rows:
            yield row["created"], row["session"], row
        params["id"] = f"gt.{rows[-1]['id']}"


def supabase_metrics(db, since=""):
    """Use a server-side aggregation when available and otherwise scan metadata."""
    if since:
        return summarize(projected_views(db, since))
    url = db.url.rsplit("/", 1)[0] + "/rpc/santa_clara_dashboard_metrics"
    request = Request(url, headers=db.headers, method="GET")
    try:
        with urlopen(request, timeout=8) as response:
            return json.load(response)
    except HTTPError as error:
        if error.code != 404:
            raise TrackingUnavailable(f"Supabase metrics HTTP {error.code}") from None
    except (URLError, TimeoutError, ValueError):
        raise TrackingUnavailable("Supabase metrics unavailable") from None
    return summarize(projected_views(db))
