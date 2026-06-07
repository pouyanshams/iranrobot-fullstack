"""Phase 8D-3 HTTP smoke -- invoice detail wallet_payments boundary.

Focused on the API boundary (auth/ownership/projection). Deep state checks
that require seeding a wallet-paid invoice live in the bench-side smoke
(`iranrobot_backend.commands._phase8d3_smoke.run_all`).
"""

import http.client, json, sys, time, urllib.parse


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


def signup_fresh(label):
    """Best-effort signup; returns (jar, email) or (None, None) when throttled."""
    suffix = str(int(time.time() * 1000))
    email = f"phase8d3_{label}_{suffix}@example.com"
    pwd = "ChangeMe-123-Strong"
    jar = Jar()
    st, body = request("GET", "/api/method/iranrobot_backend.api.auth.whoami", jar)
    jar.csrf = (body.get("message", {}).get("data") or {}).get("csrf_token")
    st, body = request(
        "POST",
        "/api/method/iranrobot_backend.api.auth.signup",
        jar,
        {
            "email": email, "password": pwd, "confirm_password": pwd,
            "first_name": "Phase8D3", "last_name": label,
            "preferred_language": "en",
        },
    )
    msg = body.get("message", {}) if isinstance(body, dict) else {}
    if not msg.get("ok"):
        err_msg = (msg.get("error") or {}).get("message", "")
        if "Throttle" in err_msg:
            return None, None
        raise RuntimeError(f"signup failed for {email}: {body}")
    jar.csrf = (msg.get("data") or {}).get("csrf_token") or jar.csrf
    return jar, email


def call_api(jar, method, path, body=None):
    st, body_json = request(method, path, jar, body)
    msg = body_json.get("message", {}) if isinstance(body_json, dict) else {}
    return st, msg


PASS, FAIL = [], []


def check(label, ok, extra=""):
    if ok:
        PASS.append(label)
        print(f"  ✅ {label}")
    else:
        FAIL.append(label)
        print(f"  ❌ {label} {extra}")


DETAIL = "/api/method/iranrobot_backend.api.invoices.get_my_invoice_detail"


print("============================================================")
print("Phase 8D-3 HTTP smoke -- invoice detail wallet_payments")
print("============================================================\n")


# ---------------------------------------------------------------- [1] guest
print("[1] guest is blocked")
guest = Jar()
st, body = request("GET", "/api/method/iranrobot_backend.api.auth.whoami", guest)
guest.csrf = (body.get("message", {}).get("data") or {}).get("csrf_token")
st, msg = call_api(guest, "GET", DETAIL + "?name=ACC-SINV-FAKE")
check(
    "guest get_my_invoice_detail -> AUTH_REQUIRED",
    (not msg.get("ok")) and (msg.get("error") or {}).get("code") == "AUTH_REQUIRED",
)


# ---------------------------------------------------------------- [2] customer reads their own invoice
print("\n[2] customer detail includes wallet_payments (possibly empty)")
cust, email = signup_fresh("a")
if cust is None:
    print("    (signup throttled -- skipping customer scenarios)")
    print()
    print(f"{len(PASS)}/{len(PASS) + len(FAIL)} PASSED")
    sys.exit(0 if not FAIL else 1)

# Use a non-existent invoice to exercise the NOT_FOUND path.
st, msg = call_api(cust, "GET", DETAIL + "?name=ACC-SINV-DOES-NOT-EXIST")
check(
    "non-existent invoice -> NOT_FOUND",
    (not msg.get("ok")) and (msg.get("error") or {}).get("code") == "NOT_FOUND",
)

# To prove the wallet_payments field is present on a real customer's invoice,
# we fetch the invoice list first; if the customer has any submitted SI,
# we open its detail and assert the shape.
st, msg = call_api(cust, "GET", "/api/method/iranrobot_backend.api.invoices.get_my_invoices?limit=5")
data = msg.get("data") or {}
invoices = data.get("invoices") or []
if invoices:
    first = invoices[0]
    st, msg = call_api(cust, "GET", DETAIL + f"?name={urllib.parse.quote(first['name'])}")
    rec = (msg.get("data") or {}).get("record") or {}
    check(
        "invoice detail has wallet_payments key",
        "wallet_payments" in rec,
        extra=f"keys={list(rec.keys())[:20]}",
    )
    wp = rec.get("wallet_payments") or []
    forbidden = {
        "posted_by", "posted_ip", "idempotency_key", "reason",
        "linked_payment_entry", "owner", "modified_by",
        "modified", "creation", "docstatus", "wallet", "customer",
    }
    leaked = set()
    for row in wp:
        leaked |= set(row.keys()) & forbidden
    check(
        "wallet_payments customer-safe projection (no audit fields)",
        not leaked,
        extra=f"leaked={leaked}",
    )
    # payments (Phase 7D PE-based) must still be present and untouched
    check("payments field still present (Phase 7D regression)", "payments" in rec)
else:
    print("    (no invoices for this fresh customer -- skipping content assertions)")


# ---------------------------------------------------------------- [3] cross-customer NOT_FOUND
print("\n[3] cross-customer NOT_FOUND regression")
cust2, email2 = signup_fresh("b")
if cust2 is None:
    print("    (signup throttled -- skipping cross-customer check)")
else:
    # Use the FIRST customer's invoice name (if any) as a probe.
    if invoices:
        st, msg = call_api(cust2, "GET", DETAIL + f"?name={urllib.parse.quote(invoices[0]['name'])}")
        check(
            "cust2 reading cust1's invoice -> NOT_FOUND",
            (not msg.get("ok")) and (msg.get("error") or {}).get("code") == "NOT_FOUND",
        )


print()
print(f"{len(PASS)}/{len(PASS) + len(FAIL)} PASSED")
sys.exit(0 if not FAIL else 1)
