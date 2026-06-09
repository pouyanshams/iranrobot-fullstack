"""Phase 4 -- Customer authentication APIs.

All methods follow the project response envelope `{ok, data, error}` (see
`_response.py`). The five whitelisted methods:

    iranrobot_backend.api.auth.signup(...)             POST  allow_guest=True  (Phase 4.5)
    iranrobot_backend.api.auth.login(usr, pwd)         POST  allow_guest=True
    iranrobot_backend.api.auth.logout()                POST  auth required
    iranrobot_backend.api.auth.whoami()                GET   allow_guest=True
    iranrobot_backend.api.auth.update_profile(...)     POST  auth required

The login wrapper calls Frappe's built-in `LoginManager` rather than re-
implementing password verification + session management. The whoami endpoint
lazily creates the ERPNext Contact + Customer pair (one Customer per User)
the first time it is called by a newly-authenticated visitor, per the Phase
3.5 architecture decision.

Phase 4.5 signup creates a Website User (no Desk roles), then auto-logs the
new account in via the same LoginManager + post_login chain login() uses, and
pipes through whoami() so the SPA gets a fully hydrated session payload in a
single round trip.
"""

import re

import frappe
from frappe import _

from iranrobot_backend.api._response import ok, err
from iranrobot_backend.api._session import (
    get_contact_summary,
    get_csrf_token,
    get_customer_summary,
    get_or_create_customer_for_user,
    is_guest,
    is_system_manager,
    safe_user_payload,
)


# ---------------------------------------------------------------------------
# whoami -- the single source of truth for "what does the client know about
# the current session". Idempotent; safe to call on every page load.
# ---------------------------------------------------------------------------

@frappe.whitelist(allow_guest=True)
def whoami():
    csrf_token = get_csrf_token()

    if is_guest():
        return ok({
            "is_authenticated": False,
            "user": None,
            "csrf_token": csrf_token,
        })

    user_email = frappe.session.user

    try:
        contact_name, customer_name = get_or_create_customer_for_user(user_email)
        # Lazy creation may have written to the DB; commit so the rows survive
        # request rollback semantics if the caller does anything unexpected.
        frappe.db.commit()
    except Exception as e:
        # Don't fail the whoami call on lazy-creation issues -- just surface
        # the auth state without a contact/customer. The next call retries.
        frappe.log_error(title="auth.whoami lazy-create", message=f"user={user_email}\n{e}")
        contact_name, customer_name = None, None

    user_payload = safe_user_payload(user_email)
    contact_summary = get_contact_summary(contact_name) if contact_name else {}
    customer_summary = get_customer_summary(customer_name) if customer_name else {}

    return ok({
        "is_authenticated": True,
        "user": {
            **user_payload,
            "phone": contact_summary.get("phone", ""),
            "marketing_opt_in": contact_summary.get("marketing_opt_in", True),
            "contact": contact_name,
            "customer": customer_name,
            "customer_name": customer_summary.get("customer_name"),
            "is_system_manager": is_system_manager(user_email),
        },
        "csrf_token": csrf_token,
    })


# ---------------------------------------------------------------------------
# login -- wraps Frappe's LoginManager.authenticate() + post_login(), then
# pipes through whoami() so the client gets the rotated CSRF + freshly-
# created Contact/Customer in one round trip.
# ---------------------------------------------------------------------------

@frappe.whitelist(allow_guest=True, methods=["POST"])
def login(usr: str | None = None, pwd: str | None = None):
    if not usr or not pwd:
        return err("VALIDATION_ERROR", _("Email and password are required."))

    try:
        from frappe.auth import LoginManager
        lm = LoginManager()
        lm.authenticate(user=usr, pwd=pwd)
        lm.post_login()
    except frappe.AuthenticationError:
        return err("INVALID_CREDENTIALS", _("Invalid email or password."))
    except frappe.SecurityException as e:
        # rate-limit / lockout from LoginManager
        return err("RATE_LIMITED", str(e) or _("Too many login attempts. Try again later."))
    except Exception as e:
        frappe.log_error(title="auth.login server error", message=f"user={usr}\n{e}")
        return err("SERVER_ERROR", _("Could not complete login."))

    # Lazy-create Contact + Customer immediately after login so the SPA's
    # follow-up whoami() never sees a half-state.
    try:
        get_or_create_customer_for_user(frappe.session.user)
        frappe.db.commit()
    except Exception as e:
        # Auth succeeded; surface the warning but don't fail the login.
        frappe.log_error(title="auth.login lazy-create", message=f"user={frappe.session.user}\n{e}")

    # Return the same shape whoami() returns so the client can transition state
    # without an extra round trip.
    return whoami()


# ---------------------------------------------------------------------------
# logout -- clears the Frappe session and the sid cookie.
# ---------------------------------------------------------------------------

@frappe.whitelist(methods=["POST"])
def logout():
    if is_guest():
        # Idempotent: logging out an already-guest session is fine.
        return ok({"is_authenticated": False, "user": None, "csrf_token": get_csrf_token()})

    user_email = frappe.session.user
    try:
        from frappe.auth import LoginManager
        lm = LoginManager()
        lm.logout(user=user_email)
        frappe.db.commit()
    except Exception as e:
        frappe.log_error(title="auth.logout server error", message=f"user={user_email}\n{e}")
        return err("SERVER_ERROR", _("Could not complete logout."))

    return ok({
        "is_authenticated": False,
        "user": None,
        "csrf_token": get_csrf_token(),
    })


# ---------------------------------------------------------------------------
# update_profile -- patches safe fields on User + Contact for the *current*
# authenticated user. All updates flow through allow-listed field names so a
# client can't escalate roles or flip enabled/user_type.
# ---------------------------------------------------------------------------

# Persian digit table for phone normalization
_PERSIAN_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
_PHONE_RE = re.compile(r"^[0-9+\-\s]{7,}$")


@frappe.whitelist(methods=["POST"])
def update_profile(
    first_name: str | None = None,
    last_name: str | None = None,
    full_name: str | None = None,
    phone: str | None = None,
    preferred_language: str | None = None,
    marketing_opt_in: bool | str | None = None,
):
    if is_guest():
        return err("AUTH_REQUIRED", _("You must be logged in."))

    user_email = frappe.session.user
    contact_name, customer_name = get_or_create_customer_for_user(user_email)

    # ---- User fields (first_name, last_name, full_name, language) ----
    user_doc = frappe.get_doc("User", user_email)
    user_dirty = False

    if first_name is not None:
        user_doc.first_name = (first_name or "").strip()
        user_dirty = True
    if last_name is not None:
        user_doc.last_name = (last_name or "").strip()
        user_dirty = True
    if full_name is not None and not (first_name or last_name):
        # If only full_name was sent, naively split on the first whitespace
        parts = (full_name or "").strip().split(None, 1)
        user_doc.first_name = parts[0] if parts else ""
        user_doc.last_name = parts[1] if len(parts) > 1 else ""
        user_dirty = True
    if preferred_language is not None:
        lang = (preferred_language or "").strip().lower()
        if lang in ("fa", "en"):
            user_doc.language = lang
            user_dirty = True

    if user_dirty:
        try:
            user_doc.save(ignore_permissions=True)
        except frappe.ValidationError as e:
            return err("VALIDATION_ERROR", str(e))

    # ---- Contact fields (phone via phone_nos child table, unsubscribed) ----
    contact_doc = frappe.get_doc("Contact", contact_name)
    contact_dirty = False

    if phone is not None:
        phone_norm = (phone or "").translate(_PERSIAN_DIGITS).strip()
        if phone_norm and not _PHONE_RE.match(phone_norm):
            return err("VALIDATION_ERROR", _("Phone number format is invalid."))
        # ERPNext Contact stores phone numbers in the `phone_nos` child table.
        # The parent's `mobile_no` / `phone` Data fields are read-only and get
        # synchronized from the row with `is_primary_mobile_no = 1` during
        # before_save. So we update / insert the primary mobile row instead.
        primary_row = next(
            (r for r in (contact_doc.phone_nos or []) if r.is_primary_mobile_no),
            None,
        )
        if primary_row:
            primary_row.phone = phone_norm
        elif phone_norm:
            contact_doc.append("phone_nos", {
                "phone": phone_norm,
                "is_primary_mobile_no": 1,
                "is_primary_phone": 1,
            })
        contact_dirty = True

    if marketing_opt_in is not None:
        # Accept bool or "true"/"false"/"1"/"0"
        v = marketing_opt_in
        if isinstance(v, str):
            v = v.strip().lower() in ("1", "true", "yes", "on")
        contact_doc.unsubscribed = 0 if v else 1
        contact_dirty = True

    if contact_dirty:
        try:
            contact_doc.save(ignore_permissions=True)
        except frappe.ValidationError as e:
            return err("VALIDATION_ERROR", str(e))

    if user_dirty or contact_dirty:
        frappe.db.commit()

    # Return the refreshed whoami payload so the client updates its state in one go.
    return whoami()


# ---------------------------------------------------------------------------
# Phase 4.5 -- signup. Creates a Website User + auto-logs them in.
#
# Hardening notes:
#   - user_type is HARD-CODED to "Website User"; we never accept it from the
#     client.
#   - No roles are assigned beyond Frappe's default Guest -> Website User
#     auto-attachment; we never touch the `roles` table.
#   - send_welcome_email = 0 (no SMTP wired up yet).
#   - TODO(prod hardening): captcha + per-IP rate limit. Frappe's built-in
#     ratelimit decorator can be layered when an HTTP-level rate is decided.
# ---------------------------------------------------------------------------

_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
_MIN_PASSWORD_LEN = 8


@frappe.whitelist(allow_guest=True, methods=["POST"])
def signup(
    email: str | None = None,
    password: str | None = None,
    confirm_password: str | None = None,
    first_name: str | None = None,
    last_name: str | None = None,
    phone: str | None = None,
    preferred_language: str | None = None,
):
    # ---- input normalization + validation --------------------------------
    email_norm = (email or "").strip().lower()
    first_norm = (first_name or "").strip()
    last_norm = (last_name or "").strip()
    phone_norm = (phone or "").translate(_PERSIAN_DIGITS).strip()
    lang_norm = (preferred_language or "").strip().lower()

    if not email_norm or not _EMAIL_RE.match(email_norm):
        return err("VALIDATION_ERROR", _("Please enter a valid email address."))
    if not first_norm:
        return err("VALIDATION_ERROR", _("First name is required."))
    if not password or not confirm_password:
        return err("VALIDATION_ERROR", _("Password is required."))
    if password != confirm_password:
        return err("PASSWORD_MISMATCH", _("Passwords do not match."))
    if len(password) < _MIN_PASSWORD_LEN:
        return err(
            "PASSWORD_TOO_SHORT",
            _("Password must be at least {0} characters.").format(_MIN_PASSWORD_LEN),
        )
    if phone_norm and not _PHONE_RE.match(phone_norm):
        return err("VALIDATION_ERROR", _("Phone number format is invalid."))
    if lang_norm and lang_norm not in ("fa", "en"):
        lang_norm = "fa"

    # ---- duplicate check -------------------------------------------------
    if frappe.db.exists("User", email_norm):
        return err("EMAIL_ALREADY_EXISTS", _("An account with this email already exists."))

    # ---- create the User (Website User, no Desk access) ------------------
    try:
        # Authenticate as Administrator just for the duration of the insert so
        # the @frappe.whitelist guest session can write to the `User` table
        # without us having to widen its DocType permissions. We restore the
        # guest user immediately so the subsequent login_user() call rotates
        # the session correctly.
        original_user = frappe.session.user
        frappe.set_user("Administrator")
        try:
            user_doc = frappe.get_doc({
                "doctype": "User",
                "email": email_norm,
                "first_name": first_norm,
                "last_name": last_norm,
                "send_welcome_email": 0,
                "enabled": 1,
                "user_type": "Website User",
                "new_password": password,
                "language": lang_norm or "fa",
            })
            # Belt + suspenders: even if someone manages to slip a roles array
            # into the construction call above, clear it so the new user gets
            # only Frappe's default Website-User role attachment.
            user_doc.roles = []
            user_doc.insert(ignore_permissions=True)
        finally:
            frappe.set_user(original_user)

        frappe.db.commit()
    except frappe.DuplicateEntryError:
        return err("EMAIL_ALREADY_EXISTS", _("An account with this email already exists."))
    except frappe.ValidationError as e:
        return err("VALIDATION_ERROR", str(e))
    except Exception as e:
        frappe.log_error(title="auth.signup server error", message=f"email={email_norm}\n{e}")
        return err("SERVER_ERROR", _("Could not complete signup."))

    # ---- auto-login -----------------------------------------------------
    # Drive a real password-verify through LoginManager so the session cookie
    # is rotated and the new whoami() call returns the authenticated payload.
    try:
        from frappe.auth import LoginManager
        lm = LoginManager()
        lm.authenticate(user=email_norm, pwd=password)
        lm.post_login()
    except frappe.AuthenticationError:
        # Should not happen -- we just wrote the password. Treat as soft
        # failure: signup succeeded, user must log in manually.
        frappe.log_error(
            title="auth.signup auto-login auth error",
            message=f"user={email_norm}",
        )
        return ok({
            "is_authenticated": False,
            "user": None,
            "csrf_token": get_csrf_token(),
            "auto_login": False,
            "email": email_norm,
        })
    except Exception as e:
        frappe.log_error(
            title="auth.signup auto-login server error",
            message=f"user={email_norm}\n{e}",
        )
        # Same soft-failure path -- the account was created; the client can
        # surface a "please log in" message instead of failing the whole flow.
        return ok({
            "is_authenticated": False,
            "user": None,
            "csrf_token": get_csrf_token(),
            "auto_login": False,
            "email": email_norm,
        })

    # Lazy-create Contact + Customer immediately so the whoami() right below
    # never sees a half-state. Then -- and only then -- write the phone we
    # collected at signup, because Frappe's User.after_insert hooks don't
    # consistently create a Contact for new Website Users in v15; the canonical
    # creation path is our own get_or_create_customer_for_user helper.
    try:
        contact_name, _customer_name = get_or_create_customer_for_user(frappe.session.user)
        if phone_norm and contact_name:
            try:
                c = frappe.get_doc("Contact", contact_name)
                already_has = any(r.is_primary_mobile_no for r in (c.phone_nos or []))
                if not already_has:
                    c.append("phone_nos", {
                        "phone": phone_norm,
                        "is_primary_mobile_no": 1,
                        "is_primary_phone": 1,
                    })
                    c.save(ignore_permissions=True)
            except Exception as e:
                # Phone write is best-effort -- never fail the signup over this.
                frappe.log_error(
                    title="auth.signup phone write",
                    message=f"user={frappe.session.user}\n{e}",
                )
        frappe.db.commit()
    except Exception as e:
        frappe.log_error(title="auth.signup lazy-create", message=f"user={frappe.session.user}\n{e}")

    payload = whoami()
    # Add the `auto_login=True` flag so the SPA can tell signup-with-auto-login
    # apart from a plain login response (they share the whoami envelope shape).
    if payload.get("ok"):
        payload["data"]["auto_login"] = True
    return payload
