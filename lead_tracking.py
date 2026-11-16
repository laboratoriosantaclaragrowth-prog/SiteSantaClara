import time
import hmac
import json
import os
import re
import sqlite3
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit
from tracking_supabase import TrackingUnavailable, configured_supabase
import admin_painel

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


def visitor_location(headers):
    """Cidade da visita. Na Vercel os cabeçalhos x-vercel-ip-* são preenchidos pela própria Vercel."""
    location = {}
    if os.environ.get("VERCEL") == "1":
        for field, header, size in (("city", "X-Vercel-IP-City", 80), ("region", "X-Vercel-IP-Country-Region", 80),
                                    ("country", "X-Vercel-IP-Country", 60)):
            value = clipped(unquote(headers.get(header, "")), size)
            if value:
                location[field] = value
    proxy = trusted_location(headers)
    if proxy.get("city"):
        location["city"] = proxy["city"]
    return location


BOT = re.compile(r"bot|crawl|spider|slurp|preview|lighthouse|headless|facebookexternalhit|whatsapp|bingpreview|pingdom|uptime", re.I)
TRACK_EVENTS = {"pageview", "page_time", "section_view", "section_time", "click", "ebook_open", "ebook_close", "ebook_submit"}
TRACK_TARGETS = {"whatsapp", "phone", "maps", "email", "internal", "external", "button", "download"}
SESSION_FIELDS = {
    "landing_page": 300, "page": 300, "referrer": 500, "referrer_host": 200, "utm_source": 120, "utm_medium": 120,
    "utm_campaign": 200, "utm_term": 200, "utm_content": 200, "gclid": 200, "device": 20, "os": 40, "browser": 40,
    "screen": 20, "language": 20, "timezone": 60,
}


def clean_track_batch(item):
    """Valida o lote do rastreador do site. Retorna None se estiver malformado."""
    session = item.get("session")
    events = item.get("events", [])
    if not isinstance(session, dict) or not isinstance(events, list):
        return None
    try:
        clean = {"id": str(uuid.UUID(clipped(session.get("id"), 40))),
                 "visitor_id": str(uuid.UUID(clipped(session.get("visitor_id"), 40)))}
    except ValueError:
        return None
    # Campos vazios ficam de fora (viram nulo no banco), senão "gclid vazio" contaria como anúncio.
    clean.update({key: value for key, size in SESSION_FIELDS.items() if (value := clipped(session.get(key), size))})
    for key in ("landing_page", "page"):
        clean[key] = path_only(clean.get(key, "")) or "/"
    for key, top in (("active_seconds", 14400), ("max_scroll", 100)):
        value = session.get(key)
        valid = isinstance(value, (int, float)) and not isinstance(value, bool)
        clean[key] = min(max(int(value), 0), top) if valid else 0
    clean["is_returning"] = session.get("is_returning") is True
    cleaned_events = []
    for event in events[:200]:
        if not isinstance(event, dict) or event.get("type") not in TRACK_EVENTS:
            continue
        value = event.get("value")
        cleaned_events.append({
            "type": event["type"], "page": path_only(clipped(event.get("page"), 300)) or "/",
            "section": clipped(event.get("section"), 60), "label": clipped(event.get("label"), 120),
            "target": event.get("target") if event.get("target") in TRACK_TARGETS else "",
            "href": clipped(event.get("href"), 300), "ts": clipped(event.get("ts"), 40),
            "value": value if isinstance(value, (int, float)) and not isinstance(value, bool) else None,
        })
    return {"first": item.get("first") is True, "session": clean, "events": cleaned_events}


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
        if path in ("/admin/login", "/admin/logout"):
            return self.handle_admin_post(path)
        if path == "/api/track":
            return self.handle_track_post()
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
                            consent_version="ebook-v1",
                            is_test=admin_painel.is_test_visit(self.headers.get("Host"), self.headers.get("Cookie")))
                if consent_at:
                    # Liga o cadastro à visita no painel (só com a análise autorizada).
                    for field, source in (("visitor_id", "visitorId"), ("track_session", "trackSession")):
                        try:
                            data[field] = str(uuid.UUID(clipped(item.get(source), 40)))
                        except ValueError:
                            pass
                    data.update(device=device_type(self.headers), **visitor_location(self.headers))
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
        if url.path in ("/admin", "/admin/", "/admin/leads.csv"):
            self.handle_admin_get(url)
            return True
        return False

    # ------------------------------------------------------------ painel do site

    def send_empty(self, status=204, headers=()):
        self.send_response(status)
        self.send_header("Content-Length", "0")
        self.send_header("Cache-Control", "no-store")
        for key, value in headers:
            self.send_header(key, value)
        self.end_headers()

    def same_origin(self):
        origin = self.headers.get("Origin")
        host = self.headers.get("Host")
        if origin == "null":
            # Com "Referrer-Policy: no-referrer" o Chrome manda Origin "null" no formulário.
            # Sec-Fetch-Site é preenchido pelo próprio navegador e não pode ser forjado por outra página.
            return self.headers.get("Sec-Fetch-Site") == "same-origin"
        return not origin or origin in (f"http://{host}", f"https://{host}")

    def handle_track_post(self):
        if not self.same_origin():
            return self.send_empty(403)
        if BOT.search(self.headers.get("User-Agent") or "bot"):
            return self.send_empty()
        try:
            length = int(self.headers.get("Content-Length", 0))
            if not 0 < length <= 64000:
                raise ValueError
            item = json.loads(self.rfile.read(length))
            if not isinstance(item, dict):
                raise ValueError
        except (ValueError, TypeError):
            return self.send_empty(400)
        if not analytics_consent(item, self.headers):
            return self.send_empty(403)
        batch = clean_track_batch(item)
        if batch is None:
            return self.send_empty(400)
        host = self.headers.get("Host")
        batch["session"]["hostname"] = admin_painel.host_name(host)
        batch["session"]["is_test"] = admin_painel.is_test_visit(host, self.headers.get("Cookie"))
        if batch["first"]:
            batch["session"].update(visitor_location(self.headers))
        supabase = configured_supabase(required=self.require_supabase)
        if supabase:
            try:
                supabase.rpc("sc_track_batch", {"p": batch})
            except TrackingUnavailable as error:
                self.log_error("track: %s", error)
        self.send_empty()

    def handle_admin_post(self, path):
        if not self.same_origin():
            return self.send_empty(403)
        if path == "/admin/logout":
            return self.send_empty(303, [("Location", "/admin"),
                                         ("Set-Cookie", admin_painel.session_cookie(self.headers.get("Host")))])
        try:
            length = int(self.headers.get("Content-Length", 0))
            form = parse_qs(self.rfile.read(length).decode("utf-8")) if 0 < length <= 2048 else {}
        except (ValueError, UnicodeDecodeError):
            form = {}
        time.sleep(0.4)  # dificulta tentativa e erro
        if not admin_painel.check_password(form.get("password", [""])[0]):
            return self.send_empty(303, [("Location", "/admin?erro=1")])
        cookie = admin_painel.session_cookie(self.headers.get("Host"), admin_painel.create_token())
        self.send_empty(303, [("Location", "/admin"), ("Set-Cookie", cookie)])

    def handle_admin_get(self, url):
        query = parse_qs(url.query)
        html = "text/html; charset=utf-8"
        private = [("X-Frame-Options", "DENY")]
        if not admin_painel.verify_token(admin_painel.cookie_token(self.headers.get("Cookie"))):
            if url.path == "/admin/leads.csv":
                return self.send_empty(303, [("Location", "/admin")])
            return self.response(200, admin_painel.render_login(error="erro" in query), html, private)
        supabase = configured_supabase()
        if not supabase:
            return self.response(503, admin_painel.render_message(
                "Falta conectar o Supabase",
                "Preencha <code>SUPABASE_URL</code> e <code>SUPABASE_SECRET_KEY</code> no servidor."), html, private)
        include_test = query.get("t", [""])[0] == "1"
        if url.path == "/admin/leads.csv":
            params = [("select", "created_at,name,email,phone,page,utm_source,utm_medium,utm_campaign,device,city,region"),
                      ("order", "created_at.desc"), ("limit", "10000")]
            if not include_test:
                params.append(("is_test", "eq.false"))
            try:
                rows = supabase.call("sc_leads", params)
            except TrackingUnavailable as error:
                self.log_error("leads: %s", error)
                return self.response(503, admin_painel.render_message("Erro ao baixar", "Tente novamente em instantes."),
                                     html, private)
            disposition = "attachment; filename*=UTF-8''" + admin_painel.leads_filename()
            return self.response(200, admin_painel.leads_csv(rows), "text/csv; charset=utf-8",
                                 [("Content-Disposition", disposition)])
        preset = query.get("p", [""])[0]
        month = query.get("m", [""])[0]
        period = admin_painel.resolve_period(preset, month)
        start, end = period["from"], period["to"]
        previous = start - (end - start)
        args = {"p_from": admin_painel.iso(start), "p_to": admin_painel.iso(end), "p_include_test": include_test}
        lead_params = [("select", "created_at,name,email,phone,page,utm_source,utm_campaign,city,region,device"),
                       ("created_at", f"gte.{args['p_from']}"), ("created_at", f"lt.{args['p_to']}"),
                       ("order", "created_at.desc"), ("limit", "200")]
        if not include_test:
            lead_params.append(("is_test", "eq.false"))

        def optional(call):
            try:
                return call.result()
            except TrackingUnavailable:
                return None

        with ThreadPoolExecutor(max_workers=5) as pool:
            dash = pool.submit(supabase.rpc, "sc_admin_dashboard", args)
            prev = pool.submit(supabase.rpc, "sc_admin_dashboard",
                               {**args, "p_from": admin_painel.iso(previous), "p_to": args["p_from"]})
            leads = pool.submit(supabase.call, "sc_leads", lead_params)
            visitors = pool.submit(supabase.rpc, "sc_admin_visitors", args)
            keywords = pool.submit(supabase.rpc, "sc_admin_keywords", args)
            try:
                dash_data = dash.result()
            except TrackingUnavailable as error:
                self.log_error("painel: %s", error)
                missing = "404" in str(error) or "sc_" in str(error)
                text = ("Falta criar as tabelas do painel. Abra o Supabase, vá em SQL Editor, New query, cole o arquivo "
                        "<code>supabase_painel.sql</code> e clique em Run." if missing else "Tente novamente em instantes.")
                return self.response(503, admin_painel.render_message("Erro ao carregar o painel", text), html, private)
            markup = admin_painel.render_dashboard(
                dash=dash_data, prev=optional(prev), leads=optional(leads) or [], visitors=optional(visitors),
                keywords=optional(keywords), period=period, include_test=include_test, preset=preset, month=month)
        self.response(200, markup, html, private)
