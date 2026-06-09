"""Phase 8C E2E fixture seeder.

Runs once before the puppeteer suite to produce a deterministic, isolated
customer (with their own freshly created Robot Wallet Account) and to seed an
already-approved Top Up so the transaction history list has at least one row.

Run via::

    bench --site iranrobot.localhost execute \\
        iranrobot_backend.commands._phase8c_e2e_fixtures.seed_phase8c_e2e_fixture

The result is written to tests/artifacts/phase8c_e2e_fixture.json (gitignored).
The puppeteer suite reads this file at startup to know which email/password to
log in as.
"""

from __future__ import annotations

import json
import os
import secrets

import frappe


# Same artifacts root the rest of the repo uses.
_ARTIFACTS_DIR = os.path.join(
    "/Users/pouyanshams/Desktop/iran-robota", "tests", "artifacts"
)
_FIXTURE_PATH = os.path.join(_ARTIFACTS_DIR, "phase8c_e2e_fixture.json")


def seed_phase8c_e2e_fixture():
    """Sign up a fresh customer + seed one Approved Top Up transaction.

    Returns the fixture dict and also writes it to disk for the e2e runner.
    """
    from iranrobot_backend.api.auth import signup
    from iranrobot_backend.api._session import (
        get_or_create_customer_for_user,
        get_or_create_wallet_for_customer,
    )
    from iranrobot_backend.api.wallet import (
        create_top_up_request,
        staff_approve_top_up_request,
    )

    suffix = secrets.token_hex(4)
    email = f"phase8c_{suffix}@example.com"
    pwd = "ChangeMe-123-Strong"

    # 1) signup (runs as Guest like the React flow)
    original_user = frappe.session.user
    frappe.set_user("Guest")
    try:
        res = signup(
            email=email, password=pwd, confirm_password=pwd,
            first_name="Phase8C", last_name="E2E",
            preferred_language="en",
        )
    finally:
        frappe.set_user(original_user)
    if not res.get("ok"):
        raise RuntimeError(f"signup failed: {res}")

    # 2) resolve customer + lazy create wallet
    _contact, cust = get_or_create_customer_for_user(email)
    wallet = get_or_create_wallet_for_customer(cust)
    frappe.db.commit()

    # 3) seed one Approved Top Up so the transaction history isn't empty
    _previous = frappe.session.user
    frappe.set_user(email)
    try:
        topup_res = create_top_up_request(
            amount_usd=120,
            method="Bank Transfer",
            customer_note="phase8c e2e seed",
        )
    finally:
        frappe.set_user(_previous)
    if not topup_res.get("ok"):
        raise RuntimeError(f"create_top_up_request failed: {topup_res}")
    seeded_topup = topup_res["data"]["request_id"]

    approve_res = staff_approve_top_up_request(name=seeded_topup, bank_reference="E2E-FIX-001")
    if not approve_res.get("ok"):
        raise RuntimeError(f"approve failed: {approve_res}")
    frappe.db.commit()

    seeded_tx = approve_res["data"]["transaction_id"]
    balance = approve_res["data"].get("new_balance_usd")

    fixture = {
        "email": email,
        "password": pwd,
        "customer": cust,
        "wallet": wallet,
        "seeded_approved_topup_request": seeded_topup,
        "seeded_transaction": seeded_tx,
        "seeded_balance_usd": balance,
    }

    os.makedirs(_ARTIFACTS_DIR, exist_ok=True)
    with open(_FIXTURE_PATH, "w", encoding="utf-8") as f:
        json.dump(fixture, f, indent=2)

    print("PHASE8C_FIXTURE::" + json.dumps(fixture, default=str))
    return fixture
