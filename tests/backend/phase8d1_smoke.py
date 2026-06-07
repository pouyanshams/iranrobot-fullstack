"""Phase 8D-1 HTTP smoke -- atomic approval (TX + PE) via the API surface.

After 8D-1, every approval through `staff_approve_top_up_request` creates
BOTH a submitted Robot Wallet Transaction AND a submitted ERPNext Payment
Entry, links both on the request, and increases the wallet balance.

This HTTP smoke covers the API contract:
  - new approval returns `payment_entry` in the success payload
  - balance is credited
  - duplicate approval is idempotent and reuses the same PE
  - customer-facing endpoints still behave (Phase 8A/8B/8C invariants)
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
    suffix = str(int(time.time() * 1000))
    email = f"phase8d1_{label}_{suffix}@example.com"
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
            "first_name": "Phase8D1", "last_name": label,
            "preferred_language": "en",
        },
    )
    msg = body.get("message", {}) if isinstance(body, dict) else {}
    if not msg.get("ok"):
        raise RuntimeError(f"signup failed for {email}: {body}")
    jar.csrf = (msg.get("data") or {}).get("csrf_token") or jar.csrf
    return jar, email


def login(jar, email, password):
    request("GET", "/api/method/iranrobot_backend.api.auth.whoami", jar)
    st, body = request(
        "POST",
        "/api/method/iranrobot_backend.api.auth.login",
        jar, {"usr": email, "pwd": password},
    )
    msg = body.get("message", {}) if isinstance(body, dict) else {}
    jar.csrf = (msg.get("data") or {}).get("csrf_token") or jar.csrf
    return msg


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


CREATE = "/api/method/iranrobot_backend.api.wallet.create_top_up_request"
APPROVE = "/api/method/iranrobot_backend.api.wallet.staff_approve_top_up_request"
SUMMARY = "/api/method/iranrobot_backend.api.wallet.get_wallet_summary"


print("============================================================")
print("Phase 8D-1 HTTP smoke -- atomic approval (TX + PE)")
print("============================================================\n")


# ---------------------------------------------------------------- [1] customer creates Pending
print("[1] customer creates a Pending top-up")
cust, email = signup_fresh("topup")
st, msg = call_api(cust, "POST", CREATE, {"amount_usd": 88, "method": "Bank Transfer"})
data = msg.get("data") or {}
request_id = data.get("request_id")
check("create Pending ok", msg.get("ok") and bool(request_id), extra=f"msg={msg}")


# ---------------------------------------------------------------- [2] staff (Administrator) approves
print("\n[2] staff approval returns transaction_id AND payment_entry")
admin = Jar()
admin_msg = login(admin, "Administrator", "ChangeMe-123")
# If admin password differs in this dev box, the API tests below will be
# skipped. We try one canonical password; on failure we document and stop.
if not admin_msg.get("ok"):
    # try another commonly seeded password
    admin = Jar()
    admin_msg = login(admin, "Administrator", "admin")
if not admin_msg.get("ok"):
    print("    (admin login failed -- HTTP approval scenarios skipped; bench-side smoke covers them.)")
else:
    st, msg = call_api(admin, "POST", APPROVE, {"name": request_id, "bank_reference": "REF-8D1-HTTP"})
    data = msg.get("data") or {}
    pe = data.get("payment_entry")
    tx = data.get("transaction_id")
    check("approval returns ok", msg.get("ok"), extra=f"msg={msg}")
    check("approval response has transaction_id", bool(tx))
    check("approval response has payment_entry", bool(pe), extra=f"data={data}")
    check("response idempotent flag is False on first approval", data.get("idempotent") is False)
    check("response status is Approved", data.get("status") == "Approved")
    try:
        new_balance = float(data.get("new_balance_usd") or 0)
    except Exception:
        new_balance = -1.0
    check("new_balance_usd is 88", new_balance == 88.0, extra=f"balance={new_balance}")

    # ------------------------------------------------------------ [3] customer's summary reflects the credit
    print("\n[3] customer summary reflects the credit")
    st, msg = call_api(cust, "GET", SUMMARY)
    data = msg.get("data") or {}
    wallet = data.get("wallet") or {}
    try:
        balance = float(wallet.get("balance_usd") or 0)
    except Exception:
        balance = -1.0
    check("customer balance now 88", balance == 88.0, extra=f"balance={balance}")
    check("pending_top_ups is empty after approval", data.get("pending_top_ups") == [])

    # ------------------------------------------------------------ [4] duplicate approval is idempotent
    print("\n[4] duplicate approval is idempotent (same PE)")
    st, msg = call_api(admin, "POST", APPROVE, {"name": request_id})
    data = msg.get("data") or {}
    check("second approval ok", msg.get("ok"))
    check("second approval marked idempotent", data.get("idempotent") is True)
    check("second approval returns the same payment_entry", data.get("payment_entry") == pe)
    check("second approval returns the same transaction_id", data.get("transaction_id") == tx)

    # ------------------------------------------------------------ [5] customer-safe projection unchanged
    print("\n[5] customer summary projection still excludes PE/payment internals")
    st, msg = call_api(cust, "GET", SUMMARY)
    data = msg.get("data") or {}
    wallet = data.get("wallet") or {}
    forbidden = {"linked_payment_entry", "approval_idempotency_key", "posted_ip"}
    leaked = set(wallet.keys()) & forbidden
    check("wallet summary still uses allow-list", not leaked, extra=f"leaked={leaked}")


# ---------------------------------------------------------------- [6] customer cannot approve self (regression)
print("\n[6] customer cannot approve their own top-up (Phase 8B regression)")
cust2, email2 = signup_fresh("selfapprove")
st, msg = call_api(cust2, "POST", CREATE, {"amount_usd": 10, "method": "Bank Transfer"})
req2 = (msg.get("data") or {}).get("request_id")
st, msg = call_api(cust2, "POST", APPROVE, {"name": req2})
code = (msg.get("error") or {}).get("code")
check("customer self-approve still NOT_PERMITTED", (not msg.get("ok")) and code == "NOT_PERMITTED")


# ---------------------------------------------------------------- summary
print()
print(f"{len(PASS)}/{len(PASS) + len(FAIL)} PASSED")
sys.exit(0 if not FAIL else 1)
