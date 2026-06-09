"""Phase 8A bench-side smoke -- ledger derivation + cache invariants.

Run via::

    bench --site iranrobot.localhost execute \\
        iranrobot_backend.commands._phase8a_smoke.run_all

Asserts:
    1. Lazy wallet creation is idempotent (returns same name twice).
    2. Submitting Top Up / Spend / Refund / Adjustment transactions in mixed
       order produces `balance_usd` equal to SUM(credit - debit) over the
       submitted ledger.
    3. Cancelling a submitted transaction removes it from the SUM (cache
       refreshed correctly).
    4. `balance_after_usd` snapshot on each row matches the cached balance at
       submit time.
    5. `idempotency_key` uniqueness blocks duplicates.

Customer used: customer1@example.com (created by Phase 4.5 seed). The seeder
NEVER touches ERPNext Payment Entry / Sales Invoice / Mode of Payment.
"""

from __future__ import annotations

import json

import frappe


CUSTOMER_EMAIL = "customer1@example.com"


def emit(payload):
    print("PHASE8A::" + json.dumps(payload, default=str))


# ---------------------------------------------------------------- helpers

def _resolve_customer() -> str:
    from iranrobot_backend.api._session import get_or_create_customer_for_user

    original = frappe.session.user
    frappe.set_user(CUSTOMER_EMAIL)
    try:
        _contact, cust = get_or_create_customer_for_user(CUSTOMER_EMAIL)
    finally:
        frappe.set_user(original)
    if not cust:
        raise RuntimeError(f"could not resolve customer for {CUSTOMER_EMAIL}")
    return cust


def _lazy_wallet(customer: str) -> str:
    from iranrobot_backend.api._session import get_or_create_wallet_for_customer

    name = get_or_create_wallet_for_customer(customer)
    frappe.db.commit()
    return name


def _ledger_sum(wallet_name: str) -> float:
    rows = frappe.db.sql(
        """
        SELECT COALESCE(SUM(credit_amount_usd - debit_amount_usd), 0) AS bal
          FROM `tabRobot Wallet Transaction`
         WHERE wallet=%s AND docstatus=1
        """,
        (wallet_name,),
    )
    return float(rows[0][0] or 0) if rows else 0.0


def _cached_balance(wallet_name: str) -> float:
    return float(frappe.db.get_value("Robot Wallet Account", wallet_name, "balance_usd") or 0)


def _make_and_submit_tx(
    wallet: str,
    *,
    transaction_type: str,
    credit: float = 0,
    debit: float = 0,
    idempotency_key: str,
    reason: str | None = None,
    notes: str | None = None,
) -> str:
    """Build, save, and submit a Robot Wallet Transaction. Returns its name."""
    doc = frappe.get_doc({
        "doctype": "Robot Wallet Transaction",
        "wallet": wallet,
        "transaction_type": transaction_type,
        "currency": "USD",
        "credit_amount_usd": credit,
        "debit_amount_usd": debit,
        "idempotency_key": idempotency_key,
        "reason": reason,
        "notes": notes,
        "posted_at": frappe.utils.now_datetime(),
    })
    doc.insert(ignore_permissions=True)
    doc.submit()
    frappe.db.commit()
    return doc.name


# ---------------------------------------------------------------- tests

def test_lazy_wallet_idempotent():
    cust = _resolve_customer()
    w1 = _lazy_wallet(cust)
    w2 = _lazy_wallet(cust)
    emit({"step": "lazy_idempotent", "customer": cust, "w1": w1, "w2": w2, "ok": w1 == w2})
    return w1


def test_balance_derivation_and_cache(wallet: str):
    """Submit several transactions and verify cache == ledger SUM at each step."""
    suffix = frappe.utils.now_datetime().strftime("%Y%m%d%H%M%S%f")

    # Top Up $100
    n1 = _make_and_submit_tx(
        wallet,
        transaction_type="Top Up",
        credit=100,
        idempotency_key=f"phase8a-test-topup-100-{suffix}",
        notes="phase8a derivation test #1",
    )
    s1 = _ledger_sum(wallet)
    c1 = _cached_balance(wallet)
    emit({"step": "after_topup_100", "tx": n1, "ledger_sum": s1, "cached": c1, "match": abs(s1 - c1) < 1e-6})

    # Top Up $50
    n2 = _make_and_submit_tx(
        wallet,
        transaction_type="Top Up",
        credit=50,
        idempotency_key=f"phase8a-test-topup-50-{suffix}",
        notes="phase8a derivation test #2",
    )
    s2 = _ledger_sum(wallet)
    c2 = _cached_balance(wallet)
    emit({"step": "after_topup_50", "tx": n2, "ledger_sum": s2, "cached": c2, "match": abs(s2 - c2) < 1e-6})

    # Spend $30 -> balance should be 120
    n3 = _make_and_submit_tx(
        wallet,
        transaction_type="Spend",
        debit=30,
        idempotency_key=f"phase8a-test-spend-30-{suffix}",
        notes="phase8a derivation test #3",
    )
    s3 = _ledger_sum(wallet)
    c3 = _cached_balance(wallet)
    emit({"step": "after_spend_30", "tx": n3, "ledger_sum": s3, "cached": c3, "match": abs(s3 - c3) < 1e-6})

    # balance_after_usd snapshot on tx #3 should equal c3
    after = float(frappe.db.get_value("Robot Wallet Transaction", n3, "balance_after_usd") or 0)
    emit({"step": "balance_after_snapshot", "tx": n3, "balance_after_usd": after, "matches_cache": abs(after - c3) < 1e-6})

    # Cancel tx #3 -> balance should revert to s2
    doc3 = frappe.get_doc("Robot Wallet Transaction", n3)
    doc3.cancel()
    frappe.db.commit()
    s4 = _ledger_sum(wallet)
    c4 = _cached_balance(wallet)
    emit({"step": "after_cancel_spend", "tx": n3, "ledger_sum": s4, "cached": c4, "match": abs(s4 - c4) < 1e-6, "matches_pre_spend": abs(s4 - s2) < 1e-6})

    return [n1, n2, n3]


def test_idempotency_key_uniqueness(wallet: str):
    key = f"phase8a-test-dup-{frappe.utils.now_datetime().strftime('%Y%m%d%H%M%S%f')}"
    _make_and_submit_tx(
        wallet,
        transaction_type="Adjustment-Credit",
        credit=1,
        idempotency_key=key,
        reason="phase8a dup test #1",
    )
    blocked = False
    try:
        _make_and_submit_tx(
            wallet,
            transaction_type="Adjustment-Credit",
            credit=1,
            idempotency_key=key,
            reason="phase8a dup test #2",
        )
    except Exception as e:
        blocked = True
        emit({"step": "idempotency_dup_blocked", "ok": True, "err_type": type(e).__name__})
    if not blocked:
        emit({"step": "idempotency_dup_blocked", "ok": False, "err": "second insert was not blocked"})


def test_adjustment_requires_reason(wallet: str):
    raised = False
    try:
        _make_and_submit_tx(
            wallet,
            transaction_type="Adjustment-Debit",
            debit=1,
            idempotency_key=f"phase8a-test-adj-no-reason-{frappe.utils.now_datetime().strftime('%Y%m%d%H%M%S%f')}",
            reason=None,
        )
    except Exception as e:
        raised = True
        emit({"step": "adjustment_requires_reason", "ok": True, "err_type": type(e).__name__})
    if not raised:
        emit({"step": "adjustment_requires_reason", "ok": False})


def test_credit_xor_debit(wallet: str):
    """Both zero must fail; both non-zero must fail."""
    suffix = frappe.utils.now_datetime().strftime("%Y%m%d%H%M%S%f")
    both_zero_raised = False
    try:
        _make_and_submit_tx(
            wallet,
            transaction_type="Top Up",
            credit=0,
            debit=0,
            idempotency_key=f"phase8a-test-both-zero-{suffix}",
        )
    except Exception:
        both_zero_raised = True
    both_nonzero_raised = False
    try:
        _make_and_submit_tx(
            wallet,
            transaction_type="Top Up",
            credit=1,
            debit=1,
            idempotency_key=f"phase8a-test-both-nonzero-{suffix}",
        )
    except Exception:
        both_nonzero_raised = True
    emit({"step": "credit_xor_debit", "both_zero_raised": both_zero_raised, "both_nonzero_raised": both_nonzero_raised})


# ---------------------------------------------------------------- runner

def run_all():
    print("\n=== Phase 8A bench-side smoke ===\n")
    wallet = test_lazy_wallet_idempotent()
    if not wallet:
        emit({"step": "abort", "reason": "no wallet"})
        return
    test_balance_derivation_and_cache(wallet)
    test_idempotency_key_uniqueness(wallet)
    test_adjustment_requires_reason(wallet)
    test_credit_xor_debit(wallet)
    print("\n=== Phase 8A bench-side smoke complete ===")
