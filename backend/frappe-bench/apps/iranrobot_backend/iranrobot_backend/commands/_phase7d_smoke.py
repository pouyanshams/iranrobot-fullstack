"""Phase 7D staff-side smoke helpers.

Run via `bench --site iranrobot.localhost execute
iranrobot_backend.commands._phase7d_smoke.run_all`.
"""

import json

import frappe


def emit(payload):
    print("PHASE7D::" + json.dumps(payload, default=str))


def _seed_qr_with_submitted_sales_order(label: str) -> tuple[str, str]:
    """Submit a quote as customer1, convert to Quotation, set prices on each
    line, submit the Quotation, accept it (as customer1), convert to Sales
    Order (as Administrator), and submit the SO. Returns (qr_name, so_name).

    The Phase 7C smoke does most of this -- we replicate it here so the SO
    is in Submitted state (docstatus=1), which is the prerequisite for
    Phase 7D's `make_sales_invoice`.
    """
    from iranrobot_backend.api.requests import (
        submit_quote_request,
        convert_quote_request_to_quotation,
        respond_to_quotation,
        convert_accepted_quote_to_sales_order,
    )

    original = frappe.session.user
    frappe.set_user("customer1@example.com")
    try:
        res = submit_quote_request(
            items=json.dumps([{"robot_product": "aimoga-mornine", "quantity": 1, "mode": "buy"}]),
            message=label,
            language="en",
        )
    finally:
        frappe.set_user(original)
    qr = res["data"]["request_id"]

    convert_quote_request_to_quotation(qr)
    qid = frappe.db.get_value("Robot Quote Request", qr, "erpnext_quotation")

    # Price + submit the Quotation
    q = frappe.get_doc("Quotation", qid)
    for it in q.items:
        if not it.rate or it.rate <= 0:
            it.rate = 150.0
    q.flags.ignore_permissions = True
    q.save(ignore_permissions=True)
    q.submit()
    frappe.db.commit()

    frappe.set_user("customer1@example.com")
    try:
        respond_to_quotation(qr, "accept", note="phase7d seed accept")
    finally:
        frappe.set_user(original)

    convert_accepted_quote_to_sales_order(qr)
    so = frappe.db.get_value("Robot Quote Request", qr, "erpnext_sales_order")

    # Submit the Sales Order so make_sales_invoice will accept it
    so_doc = frappe.get_doc("Sales Order", so)
    so_doc.flags.ignore_permissions = True
    if so_doc.docstatus == 0:
        so_doc.submit()
    frappe.db.commit()
    return qr, so


def test_convert_happy_path():
    from iranrobot_backend.api.requests import convert_sales_order_to_sales_invoice
    qr, so = _seed_qr_with_submitted_sales_order("phase7d happy")
    res = convert_sales_order_to_sales_invoice(qr)
    snap = frappe.db.get_value(
        "Robot Quote Request", qr,
        [
            "erpnext_sales_invoice",
            "sales_invoice_status",
            "sales_invoice_grand_total_usd",
            "sales_invoice_outstanding_amount_usd",
            "sales_invoice_created_at",
            "payment_status",
        ],
        as_dict=True,
    ) or {}
    si_id = (res.get("data") or {}).get("sales_invoice_id")
    si_doc = frappe.db.get_value(
        "Sales Invoice", si_id,
        ["docstatus", "status", "customer", "currency", "company"],
        as_dict=True,
    ) if si_id else {}
    emit({
        "step": "convert_happy",
        "qr": qr,
        "so": so,
        "res": res,
        "snap": snap,
        "si_doc": si_doc,
    })


def test_convert_already_invoiced():
    from iranrobot_backend.api.requests import convert_sales_order_to_sales_invoice
    row = frappe.db.get_value(
        "Robot Quote Request",
        {"user_email": "customer1@example.com", "erpnext_sales_invoice": ["is", "set"]},
        "name",
    )
    if not row:
        emit({"step": "already_invoiced", "skipped": True})
        return
    res = convert_sales_order_to_sales_invoice(row)
    emit({"step": "already_invoiced", "qr": row, "res": res})


def test_convert_no_sales_order():
    from iranrobot_backend.api.requests import convert_sales_order_to_sales_invoice
    # A QR that has no Sales Order linked
    row = frappe.db.get_value(
        "Robot Quote Request",
        {"erpnext_sales_order": ["in", [None, ""]]},
        "name",
    )
    if not row:
        emit({"step": "no_sales_order", "skipped": True})
        return
    res = convert_sales_order_to_sales_invoice(row)
    emit({"step": "no_sales_order", "qr": row, "res": res})


def test_convert_so_not_submitted():
    """Submit + Convert flow that stops at a Draft Sales Order should return
    SALES_ORDER_NOT_SUBMITTED rather than letting ERPNext throw a raw error."""
    from iranrobot_backend.api.requests import (
        submit_quote_request,
        convert_quote_request_to_quotation,
        respond_to_quotation,
        convert_accepted_quote_to_sales_order,
        convert_sales_order_to_sales_invoice,
    )

    original = frappe.session.user
    frappe.set_user("customer1@example.com")
    try:
        res_sq = submit_quote_request(
            items=json.dumps([{"robot_product": "aimoga-mornine", "quantity": 1, "mode": "buy"}]),
            message="phase7d so not submitted",
            language="en",
        )
    finally:
        frappe.set_user(original)
    qr = res_sq["data"]["request_id"]
    convert_quote_request_to_quotation(qr)
    qid = frappe.db.get_value("Robot Quote Request", qr, "erpnext_quotation")
    q = frappe.get_doc("Quotation", qid)
    for it in q.items:
        if not it.rate or it.rate <= 0:
            it.rate = 100.0
    q.flags.ignore_permissions = True
    q.save(ignore_permissions=True)
    q.submit()
    frappe.db.commit()
    frappe.set_user("customer1@example.com")
    try:
        respond_to_quotation(qr, "accept")
    finally:
        frappe.set_user(original)
    convert_accepted_quote_to_sales_order(qr)
    # Leave the Sales Order as Draft -- don't submit
    res = convert_sales_order_to_sales_invoice(qr)
    emit({"step": "so_not_submitted", "qr": qr, "res": res})


def test_convert_as_customer_blocked():
    from iranrobot_backend.api.requests import convert_sales_order_to_sales_invoice
    row = frappe.db.get_value(
        "Robot Quote Request",
        {"user_email": "customer1@example.com", "erpnext_sales_order": ["is", "set"]},
        "name",
    )
    original = frappe.session.user
    frappe.set_user("customer1@example.com")
    try:
        res = convert_sales_order_to_sales_invoice(row)
    finally:
        frappe.set_user(original)
    emit({"step": "as_customer", "qr": row, "res": res})


def test_payment_entry_visibility():
    """Submit a Sales Invoice and record a partial Payment Entry; verify the
    QR's snapshot fields update + the customer-facing detail surfaces the PE."""
    from iranrobot_backend.api.invoices import (
        get_my_invoice_detail,
    )

    # Reuse the SI from the happy path
    row = frappe.db.get_value(
        "Robot Quote Request",
        {"user_email": "customer1@example.com", "erpnext_sales_invoice": ["is", "set"]},
        ["name", "erpnext_sales_invoice"],
        as_dict=True,
    )
    if not row:
        emit({"step": "payment_visibility", "skipped": True})
        return

    si = frappe.get_doc("Sales Invoice", row.erpnext_sales_invoice)
    if si.docstatus == 0:
        si.flags.ignore_permissions = True
        si.submit()
        frappe.db.commit()

    # Build a Payment Entry via ERPNext's get_payment_entry helper
    from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry
    pe = get_payment_entry("Sales Invoice", si.name)
    pe.reference_no = "PHASE7D-TEST-REF"
    pe.reference_date = frappe.utils.today()
    # Pay roughly 40% of the outstanding to exercise the "Partly Paid" branch
    target_pay = round(float(si.outstanding_amount or si.grand_total) * 0.4, 2)
    pe.paid_amount = target_pay
    pe.received_amount = target_pay
    if pe.references:
        pe.references[0].allocated_amount = target_pay
    pe.flags.ignore_permissions = True
    pe.insert(ignore_permissions=True)
    pe.submit()
    frappe.db.commit()

    snap = frappe.db.get_value(
        "Robot Quote Request", row.name,
        [
            "latest_payment_entry",
            "sales_invoice_outstanding_amount_usd",
            "payment_status",
        ],
        as_dict=True,
    ) or {}

    # Now read the invoice detail as customer1 -> payments summary present
    original = frappe.session.user
    frappe.set_user("customer1@example.com")
    try:
        detail = get_my_invoice_detail(name=si.name)
    finally:
        frappe.set_user(original)
    rec = (detail.get("data") or {}).get("record") or {}
    emit({
        "step": "payment_visibility",
        "qr": row.name,
        "si": si.name,
        "pe": pe.name,
        "qr_snap": snap,
        "detail_payment_status": rec.get("payment_status"),
        "detail_outstanding": rec.get("outstanding_amount"),
        "detail_paid_amount": rec.get("paid_amount"),
        "detail_payments_count": len(rec.get("payments") or []),
        "detail_payment0": (rec.get("payments") or [None])[0],
    })


def test_customer_get_my_invoices():
    from iranrobot_backend.api.invoices import get_my_invoices
    original = frappe.session.user
    frappe.set_user("customer1@example.com")
    try:
        res = get_my_invoices(limit=10)
    finally:
        frappe.set_user(original)
    invoices = (res.get("data") or {}).get("invoices") or []
    emit({
        "step": "get_my_invoices",
        "count": len(invoices),
        "first_keys": sorted(invoices[0].keys()) if invoices else [],
        "first_payment_status": invoices[0].get("payment_status") if invoices else None,
    })


def test_cross_customer_invoice_detail():
    from iranrobot_backend.api.invoices import get_my_invoice_detail
    si = frappe.db.get_value(
        "Robot Quote Request",
        {"user_email": "customer1@example.com", "erpnext_sales_invoice": ["is", "set"]},
        "erpnext_sales_invoice",
    )
    if not si:
        emit({"step": "cross_customer", "skipped": True})
        return
    other = frappe.get_all(
        "User",
        filters={"user_type": "Website User", "email": ["!=", "customer1@example.com"], "enabled": 1},
        fields=["email"],
        limit=5,
    )
    other_email = next((u.email for u in other if u.email and u.email != "Guest"), None)
    if not other_email:
        emit({"step": "cross_customer", "skipped": True, "reason": "no other website user"})
        return
    original = frappe.session.user
    frappe.set_user(other_email)
    try:
        res = get_my_invoice_detail(name=si)
    finally:
        frappe.set_user(original)
    emit({"step": "cross_customer", "si": si, "other": other_email, "res": res})


def run_all():
    for fn in (
        test_convert_happy_path,
        test_convert_already_invoiced,
        test_convert_no_sales_order,
        test_convert_so_not_submitted,
        test_convert_as_customer_blocked,
        test_payment_entry_visibility,
        test_customer_get_my_invoices,
        test_cross_customer_invoice_detail,
    ):
        try:
            fn()
        except Exception as e:
            emit({"step": fn.__name__, "exception": str(e)})
