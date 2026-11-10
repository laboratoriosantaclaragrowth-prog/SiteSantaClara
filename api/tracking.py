from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlsplit

from lead_tracking import LeadTracking
from tracking_supabase import TrackingUnavailable


PATHS = {
    "ebook-leads": "/api/ebook-leads",
    "ebook": "/api/ebook",
    "events": "/api/events",
    "admin": "/admin",
}


class handler(LeadTracking, BaseHTTPRequestHandler):
    require_supabase = True

    def tracking_path(self):
        url = urlsplit(self.path)
        path = url.path.rstrip("/")
        if path == "/ebook":
            path = PATHS["ebook"]
        if path == "/api/tracking":
            actions = parse_qs(url.query).get("sc_action", [])
            path = PATHS.get(actions[0], "") if len(actions) == 1 else ""
        self.path = f"{path}?{url.query}" if url.query else path
        return path

    def do_GET(self):
        path = self.tracking_path()
        if path not in {PATHS["ebook"], PATHS["admin"]}:
            return self.response(404, {"error": "Página não encontrada."})
        try:
            self.handle_tracking_get()
        except TrackingUnavailable as error:
            self.log_error("%s", error)
            self.response(503, {"error": "Serviço temporariamente indisponível. Tente novamente."})

    def do_POST(self):
        path = self.tracking_path()
        if path not in {PATHS["ebook-leads"], PATHS["events"]}:
            return self.response(404, {"error": "Página não encontrada."})
        try:
            self.handle_tracking_post()
        except TrackingUnavailable as error:
            self.log_error("%s", error)
            self.response(503, {"error": "Não foi possível concluir agora. Tente novamente."})

    def ebook_registration_url(self, key, supabase):
        supabase.ebook_download_url()
        return f"/ebook?id={key}"

    def respond_ebook(self, supabase):
        self.response(200, supabase.ebook_pdf(), "application/pdf",
                      [("Content-Disposition", 'inline; filename="ebook-santa-clara.pdf"')])

    def end_headers(self):
        self.send_header("X-Robots-Tag", "noindex, nofollow")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        super().end_headers()
