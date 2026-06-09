"""Phase 5 -- Robot Procurement Request controller.

A customer-submitted sourcing intake record. Staff convert accepted requests
into ERPNext Quotation + Purchase Order downstream (out of scope for Phase 5).
"""

import frappe
from frappe import _
from frappe.model.document import Document


VALID_STATUSES = {
    "New",
    "Reviewing",
    "Sourcing",
    "Supplier Found",
    "Proposal Sent",
    "Accepted",
    "Rejected",
    "Closed",
}


class RobotProcurementRequest(Document):
    def validate(self):
        if not (self.product_name or "").strip():
            frappe.throw(_("Product or need is required."), title=_("Validation"))

        if self.quantity is None or int(self.quantity) < 1:
            self.quantity = 1

        # Either a linked Customer OR (contact_name + email/phone) must be present.
        has_customer_link = bool(self.customer)
        has_guest_contact = bool(
            (self.contact_name or "").strip()
            and ((self.email or "").strip() or (self.phone or "").strip())
        )
        if not (has_customer_link or has_guest_contact):
            frappe.throw(
                _("Provide a contact name and at least one of email or phone."),
                title=_("Missing contact info"),
            )
