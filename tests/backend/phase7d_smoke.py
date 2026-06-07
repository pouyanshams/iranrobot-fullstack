"""Phase 7D HTTP smoke -- customer-side reads + auth boundary on the convert endpoint."""

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
print("Phase 7D HTTP smoke")
print("============================================================\n")

# 1. Guest cannot convert
guest = Jar()
st, body = request("GET", "/api/method/iranrobot_backend.api.auth.whoami", guest)
guest.csrf = (body.get("message", {}).get("data") or {}).get("csrf_token")
st, body = request(
    "POST",
    "/api/method/iranrobot_backend.api.requests.convert_sales_order_to_sales_invoice",
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

# 2. Customer cannot convert
st, body = request(
    "POST",
    "/api/method/iranrobot_backend.api.requests.convert_sales_order_to_sales_invoice",
    customer, {"name": "QR-WHATEVER"},
)
msg = body.get("message", {}) if isinstance(body, dict) else {}
not_permitted = (
    (not msg.get("ok"))
    and (msg.get("error") or {}).get("code") == "NOT_PERMITTED"
) or st in (403, 417)
check("customer convert -> NOT_PERMITTED", not_permitted, extra=f"status={st} body={body}")

# 3. get_my_invoices
st, body = request("GET", "/api/method/iranrobot_backend.api.invoices.get_my_invoices?limit=10", customer)
msg = body.get("message", {})
data = msg.get("data") or {}
invoices = data.get("invoices") or []
check("get_my_invoices returns ok", msg.get("ok"))
print(f"    invoices count: {len(invoices)}")
allowed_list_keys = {
    "name", "status", "posting_date", "due_date", "customer_name",
    "grand_total", "outstanding_amount", "currency", "creation",
    "items_count", "paid_amount", "payment_status",
    "linked_quote_request", "linked_quotation", "linked_sales_order",
}
extra_keys = set()
for inv in invoices:
    extra_keys |= (set(inv.keys()) - allowed_list_keys)
check("invoices payload uses customer-safe allow-list", not extra_keys, extra=f"unexpected={extra_keys}")

# 4. Detail of customer's own invoice
if invoices:
    inv_name = invoices[0]["name"]
    st, body = request(
        "GET",
        f"/api/method/iranrobot_backend.api.invoices.get_my_invoice_detail?name={urllib.parse.quote(inv_name)}",
        customer,
    )
    msg = body.get("message", {})
    rec = (msg.get("data") or {}).get("record") or {}
    check("get_my_invoice_detail returns ok", msg.get("ok"))
    bad_keys = [k for k in rec.keys() if any(
        s in k.lower() for s in ("base_", "tax", "discount", "margin", "internal", "owner", "modified_by", "_user_tags", "address_display", "debit_to", "credit_to", "account")
    )]
    check("no internal/admin fields in invoice detail", not bad_keys, extra=f"leaks={bad_keys}")
    items = rec.get("items") or []
    if items:
        item_bad = [k for k in items[0].keys() if any(
            s in k.lower() for s in ("base_", "tax", "discount", "margin", "valuation", "cost", "income_account", "expense_account")
        )]
        check("no internal/admin fields in invoice item rows", not item_bad)
    payments = rec.get("payments") or []
    if payments:
        pay_bad = [k for k in payments[0].keys() if any(
            s in k.lower() for s in ("bank_account", "owner", "modified_by", "cost_center", "_user_tags", "gateway", "secret", "internal", "gl_")
        )]
        check("no internal/admin fields in payment summary", not pay_bad, extra=f"leaks={pay_bad}")
        check("payment row carries allocated_amount", "allocated_amount" in payments[0])

# 5. Forged invoice id -> NOT_FOUND
st, body = request(
    "GET",
    "/api/method/iranrobot_backend.api.invoices.get_my_invoice_detail?name=ACC-SINV-FAKE-99999",
    customer,
)
msg = body.get("message", {})
check(
    "forged invoice id -> NOT_FOUND",
    (not msg.get("ok")) and (msg.get("error") or {}).get("code") == "NOT_FOUND",
)

# 6. Catalog regression
st, body = request("GET", "/api/method/iranrobot_backend.api.catalog.get_homepage_catalog", customer)
check("catalog still works", body.get("message", {}).get("ok"))

print()
print(f"{len(PASS)}/{len(PASS) + len(FAIL)} PASSED")
sys.exit(0 if not FAIL else 1)
