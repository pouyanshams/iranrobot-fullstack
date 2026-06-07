"""Phase 4.5 backend HTTP smoke -- signup endpoint."""

import http.client
import json
import sys
import time
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
    all_cookies = [v for k, v in resp.getheaders() if k.lower() == "set-cookie"]
    if all_cookies:
        jar.update(all_cookies)
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
print("Phase 4.5 backend smoke -- signup")
print("============================================================\n")

guest = Jar()
# whoami to mint csrf
st, body = request("GET", "/api/method/iranrobot_backend.api.auth.whoami", guest)
msg = body.get("message", {})
guest.csrf = (msg.get("data") or {}).get("csrf_token")
check("guest whoami returns csrf", bool(guest.csrf))

unique_email = f"smoke_signup_{int(time.time() * 1000)}@example.com"

# 1. Valid signup -> auto-login
st, body = request(
    "POST",
    "/api/method/iranrobot_backend.api.auth.signup",
    guest,
    {
        "email": unique_email,
        "password": "ChangeMe-123",
        "confirm_password": "ChangeMe-123",
        "first_name": "Smoke",
        "last_name": "Signup",
        "phone": "09127770001",
        "preferred_language": "en",
    },
)
msg = body.get("message", {})
data = msg.get("data") or {}
auto_login = data.get("auto_login")
authed = data.get("is_authenticated")
user_obj = data.get("user") or {}
check(
    "valid signup returns ok + auto_login + authenticated",
    msg.get("ok") and auto_login and authed,
    extra=f"body={body}",
)
check("signed-up user email matches", user_obj.get("email") == unique_email)
check("signed-up user has linked customer", bool(user_obj.get("customer")))
check("signed-up user has linked contact", bool(user_obj.get("contact")))
check(
    "signed-up user is NOT system manager",
    user_obj.get("is_system_manager") is False,
)
check(
    "signed-up user picked preferred_language=en",
    user_obj.get("preferred_language") == "en",
)
check(
    "phone from signup made it onto Contact",
    user_obj.get("phone", "").endswith("09127770001"),
    extra=f"phone={user_obj.get('phone')}",
)
guest.csrf = (data or {}).get("csrf_token") or guest.csrf

# 2. Same session: can submit a quote (proves session cookie is functional)
st, body = request(
    "POST",
    "/api/method/iranrobot_backend.api.requests.submit_quote_request",
    guest,
    {
        "items": json.dumps(
            [{"robot_product": "aimoga-mornine", "quantity": 1, "mode": "buy"}]
        ),
        "message": "Phase 4.5 smoke submission",
        "language": "en",
    },
)
msg = body.get("message", {})
check("auto-logged-in session can submit a quote", msg.get("ok"))

# 3. Logout fresh session and try duplicate signup
fresh = Jar()
request("GET", "/api/method/iranrobot_backend.api.auth.whoami", fresh)
fresh.csrf = (body.get("message", {}).get("data") or {}).get("csrf_token")
st, body = request("GET", "/api/method/iranrobot_backend.api.auth.whoami", fresh)
fresh.csrf = (body.get("message", {}).get("data") or {}).get("csrf_token")

st, body = request(
    "POST",
    "/api/method/iranrobot_backend.api.auth.signup",
    fresh,
    {
        "email": unique_email,
        "password": "ChangeMe-123",
        "confirm_password": "ChangeMe-123",
        "first_name": "Should",
    },
)
msg = body.get("message", {})
check(
    "duplicate email returns EMAIL_ALREADY_EXISTS",
    (not msg.get("ok")) and (msg.get("error") or {}).get("code") == "EMAIL_ALREADY_EXISTS",
    extra=f"body={body}",
)

# 4. Password mismatch
fresh2 = Jar()
st, body = request("GET", "/api/method/iranrobot_backend.api.auth.whoami", fresh2)
fresh2.csrf = (body.get("message", {}).get("data") or {}).get("csrf_token")
st, body = request(
    "POST",
    "/api/method/iranrobot_backend.api.auth.signup",
    fresh2,
    {
        "email": f"mismatch_{int(time.time() * 1000)}@example.com",
        "password": "ChangeMe-123",
        "confirm_password": "WrongPassword",
        "first_name": "Mismatch",
    },
)
msg = body.get("message", {})
check(
    "password mismatch returns PASSWORD_MISMATCH",
    (not msg.get("ok")) and (msg.get("error") or {}).get("code") == "PASSWORD_MISMATCH",
)

# 5. Too short password
fresh3 = Jar()
st, body = request("GET", "/api/method/iranrobot_backend.api.auth.whoami", fresh3)
fresh3.csrf = (body.get("message", {}).get("data") or {}).get("csrf_token")
st, body = request(
    "POST",
    "/api/method/iranrobot_backend.api.auth.signup",
    fresh3,
    {
        "email": f"short_{int(time.time() * 1000)}@example.com",
        "password": "123",
        "confirm_password": "123",
        "first_name": "Short",
    },
)
msg = body.get("message", {})
check(
    "short password returns PASSWORD_TOO_SHORT",
    (not msg.get("ok")) and (msg.get("error") or {}).get("code") == "PASSWORD_TOO_SHORT",
)

# 6. Bad email -> VALIDATION_ERROR
fresh4 = Jar()
st, body = request("GET", "/api/method/iranrobot_backend.api.auth.whoami", fresh4)
fresh4.csrf = (body.get("message", {}).get("data") or {}).get("csrf_token")
st, body = request(
    "POST",
    "/api/method/iranrobot_backend.api.auth.signup",
    fresh4,
    {
        "email": "not-an-email",
        "password": "ChangeMe-123",
        "confirm_password": "ChangeMe-123",
        "first_name": "Bad",
    },
)
msg = body.get("message", {})
check(
    "bad email returns VALIDATION_ERROR",
    (not msg.get("ok")) and (msg.get("error") or {}).get("code") == "VALIDATION_ERROR",
)

# 7. Role-injection attempt -- ignore extra fields
inject_email = f"inject_{int(time.time() * 1000)}@example.com"
fresh5 = Jar()
st, body = request("GET", "/api/method/iranrobot_backend.api.auth.whoami", fresh5)
fresh5.csrf = (body.get("message", {}).get("data") or {}).get("csrf_token")
st, body = request(
    "POST",
    "/api/method/iranrobot_backend.api.auth.signup",
    fresh5,
    {
        "email": inject_email,
        "password": "ChangeMe-123",
        "confirm_password": "ChangeMe-123",
        "first_name": "Inject",
        # These should be ignored by the whitelisted signature.
        "user_type": "System User",
        "enabled": "1",
        "roles": '["System Manager"]',
        "role_profile_name": "System Manager",
    },
)
msg = body.get("message", {})
data = msg.get("data") or {}
inject_user = data.get("user") or {}
check(
    "role-injection signup still succeeds without escalation",
    msg.get("ok") and inject_user.get("is_system_manager") is False,
)
check(
    "role-injection signup did not become a System Manager",
    inject_user.get("is_system_manager") is False,
)

print()
print(f"{len(PASS)}/{len(PASS) + len(FAIL)} PASSED")
sys.exit(0 if not FAIL else 1)
