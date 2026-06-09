"""Phase 7A.1 staff-side smoke helpers."""

import json

import frappe

from iranrobot_backend.api.requests import convert_quote_request_to_quotation


def emit(payload):
    print("PHASE7A1::" + json.dumps(payload, default=str))


def _create_test_address_for_customer(customer_name: str, suffix: str, address_type: str, primary: int, shipping: int) -> str:
    addr = frappe.get_doc({
        "doctype": "Address",
        "address_title": f"phase7a1-autofill-{suffix}",
        "address_type": address_type,
        "address_line1": f"Phase 7A.1 {suffix} street",
        "city": "Tehran",
        "country": "Iran",
        "pincode": "1234567890",
        "is_primary_address": primary,
        "is_shipping_address": shipping,
        "links": [{
            "link_doctype": "Customer",
            "link_name": customer_name,
        }],
    })
    addr.insert(ignore_permissions=True)
    return addr.name


def _cleanup_address(name: str):
    try:
        frappe.delete_doc("Address", name, ignore_permissions=True, force=True)
    except Exception:
        # If it's linked from a Quotation already, just disable it
        try:
            frappe.db.set_value("Address", name, "disabled", 1, update_modified=False)
        except Exception:
            pass


def _new_unlinked_qr_for_customer1() -> str:
    """Submit a fresh Robot Quote Request as customer1, return the name."""
    original = frappe.session.user
    frappe.set_user("customer1@example.com")
    try:
        from iranrobot_backend.api.requests import submit_quote_request
        res = submit_quote_request(
            items=json.dumps([{"robot_product": "aimoga-mornine", "quantity": 1, "mode": "buy"}]),
            message="Phase 7A.1 autofill test",
            language="en",
        )
    finally:
        frappe.set_user(original)
    frappe.db.commit()
    if not res.get("ok"):
        raise RuntimeError(f"could not create QR: {res}")
    return res["data"]["request_id"]


def test_autofill_with_billing_and_shipping():
    """Customer has both a Billing (primary) AND a Shipping address; conversion
    should put billing in customer_address and shipping in shipping_address_name.
    """
    cust = frappe.db.get_value("Robot Quote Request", {"user_email": "customer1@example.com"}, "customer")
    if not cust:
        emit({"step": "autofill_billing_shipping", "skipped": True, "reason": "no customer1 customer"})
        return

    billing = _create_test_address_for_customer(cust, "billing", "Billing", primary=1, shipping=0)
    shipping = _create_test_address_for_customer(cust, "shipping", "Shipping", primary=0, shipping=1)
    qr_name = _new_unlinked_qr_for_customer1()
    res = convert_quote_request_to_quotation(qr_name)
    qid = (res.get("data") or {}).get("quotation_id")
    snapshot = {}
    if qid:
        snapshot = frappe.db.get_value(
            "Quotation",
            qid,
            ["customer_address", "shipping_address_name", "contact_person"],
            as_dict=True,
        ) or {}
    emit({
        "step": "autofill_billing_shipping",
        "qr": qr_name,
        "billing": billing,
        "shipping": shipping,
        "quotation": qid,
        "snapshot": snapshot,
    })
    _cleanup_address(billing)
    _cleanup_address(shipping)


def test_autofill_with_only_billing():
    """Customer has only a Billing address; shipping should fall back to billing."""
    cust = frappe.db.get_value("Robot Quote Request", {"user_email": "customer1@example.com"}, "customer")
    if not cust:
        emit({"step": "autofill_only_billing", "skipped": True})
        return

    billing = _create_test_address_for_customer(cust, "billing-only", "Billing", primary=1, shipping=0)
    qr_name = _new_unlinked_qr_for_customer1()
    res = convert_quote_request_to_quotation(qr_name)
    qid = (res.get("data") or {}).get("quotation_id")
    snapshot = frappe.db.get_value(
        "Quotation",
        qid,
        ["customer_address", "shipping_address_name", "contact_person"],
        as_dict=True,
    ) or {}
    emit({
        "step": "autofill_only_billing",
        "qr": qr_name,
        "billing": billing,
        "quotation": qid,
        "snapshot": snapshot,
    })
    _cleanup_address(billing)


def test_autofill_without_address():
    """Customer has no addresses linked. Conversion should still succeed; the
    Quotation just has empty address/contact fields. (Contact may still be
    autofilled because we lazy-create one in Phase 4.)"""
    cust = frappe.db.get_value("Robot Quote Request", {"user_email": "customer1@example.com"}, "customer")
    if not cust:
        emit({"step": "autofill_no_address", "skipped": True})
        return

    # Ensure customer1 has no linked Address rows for this test
    addr_rows = frappe.db.sql(
        """
        SELECT a.name FROM `tabAddress` a
          JOIN `tabDynamic Link` dl
            ON dl.parent = a.name
           AND dl.parenttype = 'Address'
           AND dl.link_doctype = 'Customer'
           AND dl.link_name = %s
        """,
        (cust,),
    )
    for (n,) in addr_rows:
        _cleanup_address(n)

    qr_name = _new_unlinked_qr_for_customer1()
    res = convert_quote_request_to_quotation(qr_name)
    qid = (res.get("data") or {}).get("quotation_id")
    snapshot = frappe.db.get_value(
        "Quotation",
        qid,
        ["customer_address", "shipping_address_name", "contact_person"],
        as_dict=True,
    ) or {}
    emit({
        "step": "autofill_no_address",
        "qr": qr_name,
        "quotation": qid,
        "snapshot": snapshot,
    })


def run_all():
    for fn in (
        test_autofill_with_billing_and_shipping,
        test_autofill_with_only_billing,
        test_autofill_without_address,
    ):
        try:
            fn()
        except Exception as e:
            emit({"step": fn.__name__, "exception": str(e)})
