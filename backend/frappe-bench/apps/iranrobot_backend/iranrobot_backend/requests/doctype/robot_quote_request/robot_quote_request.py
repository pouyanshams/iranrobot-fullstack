"""Phase 5 -- Robot Quote Request controller.

A customer-submitted intake record. NOT an ERPNext Quotation -- staff convert
accepted/priced Quote Requests into ERPNext Quotation downstream (out of scope
for Phase 5).
"""

import frappe
from frappe import _
from frappe.model.document import Document


VALID_STATUSES = {
    "New",
    "Reviewing",
    "Pricing",
    "Proposal Sent",
    "Accepted",
    "Rejected",
    "Closed",
}


class RobotQuoteRequest(Document):
    def validate(self):
        self._validate_items()
        self._validate_contact_fields()
        self._compute_total_estimate()

    def _validate_items(self):
        if not self.items:
            frappe.throw(
                _("A Quote Request must contain at least one item."),
                title=_("No items"),
            )
        for row in self.items:
            if not row.quantity or row.quantity < 1:
                frappe.throw(
                    _("Quantity for {0} must be at least 1.").format(
                        row.product_name or row.robot_product or "item"
                    )
                )
            if row.mode not in ("buy", "rent", "procure"):
                frappe.throw(_("Invalid mode '{0}'.").format(row.mode))
            if row.mode == "rent" and (not row.requested_days or row.requested_days < 1):
                # Default to 1 day rather than throwing -- the frontend may not
                # send rent days for accessory-style requests.
                row.requested_days = 1

    def _validate_contact_fields(self):
        # Either a linked Customer OR (name+email/phone) must be present so the
        # sales team has someone to reach.
        has_customer_link = bool(self.customer)
        has_guest_contact = bool(
            (self.customer_name or "").strip()
            and ((self.email or "").strip() or (self.phone or "").strip())
        )
        if not (has_customer_link or has_guest_contact):
            frappe.throw(
                _("Provide a contact name and at least one of email or phone."),
                title=_("Missing contact info"),
            )

    def _compute_total_estimate(self):
        total = 0.0
        for row in self.items:
            unit = float(row.unit_price_usd or 0)
            qty = int(row.quantity or 0)
            if row.mode == "rent":
                days = int(row.requested_days or 1)
                line = unit * qty * days
            else:
                line = unit * qty
            row.line_total_usd = line
            total += line
        self.total_estimate_usd = total
