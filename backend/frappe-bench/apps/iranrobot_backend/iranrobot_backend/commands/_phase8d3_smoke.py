"""Phase 8D-3 bench-side smoke -- get_my_invoice_detail.wallet_payments.

After Phase 8D-2 the wallet settlement creates a Robot Wallet Transaction
(Spend) and a Journal Entry, but the Phase 7D `payments` field is PE-only
so wallet settlements would be invisible. Phase 8D-3 extends the invoice
detail response with a parallel `wallet_payments` array.

This smoke verifies:
  1. After a successful pay_invoice_with_wallet, get_my_invoice_detail
     returns the wallet_payments row with name == transaction_id and
     journal_entry == the settlement JE.
  2. Partial payments produce multiple wallet_payments rows.
  3. Invoices without wallet spend return wallet_payments=[].
  4. The projection is customer-safe (no audit fields leaked).

Run via::

    bench --site iranrobot.localhost execute \\
        iranrobot_backend.commands._phase8d3_smoke.run_all
"""

from __future__ import annotations

import json
import secrets

import frappe

from iranrobot_backend.commands.wallet_accounting_bootstrap import COMPANY


INCOME_ACCOUNT = "Sales - IR"


def emit(payload):
    print("PHASE8D3::" + json.dumps(payload, default=str))


# ---------------------------------------------------------------- helpers


def _fresh_customer():
    from iranrobot_backend.api._session import (
        get_or_create_customer_for_user,
        get_or_create_wallet_for_customer,
    )
    suffix = secrets.token_hex(4)
    email = f"phase8d3_{suffix}@example.com"
    prior = getattr(frappe.flags, "in_import", False)
    frappe.flags.in_import = True
    try:
        user = frappe.get_doc({
            "doctype": "User", "email": email,
            "first_name": "Phase8D3", "last_name": "Smoke",
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
    req = res["data"]["request_id"]
    appr = staff_approve_top_up_request(name=req, bank_reference="REF-8D3")
    frappe.db.commit()
    if not appr.get("ok"):
        raise RuntimeError(f"staff_approve_top_up_request failed: {appr}")


def _find_test_item():
    code = frappe.db.get_value(
        "Robot Product", filters={"erpnext_item": ["!=", ""]},
        fieldname="erpnext_item",
    )
    if code and frappe.db.exists("Item", code):
        return code
    return frappe.db.get_value("Item", filters={"disabled": 0}, fieldname="name")


def _submitted_si(customer, rate):
    si = frappe.get_doc({
        "doctype": "Sales Invoice",
        "customer": customer, "company": COMPANY, "currency": "USD",
        "posting_date": frappe.utils.today(), "due_date": frappe.utils.today(),
        "set_posting_time": 1,
        "items": [{
            "item_code": _find_test_item(), "qty": 1, "rate": rate,
            "uom": "Nos", "income_account": INCOME_ACCOUNT,
        }],
    })
    si.insert(ignore_permissions=True)
    si.submit()
    frappe.db.commit()
    return si


def _pay_as(email, si_name, amount=None):
    from iranrobot_backend.api.wallet import pay_invoice_with_wallet
    original = frappe.session.user
    frappe.set_user(email)
    try:
        return pay_invoice_with_wallet(
            sales_invoice_name=si_name, amount_usd=amount,
        )
    finally:
        frappe.set_user(original)


def _detail_as(email, si_name):
    from iranrobot_backend.api.invoices import get_my_invoice_detail
    original = frappe.session.user
    frappe.set_user(email)
    try:
        return get_my_invoice_detail(name=si_name)
    finally:
        frappe.set_user(original)


# ---------------------------------------------------------------- tests


def test_invoice_detail_includes_wallet_payment():
    email, cust, _w = _fresh_customer()
    _credit_wallet(email, cust, 300)
    si = _submitted_si(cust, rate=120)
    pay = _pay_as(email, si.name)
    pay_data = pay.get("data") or {}
    tx_id = pay_data.get("transaction_id")
    je_id = pay_data.get("journal_entry")

    det = _detail_as(email, si.name)
    rec = (det.get("data") or {}).get("record") or {}
    wallet_payments = rec.get("wallet_payments") or []
    payments = rec.get("payments") or []

    ok = (
        det.get("ok") is True
        and len(wallet_payments) == 1
        and wallet_payments[0].get("name") == tx_id
        and wallet_payments[0].get("transaction_type") == "Spend"
        and wallet_payments[0].get("journal_entry") == je_id
        and float(wallet_payments[0].get("debit_amount_usd") or 0) == 120.0
        and wallet_payments[0].get("linked_sales_invoice") == si.name
    )
    emit({
        "step": "invoice_detail_includes_wallet_payment",
        "ok": ok,
        "tx": tx_id, "je": je_id, "si": si.name,
        "wallet_payments": wallet_payments,
        "payments_count": len(payments),
    })


def test_partial_payments_create_multiple_wallet_payment_rows():
    email, cust, _w = _fresh_customer()
    _credit_wallet(email, cust, 200)
    si = _submitted_si(cust, rate=100)
    r1 = _pay_as(email, si.name, amount=30)
    r2 = _pay_as(email, si.name, amount=70)
    det = _detail_as(email, si.name)
    rec = (det.get("data") or {}).get("record") or {}
    wp = rec.get("wallet_payments") or []
    tx_ids = {row.get("name") for row in wp}
    sum_debits = sum(float(row.get("debit_amount_usd") or 0) for row in wp)
    ok = (
        len(wp) == 2
        and (r1["data"]["transaction_id"] in tx_ids)
        and (r2["data"]["transaction_id"] in tx_ids)
        and abs(sum_debits - 100.0) < 0.005
        and abs(float(rec.get("outstanding_amount") or 0)) < 0.005
    )
    emit({
        "step": "partial_payments_create_multiple_wallet_payment_rows",
        "ok": ok,
        "wallet_payments_count": len(wp),
        "sum_debits": sum_debits,
        "outstanding": rec.get("outstanding_amount"),
    })


def test_invoice_without_wallet_spend_returns_empty():
    email, cust, _w = _fresh_customer()
    # No top-up, no payments
    si = _submitted_si(cust, rate=50)
    det = _detail_as(email, si.name)
    rec = (det.get("data") or {}).get("record") or {}
    wp = rec.get("wallet_payments")
    ok = isinstance(wp, list) and len(wp) == 0
    emit({
        "step": "invoice_without_wallet_spend_returns_empty",
        "ok": ok, "wallet_payments": wp,
    })


def test_customer_safe_projection_no_internals():
    email, cust, _w = _fresh_customer()
    _credit_wallet(email, cust, 100)
    si = _submitted_si(cust, rate=40)
    _pay_as(email, si.name)
    det = _detail_as(email, si.name)
    rec = (det.get("data") or {}).get("record") or {}
    wp = rec.get("wallet_payments") or []
    forbidden = {
        "posted_by", "posted_ip", "idempotency_key", "reason",
        "linked_payment_entry", "owner", "modified_by", "modified",
        "creation", "docstatus", "wallet", "customer",
        "linked_counter_transaction", "currency",
    }
    leaked = set()
    for row in wp:
        leaked |= set(row.keys()) & forbidden
    ok = not leaked
    emit({
        "step": "customer_safe_projection_no_internals",
        "ok": ok,
        "leaked": list(leaked),
        "sample_keys": list(wp[0].keys()) if wp else [],
    })


# ---------------------------------------------------------------- runner


def run_all():
    print("\n=== Phase 8D-3 bench-side smoke ===\n")
    for fn in (
        test_invoice_detail_includes_wallet_payment,
        test_partial_payments_create_multiple_wallet_payment_rows,
        test_invoice_without_wallet_spend_returns_empty,
        test_customer_safe_projection_no_internals,
    ):
        try:
            fn()
        except Exception as e:
            emit({
                "step": fn.__name__,
                "exception": str(e), "exception_type": type(e).__name__,
            })
    print("\n=== Phase 8D-3 bench-side smoke complete ===")
