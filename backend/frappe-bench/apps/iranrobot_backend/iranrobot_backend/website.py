"""
Phase 4 hotfix -- redirect Website-User customers away from the default
ERPNext/Frappe portal toward the React SPA.

Why:
    After Phase 4 the customer-portal route on iranrobot.localhost still
    renders ERPNext's default sidebar (Projects, Quotations, Orders, ...).
    Most of those rows say "Not Permitted" for a regular Website User
    because we never granted them the underlying roles -- which is the
    correct security posture, but produces a confusing landing page.

    Phase 6 builds the real customer dashboard in React. Until then, this
    hook diverts any Website User that lands on the Frappe portal toward
    the React app so they never see the broken sidebar.

What it does NOT do:
    - It does NOT widen any DocType permission.
    - It does NOT grant any role to Website Users.
    - It does NOT touch Desk -- Administrator / System Manager / any user
      with Desk access flows through untouched.
    - It does NOT touch JSON / API / asset traffic. Only top-level
      HTML GETs are redirected.
"""

import frappe
from werkzeug.exceptions import HTTPException
from werkzeug.wrappers import Response as WerkzeugResponse

# React SPA target (dev). When the SPA moves to a real domain, only this
# constant changes -- the redirect logic stays identical.
REACT_APP_HOME = "http://localhost:5173/#/account"


def _redirect_to(location: str, code: int = 302) -> "HTTPException":
    """Build a Werkzeug HTTPException carrying an explicit redirect Response.

    Why this shape instead of `frappe.Redirect`:

        `frappe.Redirect` only fires a proper Location header when raised
        from inside the website page renderer (`frappe.website.serve`),
        which catches it and delegates to `RedirectPage`. When raised
        from a `before_request` hook the exception falls through to
        `frappe.app.handle_exception`, which renders a 301 *web page* with
        no Location header -- not an actual redirect.

        Frappe's outer `application` catches every `HTTPException` and
        returns it directly (`return e`) -- Werkzeug then converts it to
        the Response we pre-built here. That cleanly bypasses Frappe's
        error renderer.
    """
    body = (
        '<!doctype html><html><head><meta charset="utf-8">'
        '<title>Redirecting</title>'
        f'<meta http-equiv="refresh" content="0; url={location}">'
        '</head><body>'
        f'<p>Redirecting to <a href="{location}">{location}</a> ...</p>'
        '</body></html>'
    )
    response = WerkzeugResponse(
        body,
        status=code,
        headers={
            "Location": location,
            "Cache-Control": "no-store, no-cache, must-revalidate",
        },
        content_type="text/html; charset=utf-8",
    )
    exc = HTTPException(response=response)
    exc.code = code
    return exc

# Path prefixes that must NEVER redirect.
#  - /api/*       : JSON RPC, including our own auth.* methods
#  - /assets/*    : static assets served by Frappe
#  - /files/*     : public file uploads
#  - /private/*   : private file downloads
#  - /method/*    : legacy method dispatch
#  - /socketio    : realtime socket
#  - /app, /app/* : Desk -- staff users should always reach Desk
#  - /login/*     : login + reset URLs
#  - /api/method/iranrobot_backend.* : never redirect our own endpoints
_SKIP_PREFIXES = (
    "/api/",
    "/assets/",
    "/files/",
    "/private/",
    "/method/",
    "/socketio",
    "/app",
    "/login",
)

# Exact paths the redirect leaves alone (login / password-reset flow).
_SKIP_EXACT = {
    "/logout",
    "/update-password",
    "/api/method/login",
    "/api/method/logout",
}


def _is_staff_user(user: str) -> bool:
    """Administrator + anyone with a Desk-bearing role is staff.

    We intentionally do NOT check the full role list -- only the two
    flags that determine "should this user see Frappe Desk". The portal
    redirect is for non-Desk Website Users.
    """
    if user in ("Guest", "Administrator"):
        # Guest stays on the public portal (login page).
        # Administrator obviously stays on Desk.
        return True

    try:
        user_type = frappe.db.get_value("User", user, "user_type")
    except Exception:
        return True  # fail-open: never redirect on lookup errors

    if user_type != "Website User":
        # "System User" -- staff. Leave them alone.
        return True

    return False


def before_request_redirect_customers():
    """Frappe `before_request` hook.

    Runs once per HTTP request, before routing. Re-raises
    `frappe.Redirect` for Website Users hitting the legacy portal.
    Silent no-op for every other case (Guest, staff, API, assets,
    Desk, login flow).
    """
    try:
        request = getattr(frappe.local, "request", None)
        if request is None:
            return

        # Only redirect navigational GETs. POST / PUT / DELETE go straight
        # through -- if it's a form post on the legacy portal, let Frappe
        # handle it and we'll catch the follow-up GET.
        method = (request.method or "").upper()
        if method != "GET":
            return

        path = request.path or "/"

        if path in _SKIP_EXACT:
            return
        for prefix in _SKIP_PREFIXES:
            if path.startswith(prefix):
                return

        user = getattr(frappe.session, "user", None) or "Guest"

        # Guests stay on the portal so they can reach /login if needed.
        # Staff stay on the portal so they can reach /app from there.
        if _is_staff_user(user):
            return

        # This is a Website-User customer landing on the legacy portal.
        # Send them to the React account view via a real HTTP redirect.
        raise _redirect_to(REACT_APP_HOME, code=302)

    except HTTPException:
        # Our own redirect exception (or any HTTPException) goes straight
        # to Frappe's outer handler, which turns it into the response.
        raise
    except Exception:
        # NEVER let this hook break a request. If our logic errors,
        # silently fall through and let Frappe render its usual page.
        try:
            frappe.log_error(
                title="iranrobot portal redirect failed",
                message=frappe.get_traceback(),
            )
        except Exception:
            pass
