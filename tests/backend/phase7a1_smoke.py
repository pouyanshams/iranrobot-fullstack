"""Phase 7A.1 HTTP smoke -- address CRUD as customer1.

The autofill + Desk-visibility checks are run via `bench execute` on
`iranrobot_backend.commands._phase7a1_smoke.run_all` (see that module).
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

    def update(self, headers):
        for raw in headers:
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
print("Phase 7A.1 HTTP smoke -- customer addresses")
print("============================================================\n")

# Login as customer1
jar = Jar()
st, body = request("GET", "/api/method/iranrobot_backend.api.auth.whoami", jar)
jar.csrf = (body.get("message", {}).get("data") or {}).get("csrf_token")
st, body = request(
    "POST",
    "/api/method/iranrobot_backend.api.auth.login",
    jar,
    {"usr": "customer1@example.com", "pwd": "ChangeMe-123"},
)
msg = body.get("message", {})
jar.csrf = (msg.get("data") or {}).get("csrf_token") or jar.csrf
check("login as customer1", msg.get("ok") and (msg.get("data") or {}).get("is_authenticated"))

# 1. List addresses (may already have some from previous runs; we'll clean)
st, body = request("GET", "/api/method/iranrobot_backend.api.account.get_my_addresses", jar)
msg = body.get("message", {})
check("get_my_addresses returns ok", msg.get("ok"))
initial = (msg.get("data") or {}).get("addresses") or []
print(f"    existing addresses: {len(initial)}")

# Clean any previous Phase 7A.1 addresses
for a in initial:
    if "phase7a1-" in (a.get("address_title") or ""):
        request("POST", "/api/method/iranrobot_backend.api.account.delete_my_address", jar, {"name": a["name"]})

# 2. Create a Billing address
st, body = request(
    "POST",
    "/api/method/iranrobot_backend.api.account.save_my_address",
    jar,
    {
        "address_title": "phase7a1-billing",
        "address_type": "Billing",
        "address_line1": "Plot 5, Block 2",
        "address_line2": "Pardis Tech Park",
        "city": "Tehran",
        "state": "Tehran",
        "country": "Iran",
        "pincode": "1659999999",
        "phone": "۰۹۱۲۱۲۳۴۵۶۷",
        "email_id": "billing-7a1@example.com",
        "is_primary_address": "true",
        "is_shipping_address": "false",
    },
)
msg = body.get("message", {})
billing_addr = (msg.get("data") or {}).get("address") or {}
check("create billing address ok", msg.get("ok") and billing_addr.get("name"))
check(
    "phone normalized to ASCII",
    billing_addr.get("phone", "") == "09121234567",
    extra=f"phone={billing_addr.get('phone')}",
)
check(
    "is_primary_address true on the new billing",
    bool(billing_addr.get("is_primary_address")),
)

# 3. List again -> should include this one
st, body = request("GET", "/api/method/iranrobot_backend.api.account.get_my_addresses", jar)
addrs = (body.get("message", {}).get("data") or {}).get("addresses") or []
check("list includes newly created billing", any(a.get("name") == billing_addr.get("name") for a in addrs))

# 4. Create a Shipping address
st, body = request(
    "POST",
    "/api/method/iranrobot_backend.api.account.save_my_address",
    jar,
    {
        "address_title": "phase7a1-shipping",
        "address_type": "Shipping",
        "address_line1": "Industrial Zone, Bldg 12",
        "city": "Isfahan",
        "country": "Iran",
        "pincode": "8158888888",
        "is_shipping_address": "true",
    },
)
msg = body.get("message", {})
shipping_addr = (msg.get("data") or {}).get("address") or {}
check("create shipping address ok", msg.get("ok") and shipping_addr.get("name"))

# 5. Update the billing address (city changes)
st, body = request(
    "POST",
    "/api/method/iranrobot_backend.api.account.save_my_address",
    jar,
    {
        "name": billing_addr["name"],
        "address_title": "phase7a1-billing",
        "address_type": "Billing",
        "address_line1": "Plot 5, Block 2",
        "city": "Shiraz",
        "country": "Iran",
        "pincode": "1659999999",
        "phone": "09121234567",
        "email_id": "billing-7a1@example.com",
        "is_primary_address": "true",
    },
)
msg = body.get("message", {})
updated = (msg.get("data") or {}).get("address") or {}
check("update billing city ok", msg.get("ok") and updated.get("city") == "Shiraz")

# 6. Save with bad country -> VALIDATION_ERROR
st, body = request(
    "POST",
    "/api/method/iranrobot_backend.api.account.save_my_address",
    jar,
    {
        "address_title": "phase7a1-bad",
        "address_line1": "x",
        "city": "x",
        "country": "Mordor",
    },
)
msg = body.get("message", {})
check(
    "bad country -> VALIDATION_ERROR",
    (not msg.get("ok")) and (msg.get("error") or {}).get("code") == "VALIDATION_ERROR",
)

# 7. Update someone else's address -> NOT_FOUND
# Use a clearly forged Address name
st, body = request(
    "POST",
    "/api/method/iranrobot_backend.api.account.save_my_address",
    jar,
    {
        "name": "ADDR-NOT-OURS-99999",
        "address_title": "x",
        "address_line1": "x",
        "city": "x",
        "country": "Iran",
    },
)
msg = body.get("message", {})
check(
    "update foreign address -> NOT_FOUND",
    (not msg.get("ok")) and (msg.get("error") or {}).get("code") == "NOT_FOUND",
)

# 8. Delete shipping
st, body = request(
    "POST",
    "/api/method/iranrobot_backend.api.account.delete_my_address",
    jar,
    {"name": shipping_addr["name"]},
)
msg = body.get("message", {})
check("delete shipping address ok", msg.get("ok"))

# 9. Catalog regression
st, body = request("GET", "/api/method/iranrobot_backend.api.catalog.get_homepage_catalog", jar)
check("catalog still works", body.get("message", {}).get("ok"))

# Cleanup billing too
request("POST", "/api/method/iranrobot_backend.api.account.delete_my_address", jar, {"name": billing_addr["name"]})

print()
print(f"{len(PASS)}/{len(PASS) + len(FAIL)} PASSED")
sys.exit(0 if not FAIL else 1)
