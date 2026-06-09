import frappe
from frappe import _
from frappe.model.document import Document

from iranrobot_backend.catalog.slug import (
    SLUG_PATTERN,  # re-exported for backwards-compat with any external import
    assert_valid_slug,
    normalize_slug,
)


MAX_CATEGORY_DEPTH = 2  # Top-level (depth 1) + one level of subcategories (depth 2). Locked in Phase 1.


class RobotCategory(Document):
    def autoname(self):
        """Normalize + validate slug BEFORE Frappe captures it as the doc name.

        Runs at `doc.run_method("autoname")` inside frappe.model.naming.set_new_name
        (naming.py:172). Setting self.name here makes the subsequent `field:slug`
        directive a no-op (naming.py:174 is guarded by `if not doc.name`), so the
        normalized value wins. Without this, validate()'s normalization gets
        reverted by _sync_autoname_field() at the end of _validate().
        """
        self.slug = normalize_slug(self.slug)
        assert_valid_slug(self.slug, "Slug")
        self.name = self.slug

    def validate(self):
        # Defensive: also normalize on save() paths (autoname() only fires on insert).
        # For an existing doc this is mostly cosmetic -- _sync_autoname_field keeps
        # self.slug pinned to self.name -- but if someone edits slug via the API on
        # an unsaved-changes path, we still surface a clean error.
        self.slug = normalize_slug(self.slug)
        assert_valid_slug(self.slug, "Slug")
        self._validate_parent_not_self()
        self._validate_max_depth()
        self._strip_text_fields()

    # ---- helpers ------------------------------------------------------------

    def _validate_parent_not_self(self):
        if self.parent_category and self.parent_category == self.name:
            frappe.throw(_("A category cannot be its own parent."), frappe.ValidationError)

    def _validate_max_depth(self):
        """Walk up parent_category links. If we exceed MAX_CATEGORY_DEPTH, reject."""
        if not self.parent_category:
            return
        # Already known: self is depth 2 (has a parent). Verify the parent is depth 1 (top-level).
        try:
            parent_parent = frappe.db.get_value("Robot Category", self.parent_category, "parent_category")
        except Exception:
            parent_parent = None
        if parent_parent:
            frappe.throw(
                _(
                    "Robot Category supports {0} levels only (top-level + one subcategory). "
                    "Selected parent already has its own parent."
                ).format(MAX_CATEGORY_DEPTH),
                frappe.ValidationError,
            )

    def _strip_text_fields(self):
        for field in ("label_fa", "label_en", "icon"):
            value = self.get(field)
            if isinstance(value, str):
                self.set(field, value.strip())
