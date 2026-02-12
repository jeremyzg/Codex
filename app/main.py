import json
import sqlite3
from datetime import date, datetime
from pathlib import Path
from urllib.parse import parse_qs
from wsgiref.simple_server import make_server

DB_PATH = Path("gifting.db")
STATIC_DIR = Path("static")

GIFT_CATALOG = [
    {"product_name": "Premium Fountain Pen", "vendor": "Amazon", "category": "office", "price": 89.0, "tags": {"executive", "writing", "professional"}, "link": "https://www.amazon.com/"},
    {"product_name": "Artisan Coffee Sampler", "vendor": "Trade Coffee", "category": "food", "price": 45.0, "tags": {"coffee", "gourmet", "casual"}, "link": "https://www.drinktrade.com/"},
    {"product_name": "Desk Succulent Collection", "vendor": "The Sill", "category": "decor", "price": 55.0, "tags": {"plants", "office", "design"}, "link": "https://www.thesill.com/"},
    {"product_name": "Leather Portfolio", "vendor": "Leatherology", "category": "office", "price": 120.0, "tags": {"executive", "meetings", "premium"}, "link": "https://www.leatherology.com/"},
    {"product_name": "Luxury Chocolate Box", "vendor": "Godiva", "category": "food", "price": 35.0, "tags": {"sweet", "gourmet", "celebration"}, "link": "https://www.godiva.com/"},
    {"product_name": "Noise-Canceling Earbuds", "vendor": "Best Buy", "category": "tech", "price": 99.0, "tags": {"tech", "travel", "productivity"}, "link": "https://www.bestbuy.com/"},
    {"product_name": "Spa & Wellness Gift Set", "vendor": "Sephora", "category": "wellness", "price": 72.0, "tags": {"relaxation", "self-care", "wellness"}, "link": "https://www.sephora.com/"},
    {"product_name": "High-End Notebook Set", "vendor": "Moleskine", "category": "office", "price": 38.0, "tags": {"writing", "planning", "professional"}, "link": "https://www.moleskine.com/"},
    {"product_name": "Gourmet Snack Basket", "vendor": "Harry & David", "category": "food", "price": 95.0, "tags": {"gourmet", "sharing", "celebration"}, "link": "https://www.harryanddavid.com/"},
    {"product_name": "Bluetooth Speaker", "vendor": "Bose", "category": "tech", "price": 129.0, "tags": {"music", "tech", "premium"}, "link": "https://www.bose.com/"},
]


def db_connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = db_connect()
    cur = conn.cursor()
    cur.executescript(
        """
        CREATE TABLE IF NOT EXISTS professionals (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          name TEXT NOT NULL,
          business_type TEXT NOT NULL,
          email TEXT NOT NULL UNIQUE,
          card_token TEXT NOT NULL,
          card_last4 TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS clients (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          professional_id INTEGER NOT NULL,
          full_name TEXT NOT NULL,
          email TEXT NOT NULL,
          shipping_address TEXT NOT NULL,
          birthday TEXT NOT NULL,
          budget REAL NOT NULL CHECK (budget > 0),
          preferences TEXT DEFAULT '',
          FOREIGN KEY(professional_id) REFERENCES professionals(id)
        );
        CREATE TABLE IF NOT EXISTS occasions (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          client_id INTEGER NOT NULL,
          name TEXT NOT NULL,
          date TEXT NOT NULL,
          FOREIGN KEY(client_id) REFERENCES clients(id)
        );
        CREATE TABLE IF NOT EXISTS gift_orders (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          client_id INTEGER NOT NULL,
          occasion_name TEXT NOT NULL,
          vendor TEXT NOT NULL,
          product_name TEXT NOT NULL,
          price REAL NOT NULL CHECK (price > 0),
          shipping_address TEXT NOT NULL,
          status TEXT NOT NULL,
          created_at TEXT NOT NULL,
          FOREIGN KEY(client_id) REFERENCES clients(id)
        );
        """
    )
    conn.commit()
    conn.close()


def parse_date(raw: str):
    return datetime.strptime(raw, "%Y-%m-%d").date()


def json_response(start_response, status, body):
    payload = json.dumps(body).encode("utf-8")
    start_response(status, [("Content-Type", "application/json"), ("Content-Length", str(len(payload))), ("Access-Control-Allow-Origin", "*")])
    return [payload]


def text_response(start_response, status, body, content_type="text/plain"):
    payload = body.encode("utf-8")
    start_response(status, [("Content-Type", content_type), ("Content-Length", str(len(payload)))])
    return [payload]


def parse_body(environ):
    try:
        length = int(environ.get("CONTENT_LENGTH", 0))
    except ValueError:
        length = 0
    data = environ["wsgi.input"].read(length) if length else b"{}"
    try:
        return json.loads(data.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return None


def days_until(raw_date):
    today = date.today()
    dt = parse_date(raw_date)
    candidate = dt.replace(year=today.year)
    if candidate < today:
        candidate = candidate.replace(year=today.year + 1)
    return (candidate - today).days


def recommendations(budget, preferences, occasion, limit=10):
    preference_tags = {p.strip().lower() for p in (preferences or "").split(",") if p.strip()}
    occasion_tags = {occasion.lower(), "celebration"}
    scored = []
    for item in GIFT_CATALOG:
        if item["price"] > budget:
            continue
        overlap = len((preference_tags | occasion_tags) & item["tags"])
        budget_fit = 1 - abs((budget - item["price"]) / max(budget, 1))
        score = overlap * 2 + budget_fit
        reason = "matches profile and occasion" if overlap else "fits budget well"
        rec = {k: item[k] for k in ["product_name", "vendor", "category", "price", "link"]}
        rec["reason"] = reason
        scored.append((score, rec))

    if not scored:
        fallback = sorted(GIFT_CATALOG, key=lambda x: x["price"])[:max(1, min(limit, 10))]
        return [{**{k: item[k] for k in ["product_name", "vendor", "category", "price", "link"]}, "reason": "closest available option"} for item in fallback]

    scored.sort(key=lambda x: x[0], reverse=True)
    return [x[1] for x in scored[:max(1, min(limit, 10))]]


def validate_required(body, fields):
    missing = [f for f in fields if body.get(f) in (None, "")]
    return missing


def serve_static(path, start_response):
    target = "index.html" if path == "/" else path.lstrip("/")
    file_path = (STATIC_DIR / target).resolve()
    if STATIC_DIR.resolve() not in file_path.parents and file_path != STATIC_DIR.resolve():
        return text_response(start_response, "403 Forbidden", "Forbidden")
    if not file_path.exists() or not file_path.is_file():
        return text_response(start_response, "404 Not Found", "Not found")
    content = file_path.read_bytes()
    if file_path.suffix == ".css":
        ctype = "text/css"
    elif file_path.suffix == ".js":
        ctype = "application/javascript"
    else:
        ctype = "text/html"
    start_response("200 OK", [("Content-Type", ctype), ("Content-Length", str(len(content)))])
    return [content]


def app(environ, start_response):
    method = environ["REQUEST_METHOD"]
    path = environ["PATH_INFO"]

    if method == "OPTIONS":
        start_response("200 OK", [
            ("Access-Control-Allow-Origin", "*"),
            ("Access-Control-Allow-Methods", "GET,POST,OPTIONS"),
            ("Access-Control-Allow-Headers", "Content-Type"),
        ])
        return [b""]

    if not path.startswith("/api/"):
        return serve_static(path, start_response)

    conn = db_connect()
    cur = conn.cursor()

    try:
        if method == "GET" and path == "/api/health":
            return json_response(start_response, "200 OK", {"ok": True})

        if method == "POST" and path == "/api/professionals":
            body = parse_body(environ)
            if body is None:
                return json_response(start_response, "400 Bad Request", {"detail": "Invalid JSON"})
            missing = validate_required(body, ["name", "business_type", "email", "card_token", "card_last4"])
            if missing:
                return json_response(start_response, "400 Bad Request", {"detail": f"Missing required fields: {', '.join(missing)}"})
            if len(str(body["card_last4"])) != 4 or not str(body["card_last4"]).isdigit():
                return json_response(start_response, "400 Bad Request", {"detail": "card_last4 must be 4 digits"})
            try:
                cur.execute(
                    "INSERT INTO professionals(name,business_type,email,card_token,card_last4) VALUES (?,?,?,?,?)",
                    (body["name"].strip(), body["business_type"].strip(), body["email"].strip().lower(), body["card_token"].strip(), str(body["card_last4"])),
                )
                conn.commit()
            except sqlite3.IntegrityError:
                return json_response(start_response, "400 Bad Request", {"detail": "Professional with this email already exists"})
            row = cur.execute("SELECT id,name,business_type,email,card_last4 FROM professionals WHERE id=?", (cur.lastrowid,)).fetchone()
            return json_response(start_response, "200 OK", dict(row))

        if method == "POST" and path == "/api/clients":
            body = parse_body(environ)
            if body is None:
                return json_response(start_response, "400 Bad Request", {"detail": "Invalid JSON"})
            missing = validate_required(body, ["professional_id", "full_name", "email", "shipping_address", "birthday", "budget"])
            if missing:
                return json_response(start_response, "400 Bad Request", {"detail": f"Missing required fields: {', '.join(missing)}"})
            try:
                budget = float(body["budget"])
                parse_date(body["birthday"])
            except (ValueError, TypeError):
                return json_response(start_response, "400 Bad Request", {"detail": "Invalid birthday or budget format"})
            if budget <= 0:
                return json_response(start_response, "400 Bad Request", {"detail": "Budget must be greater than 0"})
            exists = cur.execute("SELECT id FROM professionals WHERE id=?", (body["professional_id"],)).fetchone()
            if not exists:
                return json_response(start_response, "404 Not Found", {"detail": "Professional not found"})
            cur.execute(
                "INSERT INTO clients(professional_id,full_name,email,shipping_address,birthday,budget,preferences) VALUES (?,?,?,?,?,?,?)",
                (body["professional_id"], body["full_name"].strip(), body["email"].strip().lower(), body["shipping_address"].strip(), body["birthday"], budget, (body.get("preferences") or "").strip()),
            )
            conn.commit()
            row = cur.execute("SELECT * FROM clients WHERE id=?", (cur.lastrowid,)).fetchone()
            return json_response(start_response, "200 OK", dict(row))

        if method == "GET" and path == "/api/clients":
            rows = [dict(r) for r in cur.execute("SELECT * FROM clients ORDER BY id DESC").fetchall()]
            return json_response(start_response, "200 OK", rows)

        if method == "POST" and path.startswith("/api/clients/") and path.endswith("/occasions"):
            client_id = int(path.split("/")[3])
            body = parse_body(environ)
            if body is None:
                return json_response(start_response, "400 Bad Request", {"detail": "Invalid JSON"})
            missing = validate_required(body, ["name", "date"])
            if missing:
                return json_response(start_response, "400 Bad Request", {"detail": f"Missing required fields: {', '.join(missing)}"})
            try:
                parse_date(body["date"])
            except ValueError:
                return json_response(start_response, "400 Bad Request", {"detail": "Invalid date format, expected YYYY-MM-DD"})
            exists = cur.execute("SELECT id FROM clients WHERE id=?", (client_id,)).fetchone()
            if not exists:
                return json_response(start_response, "404 Not Found", {"detail": "Client not found"})
            cur.execute("INSERT INTO occasions(client_id,name,date) VALUES (?,?,?)", (client_id, body["name"].strip(), body["date"]))
            conn.commit()
            row = cur.execute("SELECT * FROM occasions WHERE id=?", (cur.lastrowid,)).fetchone()
            return json_response(start_response, "200 OK", dict(row))

        if method == "GET" and path.startswith("/api/clients/") and path.endswith("/recommendations"):
            client_id = int(path.split("/")[3])
            client_row = cur.execute("SELECT * FROM clients WHERE id=?", (client_id,)).fetchone()
            if not client_row:
                return json_response(start_response, "404 Not Found", {"detail": "Client not found"})
            qs = parse_qs(environ.get("QUERY_STRING", ""))
            occasion = qs.get("occasion", ["birthday"])[0]
            try:
                limit = int(qs.get("limit", ["10"])[0])
            except ValueError:
                return json_response(start_response, "400 Bad Request", {"detail": "limit must be an integer"})
            recs = recommendations(float(client_row["budget"]), client_row["preferences"] or "", occasion, limit)
            return json_response(start_response, "200 OK", recs)

        if method == "POST" and path == "/api/orders":
            body = parse_body(environ)
            if body is None:
                return json_response(start_response, "400 Bad Request", {"detail": "Invalid JSON"})
            missing = validate_required(body, ["client_id", "occasion_name", "vendor", "product_name", "price"])
            if missing:
                return json_response(start_response, "400 Bad Request", {"detail": f"Missing required fields: {', '.join(missing)}"})
            client_row = cur.execute("SELECT id,budget,shipping_address FROM clients WHERE id=?", (body["client_id"],)).fetchone()
            if not client_row:
                return json_response(start_response, "404 Not Found", {"detail": "Client not found"})
            try:
                price = float(body["price"])
            except (TypeError, ValueError):
                return json_response(start_response, "400 Bad Request", {"detail": "price must be a number"})
            if price <= 0:
                return json_response(start_response, "400 Bad Request", {"detail": "price must be greater than 0"})
            if price > float(client_row["budget"]):
                return json_response(start_response, "400 Bad Request", {"detail": "Selected gift exceeds client budget"})
            cur.execute(
                "INSERT INTO gift_orders(client_id,occasion_name,vendor,product_name,price,shipping_address,status,created_at) VALUES (?,?,?,?,?,?,?,?)",
                (body["client_id"], body["occasion_name"].strip(), body["vendor"].strip(), body["product_name"].strip(), price, client_row["shipping_address"], "confirmed", datetime.utcnow().isoformat()),
            )
            conn.commit()
            row = cur.execute("SELECT * FROM gift_orders WHERE id=?", (cur.lastrowid,)).fetchone()
            return json_response(start_response, "200 OK", dict(row))

        if method == "GET" and path == "/api/orders":
            rows = [dict(r) for r in cur.execute("SELECT * FROM gift_orders ORDER BY id DESC").fetchall()]
            return json_response(start_response, "200 OK", rows)

        if method == "GET" and path == "/api/dashboard":
            clients = cur.execute("SELECT * FROM clients").fetchall()
            orders = cur.execute("SELECT * FROM gift_orders").fetchall()
            occasions = cur.execute("SELECT date FROM occasions").fetchall()
            upcoming_30 = sum(1 for c in clients if days_until(c["birthday"]) <= 30)
            upcoming_30 += sum(1 for o in occasions if days_until(o["date"]) <= 30)
            payload = {
                "clients": len(clients),
                "orders": len(orders),
                "total_budget": round(sum(c["budget"] for c in clients), 2),
                "total_order_value": round(sum(o["price"] for o in orders), 2),
                "upcoming_30_days": upcoming_30,
            }
            return json_response(start_response, "200 OK", payload)

        return json_response(start_response, "404 Not Found", {"detail": "Not found"})
    except ValueError:
        return json_response(start_response, "400 Bad Request", {"detail": "Invalid path parameter"})
    finally:
        conn.close()


def run(host="0.0.0.0", port=8000):
    init_db()
    with make_server(host, port, app) as httpd:
        print(f"Serving on http://{host}:{port}")
        httpd.serve_forever()


if __name__ == "__main__":
    run()
