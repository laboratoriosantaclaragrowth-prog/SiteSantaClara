"""Local-only preview server for the Santa Clara homepage."""
import argparse
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
from lead_tracking import LeadTracking
from tracking_supabase import TrackingUnavailable, load_tracking_env

ROOT = Path(__file__).resolve().parent
PUBLIC_FILES = {
    "index.html", "logo.png", "hero.png", "santa-clara.css",
    "informational.js", "site-config.js", "robots.txt", "sitemap.xml", "llms.txt",
}


class Handler(LeadTracking, SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def allowed(self):
        path = urlsplit(self.path).path
        target = Path(self.translate_path(path)).resolve()
        if not target.is_relative_to(ROOT):
            return False
        relative = target.relative_to(ROOT)
        if relative.as_posix() == "assets/ebook-santa-clara.pdf":
            return False
        if relative.parts and relative.parts[0] in {"blog", "contato", "exames", "santa-clara-ate-voce"}:
            return (target.is_file() and target.suffix == ".html") or (target.is_dir() and (target / "index.html").is_file())
        return path == "/" or (
            target.is_file() and (
                relative.as_posix() in PUBLIC_FILES
                or relative.parts[0] == "assets"
            )
        )

    def do_GET(self):
        try:
            if self.handle_tracking_get():
                return
        except TrackingUnavailable as error:
            self.log_error("%s", error)
            return self.response(503, {"error": "Banco de dados temporariamente indisponível."})
        if self.allowed():
            super().do_GET()
        else:
            self.send_error(404)

    def do_HEAD(self):
        if self.allowed():
            super().do_HEAD()
        else:
            self.send_error(404)

    def do_POST(self):
        try:
            self.handle_tracking_post()
        except TrackingUnavailable as error:
            self.log_error("%s", error)
            self.response(503, {"error": "Não foi possível salvar agora. Tente novamente."})

    def end_headers(self):
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Robots-Tag", "noindex, nofollow")
        super().end_headers()


if __name__ == "__main__":
    load_tracking_env(ROOT / ".env")
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=5174)
    args = parser.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"Santa Clara: http://localhost:{args.port}/", flush=True)
    server.serve_forever()
