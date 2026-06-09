from frappe.model.document import Document


class RobotProductImage(Document):
    """Child of Robot Product. One row per gallery image.

    Hero-row uniqueness is enforced by the parent Robot Product controller.
    """

    pass
