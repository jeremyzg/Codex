import json
import threading
import time
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from wsgiref.simple_server import make_server

from app.main import DB_PATH, app, init_db


class AppE2ETest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if DB_PATH.exists():
            DB_PATH.unlink()
        init_db()
        cls.server = make_server("127.0.0.1", 8011, app)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        time.sleep(0.1)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        if DB_PATH.exists():
            DB_PATH.unlink()

    def api(self, method, path, payload=None):
        data = None
        headers = {}
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = Request(f"http://127.0.0.1:8011{path}", data=data, headers=headers, method=method)
        try:
            with urlopen(req) as res:
                return res.status, json.loads(res.read().decode("utf-8"))
        except HTTPError as err:
            return err.code, json.loads(err.read().decode("utf-8"))

    def test_full_flow(self):
        status, p = self.api(
            "POST",
            "/api/professionals",
            {
                "name": "Jordan Smith",
                "business_type": "Law Firm",
                "email": "jordan@example.com",
                "card_token": "tok_12345678",
                "card_last4": "4242",
            },
        )
        self.assertEqual(status, 200)

        status, c = self.api(
            "POST",
            "/api/clients",
            {
                "professional_id": p["id"],
                "full_name": "Alex Client",
                "email": "alex@example.com",
                "shipping_address": "100 Main St, Denver, CO",
                "birthday": "1990-06-15",
                "budget": 100,
                "preferences": "coffee,tech,professional",
            },
        )
        self.assertEqual(status, 200)

        status, _ = self.api("POST", f"/api/clients/{c['id']}/occasions", {"name": "Anniversary", "date": "2027-12-31"})
        self.assertEqual(status, 200)

        status, recs = self.api("GET", f"/api/clients/{c['id']}/recommendations?occasion=birthday&limit=10")
        self.assertEqual(status, 200)
        self.assertTrue(1 <= len(recs) <= 10)

        choice = recs[0]
        status, order = self.api(
            "POST",
            "/api/orders",
            {
                "client_id": c["id"],
                "occasion_name": "birthday",
                "vendor": choice["vendor"],
                "product_name": choice["product_name"],
                "price": choice["price"],
            },
        )
        self.assertEqual(status, 200)
        self.assertEqual(order["status"], "confirmed")

        status, dashboard = self.api("GET", "/api/dashboard")
        self.assertEqual(status, 200)
        self.assertEqual(dashboard["clients"], 1)
        self.assertEqual(dashboard["orders"], 1)

    def test_validation_and_limits(self):
        status, err = self.api(
            "POST",
            "/api/professionals",
            {
                "name": "Bad",
                "business_type": "Banking",
                "email": "bad@example.com",
                "card_token": "tok_abc",
                "card_last4": "12",
            },
        )
        self.assertEqual(status, 400)
        self.assertIn("card_last4", err["detail"])

        status, _ = self.api("GET", "/api/clients/999/recommendations?occasion=birthday&limit=bad")
        self.assertEqual(status, 404)


if __name__ == "__main__":
    unittest.main()
