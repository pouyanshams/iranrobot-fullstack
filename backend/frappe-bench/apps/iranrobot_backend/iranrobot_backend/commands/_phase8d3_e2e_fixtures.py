"""Phase 8D-3 E2E fixture seeder.

Creates a deterministic, isolated customer + wallet + submitted SI + linked
QR for the puppeteer suite to drive. Writes a JSON manifest to
`tests/artifacts/phase8d3_e2e_fixture.json` so the suite can read the email
/ password / SI name at startup.

Run via::

    bench --site iranrobot.localhost execute \\
        iranrobot_backend.commands._phase8d3_e2e_fixtures.seed_phase8d3_e2e_fixture
"""

from __future__ import annotations

import json
import os
import secrets

import frappe


_ARTIFACTS_DIR = os.path.join(
    "/Users/pouyanshams/Desktop/iran-robota", "tests", "artifacts"
)
_FIXTURE_PATH = os.path.join(_ARTIFACTS_DIR, "phase8d3_e2e_fixture.json")

COMPANY = "IranRobot"
INCOME_ACCOUNT = "Sales - IR"


def _find_test_item():
    code = frappe.db.get_value(
        "Robot Product", filters={"erpnext_item": ["!=", ""]},
        fieldname="erpnext_item",
    )
    if code and frappe.db.exists("Item", code):
        return code
    return frappe.db.get_value("Item", filters={"disabled": 0}, fieldname="name")


def seed_phase8d3_e2e_fixture():
    from iranrobot_backend.api.auth import signup
    from iranrobot_backend.api._session import (
        get_or_create_customer_for_user,
        get_or_create_wallet_for_customer,
    )
    from iranrobot_backend.api.wallet import (
        create_top_up_request, staff_approve_top_up_request,
    )

    suffix = secrets.token_hex(4)
    email = f"phase8d3_{suffix}@example.com"
    pwd = "ChangeMe-123-Strong"

    # 1) signup (try real flow first, fall back to direct ORM when throttled)
    original = frappe.session.user
    frappe.set_user("Guest")
    try:
        sres = signup(
            email=email, password=pwd, confirm_password=pwd,
            first_name="Phase8D3", last_name="E2E",
            preferred_language="en",
        )
    finally:
        frappe.set_user(original)
    if not sres.get("ok"):
        # Throttled or other failure: create the user directly. This still
        # produces a valid Website User who can log in with `pwd`.
        prior_flag = getattr(frappe.flags, "in_import", False)
        frappe.flags.in_import = True
        try:
            user = frappe.get_doc({
                "doctype": "User", "email": email,
                "first_name": "Phase8D3", "last_name": "E2E",
                "send_welcome_email": 0, "enabled": 1,
                "user_type": "Website User",
                "new_password": pwd,
                "roles": [{"role": "Customer"}],
            })
            user.insert(ignore_permissions=True)
        finally:
            frappe.flags.in_import = prior_flag
        frappe.db.commit()

    # 2) resolve customer + wallet
    _contact, cust = get_or_create_customer_for_user(email)
    wallet = get_or_create_wallet_for_customer(cust)
    frappe.db.commit()

    # 3) credit wallet via top-up + approve
    frappe.set_user(email)
    try:
        tres = create_top_up_request(amount_usd=300, method="Bank Transfer")
    finally:
        frappe.set_user(original)
    if not tres.get("ok"):
        raise RuntimeError(f"top-up failed: {tres}")
    appr = staff_approve_top_up_request(name=tres["data"]["request_id"], bank_reference="REF-8D3-E2E")
    if not appr.get("ok"):
        raise RuntimeError(f"approve failed: {appr}")
    frappe.db.commit()

    # 4) submitted SI for $120
    si = frappe.get_doc({
        "doctype": "Sales Invoice",
        "customer": cust, "company": COMPANY, "currency": "USD",
        "posting_date": frappe.utils.today(),
        "due_date": frappe.utils.today(), "set_posting_time": 1,
        "items": [{
            "item_code": _find_test_item(), "qty": 1, "rate": 120, "uom": "Nos",
            "income_account": INCOME_ACCOUNT,
        }],
    })
    si.insert(ignore_permissions=True)
    si.submit()
    frappe.db.commit()

    # 5) Robot Quote Request linked to the SI (for the Phase 7D QR sync check)
    qr_name = None
    rp = frappe.db.get_value("Robot Product", filters={}, fieldname="name")
    if rp:
        qr = frappe.get_doc({
            "doctype": "Robot Quote Request",
            "customer": cust, "user_email": email,
            "customer_name": "Phase8D3 E2E",
            "email": email, "phone": "", "language": "en",
            "submitted_at": frappe.utils.now_datetime(),
            "status": "New",
            "message": "Phase 8D-3 E2E fixture",
            "items": [{
                "robot_product": rp, "product_name": "Phase 8D-3 Item",
                "mode": "buy", "quantity": 1, "unit_price_usd": 120,
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
        qr_name = qr.name

    fixture = {
        "email": email,
        "password": pwd,
        "customer": cust,
        "wallet": wallet,
        "sales_invoice": si.name,
        "qr": qr_name,
        "expected_balance_before": 300.0,
        "expected_outstanding_before": 120.0,
    }

    os.makedirs(_ARTIFACTS_DIR, exist_ok=True)
    with open(_FIXTURE_PATH, "w", encoding="utf-8") as f:
        json.dump(fixture, f, indent=2)

    print("PHASE8D3_FIXTURE::" + json.dumps(fixture, default=str))
    return fixture
