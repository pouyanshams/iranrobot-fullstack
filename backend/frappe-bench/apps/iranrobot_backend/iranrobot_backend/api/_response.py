"""Shared response envelope helpers for public API methods.

All Phase 2+ public methods return either ok() or err(). Frappe's whitelist
decorator wraps the return value in `{"message": <value>}` when accessed via
/api/method/, so the actual HTTP body looks like:

    { "message": { "ok": true,  "data": {...}, "message": "Success" } }
    { "message": { "ok": false, "error": { "code": "...", "message": "..." } } }

We accept that outer wrapping; the inner envelope stays consistent.
"""


def ok(data, message="Success"):
    return {"ok": True, "data": data, "message": message}


def err(code, message):
    return {"ok": False, "error": {"code": code, "message": message}}
