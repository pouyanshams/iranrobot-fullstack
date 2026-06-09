"""Phase 3.5 -- One-shot ERPNext setup wizard bootstrap.

ERPNext refuses to be used until its setup wizard is run once (Company,
default currency, country, etc.). The wizard is normally a multi-step
form in Desk; this module completes it programmatically so the rest of the
Phase 3.5 sync command can create Items + Item Groups without manual UI work.

Idempotent: calling `run()` again on an already-bootstrapped site is a no-op.

Invocation:

    bench --site iranrobot.localhost execute \\
        iranrobot_backend.commands.erpnext_bootstrap.run
"""

import frappe


COMPANY_NAME = "IranRobot"
COMPANY_ABBR = "IR"
COUNTRY = "Iran"
CURRENCY = "USD"
TIMEZONE = "Asia/Tehran"
LANGUAGE = "en"
DOMAIN = "Retail"


def run():
    """Complete the ERPNext setup wizard for the IranRobot site."""
    print(f"=== ERPNext bootstrap for site: {frappe.local.site} ===")

    if _already_bootstrapped():
        print("  Already bootstrapped -- nothing to do.")
        return _summary()

    print("  Running setup_complete(...) ...")
    from erpnext.setup.setup_wizard.setup_wizard import setup_complete

    # ERPNext's setup_wizard expects `frappe._dict` (attribute-style access)
    # rather than a plain Python dict. install_fixtures reads e.g.
    # `args.fy_start_date` which would fail on a regular dict.
    setup_complete(frappe._dict({
        "country": COUNTRY,
        "company_name": COMPANY_NAME,
        "company_abbr": COMPANY_ABBR,
        "currency": CURRENCY,
        "language": LANGUAGE,
        "timezone": TIMEZONE,
        "domains": [DOMAIN],
        "company_tagline": "Industrial robots, sold direct.",
        # Use the existing Administrator; don't try to create another user here.
        "full_name": "IranRobot Admin",
        "email": "Administrator",
        "password": "",
        "fy_start_date": "2026-01-01",
        "fy_end_date": "2026-12-31",
        "setup_demo": 0,
    }))
    frappe.db.commit()

    print("  setup_complete() returned OK.")
    return _summary()


def _already_bootstrapped() -> bool:
    return bool(frappe.db.exists("Company", COMPANY_NAME))


def _summary():
    company = frappe.db.exists("Company", COMPANY_NAME)
    currency = frappe.db.get_default("currency")
    item_group_count = frappe.db.count("Item Group")
    print(f"  Company exists?       {bool(company)}")
    print(f"  Default currency:     {currency}")
    print(f"  Item Group count:     {item_group_count}")
    return {
        "company": COMPANY_NAME if company else None,
        "currency": currency,
        "item_group_count": item_group_count,
    }
