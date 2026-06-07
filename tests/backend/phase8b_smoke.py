"""Phase 8B HTTP smoke -- customer top-up create/cancel + staff approve/reject boundary.

This smoke covers everything reachable from HTTP -- guest blocking, customer
flow, cross-customer NOT_FOUND, customer-cannot-self-approve, customer-safe
projection, and the `get_wallet_summary` extension (pending_top_ups +
can_top_up=true).

The deeper assertions (idempotency_key uniqueness, ledger SUM, the cache
invariant, the manual-Spend role guard) live in the bench-side smoke at
`iranrobot_backend.commands._phase8b_smoke.run_all` because they require
Administrator-side calls.

All test users are freshly signed up inline -- no dependency on customer1.
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
    """Sign up a fresh user and return a logged-in Jar + the email used."""
    suffix = str(int(time.time() * 1000))
    email = f"phase8b_{label}_{suffix}@example.com"
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
            "first_name": "Phase8B", "last_name": label,
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


print("============================================================")
print("Phase 8B HTTP smoke")
print("============================================================\n")

CREATE = "/api/method/iranrobot_backend.api.wallet.create_top_up_request"
CANCEL = "/api/method/iranrobot_backend.api.wallet.cancel_top_up_request"
APPROVE = "/api/method/iranrobot_backend.api.wallet.staff_approve_top_up_request"
REJECT = "/api/method/iranrobot_backend.api.wallet.staff_reject_top_up_request"
SUMMARY = "/api/method/iranrobot_backend.api.wallet.get_wallet_summary"
LIST = "/api/method/iranrobot_backend.api.wallet.get_my_top_up_requests"


# ---------------------------------------------------------------- [1] guest blocking
print("[1] guest cannot create / cancel / list top-ups")
guest = Jar()
st, body = request("GET", "/api/method/iranrobot_backend.api.auth.whoami", guest)
guest.csrf = (body.get("message", {}).get("data") or {}).get("csrf_token")

st, msg = call_api(guest, "POST", CREATE, {"amount_usd": 100, "method": "Bank Transfer"})
check(
    "guest create_top_up_request -> AUTH_REQUIRED",
    (not msg.get("ok")) and (msg.get("error") or {}).get("code") == "AUTH_REQUIRED",
    extra=f"status={st} msg={msg}",
)
st, msg = call_api(guest, "POST", CANCEL, {"name": "WTR-NONE"})
check(
    "guest cancel_top_up_request -> AUTH_REQUIRED",
    (not msg.get("ok")) and (msg.get("error") or {}).get("code") == "AUTH_REQUIRED",
)
st, msg = call_api(guest, "GET", LIST)
check(
    "guest get_my_top_up_requests -> AUTH_REQUIRED",
    (not msg.get("ok")) and (msg.get("error") or {}).get("code") == "AUTH_REQUIRED",
)


# ---------------------------------------------------------------- [2] customer create
print("\n[2] customer can create a Pending top-up")
cust1, email1 = signup_fresh("alpha")

# Pre: summary should report can_top_up=true and an empty pending list (or whatever pre-existed for a fresh signup, which is 0).
st, msg = call_api(cust1, "GET", SUMMARY)
data_before = msg.get("data") or {}
check("fresh signup get_wallet_summary ok", msg.get("ok"))
check("fresh signup can_top_up=true (Phase 8B contract)", data_before.get("can_top_up") is True, extra=f"data={data_before}")
check("fresh signup can_spend=false (no 8D yet)", data_before.get("can_spend") is False)
check("fresh signup pending_top_ups present + empty", data_before.get("pending_top_ups") == [], extra=f"pending={data_before.get('pending_top_ups')}")
try:
    balance_before = float((data_before.get("wallet") or {}).get("balance_usd") or 0)
except Exception:
    balance_before = -1.0
check("fresh signup balance is 0", balance_before == 0.0, extra=f"balance={balance_before}")

st, msg = call_api(cust1, "POST", CREATE, {"amount_usd": 250, "method": "Bank Transfer", "customer_note": "phase8b alpha"})
data_create = msg.get("data") or {}
check("create_top_up_request ok", msg.get("ok"), extra=f"msg={msg}")
check("response carries request_id", bool(data_create.get("request_id")), extra=f"data={data_create}")
check("response status is Pending", data_create.get("status") == "Pending")
check("response carries instructions.reference == request_id", (data_create.get("instructions") or {}).get("reference") == data_create.get("request_id"))
check("response carries instructions.beneficiary", bool((data_create.get("instructions") or {}).get("beneficiary")))
request_alpha = data_create.get("request_id")


# ---------------------------------------------------------------- [3] pending does not affect balance
print("\n[3] pending top-up does NOT change wallet balance")
st, msg = call_api(cust1, "GET", SUMMARY)
data_after = msg.get("data") or {}
try:
    balance_after = float((data_after.get("wallet") or {}).get("balance_usd") or 0)
except Exception:
    balance_after = -1.0
check("balance unchanged after Pending create", balance_after == balance_before == 0.0, extra=f"before={balance_before} after={balance_after}")
pending_names = [r.get("name") for r in (data_after.get("pending_top_ups") or [])]
check("summary.pending_top_ups now includes the new request", request_alpha in pending_names, extra=f"pending={pending_names}")
# Confirm pending_top_ups projection does not leak admin fields
pending_first = (data_after.get("pending_top_ups") or [{}])[0]
forbidden_topup = {"user", "customer", "wallet", "approval_idempotency_key", "posted_ip", "linked_payment_entry", "approved_by", "rejected_by", "cancelled_by", "owner", "modified_by", "modified", "creation", "docstatus", "naming_series"}
leak = set(pending_first.keys()) & forbidden_topup
check("pending_top_ups projection excludes audit/internal fields", not leak, extra=f"leak={leak}")


# ---------------------------------------------------------------- [4] validation
print("\n[4] invalid input rejected")
for label, body, code in (
    ("amount 0",        {"amount_usd": 0, "method": "Bank Transfer"},     "VALIDATION_ERROR"),
    ("amount negative", {"amount_usd": -5, "method": "Bank Transfer"},    "VALIDATION_ERROR"),
    ("amount too big",  {"amount_usd": 100000000, "method": "Bank Transfer"}, "VALIDATION_ERROR"),
    ("amount missing",  {"method": "Bank Transfer"},                      "VALIDATION_ERROR"),
    ("bad method",      {"amount_usd": 50, "method": "Gateway"},          "VALIDATION_ERROR"),
):
    st, msg = call_api(cust1, "POST", CREATE, body)
    got = (msg.get("error") or {}).get("code")
    check(f"create with {label} -> VALIDATION_ERROR", (not msg.get("ok")) and got == code, extra=f"got={got} body={body}")


# ---------------------------------------------------------------- [5] customer cancel
print("\n[5] customer can cancel own Pending; cannot cancel non-Pending")
# Create a second top-up to cancel without disturbing request_alpha.
st, msg = call_api(cust1, "POST", CREATE, {"amount_usd": 60, "method": "Bank Transfer"})
data = msg.get("data") or {}
request_cancel = data.get("request_id")
check("seed a second Pending for cancel test", bool(request_cancel))

st, msg = call_api(cust1, "POST", CANCEL, {"name": request_cancel})
data = msg.get("data") or {}
check("cancel own Pending -> ok", msg.get("ok"), extra=f"msg={msg}")
check("cancelled response carries status=Cancelled", data.get("status") == "Cancelled")

# Cancel again -> STATUS_NOT_CANCELLABLE
st, msg = call_api(cust1, "POST", CANCEL, {"name": request_cancel})
got = (msg.get("error") or {}).get("code")
check("cancel-already-cancelled -> STATUS_NOT_CANCELLABLE", (not msg.get("ok")) and got == "STATUS_NOT_CANCELLABLE", extra=f"got={got}")


# ---------------------------------------------------------------- [6] customer cannot approve/reject self
print("\n[6] customer cannot approve or reject their own request")
st, msg = call_api(cust1, "POST", APPROVE, {"name": request_alpha})
got = (msg.get("error") or {}).get("code")
check("customer approve self -> NOT_PERMITTED", (not msg.get("ok")) and got == "NOT_PERMITTED", extra=f"got={got}")
st, msg = call_api(cust1, "POST", REJECT, {"name": request_alpha, "reason": "phase8b"})
got = (msg.get("error") or {}).get("code")
check("customer reject self -> NOT_PERMITTED", (not msg.get("ok")) and got == "NOT_PERMITTED", extra=f"got={got}")


# ---------------------------------------------------------------- [7] cross-customer
print("\n[7] cross-customer access returns NOT_FOUND (no 403, no leak)")
cust2, email2 = signup_fresh("beta")

st, msg = call_api(cust2, "POST", CANCEL, {"name": request_alpha})
got = (msg.get("error") or {}).get("code")
check("cust2 cancel cust1's request -> NOT_FOUND", (not msg.get("ok")) and got == "NOT_FOUND", extra=f"got={got}")

st, msg = call_api(cust2, "GET", LIST)
data = msg.get("data") or {}
names_cust2 = {r.get("name") for r in (data.get("top_up_requests") or [])}
check("cust2 list does NOT include cust1's request_alpha", request_alpha not in names_cust2)

st, msg = call_api(cust2, "GET", SUMMARY)
data = msg.get("data") or {}
pending_cust2 = [r.get("name") for r in (data.get("pending_top_ups") or [])]
check("cust2 pending list does NOT include cust1's request_alpha", request_alpha not in pending_cust2)


# ---------------------------------------------------------------- [8] customer-safe projection on list
print("\n[8] customer-safe projection on get_my_top_up_requests")
st, msg = call_api(cust1, "GET", LIST + "?limit=50")
data = msg.get("data") or {}
rows = data.get("top_up_requests") or []
check("get_my_top_up_requests ok", msg.get("ok"))
allowed = {
    "name", "status", "amount_usd", "currency", "method",
    "submitted_at", "approved_at", "rejected_at", "cancelled_at",
    "customer_note", "bank_reference", "rejection_reason",
    "linked_transaction",
}
extra_keys, leak_keys = set(), set()
for r in rows:
    extra_keys |= set(r.keys()) - allowed
    leak_keys |= set(r.keys()) & forbidden_topup
check("list rows use allow-list", not extra_keys, extra=f"extra={extra_keys}")
check("list rows do NOT expose audit fields", not leak_keys, extra=f"leak={leak_keys}")


# ---------------------------------------------------------------- [9] non-existent request
print("\n[9] non-existent name -> NOT_FOUND on cancel")
st, msg = call_api(cust1, "POST", CANCEL, {"name": "WTR-DOES-NOT-EXIST"})
got = (msg.get("error") or {}).get("code")
check("cancel non-existent -> NOT_FOUND", (not msg.get("ok")) and got == "NOT_FOUND", extra=f"got={got}")


# ---------------------------------------------------------------- [10] staff endpoints reject customer
print("\n[10] staff endpoints reject a logged-in customer caller (role check)")
st, msg = call_api(cust2, "POST", APPROVE, {"name": request_alpha})
got = (msg.get("error") or {}).get("code")
# cust2 is a Website User without Accounts roles -- NOT_PERMITTED expected
check("cust2 approve someone else's request -> NOT_PERMITTED", (not msg.get("ok")) and got == "NOT_PERMITTED", extra=f"got={got}")
st, msg = call_api(cust2, "POST", REJECT, {"name": request_alpha, "reason": "phase8b"})
got = (msg.get("error") or {}).get("code")
check("cust2 reject someone else's request -> NOT_PERMITTED", (not msg.get("ok")) and got == "NOT_PERMITTED", extra=f"got={got}")


# ---------------------------------------------------------------- summary
print()
print(f"{len(PASS)}/{len(PASS) + len(FAIL)} PASSED")
sys.exit(0 if not FAIL else 1)
