"""Phase 7 E2E fixtures.

Provides a deterministic seed that the Phase 7A puppeteer suite consumes,
so the suite no longer has to walk customer1's quote list looking for a
QR that happens to be Draft/Sent. The fixture pattern mirrors the helpers
in :mod:`iranrobot_backend.commands._phase7b_smoke`.

Run via::

    bench --site iranrobot.localhost execute \\
        iranrobot_backend.commands._phase7_e2e_fixtures.seed_phase7a_e2e_fixture

This is a **development-only** command. It refuses to run unless the active
Frappe site is ``iranrobot.localhost``.
"""

import json
import pathlib

import frappe


FIXTURE_REL_PATH = "tests/artifacts/phase7a_e2e_fixture.json"
ALLOWED_SITE = "iranrobot.localhost"


def _repo_root() -> pathlib.Path:
    # commands/ -> iranrobot_backend/ -> iranrobot_backend/ (outer app) ->
    # apps/ -> frappe-bench/ -> backend/ -> repo root
    return pathlib.Path(__file__).resolve().parents[6]


def _guard_site():
    site = getattr(frappe.local, "site", None) or ""
    if site != ALLOWED_SITE:
        raise RuntimeError(
            f"refusing to seed fixture on site={site!r}; "
            f"only {ALLOWED_SITE!r} is allowed"
        )


def _new_customer1_qr(message: str) -> str:
    """Submit a fresh quote as customer1, return the new request id.

    Mirrors :func:`_phase7b_smoke._new_customer1_qr`.
    """
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
    """Convert QR to Quotation (as Administrator), then promote
    Robot Quote Request.quotation_status to ``Sent`` so the customer-respond
    flow is unlocked. Mirrors :func:`_phase7b_smoke._convert_and_mark_sent`.
    """
    from iranrobot_backend.api.requests import convert_quote_request_to_quotation

    res = convert_quote_request_to_quotation(qr_name)
    if not res.get("ok"):
        raise RuntimeError(f"convert failed: {res}")
    qid = res["data"]["quotation_id"]
    frappe.db.set_value(
        "Robot Quote Request", qr_name, "quotation_status", "Sent",
        update_modified=False,
    )
    frappe.db.commit()
    return qid


def seed_phase7a_e2e_fixture():
    """Seed one isolated Robot Quote Request for the Phase 7A puppeteer
    suite. Writes ``tests/artifacts/phase7a_e2e_fixture.json`` and prints
    the fixture so it shows in the bench log.

    Always creates a fresh QR (cheap, deterministic). The Phase 7A E2E
    reads the resulting JSON and opens that exact QR -- no picker.
    """
    _guard_site()

    qr = _new_customer1_qr("phase7a e2e fixture")
    qid = _convert_and_mark_sent(qr)

    fixture = {
        "qr_name": qr,
        "quotation_id": qid,
        "quotation_status": "Sent",
        "customer_email": "customer1@example.com",
    }

    out_path = _repo_root() / FIXTURE_REL_PATH
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(fixture, indent=2) + "\n")

    print("PHASE7_FIXTURE::" + json.dumps({"path": str(out_path), **fixture}))
    return fixture
