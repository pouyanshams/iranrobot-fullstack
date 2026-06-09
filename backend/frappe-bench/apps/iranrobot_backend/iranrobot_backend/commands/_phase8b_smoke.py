"""Phase 8B bench-side smoke -- approval correctness + idempotency + invariants.

Run via::

    bench --site iranrobot.localhost execute \\
        iranrobot_backend.commands._phase8b_smoke.run_all

Each invocation seeds a fresh isolated Website User so the assertions are
deterministic regardless of Phase 8A / customer1 history.

Asserts:
    1. Pending top-up DOES NOT change wallet balance.
    2. Approval creates exactly one submitted Robot Wallet Transaction of
       type "Top Up" with credit_amount_usd == request.amount_usd.
    3. Approval increases wallet balance by exactly the request amount.
    4. Duplicate approval returns the same transaction id (idempotent) and
       leaves the SQL COUNT(*) at 1 for that idempotency_key.
    5. Reject keeps balance unchanged; no transaction is created.
    6. Already-Approved cannot be rejected.
    7. Already-Rejected cannot be approved.
    8. Cancelled cannot be approved.
    9. Manual Spend submission via Desk by an Accounts User raises (System
       Manager guard from Phase 8B hardening).
"""

from __future__ import annotations

import json
import secrets

import frappe


def emit(payload):
    print("PHASE8B::" + json.dumps(payload, default=str))


# ---------------------------------------------------------------- helpers

def _fresh_customer():
    """Sign up a fresh Website User + lazy-create their wallet. Returns
    (email, customer_name, wallet_name).

    Uses the existing signup API so the user-Contact-Customer chain is built
    by the same code path the React app uses.
    """
    from iranrobot_backend.api.auth import signup
    from iranrobot_backend.api._session import (
        get_or_create_customer_for_user,
        get_or_create_wallet_for_customer,
    )

    suffix = secrets.token_hex(4)
    email = f"phase8b_{suffix}@example.com"
    pwd = "ChangeMe-123-Strong"

    original = frappe.session.user
    # signup runs as Guest in the real flow; mirror that here so the same
    # validation runs.
    frappe.set_user("Guest")
    try:
        res = signup(
            email=email,
            password=pwd,
            confirm_password=pwd,
            first_name="Phase8B",
            last_name="Tester",
        )
    finally:
        frappe.set_user(original)
    if not res.get("ok"):
        raise RuntimeError(f"signup failed for {email}: {res}")

    # Resolve their Customer + lazy-create the wallet.
    _contact, cust = get_or_create_customer_for_user(email)
    wallet = get_or_create_wallet_for_customer(cust)
    frappe.db.commit()
    return email, cust, wallet


def _as_user(email):
    """Context manager-ish helper to flip the session user briefly."""
    return _SetUser(email)


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


def _create_pending(email, amount=100):
    from iranrobot_backend.api.wallet import create_top_up_request
    with _as_user(email):
        res = create_top_up_request(amount_usd=amount, method="Bank Transfer", customer_note="phase8b seed")
    frappe.db.commit()
    if not res.get("ok"):
        raise RuntimeError(f"create_top_up_request failed: {res}")
    return res["data"]["request_id"]


def _approve(name, bank_reference=None):
    from iranrobot_backend.api.wallet import staff_approve_top_up_request
    res = staff_approve_top_up_request(name=name, bank_reference=bank_reference)
    frappe.db.commit()
    return res


def _reject(name, reason="phase8b reject"):
    from iranrobot_backend.api.wallet import staff_reject_top_up_request
    res = staff_reject_top_up_request(name=name, reason=reason)
    frappe.db.commit()
    return res


def _wallet_balance(wallet):
    return float(frappe.db.get_value("Robot Wallet Account", wallet, "balance_usd") or 0)


def _ledger_sum(wallet):
    rows = frappe.db.sql(
        """
        SELECT COALESCE(SUM(credit_amount_usd - debit_amount_usd), 0)
          FROM `tabRobot Wallet Transaction`
         WHERE wallet=%s AND docstatus=1
        """,
        (wallet,),
    )
    return float(rows[0][0] or 0) if rows else 0.0


# ---------------------------------------------------------------- tests

def test_pending_does_not_change_balance():
    email, _cust, wallet = _fresh_customer()
    before = _wallet_balance(wallet)
    req = _create_pending(email, amount=75)
    after = _wallet_balance(wallet)
    ledger = _ledger_sum(wallet)
    emit({
        "step": "pending_does_not_change_balance",
        "email": email, "wallet": wallet, "request": req,
        "before": before, "after": after, "ledger": ledger,
        "ok": before == after == ledger == 0.0,
    })


def test_approval_credits_balance_and_creates_single_tx():
    email, _cust, wallet = _fresh_customer()
    before = _wallet_balance(wallet)
    req = _create_pending(email, amount=120)
    res = _approve(req, bank_reference="REF-001")
    after = _wallet_balance(wallet)
    ledger = _ledger_sum(wallet)
    # SQL COUNT(*) for the idempotency_key produced by approval.
    idem = f"topup-request:{req}"
    count = frappe.db.count(
        "Robot Wallet Transaction",
        {"idempotency_key": idem, "docstatus": 1},
    )
    tx_id = res.get("data", {}).get("transaction_id")
    tx_row = frappe.db.get_value(
        "Robot Wallet Transaction", tx_id,
        ["transaction_type", "credit_amount_usd", "linked_top_up_request"],
        as_dict=True,
    )
    emit({
        "step": "approval_credits_balance_and_creates_single_tx",
        "request": req, "transaction": tx_id,
        "before": before, "after": after, "ledger": ledger,
        "count_for_idempotency_key": count, "tx_row": tx_row,
        "ok": (
            before == 0.0 and after == 120.0 and ledger == 120.0
            and count == 1
            and tx_row and tx_row.get("transaction_type") == "Top Up"
            and float(tx_row.get("credit_amount_usd") or 0) == 120.0
            and tx_row.get("linked_top_up_request") == req
        ),
    })


def test_duplicate_approval_is_idempotent():
    email, _cust, wallet = _fresh_customer()
    req = _create_pending(email, amount=42)
    r1 = _approve(req)
    r2 = _approve(req)
    after = _wallet_balance(wallet)
    idem = f"topup-request:{req}"
    count = frappe.db.count(
        "Robot Wallet Transaction",
        {"idempotency_key": idem, "docstatus": 1},
    )
    tx1 = r1.get("data", {}).get("transaction_id")
    tx2 = r2.get("data", {}).get("transaction_id")
    emit({
        "step": "duplicate_approval_is_idempotent",
        "request": req,
        "transaction_first": tx1, "transaction_second": tx2,
        "balance_after": after,
        "count_for_idempotency_key": count,
        "second_idempotent_flag": r2.get("data", {}).get("idempotent"),
        "ok": tx1 == tx2 and count == 1 and after == 42.0 and r2.get("data", {}).get("idempotent") is True,
    })


def test_reject_keeps_balance():
    email, _cust, wallet = _fresh_customer()
    req = _create_pending(email, amount=99)
    before = _wallet_balance(wallet)
    res = _reject(req, reason="phase8b test reject")
    after = _wallet_balance(wallet)
    tx_count = frappe.db.count(
        "Robot Wallet Transaction",
        {"linked_top_up_request": req},
    )
    emit({
        "step": "reject_keeps_balance",
        "request": req, "before": before, "after": after,
        "tx_count_for_request": tx_count,
        "status_returned": res.get("data", {}).get("status"),
        "ok": before == after == 0.0 and tx_count == 0 and res.get("data", {}).get("status") == "Rejected",
    })


def test_already_approved_cannot_be_rejected():
    email, _cust, _wallet = _fresh_customer()
    req = _create_pending(email, amount=10)
    _approve(req)
    res = _reject(req, reason="should not work")
    emit({
        "step": "already_approved_cannot_be_rejected",
        "request": req,
        "code": (res.get("error") or {}).get("code"),
        "ok": res.get("ok") is False and (res.get("error") or {}).get("code") == "STATUS_NOT_REJECTABLE",
    })


def test_already_rejected_cannot_be_approved():
    email, _cust, _wallet = _fresh_customer()
    req = _create_pending(email, amount=10)
    _reject(req, reason="phase8b test")
    res = _approve(req)
    emit({
        "step": "already_rejected_cannot_be_approved",
        "request": req,
        "code": (res.get("error") or {}).get("code"),
        "ok": res.get("ok") is False and (res.get("error") or {}).get("code") == "STATUS_NOT_APPROVABLE",
    })


def test_cancelled_cannot_be_approved():
    from iranrobot_backend.api.wallet import cancel_top_up_request
    email, _cust, _wallet = _fresh_customer()
    req = _create_pending(email, amount=10)
    with _as_user(email):
        cancel_top_up_request(name=req)
    frappe.db.commit()
    res = _approve(req)
    emit({
        "step": "cancelled_cannot_be_approved",
        "request": req,
        "code": (res.get("error") or {}).get("code"),
        "ok": res.get("ok") is False and (res.get("error") or {}).get("code") == "STATUS_NOT_APPROVABLE",
    })


def test_manual_spend_blocked_for_accounts_user():
    """Phase 8B hardening: Accounts User cannot submit a manual Spend
    transaction via Desk. Only System Manager (and Administrator) can."""
    email, cust, wallet = _fresh_customer()
    # Pre-credit the wallet so we can attempt a Spend later.
    req = _create_pending(email, amount=50)
    _approve(req)

    # Ensure there is an Accounts User available to act under. We create a
    # throwaway one whose only role is Accounts User.
    accounts_user_email = f"phase8b_accounts_{secrets.token_hex(4)}@example.com"
    u = frappe.get_doc({
        "doctype": "User",
        "email": accounts_user_email,
        "first_name": "AccountsUser",
        "last_name": "Test",
        "send_welcome_email": 0,
        "enabled": 1,
        "user_type": "System User",
        "roles": [{"role": "Accounts User"}],
    })
    u.insert(ignore_permissions=True)
    frappe.db.commit()

    blocked = False
    err_msg = ""
    with _as_user(accounts_user_email):
        try:
            tx = frappe.get_doc({
                "doctype": "Robot Wallet Transaction",
                "wallet": wallet,
                "transaction_type": "Spend",
                "currency": "USD",
                "credit_amount_usd": 0,
                "debit_amount_usd": 10,
                "idempotency_key": f"phase8b-spend-test-{secrets.token_hex(4)}",
                "notes": "phase8b manual spend attempt",
                "posted_at": frappe.utils.now_datetime(),
            })
            tx.insert(ignore_permissions=True)
            tx.submit()
        except Exception as e:
            blocked = True
            err_msg = type(e).__name__
    emit({
        "step": "manual_spend_blocked_for_accounts_user",
        "actor": accounts_user_email, "wallet": wallet,
        "blocked": blocked, "exception_type": err_msg,
        "ok": blocked,
    })


# ---------------------------------------------------------------- runner

def run_all():
    print("\n=== Phase 8B bench-side smoke ===\n")
    for fn in (
        test_pending_does_not_change_balance,
        test_approval_credits_balance_and_creates_single_tx,
        test_duplicate_approval_is_idempotent,
        test_reject_keeps_balance,
        test_already_approved_cannot_be_rejected,
        test_already_rejected_cannot_be_approved,
        test_cancelled_cannot_be_approved,
        test_manual_spend_blocked_for_accounts_user,
    ):
        try:
            fn()
        except Exception as e:
            emit({"step": fn.__name__, "exception": str(e), "exception_type": type(e).__name__})
    print("\n=== Phase 8B bench-side smoke complete ===")
