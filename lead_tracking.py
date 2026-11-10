import base64
import hmac
import json
import os
import re
import sqlite3
import uuid
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit
from tracking_supabase import configured_supabase
from tracking_metrics import PERIODS, period_start, summarize, supabase_metrics
from admin_dashboard import render_dashboard_html

ROOT = Path(__file__).resolve().parent
PRIVATE = ROOT / ".santa-clara-private"
EVENTS = {"page_view", "link_click", "ebook_popup_view", "ebook_popup_close", "ebook_popup_click"}
UTMS = ("utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term", "utm_id")


def database():
    PRIVATE.mkdir(exist_ok=True)
    db = sqlite3.connect(PRIVATE / "tracking.sqlite3", timeout=10)
    db.execute("""CREATE TABLE IF NOT EXISTS records (
        id TEXT PRIMARY KEY, kind TEXT NOT NULL, session TEXT NOT NULL,
        created TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')), data TEXT NOT NULL
    )""")
    return db


def clipped(value, size=250):
    return value.strip()[:size] if isinstance(value, str) else ""


def path_only(value):
    value = clipped(value)
    return value if value.startswith("/") and not value.startswith("//") and not any(c in value for c in "?#") else ""


def attribution(value):
    value = value if isinstance(value, dict) else {}
    referrer = urlsplit(clipped(value.get("referrer")))
    return {"page": path_only(value.get("page")), "referrer": referrer.hostname or "",
            **{key: clipped(value.get(key)) for key in UTMS}}


def device_type(headers):
    agent = headers.get("User-Agent", "").lower()
    mobile_hint = headers.get("Sec-CH-UA-Mobile")
    if "ipad" in agent or "tablet" in agent or ("android" in agent and "mobile" not in agent):
        return "Tablet"
    if mobile_hint == "?1" or any(token in agent for token in ("mobile", "iphone", "ipod", "windows phone")):
        return "Celular"
    if mobile_hint == "?0" or any(token in agent for token in ("windows", "macintosh", "linux", "cros")):
        return "Computador"
    return ""


def trusted_location(headers):
    secret = os.environ.get("SANTA_CLARA_GEO_PROXY_TOKEN")
    supplied = headers.get("X-Santa-Clara-Geo-Token", "")
    if not secret or not hmac.compare_digest(secret.encode(), supplied.encode()):
        return {}
    return {field: clipped(unquote(headers.get(f"X-Santa-Clara-{header}", "")), 100)
            for field, header in (("city", "City"), ("neighborhood", "Neighborhood"))}


def analytics_consent(item, headers):
    if item.get("analyticsConsent") != "v1" or headers.get("Sec-GPC") == "1" or headers.get("DNT") == "1":
        return None
    try:
        accepted = datetime.fromisoformat(clipped(item.get("analyticsConsentAt"), 40))
    except ValueError:
        return None
    if accepted.tzinfo is None:
        return None
    age = datetime.now(timezone.utc) - accepted
    if timedelta(minutes=-5) <= age < timedelta(days=30):
        return accepted.astimezone(timezone.utc).isoformat()
    return None


class LeadTracking:
    require_supabase = False

    def response(self, status, content, mime="application/json", headers=()):
        if mime == "application/json":
            content = json.dumps(content, ensure_ascii=False)
        body = content.encode("utf-8") if isinstance(content, str) else content
        self.send_response(status)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for key, value in headers:
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def handle_tracking_post(self):
        path = urlsplit(self.path).path
        if path not in ("/api/events", "/api/ebook-leads"):
            return self.send_error(404)
        origin = self.headers.get("Origin")
        host = self.headers.get("Host")
        if origin and origin not in (f"http://{host}", f"https://{host}"):
            return self.response(403, {"error": "Origem inválida."})
        if self.headers.get_content_type() != "application/json":
            return self.response(415, {"error": "Formato inválido."})
        try:
            length = int(self.headers.get("Content-Length", 0))
            if not 0 < length <= 8192:
                raise ValueError
            item = json.loads(self.rfile.read(length))
            if not isinstance(item, dict):
                raise ValueError
            key = str(uuid.UUID(item.get("id", "")))
            session = str(uuid.UUID(item.get("session", "")))
            consent_at = analytics_consent(item, self.headers)
            if path == "/api/events" and not consent_at:
                return self.response(403, {"error": "Análise de audiência não autorizada."})
            data = {"current": attribution(item.get("current") if consent_at else None),
                    "entry": attribution(item.get("entry") if consent_at else None)}
            if consent_at:
                data.update(analytics_consent_version="v1", analytics_consent_at=consent_at)
            if path == "/api/ebook-leads":
                kind = "ebook_lead"
                name, email, phone = (clipped(item.get(key), size) for key, size in (
                    ("name", 80), ("email", 254), ("phone", 30)))
                if not name or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
                    return self.response(400, {"error": "Informe seu primeiro nome e um e-mail válido."})
                if phone and (not re.fullmatch(r"[+\d ()-]+", phone) or not 10 <= len(re.sub(r"\D", "", phone)) <= 15):
                    return self.response(400, {"error": "Confira o número de WhatsApp informado."})
                data.update(name=name, email=email, phone=phone, marketing=item.get("marketing") is True,
                            consent_version="ebook-v1")
            else:
                kind = clipped(item.get("event"), 40)
                if kind not in EVENTS:
                    raise ValueError
                data.update(target=clipped(item.get("target")), reason=clipped(item.get("reason"), 20))
                if kind == "page_view":
                    visitor = clipped(item.get("visitorId"), 40)
                    try:
                        data["visitor_id"] = str(uuid.UUID(visitor))
                    except ValueError:
                        pass
                    data.update(device=device_type(self.headers), **trusted_location(self.headers))
        except (ValueError, TypeError, AttributeError):
            return self.response(400, {"error": "Dados inválidos."})

        supabase = configured_supabase(required=self.require_supabase)
        download = self.ebook_registration_url(key, supabase) if kind == "ebook_lead" else None
        if supabase:
            saved = supabase.save(key, kind, session, data)
        else:
            with closing(database()) as db, db:
                db.execute("INSERT OR IGNORE INTO records(id,kind,session,data) VALUES (?,?,?,?)",
                           (key, kind, session, json.dumps(data, ensure_ascii=False)))
                saved = db.execute("SELECT 1 FROM records WHERE id=? AND kind=? AND session=?",
                                   (key, kind, session)).fetchone()
        if not saved:
            return self.response(409, {"error": "Não foi possível registrar a solicitação."})
        self.response(200, {"download": download} if download else {"ok": True})

    def ebook_registration_url(self, key, supabase):
        return f"/api/ebook?id={key}"

    def respond_ebook(self, supabase):
        self.response(200, (ROOT / "assets/ebook-santa-clara.pdf").read_bytes(), "application/pdf",
                      [("Content-Disposition", 'inline; filename="ebook-santa-clara.pdf"')])

    def handle_tracking_get(self):
        url = urlsplit(self.path)
        if url.path == "/api/ebook":
            key = parse_qs(url.query).get("id", [""])[0]
            supabase = configured_supabase(required=self.require_supabase)
            if not re.fullmatch(r"[a-f0-9-]{36}", key):
                found = False
            elif supabase:
                found = supabase.exists(key, "ebook_lead")
            else:
                with closing(database()) as db:
                    found = db.execute("SELECT 1 FROM records WHERE id=? AND kind='ebook_lead'", (key,)).fetchone()
            if not found:
                self.response(404, {"error": "Preencha o formulário para acessar o e-book."})
            else:
                self.respond_ebook(supabase)
            return True
        if url.path not in ("/admin", "/admin/"):
            return False
        password = os.environ.get("SANTA_CLARA_ADMIN_PASSWORD")
        if not password:
            self.response(503, "Configure a senha do painel no servidor.", "text/plain; charset=utf-8")
            return True
        token = base64.b64encode(f"admin:{password}".encode()).decode()
        supplied = self.headers.get("Authorization", "")
        if not hmac.compare_digest(supplied.encode(), f"Basic {token}".encode()):
            self.response(401, "Acesso restrito", "text/plain; charset=utf-8",
                          [("WWW-Authenticate", 'Basic realm="Santa Clara"')])
            return True
        self.render_dashboard(url)
        return True

    def render_dashboard(self, url):
        query = parse_qs(url.query)
        period = query.get("periodo", ["7d"])[0]
        if period not in PERIODS:
            period = "7d"
        since = period_start(period)
        kind = query.get("tipo", [""])[0]
        if kind not in EVENTS | {"ebook_lead"}:
            kind = ""
        raw_page = query.get("pagina", ["1"])[0]
        page = max(1, int(raw_page)) if re.fullmatch(r"\d{1,8}", raw_page) else 1
        supabase = configured_supabase(required=self.require_supabase)
        if supabase:
            counts, rows = supabase.dashboard(kind, page, sorted(EVENTS | {"ebook_lead"}), since)
            metrics = supabase_metrics(supabase, since)
        else:
            with closing(database()) as db:
                counts = dict(db.execute("SELECT kind, COUNT(*) FROM records WHERE created >= ? GROUP BY kind",
                                         (since,)))
                counts["whatsapp_click"] = db.execute("""SELECT COUNT(*) FROM records
                    WHERE created >= ? AND kind = 'link_click' AND (
                        json_extract(data, '$.target') LIKE 'https://wa.me/%'
                        OR json_extract(data, '$.target') LIKE 'https://api.whatsapp.com/%'
                        OR json_extract(data, '$.target') LIKE 'https://web.whatsapp.com/%'
                    )""", (since,)).fetchone()[0]
                rows = db.execute("""SELECT created, kind, session, data FROM records
                    WHERE created >= ? AND (?='' OR kind=?) ORDER BY created DESC, rowid DESC LIMIT 100 OFFSET ?""",
                                  (since, kind, kind, (page - 1) * 100)).fetchall()
                metrics = summarize(db.execute("""SELECT created, session, data FROM records
                    WHERE kind='page_view' AND created >= ?""", (since,)))
        labels = {"ebook_lead": "Cadastros", "page_view": "Páginas vistas", "link_click": "Cliques em links",
                  "ebook_popup_view": "Pop-ups vistos", "ebook_popup_click": "Envios iniciados",
                  "ebook_popup_close": "Pop-ups fechados"}
        markup = render_dashboard_html(counts=counts, rows=rows, kind=kind, page=page,
                                       labels=labels, metrics=metrics, period=period)
        self.response(200, markup, "text/html; charset=utf-8")
