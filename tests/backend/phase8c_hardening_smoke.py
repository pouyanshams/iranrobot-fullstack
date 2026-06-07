"""Phase 8C HTTP smoke -- backend hardening.

Three small hardening items shipped alongside Phase 8C's frontend rewrite:

    1. `TOO_MANY_PENDING`: a customer may not have more than
       _MAX_PENDING_PER_WALLET (=5) simultaneous Pending top-up requests.
    2. `cancelled_ip`: when a customer cancels a Pending top-up, the request
       row's `cancelled_ip` snapshot is filled (audit-only; not customer-safe).
    3. `linked_payment_entry` is reserved for the future accounting-hardening
       phase. NO write to that field is allowed -- not from API, not from
       Desk, not from bench. The smoke confirms the controller throws.

Item #3 is exercised via direct ORM (bench-side intent), but since this
HTTP smoke runs externally we can only fully test it via a separate
`bench execute` step. The HTTP portion covers items #1 and #2.
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
    email = f"phase8c_{label}_{suffix}@example.com"
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
            "first_name": "Phase8C", "last_name": label,
            "preferred_language": "en",
        },
    )
    msg = body.get("message", {}) if isinstance(body, dict) else {}
    if not msg.get("ok"):
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


CREATE = "/api/method/iranrobot_backend.api.wallet.create_top_up_request"
CANCEL = "/api/method/iranrobot_backend.api.wallet.cancel_top_up_request"
LIST = "/api/method/iranrobot_backend.api.wallet.get_my_top_up_requests"


print("============================================================")
print("Phase 8C HTTP smoke -- backend hardening")
print("============================================================\n")

# ---------------------------------------------------------------- [1] TOO_MANY_PENDING
print("[1] max 5 simultaneous Pending top-up requests")
cust, email = signup_fresh("flood")

names = []
for i in range(5):
    st, msg = call_api(cust, "POST", CREATE, {"amount_usd": 10 + i, "method": "Bank Transfer"})
    if msg.get("ok"):
        names.append((msg.get("data") or {}).get("request_id"))
check("5 Pending top-ups created successfully", len(names) == 5, extra=f"got {len(names)} names")

# 6th must be rejected with TOO_MANY_PENDING
st, msg = call_api(cust, "POST", CREATE, {"amount_usd": 99, "method": "Bank Transfer"})
got = (msg.get("error") or {}).get("code")
check("6th Pending -> TOO_MANY_PENDING", (not msg.get("ok")) and got == "TOO_MANY_PENDING", extra=f"got={got} msg={msg}")

# Cancel one, then the next create should succeed again
if names:
    st, msg = call_api(cust, "POST", CANCEL, {"name": names[0]})
    check("cancel one Pending -> ok", msg.get("ok"), extra=f"msg={msg}")

st, msg = call_api(cust, "POST", CREATE, {"amount_usd": 77, "method": "Bank Transfer"})
check(
    "after cancelling one slot, create succeeds again",
    msg.get("ok"),
    extra=f"msg={msg}",
)


# ---------------------------------------------------------------- [2] cancelled_ip snapshot
print("\n[2] cancel records cancelled_ip on the row")
cust2, email2 = signup_fresh("ipsnap")

st, msg = call_api(cust2, "POST", CREATE, {"amount_usd": 25, "method": "Bank Transfer"})
data = msg.get("data") or {}
target = data.get("request_id")
check("create Pending for cancel-ip test", bool(target), extra=f"msg={msg}")

if target:
    st, msg = call_api(cust2, "POST", CANCEL, {"name": target})
    check("cancel ok", msg.get("ok"), extra=f"msg={msg}")
    # cancelled_ip is NOT in the customer-safe projection; we can only
    # verify the field's presence via the list endpoint allow-list NOT
    # containing it. We rely on a bench-side check for the value itself.
    st, msg = call_api(cust2, "GET", LIST + "?limit=50")
    rows = (msg.get("data") or {}).get("top_up_requests") or []
    row = next((r for r in rows if r.get("name") == target), {})
    leaked = "cancelled_ip" in row
    check("cancelled_ip is NOT in customer-safe projection", not leaked, extra=f"row keys={list(row.keys())}")


# ---------------------------------------------------------------- summary
print()
print(f"{len(PASS)}/{len(PASS) + len(FAIL)} PASSED")
sys.exit(0 if not FAIL else 1)
