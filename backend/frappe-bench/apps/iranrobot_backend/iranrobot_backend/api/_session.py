"""Session + identity helpers for Phase 4 auth API.

Phase 4 uses the native Frappe/ERPNext customer model:

    Frappe User ─link via Contact.user─▶ Contact ─Dynamic Link─▶ ERPNext Customer

No custom Customer Profile DocType. This module owns the *idempotent* lazy
creation of the Contact + Customer pair on first authenticated whoami().
"""

import frappe


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def is_guest() -> bool:
    return frappe.session.user in (None, "Guest")


def get_csrf_token() -> str:
    """Return the current session's CSRF token so the SPA can attach it to POSTs.

    Frappe stores this on `frappe.local.session.data.csrf_token`. For a freshly
    minted Guest session, it may not be generated until first reference; we
    force generation if missing so the first whoami response is usable.
    """
    sess = getattr(frappe.local, "session", None)
    if sess is None or not getattr(sess, "data", None):
        return ""
    token = sess.data.get("csrf_token") if isinstance(sess.data, dict) else getattr(sess.data, "csrf_token", None)
    if not token:
        # Generate + store one (matches frappe.sessions.Session.get_csrf_token behavior)
        from frappe.utils import generate_hash
        token = generate_hash()
        if isinstance(sess.data, dict):
            sess.data["csrf_token"] = token
        else:
            sess.data.csrf_token = token
    return token or ""


def safe_user_payload(user_email: str) -> dict:
    """Customer-facing User fields. Never includes role list, enabled flag,
    user_type, or any admin/internal field."""
    u = frappe.db.get_value(
        "User",
        user_email,
        ["email", "full_name", "first_name", "last_name", "language"],
        as_dict=True,
    ) or {}
    return {
        "email": u.get("email"),
        "full_name": u.get("full_name") or "",
        "first_name": u.get("first_name") or "",
        "last_name": u.get("last_name") or "",
        "preferred_language": (u.get("language") or "fa").lower(),
    }


def is_system_manager(user_email: str) -> bool:
    """True iff the user has the System Manager role. Returned as a single
    boolean flag (we never expose the raw role list)."""
    if not user_email or user_email == "Guest":
        return False
    return bool(
        frappe.db.exists("Has Role", {"parent": user_email, "role": "System Manager"})
    )


# ---------------------------------------------------------------------------
# Lazy Contact + Customer creation
# ---------------------------------------------------------------------------

def get_or_create_customer_for_user(user_email: str) -> tuple[str | None, str | None]:
    """Return (contact_name, customer_name) for the given User, or (None, None)
    if the user is staff (Administrator / System Manager) and should not have
    a Customer record.

    Idempotent: subsequent calls find the existing Contact and its linked
    Customer; they do NOT create duplicates.
    """
    if not user_email or user_email == "Guest":
        raise frappe.PermissionError("Cannot resolve a customer for Guest.")

    # Staff users (Administrator + System Manager) operate the back-office in
    # Desk; we deliberately don't link them to a Customer. This also avoids a
    # known ERPNext v15 Loyalty Program SQL bug that fires on Customer.insert
    # when the saving user has no Customer Group context (e.g. bench-execute
    # smoke tests running as Administrator).
    if user_email == "Administrator" or is_system_manager(user_email):
        return None, None

    user_doc = frappe.get_doc("User", user_email)

    # Step 1 — find an existing Contact for this user (by the Contact.user link)
    contact_name = frappe.db.get_value("Contact", {"user": user_email}, "name")

    if contact_name:
        # Step 2a — find a Customer linked to this Contact via Dynamic Link
        existing_customer = _find_linked_customer(contact_name)
        if existing_customer:
            return contact_name, existing_customer
        # Contact exists but no Customer link — create the Customer + append the link
        customer_name = _create_customer(user_doc)
        contact_doc = frappe.get_doc("Contact", contact_name)
        contact_doc.append("links", {
            "link_doctype": "Customer",
            "link_name": customer_name,
        })
        contact_doc.save(ignore_permissions=True)
        return contact_name, customer_name

    # Step 2b — no Contact yet → create Customer first, then Contact with its link
    customer_name = _create_customer(user_doc)
    contact_doc = frappe.get_doc({
        "doctype": "Contact",
        "first_name": user_doc.first_name or (user_doc.email or "").split("@")[0],
        "last_name": user_doc.last_name or "",
        "email_ids": [{"email_id": user_doc.email, "is_primary": 1}],
        "user": user_doc.email,
        "links": [{
            "link_doctype": "Customer",
            "link_name": customer_name,
        }],
    })
    contact_doc.insert(ignore_permissions=True)
    return contact_doc.name, customer_name


def _create_customer(user_doc) -> str:
    """Create a fresh ERPNext Customer for this User and return its name."""
    customer_name_str = (
        user_doc.full_name
        or f"{user_doc.first_name or ''} {user_doc.last_name or ''}".strip()
        or user_doc.email
    )
    customer = frappe.get_doc({
        "doctype": "Customer",
        "customer_name": customer_name_str,
        "customer_type": "Individual",
        "customer_group": "Individual",
        "territory": "All Territories",
    })
    # Work around an ERPNext v15 + MariaDB 12 SQL bug: Customer.validate()
    # calls set_loyalty_program() which runs `get_loyalty_programs()`, whose
    # filter contains `ifnull(to_date, ...)` without backticking the column.
    # MariaDB 12.x rejects this with a 1064 syntax error. There are no Loyalty
    # Programs configured on this project, so the method's only effect would
    # be to query (and crash); we no-op it on the single doc instance.
    customer.set_loyalty_program = lambda: None  # noqa: E731
    customer.insert(ignore_permissions=True)
    return customer.name


def _find_linked_customer(contact_name: str) -> str | None:
    """Return the Customer name linked to this Contact via Dynamic Link, or None."""
    rows = frappe.db.sql(
        """
        SELECT link_name
        FROM `tabDynamic Link`
        WHERE parent = %s
          AND parenttype = 'Contact'
          AND link_doctype = 'Customer'
        LIMIT 1
        """,
        (contact_name,),
    )
    return rows[0][0] if rows else None


# ---------------------------------------------------------------------------
# Contact + Customer field projection (customer-safe)
# ---------------------------------------------------------------------------

def get_contact_summary(contact_name: str) -> dict:
    """Return the customer-safe view of a Contact row."""
    if not contact_name or not frappe.db.exists("Contact", contact_name):
        return {}
    c = frappe.get_doc("Contact", contact_name)
    # mobile_no is the canonical phone for ERPNext Contact; we surface a single
    # "phone" field on the SPA-facing payload pointing at mobile_no.
    mobile = c.mobile_no or c.phone or ""
    return {
        "contact_id": c.name,
        "phone": mobile,
        # ERPNext stores marketing-opt-OUT as `unsubscribed`. Flip for the SPA so
        # the frontend handles a positive "opted-in" flag.
        "marketing_opt_in": not bool(c.unsubscribed),
    }


def get_customer_summary(customer_name: str) -> dict:
    if not customer_name or not frappe.db.exists("Customer", customer_name):
        return {}
    c = frappe.get_doc("Customer", customer_name)
    return {
        "customer_id": c.name,
        "customer_name": c.customer_name,
    }


# ---------------------------------------------------------------------------
# Phase 8A -- Lazy Robot Wallet Account creation
# ---------------------------------------------------------------------------

def get_or_create_wallet_for_customer(customer_name: str) -> str | None:
    """Return the Robot Wallet Account name for this Customer, creating one if
    missing. Returns None if `customer_name` is falsy.

    Idempotent: a second call with the same Customer returns the existing
    wallet. The unique constraint on Robot Wallet Account.customer is the
    backstop against duplicates.
    """
    if not customer_name:
        return None
    existing = frappe.db.get_value(
        "Robot Wallet Account",
        {"customer": customer_name},
        "name",
    )
    if existing:
        return existing
    wallet = frappe.get_doc({
        "doctype": "Robot Wallet Account",
        "customer": customer_name,
        "currency": "USD",
        "status": "Active",
        "balance_usd": 0,
        "available_balance_usd": 0,
    })
    wallet.insert(ignore_permissions=True)
    return wallet.name
