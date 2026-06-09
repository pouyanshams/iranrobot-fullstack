"""Phase 8D-1 bench-side smoke -- atomic approval (TX + PE) + idempotency.

Covers the assertions that need direct ORM access:

  1. Approving a fresh top-up creates BOTH a submitted Robot Wallet Transaction
     and a submitted Payment Entry, links both on the request, and increases
     the wallet balance by exactly the request amount.
  2. Duplicate approval returns the same transaction_id and payment_entry --
     no second PE is created.
  3. When `_accounting_ready()` returns False, approval returns
     ACCOUNTING_NOT_READY without touching the wallet ledger.

The HTTP smoke (`tests/backend/phase8d1_smoke.py`) covers the API boundary.

Run via::

    bench --site iranrobot.localhost execute \\
        iranrobot_backend.commands._phase8d1_smoke.run_all
"""

from __future__ import annotations

import json
import secrets

import frappe


def emit(payload):
    print("PHASE8D1::" + json.dumps(payload, default=str))


def _fresh_customer():
    from iranrobot_backend.api.auth import signup
    from iranrobot_backend.api._session import (
        get_or_create_customer_for_user,
        get_or_create_wallet_for_customer,
    )
    suffix = secrets.token_hex(4)
    email = f"phase8d1_{suffix}@example.com"
    pwd = "ChangeMe-123-Strong"
    original = frappe.session.user
    frappe.set_user("Guest")
    try:
        res = signup(
            email=email, password=pwd, confirm_password=pwd,
            first_name="Phase8D1", last_name="Smoke",
        )
    finally:
        frappe.set_user(original)
    if not res.get("ok"):
        raise RuntimeError(f"signup failed: {res}")
    _contact, cust = get_or_create_customer_for_user(email)
    wallet = get_or_create_wallet_for_customer(cust)
    frappe.db.commit()
    return email, cust, wallet


def _create_pending(email, amount=100):
    from iranrobot_backend.api.wallet import create_top_up_request
    original = frappe.session.user
    frappe.set_user(email)
    try:
        res = create_top_up_request(amount_usd=amount, method="Bank Transfer")
    finally:
        frappe.set_user(original)
    frappe.db.commit()
    if not res.get("ok"):
        raise RuntimeError(f"create_top_up_request failed: {res}")
    return res["data"]["request_id"]


def _approve(name, bank_reference=None):
    from iranrobot_backend.api.wallet import staff_approve_top_up_request
    res = staff_approve_top_up_request(name=name, bank_reference=bank_reference)
    frappe.db.commit()
    return res


def _wallet_balance(wallet):
    return float(frappe.db.get_value("Robot Wallet Account", wallet, "balance_usd") or 0)


# ---------------------------------------------------------------- tests


def test_approval_creates_tx_and_pe_atomically():
    email, _cust, wallet = _fresh_customer()
    before = _wallet_balance(wallet)
    req = _create_pending(email, amount=75)

    res = _approve(req, bank_reference="REF-8D1-A")
    data = res.get("data") or {}
    tx_id = data.get("transaction_id")
    pe_id = data.get("payment_entry")

    after = _wallet_balance(wallet)

    # PE must exist and be submitted
    pe_row = frappe.db.get_value(
        "Payment Entry", pe_id,
        ["docstatus", "payment_type", "party_type", "party",
         "paid_from", "paid_to", "paid_amount", "reference_no", "mode_of_payment"],
        as_dict=True,
    ) if pe_id else None

    # TX must be linked back on the request, and linked_payment_entry too
    request_row = frappe.db.get_value(
        "Robot Wallet Top Up Request", req,
        ["status", "linked_transaction", "linked_payment_entry"],
        as_dict=True,
    )

    ok = (
        bool(tx_id) and bool(pe_id) and pe_row is not None
        and int(pe_row.get("docstatus") or 0) == 1
        and pe_row.get("payment_type") == "Receive"
        and pe_row.get("party_type") == "Customer"
        and pe_row.get("mode_of_payment") == "Wallet"
        and pe_row.get("paid_from") == "Customer Wallet Liability - IR"
        and pe_row.get("paid_to") == "Cash - IR"
        and abs(float(pe_row.get("paid_amount") or 0) - 75.0) < 0.005
        and pe_row.get("reference_no") == req
        and request_row.get("status") == "Approved"
        and request_row.get("linked_transaction") == tx_id
        and request_row.get("linked_payment_entry") == pe_id
        and abs(after - before - 75.0) < 0.005
    )
    emit({
        "step": "approval_creates_tx_and_pe_atomically",
        "ok": ok,
        "request": req,
        "tx": tx_id,
        "pe": pe_id,
        "balance_before": before,
        "balance_after": after,
        "pe_row": pe_row,
        "request_row": request_row,
    })


def test_duplicate_approval_returns_same_pe():
    email, _cust, wallet = _fresh_customer()
    req = _create_pending(email, amount=42)

    r1 = _approve(req)
    r2 = _approve(req)
    pe1 = (r1.get("data") or {}).get("payment_entry")
    pe2 = (r2.get("data") or {}).get("payment_entry")
    tx1 = (r1.get("data") or {}).get("transaction_id")
    tx2 = (r2.get("data") or {}).get("transaction_id")

    # Count PEs that reference this request as reference_no
    pe_count = frappe.db.count(
        "Payment Entry",
        {"reference_no": req, "docstatus": 1, "payment_type": "Receive"},
    )

    after = _wallet_balance(wallet)

    ok = (
        pe1 == pe2 and tx1 == tx2 and pe_count == 1
        and (r2.get("data") or {}).get("idempotent") is True
        and abs(after - 42.0) < 0.005
    )
    emit({
        "step": "duplicate_approval_returns_same_pe",
        "ok": ok,
        "request": req,
        "pe_first": pe1, "pe_second": pe2,
        "tx_first": tx1, "tx_second": tx2,
        "pe_count_in_db": pe_count,
        "balance_after": after,
        "second_idempotent_flag": (r2.get("data") or {}).get("idempotent"),
    })


def test_accounting_not_ready_blocks_approval():
    """Monkey-patch `_accounting_ready` to return False and confirm that
    approval fails BEFORE creating any wallet ledger row."""
    from iranrobot_backend.api import wallet as wallet_api

    email, _cust, wallet = _fresh_customer()
    req = _create_pending(email, amount=33)
    before = _wallet_balance(wallet)

    original = wallet_api._accounting_ready
    wallet_api._accounting_ready = lambda: False
    try:
        res = _approve(req)
    finally:
        wallet_api._accounting_ready = original

    after = _wallet_balance(wallet)
    code = (res.get("error") or {}).get("code")
    tx_exists = frappe.db.exists(
        "Robot Wallet Transaction",
        {"idempotency_key": f"topup-request:{req}", "docstatus": 1},
    )
    pe_exists = frappe.db.exists(
        "Payment Entry",
        {"reference_no": req, "docstatus": 1},
    )
    request_row = frappe.db.get_value(
        "Robot Wallet Top Up Request", req,
        ["status", "linked_transaction", "linked_payment_entry"],
        as_dict=True,
    )

    ok = (
        res.get("ok") is False
        and code == "ACCOUNTING_NOT_READY"
        and abs(after - before) < 0.005
        and not tx_exists
        and not pe_exists
        and request_row.get("status") == "Pending"
        and not request_row.get("linked_transaction")
        and not request_row.get("linked_payment_entry")
    )
    emit({
        "step": "accounting_not_ready_blocks_approval",
        "ok": ok,
        "request": req,
        "code": code,
        "tx_exists": bool(tx_exists),
        "pe_exists": bool(pe_exists),
        "balance_before": before,
        "balance_after": after,
        "request_row": request_row,
    })


def test_backfill_dry_run_no_writes():
    """Dry-run must not create any PE."""
    from iranrobot_backend.commands import wallet_accounting_backfill

    before_pe_count = frappe.db.count("Payment Entry")
    counts = wallet_accounting_backfill.run(dry_run=True)
    after_pe_count = frappe.db.count("Payment Entry")

    ok = before_pe_count == after_pe_count
    emit({
        "step": "backfill_dry_run_no_writes",
        "ok": ok,
        "counts": counts,
        "pe_count_before": before_pe_count,
        "pe_count_after": after_pe_count,
    })
    return counts


def test_backfill_real_run_creates_then_idempotent():
    """Real run creates PEs; rerun finds zero unfilled rows."""
    from iranrobot_backend.commands import wallet_accounting_backfill

    counts_real = wallet_accounting_backfill.run(dry_run=False)
    # Rerun must report zero work
    counts_rerun = wallet_accounting_backfill.run(dry_run=False)

    ok = counts_rerun["found"] == 0 and counts_rerun["created"] == 0
    emit({
        "step": "backfill_real_run_creates_then_idempotent",
        "ok": ok,
        "first_run_counts": counts_real,
        "rerun_counts": counts_rerun,
    })


# ---------------------------------------------------------------- runner


def run_all():
    print("\n=== Phase 8D-1 bench-side smoke ===\n")
    for fn in (
        test_backfill_dry_run_no_writes,
        test_backfill_real_run_creates_then_idempotent,
        test_approval_creates_tx_and_pe_atomically,
        test_duplicate_approval_returns_same_pe,
        test_accounting_not_ready_blocks_approval,
    ):
        try:
            fn()
        except Exception as e:
            emit({
                "step": fn.__name__,
                "exception": str(e),
                "exception_type": type(e).__name__,
            })
    print("\n=== Phase 8D-1 bench-side smoke complete ===")
