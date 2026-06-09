"""Phase 7D -- Customer-facing Sales Invoice + Payment Entry read APIs.

    iranrobot_backend.api.invoices.get_my_invoices        GET   auth required
    iranrobot_backend.api.invoices.get_my_invoice_detail  GET   auth required

Ownership: every read filters server-side by the session user's linked
ERPNext Customer (Phase 4 lazy helper). Cross-customer access returns
NOT_FOUND (not 403) to avoid existence leak via name enumeration.

Payment Entry exposure (read-only):
  The detail endpoint surfaces the customer-safe Payment Entry summary for any
  PE that references the Sales Invoice (`Payment Entry Reference` child where
  reference_doctype="Sales Invoice"). The customer NEVER sees bank account
  numbers, internal references, accounting heads, cost centres, GL entries,
  modes-of-payment internals (only the label), owner / modified_by, or any
  gateway secret. The whitelisted Sales Invoice fields likewise exclude the
  full taxes table, internal_notes, accounting fields, and base-currency
  columns.
"""

from __future__ import annotations

import frappe
from frappe import _

from iranrobot_backend.api._response import err, ok
from iranrobot_backend.api._session import (
    get_or_create_customer_for_user,
    is_guest,
)


# ---------- Customer-safe field allow-lists ----------

_SI_LIST_FIELDS = (
    "name",
    "status",
    "posting_date",
    "due_date",
    "customer_name",
    "grand_total",
    "outstanding_amount",
    "currency",
    "creation",
)

_SI_DETAIL_FIELDS = (
    "name",
    "status",
    "posting_date",
    "due_date",
    "customer_name",
    "grand_total",
    "total",
    "net_total",
    "outstanding_amount",
    "currency",
    "po_no",
    "creation",
    "modified",
)

_SI_ITEM_DETAIL_FIELDS = (
    "idx",
    "item_code",
    "item_name",
    "description",
    "qty",
    "uom",
    "rate",
    "amount",
)

_PE_SUMMARY_FIELDS = (
    "name",
    "posting_date",
    "paid_amount",
    "received_amount",
    "mode_of_payment",
    "reference_no",
    "reference_date",
    "status",
    "docstatus",
)


def _project(doc: dict, allow_list: tuple) -> dict:
    return {k: doc.get(k) for k in allow_list if k in doc}


def _resolve_customer() -> str | None:
    if is_guest():
        return None
    try:
        _contact_id, cust_id = get_or_create_customer_for_user(frappe.session.user)
        return cust_id
    except Exception as e:
        frappe.log_error(title="invoices._resolve_customer", message=str(e))
        return None


def _payment_status_label(si: dict) -> str:
    """Customer-facing 5-value enum derived from Sales Invoice state.
    Mirrors `_derive_payment_status` in api/requests.py without importing it
    (avoids a circular-ish dependency just for one helper)."""
    status = (si.get("status") or "").strip()
    docstatus = si.get("docstatus")
    grand_total = float(si.get("grand_total") or 0)
    outstanding = float(si.get("outstanding_amount") or 0)

    if docstatus == 2:
        return "Cancelled"
    if status in ("Paid",):
        return "Paid"
    if status in ("Partly Paid", "Partly Paid and Discounted"):
        return "Partly Paid"
    if status in ("Overdue", "Overdue and Discounted"):
        return "Overdue"
    if status in ("Unpaid", "Unpaid and Discounted"):
        return "Unpaid"
    if docstatus == 0:
        return "Unpaid"
    if grand_total <= 0 or outstanding <= 0:
        return "Paid"
    if outstanding < grand_total:
        return "Partly Paid"
    return "Unpaid"


def _si_back_links(si_name: str) -> dict:
    """Best-effort back-pointers: which Robot Quote Request created this SI?
    From there, surface the Quotation + Sales Order ids too -- so the
    customer can pivot through the entire commercial chain from one record."""
    row = frappe.db.get_value(
        "Robot Quote Request",
        {"erpnext_sales_invoice": si_name},
        ["name", "erpnext_quotation", "erpnext_sales_order"],
        as_dict=True,
    )
    if not row:
        return {}
    return {
        "linked_quote_request": row.name,
        "linked_quotation": row.erpnext_quotation,
        "linked_sales_order": row.erpnext_sales_order,
    }


# Phase 8D-3 -- wallet payments projection.
# Wallet settlements are Journal Entries (not Payment Entries), so they don't
# show up in `_payment_summary_for_invoice`. The frontend invoice drawer reads
# both lists and renders them in separate sections. The fields below are the
# ONLY ones surfaced for wallet payments -- audit-only fields (`posted_by`,
# `posted_ip`, `idempotency_key`, `reason`, `linked_payment_entry`) are
# deliberately excluded.
_WALLET_PAYMENT_PUBLIC_FIELDS = (
    "name",                  # WT-2026-...
    "transaction_type",      # always "Spend" here
    "debit_amount_usd",
    "balance_after_usd",
    "posted_at",
    "linked_sales_invoice",
    "linked_quote_request",
    "notes",
)


def _wallet_je_for_tx(wt_name: str) -> str | None:
    """Return the submitted Journal Entry created by `pay_invoice_with_wallet`
    for this Robot Wallet Transaction. The JE doesn't have a direct
    back-link to the transaction; instead, the settlement helper writes the
    marker `wallet_tx=<TX_NAME>` into `Journal Entry.user_remark`, which we
    LIKE-search here. Single row per wallet TX by design."""
    if not wt_name:
        return None
    return frappe.db.get_value(
        "Journal Entry",
        {
            "user_remark": ["like", f"%wallet_tx={wt_name}%"],
            "docstatus": 1,
        },
        "name",
    )


def _wallet_payments_for_invoice(si_name: str) -> list[dict]:
    """Return customer-safe wallet-spend rows targeting this Sales Invoice.

    The caller (`get_my_invoice_detail`) has already enforced
    `SI.customer == session_customer`, so cross-customer leakage is
    impossible by construction here. We re-filter on `linked_sales_invoice`
    rather than re-joining on customer.

    NEVER returns posted_by / posted_ip / idempotency_key / reason /
    linked_payment_entry / owner / modified_by / raw internals.
    """
    if not si_name:
        return []
    try:
        rows = frappe.get_all(
            "Robot Wallet Transaction",
            filters={
                "linked_sales_invoice": si_name,
                "transaction_type": "Spend",
                "docstatus": 1,
            },
            fields=list(_WALLET_PAYMENT_PUBLIC_FIELDS),
            order_by="posted_at desc, creation desc",
            ignore_permissions=True,
        )
    except Exception as e:
        frappe.log_error(title="_wallet_payments_for_invoice", message=str(e))
        return []
    out: list[dict] = []
    for r in rows:
        entry = _project(r, _WALLET_PAYMENT_PUBLIC_FIELDS)
        entry["journal_entry"] = _wallet_je_for_tx(r["name"])
        out.append(entry)
    return out


def _payment_summary_for_invoice(si_name: str) -> list[dict]:
    """Return the customer-safe summary of every SUBMITTED Payment Entry
    referencing this Sales Invoice. Draft / Cancelled PEs are excluded -- a
    customer should only see payments that have actually been recorded."""
    refs = frappe.db.sql(
        """
        SELECT per.parent AS pe_name, per.allocated_amount
          FROM `tabPayment Entry Reference` per
          JOIN `tabPayment Entry` pe ON pe.name = per.parent
         WHERE per.reference_doctype = 'Sales Invoice'
           AND per.reference_name    = %s
           AND pe.docstatus          = 1
         ORDER BY pe.posting_date DESC, pe.creation DESC
        """,
        (si_name,),
        as_dict=True,
    )
    out: list[dict] = []
    for r in refs:
        pe = frappe.db.get_value(
            "Payment Entry",
            r["pe_name"],
            list(_PE_SUMMARY_FIELDS),
            as_dict=True,
        ) or {}
        entry = _project(pe, _PE_SUMMARY_FIELDS)
        # Surface the *allocated* portion against this invoice, not the full PE
        # paid_amount (which may cover several invoices).
        entry["allocated_amount"] = float(r["allocated_amount"] or 0)
        out.append(entry)
    return out


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_my_invoices(limit: int = 20):
    if is_guest():
        return err("AUTH_REQUIRED", _("You must be logged in."))

    cust_id = _resolve_customer()
    if not cust_id:
        return ok({"invoices": []})

    try:
        limit_n = max(1, min(int(limit), 100))
    except (TypeError, ValueError):
        limit_n = 20

    try:
        rows = frappe.get_all(
            "Sales Invoice",
            filters={"customer": cust_id},
            fields=[*_SI_LIST_FIELDS, "docstatus"],
            order_by="posting_date desc, creation desc",
            limit_page_length=limit_n,
            ignore_permissions=True,
        )
    except Exception as e:
        frappe.log_error(title="get_my_invoices list", message=str(e))
        return err("SERVER_ERROR", _("Could not load your invoices."))

    enriched: list[dict] = []
    for r in rows:
        try:
            items_count = frappe.db.count(
                "Sales Invoice Item",
                {"parent": r["name"], "parenttype": "Sales Invoice"},
            )
        except Exception:
            items_count = 0
        try:
            paid_amount = max(0.0, float(r.get("grand_total") or 0) - float(r.get("outstanding_amount") or 0))
        except Exception:
            paid_amount = 0.0
        record = _project(r, _SI_LIST_FIELDS)
        record["items_count"] = items_count
        record["paid_amount"] = paid_amount
        record["payment_status"] = _payment_status_label(r)
        record.update(_si_back_links(r["name"]))
        enriched.append(record)
    return ok({"invoices": enriched})


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_my_invoice_detail(name: str | None = None):
    if is_guest():
        return err("AUTH_REQUIRED", _("You must be logged in."))

    if not name:
        return err("VALIDATION_ERROR", _("Invoice name is required."))

    cust_id = _resolve_customer()
    if not cust_id:
        return err("NOT_FOUND", _("Invoice not found."))

    if not frappe.db.exists("Sales Invoice", name):
        return err("NOT_FOUND", _("Invoice not found."))

    si_customer = frappe.db.get_value("Sales Invoice", name, "customer")
    if si_customer != cust_id:
        return err("NOT_FOUND", _("Invoice not found."))

    try:
        doc = frappe.get_doc("Sales Invoice", name)
    except Exception as e:
        frappe.log_error(title="get_my_invoice_detail load", message=str(e))
        return err("SERVER_ERROR", _("Could not load the invoice."))

    as_dict = doc.as_dict()
    payload = _project(as_dict, _SI_DETAIL_FIELDS)
    try:
        paid_amount = max(0.0, float(payload.get("grand_total") or 0) - float(payload.get("outstanding_amount") or 0))
    except Exception:
        paid_amount = 0.0
    payload["paid_amount"] = paid_amount
    payload["payment_status"] = _payment_status_label({
        "status": payload.get("status"),
        "docstatus": doc.docstatus,
        "grand_total": payload.get("grand_total"),
        "outstanding_amount": payload.get("outstanding_amount"),
    })
    payload["items"] = [
        _project(row, _SI_ITEM_DETAIL_FIELDS)
        for row in (as_dict.get("items") or [])
    ]
    payload.update(_si_back_links(name))
    payload["payments"] = _payment_summary_for_invoice(name)
    # Phase 8D-3: surface wallet settlements separately (these come from
    # Journal Entries created by `pay_invoice_with_wallet`, not Payment
    # Entries, so they would otherwise be invisible to the customer).
    payload["wallet_payments"] = _wallet_payments_for_invoice(name)
    return ok({"record": payload})
