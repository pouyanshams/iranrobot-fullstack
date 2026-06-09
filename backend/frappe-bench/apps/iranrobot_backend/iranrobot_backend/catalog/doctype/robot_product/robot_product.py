import frappe
from frappe import _
from frappe.model.document import Document

from iranrobot_backend.catalog.slug import (
    SLUG_PATTERN,  # re-exported for backwards-compat with any external import
    assert_valid_slug,
    normalize_slug,
)


class RobotProduct(Document):
    def autoname(self):
        """Normalize + validate product_id (the autoname field) and slug BEFORE
        Frappe captures product_id as the doc name.

        Same root-cause fix as Robot Category: with `autoname: field:product_id`,
        validate()-time normalization gets reverted by _sync_autoname_field().
        Doing it here, in run_method("autoname") -> set self.name, locks the
        normalized value in.

        slug is also normalized here for consistency; it's not an autoname field
        so it wouldn't be reverted, but keeping the rules co-located avoids drift.
        """
        self.product_id = normalize_slug(self.product_id)
        assert_valid_slug(self.product_id, "Product ID")
        self.slug = normalize_slug(self.slug)
        assert_valid_slug(self.slug, "Slug")
        self.name = self.product_id

    def validate(self):
        # Defensive re-normalization for save() paths (autoname() only fires on insert).
        self.product_id = normalize_slug(self.product_id)
        assert_valid_slug(self.product_id, "Product ID")
        self.slug = normalize_slug(self.slug)
        assert_valid_slug(self.slug, "Slug")
        self._validate_category_is_top_level()
        self._validate_subcategory_under_category()
        self._validate_at_least_one_mode()
        self._validate_pricing_against_modes()
        self._validate_quote_labels_when_no_price()
        self._validate_single_hero_image()
        self._validate_rating_range()

    # ---- helpers ------------------------------------------------------------

    def _validate_category_is_top_level(self):
        if not self.category:
            return
        parent = frappe.db.get_value("Robot Category", self.category, "parent_category")
        if parent:
            frappe.throw(
                _(
                    "Category must be a top-level Robot Category (one with no parent). "
                    "'{0}' has parent '{1}' — pick its parent or a sibling top-level category."
                ).format(self.category, parent),
                frappe.ValidationError,
            )

    def _validate_subcategory_under_category(self):
        if not self.subcategory:
            return
        if not self.category:
            frappe.throw(
                _("Subcategory cannot be set without first selecting a Category."),
                frappe.ValidationError,
            )
        parent = frappe.db.get_value("Robot Category", self.subcategory, "parent_category")
        if parent != self.category:
            frappe.throw(
                _(
                    "Subcategory '{0}' is not a child of Category '{1}'. "
                    "Its parent_category is '{2}'."
                ).format(self.subcategory, self.category, parent or "—"),
                frappe.ValidationError,
            )

    def _validate_at_least_one_mode(self):
        if not (self.mode_buy or self.mode_rent or self.mode_procure):
            frappe.throw(
                _("A product must support at least one availability mode (Buy, Rent, or Procure)."),
                frappe.ValidationError,
            )

    def _validate_pricing_against_modes(self):
        if self.mode_buy and not (self.price_usd and self.price_usd > 0):
            frappe.throw(
                _("Sellable (Buy) requires Price (USD) to be set and greater than zero."),
                frappe.ValidationError,
            )
        if self.mode_rent and not (self.rent_per_day_usd and self.rent_per_day_usd > 0):
            frappe.throw(
                _("Rentable (Rent) requires Rent per Day (USD) to be set and greater than zero."),
                frappe.ValidationError,
            )

    def _validate_quote_labels_when_no_price(self):
        """When there is no numeric price, both bilingual price labels must be present."""
        if not self.price_usd:
            if not (self.price_label_fa and self.price_label_en):
                frappe.throw(
                    _(
                        "When Price (USD) is empty, both Price Label (fa) and Price Label (en) "
                        "are required so the public PLP/PDP can render a quote affordance."
                    ),
                    frappe.ValidationError,
                )

    def _validate_single_hero_image(self):
        heroes = [row for row in (self.images or []) if row.is_hero]
        if len(heroes) > 1:
            frappe.throw(
                _("Only one row in Images may have Is Hero checked (found {0}).").format(len(heroes)),
                frappe.ValidationError,
            )

    def _validate_rating_range(self):
        if self.rating is None:
            return
        try:
            value = float(self.rating)
        except (TypeError, ValueError):
            return  # frappe will reject non-floats upstream
        if value < 0 or value > 5:
            frappe.throw(_("Rating must be between 0 and 5."), frappe.ValidationError)
