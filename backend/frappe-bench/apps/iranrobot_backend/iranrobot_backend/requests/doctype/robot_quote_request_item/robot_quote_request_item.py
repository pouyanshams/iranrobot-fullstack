from frappe.model.document import Document


class RobotQuoteRequestItem(Document):
    """Child rows of Robot Quote Request. Validation is enforced by the parent
    on save; this file exists so Frappe can import a controller class."""

    pass
