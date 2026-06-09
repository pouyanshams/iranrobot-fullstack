"""Slug normalization + validation shared by Catalog DocTypes.

This must run in `autoname()` for any DocType whose `meta.autoname` is `field:<slug-like-field>`.
If normalization runs only in `validate()`, Frappe's `_sync_autoname_field()` (called from
`_validate()` after `validate()`) will overwrite the field back to whatever `self.name` was
captured at insert time -- silently reverting case fixes.

See findings in the Phase 1 cleanup report.
"""

import re

import frappe
from frappe import _


SLUG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*$")

_WHITESPACE_OR_UNDERSCORE = re.compile(r"[\s_]+")
_HYPHEN_RUN = re.compile(r"-{2,}")


def normalize_slug(value):
    """Lowercase + collapse whitespace/underscores to single hyphens + trim hyphens.

    Does NOT strip other invalid characters -- the format check is supposed to reject
    those, not silently mangle them.

    Examples:
        'Humanoids'           -> 'humanoids'
        'Bipedal Humanoids'   -> 'bipedal-humanoids'
        '  Quad  Robots  '    -> 'quad-robots'
        'Robot__Arm'          -> 'robot-arm'
        '-foo--bar-'          -> 'foo-bar'
        'humanoids!'          -> 'humanoids!'   (passes through; format check rejects)
        'انسان نماها'          -> 'انسان-نماها'   (format check rejects: non-ASCII)
        None / ''             -> unchanged (caller's format check throws "required")
    """
    if not value or not isinstance(value, str):
        return value
    s = value.strip().lower()
    s = _WHITESPACE_OR_UNDERSCORE.sub("-", s)
    s = _HYPHEN_RUN.sub("-", s)
    s = s.strip("-")
    return s


def assert_valid_slug(value, field_label):
    """Reject if value doesn't match SLUG_PATTERN. Pair with normalize_slug() upstream."""
    if not value or not SLUG_PATTERN.match(value):
        frappe.throw(
            _(
                "{0} must be lowercase letters, digits, and hyphens "
                "(e.g. 'humanoids', 'bipedal-humanoids'). Got: {1!r}"
            ).format(_(field_label), value or ""),
            frappe.ValidationError,
        )
