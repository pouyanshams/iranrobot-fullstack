"""Phase 7A HTTP smoke -- exercises the customer-facing path end-to-end and
verifies the staff-only convert endpoint is properly guarded against guest /
customer callers over HTTP.

The staff-side convert tests + sync hook are exercised separately through
`bench execute iranrobot_backend.commands._phase7a_smoke.run_all`.
"""

import http.client
import json
import sys
import urllib.parse


HOST = "iranrobot.localhost"
PORT = 8000


class Jar:
    def __init__(self):
        self.cookies: dict[str, str] = {}
        self.csrf: str | None = None

    def update(self, set_cookie_headers):
        for raw in set_cookie_headers:
            head = raw.split(";", 1)[0].strip()
            if "=" not in head:
                continue
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
    cookies = [v for k, v in resp.getheaders() if k.lower() == "set-cookie"]
    if cookies:
        jar.update(cookies)
    try:
        return resp.status, json.loads(data)
    except Exception:
        return resp.status, {"_raw": data[:500]}


PASS, FAIL = [], []


def check(label, ok, extra=""):
    if ok:
        PASS.append(label)
        print(f"  ✅ {label}")
    else:
        FAIL.append(label)
        print(f"  ❌ {label} {extra}")


print("============================================================")
print("Phase 7A HTTP smoke")
print("============================================================\n")

# 1. Guest can't call convert -- Frappe returns raw 403 before our code runs,
#    which is acceptable because the endpoint is not allow_guest.
guest = Jar()
st, body = request("GET", "/api/method/iranrobot_backend.api.auth.whoami", guest)
guest.csrf = (body.get("message", {}).get("data") or {}).get("csrf_token")
st, body = request(
    "POST",
    "/api/method/iranrobot_backend.api.requests.convert_quote_request_to_quotation",
    guest,
    {"name": "QR-NONEXISTENT"},
)
check("guest hitting convert endpoint -> HTTP 403", st == 403, extra=f"status={st} body={body}")

# 2. Customer (no Sales role) can't call convert even with a valid session
customer = Jar()
st, body = request("GET", "/api/method/iranrobot_backend.api.auth.whoami", customer)
customer.csrf = (body.get("message", {}).get("data") or {}).get("csrf_token")
st, body = request(
    "POST",
    "/api/method/iranrobot_backend.api.auth.login",
    customer,
    {"usr": "customer1@example.com", "pwd": "ChangeMe-123"},
)
msg = body.get("message", {})
customer.csrf = (msg.get("data") or {}).get("csrf_token") or customer.csrf
check("login as customer1 ok", msg.get("ok") and (msg.get("data") or {}).get("is_authenticated"))

# Try to call convert as the logged-in customer -- should return NOT_PERMITTED
# via our envelope (Frappe lets the call through because customer has a session;
# our code's role check rejects).
st, body = request(
    "POST",
    "/api/method/iranrobot_backend.api.requests.convert_quote_request_to_quotation",
    customer,
    {"name": "QR-ANYTHING"},
)
msg = body.get("message", {}) if isinstance(body, dict) else {}
# Frappe might also block at the whitelist layer (some configurations); accept
# either NOT_PERMITTED (our app envelope) or 403/417 (Frappe layer rejection).
not_permitted = (
    (not msg.get("ok")) and (msg.get("error") or {}).get("code") == "NOT_PERMITTED"
) or st in (403, 417)
check("customer1 cannot call convert (role gate)", not_permitted, extra=f"status={st} body={body}")

# 3. Customer can read get_my_request_detail and see the quotation block on
#    one of their converted quotes.
st, body = request(
    "GET",
    "/api/method/iranrobot_backend.api.requests.get_my_requests?limit=50",
    customer,
)
data = body.get("message", {}).get("data") or {}
quotes = data.get("quote_requests") or []
quoted = [q for q in quotes if q.get("name")]
# Find a quote whose detail has a linked Quotation
found_with_quotation = None
for q in quoted:
    st, dbody = request(
        "GET",
        f"/api/method/iranrobot_backend.api.requests.get_my_request_detail?kind=quote&name={q['name']}",
        customer,
    )
    rec = (dbody.get("message", {}).get("data") or {}).get("record") or {}
    if rec.get("erpnext_quotation"):
        found_with_quotation = rec
        break

check("customer1 has at least one converted quote", found_with_quotation is not None)
if found_with_quotation:
    qblock = found_with_quotation.get("quotation")
    check("detail includes 'quotation' block", isinstance(qblock, dict))
    if isinstance(qblock, dict):
        # Customer-safe field allow-list check
        allowed = {
            "quotation_id", "status", "transaction_date", "valid_till",
            "currency", "grand_total_usd", "customer_name", "items",
        }
        extra = set(qblock.keys()) - allowed
        check("quotation block has only customer-safe fields", not extra, extra=f"unexpected_keys={extra}")

        # No internal/admin fields anywhere
        leaks = [k for k in qblock if any(s in k.lower() for s in (
            "base_", "internal", "tax", "discount", "margin", "conversion", "address", "modified_by", "owner"
        ))]
        check("quotation block has no internal/admin fields", not leaks, extra=f"leaks={leaks}")

        items = qblock.get("items") or []
        item_allowed = {"idx", "item_code", "item_name", "description", "qty", "uom", "rate", "amount"}
        if items:
            extra_items = set(items[0].keys()) - item_allowed
            check("quotation item rows are customer-safe", not extra_items, extra=f"extra_keys={extra_items}")

# 4. Customer reading a forged quote id -> NOT_FOUND (no leak)
st, body = request(
    "GET",
    "/api/method/iranrobot_backend.api.requests.get_my_request_detail?kind=quote&name=QR-2026-99999",
    customer,
)
msg = body.get("message", {})
check(
    "forged quote id -> NOT_FOUND",
    (not msg.get("ok")) and (msg.get("error") or {}).get("code") == "NOT_FOUND",
)

# 5. Catalog regression (quick)
st, body = request("GET", "/api/method/iranrobot_backend.api.catalog.get_homepage_catalog", customer)
check("catalog still works", body.get("message", {}).get("ok"))

print()
print(f"{len(PASS)}/{len(PASS) + len(FAIL)} PASSED")
sys.exit(0 if not FAIL else 1)
