"""Phase 8C bench-side hardening smoke.

Covers the two hardening checks that need direct ORM access:

    A. cancelled_ip is set to a non-empty string on cancelled rows.
    B. linked_payment_entry is reserved -- no insert OR update may set it.

Run via::

    bench --site iranrobot.localhost execute \\
        iranrobot_backend.commands._phase8c_hardening_smoke.run_all
"""

from __future__ import annotations

import json
import secrets

import frappe


def emit(payload):
    print("PHASE8C::" + json.dumps(payload, default=str))


def _fresh_customer():
    from iranrobot_backend.api.auth import signup
    from iranrobot_backend.api._session import (
        get_or_create_customer_for_user,
        get_or_create_wallet_for_customer,
    )

    suffix = secrets.token_hex(4)
    email = f"phase8c_{suffix}@example.com"
    pwd = "ChangeMe-123-Strong"
    original = frappe.session.user
    frappe.set_user("Guest")
    try:
        res = signup(email=email, password=pwd, confirm_password=pwd,
                     first_name="Phase8C", last_name="Hardening")
    finally:
        frappe.set_user(original)
    if not res.get("ok"):
        raise RuntimeError(f"signup failed for {email}: {res}")
    _contact, cust = get_or_create_customer_for_user(email)
    wallet = get_or_create_wallet_for_customer(cust)
    frappe.db.commit()
    return email, cust, wallet


class _SetUser:
    def __init__(self, target):
        self.target = target
        self._previous = None
    def __enter__(self):
        self._previous = frappe.session.user
        frappe.set_user(self.target)
        return self
    def __exit__(self, exc_type, exc, tb):
        frappe.set_user(self._previous)


def _create_pending(email, amount=15):
    from iranrobot_backend.api.wallet import create_top_up_request
    with _SetUser(email):
        # The API reads frappe.local.request_ip; in bench we don't have one
        # so the snapshot will be "". We patch it for these tests.
        frappe.local.request_ip = "203.0.113.7"
        try:
            res = create_top_up_request(amount_usd=amount, method="Bank Transfer")
        finally:
            try:
                del frappe.local.request_ip
            except Exception:
                pass
    frappe.db.commit()
    return (res.get("data") or {}).get("request_id")


# -------------------------------------------------------------------- A

def test_cancelled_ip_is_set():
    from iranrobot_backend.api.wallet import cancel_top_up_request
    email, _cust, _wallet = _fresh_customer()
    req = _create_pending(email)
    with _SetUser(email):
        frappe.local.request_ip = "198.51.100.42"
        try:
            res = cancel_top_up_request(name=req)
        finally:
            try:
                del frappe.local.request_ip
            except Exception:
                pass
    frappe.db.commit()
    ip = frappe.db.get_value("Robot Wallet Top Up Request", req, "cancelled_ip")
    emit({
        "step": "cancelled_ip_is_set",
        "request": req,
        "ip_on_row": ip,
        "api_status": (res.get("data") or {}).get("status"),
        "ok": bool(ip) and ip == "198.51.100.42" and (res.get("data") or {}).get("status") == "Cancelled",
    })


# -------------------------------------------------------------------- B

def test_linked_payment_entry_blocked_on_insert():
    """Even as Administrator (System Manager), inserting a Top Up Request
    with linked_payment_entry set must throw."""
    blocked = False
    err_type = ""
    try:
        doc = frappe.get_doc({
            "doctype": "Robot Wallet Top Up Request",
            "customer": frappe.db.get_value("Robot Wallet Account", filters={}, fieldname="customer"),
            "user": "Administrator",
            "wallet": frappe.db.get_value("Robot Wallet Account", filters={}, fieldname="name"),
            "amount_usd": 1,
            "currency": "USD",
            "method": "Bank Transfer",
            "status": "Pending",
            "submitted_at": frappe.utils.now_datetime(),
            # Forbidden: a PE link on a brand-new row.
            "linked_payment_entry": "FAKE-PE-001",
        })
        doc.insert(ignore_permissions=True)
        frappe.db.commit()
    except Exception as e:
        blocked = True
        err_type = type(e).__name__
        frappe.db.rollback()
    emit({
        "step": "linked_payment_entry_blocked_on_insert",
        "blocked": blocked,
        "err_type": err_type,
        "ok": blocked,
    })


def test_linked_payment_entry_blocked_on_update():
    """Take a real Approved request and try to set linked_payment_entry
    after the fact -- must throw."""
    from iranrobot_backend.api.wallet import staff_approve_top_up_request
    email, _cust, _wallet = _fresh_customer()
    req = _create_pending(email, amount=33)
    approve_res = staff_approve_top_up_request(name=req, bank_reference="REF-8c-B")
    frappe.db.commit()
    if not approve_res.get("ok"):
        emit({"step": "linked_payment_entry_blocked_on_update", "skipped": True, "reason": approve_res})
        return

    blocked = False
    err_type = ""
    try:
        doc = frappe.get_doc("Robot Wallet Top Up Request", req)
        doc.linked_payment_entry = "FAKE-PE-002"
        doc.save(ignore_permissions=True)
        frappe.db.commit()
    except Exception as e:
        blocked = True
        err_type = type(e).__name__
        frappe.db.rollback()
    emit({
        "step": "linked_payment_entry_blocked_on_update",
        "request": req,
        "blocked": blocked,
        "err_type": err_type,
        "ok": blocked,
    })


# -------------------------------------------------------------------- runner

def run_all():
    print("\n=== Phase 8C bench-side hardening smoke ===\n")
    for fn in (
        test_cancelled_ip_is_set,
        test_linked_payment_entry_blocked_on_insert,
        test_linked_payment_entry_blocked_on_update,
    ):
        try:
            fn()
        except Exception as e:
            emit({"step": fn.__name__, "exception": str(e), "exception_type": type(e).__name__})
    print("\n=== Phase 8C bench-side hardening smoke complete ===")
