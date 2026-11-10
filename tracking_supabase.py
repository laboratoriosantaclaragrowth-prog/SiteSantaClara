import json
import os
import re
from concurrent.futures import ThreadPoolExecutor
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class TrackingUnavailable(Exception):
    pass


class SupabaseTracking:
    def __init__(self, url, key):
        if not re.fullmatch(r"https://[a-z0-9-]+\.supabase\.co/?", url):
            raise TrackingUnavailable("Invalid Supabase URL")
        self.url = url.rstrip("/") + "/rest/v1/santa_clara_tracking"
        self.headers = {"apikey": key, "Content-Type": "application/json"}
        if key.startswith("eyJ"):
            self.headers["Authorization"] = f"Bearer {key}"

    def request(self, params, *, record=None, count=False):
        headers = self.headers.copy()
        payload = None
        method = "HEAD" if count else "GET"
        if record is not None:
            method = "POST"
            payload = json.dumps(record).encode("utf-8")
            headers["Prefer"] = "resolution=ignore-duplicates,return=minimal"
        elif count:
            headers["Prefer"] = "count=exact"
        req = Request(f"{self.url}?{urlencode(params)}", payload, headers, method=method)
        try:
            with urlopen(req, timeout=8) as response:
                if count:
                    return int(response.headers["Content-Range"].rsplit("/", 1)[-1])
                return json.load(response) if method == "GET" else None
        except HTTPError as error:
            raise TrackingUnavailable(f"Supabase HTTP {error.code}") from None
        except (URLError, TimeoutError, ValueError, KeyError, AttributeError):
            raise TrackingUnavailable("Supabase response unavailable") from None

    def exists(self, key, kind, session=None):
        params = {"select": "id", "id": f"eq.{key}", "kind": f"eq.{kind}", "limit": 1}
        if session:
            params["session"] = f"eq.{session}"
        return bool(self.request(params))

    def save(self, key, kind, session, data):
        self.request({"on_conflict": "id"}, record=dict(id=key, kind=kind, session=session, data=data))
        return self.exists(key, kind, session)

    def dashboard(self, kind, page, kinds, since=""):
        params = {"select": "created,kind,session,data", "order": "created.desc,id.desc",
                  "limit": 100, "offset": (page - 1) * 100}
        if kind:
            params["kind"] = f"eq.{kind}"
        date_filter = {"created": f"gte.{since}"} if since else {}
        params.update(date_filter)
        with ThreadPoolExecutor(max_workers=4) as pool:
            activity = pool.submit(self.request, params)
            pending_counts = {
                name: pool.submit(self.request, {"select": "id", "kind": f"eq.{name}", "limit": 1,
                                                 **date_filter}, count=True)
                for name in kinds
            }
            pending_counts["whatsapp_click"] = pool.submit(self.request, {
                "select": "id", "kind": "eq.link_click", "limit": 1, **date_filter,
                "or": "(data->>target.like.https://wa.me/*,data->>target.like.https://api.whatsapp.com/*,data->>target.like.https://web.whatsapp.com/*)",
            }, count=True)
            rows = activity.result()
            counts = {name: pending.result() for name, pending in pending_counts.items()}
        return counts, [(row["created"], row["kind"], row["session"], row["data"]) for row in rows]


def configured_supabase():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SECRET_KEY")
    if url or key:
        if not url or not key:
            raise TrackingUnavailable("Incomplete Supabase configuration")
        return SupabaseTracking(url, key)


def load_tracking_env(path):
    names = {"SUPABASE_URL", "SUPABASE_SECRET_KEY", "SANTA_CLARA_ADMIN_PASSWORD", "SANTA_CLARA_GEO_PROXY_TOKEN"}
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        name, sep, value = line.partition("=")
        value = value.strip()
        if len(value) > 1 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if sep and name.strip() in names and value:
            os.environ.setdefault(name.strip(), value)
