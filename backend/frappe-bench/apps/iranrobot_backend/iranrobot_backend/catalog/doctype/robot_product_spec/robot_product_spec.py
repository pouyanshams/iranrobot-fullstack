from frappe.model.document import Document


class RobotProductSpec(Document):
    """Child of Robot Product. One row per bilingual spec line.

    No row-level validation in Phase 1 — parent Robot Product validates that the
    spec list is well-formed. Both fa and en sides are required at the field level.
    """

    pass
