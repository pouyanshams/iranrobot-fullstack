"""Phase 7B staff-side smoke helpers.

Run via `bench --site iranrobot.localhost execute
iranrobot_backend.commands._phase7b_smoke.run_all`.
"""

import json

import frappe


def emit(payload):
    print("PHASE7B::" + json.dumps(payload, default=str))


def _new_customer1_qr(message: str) -> str:
    """Submit a quote as customer1, return the new request id."""
    from iranrobot_backend.api.requests import submit_quote_request
    original = frappe.session.user
    frappe.set_user("customer1@example.com")
    try:
        res = submit_quote_request(
            items=json.dumps([{"robot_product": "aimoga-mornine", "quantity": 1, "mode": "buy"}]),
            message=message,
            language="en",
        )
    finally:
        frappe.set_user(original)
    frappe.db.commit()
    if not res.get("ok"):
        raise RuntimeError(f"could not create QR: {res}")
    return res["data"]["request_id"]


def _convert_and_mark_sent(qr_name: str) -> str:
    """Convert QR to Quotation (as Administrator) then bump its status from
    Draft to Sent so the customer-respond flow is unlocked."""
    from iranrobot_backend.api.requests import convert_quote_request_to_quotation
    res = convert_quote_request_to_quotation(qr_name)
    if not res.get("ok"):
        raise RuntimeError(f"convert failed: {res}")
    qid = res["data"]["quotation_id"]
    # Promote Robot Quote Request.quotation_status to "Sent" without
    # touching the underlying ERPNext Quotation docstatus -- mirrors the
    # state the doc_events sync produces after staff submits in Desk.
    frappe.db.set_value("Robot Quote Request", qr_name, "quotation_status", "Sent", update_modified=False)
    frappe.db.commit()
    return qid


def test_respond_to_quotation_happy_paths():
    from iranrobot_backend.api.requests import respond_to_quotation

    # Happy path: ACCEPT
    qr_accept = _new_customer1_qr("phase7b accept")
    _convert_and_mark_sent(qr_accept)
    original = frappe.session.user
    frappe.set_user("customer1@example.com")
    try:
        res = respond_to_quotation(qr_accept, "accept", note="Looks great, please proceed.")
    finally:
        frappe.set_user(original)
    snap = frappe.db.get_value(
        "Robot Quote Request", qr_accept,
        ["customer_response", "quotation_status", "customer_response_at",
         "customer_response_user", "customer_response_note"],
        as_dict=True,
    ) or {}
    emit({"step": "accept_happy", "qr": qr_accept, "res": res, "snap": snap})

    # Happy path: REJECT
    qr_reject = _new_customer1_qr("phase7b reject")
    _convert_and_mark_sent(qr_reject)
    frappe.set_user("customer1@example.com")
    try:
        res = respond_to_quotation(qr_reject, "reject", note="Too expensive.")
    finally:
        frappe.set_user(original)
    snap = frappe.db.get_value(
        "Robot Quote Request", qr_reject,
        ["customer_response", "quotation_status", "customer_response_note"],
        as_dict=True,
    ) or {}
    emit({"step": "reject_happy", "qr": qr_reject, "res": res, "snap": snap})


def test_state_guards():
    from iranrobot_backend.api.requests import respond_to_quotation

    # ALREADY_RESPONDED: re-accept the same QR
    qr_dup = _new_customer1_qr("phase7b dup")
    _convert_and_mark_sent(qr_dup)
    original = frappe.session.user
    frappe.set_user("customer1@example.com")
    try:
        respond_to_quotation(qr_dup, "accept")
        res = respond_to_quotation(qr_dup, "reject")
    finally:
        frappe.set_user(original)
    emit({"step": "already_responded", "qr": qr_dup, "res": res})

    # QUOTATION_NOT_READY: convert but DON'T promote status (stays Draft)
    qr_draft = _new_customer1_qr("phase7b draft")
    from iranrobot_backend.api.requests import convert_quote_request_to_quotation
    convert_quote_request_to_quotation(qr_draft)
    frappe.set_user("customer1@example.com")
    try:
        res = respond_to_quotation(qr_draft, "accept")
    finally:
        frappe.set_user(original)
    emit({"step": "draft_not_ready", "qr": qr_draft, "res": res})

    # QUOTATION_NOT_FOUND: brand new QR without a linked Quotation
    qr_no_quote = _new_customer1_qr("phase7b no quote")
    frappe.set_user("customer1@example.com")
    try:
        res = respond_to_quotation(qr_no_quote, "accept")
    finally:
        frappe.set_user(original)
    emit({"step": "no_quotation", "qr": qr_no_quote, "res": res})

    # INVALID_ACTION
    qr_bad = _new_customer1_qr("phase7b bad action")
    _convert_and_mark_sent(qr_bad)
    frappe.set_user("customer1@example.com")
    try:
        res = respond_to_quotation(qr_bad, "approve")  # not 'accept' / 'reject'
    finally:
        frappe.set_user(original)
    emit({"step": "invalid_action", "qr": qr_bad, "res": res})


def test_cross_customer_returns_not_found():
    """Customer1 owns a QR. We attempt to act on it as a different Website User."""
    from iranrobot_backend.api.requests import respond_to_quotation

    qr = _new_customer1_qr("phase7b cross")
    _convert_and_mark_sent(qr)

    # Find any other Website User
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
        res = respond_to_quotation(qr, "accept")
    finally:
        frappe.set_user(original)
    emit({"step": "cross_customer", "qr": qr, "other_user": other_email, "res": res})


def test_sync_hook_guard_after_accept():
    """After customer accepts, a staff-side Quotation save should NOT undo
    the Accepted status on the Robot Quote Request."""
    from iranrobot_backend.api.requests import (
        respond_to_quotation,
        sync_quotation_back_to_quote_request,
    )

    qr = _new_customer1_qr("phase7b sync guard")
    qid = _convert_and_mark_sent(qr)

    original = frappe.session.user
    frappe.set_user("customer1@example.com")
    try:
        respond_to_quotation(qr, "accept")
    finally:
        frappe.set_user(original)

    # Now simulate staff editing the Quotation in Desk -> the sync hook fires.
    quotation = frappe.get_doc("Quotation", qid)
    sync_quotation_back_to_quote_request(quotation)

    snap = frappe.db.get_value(
        "Robot Quote Request", qr,
        ["customer_response", "quotation_status"],
        as_dict=True,
    ) or {}
    emit({"step": "sync_guard", "qr": qr, "snap": snap})


def test_get_my_request_detail_can_respond():
    """Validate the new `can_respond` flag returned by get_my_request_detail."""
    from iranrobot_backend.api.requests import get_my_request_detail

    # 1) Draft -> can_respond False
    qr_draft = _new_customer1_qr("phase7b detail draft")
    from iranrobot_backend.api.requests import convert_quote_request_to_quotation
    convert_quote_request_to_quotation(qr_draft)

    original = frappe.session.user
    frappe.set_user("customer1@example.com")
    try:
        res_draft = get_my_request_detail(kind="quote", name=qr_draft)
    finally:
        frappe.set_user(original)

    # 2) Sent -> can_respond True
    qr_sent = _new_customer1_qr("phase7b detail sent")
    _convert_and_mark_sent(qr_sent)
    frappe.set_user("customer1@example.com")
    try:
        res_sent = get_my_request_detail(kind="quote", name=qr_sent)
    finally:
        frappe.set_user(original)

    # 3) Accepted -> can_respond False
    qr_acc = _new_customer1_qr("phase7b detail accepted")
    _convert_and_mark_sent(qr_acc)
    frappe.set_user("customer1@example.com")
    try:
        from iranrobot_backend.api.requests import respond_to_quotation
        respond_to_quotation(qr_acc, "accept")
        res_acc = get_my_request_detail(kind="quote", name=qr_acc)
    finally:
        frappe.set_user(original)

    emit({"step": "detail_can_respond",
          "draft": (res_draft.get("data") or {}).get("record", {}).get("can_respond"),
          "sent":  (res_sent.get("data") or {}).get("record", {}).get("can_respond"),
          "accepted": (res_acc.get("data") or {}).get("record", {}).get("can_respond")})


def run_all():
    for fn in (
        test_respond_to_quotation_happy_paths,
        test_state_guards,
        test_cross_customer_returns_not_found,
        test_sync_hook_guard_after_accept,
        test_get_my_request_detail_can_respond,
    ):
        try:
            fn()
        except Exception as e:
            emit({"step": fn.__name__, "exception": str(e)})
