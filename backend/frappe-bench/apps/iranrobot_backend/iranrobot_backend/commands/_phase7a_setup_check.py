"""Phase 7A setup-verification helper.

Invoked via `bench --site iranrobot.localhost execute
iranrobot_backend.commands._phase7a_setup_check.run`.

Verifies the prerequisites for converting a Robot Quote Request into an
ERPNext Quotation:
  - Company "IranRobot" exists
  - Currency "USD" exists
  - UOM "Nos" exists
  - At least one Selling Price List exists; reports which we'll use
  - Robot Quote Request DocType has the three Phase 7A fields
"""

import frappe


def run():
    out = []

    def line(label, value, ok):
        flag = "OK " if ok else "!! "
        out.append(f"{flag}{label:35s} {value}")

    line("Company 'IranRobot' exists", frappe.db.exists("Company", "IranRobot"), bool(frappe.db.exists("Company", "IranRobot")))
    line("Currency 'USD' exists", frappe.db.exists("Currency", "USD"), bool(frappe.db.exists("Currency", "USD")))
    line("UOM 'Nos' exists", frappe.db.exists("UOM", "Nos"), bool(frappe.db.exists("UOM", "Nos")))

    # Prefer the canonical 'Standard Selling'; otherwise pick any selling list.
    preferred = "Standard Selling"
    if frappe.db.exists("Price List", preferred):
        chosen = preferred
    else:
        rows = frappe.get_all("Price List", filters={"selling": 1, "enabled": 1}, fields=["name"], limit=1)
        chosen = rows[0].name if rows else None
    line("Selling Price List (chosen)", chosen, chosen is not None)

    meta = frappe.get_meta("Robot Quote Request")
    for fn in ("erpnext_quotation", "quotation_status", "proposal_amount_usd"):
        line(f"Robot Quote Request.{fn}", "present" if meta.has_field(fn) else "MISSING", meta.has_field(fn))

    print("\n".join(out))
