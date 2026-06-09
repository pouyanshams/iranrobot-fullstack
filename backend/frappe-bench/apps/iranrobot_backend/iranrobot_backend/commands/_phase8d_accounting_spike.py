"""Phase 8D-0 -- Accounting validation spike.

Empirically tests the wallet accounting model proposed in the Phase 8D plan
on the live dev site. Creates fresh isolated fixtures (a new customer, a new
Sales Invoice, a new Robot Quote Request) and observes:

  Test A  -- Wallet top-up Payment Entry
            * payment_type=Receive, paid_from=Customer Wallet Liability,
              paid_to=Cash. Verifies submit works and GL is:
                  DEBIT Cash, CREDIT Customer Wallet Liability.

  Test B  -- Sales Invoice settlement Payment Entry
            * payment_type=Receive, paid_from=Debtors, paid_to=Customer
              Wallet Liability, references=[{SI, allocated_amount}].
              Verifies:
                - PE submits cleanly
                - SI.outstanding_amount decreases to zero
                - SI.status becomes Paid (or Partly Paid)
                - GL is balanced (debit Liability, credit Debtors)
                - Phase 7D `sync_payment_entry_back_to_quote_request` updated
                  the linked Robot Quote Request's payment_status
                - Idempotency rerun finds the same PE and does NOT create
                  a duplicate.

Run via::

    bench --site iranrobot.localhost execute \\
        iranrobot_backend.commands._phase8d_accounting_spike.run_all

All output is emitted as `PHASE8D_SPIKE::<json>` lines so the spike can be
parsed by future tooling. The spike is read-only outside of its own
fixtures.
"""

from __future__ import annotations

import json
import secrets

import frappe

from iranrobot_backend.commands.wallet_accounting_bootstrap import (
    COMPANY,
    WALLET_LIABILITY_ACCOUNT,
    WALLET_MOP,
)


CASH_ACCOUNT = "Cash - IR"
DEBTORS_ACCOUNT = "Debtors - IR"
INCOME_ACCOUNT = "Sales - IR"


def emit(payload):
    print("PHASE8D_SPIKE::" + json.dumps(payload, default=str))


# ============================================================ fixture helpers


def _fresh_customer():
    """Sign up a fresh Website User + lazy-create their wallet."""
    from iranrobot_backend.api.auth import signup
    from iranrobot_backend.api._session import (
        get_or_create_customer_for_user,
        get_or_create_wallet_for_customer,
    )

    suffix = secrets.token_hex(4)
    email = f"phase8d_spike_{suffix}@example.com"
    pwd = "ChangeMe-123-Strong"

    original = frappe.session.user
    frappe.set_user("Guest")
    try:
        res = signup(
            email=email, password=pwd, confirm_password=pwd,
            first_name="Phase8D", last_name="Spike",
            preferred_language="en",
        )
    finally:
        frappe.set_user(original)
    if not res.get("ok"):
        raise RuntimeError(f"signup failed: {res}")
    _contact, cust = get_or_create_customer_for_user(email)
    wallet = get_or_create_wallet_for_customer(cust)
    frappe.db.commit()
    return email, cust, wallet


def _find_test_item():
    """Find any existing Item we can put on the SI line. Prefer an item that's
    linked from a Robot Product (the catalog seed)."""
    code = frappe.db.get_value(
        "Robot Product",
        filters={"erpnext_item": ["!=", ""]},
        fieldname="erpnext_item",
    )
    if code and frappe.db.exists("Item", code):
        return code
    any_item = frappe.db.get_value("Item", filters={"disabled": 0}, fieldname="name")
    if any_item:
        return any_item
    raise RuntimeError(
        "Spike could not find any Item to put on the SI. Has the catalog "
        "seed been run?"
    )


def _create_submitted_si(customer: str, item_code: str, rate: float = 120.0):
    """Create + submit a Sales Invoice for this customer with one item line."""
    si = frappe.get_doc({
        "doctype": "Sales Invoice",
        "customer": customer,
        "company": COMPANY,
        "currency": "USD",
        "posting_date": frappe.utils.today(),
        "due_date": frappe.utils.today(),
        "set_posting_time": 1,
        "items": [{
            "item_code": item_code,
            "qty": 1,
            "rate": rate,
            "uom": "Nos",
            "income_account": INCOME_ACCOUNT,
        }],
    })
    si.insert(ignore_permissions=True)
    si.submit()
    frappe.db.commit()
    return si


def _link_qr_to_si(customer: str, email: str, si):
    """Create a Robot Quote Request and link it to the SI so Phase 7D's
    `sync_payment_entry_back_to_quote_request` hook can find the QR when the
    settlement PE submits."""
    rp = frappe.db.get_value("Robot Product", filters={}, fieldname="name")
    if not rp:
        emit({"step": "link_qr_to_si", "skipped": True, "reason": "no Robot Product available"})
        return None

    qr = frappe.get_doc({
        "doctype": "Robot Quote Request",
        "customer": customer,
        "user_email": email,
        "customer_name": "Phase 8D Spike",
        "email": email,
        "phone": "",
        "language": "en",
        "submitted_at": frappe.utils.now_datetime(),
        "status": "New",
        "message": "Phase 8D spike fixture",
        "items": [{
            "robot_product": rp,
            "product_name": "Phase 8D Item",
            "mode": "buy",
            "quantity": 1,
            "unit_price_usd": float(si.grand_total or 0),
        }],
    })
    qr.insert(ignore_permissions=True)

    qr.db_set("erpnext_sales_invoice", si.name, update_modified=False)
    qr.db_set("sales_invoice_status", si.status, update_modified=False)
    qr.db_set("sales_invoice_grand_total_usd", float(si.grand_total or 0), update_modified=False)
    qr.db_set(
        "sales_invoice_outstanding_amount_usd",
        float(si.outstanding_amount or 0),
        update_modified=False,
    )
    qr.db_set("sales_invoice_created_at", frappe.utils.now_datetime(), update_modified=False)
    frappe.db.commit()
    return qr.name


def _gl_for_pe(pe_name):
    rows = frappe.db.sql(
        """SELECT account, debit, credit, against, against_voucher_type,
                  against_voucher
           FROM `tabGL Entry`
           WHERE voucher_type = 'Payment Entry'
             AND voucher_no  = %s
             AND is_cancelled = 0
           ORDER BY account""",
        (pe_name,),
        as_dict=True,
    )
    return [
        {
            "account": r["account"],
            "debit": float(r["debit"] or 0),
            "credit": float(r["credit"] or 0),
            "against_voucher": r["against_voucher"],
        }
        for r in rows
    ]


def _existing_settlement_pe(si_name: str, customer: str, amount: float):
    rows = frappe.db.sql(
        """SELECT pe.name
             FROM `tabPayment Entry` pe
             JOIN `tabPayment Entry Reference` per ON per.parent = pe.name
            WHERE per.reference_doctype = 'Sales Invoice'
              AND per.reference_name    = %s
              AND pe.docstatus          = 1
              AND pe.party              = %s
              AND ABS(pe.paid_amount - %s) < 0.005
            LIMIT 1""",
        (si_name, customer, amount),
    )
    return rows[0][0] if rows else None


# ============================================================ Test A


def test_a_topup_pe(customer: str, amount: float = 100.0):
    """Create a Payment Entry representing approved wallet top-up.

    Receive  paid_from=Customer Wallet Liability  paid_to=Cash
    Expected GL: DEBIT Cash, CREDIT Customer Wallet Liability.
    """
    emit({"step": "test_a_topup_pe", "starting": True, "customer": customer, "amount": amount})

    pe = frappe.get_doc({
        "doctype": "Payment Entry",
        "naming_series": "ACC-PAY-.YYYY.-",
        "payment_type": "Receive",
        "party_type": "Customer",
        "party": customer,
        "company": COMPANY,
        "posting_date": frappe.utils.today(),
        "mode_of_payment": WALLET_MOP,
        "paid_from": WALLET_LIABILITY_ACCOUNT,
        "paid_from_account_currency": "USD",
        "paid_to": CASH_ACCOUNT,
        "paid_to_account_currency": "USD",
        "paid_amount": amount,
        "received_amount": amount,
        "source_exchange_rate": 1,
        "target_exchange_rate": 1,
        "reference_no": "PHASE8D-SPIKE-TOPUP",
        "reference_date": frappe.utils.today(),
    })
    try:
        pe.insert(ignore_permissions=True)
        pe.submit()
        frappe.db.commit()
    except Exception as e:
        emit({
            "step": "test_a_topup_pe",
            "ok": False,
            "error": str(e),
            "exception_type": type(e).__name__,
        })
        return None

    gl = _gl_for_pe(pe.name)
    debit_cash = sum(r["debit"] for r in gl if r["account"] == CASH_ACCOUNT)
    credit_liab = sum(r["credit"] for r in gl if r["account"] == WALLET_LIABILITY_ACCOUNT)
    ok = abs(debit_cash - amount) < 0.005 and abs(credit_liab - amount) < 0.005
    emit({
        "step": "test_a_topup_pe",
        "ok": ok,
        "pe": pe.name,
        "gl_entries": gl,
        "debit_cash": debit_cash,
        "credit_liability": credit_liab,
        "expected_amount": amount,
    })
    return pe.name


# ============================================================ Test B


def test_b_settlement_pe(customer: str, email: str, amount: float = 120.0):
    """Create a Sales Invoice + a settlement Payment Entry that allocates the
    invoice from the wallet liability. Verify GL, SI outstanding, status, and
    Phase 7D QR sync.
    """
    emit({"step": "test_b_settlement_pe", "starting": True, "customer": customer})

    try:
        item_code = _find_test_item()
    except Exception as e:
        emit({"step": "test_b_settlement_pe", "ok": False, "fixture_error": str(e)})
        return None

    try:
        si = _create_submitted_si(customer, item_code, rate=amount)
    except Exception as e:
        emit({
            "step": "test_b_settlement_pe",
            "ok": False,
            "si_creation_error": str(e),
            "exception_type": type(e).__name__,
        })
        return None

    qr_name = _link_qr_to_si(customer, email, si)

    outstanding_before = float(si.outstanding_amount or 0)
    status_before = si.status
    emit({
        "step": "test_b_settlement_pe",
        "fixture": "created",
        "item_code": item_code,
        "si": si.name,
        "si_grand_total": float(si.grand_total or 0),
        "si_outstanding_before": outstanding_before,
        "si_status_before": status_before,
        "si_debit_to": si.debit_to,
        "qr": qr_name,
    })

    # Idempotency pre-check: if a previous spike run already created the PE,
    # short-circuit before insert.
    existing = _existing_settlement_pe(si.name, customer, amount)
    if existing:
        emit({"step": "test_b_settlement_pe", "idempotent_short_circuit": existing})
        return existing

    pe = frappe.get_doc({
        "doctype": "Payment Entry",
        "naming_series": "ACC-PAY-.YYYY.-",
        "payment_type": "Receive",
        "party_type": "Customer",
        "party": customer,
        "company": COMPANY,
        "posting_date": frappe.utils.today(),
        "mode_of_payment": WALLET_MOP,
        "paid_from": DEBTORS_ACCOUNT,
        "paid_from_account_currency": "USD",
        "paid_to": WALLET_LIABILITY_ACCOUNT,
        "paid_to_account_currency": "USD",
        "paid_amount": amount,
        "received_amount": amount,
        "source_exchange_rate": 1,
        "target_exchange_rate": 1,
        "reference_no": "PHASE8D-SPIKE-SETTLE",
        "reference_date": frappe.utils.today(),
        "references": [{
            "reference_doctype": "Sales Invoice",
            "reference_name": si.name,
            "allocated_amount": amount,
            "total_amount": float(si.grand_total or 0),
            "outstanding_amount": outstanding_before,
        }],
    })
    try:
        pe.insert(ignore_permissions=True)
        pe.submit()
        frappe.db.commit()
    except Exception as e:
        emit({
            "step": "test_b_settlement_pe",
            "ok": False,
            "pe_submit_error": str(e),
            "exception_type": type(e).__name__,
        })
        return None

    si.reload()
    outstanding_after = float(si.outstanding_amount or 0)
    status_after = si.status
    gl = _gl_for_pe(pe.name)
    debit_liab = sum(r["debit"] for r in gl if r["account"] == WALLET_LIABILITY_ACCOUNT)
    credit_debtors = sum(r["credit"] for r in gl if r["account"] == DEBTORS_ACCOUNT)

    qr_payload = {}
    if qr_name and frappe.db.exists("Robot Quote Request", qr_name):
        qr = frappe.db.get_value(
            "Robot Quote Request",
            qr_name,
            [
                "payment_status",
                "sales_invoice_status",
                "sales_invoice_outstanding_amount_usd",
                "latest_payment_entry",
            ],
            as_dict=True,
        ) or {}
        qr_payload = dict(qr)

    rerun_existing = _existing_settlement_pe(si.name, customer, amount)

    ok = (
        abs(outstanding_after - 0.0) < 0.005
        and status_after in ("Paid", "Partly Paid", "Submitted")
        and abs(debit_liab - amount) < 0.005
        and abs(credit_debtors - amount) < 0.005
    )
    emit({
        "step": "test_b_settlement_pe",
        "ok": ok,
        "pe": pe.name,
        "si_outstanding_before": outstanding_before,
        "si_outstanding_after": outstanding_after,
        "si_status_before": status_before,
        "si_status_after": status_after,
        "gl_entries": gl,
        "debit_liability": debit_liab,
        "credit_debtors": credit_debtors,
        "qr": qr_payload,
        "qr_sync_ok": bool(qr_payload) and qr_payload.get("latest_payment_entry") == pe.name
                      and qr_payload.get("payment_status") in ("Paid", "Partly Paid"),
        "idempotent_rerun_finds_same_pe": rerun_existing == pe.name,
    })
    return pe.name


# ============================================================ runner


# ============================================================ Test B-2 (JE)


def test_b2_settlement_via_je(customer: str, email: str, amount: float = 120.0):
    """Alternative settlement path using a Journal Entry.

    Test B's Payment Entry approach failed because ERPNext's auto-party logic
    only sets `party` on the party_account leg (paid_from for a Receive PE).
    When both legs hit Receivable accounts, the non-party leg lacks `party`
    and ERPNext throws "Customer is required against Receivable account
    Customer Wallet Liability - IR".

    A Journal Entry lets us declare `party` on both legs explicitly, and JEs
    that reference a Sales Invoice (`reference_type` + `reference_name` on
    the credit row) post against the invoice exactly like a Payment Entry
    would: SI.outstanding_amount decreases and SI.status flips on submit.
    Phase 7D's `sync_sales_invoice_back_to_quote_request` fires on SI
    on_update and updates the linked Robot Quote Request.
    """
    emit({"step": "test_b2_settlement_via_je", "starting": True, "customer": customer})

    try:
        item_code = _find_test_item()
    except Exception as e:
        emit({"step": "test_b2_settlement_via_je", "ok": False, "fixture_error": str(e)})
        return None

    try:
        si = _create_submitted_si(customer, item_code, rate=amount)
    except Exception as e:
        emit({
            "step": "test_b2_settlement_via_je",
            "ok": False,
            "si_creation_error": str(e),
            "exception_type": type(e).__name__,
        })
        return None

    qr_name = _link_qr_to_si(customer, email, si)

    outstanding_before = float(si.outstanding_amount or 0)
    status_before = si.status
    emit({
        "step": "test_b2_settlement_via_je",
        "fixture": "created",
        "item_code": item_code,
        "si": si.name,
        "si_grand_total": float(si.grand_total or 0),
        "si_outstanding_before": outstanding_before,
        "si_status_before": status_before,
        "qr": qr_name,
    })

    je = frappe.get_doc({
        "doctype": "Journal Entry",
        "voucher_type": "Journal Entry",
        "posting_date": frappe.utils.today(),
        "company": COMPANY,
        "user_remark": f"Phase 8D spike wallet settlement for {si.name}",
        "accounts": [
            {
                # Decrease wallet liability (we owe the customer less).
                "account": WALLET_LIABILITY_ACCOUNT,
                "debit_in_account_currency": amount,
                "party_type": "Customer",
                "party": customer,
            },
            {
                # Decrease invoice receivable (customer owes us less).
                "account": DEBTORS_ACCOUNT,
                "credit_in_account_currency": amount,
                "party_type": "Customer",
                "party": customer,
                "reference_type": "Sales Invoice",
                "reference_name": si.name,
            },
        ],
    })
    try:
        je.insert(ignore_permissions=True)
        je.submit()
        frappe.db.commit()
    except Exception as e:
        emit({
            "step": "test_b2_settlement_via_je",
            "ok": False,
            "je_submit_error": str(e),
            "exception_type": type(e).__name__,
        })
        return None

    si.reload()
    outstanding_after = float(si.outstanding_amount or 0)
    status_after = si.status

    # GL for the JE
    gl_rows = frappe.db.sql(
        """SELECT account, debit, credit
             FROM `tabGL Entry`
            WHERE voucher_type = 'Journal Entry' AND voucher_no = %s
              AND is_cancelled = 0
            ORDER BY account""",
        (je.name,),
        as_dict=True,
    )
    gl = [
        {"account": r["account"], "debit": float(r["debit"] or 0), "credit": float(r["credit"] or 0)}
        for r in gl_rows
    ]
    debit_liab = sum(r["debit"] for r in gl if r["account"] == WALLET_LIABILITY_ACCOUNT)
    credit_debtors = sum(r["credit"] for r in gl if r["account"] == DEBTORS_ACCOUNT)

    qr_payload = {}
    if qr_name and frappe.db.exists("Robot Quote Request", qr_name):
        qr_payload = frappe.db.get_value(
            "Robot Quote Request",
            qr_name,
            [
                "payment_status",
                "sales_invoice_status",
                "sales_invoice_outstanding_amount_usd",
                "latest_payment_entry",
            ],
            as_dict=True,
        ) or {}
        qr_payload = dict(qr_payload)

    ok_si = abs(outstanding_after - 0.0) < 0.005 and status_after in ("Paid", "Submitted")
    ok_gl = abs(debit_liab - amount) < 0.005 and abs(credit_debtors - amount) < 0.005
    # Note: QR.latest_payment_entry tracks Payment Entry only; for a JE
    # settlement it stays null. The SI sync hook still updates QR.payment_status.
    ok_qr_sync = bool(qr_payload) and qr_payload.get("payment_status") == "Paid"

    emit({
        "step": "test_b2_settlement_via_je",
        "ok": ok_si and ok_gl and ok_qr_sync,
        "je": je.name,
        "si_outstanding_before": outstanding_before,
        "si_outstanding_after": outstanding_after,
        "si_status_before": status_before,
        "si_status_after": status_after,
        "gl_entries": gl,
        "debit_liability": debit_liab,
        "credit_debtors": credit_debtors,
        "qr": qr_payload,
        "qr_sync_ok": ok_qr_sync,
        "notes": (
            "QR.latest_payment_entry stays null for a JE settlement (PE-only "
            "field). QR.payment_status is updated by "
            "sync_sales_invoice_back_to_quote_request via SI.on_update."
        ),
    })
    return je.name


def run_all():
    print("\n=== Phase 8D-0 accounting validation spike ===\n")
    email, cust, wallet = _fresh_customer()
    emit({"step": "fixture", "email": email, "customer": cust, "wallet": wallet})
    test_a_topup_pe(cust, amount=100.0)
    test_b_settlement_pe(cust, email, amount=120.0)
    test_b2_settlement_via_je(cust, email, amount=120.0)
    print("\n=== Phase 8D-0 spike complete ===")
