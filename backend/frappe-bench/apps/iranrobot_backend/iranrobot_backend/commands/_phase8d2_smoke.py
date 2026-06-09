"""Phase 8D-2 bench-side smoke -- Pay Sales Invoice with Wallet.

Each test seeds a fresh isolated customer with a known wallet balance and a
submitted Sales Invoice (linked to a Robot Quote Request when needed for the
QR-sync assertion). The tests then exercise `pay_invoice_with_wallet` /
`get_wallet_payment_status` directly via the Python API and assert on the
resulting Robot Wallet Transaction, Journal Entry, Sales Invoice state,
QR sync, and wallet balance.

Run via::

    bench --site iranrobot.localhost execute \\
        iranrobot_backend.commands._phase8d2_smoke.run_all
"""

from __future__ import annotations

import json
import secrets

import frappe

from iranrobot_backend.commands.wallet_accounting_bootstrap import (
    COMPANY,
    WALLET_LIABILITY_ACCOUNT,
)


CASH_ACCOUNT = "Cash - IR"
DEBTORS_ACCOUNT = "Debtors - IR"
INCOME_ACCOUNT = "Sales - IR"


def emit(payload):
    print("PHASE8D2::" + json.dumps(payload, default=str))


# ---------------------------------------------------------------- fixture helpers


def _fresh_customer():
    """Create a fresh Website User + Contact + Customer + wallet directly via
    ORM. We don't go through `auth.signup` because that endpoint applies a
    rate limit (intentional in prod, painful when a single bench-side smoke
    needs ~12 fresh users in one shot)."""
    from iranrobot_backend.api._session import (
        get_or_create_customer_for_user,
        get_or_create_wallet_for_customer,
    )
    suffix = secrets.token_hex(4)
    email = f"phase8d2_{suffix}@example.com"

    # Frappe's `throttle_user_creation` blocks the bench smoke when >60 Users
    # are created in the last 60 minutes. The `in_import` flag is the
    # canonical bypass; we set it for User.insert() only, then restore.
    prior_flag = getattr(frappe.flags, "in_import", False)
    frappe.flags.in_import = True
    try:
        user = frappe.get_doc({
            "doctype": "User",
            "email": email,
            "first_name": "Phase8D2",
            "last_name": "Smoke",
            "send_welcome_email": 0,
            "enabled": 1,
            "user_type": "Website User",
            "roles": [{"role": "Customer"}],
        })
        user.insert(ignore_permissions=True)
    finally:
        frappe.flags.in_import = prior_flag
    frappe.db.commit()

    _contact, cust = get_or_create_customer_for_user(email)
    wallet = get_or_create_wallet_for_customer(cust)
    frappe.db.commit()
    return email, cust, wallet


def _credit_wallet(email, customer, amount):
    """Create + approve a top-up so the wallet has `amount` USD."""
    from iranrobot_backend.api.wallet import (
        create_top_up_request,
        staff_approve_top_up_request,
    )
    original = frappe.session.user
    frappe.set_user(email)
    try:
        req_res = create_top_up_request(amount_usd=amount, method="Bank Transfer")
    finally:
        frappe.set_user(original)
    if not req_res.get("ok"):
        raise RuntimeError(f"top-up create failed: {req_res}")
    req_name = req_res["data"]["request_id"]

    # Administrator approves
    appr_res = staff_approve_top_up_request(name=req_name, bank_reference="REF-8D2")
    frappe.db.commit()
    if not appr_res.get("ok"):
        raise RuntimeError(f"top-up approve failed: {appr_res}")
    return req_name


def _find_test_item():
    code = frappe.db.get_value(
        "Robot Product", filters={"erpnext_item": ["!=", ""]}, fieldname="erpnext_item",
    )
    if code and frappe.db.exists("Item", code):
        return code
    any_item = frappe.db.get_value("Item", filters={"disabled": 0}, fieldname="name")
    if any_item:
        return any_item
    raise RuntimeError("no Item available")


def _create_submitted_si(customer, rate):
    item = _find_test_item()
    si = frappe.get_doc({
        "doctype": "Sales Invoice",
        "customer": customer,
        "company": COMPANY,
        "currency": "USD",
        "posting_date": frappe.utils.today(),
        "due_date": frappe.utils.today(),
        "set_posting_time": 1,
        "items": [{
            "item_code": item, "qty": 1, "rate": rate, "uom": "Nos",
            "income_account": INCOME_ACCOUNT,
        }],
    })
    si.insert(ignore_permissions=True)
    si.submit()
    frappe.db.commit()
    return si


def _create_qr_linked_to(customer, email, si):
    rp = frappe.db.get_value("Robot Product", filters={}, fieldname="name")
    if not rp:
        return None
    qr = frappe.get_doc({
        "doctype": "Robot Quote Request",
        "customer": customer,
        "user_email": email,
        "customer_name": "Phase8D2 Smoke",
        "email": email, "phone": "", "language": "en",
        "submitted_at": frappe.utils.now_datetime(),
        "status": "New",
        "message": "Phase 8D-2 smoke fixture",
        "items": [{
            "robot_product": rp, "product_name": "8D-2 Item",
            "mode": "buy", "quantity": 1,
            "unit_price_usd": float(si.grand_total or 0),
        }],
    })
    qr.insert(ignore_permissions=True)
    qr.db_set("erpnext_sales_invoice", si.name, update_modified=False)
    qr.db_set("sales_invoice_status", si.status, update_modified=False)
    qr.db_set("sales_invoice_grand_total_usd", float(si.grand_total or 0), update_modified=False)
    qr.db_set("sales_invoice_outstanding_amount_usd",
              float(si.outstanding_amount or 0), update_modified=False)
    qr.db_set("sales_invoice_created_at", frappe.utils.now_datetime(), update_modified=False)
    frappe.db.commit()
    return qr.name


def _pay_as(email, sales_invoice_name, amount_usd=None):
    """Call pay_invoice_with_wallet under the customer's session."""
    from iranrobot_backend.api.wallet import pay_invoice_with_wallet
    original = frappe.session.user
    frappe.set_user(email)
    try:
        res = pay_invoice_with_wallet(
            sales_invoice_name=sales_invoice_name,
            amount_usd=amount_usd,
        )
    finally:
        frappe.set_user(original)
    return res


def _status_as(email, sales_invoice_name):
    from iranrobot_backend.api.wallet import get_wallet_payment_status
    original = frappe.session.user
    frappe.set_user(email)
    try:
        res = get_wallet_payment_status(sales_invoice_name=sales_invoice_name)
    finally:
        frappe.set_user(original)
    return res


def _wallet_balance(wallet):
    return float(frappe.db.get_value("Robot Wallet Account", wallet, "balance_usd") or 0)


def _ledger_sum(wallet):
    rows = frappe.db.sql(
        """SELECT COALESCE(SUM(credit_amount_usd - debit_amount_usd), 0)
             FROM `tabRobot Wallet Transaction`
            WHERE wallet=%s AND docstatus=1""",
        (wallet,),
    )
    return float(rows[0][0] or 0) if rows else 0.0


# ---------------------------------------------------------------- tests


def test_get_status_payable():
    email, cust, wallet = _fresh_customer()
    _credit_wallet(email, cust, 500)
    si = _create_submitted_si(cust, rate=200)
    res = _status_as(email, si.name)
    d = res.get("data") or {}
    ok = (
        res.get("ok") is True
        and d.get("can_pay_with_wallet") is True
        and "blocked_reason" not in d
        and abs(float(d["max_payable_usd"]) - 200.0) < 0.005
        and d["invoice"]["currency"] == "USD"
        and d["invoice"]["debit_to"] == DEBTORS_ACCOUNT
        and d["wallet"]["status"] == "Active"
    )
    emit({"step": "get_status_payable", "ok": ok, "data": d})


def test_get_status_cross_customer_not_found():
    emailA, custA, walletA = _fresh_customer()
    _credit_wallet(emailA, custA, 100)
    si = _create_submitted_si(custA, rate=50)
    emailB, custB, walletB = _fresh_customer()
    res = _status_as(emailB, si.name)
    code = (res.get("error") or {}).get("code")
    ok = res.get("ok") is False and code == "NOT_FOUND"
    emit({"step": "get_status_cross_customer_not_found", "ok": ok, "code": code})


def test_full_payment_succeeds():
    email, cust, wallet = _fresh_customer()
    _credit_wallet(email, cust, 300)
    si = _create_submitted_si(cust, rate=120)
    qr_name = _create_qr_linked_to(cust, email, si)

    balance_before = _wallet_balance(wallet)

    res = _pay_as(email, si.name)
    d = res.get("data") or {}
    tx_name = d.get("transaction_id")
    je_name = d.get("journal_entry")

    si_row = frappe.db.get_value(
        "Sales Invoice", si.name,
        ["status", "outstanding_amount"],
        as_dict=True,
    )
    qr_row = frappe.db.get_value(
        "Robot Quote Request", qr_name,
        ["payment_status", "sales_invoice_status",
         "sales_invoice_outstanding_amount_usd"],
        as_dict=True,
    ) if qr_name else {}

    tx_row = frappe.db.get_value(
        "Robot Wallet Transaction", tx_name,
        ["transaction_type", "direction", "debit_amount_usd",
         "linked_sales_invoice", "linked_quote_request", "linked_payment_entry"],
        as_dict=True,
    ) if tx_name else {}

    je_rows = frappe.db.sql(
        """SELECT account, debit_in_account_currency, credit_in_account_currency,
                  party_type, party, reference_type, reference_name
             FROM `tabJournal Entry Account`
            WHERE parent=%s ORDER BY idx""",
        (je_name,), as_dict=True,
    ) if je_name else []
    je_rows = [dict(r) for r in je_rows]

    balance_after = _wallet_balance(wallet)
    ledger_after = _ledger_sum(wallet)

    has_liab_debit = any(
        r["account"] == WALLET_LIABILITY_ACCOUNT
        and float(r["debit_in_account_currency"] or 0) == 120.0
        for r in je_rows
    )
    has_debtors_credit = any(
        r["account"] == DEBTORS_ACCOUNT
        and float(r["credit_in_account_currency"] or 0) == 120.0
        and r["reference_type"] == "Sales Invoice"
        and r["reference_name"] == si.name
        for r in je_rows
    )

    ok = (
        res.get("ok") is True
        and bool(tx_name) and bool(je_name)
        and abs(float(si_row["outstanding_amount"] or 0)) < 0.005
        and si_row["status"] == "Paid"
        and (qr_row.get("payment_status") == "Paid")
        and (qr_row.get("sales_invoice_status") == "Paid")
        and abs(float(qr_row.get("sales_invoice_outstanding_amount_usd") or 0)) < 0.005
        and tx_row.get("transaction_type") == "Spend"
        and tx_row.get("direction") == "Debit"
        and float(tx_row.get("debit_amount_usd") or 0) == 120.0
        and tx_row.get("linked_sales_invoice") == si.name
        and tx_row.get("linked_quote_request") == qr_name
        and not tx_row.get("linked_payment_entry")
        and has_liab_debit and has_debtors_credit
        and abs(balance_before - balance_after - 120.0) < 0.005
        and abs(balance_after - ledger_after) < 0.005
    )
    emit({
        "step": "full_payment_succeeds",
        "ok": ok,
        "si": si.name, "tx": tx_name, "je": je_name, "qr": qr_name,
        "balance_before": balance_before,
        "balance_after": balance_after,
        "ledger_after": ledger_after,
        "si_row": si_row, "qr_row": qr_row, "tx_row": tx_row,
        "je_rows": je_rows,
        "response_data": d,
    })


def test_partial_payment_succeeds():
    email, cust, wallet = _fresh_customer()
    _credit_wallet(email, cust, 100)  # less than the SI
    si = _create_submitted_si(cust, rate=150)
    qr_name = _create_qr_linked_to(cust, email, si)

    res = _pay_as(email, si.name, amount_usd=60)  # explicit partial
    d = res.get("data") or {}

    si_row = frappe.db.get_value(
        "Sales Invoice", si.name,
        ["status", "outstanding_amount"], as_dict=True,
    )
    qr_row = frappe.db.get_value(
        "Robot Quote Request", qr_name,
        ["payment_status", "sales_invoice_outstanding_amount_usd"],
        as_dict=True,
    ) if qr_name else {}
    bal = _wallet_balance(wallet)

    ok = (
        res.get("ok") is True
        and abs(float(d["allocated_usd"]) - 60.0) < 0.005
        and abs(float(si_row["outstanding_amount"] or 0) - 90.0) < 0.005
        and si_row["status"] in ("Partly Paid", "Partly Paid and Discounted")
        and qr_row.get("payment_status") == "Partly Paid"
        and abs(bal - 40.0) < 0.005
    )
    emit({
        "step": "partial_payment_succeeds",
        "ok": ok, "data": d,
        "si_row": si_row, "qr_row": qr_row, "wallet_balance": bal,
    })


def test_duplicate_same_amount_is_idempotent():
    email, cust, wallet = _fresh_customer()
    _credit_wallet(email, cust, 200)
    si = _create_submitted_si(cust, rate=80)

    r1 = _pay_as(email, si.name, amount_usd=80)
    r2 = _pay_as(email, si.name, amount_usd=80)
    d1 = r1.get("data") or {}
    d2 = r2.get("data") or {}

    # Count TX + JE rows -- there should be exactly one of each.
    tx_count = frappe.db.count(
        "Robot Wallet Transaction",
        {"idempotency_key": f"invoice-pay:{si.name}:8000", "docstatus": 1},
    )
    je_count_for_si = frappe.db.sql(
        """SELECT COUNT(DISTINCT je.name)
             FROM `tabJournal Entry` je
             JOIN `tabJournal Entry Account` jea ON jea.parent = je.name
            WHERE jea.reference_type = 'Sales Invoice'
              AND jea.reference_name = %s
              AND je.docstatus = 1""",
        (si.name,),
    )[0][0]
    bal = _wallet_balance(wallet)

    ok = (
        r1.get("ok") is True and r2.get("ok") is True
        and d1.get("transaction_id") == d2.get("transaction_id")
        and d1.get("journal_entry") == d2.get("journal_entry")
        and d2.get("idempotent") is True
        and tx_count == 1 and je_count_for_si == 1
        and abs(bal - 120.0) < 0.005
    )
    emit({
        "step": "duplicate_same_amount_is_idempotent",
        "ok": ok,
        "first": d1, "second": d2,
        "tx_count": tx_count, "je_count_for_si": je_count_for_si,
        "balance_after": bal,
    })


def test_insufficient_balance_blocked():
    email, cust, wallet = _fresh_customer()
    # No top-up: balance stays 0.
    si = _create_submitted_si(cust, rate=40)
    before_tx_count = frappe.db.count("Robot Wallet Transaction", {"wallet": wallet})
    # Send an explicit amount > balance so we hit the INSUFFICIENT_FUNDS branch
    # (the default-amount path with balance=0 lands on VALIDATION_ERROR
    # because min(outstanding, 0) = 0, which is rejected as non-positive).
    res = _pay_as(email, si.name, amount_usd=10)
    code = (res.get("error") or {}).get("code")
    after_tx_count = frappe.db.count("Robot Wallet Transaction", {"wallet": wallet})
    si_row = frappe.db.get_value(
        "Sales Invoice", si.name, ["status", "outstanding_amount"], as_dict=True,
    )
    ok = (
        res.get("ok") is False
        and code == "INSUFFICIENT_FUNDS"
        and before_tx_count == after_tx_count
        and abs(float(si_row["outstanding_amount"] or 0) - 40.0) < 0.005
    )
    emit({"step": "insufficient_balance_blocked", "ok": ok, "code": code,
          "tx_count_unchanged": before_tx_count == after_tx_count})


def test_cross_customer_pay_not_found():
    emailA, custA, _wA = _fresh_customer()
    _credit_wallet(emailA, custA, 80)
    si_A = _create_submitted_si(custA, rate=50)
    emailB, custB, _wB = _fresh_customer()
    _credit_wallet(emailB, custB, 100)
    res = _pay_as(emailB, si_A.name, amount_usd=50)
    code = (res.get("error") or {}).get("code")
    ok = res.get("ok") is False and code == "NOT_FOUND"
    emit({"step": "cross_customer_pay_not_found", "ok": ok, "code": code})


def test_cancelled_invoice_blocked():
    email, cust, _wallet = _fresh_customer()
    _credit_wallet(email, cust, 100)
    si = _create_submitted_si(cust, rate=20)
    si.reload()
    si.cancel()
    frappe.db.commit()
    res = _pay_as(email, si.name)
    code = (res.get("error") or {}).get("code")
    ok = res.get("ok") is False and code == "INVOICE_NOT_PAYABLE"
    emit({"step": "cancelled_invoice_blocked", "ok": ok, "code": code})


def test_already_paid_blocked():
    email, cust, _wallet = _fresh_customer()
    _credit_wallet(email, cust, 200)
    si = _create_submitted_si(cust, rate=30)
    # Full pay (default amount). After this SI.outstanding=0.
    _pay_as(email, si.name)
    # Second attempt with an explicit amount targets the ALREADY_PAID branch.
    # (Without an explicit amount the default resolves to min(0, balance) = 0
    # which correctly trips the VALIDATION_ERROR positive-amount guard, not
    # ALREADY_PAID.)
    res = _pay_as(email, si.name, amount_usd=5)
    code = (res.get("error") or {}).get("code")
    ok = res.get("ok") is False and code == "ALREADY_PAID"
    emit({"step": "already_paid_blocked", "ok": ok, "code": code})


def test_amount_exceeds_outstanding_blocked():
    email, cust, _wallet = _fresh_customer()
    _credit_wallet(email, cust, 500)
    si = _create_submitted_si(cust, rate=50)
    res = _pay_as(email, si.name, amount_usd=400)
    code = (res.get("error") or {}).get("code")
    ok = res.get("ok") is False and code == "AMOUNT_EXCEEDS_OUTSTANDING"
    emit({"step": "amount_exceeds_outstanding_blocked", "ok": ok, "code": code})


def test_accounting_not_ready_blocked():
    from iranrobot_backend.api import wallet as wallet_api
    email, cust, wallet = _fresh_customer()
    _credit_wallet(email, cust, 100)
    si = _create_submitted_si(cust, rate=40)
    before_tx_count = frappe.db.count("Robot Wallet Transaction", {"wallet": wallet})
    original = wallet_api._accounting_ready
    wallet_api._accounting_ready = lambda: False
    try:
        res = _pay_as(email, si.name)
    finally:
        wallet_api._accounting_ready = original
    code = (res.get("error") or {}).get("code")
    after_tx_count = frappe.db.count("Robot Wallet Transaction", {"wallet": wallet})
    ok = (
        res.get("ok") is False
        and code == "ACCOUNTING_NOT_READY"
        and before_tx_count == after_tx_count
    )
    emit({"step": "accounting_not_ready_blocked", "ok": ok, "code": code})


def test_invariant_wallet_cache_eq_ledger_and_je_refs_si():
    email, cust, wallet = _fresh_customer()
    _credit_wallet(email, cust, 200)
    si = _create_submitted_si(cust, rate=70)
    res = _pay_as(email, si.name)
    d = res.get("data") or {}
    tx_name, je_name = d.get("transaction_id"), d.get("journal_entry")

    cache = _wallet_balance(wallet)
    ledger = _ledger_sum(wallet)

    je_refs_si = bool(frappe.db.sql(
        """SELECT 1 FROM `tabJournal Entry Account`
            WHERE parent=%s AND reference_type='Sales Invoice'
              AND reference_name=%s LIMIT 1""",
        (je_name, si.name),
    ))

    si_row = frappe.db.get_value(
        "Sales Invoice", si.name,
        ["status", "outstanding_amount"], as_dict=True,
    )
    qr_name = _find_qr_name(si.name)
    qr_row = frappe.db.get_value(
        "Robot Quote Request", qr_name,
        ["sales_invoice_status", "sales_invoice_outstanding_amount_usd",
         "payment_status"],
        as_dict=True,
    ) if qr_name else {}

    qr_matches_si = (
        (not qr_name)
        or (
            qr_row.get("sales_invoice_status") == si_row["status"]
            and abs(
                float(qr_row.get("sales_invoice_outstanding_amount_usd") or 0)
                - float(si_row["outstanding_amount"] or 0)
            ) < 0.005
        )
    )

    ok = (
        abs(cache - ledger) < 0.005
        and je_refs_si
        and qr_matches_si
    )
    emit({
        "step": "invariant_cache_eq_ledger_and_je_refs_si",
        "ok": ok, "cache": cache, "ledger": ledger,
        "je_refs_si": je_refs_si,
        "qr_matches_si": qr_matches_si,
        "qr_row": qr_row, "si_row": si_row,
    })


def _find_qr_name(si_name):
    return frappe.db.get_value(
        "Robot Quote Request",
        {"erpnext_sales_invoice": si_name},
        "name",
    )


# ---------------------------------------------------------------- runner


def run_all():
    print("\n=== Phase 8D-2 bench-side smoke ===\n")
    for fn in (
        test_get_status_payable,
        test_get_status_cross_customer_not_found,
        test_full_payment_succeeds,
        test_partial_payment_succeeds,
        test_duplicate_same_amount_is_idempotent,
        test_insufficient_balance_blocked,
        test_cross_customer_pay_not_found,
        test_cancelled_invoice_blocked,
        test_already_paid_blocked,
        test_amount_exceeds_outstanding_blocked,
        test_accounting_not_ready_blocked,
        test_invariant_wallet_cache_eq_ledger_and_je_refs_si,
    ):
        try:
            fn()
        except Exception as e:
            emit({"step": fn.__name__, "exception": str(e),
                  "exception_type": type(e).__name__})
    print("\n=== Phase 8D-2 bench-side smoke complete ===")
