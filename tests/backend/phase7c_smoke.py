"""Phase 7C HTTP smoke -- customer-side reads + auth boundary on the convert endpoint."""

import http.client, json, sys, urllib.parse


HOST, PORT = "iranrobot.localhost", 8000


class Jar:
    def __init__(self):
        self.cookies, self.csrf = {}, None

    def update(self, headers):
        for raw in headers:
            head = raw.split(";", 1)[0].strip()
            if "=" in head:
                k, v = head.split("=", 1)
                self.cookies[k] = v

    def header(self):
        return "; ".join(f"{k}={v}" for k, v in self.cookies.items())


def request(method, path, jar, body=None):
    conn = http.client.HTTPConnection(HOST, PORT, timeout=15)
    headers = {"Accept": "application/json"}
    encoded = ""
    if body:
        encoded = urllib.parse.urlencode({k: ("" if v is None else v) for k, v in body.items()})
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    if jar.header():
        headers["Cookie"] = jar.header()
    if jar.csrf:
        headers["X-Frappe-CSRF-Token"] = jar.csrf
    conn.request(method, path, body=encoded, headers=headers)
    resp = conn.getresponse()
    data = resp.read().decode("utf-8", errors="replace")
    set_cookies = [v for k, v in resp.getheaders() if k.lower() == "set-cookie"]
    if set_cookies:
        jar.update(set_cookies)
    try:
        return resp.status, json.loads(data)
    except Exception:
        return resp.status, {"_raw": data[:300]}


PASS, FAIL = [], []


def check(label, ok, extra=""):
    if ok:
        PASS.append(label)
        print(f"  ✅ {label}")
    else:
        FAIL.append(label)
        print(f"  ❌ {label} {extra}")


print("============================================================")
print("Phase 7C HTTP smoke")
print("============================================================\n")

# 1. Guest convert -> Frappe 403 (POST not allow_guest)
guest = Jar()
st, body = request("GET", "/api/method/iranrobot_backend.api.auth.whoami", guest)
guest.csrf = (body.get("message", {}).get("data") or {}).get("csrf_token")
st, body = request(
    "POST",
    "/api/method/iranrobot_backend.api.requests.convert_accepted_quote_to_sales_order",
    guest, {"name": "QR-WHATEVER"},
)
check("guest convert -> HTTP 403", st == 403)

# Login as customer1
customer = Jar()
request("GET", "/api/method/iranrobot_backend.api.auth.whoami", customer)
customer.csrf = (body.get("message", {}).get("data") or {}).get("csrf_token")
st, body = request(
    "POST",
    "/api/method/iranrobot_backend.api.auth.login",
    customer, {"usr": "customer1@example.com", "pwd": "ChangeMe-123"},
)
msg = body.get("message", {})
customer.csrf = (msg.get("data") or {}).get("csrf_token") or customer.csrf
check("login as customer1", msg.get("ok"))

# 2. Customer convert -> NOT_PERMITTED via our envelope
st, body = request(
    "POST",
    "/api/method/iranrobot_backend.api.requests.convert_accepted_quote_to_sales_order",
    customer, {"name": "QR-WHATEVER"},
)
msg = body.get("message", {}) if isinstance(body, dict) else {}
not_permitted = (
    (not msg.get("ok"))
    and (msg.get("error") or {}).get("code") == "NOT_PERMITTED"
) or st in (403, 417)
check("customer convert -> NOT_PERMITTED", not_permitted, extra=f"status={st} body={body}")

# 3. Customer get_my_orders -> ok
st, body = request("GET", "/api/method/iranrobot_backend.api.orders.get_my_orders?limit=10", customer)
msg = body.get("message", {})
data = msg.get("data") or {}
orders = data.get("orders") or []
check("get_my_orders returns ok", msg.get("ok"))
print(f"    orders count: {len(orders)}")
check("orders payload uses customer-safe field allow-list", all(
    set(o.keys()).issubset({
        "name", "status", "transaction_date", "delivery_date", "customer_name",
        "grand_total", "currency", "creation", "items_count",
        "linked_quote_request", "linked_quotation",
    })
    for o in orders
), extra=f"sample keys: {orders[0].keys() if orders else None}")

# 4. Customer get_my_order_detail with their own order
if orders:
    so_name = orders[0]["name"]
    st, body = request(
        "GET",
        f"/api/method/iranrobot_backend.api.orders.get_my_order_detail?name={urllib.parse.quote(so_name)}",
        customer,
    )
    msg = body.get("message", {})
    rec = (msg.get("data") or {}).get("record") or {}
    check("get_my_order_detail returns ok", msg.get("ok"))
    # No leakage: ensure none of the forbidden fields snuck in
    bad_keys = [k for k in rec.keys() if any(
        s in k.lower() for s in ("base_", "tax", "discount", "margin", "internal", "owner", "modified_by", "_user_tags", "address_display")
    )]
    check("no internal/admin fields in order detail", not bad_keys, extra=f"leaks={bad_keys}")
    items = rec.get("items") or []
    if items:
        item_bad = [k for k in items[0].keys() if any(
            s in k.lower() for s in ("base_", "tax", "discount", "margin", "valuation", "cost")
        )]
        check("no internal/admin fields in order item rows", not item_bad)

# 5. Forged SO id -> NOT_FOUND
st, body = request(
    "GET",
    "/api/method/iranrobot_backend.api.orders.get_my_order_detail?name=SAL-ORD-FAKE-99999",
    customer,
)
msg = body.get("message", {})
check(
    "forged SO id -> NOT_FOUND",
    (not msg.get("ok")) and (msg.get("error") or {}).get("code") == "NOT_FOUND",
)

# 6. Catalog regression
st, body = request("GET", "/api/method/iranrobot_backend.api.catalog.get_homepage_catalog", customer)
check("catalog still works", body.get("message", {}).get("ok"))

print()
print(f"{len(PASS)}/{len(PASS) + len(FAIL)} PASSED")
sys.exit(0 if not FAIL else 1)
