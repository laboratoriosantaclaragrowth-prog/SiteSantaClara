import json
import os
import threading
import unittest
import uuid
from datetime import datetime, timezone
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from unittest.mock import patch

import admin_painel
from api.tracking import handler
from lead_tracking import clean_track_batch


class QuietHandler(handler):
    def log_message(self, *args):
        pass


def batch(**session):
    return {
        "first": True, "analyticsConsent": "v1", "analyticsConsentAt": datetime.now(timezone.utc).isoformat(),
        "session": {"id": str(uuid.uuid4()), "visitor_id": str(uuid.uuid4()), "page": "/", "landing_page": "/",
                    "active_seconds": 12, "max_scroll": 40, **session},
        "events": [{"type": "pageview", "page": "/"}, {"type": "click", "label": "WhatsApp", "target": "whatsapp"},
                   {"type": "hack", "page": "/"}],
    }


@patch.dict(os.environ, {"SANTA_CLARA_ADMIN_PASSWORD": "senha-de-teste", "SUPABASE_SECRET_KEY": "x"})
class PainelTests(unittest.TestCase):
    def setUp(self):
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), QuietHandler)
        self.addCleanup(self.server.server_close)
        thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.01})
        thread.start()
        self.addCleanup(thread.join)
        self.addCleanup(self.server.shutdown)

    def request(self, method, path, body=None, headers=None):
        client = HTTPConnection(*self.server.server_address, timeout=5)
        try:
            client.request(method, path, body, headers or {})
            response = client.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            client.close()

    def test_admin_shows_login_without_cookie(self):
        status, headers, body = self.request("GET", "/api/tracking?sc_action=admin")
        self.assertEqual(status, 200)
        self.assertIn(b'name="password"', body)
        self.assertEqual(headers.get("X-Frame-Options"), "DENY")

    def test_wrong_password_does_not_log_in(self):
        status, headers, _ = self.request("POST", "/api/tracking?sc_action=admin-login", "password=errada",
                                          {"Content-Type": "application/x-www-form-urlencoded"})
        self.assertEqual(status, 303)
        self.assertEqual(headers["Location"], "/admin?erro=1")
        self.assertNotIn("Set-Cookie", headers)

    def test_right_password_sets_signed_cookie(self):
        status, headers, _ = self.request("POST", "/api/tracking?sc_action=admin-login", "password=senha-de-teste",
                                          {"Content-Type": "application/x-www-form-urlencoded"})
        self.assertEqual(status, 303)
        token = headers["Set-Cookie"].split(";")[0].split("=", 1)[1]
        self.assertTrue(admin_painel.verify_token(token))
        self.assertIn("HttpOnly", headers["Set-Cookie"])
        self.assertFalse(admin_painel.verify_token(token + "0"))

    def test_login_accepts_null_origin_only_from_same_site(self):
        form = {"Content-Type": "application/x-www-form-urlencoded", "Origin": "null"}
        status, headers, _ = self.request("POST", "/api/tracking?sc_action=admin-login", "password=senha-de-teste",
                                          {**form, "Sec-Fetch-Site": "same-origin"})
        self.assertEqual((status, headers["Location"]), (303, "/admin"))
        status, _, _ = self.request("POST", "/api/tracking?sc_action=admin-login", "password=senha-de-teste",
                                    {**form, "Sec-Fetch-Site": "cross-site"})
        self.assertEqual(status, 403)

    def test_leads_csv_requires_login(self):
        status, headers, _ = self.request("GET", "/api/tracking?sc_action=admin-leads")
        self.assertEqual(status, 303)
        self.assertEqual(headers["Location"], "/admin")

    @patch("lead_tracking.configured_supabase")
    def test_track_requires_consent(self, configured):
        data = batch()
        del data["analyticsConsent"]
        status, _, _ = self.request("POST", "/api/tracking?sc_action=track", json.dumps(data),
                                    {"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"})
        self.assertEqual(status, 403)
        configured.assert_not_called()

    @patch("lead_tracking.configured_supabase")
    def test_track_marks_local_visits_as_test(self, configured):
        status, _, _ = self.request("POST", "/api/tracking?sc_action=track", json.dumps(batch()),
                                    {"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"})
        self.assertEqual(status, 204)
        name, args = configured.return_value.rpc.call_args.args
        self.assertEqual(name, "sc_track_batch")
        self.assertTrue(args["p"]["session"]["is_test"])
        self.assertEqual([e["type"] for e in args["p"]["events"]], ["pageview", "click"])

    def test_clean_batch_rejects_bad_ids_and_clamps_numbers(self):
        self.assertIsNone(clean_track_batch(batch(id="nao-e-uuid")))
        clean = clean_track_batch(batch(active_seconds=10 ** 9, max_scroll=-5, page="https://outro.site/"))
        self.assertEqual(clean["session"]["active_seconds"], 14400)
        self.assertEqual(clean["session"]["max_scroll"], 0)
        self.assertEqual(clean["session"]["page"], "/")
        self.assertNotIn("gclid", clean_track_batch(batch(gclid="", landing_page=None))["session"])

    def test_production_host_counts_unless_admin(self):
        self.assertFalse(admin_painel.is_test_visit("laboratoriosantaclaramg.com.br", ""))
        self.assertTrue(admin_painel.is_test_visit("sitesantaclara.vercel.app", ""))
        cookie = f"{admin_painel.ADMIN_COOKIE}={admin_painel.create_token()}"
        self.assertTrue(admin_painel.is_test_visit("laboratoriosantaclaramg.com.br", cookie))

    def test_dashboard_renders_with_empty_data(self):
        period = admin_painel.resolve_period("7d", "")
        html = admin_painel.render_dashboard(dash={"totals": {}}, prev=None, leads=[], visitors=[], keywords=[],
                                             period=period, include_test=False, preset="7d", month="")
        self.assertIn("Painel do site", html)
        self.assertIn("Nenhuma visita real", html)

    def test_csv_blocks_spreadsheet_formulas(self):
        csv = admin_painel.leads_csv([{"name": "=HYPERLINK(1)", "email": "a@b.c"}])
        self.assertIn("\"'=HYPERLINK(1)\"", csv)
        self.assertNotIn("\"'\"", csv)  # célula vazia continua vazia


if __name__ == "__main__":
    unittest.main()
