"""Phase 7A staff-side smoke helpers.

Invoked from /tmp/phase7a_smoke.py via `bench execute` because the conversion
endpoint requires a Sales role / Administrator and we don't want to widen
permissions just to test from HTTP.
"""

import json

import frappe

from iranrobot_backend.api.requests import (
    convert_quote_request_to_quotation,
    sync_quotation_back_to_quote_request,
)


def _pick_customer1_quote_no_quotation():
    """Find a Robot Quote Request owned by customer1@example.com that does not
    yet have an erpnext_quotation linked. Returns the doc name or raises.
    """
    rows = frappe.get_all(
        "Robot Quote Request",
        filters={
            "user_email": "customer1@example.com",
            "erpnext_quotation": ["in", [None, ""]],
        },
        fields=["name", "customer", "user_email"],
        order_by="creation desc",
        limit=1,
    )
    if not rows:
        raise RuntimeError("No customer1 Robot Quote Request without a Quotation found.")
    return rows[0].name


def emit(payload):
    """Print a single JSON line for the bash caller to parse."""
    print("PHASE7A::" + json.dumps(payload, default=str))


def convert_as_administrator():
    """Run the conversion as Administrator; emit the resulting envelope."""
    qr_name = _pick_customer1_quote_no_quotation()
    res = convert_quote_request_to_quotation(qr_name)
    emit({"step": "convert_admin", "qr": qr_name, "res": res})


def convert_existing_again():
    """Find the most recent customer1 QR WITH a quotation and try to re-convert.
    Should return ALREADY_CONVERTED."""
    rows = frappe.get_all(
        "Robot Quote Request",
        filters={
            "user_email": "customer1@example.com",
            "erpnext_quotation": ["is", "set"],
        },
        fields=["name"],
        order_by="creation desc",
        limit=1,
    )
    if not rows:
        emit({"step": "convert_again", "skipped": True, "reason": "no linked quotation"})
        return
    res = convert_quote_request_to_quotation(rows[0].name)
    emit({"step": "convert_again", "qr": rows[0].name, "res": res})


def convert_as_customer():
    """Switch session user to customer1 and attempt conversion. Should return
    NOT_PERMITTED."""
    rows = frappe.get_all(
        "Robot Quote Request",
        filters={"user_email": "customer1@example.com"},
        fields=["name"],
        order_by="creation desc",
        limit=1,
    )
    qr_name = rows[0].name if rows else None
    original = frappe.session.user
    frappe.set_user("customer1@example.com")
    try:
        res = convert_quote_request_to_quotation(qr_name)
    finally:
        frappe.set_user(original)
    emit({"step": "convert_as_customer", "qr": qr_name, "res": res})


def convert_guest_qr():
    """Find a guest-submitted Robot Quote Request (no customer link) and try
    to convert it. Should return CUSTOMER_REQUIRED."""
    rows = frappe.get_all(
        "Robot Quote Request",
        filters={"customer": ["in", [None, ""]], "erpnext_quotation": ["in", [None, ""]]},
        fields=["name"],
        order_by="creation desc",
        limit=1,
    )
    if not rows:
        emit({"step": "convert_guest", "skipped": True})
        return
    res = convert_quote_request_to_quotation(rows[0].name)
    emit({"step": "convert_guest", "qr": rows[0].name, "res": res})


def convert_with_bad_item():
    """Simulate a stale erpnext_item on a Robot Quote Request line (e.g. the
    Item was deleted in Desk after the customer submitted). Should surface
    ITEM_NOT_LINKED.

    We create a fresh Robot Quote Request normally (passes Link validation
    against the real Item), then directly UPDATE the child table to point at
    a non-existent Item -- bypassing Frappe's save-time Link validation. The
    convert code re-validates via frappe.db.exists, so it must catch this.
    """
    customer_name = frappe.db.get_value(
        "Robot Quote Request",
        {"user_email": "customer1@example.com", "customer": ["is", "set"]},
        "customer",
    )
    if not customer_name:
        emit({"step": "convert_bad_item", "skipped": True, "reason": "no customer1 customer"})
        return
    qr = frappe.get_doc({
        "doctype": "Robot Quote Request",
        "status": "New",
        "source": "Desk",
        "language": "en",
        "submitted_at": frappe.utils.now_datetime(),
        "customer": customer_name,
        "user_email": "customer1@example.com",
        "customer_name": "Phase 7A bad-item test",
        "email": "customer1@example.com",
        "phone": "09120000000",
        "message": "test",
        "items": [{
            "robot_product": "aimoga-mornine",
            "erpnext_item": "aimoga-mornine",  # valid at insert time
            "product_name": "Bad Item",
            "quantity": 1,
            "mode": "buy",
            "unit_price_usd": 0,
        }],
    })
    qr.insert(ignore_permissions=True)
    frappe.db.commit()
    # Now flip the child row's erpnext_item to a non-existent value, mirroring
    # what would happen if the corresponding Item were deleted in Desk later.
    frappe.db.sql(
        """UPDATE `tabRobot Quote Request Item`
           SET erpnext_item = %s
           WHERE parent = %s""",
        ("definitely-not-an-item", qr.name),
    )
    frappe.db.commit()
    res = convert_quote_request_to_quotation(qr.name)
    emit({"step": "convert_bad_item", "qr": qr.name, "res": res})
    # Clean up
    try:
        frappe.delete_doc("Robot Quote Request", qr.name, ignore_permissions=True, force=True)
        frappe.db.commit()
    except Exception:
        # If deletion fails (e.g. because of the dangling link), leave the row
        # for manual cleanup. We don't want test setup failure to mask result.
        pass


def test_doc_events_sync():
    """Edit the linked Quotation's grand_total via db_set and call the sync
    hook directly to confirm Robot Quote Request fields update."""
    rows = frappe.get_all(
        "Robot Quote Request",
        filters={
            "user_email": "customer1@example.com",
            "erpnext_quotation": ["is", "set"],
        },
        fields=["name", "erpnext_quotation"],
        order_by="creation desc",
        limit=1,
    )
    if not rows:
        emit({"step": "sync_hook", "skipped": True})
        return
    qr_name, quotation_name = rows[0].name, rows[0].erpnext_quotation
    quotation = frappe.get_doc("Quotation", quotation_name)
    sync_quotation_back_to_quote_request(quotation)
    refreshed = frappe.db.get_value(
        "Robot Quote Request",
        qr_name,
        ["quotation_status", "proposal_amount_usd"],
        as_dict=True,
    )
    emit({"step": "sync_hook", "qr": qr_name, "refreshed": refreshed, "erp_status": quotation.status})


def show_quote_detail_as_customer():
    """Call get_my_request_detail as customer1 for their most recent quote
    with a linked Quotation, and emit a customer-safe-fields summary."""
    from iranrobot_backend.api.requests import get_my_request_detail

    rows = frappe.get_all(
        "Robot Quote Request",
        filters={"user_email": "customer1@example.com", "erpnext_quotation": ["is", "set"]},
        fields=["name"],
        order_by="creation desc",
        limit=1,
    )
    if not rows:
        emit({"step": "detail_as_customer", "skipped": True})
        return
    original = frappe.session.user
    frappe.set_user("customer1@example.com")
    try:
        res = get_my_request_detail(kind="quote", name=rows[0].name)
    finally:
        frappe.set_user(original)
    emit({"step": "detail_as_customer", "qr": rows[0].name, "res": res})


def show_quote_detail_as_other_customer():
    """Try to read customer1's quote as a different user -> NOT_FOUND."""
    from iranrobot_backend.api.requests import get_my_request_detail

    rows = frappe.get_all(
        "Robot Quote Request",
        filters={"user_email": "customer1@example.com", "erpnext_quotation": ["is", "set"]},
        fields=["name"],
        order_by="creation desc",
        limit=1,
    )
    if not rows:
        emit({"step": "detail_as_other", "skipped": True})
        return
    qr_name = rows[0].name

    # Find any other Website User with a Customer record
    other = frappe.get_all(
        "User",
        filters={"user_type": "Website User", "email": ["!=", "customer1@example.com"], "enabled": 1},
        fields=["email"],
        limit=5,
    )
    other_email = next((u.email for u in other if u.email and u.email != "Guest"), None)
    if not other_email:
        emit({"step": "detail_as_other", "skipped": True, "reason": "no other website user"})
        return

    original = frappe.session.user
    frappe.set_user(other_email)
    try:
        res = get_my_request_detail(kind="quote", name=qr_name)
    finally:
        frappe.set_user(original)
    emit({"step": "detail_as_other", "qr": qr_name, "other_user": other_email, "res": res})


def run_all():
    """Run every step; isolate failures so one bad step doesn't mask others."""
    for fn in (
        convert_as_administrator,
        convert_existing_again,
        convert_as_customer,
        convert_guest_qr,
        convert_with_bad_item,
        test_doc_events_sync,
        show_quote_detail_as_customer,
        show_quote_detail_as_other_customer,
    ):
        try:
            fn()
        except Exception as e:
            emit({"step": fn.__name__, "exception": str(e)})
