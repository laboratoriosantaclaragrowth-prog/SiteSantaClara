import json
import threading
import unittest
import uuid
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from unittest.mock import Mock, patch

from api.tracking import handler
from tracking_supabase import TrackingUnavailable


class QuietHandler(handler):
    def log_message(self, *args):
        pass


class VercelTrackingTests(unittest.TestCase):
    def setUp(self):
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), QuietHandler)
        self.addCleanup(self.server.server_close)
        thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.01})
        thread.start()
        self.addCleanup(thread.join)
        self.addCleanup(self.server.shutdown)
        self.data = {"id": str(uuid.uuid4()), "session": str(uuid.uuid4()),
                     "name": "Teste", "email": "teste@example.test"}

    def request(self, method, path, data=None):
        client = HTTPConnection(*self.server.server_address, timeout=3)
        try:
            body = json.dumps(data) if data is not None else None
            client.request(method, path, body, {"Content-Type": "application/json"})
            response = client.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            client.close()

    @patch("lead_tracking.configured_supabase")
    def test_rewritten_form_only_returns_the_pdf_link_after_saving(self, configured):
        db = configured.return_value
        db.ebook_download_url.return_value = "https://example.test/signed.pdf"
        db.save.side_effect = [False, True]
        path = "/api/tracking?sc_action=ebook-leads"
        status, _, body = self.request("POST", path, self.data)
        self.assertEqual(status, 409)
        self.assertNotIn("download", json.loads(body))
        status, headers, body = self.request("POST", path, self.data)
        self.assertEqual(status, 200)
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertEqual(json.loads(body)["download"], db.ebook_download_url.return_value)
        configured.assert_called_with(required=True)
        self.assertEqual(db.save.call_args.args[:3], (self.data["id"], "ebook_lead", self.data["session"]))

    @patch("lead_tracking.configured_supabase")
    def test_download_requires_a_registered_id(self, configured):
        db = configured.return_value
        db.exists.side_effect = [False, True]
        db.ebook_download_url.return_value = "https://example.test/signed.pdf"
        path = f"/api/tracking?sc_action=ebook&id={self.data['id']}"
        self.assertEqual(self.request("GET", path)[0], 404)
        db.ebook_download_url.assert_not_called()
        status, headers, _ = self.request("GET", path)
        self.assertEqual(status, 302)
        self.assertEqual(headers["Location"], db.ebook_download_url.return_value)

    @patch("lead_tracking.configured_supabase", side_effect=TrackingUnavailable)
    def test_bad_requests_and_missing_configuration_return_json(self, configured):
        path = "/api/ebook-leads"
        status, headers, _ = self.request("POST", path, {})
        self.assertEqual(status, 400)
        self.assertEqual(headers["Content-Type"], "application/json")
        configured.assert_not_called()
        status, headers, _ = self.request("POST", path, self.data)
        self.assertEqual(status, 503)
        self.assertEqual(headers["Content-Type"], "application/json")

    @patch("lead_tracking.configured_supabase", return_value=Mock())
    def test_events_require_consent(self, configured):
        status, _, _ = self.request("POST", "/api/tracking?sc_action=events", self.data)
        self.assertEqual(status, 403)
        configured.assert_not_called()
