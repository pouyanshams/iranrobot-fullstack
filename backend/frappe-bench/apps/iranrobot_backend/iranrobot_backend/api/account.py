"""Phase 7A.1 -- Customer Address APIs.

Three whitelisted methods power the React Profile → Addresses surface and the
Phase 7A Quotation autofill. All methods return the project's `{ok, data,
error}` envelope and are auth-required (customers manage their own addresses;
they never see other customers' addresses).

    iranrobot_backend.api.account.get_my_addresses    GET   auth required
    iranrobot_backend.api.account.save_my_address     POST  auth required
    iranrobot_backend.api.account.delete_my_address   POST  auth required

Identity / ownership model:
    A customer is identified by their Frappe session user. We resolve their
    linked ERPNext Customer via the Phase 4 lazy-creation helper
    (`api/_session.get_or_create_customer_for_user`). Addresses are linked to
    that Customer via ERPNext's `Dynamic Link` child table on Address.

Security:
    - Never trust a `customer` parameter from the frontend.
    - Cross-customer access returns NOT_FOUND, not 403 (no existence leak).
    - Field allow-list on every read response.
    - System Manager / Administrator users have no Customer record and get a
      clean message rather than an exception.
"""

import re

import frappe
from frappe import _

from iranrobot_backend.api._response import err, ok
from iranrobot_backend.api._session import (
    get_or_create_customer_for_user,
    is_guest,
    is_system_manager,
)


# Persian-digit normalization mirrors auth.update_profile + requests.py.
_PERSIAN_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
_PHONE_RE = re.compile(r"^[0-9+\-\s]{6,}$")
_MAX_DATA_LEN = 240

# ERPNext Address.address_type Select options, restricted to the subset that
# makes sense for a customer-facing form.
_ALLOWED_TYPES = {"Billing", "Shipping", "Office", "Personal", "Other"}

# Customer-safe field allow-list. Anything outside this set is never returned.
_ADDRESS_PUBLIC_FIELDS = (
    "name",
    "address_title",
    "address_type",
    "address_line1",
    "address_line2",
    "city",
    "state",
    "country",
    "pincode",
    "phone",
    "email_id",
    "is_primary_address",
    "is_shipping_address",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _norm(value, max_len: int = _MAX_DATA_LEN) -> str:
    s = (value if isinstance(value, str) else ("" if value is None else str(value))).strip()
    return s[:max_len]


def _norm_phone(value) -> str:
    return _norm(value).translate(_PERSIAN_DIGITS)


def _coerce_bool(value) -> int:
    if isinstance(value, bool):
        return 1 if value else 0
    if value in (None, ""):
        return 0
    s = str(value).strip().lower()
    return 1 if s in ("1", "true", "yes", "on") else 0


def get_customer_for_session_user() -> str | None:
    """Return the ERPNext Customer name for `frappe.session.user`, or None.

    Staff users (Administrator / System Manager) deliberately have no Customer
    record (see Phase 4 _session helper). For them we return None and the
    caller surfaces a clean error.
    """
    if is_guest():
        return None
    user_email = frappe.session.user
    if user_email == "Administrator" or is_system_manager(user_email):
        return None
    try:
        _contact, customer_name = get_or_create_customer_for_user(user_email)
        return customer_name
    except Exception as e:
        frappe.log_error(title="account.get_customer_for_session_user", message=str(e))
        return None


def address_belongs_to_customer(address_name: str, customer_name: str) -> bool:
    """Server-side ownership check via ERPNext Dynamic Link."""
    if not address_name or not customer_name:
        return False
    if not frappe.db.exists("Address", address_name):
        return False
    rows = frappe.db.sql(
        """
        SELECT 1
          FROM `tabDynamic Link`
         WHERE parent = %s
           AND parenttype = 'Address'
           AND link_doctype = 'Customer'
           AND link_name = %s
         LIMIT 1
        """,
        (address_name, customer_name),
    )
    return bool(rows)


def _list_addresses_for_customer(customer_name: str) -> list[dict]:
    """Return the customer-safe projection of every Address linked to this Customer."""
    rows = frappe.db.sql(
        """
        SELECT a.name
          FROM `tabAddress` a
          JOIN `tabDynamic Link` dl
            ON dl.parent = a.name
           AND dl.parenttype = 'Address'
           AND dl.link_doctype = 'Customer'
           AND dl.link_name = %s
         WHERE COALESCE(a.disabled, 0) = 0
         ORDER BY a.is_primary_address DESC,
                  a.is_shipping_address DESC,
                  a.modified DESC
        """,
        (customer_name,),
        as_dict=True,
    )
    out = []
    for r in rows:
        full = frappe.db.get_value(
            "Address",
            r["name"],
            list(_ADDRESS_PUBLIC_FIELDS),
            as_dict=True,
        ) or {}
        out.append({k: full.get(k) for k in _ADDRESS_PUBLIC_FIELDS})
    return out


def get_default_customer_address(customer_name: str) -> dict | None:
    """Return the customer-safe default billing address for the Phase 7A
    Quotation autofill, or None if none exists. Prefers explicit primary,
    falls back to the most-recently modified address linked to the Customer.
    """
    addrs = _list_addresses_for_customer(customer_name)
    if not addrs:
        return None
    for a in addrs:
        if a.get("is_primary_address"):
            return a
    return addrs[0]


def get_shipping_customer_address(customer_name: str) -> dict | None:
    """Return the customer-safe shipping address, or fall back to billing."""
    addrs = _list_addresses_for_customer(customer_name)
    if not addrs:
        return None
    for a in addrs:
        if a.get("is_shipping_address"):
            return a
    return get_default_customer_address(customer_name)


# ---------------------------------------------------------------------------
# Whitelisted methods
# ---------------------------------------------------------------------------

@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_my_addresses():
    """Return the current session user's addresses (customer-safe fields only).

    `allow_guest=True` so Frappe doesn't 403 the guest; we then return our own
    AUTH_REQUIRED envelope -- matching the Phase 6 pattern for consistency.
    """
    if is_guest():
        return err("AUTH_REQUIRED", _("You must be logged in."))

    customer_name = get_customer_for_session_user()
    if not customer_name:
        # Staff users / users whose Customer didn't lazy-create. Returning []
        # is friendlier than an error here; the client UI will show the empty
        # state and address creation still works for real customers.
        return ok({"addresses": []})

    return ok({"addresses": _list_addresses_for_customer(customer_name)})


@frappe.whitelist(methods=["POST"])
def save_my_address(
    name: str | None = None,
    address_title: str | None = None,
    address_type: str | None = None,
    address_line1: str | None = None,
    address_line2: str | None = None,
    city: str | None = None,
    state: str | None = None,
    country: str | None = None,
    pincode: str | None = None,
    phone: str | None = None,
    email_id: str | None = None,
    is_primary_address: bool | str | None = None,
    is_shipping_address: bool | str | None = None,
):
    if is_guest():
        return err("AUTH_REQUIRED", _("You must be logged in."))

    customer_name = get_customer_for_session_user()
    if not customer_name:
        return err(
            "CUSTOMER_REQUIRED",
            _("Your account does not have a linked Customer record."),
        )

    # Validation -------------------------------------------------------------
    a_type = _norm(address_type, 32)
    if a_type and a_type not in _ALLOWED_TYPES:
        a_type = "Billing"
    if not a_type:
        a_type = "Billing"

    line1 = _norm(address_line1)
    if not line1:
        return err("VALIDATION_ERROR", _("Address line 1 is required."))

    city_norm = _norm(city)
    if not city_norm:
        return err("VALIDATION_ERROR", _("City is required."))

    country_norm = _norm(country, 128)
    if not country_norm:
        return err("VALIDATION_ERROR", _("Country is required."))
    if not frappe.db.exists("Country", country_norm):
        return err(
            "VALIDATION_ERROR",
            _("Country '{0}' is not recognized.").format(country_norm),
        )

    line2 = _norm(address_line2)
    state_norm = _norm(state, 128)
    pincode_norm = _norm_phone(pincode) if pincode else ""
    phone_norm = _norm_phone(phone) if phone else ""
    if phone_norm and not _PHONE_RE.match(phone_norm):
        return err("VALIDATION_ERROR", _("Phone number format is invalid."))
    email_norm = _norm(email_id, 240)
    if email_norm and not _EMAIL_RE.match(email_norm):
        return err("VALIDATION_ERROR", _("Email format is invalid."))

    title = _norm(address_title) or _norm(address_title or city_norm)
    if not title:
        title = customer_name

    primary_flag = _coerce_bool(is_primary_address)
    shipping_flag = _coerce_bool(is_shipping_address)

    # Branch: update existing vs create new ----------------------------------
    target_name = _norm(name)
    try:
        if target_name:
            if not address_belongs_to_customer(target_name, customer_name):
                # Same 404 as "not yours" -- no existence leak.
                return err("NOT_FOUND", _("Address not found."))
            addr = frappe.get_doc("Address", target_name)
        else:
            addr = frappe.new_doc("Address")
            addr.append("links", {
                "link_doctype": "Customer",
                "link_name": customer_name,
            })

        addr.address_title = title
        addr.address_type = a_type
        addr.address_line1 = line1
        addr.address_line2 = line2
        addr.city = city_norm
        addr.state = state_norm
        addr.country = country_norm
        addr.pincode = pincode_norm
        addr.phone = phone_norm
        addr.email_id = email_norm
        addr.is_primary_address = primary_flag
        addr.is_shipping_address = shipping_flag

        addr.save(ignore_permissions=True)

        # When the user flips a row to primary/shipping, ERPNext doesn't
        # automatically clear the flag on sibling addresses. Do it ourselves
        # so the customer always has exactly one of each.
        _ensure_single_flag(customer_name, addr.name, "is_primary_address", primary_flag)
        _ensure_single_flag(customer_name, addr.name, "is_shipping_address", shipping_flag)

        frappe.db.commit()
    except frappe.ValidationError as e:
        return err("VALIDATION_ERROR", str(e))
    except Exception as e:
        frappe.log_error(title="save_my_address server error", message=str(e))
        return err("SERVER_ERROR", _("Could not save the address."))

    full = frappe.db.get_value(
        "Address",
        addr.name,
        list(_ADDRESS_PUBLIC_FIELDS),
        as_dict=True,
    ) or {}
    return ok({"address": {k: full.get(k) for k in _ADDRESS_PUBLIC_FIELDS}})


def _ensure_single_flag(customer_name: str, address_name: str, field: str, flag: int):
    """Clear `field` on every OTHER Address of this Customer when this one is
    set. Idempotent + no-op if flag is 0.
    """
    if not flag:
        return
    sibling_rows = frappe.db.sql(
        """
        SELECT a.name
          FROM `tabAddress` a
          JOIN `tabDynamic Link` dl
            ON dl.parent = a.name
           AND dl.parenttype = 'Address'
           AND dl.link_doctype = 'Customer'
           AND dl.link_name = %s
         WHERE a.name != %s
        """,
        (customer_name, address_name),
    )
    for (sibling,) in sibling_rows:
        frappe.db.set_value("Address", sibling, field, 0, update_modified=False)


@frappe.whitelist(methods=["POST"])
def delete_my_address(name: str | None = None):
    if is_guest():
        return err("AUTH_REQUIRED", _("You must be logged in."))

    customer_name = get_customer_for_session_user()
    if not customer_name:
        return err(
            "CUSTOMER_REQUIRED",
            _("Your account does not have a linked Customer record."),
        )

    target = _norm(name)
    if not target:
        return err("VALIDATION_ERROR", _("Address name is required."))

    if not address_belongs_to_customer(target, customer_name):
        return err("NOT_FOUND", _("Address not found."))

    try:
        frappe.delete_doc("Address", target, ignore_permissions=True)
        frappe.db.commit()
        return ok({"deleted": target})
    except frappe.LinkExistsError as e:
        # Address is linked to a submitted document (e.g. Quotation). Soft-
        # delete instead: clear the Customer Dynamic Link AND mark disabled.
        # This way the address disappears from the customer's list without
        # breaking referential integrity on submitted docs.
        try:
            frappe.db.sql(
                """
                DELETE FROM `tabDynamic Link`
                 WHERE parent = %s
                   AND parenttype = 'Address'
                   AND link_doctype = 'Customer'
                   AND link_name = %s
                """,
                (target, customer_name),
            )
            frappe.db.set_value("Address", target, "disabled", 1, update_modified=False)
            frappe.db.commit()
            return ok({"deleted": target, "soft": True, "reason": str(e)})
        except Exception as e2:
            frappe.log_error(title="delete_my_address soft fallback", message=str(e2))
            return err(
                "BLOCKED_BY_LINKS",
                _("This address is referenced by another document and could not be deleted."),
            )
    except Exception as e:
        frappe.log_error(title="delete_my_address server error", message=str(e))
        return err("SERVER_ERROR", _("Could not delete the address."))
