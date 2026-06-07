"""Phase 5 backend HTTP smoke test.

Runs against http://iranrobot.localhost:8000 with a fresh cookie jar.
"""

import json
import sys
import urllib.parse
import http.client


HOST = "iranrobot.localhost"
PORT = 8000


class Jar:
    def __init__(self):
        self.cookies: dict[str, str] = {}
        self.csrf: str | None = None

    def update(self, set_cookie_headers):
        for raw in set_cookie_headers:
            # naive parse: take first "k=v" pair
            head = raw.split(";", 1)[0].strip()
            if "=" not in head:
                continue
            k, v = head.split("=", 1)
            self.cookies[k] = v

    def header(self) -> str:
        return "; ".join(f"{k}={v}" for k, v in self.cookies.items())


def request(method: str, path: str, jar: Jar, body: dict | None = None, json_body: bool = False):
    conn = http.client.HTTPConnection(HOST, PORT, timeout=15)
    headers = {"Accept": "application/json"}
    encoded = ""
    if body:
        if json_body:
            encoded = json.dumps(body)
            headers["Content-Type"] = "application/json"
        else:
            encoded = urllib.parse.urlencode({k: (json.dumps(v) if not isinstance(v, (str, int, float, bool)) and v is not None else "" if v is None else v) for k, v in body.items()})
            headers["Content-Type"] = "application/x-www-form-urlencoded"
    if jar.header():
        headers["Cookie"] = jar.header()
    if jar.csrf:
        headers["X-Frappe-CSRF-Token"] = jar.csrf
    conn.request(method, path, body=encoded, headers=headers)
    resp = conn.getresponse()
    data = resp.read().decode("utf-8", errors="replace")
    set_cookie = resp.getheader("Set-Cookie")
    if set_cookie:
        # http.client lowercases header keys; getheader joins them. Split safely.
        # Walk all headers to grab every Set-Cookie line.
        all_cookies = [v for k, v in resp.getheaders() if k.lower() == "set-cookie"]
        jar.update(all_cookies)
    try:
        return resp.status, json.loads(data)
    except Exception:
        return resp.status, {"_raw": data[:500]}


PASSES, FAILS = [], []

def check(label, cond, extra=""):
    if cond:
        PASSES.append(label)
        print(f"  ✅ {label}")
    else:
        FAILS.append(f"{label} {extra}")
        print(f"  ❌ {label} {extra}")


print("============================================================")
print("Phase 5 backend smoke")
print("============================================================\n")

# ------------------------ GUEST FLOWS ------------------------
guest = Jar()
# Boot whoami to mint a CSRF token
st, body = request("GET", "/api/method/iranrobot_backend.api.auth.whoami", guest)
msg = body.get("message", {}) if isinstance(body, dict) else {}
guest.csrf = (msg.get("data") or {}).get("csrf_token") if msg.get("ok") else None
check("guest whoami returns csrf token", bool(guest.csrf))

# 1. GUEST quote: valid product
items = [
    {"robot_product": "aimoga-mornine", "quantity": 1, "mode": "buy"},
]
st, body = request(
    "POST",
    "/api/method/iranrobot_backend.api.requests.submit_quote_request",
    guest,
    {
        "items": json.dumps(items),
        "customer_name": "Guest Tester",
        "email": "guest@example.com",
        "phone": "09125550101",
        "message": "I'd like a quote.",
        "language": "en",
    },
)
msg = body.get("message", {})
GUEST_QUOTE_ID = (msg.get("data") or {}).get("request_id")
check("guest quote submit returns ok + request_id", msg.get("ok") and GUEST_QUOTE_ID, extra=f"body={body}")
check("guest quote starts in status=New", (msg.get("data") or {}).get("status") == "New")

# 2. GUEST quote: empty cart
st, body = request(
    "POST", "/api/method/iranrobot_backend.api.requests.submit_quote_request",
    guest, {"items": "[]", "customer_name": "x", "email": "x@example.com"},
)
msg = body.get("message", {})
check("empty cart -> EMPTY_CART", (not msg.get("ok")) and (msg.get("error") or {}).get("code") == "EMPTY_CART", extra=f"body={body}")

# 3. GUEST quote: bad product
st, body = request(
    "POST", "/api/method/iranrobot_backend.api.requests.submit_quote_request",
    guest, {
        "items": json.dumps([{"robot_product": "does-not-exist", "quantity": 1, "mode": "buy"}]),
        "customer_name": "Bad", "email": "bad@example.com",
    },
)
msg = body.get("message", {})
check("bad product id -> INVALID_PRODUCT", (not msg.get("ok")) and (msg.get("error") or {}).get("code") == "INVALID_PRODUCT", extra=f"body={body}")

# 4. GUEST procurement
st, body = request(
    "POST", "/api/method/iranrobot_backend.api.requests.submit_procurement_request",
    guest, {
        "product_name": "FANUC LR Mate 200iD/7L",
        "brand": "FANUC",
        "quantity": 2,
        "origin_country": "Japan",
        "destination_city": "Tehran",
        "target_budget_usd": 35000,
        "timeline": "Q4 2026",
        "message": "We need this for a packaging line.",
        "contact_name": "Guest Procurement",
        "email": "procure-guest@example.com",
        "phone": "09125550202",
        "language": "fa",
    },
)
msg = body.get("message", {})
GUEST_PROC_ID = (msg.get("data") or {}).get("request_id")
check("guest procurement submit ok", msg.get("ok") and GUEST_PROC_ID, extra=f"body={body}")

# 5. GUEST support
st, body = request(
    "POST", "/api/method/iranrobot_backend.api.requests.submit_support_ticket",
    guest, {
        "name": "Guest Support",
        "email": "support-guest@example.com",
        "phone": "09125550303",
        "topic": "tech",
        "subject": "Need help connecting via ROS2",
        "message": "ROS2 humble can't see the Aimoga Mornine sensor.",
        "language": "en",
    },
)
msg = body.get("message", {})
GUEST_TICKET_ID = (msg.get("data") or {}).get("ticket_id")
check("guest support submit ok", msg.get("ok") and GUEST_TICKET_ID, extra=f"body={body}")

# ------------------------ LOGGED-IN FLOWS ------------------------
user = Jar()
st, body = request("GET", "/api/method/iranrobot_backend.api.auth.whoami", user)
msg = body.get("message", {}) if isinstance(body, dict) else {}
user.csrf = (msg.get("data") or {}).get("csrf_token") if msg.get("ok") else None

st, body = request(
    "POST", "/api/method/iranrobot_backend.api.auth.login",
    user, {"usr": "customer1@example.com", "pwd": "ChangeMe-123"},
)
msg = body.get("message", {})
LOGGED_IN_OK = msg.get("ok") and (msg.get("data") or {}).get("is_authenticated")
CUSTOMER_LINK = (msg.get("data") or {}).get("user", {}).get("customer") if LOGGED_IN_OK else None
user.csrf = (msg.get("data") or {}).get("csrf_token") if LOGGED_IN_OK else user.csrf
check("login as customer1 succeeds", LOGGED_IN_OK, extra=f"body={body}")
check("login returns linked customer id", bool(CUSTOMER_LINK))

# 6. LOGGED-IN quote
st, body = request(
    "POST",
    "/api/method/iranrobot_backend.api.requests.submit_quote_request",
    user, {
        "items": json.dumps([
            {"robot_product": "aimoga-mornine", "quantity": 2, "mode": "buy"},
            {"robot_product": "unitree-g1-edu-u3", "quantity": 1, "mode": "rent", "requested_days": 14},
        ]),
        "message": "Procurement test from authenticated session.",
        "language": "fa",
    },
)
msg = body.get("message", {})
LOG_QUOTE_ID = (msg.get("data") or {}).get("request_id")
check("logged-in quote submit ok", msg.get("ok") and LOG_QUOTE_ID, extra=f"body={body}")

# 7. LOGGED-IN procurement
st, body = request(
    "POST",
    "/api/method/iranrobot_backend.api.requests.submit_procurement_request",
    user, {
        "product_name": "ABB IRB 1100",
        "brand": "ABB",
        "quantity": 1,
        "origin_country": "Switzerland",
        "destination_city": "Isfahan",
        "target_budget_usd": 50000,
        "timeline": "ASAP",
        "message": "Pilot project sourcing.",
        "language": "fa",
    },
)
msg = body.get("message", {})
LOG_PROC_ID = (msg.get("data") or {}).get("request_id")
check("logged-in procurement submit ok", msg.get("ok") and LOG_PROC_ID, extra=f"body={body}")

# 8. LOGGED-IN support
st, body = request(
    "POST",
    "/api/method/iranrobot_backend.api.requests.submit_support_ticket",
    user, {
        "topic": "sales",
        "subject": "Question about volume discounts",
        "message": "We want to buy 10 units of the same robot. Is there a discount?",
        "language": "fa",
    },
)
msg = body.get("message", {})
LOG_TICKET_ID = (msg.get("data") or {}).get("ticket_id")
check("logged-in support submit ok", msg.get("ok") and LOG_TICKET_ID, extra=f"body={body}")

# 9. LOGGED-IN get_my_requests
st, body = request(
    "GET",
    "/api/method/iranrobot_backend.api.requests.get_my_requests",
    user,
)
msg = body.get("message", {})
data = msg.get("data") or {}
my_q = data.get("quote_requests") or []
my_p = data.get("procurement_requests") or []
my_t = data.get("support_tickets") or []
check("get_my_requests returns ok", msg.get("ok"), extra=f"body={body}")
check("get_my_requests includes my submitted quote", any(r["name"] == LOG_QUOTE_ID for r in my_q))
check("get_my_requests includes my submitted procurement", any(r["name"] == LOG_PROC_ID for r in my_p))
check("get_my_requests includes my support ticket", any(r["name"] == LOG_TICKET_ID for r in my_t))

# 10. GUEST get_my_requests -> AUTH_REQUIRED
st, body = request("GET", "/api/method/iranrobot_backend.api.requests.get_my_requests", guest)
msg = body.get("message", {})
check("guest get_my_requests -> AUTH_REQUIRED", (not msg.get("ok")) and (msg.get("error") or {}).get("code") == "AUTH_REQUIRED")

# 11. Logout, then repeated submit -> separate record
st, body = request("POST", "/api/method/iranrobot_backend.api.auth.logout", user)
user.csrf = (body.get("message", {}).get("data") or {}).get("csrf_token") or user.csrf

st, body1 = request("POST", "/api/method/iranrobot_backend.api.requests.submit_quote_request", user, {
    "items": json.dumps([{"robot_product": "aimoga-mornine", "quantity": 1, "mode": "buy"}]),
    "customer_name": "Dup1", "email": "dup1@example.com",
})
st, body2 = request("POST", "/api/method/iranrobot_backend.api.requests.submit_quote_request", user, {
    "items": json.dumps([{"robot_product": "aimoga-mornine", "quantity": 1, "mode": "buy"}]),
    "customer_name": "Dup2", "email": "dup2@example.com",
})
id1 = (body1.get("message", {}).get("data") or {}).get("request_id")
id2 = (body2.get("message", {}).get("data") or {}).get("request_id")
check("repeated submit creates distinct records", id1 and id2 and id1 != id2, extra=f"id1={id1} id2={id2}")

# Catalog regression: catalog still 200
st, body = request("GET", "/api/method/iranrobot_backend.api.catalog.get_homepage_catalog", guest)
check("catalog regression ok", body.get("message", {}).get("ok"))

print()
print(f"{len(PASSES)}/{len(PASSES) + len(FAILS)} PASSED")
for f in FAILS:
    print(f"  FAIL: {f}")
sys.exit(0 if not FAILS else 1)
