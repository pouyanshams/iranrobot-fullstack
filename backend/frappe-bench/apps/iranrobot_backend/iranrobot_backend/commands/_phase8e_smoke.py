"""Phase 8E bench-side smoke -- wallet reconciliation correctness.

Each test seeds a fresh isolated customer + wallet (via the same direct-ORM
pattern Phase 8D-2 uses to dodge Frappe's hourly user-creation throttle),
runs `reconciliation.reconcile_one()`, and asserts on:

  * Clean / Mismatch / Frozen classification at the right threshold
  * Robot Wallet Account.status flips to Frozen only above the threshold
  * Error Log entries are written for mismatches
  * Sub-threshold drift logs but does not freeze
  * Cached-vs-ledger AND ledger-vs-GL deltas both feed the freeze decision
  * Single-wallet and bulk modes are idempotent
  * `pay_invoice_with_wallet` blocks Frozen wallets
  * `get_wallet_summary` remains readable for Frozen wallets

Run via::

    bench --site iranrobot.localhost execute \\
        iranrobot_backend.commands._phase8e_smoke.run_all
"""

from __future__ import annotations

import json
import secrets

import frappe

from iranrobot_backend.commands.wallet_accounting_bootstrap import COMPANY
from iranrobot_backend.wallet import reconciliation


WALLET_LIABILITY = reconciliation.WALLET_LIABILITY_ACCOUNT
INCOME_ACCOUNT = "Sales - IR"


def emit(payload):
    print("PHASE8E::" + json.dumps(payload, default=str))


# ---------------------------------------------------------------- helpers


def _fresh_customer():
    from iranrobot_backend.api._session import (
        get_or_create_customer_for_user,
        get_or_create_wallet_for_customer,
    )
    suffix = secrets.token_hex(4)
    email = f"phase8e_{suffix}@example.com"
    prior = getattr(frappe.flags, "in_import", False)
    frappe.flags.in_import = True
    try:
        user = frappe.get_doc({
            "doctype": "User", "email": email,
            "first_name": "Phase8E", "last_name": "Smoke",
            "send_welcome_email": 0, "enabled": 1,
            "user_type": "Website User",
            "roles": [{"role": "Customer"}],
        })
        user.insert(ignore_permissions=True)
    finally:
        frappe.flags.in_import = prior
    frappe.db.commit()
    _contact, cust = get_or_create_customer_for_user(email)
    wallet = get_or_create_wallet_for_customer(cust)
    frappe.db.commit()
    return email, cust, wallet


def _credit_wallet(email, customer, amount):
    """Credit via the real top-up + approve flow so all three balances agree."""
    from iranrobot_backend.api.wallet import (
        create_top_up_request, staff_approve_top_up_request,
    )
    original = frappe.session.user
    frappe.set_user(email)
    try:
        res = create_top_up_request(amount_usd=amount, method="Bank Transfer")
    finally:
        frappe.set_user(original)
    if not res.get("ok"):
        raise RuntimeError(f"create_top_up_request failed: {res}")
    appr = staff_approve_top_up_request(
        name=res["data"]["request_id"], bank_reference="REF-8E",
    )
    frappe.db.commit()
    if not appr.get("ok"):
        raise RuntimeError(f"approve failed: {appr}")


def _bump_cache(wallet, new_balance):
    """Forcefully overwrite the cached balance to simulate a corrupted
    header. Uses db.set_value so the controller doesn't fire."""
    frappe.db.set_value(
        "Robot Wallet Account", wallet, "balance_usd",
        float(new_balance), update_modified=False,
    )
    frappe.db.commit()


def _inject_gl_entry(customer, debit, credit):
    """Append a raw GL Entry for the Customer Wallet Liability party balance
    to simulate an unaccounted accounting movement. Bypasses ERPNext's PE/JE
    machinery -- only used to corrupt the GL for tests."""
    je = frappe.get_doc({
        "doctype": "Journal Entry",
        "voucher_type": "Journal Entry",
        "posting_date": frappe.utils.today(),
        "company": COMPANY,
        "user_remark": f"phase8e GL injection for {customer}",
        "accounts": [
            {
                "account": WALLET_LIABILITY,
                "debit_in_account_currency": debit,
                "credit_in_account_currency": 0 if debit else credit,
                "party_type": "Customer", "party": customer,
            },
            {
                # other leg: balance the JE against Cash so it posts
                "account": "Cash - IR",
                "debit_in_account_currency": credit if credit else 0,
                "credit_in_account_currency": debit if debit else 0,
            },
        ],
    })
    je.insert(ignore_permissions=True)
    je.submit()
    frappe.db.commit()
    return je.name


def _get_status(wallet):
    return frappe.db.get_value("Robot Wallet Account", wallet, "status")


def _last_error_log_for_wallet(wallet):
    """Return (title, message_text) of the most recent Error Log mentioning
    this wallet, or (None, None)."""
    rows = frappe.db.sql(
        """SELECT method, error FROM `tabError Log`
            WHERE error LIKE %s
            ORDER BY creation DESC LIMIT 1""",
        (f'%{wallet}%',),
        as_dict=True,
    )
    if not rows:
        return None, None
    return rows[0]["method"], rows[0]["error"]


# ---------------------------------------------------------------- tests


def test_clean_wallet_passes():
    email, cust, wallet = _fresh_customer()
    _credit_wallet(email, cust, 100)
    res = reconciliation.reconcile_one(wallet, freeze=True)
    status_after = _get_status(wallet)
    ok = (
        res["status"] == "Clean"
        and res["max_delta"] <= 0.01
        and status_after == "Active"
        and frappe.db.get_value("Robot Wallet Account", wallet,
                                "last_reconciliation_status") == "Clean"
    )
    emit({
        "step": "clean_wallet_passes", "ok": ok,
        "result": res, "status_after": status_after,
    })


def test_cached_corruption_sub_threshold_logs_only():
    email, cust, wallet = _fresh_customer()
    _credit_wallet(email, cust, 100)
    _bump_cache(wallet, 100.50)   # delta 0.50 -- above tolerance, below threshold
    res = reconciliation.reconcile_one(wallet, freeze=True)
    status_after = _get_status(wallet)
    title, _msg = _last_error_log_for_wallet(wallet)
    ok = (
        res["status"] == "Mismatch"
        and 0.4 < res["delta_cached_ledger"] < 0.6
        and res["action_taken"] == "logged"
        and status_after == "Active"  # NOT frozen
        and (title or "").startswith("Wallet reconciliation mismatch [Mismatch]")
    )
    emit({
        "step": "cached_corruption_sub_threshold_logs_only",
        "ok": ok, "result": res, "status_after": status_after,
        "error_log_title": title,
    })


def test_cached_corruption_above_threshold_freezes():
    email, cust, wallet = _fresh_customer()
    _credit_wallet(email, cust, 100)
    _bump_cache(wallet, 250)      # delta 150 -- above freeze threshold
    res = reconciliation.reconcile_one(wallet, freeze=True)
    status_after = _get_status(wallet)
    title, _msg = _last_error_log_for_wallet(wallet)
    ok = (
        res["status"] == "Frozen"
        and res["delta_cached_ledger"] > 100
        and res["action_taken"] == "frozen"
        and status_after == "Frozen"
        and (title or "").startswith("Wallet reconciliation mismatch [Frozen]")
    )
    emit({
        "step": "cached_corruption_above_threshold_freezes",
        "ok": ok, "result": res, "status_after": status_after,
        "error_log_title": title,
    })


def test_ledger_vs_gl_sub_threshold_logs_only():
    email, cust, wallet = _fresh_customer()
    _credit_wallet(email, cust, 100)
    # Push GL by 0.50 -- a credit increases the liability balance.
    _inject_gl_entry(cust, debit=0, credit=0.50)
    # Cache + ledger remain at $100; GL moves to $100.50. Roll the cache so
    # cached==ledger (we want this test to isolate the ledger-vs-GL delta).
    res = reconciliation.reconcile_one(wallet, freeze=True)
    status_after = _get_status(wallet)
    ok = (
        res["status"] == "Mismatch"
        and 0.4 < res["delta_ledger_gl"] < 0.6
        and status_after == "Active"
    )
    emit({
        "step": "ledger_vs_gl_sub_threshold_logs_only",
        "ok": ok, "result": res, "status_after": status_after,
    })


def test_ledger_vs_gl_above_threshold_freezes():
    email, cust, wallet = _fresh_customer()
    _credit_wallet(email, cust, 100)
    _inject_gl_entry(cust, debit=0, credit=50)   # GL +50 -> delta 50
    res = reconciliation.reconcile_one(wallet, freeze=True)
    status_after = _get_status(wallet)
    ok = (
        res["status"] == "Frozen"
        and res["delta_ledger_gl"] > 40
        and status_after == "Frozen"
    )
    emit({
        "step": "ledger_vs_gl_above_threshold_freezes",
        "ok": ok, "result": res, "status_after": status_after,
    })


def test_extra_gl_entry_detected():
    """A JE that credits Wallet Liability without a matching wallet
    transaction produces an above-threshold ledger-vs-GL drift."""
    email, cust, wallet = _fresh_customer()
    _credit_wallet(email, cust, 100)
    _inject_gl_entry(cust, debit=0, credit=10)
    res = reconciliation.reconcile_one(wallet, freeze=True)
    ok = (
        res["status"] == "Frozen"
        and res["delta_ledger_gl"] > 9
        and _get_status(wallet) == "Frozen"
    )
    emit({"step": "extra_gl_entry_detected", "ok": ok, "result": res})


def test_missing_gl_entry_detected():
    """A JE that debits Wallet Liability without a matching wallet spend
    produces an above-threshold ledger-vs-GL drift (GL < ledger)."""
    email, cust, wallet = _fresh_customer()
    _credit_wallet(email, cust, 100)
    _inject_gl_entry(cust, debit=15, credit=0)  # liability drops by 15
    res = reconciliation.reconcile_one(wallet, freeze=True)
    ok = (
        res["status"] == "Frozen"
        and res["delta_ledger_gl"] > 14
        and res["gl_balance"] < res["ledger_balance"]
        and _get_status(wallet) == "Frozen"
    )
    emit({"step": "missing_gl_entry_detected", "ok": ok, "result": res})


def test_reconcile_is_idempotent():
    email, cust, wallet = _fresh_customer()
    _credit_wallet(email, cust, 50)
    r1 = reconciliation.reconcile_one(wallet, freeze=True)
    r2 = reconciliation.reconcile_one(wallet, freeze=True)
    ok = (
        r1["status"] == r2["status"] == "Clean"
        and r1["max_delta"] == r2["max_delta"] == 0.0
        and _get_status(wallet) == "Active"
    )
    emit({"step": "reconcile_is_idempotent", "ok": ok})


def test_single_wallet_mode():
    """Single-wallet mode via the bench command must only touch that wallet."""
    from iranrobot_backend.commands import wallet_reconcile
    email_a, cust_a, wallet_a = _fresh_customer()
    email_b, cust_b, wallet_b = _fresh_customer()
    _credit_wallet(email_a, cust_a, 70)
    _credit_wallet(email_b, cust_b, 70)
    # Corrupt B's cache by a lot, but only run reconcile on A.
    _bump_cache(wallet_b, 500)
    summary = wallet_reconcile.run(freeze=True, wallet=wallet_a)
    a_status = _get_status(wallet_a)
    b_status = _get_status(wallet_b)
    ok = (
        summary["total"] == 1
        and summary["clean"] == 1
        and a_status == "Active"
        and b_status == "Active"  # untouched even though B is corrupt
    )
    emit({
        "step": "single_wallet_mode", "ok": ok,
        "summary": summary, "a_status": a_status, "b_status": b_status,
    })


def test_reconcile_all_daily_does_not_crash():
    """The scheduler entry point must swallow per-wallet errors and never
    propagate an exception out."""
    try:
        reconciliation.reconcile_all_daily()
        emit({"step": "reconcile_all_daily_does_not_crash", "ok": True})
    except Exception as e:
        emit({
            "step": "reconcile_all_daily_does_not_crash",
            "ok": False,
            "exception": str(e),
            "exception_type": type(e).__name__,
        })


def test_pay_invoice_with_wallet_blocks_frozen():
    """A wallet auto-frozen by reconciliation must refuse pay_invoice_with_wallet."""
    from iranrobot_backend.api.wallet import pay_invoice_with_wallet

    email, cust, wallet = _fresh_customer()
    _credit_wallet(email, cust, 200)
    # Submit an SI we could otherwise pay.
    item_code = frappe.db.get_value(
        "Robot Product", filters={"erpnext_item": ["!=", ""]},
        fieldname="erpnext_item",
    )
    si = frappe.get_doc({
        "doctype": "Sales Invoice",
        "customer": cust, "company": COMPANY, "currency": "USD",
        "posting_date": frappe.utils.today(),
        "due_date": frappe.utils.today(), "set_posting_time": 1,
        "items": [{
            "item_code": item_code, "qty": 1, "rate": 60, "uom": "Nos",
            "income_account": INCOME_ACCOUNT,
        }],
    })
    si.insert(ignore_permissions=True)
    si.submit()
    frappe.db.commit()

    # Corrupt cache and reconcile -> wallet should freeze.
    _bump_cache(wallet, 999)
    reconciliation.reconcile_one(wallet, freeze=True)

    original = frappe.session.user
    frappe.set_user(email)
    try:
        res = pay_invoice_with_wallet(sales_invoice_name=si.name, amount_usd=10)
    finally:
        frappe.set_user(original)

    code = (res.get("error") or {}).get("code")
    ok = (not res.get("ok")) and code == "WALLET_FROZEN"
    emit({
        "step": "pay_invoice_with_wallet_blocks_frozen",
        "ok": ok, "code": code,
    })


def test_get_wallet_summary_readable_for_frozen():
    """Frozen wallets must still return their summary so the customer can
    see the balance / status / pending top-ups."""
    from iranrobot_backend.api.wallet import get_wallet_summary

    email, cust, wallet = _fresh_customer()
    _credit_wallet(email, cust, 80)
    _bump_cache(wallet, 200)
    reconciliation.reconcile_one(wallet, freeze=True)

    original = frappe.session.user
    frappe.set_user(email)
    try:
        res = get_wallet_summary()
    finally:
        frappe.set_user(original)
    data = res.get("data") or {}
    w = data.get("wallet") or {}
    ok = (
        res.get("ok") is True
        and w.get("status") == "Frozen"
        and w.get("last_reconciliation_status") == "Frozen"
        and "last_reconciliation_delta_usd" not in w  # audit-only, never surfaced
        and data.get("can_top_up") is True   # 8B contract is still satisfied
        # (the actual block is enforced at create_top_up_request time)
    )
    emit({
        "step": "get_wallet_summary_readable_for_frozen",
        "ok": ok, "data": data,
    })


def test_create_top_up_request_blocks_frozen():
    from iranrobot_backend.api.wallet import create_top_up_request
    email, cust, wallet = _fresh_customer()
    _credit_wallet(email, cust, 10)
    _bump_cache(wallet, 999)
    reconciliation.reconcile_one(wallet, freeze=True)
    original = frappe.session.user
    frappe.set_user(email)
    try:
        res = create_top_up_request(amount_usd=20, method="Bank Transfer")
    finally:
        frappe.set_user(original)
    code = (res.get("error") or {}).get("code")
    ok = (not res.get("ok")) and code == "WALLET_FROZEN"
    emit({"step": "create_top_up_request_blocks_frozen", "ok": ok, "code": code})


def test_staff_approve_top_up_request_blocks_frozen():
    """Make a Pending request, then freeze the wallet, then try to approve."""
    from iranrobot_backend.api.wallet import (
        create_top_up_request, staff_approve_top_up_request,
    )
    email, cust, wallet = _fresh_customer()
    _credit_wallet(email, cust, 10)
    # Create a Pending request while the wallet is still Active.
    original = frappe.session.user
    frappe.set_user(email)
    try:
        res = create_top_up_request(amount_usd=50, method="Bank Transfer")
    finally:
        frappe.set_user(original)
    pending_id = res["data"]["request_id"]
    # Now freeze the wallet.
    _bump_cache(wallet, 9999)
    reconciliation.reconcile_one(wallet, freeze=True)
    # Try to approve as Administrator.
    appr = staff_approve_top_up_request(name=pending_id)
    code = (appr.get("error") or {}).get("code")
    ok = (not appr.get("ok")) and code == "WALLET_FROZEN"
    emit({
        "step": "staff_approve_top_up_request_blocks_frozen",
        "ok": ok, "code": code,
    })


# ---------------------------------------------------------------- runner


def run_all():
    print("\n=== Phase 8E bench-side smoke ===\n")
    for fn in (
        test_clean_wallet_passes,
        test_cached_corruption_sub_threshold_logs_only,
        test_cached_corruption_above_threshold_freezes,
        test_ledger_vs_gl_sub_threshold_logs_only,
        test_ledger_vs_gl_above_threshold_freezes,
        test_extra_gl_entry_detected,
        test_missing_gl_entry_detected,
        test_reconcile_is_idempotent,
        test_single_wallet_mode,
        test_reconcile_all_daily_does_not_crash,
        test_pay_invoice_with_wallet_blocks_frozen,
        test_get_wallet_summary_readable_for_frozen,
        test_create_top_up_request_blocks_frozen,
        test_staff_approve_top_up_request_blocks_frozen,
    ):
        try:
            fn()
        except Exception as e:
            emit({
                "step": fn.__name__,
                "exception": str(e),
                "exception_type": type(e).__name__,
            })
    print("\n=== Phase 8E bench-side smoke complete ===")
