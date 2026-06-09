"""Phase 7C staff-side smoke helpers.

Run via `bench --site iranrobot.localhost execute
iranrobot_backend.commands._phase7c_smoke.run_all`.
"""

import json

import frappe


def emit(payload):
    print("PHASE7C::" + json.dumps(payload, default=str))


def _seed_accepted_qr_for_customer1(label: str) -> tuple[str, str]:
    """Create a QR, convert to Quotation, mark Sent, accept it (as customer1).
    Returns (qr_name, quotation_id)."""
    from iranrobot_backend.api.requests import (
        submit_quote_request,
        convert_quote_request_to_quotation,
        respond_to_quotation,
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
    qr_name = res["data"]["request_id"]
    convert_quote_request_to_quotation(qr_name)
    qid = frappe.db.get_value("Robot Quote Request", qr_name, "erpnext_quotation")

    # Real staff would now set prices and Submit the Quotation in Desk. We
    # emulate that here: assign a real rate to each line (make_sales_order
    # rejects zero-priced rows in some paths) and call submit() -- which fires
    # the doc_events sync that automatically promotes quotation_status to
    # "Sent" on the back-linked Robot Quote Request.
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
        respond_to_quotation(qr_name, "accept", note="Phase 7C seed accept")
    finally:
        frappe.set_user(original)
    return qr_name, qid


def test_convert_happy_path():
    from iranrobot_backend.api.requests import convert_accepted_quote_to_sales_order
    qr, qid = _seed_accepted_qr_for_customer1("phase7c happy")
    res = convert_accepted_quote_to_sales_order(qr)
    snap = frappe.db.get_value(
        "Robot Quote Request", qr,
        ["erpnext_sales_order", "sales_order_status",
         "sales_order_grand_total_usd", "sales_order_created_at"],
        as_dict=True,
    ) or {}
    so_id = (res.get("data") or {}).get("sales_order_id")
    so_doc = frappe.db.get_value(
        "Sales Order", so_id,
        ["docstatus", "status", "customer", "currency", "company"],
        as_dict=True,
    ) if so_id else {}
    # Count items to verify mapping
    so_items = frappe.db.count("Sales Order Item", {"parent": so_id, "parenttype": "Sales Order"}) if so_id else 0
    emit({
        "step": "convert_happy",
        "qr": qr,
        "qid": qid,
        "res": res,
        "snap": snap,
        "so_doc": so_doc,
        "so_items": so_items,
    })


def test_convert_already_converted():
    from iranrobot_backend.api.requests import convert_accepted_quote_to_sales_order
    # Reuse a QR that already has erpnext_sales_order set
    row = frappe.db.get_value(
        "Robot Quote Request",
        {"user_email": "customer1@example.com", "erpnext_sales_order": ["is", "set"]},
        "name",
    )
    if not row:
        emit({"step": "already_converted", "skipped": True})
        return
    res = convert_accepted_quote_to_sales_order(row)
    emit({"step": "already_converted", "qr": row, "res": res})


def test_convert_not_accepted():
    """Quote whose customer has NOT accepted -> QUOTATION_NOT_ACCEPTED."""
    from iranrobot_backend.api.requests import (
        submit_quote_request,
        convert_quote_request_to_quotation,
        convert_accepted_quote_to_sales_order,
    )
    original = frappe.session.user
    frappe.set_user("customer1@example.com")
    try:
        res_sq = submit_quote_request(
            items=json.dumps([{"robot_product": "aimoga-mornine", "quantity": 1, "mode": "buy"}]),
            message="phase7c not accepted",
            language="en",
        )
    finally:
        frappe.set_user(original)
    qr = res_sq["data"]["request_id"]
    convert_quote_request_to_quotation(qr)
    # Don't mark Sent or accept -- leave Draft
    res = convert_accepted_quote_to_sales_order(qr)
    emit({"step": "not_accepted", "qr": qr, "res": res})


def test_convert_as_customer_blocked():
    from iranrobot_backend.api.requests import convert_accepted_quote_to_sales_order
    # Pick any QR with state acceptable
    row = frappe.db.get_value(
        "Robot Quote Request",
        {"user_email": "customer1@example.com", "customer_response": "Accepted"},
        "name",
    )
    original = frappe.session.user
    frappe.set_user("customer1@example.com")
    try:
        res = convert_accepted_quote_to_sales_order(row)
    finally:
        frappe.set_user(original)
    emit({"step": "as_customer", "qr": row, "res": res})


def test_convert_not_found():
    from iranrobot_backend.api.requests import convert_accepted_quote_to_sales_order
    res = convert_accepted_quote_to_sales_order("QR-XX-NOPE-99999")
    emit({"step": "not_found", "res": res})


def test_so_sync_hook():
    """After conversion, fire the sync hook directly and verify QR fields update."""
    from iranrobot_backend.api.requests import sync_sales_order_back_to_quote_request
    row = frappe.db.get_value(
        "Robot Quote Request",
        {"user_email": "customer1@example.com", "erpnext_sales_order": ["is", "set"]},
        ["name", "erpnext_sales_order"],
        as_dict=True,
    )
    if not row:
        emit({"step": "sync_hook", "skipped": True})
        return
    so = frappe.get_doc("Sales Order", row.erpnext_sales_order)
    sync_sales_order_back_to_quote_request(so)
    snap = frappe.db.get_value(
        "Robot Quote Request", row.name,
        ["sales_order_status", "sales_order_grand_total_usd",
         "customer_response", "quotation_status"],
        as_dict=True,
    ) or {}
    emit({"step": "sync_hook", "qr": row.name, "snap": snap, "so_status": so.status})


def test_customer_get_my_orders():
    from iranrobot_backend.api.orders import get_my_orders
    original = frappe.session.user
    frappe.set_user("customer1@example.com")
    try:
        res = get_my_orders(limit=10)
    finally:
        frappe.set_user(original)
    data = res.get("data") or {}
    orders = data.get("orders") or []
    # Just first row's keys to confirm the allow-list shape
    first = orders[0] if orders else {}
    emit({
        "step": "get_my_orders",
        "count": len(orders),
        "first_keys": sorted(first.keys()),
    })


def test_customer_get_my_order_detail():
    from iranrobot_backend.api.orders import get_my_order_detail
    row = frappe.db.get_value(
        "Robot Quote Request",
        {"user_email": "customer1@example.com", "erpnext_sales_order": ["is", "set"]},
        "erpnext_sales_order",
    )
    if not row:
        emit({"step": "get_my_order_detail", "skipped": True})
        return
    original = frappe.session.user
    frappe.set_user("customer1@example.com")
    try:
        res = get_my_order_detail(name=row)
    finally:
        frappe.set_user(original)
    rec = (res.get("data") or {}).get("record") or {}
    items = rec.get("items") or []
    emit({
        "step": "get_my_order_detail",
        "so": row,
        "rec_keys": sorted(rec.keys()),
        "items_count": len(items),
        "item0_keys": sorted(items[0].keys()) if items else [],
        "linked_qr": rec.get("linked_quote_request"),
        "linked_q": rec.get("linked_quotation"),
    })


def test_cross_customer_order_detail():
    """As an OTHER website user, attempt to read customer1's SO -> NOT_FOUND."""
    from iranrobot_backend.api.orders import get_my_order_detail
    so = frappe.db.get_value(
        "Robot Quote Request",
        {"user_email": "customer1@example.com", "erpnext_sales_order": ["is", "set"]},
        "erpnext_sales_order",
    )
    if not so:
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
        res = get_my_order_detail(name=so)
    finally:
        frappe.set_user(original)
    emit({"step": "cross_customer", "so": so, "other": other_email, "res": res})


def run_all():
    for fn in (
        test_convert_happy_path,
        test_convert_already_converted,
        test_convert_not_accepted,
        test_convert_as_customer_blocked,
        test_convert_not_found,
        test_so_sync_hook,
        test_customer_get_my_orders,
        test_customer_get_my_order_detail,
        test_cross_customer_order_detail,
    ):
        try:
            fn()
        except Exception as e:
            emit({"step": fn.__name__, "exception": str(e)})
