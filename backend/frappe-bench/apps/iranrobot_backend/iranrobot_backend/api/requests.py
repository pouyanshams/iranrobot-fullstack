"""Phase 5 + 6 + 7A -- Quote / Procurement / Support APIs.

All methods return the project's `{ok, data, error}` envelope (see
`_response.py`). The Phase 5 POSTs accept guest submissions; the Phase 6 reads
and the Phase 7A conversion are auth-only. Phase 7A creates ONE ERPNext
DocType (Quotation, in Draft); no Sales Order, Invoice, or Payment Entry is
created here -- those are deferred to later sub-phases.

    iranrobot_backend.api.requests.submit_quote_request               POST  allow_guest=True   (P5)
    iranrobot_backend.api.requests.submit_procurement_request         POST  allow_guest=True   (P5)
    iranrobot_backend.api.requests.submit_support_ticket              POST  allow_guest=True   (P5)
    iranrobot_backend.api.requests.get_my_requests                    GET   auth required      (P6)
    iranrobot_backend.api.requests.get_my_request_detail              GET   auth required      (P6)
    iranrobot_backend.api.requests.convert_quote_request_to_quotation POST  Sales role only    (P7A)

Identity model:
    - Logged-in Website Users have an ERPNext Customer + Contact (lazy-created
      in `api/_session.py`). The submit_* methods auto-link both on the new
      record so staff can find the customer from the request in Desk.
    - Guests submit name/email/phone. We do NOT create a Customer for guests
      (a guest who later becomes a customer gets their Customer lazy-created on
      first whoami, per Phase 4).

Security posture:
    - All public DocType permissions stay closed to the Customer role; staff
      use Desk to manage the queue.
    - Customers can only read their own records via `get_my_requests`
      (server-side filter by `frappe.session.user`).
    - Internal fields (internal_notes, raw audit data) are NEVER returned to
      customers.
    - Frontend prices are NEVER trusted: each Robot Quote Request Item's
      unit_price_usd is snapshotted from Robot Product on the server.
"""

import json
import re

import frappe
from frappe import _
from frappe.utils import now_datetime

from iranrobot_backend.api._response import err, ok
from iranrobot_backend.api._session import (
    get_or_create_customer_for_user,
    is_guest,
)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

_PERSIAN_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
_PHONE_RE = re.compile(r"^[0-9+\-\s]{7,}$")
_MAX_MESSAGE_LEN = 4000
_MAX_DATA_LEN = 200


def _norm(value, max_len: int = _MAX_DATA_LEN) -> str:
    """Strip + collapse whitespace + truncate. Returns "" for None."""
    s = (value if isinstance(value, str) else ("" if value is None else str(value))).strip()
    return s[:max_len]


def _norm_phone(value) -> str:
    return _norm(value).translate(_PERSIAN_DIGITS)


def _parse_int(value, default: int = 1, min_value: int = 1, max_value: int = 9999) -> int:
    try:
        n = int(str(value).strip()) if value not in (None, "") else default
    except (TypeError, ValueError):
        return default
    if n < min_value:
        return min_value
    if n > max_value:
        return max_value
    return n


def _parse_float(value):
    if value in (None, ""):
        return None
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def _coerce_lang(value) -> str:
    lang = _norm(value).lower()
    return lang if lang in ("fa", "en") else "fa"


def _parse_items(value):
    """Accept items as a list, dict-keyed list, or JSON string. Returns a list."""
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return []
        try:
            parsed = json.loads(s)
        except json.JSONDecodeError:
            return []
        if isinstance(parsed, list):
            return parsed
        if isinstance(parsed, dict) and "items" in parsed:
            return parsed["items"] or []
    return []


def _resolve_current_customer():
    """Return (customer_name, contact_name, user_email) for the current session,
    or (None, None, '') for guests / staff."""
    if is_guest():
        return None, None, ""
    user_email = frappe.session.user
    try:
        contact_name, customer_name = get_or_create_customer_for_user(user_email)
        frappe.db.commit()
        return customer_name, contact_name, user_email
    except Exception as e:
        frappe.log_error(
            title="phase5 customer lookup", message=f"user={user_email}\n{e}"
        )
        return None, None, user_email


def _customer_display(customer_name: str | None) -> str:
    if not customer_name:
        return ""
    val = frappe.db.get_value("Customer", customer_name, "customer_name") or ""
    return val


def _contact_display(contact_name: str | None) -> tuple[str, str]:
    """Return (email, phone) for the linked Contact, or ("", "")."""
    if not contact_name:
        return "", ""
    c = frappe.db.get_value(
        "Contact", contact_name, ["email_id", "mobile_no", "phone"], as_dict=True
    ) or {}
    return (c.get("email_id") or ""), (c.get("mobile_no") or c.get("phone") or "")


# ---------------------------------------------------------------------------
# 1. submit_quote_request
# ---------------------------------------------------------------------------

@frappe.whitelist(allow_guest=True, methods=["POST"])
def submit_quote_request(
    items=None,
    customer_name=None,
    email=None,
    phone=None,
    message=None,
    language=None,
):
    """Create a Robot Quote Request from a cart-style payload.

    Input:
        items     - JSON string OR list of {robot_product, quantity, mode, requested_days?, notes?}
        customer_name, email, phone - guest contact info (ignored if logged in
                    AND a linked Customer is resolved)
        message   - optional customer-facing note
        language  - "fa" | "en"
    """
    parsed_items = _parse_items(items)
    if not parsed_items:
        return err("EMPTY_CART", _("Add at least one item to the quote before submitting."))

    if len(parsed_items) > 50:
        return err("VALIDATION_ERROR", _("A single request cannot contain more than 50 lines."))

    # Resolve identity (or guest)
    cust_id, contact_id, user_email = _resolve_current_customer()

    # When the user is logged in AND has a linked Customer, prefer the linked
    # display fields. Guests must provide name + (email or phone).
    if cust_id:
        cust_display = _customer_display(cust_id)
        c_email, c_phone = _contact_display(contact_id)
        resolved_customer_name = cust_display or _norm(customer_name)
        resolved_email = c_email or _norm(email)
        resolved_phone = c_phone or _norm_phone(phone)
    else:
        resolved_customer_name = _norm(customer_name)
        resolved_email = _norm(email)
        resolved_phone = _norm_phone(phone)

        if not resolved_customer_name:
            return err("VALIDATION_ERROR", _("Name is required for guest submissions."))
        if resolved_email and not _EMAIL_RE.match(resolved_email):
            return err("VALIDATION_ERROR", _("Email format is invalid."))
        if resolved_phone and not _PHONE_RE.match(resolved_phone):
            return err("VALIDATION_ERROR", _("Phone number format is invalid."))
        if not (resolved_email or resolved_phone):
            return err("VALIDATION_ERROR", _("Provide an email or phone number."))

    # Validate + resolve each line server-side.
    resolved_lines: list[dict] = []
    for raw_row in parsed_items:
        if not isinstance(raw_row, dict):
            return err("VALIDATION_ERROR", _("Each cart line must be an object."))

        robot_id = _norm(raw_row.get("robot_product") or raw_row.get("robotId"), 140)
        if not robot_id:
            return err("INVALID_PRODUCT", _("Each line must reference a Robot Product."))

        if not frappe.db.exists("Robot Product", robot_id):
            return err("INVALID_PRODUCT", _("Robot Product '{0}' was not found.").format(robot_id))

        prod = frappe.db.get_value(
            "Robot Product",
            robot_id,
            ["product_name_en", "price_usd", "rent_per_day_usd", "erpnext_item"],
            as_dict=True,
        ) or {}

        mode = _norm(raw_row.get("mode"), 10).lower()
        if mode not in ("buy", "rent", "procure"):
            return err("VALIDATION_ERROR", _("Invalid mode '{0}'.").format(mode))

        quantity = _parse_int(raw_row.get("quantity") or raw_row.get("qty"), default=1, min_value=1, max_value=9999)
        requested_days = _parse_int(raw_row.get("requested_days") or raw_row.get("days"), default=1, min_value=1, max_value=3650) if mode == "rent" else None

        if mode == "rent":
            unit = float(prod.get("rent_per_day_usd") or 0)
        else:
            unit = float(prod.get("price_usd") or 0)

        if mode == "rent":
            line_total = unit * quantity * (requested_days or 1)
        else:
            line_total = unit * quantity

        resolved_lines.append({
            "robot_product": robot_id,
            "erpnext_item": prod.get("erpnext_item") or "",
            "product_name": (prod.get("product_name_en") or robot_id)[:_MAX_DATA_LEN],
            "quantity": quantity,
            "mode": mode,
            "requested_days": requested_days,
            "unit_price_usd": unit,
            "line_total_usd": line_total,
            "notes": _norm(raw_row.get("notes"), _MAX_DATA_LEN),
        })

    # Build + insert
    try:
        doc = frappe.get_doc({
            "doctype": "Robot Quote Request",
            "status": "New",
            "source": "Website",
            "language": _coerce_lang(language),
            "submitted_at": now_datetime(),
            "customer": cust_id or None,
            "contact": contact_id or None,
            "user_email": user_email,
            "customer_name": resolved_customer_name,
            "email": resolved_email,
            "phone": resolved_phone,
            "message": _norm(message, _MAX_MESSAGE_LEN),
            "items": resolved_lines,
        })
        doc.insert(ignore_permissions=True)
        frappe.db.commit()
    except frappe.ValidationError as e:
        return err("VALIDATION_ERROR", str(e))
    except Exception as e:
        frappe.log_error(title="submit_quote_request server error", message=str(e))
        return err("SERVER_ERROR", _("Could not save the quote request."))

    return ok({
        "request_id": doc.name,
        "status": doc.status,
        "total_estimate_usd": doc.total_estimate_usd or 0,
    })


# ---------------------------------------------------------------------------
# 2. submit_procurement_request
# ---------------------------------------------------------------------------

@frappe.whitelist(allow_guest=True, methods=["POST"])
def submit_procurement_request(
    product_name=None,
    brand=None,
    quantity=None,
    origin_country=None,
    destination_city=None,
    target_budget_usd=None,
    timeline=None,
    message=None,
    company=None,
    contact_name=None,
    email=None,
    phone=None,
    language=None,
):
    name_in = _norm(product_name, _MAX_DATA_LEN)
    if not name_in:
        return err("VALIDATION_ERROR", _("Product name is required."))

    cust_id, contact_id, user_email = _resolve_current_customer()

    if cust_id:
        cust_display = _customer_display(cust_id)
        c_email, c_phone = _contact_display(contact_id)
        resolved_contact_name = _norm(contact_name) or cust_display
        resolved_email = c_email or _norm(email)
        resolved_phone = c_phone or _norm_phone(phone)
    else:
        resolved_contact_name = _norm(contact_name)
        resolved_email = _norm(email)
        resolved_phone = _norm_phone(phone)

        if not resolved_contact_name:
            return err("VALIDATION_ERROR", _("Your name is required."))
        if resolved_email and not _EMAIL_RE.match(resolved_email):
            return err("VALIDATION_ERROR", _("Email format is invalid."))
        if resolved_phone and not _PHONE_RE.match(resolved_phone):
            return err("VALIDATION_ERROR", _("Phone number format is invalid."))
        if not (resolved_email or resolved_phone):
            return err("VALIDATION_ERROR", _("Provide an email or phone number."))

    try:
        doc = frappe.get_doc({
            "doctype": "Robot Procurement Request",
            "status": "New",
            "source": "Website",
            "language": _coerce_lang(language),
            "submitted_at": now_datetime(),
            "customer": cust_id or None,
            "contact": contact_id or None,
            "user_email": user_email,
            "contact_name": resolved_contact_name,
            "email": resolved_email,
            "phone": resolved_phone,
            "company": _norm(company, _MAX_DATA_LEN),
            "product_name": name_in,
            "brand": _norm(brand, _MAX_DATA_LEN),
            "quantity": _parse_int(quantity, default=1, min_value=1, max_value=99999),
            "origin_country": _norm(origin_country, _MAX_DATA_LEN),
            "destination_city": _norm(destination_city, _MAX_DATA_LEN),
            "target_budget_usd": _parse_float(target_budget_usd),
            "timeline": _norm(timeline, _MAX_DATA_LEN),
            "message": _norm(message, _MAX_MESSAGE_LEN),
        })
        doc.insert(ignore_permissions=True)
        frappe.db.commit()
    except frappe.ValidationError as e:
        return err("VALIDATION_ERROR", str(e))
    except Exception as e:
        frappe.log_error(title="submit_procurement_request server error", message=str(e))
        return err("SERVER_ERROR", _("Could not save the procurement request."))

    return ok({
        "request_id": doc.name,
        "status": doc.status,
    })


# ---------------------------------------------------------------------------
# 3. submit_support_ticket -- ERPNext Issue
# ---------------------------------------------------------------------------

# Mapping from the frontend topic value -> a short tag we prepend to the subject
# so Ops can triage. The frontend already sends a human label; we just snapshot.
_TOPIC_TAGS = {
    "": "Sales",
    "sales": "Sales",
    "procure": "Sourcing",
    "rent": "Rental",
    "tech": "Tech support",
    "other": "Other",
}


@frappe.whitelist(allow_guest=True, methods=["POST"])
def submit_support_ticket(
    name=None,
    email=None,
    phone=None,
    topic=None,
    subject=None,
    message=None,
    language=None,
):
    msg_norm = _norm(message, _MAX_MESSAGE_LEN)
    if not msg_norm:
        return err("VALIDATION_ERROR", _("Message is required."))

    cust_id, contact_id, user_email = _resolve_current_customer()

    if cust_id:
        cust_display = _customer_display(cust_id)
        c_email, _c_phone = _contact_display(contact_id)
        contact_display_name = _norm(name) or cust_display
        contact_email = c_email or _norm(email)
    else:
        contact_display_name = _norm(name)
        contact_email = _norm(email)

        if not contact_display_name:
            return err("VALIDATION_ERROR", _("Your name is required."))
        if not contact_email or not _EMAIL_RE.match(contact_email):
            return err("VALIDATION_ERROR", _("A valid email is required."))

    topic_in = _norm(topic, 32).lower()
    topic_tag = _TOPIC_TAGS.get(topic_in, "Sales")

    subject_in = _norm(subject, _MAX_DATA_LEN)
    if not subject_in:
        # Synthesize a reasonable default subject from the topic + name
        subject_in = f"[{topic_tag}] from {contact_display_name or 'website visitor'}"

    # Build a customer-safe description that staff can read in Desk.
    description_lines = [
        msg_norm,
        "",
        "—",
        f"Submitted via Website ({_coerce_lang(language)})",
        f"Name: {contact_display_name}",
        f"Email: {contact_email}",
    ]
    phone_norm = _norm_phone(phone)
    if phone_norm:
        description_lines.append(f"Phone: {phone_norm}")
    if topic_tag:
        description_lines.append(f"Topic: {topic_tag}")
    description_html = "<br>".join(frappe.utils.escape_html(line) for line in description_lines)

    try:
        doc = frappe.get_doc({
            "doctype": "Issue",
            "subject": subject_in,
            "description": description_html,
            "raised_by": contact_email,
            "customer": cust_id or None,
            "contact": contact_id or None,
            "status": "Open",
        })
        doc.insert(ignore_permissions=True)
        frappe.db.commit()
    except frappe.ValidationError as e:
        return err("VALIDATION_ERROR", str(e))
    except Exception as e:
        frappe.log_error(title="submit_support_ticket server error", message=str(e))
        return err("SERVER_ERROR", _("Could not save the support ticket."))

    return ok({
        "ticket_id": doc.name,
        "status": doc.status,
    })


# ---------------------------------------------------------------------------
# 4. get_my_requests -- read-only listing for the logged-in customer
# ---------------------------------------------------------------------------

# Customer-safe field projections. Internal notes / audit fields are EXCLUDED.
_QR_PUBLIC_FIELDS = [
    "name", "status", "submitted_at", "customer_name", "total_estimate_usd",
    "language", "creation",
]
_PR_PUBLIC_FIELDS = [
    "name", "status", "submitted_at", "product_name", "brand", "quantity",
    "target_budget_usd", "language", "creation",
]
_ISSUE_PUBLIC_FIELDS = [
    "name", "status", "subject", "creation",
]


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_my_requests(limit: int = 20):
    """Return the current customer's recent intake records.

    Auth required *at the application level*; we mark `allow_guest=True` only so
    that Frappe doesn't reject a guest with its raw 403 page -- we return the
    project envelope `AUTH_REQUIRED` instead. Server-side filter by
    `frappe.session.user`; we never accept a customer/user param from the
    client. Admin-only fields are never projected. Phase 6 dashboard will
    consume this; Phase 5 ships the API without wiring the UI.
    """
    if is_guest():
        return err("AUTH_REQUIRED", _("You must be logged in."))

    try:
        limit_n = max(1, min(int(limit), 100))
    except (TypeError, ValueError):
        limit_n = 20

    user_email = frappe.session.user
    cust_id, _contact_id = None, None
    try:
        _contact_id, cust_id = get_or_create_customer_for_user(user_email)
    except Exception as e:
        frappe.log_error(title="get_my_requests lookup", message=f"user={user_email}\n{e}")

    # Build "owner filter" -- match either by Customer link OR by user_email
    # snapshot, so requests submitted as a guest *before login* but with the
    # same email could (manually) be reconciled later. For now we project both.
    owner_filter_qr = {"user_email": user_email}
    owner_filter_pr = {"user_email": user_email}
    if cust_id:
        # Use an OR via two queries + dedup (Frappe's get_list doesn't easily OR).
        # Simpler: query by customer OR user_email separately and merge.
        pass

    def _list(doctype: str, fields: list[str], filters: dict, limit: int):
        try:
            return frappe.get_all(
                doctype,
                fields=fields,
                filters=filters,
                order_by="creation desc",
                limit_page_length=limit,
                ignore_permissions=True,
            )
        except Exception as e:
            frappe.log_error(title=f"get_my_requests list {doctype}", message=str(e))
            return []

    def _merge(a, b, key="name"):
        seen = set()
        out = []
        for r in (a + b):
            if r.get(key) in seen:
                continue
            seen.add(r.get(key))
            out.append(r)
        out.sort(key=lambda r: r.get("creation") or "", reverse=True)
        return out[:limit_n]

    qr_by_email = _list("Robot Quote Request", _QR_PUBLIC_FIELDS, owner_filter_qr, limit_n)
    pr_by_email = _list("Robot Procurement Request", _PR_PUBLIC_FIELDS, owner_filter_pr, limit_n)
    qr_by_customer = _list("Robot Quote Request", _QR_PUBLIC_FIELDS, {"customer": cust_id}, limit_n) if cust_id else []
    pr_by_customer = _list("Robot Procurement Request", _PR_PUBLIC_FIELDS, {"customer": cust_id}, limit_n) if cust_id else []
    quotes = _merge(qr_by_email, qr_by_customer)
    procurements = _merge(pr_by_email, pr_by_customer)

    # Issues: customers don't get a `user_email` link; match by raised_by + customer.
    issue_filters = {"raised_by": user_email}
    issues_by_email = _list("Issue", _ISSUE_PUBLIC_FIELDS, issue_filters, limit_n)
    issues_by_customer = _list("Issue", _ISSUE_PUBLIC_FIELDS, {"customer": cust_id}, limit_n) if cust_id else []
    issues = _merge(issues_by_email, issues_by_customer)

    # Enrich quote rows with a lightweight item summary so the Phase 6 list
    # view can show "3 items · AiMOGA Mornine, Unitree G1, …" without an extra
    # round trip per row. We deliberately keep this to (count, first_3_names).
    enriched_quotes = []
    for q in quotes:
        try:
            child_rows = frappe.get_all(
                "Robot Quote Request Item",
                filters={"parent": q["name"], "parenttype": "Robot Quote Request"},
                fields=["product_name"],
                order_by="idx asc",
                limit_page_length=3,
                ignore_permissions=True,
            )
            count = frappe.db.count("Robot Quote Request Item", {"parent": q["name"], "parenttype": "Robot Quote Request"})
        except Exception:
            child_rows = []
            count = 0
        enriched_quotes.append({
            **q,
            "item_count": count,
            "item_preview": [r["product_name"] for r in child_rows if r.get("product_name")],
        })

    return ok({
        "quote_requests": enriched_quotes,
        "procurement_requests": procurements,
        "support_tickets": issues,
    })


# ---------------------------------------------------------------------------
# 5. get_my_request_detail -- single-record fetch (customer-safe)
# ---------------------------------------------------------------------------

# Customer-safe field allow-lists for the detail endpoint. These are stricter
# than the list projection because the detail view shows more fields, AND we
# explicitly omit any admin-only field (internal_notes, contact link audit, etc.)
_QR_DETAIL_FIELDS = (
    "name", "status", "submitted_at", "language", "message",
    "customer_name", "total_estimate_usd", "creation",
    # Phase 7A -- expose Quotation linkage so the customer dashboard knows a
    # Quotation has been issued. The full quotation block is fetched below.
    "erpnext_quotation", "quotation_status", "proposal_amount_usd",
    # Phase 7B -- customer-side accept/reject state. The customer-safe note is
    # fine to echo back to the same customer (it's what they typed). IP and
    # response_user are kept staff-only.
    "customer_response", "customer_response_at", "customer_response_note",
)
_QR_ITEM_DETAIL_FIELDS = (
    "idx", "robot_product", "erpnext_item", "product_name",
    "quantity", "mode", "requested_days",
    "unit_price_usd", "line_total_usd", "notes",
)
_PR_DETAIL_FIELDS = (
    "name", "status", "submitted_at", "language", "message",
    "contact_name", "company",
    "product_name", "brand", "quantity",
    "origin_country", "destination_city",
    "target_budget_usd", "timeline",
    "creation",
)
_ISSUE_DETAIL_FIELDS = (
    "name", "status", "subject", "description", "creation", "modified",
)

# Allowed `kind` values from the frontend → ERPNext DocType name.
_KIND_TO_DOCTYPE = {
    "quote": "Robot Quote Request",
    "procurement": "Robot Procurement Request",
    "support": "Issue",
}


def _project(doc: dict, allow_list: tuple) -> dict:
    return {k: doc.get(k) for k in allow_list if k in doc}


def _record_belongs_to_user(doctype: str, name: str, user_email: str, cust_id: str | None) -> bool:
    """Server-side ownership check. We never trust a frontend-supplied filter."""
    if not name or not user_email or user_email == "Guest":
        return False
    if doctype == "Issue":
        row = frappe.db.get_value(
            "Issue", name, ["raised_by", "customer"], as_dict=True
        ) or {}
        if (row.get("raised_by") or "").lower() == user_email.lower():
            return True
        if cust_id and row.get("customer") == cust_id:
            return True
        return False
    row = frappe.db.get_value(
        doctype, name, ["user_email", "customer"], as_dict=True
    ) or {}
    if (row.get("user_email") or "").lower() == user_email.lower():
        return True
    if cust_id and row.get("customer") == cust_id:
        return True
    return False


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_my_request_detail(kind: str | None = None, name: str | None = None):
    """Fetch a single customer-safe record by kind + name.

    `kind` is one of "quote" | "procurement" | "support" (NEVER a DocType name
    supplied by the client). `name` is the record id. Ownership is enforced
    server-side: cross-customer access returns 404 (not 403) to avoid leaking
    record existence via id enumeration.

    Admin-only fields (internal_notes, audit data, etc.) are NEVER projected.
    """
    if is_guest():
        return err("AUTH_REQUIRED", _("You must be logged in."))

    if not kind or kind not in _KIND_TO_DOCTYPE:
        return err("VALIDATION_ERROR", _("Unknown record kind."))
    if not name:
        return err("VALIDATION_ERROR", _("Record name is required."))

    doctype = _KIND_TO_DOCTYPE[kind]
    user_email = frappe.session.user

    cust_id = None
    try:
        _contact_id, cust_id = get_or_create_customer_for_user(user_email)
    except Exception as e:
        frappe.log_error(title="get_my_request_detail lookup", message=f"user={user_email}\n{e}")

    if not frappe.db.exists(doctype, name):
        # Same 404 as "not yours", to avoid existence leak via enumeration.
        return err("NOT_FOUND", _("Record not found."))

    if not _record_belongs_to_user(doctype, name, user_email, cust_id):
        return err("NOT_FOUND", _("Record not found."))

    try:
        doc = frappe.get_doc(doctype, name)
    except Exception as e:
        frappe.log_error(title="get_my_request_detail load", message=str(e))
        return err("SERVER_ERROR", _("Could not load the record."))

    if doctype == "Robot Quote Request":
        as_dict = doc.as_dict()
        payload = _project(as_dict, _QR_DETAIL_FIELDS)
        payload["items"] = [_project(row, _QR_ITEM_DETAIL_FIELDS) for row in (as_dict.get("items") or [])]
        # Phase 7A -- attach a customer-safe Quotation block when one is linked.
        # The customer never sees taxes, base-currency fields, margins, terms,
        # internal notes, or addresses; only the allow-listed fields below.
        quotation_block = _customer_safe_quotation_block(as_dict.get("erpnext_quotation"))
        if quotation_block is not None:
            payload["quotation"] = quotation_block

        # Phase 7B -- whether the customer can act on this Quotation right now.
        # The same conditions are re-checked server-side inside
        # respond_to_quotation, so a stale `can_respond=true` cached on the
        # client can't be turned into a state-violating write.
        payload["can_respond"] = _can_customer_respond(as_dict)
        payload["response_allowed_actions"] = (
            list(_RESPONSE_ACTIONS) if payload["can_respond"] else []
        )
        return ok({"kind": "quote", "record": payload})

    if doctype == "Robot Procurement Request":
        payload = _project(doc.as_dict(), _PR_DETAIL_FIELDS)
        return ok({"kind": "procurement", "record": payload})

    # Issue
    payload = _project(doc.as_dict(), _ISSUE_DETAIL_FIELDS)
    return ok({"kind": "support", "record": payload})


# ---------------------------------------------------------------------------
# Phase 7A -- Robot Quote Request -> ERPNext Quotation conversion
# ---------------------------------------------------------------------------
#
# Staff trigger this from a Desk button (`robot_quote_request.js`). The
# endpoint never accepts guest sessions and validates role membership
# server-side; customers cannot call it even with a forged CSRF.

_QUOTATION_STATUS_FROM_ERPNEXT = {
    "Draft": "Draft",
    "Submitted": "Sent",
    "Open": "Sent",
    "Ordered": "Accepted",
    "Lost": "Rejected",
    "Expired": "Expired",
    "Cancelled": "Expired",
}

# Customer-safe projection allow-lists for the Phase 6 quote detail block.
# Anything not on these lists is NEVER returned to the customer.
_QUOTATION_CUSTOMER_FIELDS = (
    "name", "status", "transaction_date", "valid_till",
    "currency", "grand_total", "customer_name",
)
_QUOTATION_ITEM_CUSTOMER_FIELDS = (
    "idx", "item_code", "item_name", "description",
    "qty", "uom", "rate", "amount",
)

_SALES_ROLES = ("System Manager", "Sales User", "Sales Manager")


def _has_sales_role(user_email: str | None) -> bool:
    if not user_email or user_email == "Guest":
        return False
    if user_email == "Administrator":
        return True
    roles = set(frappe.get_roles(user_email) or [])
    return bool(roles.intersection(_SALES_ROLES))


def _resolve_selling_price_list() -> str | None:
    """Prefer 'Standard Selling'; fall back to any enabled selling price list."""
    if frappe.db.exists("Price List", "Standard Selling"):
        return "Standard Selling"
    rows = frappe.get_all(
        "Price List",
        filters={"selling": 1, "enabled": 1},
        fields=["name"],
        limit_page_length=1,
    )
    return rows[0].name if rows else None


def _customer_safe_quotation_block(quotation_name: str | None) -> dict | None:
    """Project a Quotation into a customer-safe block, or return None if the
    Quotation doesn't exist (e.g., it was deleted out from under the link)."""
    if not quotation_name or not frappe.db.exists("Quotation", quotation_name):
        return None
    q = frappe.get_doc("Quotation", quotation_name)
    qd = q.as_dict()
    payload = _project(qd, _QUOTATION_CUSTOMER_FIELDS)
    # Rename a couple of fields to be unambiguous on the wire.
    payload["quotation_id"] = payload.pop("name", quotation_name)
    payload["grand_total_usd"] = payload.pop("grand_total", 0) or 0
    payload["items"] = [
        _project(row, _QUOTATION_ITEM_CUSTOMER_FIELDS)
        for row in (qd.get("items") or [])
    ]
    return payload


@frappe.whitelist(methods=["POST"])
def convert_quote_request_to_quotation(name: str | None = None):
    """Create a Draft ERPNext Quotation from a Robot Quote Request.

    Phase 7A is conversion-only -- the Quotation is left in Draft so staff can
    set prices, valid-till, taxes, and submit in Desk. No Sales Order, Invoice,
    or Payment Entry is created.

    Auth: Sales User / Sales Manager / System Manager only. We don't decorate
    `allow_guest=True` and additionally re-check the role list so a Customer
    forging a CSRF token still gets NOT_PERMITTED.

    Returns:
        {ok:true, data:{quotation_id, status, grand_total_usd}} on success
        {ok:false, error:{code, message}} with one of the documented codes
    """
    if is_guest():
        return err("AUTH_REQUIRED", _("You must be logged in."))

    user_email = frappe.session.user
    if not _has_sales_role(user_email):
        return err(
            "NOT_PERMITTED",
            _("Only Sales staff can convert a Robot Quote Request to a Quotation."),
        )

    if not name:
        return err("VALIDATION_ERROR", _("Robot Quote Request name is required."))

    if not frappe.db.exists("Robot Quote Request", name):
        return err("NOT_FOUND", _("Robot Quote Request not found."))

    qr = frappe.get_doc("Robot Quote Request", name)

    # Idempotency: never create a duplicate. Staff who want a fresh Quotation
    # should clear the link in Desk first.
    if qr.erpnext_quotation:
        return err(
            "ALREADY_CONVERTED",
            _("This Quote Request already has a linked Quotation ({0}).").format(
                qr.erpnext_quotation
            ),
        )

    # Guest submissions have no Customer link; staff must create / pick one in
    # Desk before conversion can proceed.
    if not qr.customer:
        return err(
            "CUSTOMER_REQUIRED",
            _("This Quote Request has no linked Customer. Link a Customer first, then retry."),
        )
    if not frappe.db.exists("Customer", qr.customer):
        return err("CUSTOMER_REQUIRED", _("Linked Customer no longer exists."))

    if not qr.items:
        return err("VALIDATION_ERROR", _("This Quote Request has no items."))

    # Validate every line has a known ERPNext Item BEFORE creating anything.
    for row in qr.items:
        if not row.erpnext_item:
            return err(
                "ITEM_NOT_LINKED",
                _("Quote line {0} ({1}) has no linked ERPNext Item.").format(
                    row.idx, row.product_name or row.robot_product
                ),
            )
        if not frappe.db.exists("Item", row.erpnext_item):
            return err(
                "ITEM_NOT_LINKED",
                _("Quote line {0} references ERPNext Item '{1}', which no longer exists.").format(
                    row.idx, row.erpnext_item
                ),
            )

    company = "IranRobot"
    if not frappe.db.exists("Company", company):
        return err("SERVER_ERROR", _("Company 'IranRobot' is not configured."))

    price_list = _resolve_selling_price_list()
    if not price_list:
        return err("PRICE_LIST_MISSING", _("No selling Price List is available."))

    # Phase 7A.1 -- best-effort Address & Contact autofill. We resolve all
    # three fields here, BEFORE constructing the Quotation, so a fresh
    # Quotation has them populated whenever the customer has saved any
    # contact info. Missing values are silently skipped -- conversion never
    # fails on absence.
    autofill = _resolve_quotation_autofill(qr)

    # Build the Quotation. We construct directly (rather than via
    # `frappe.model.mapper.get_mapped_doc`) because our source -> target field
    # mapping is small and we want full control over which fields get touched.
    try:
        items_payload = []
        for row in qr.items:
            unit_price = float(row.unit_price_usd or 0)
            items_payload.append({
                "item_code": row.erpnext_item,
                "qty": row.quantity or 1,
                "uom": "Nos",
                "rate": unit_price,
                "description": (row.product_name or "")[:_MAX_DATA_LEN] or None,
            })

        quotation_payload = {
            "doctype": "Quotation",
            "quotation_to": "Customer",
            "party_name": qr.customer,
            "company": company,
            "currency": "USD",
            "selling_price_list": price_list,
            "transaction_date": frappe.utils.today(),
            "order_type": "Sales",
            "items": items_payload,
        }
        # Only set autofill fields when we actually resolved a value. ERPNext
        # rejects empty Link values; skipping is safer than passing "".
        if autofill.get("contact_person"):
            quotation_payload["contact_person"] = autofill["contact_person"]
        if autofill.get("customer_address"):
            quotation_payload["customer_address"] = autofill["customer_address"]
        if autofill.get("shipping_address_name"):
            quotation_payload["shipping_address_name"] = autofill["shipping_address_name"]

        quotation_doc = frappe.get_doc(quotation_payload)
        quotation_doc.insert(ignore_permissions=True)
        # Deliberately do NOT submit. Staff finishes pricing in Desk and submits
        # there. docstatus stays 0 ("Draft").

        # Back-link onto the Robot Quote Request.
        qr.db_set("erpnext_quotation", quotation_doc.name, update_modified=False)
        qr.db_set("quotation_status", "Draft", update_modified=False)
        qr.db_set(
            "proposal_amount_usd",
            float(quotation_doc.grand_total or 0),
            update_modified=False,
        )
        frappe.db.commit()
    except frappe.ValidationError as e:
        return err("VALIDATION_ERROR", str(e))
    except Exception as e:
        frappe.log_error(
            title="convert_quote_request_to_quotation error",
            message=f"qr={name}\n{e}",
        )
        return err("SERVER_ERROR", _("Could not create the Quotation."))

    return ok({
        "quotation_id": quotation_doc.name,
        "status": quotation_doc.status or "Draft",
        "grand_total_usd": float(quotation_doc.grand_total or 0),
        # Surface what we autofilled so the Desk client-script / future
        # admin tooling can confirm the assignment without re-querying.
        "autofill": autofill,
    })


def _resolve_quotation_autofill(qr) -> dict:
    """Phase 7A.1 -- compute contact_person, customer_address,
    shipping_address_name for a fresh Quotation built from a Robot Quote
    Request. Returns a dict with whichever fields could be resolved; missing
    keys mean "leave the Quotation field empty so staff can fill it in Desk".
    Never raises -- any lookup error is logged and treated as "no data".
    """
    out: dict = {}
    try:
        # ---- contact_person ----
        # Prefer the Contact already linked on the Robot Quote Request, then
        # fall back to looking up the Customer's primary Contact (Frappe
        # stores this on Contact via Dynamic Link + is_primary flag).
        contact_name = qr.contact
        if not contact_name and qr.customer:
            row = frappe.db.sql(
                """
                SELECT c.name
                  FROM `tabContact` c
                  JOIN `tabDynamic Link` dl
                    ON dl.parent = c.name
                   AND dl.parenttype = 'Contact'
                   AND dl.link_doctype = 'Customer'
                   AND dl.link_name = %s
                 ORDER BY c.is_primary_contact DESC, c.modified DESC
                 LIMIT 1
                """,
                (qr.customer,),
            )
            contact_name = row[0][0] if row else None
        if contact_name and frappe.db.exists("Contact", contact_name):
            out["contact_person"] = contact_name

        # ---- customer_address (billing/default) + shipping_address_name ----
        if qr.customer:
            from iranrobot_backend.api.account import (
                get_default_customer_address,
                get_shipping_customer_address,
            )
            billing = get_default_customer_address(qr.customer)
            shipping = get_shipping_customer_address(qr.customer)
            if billing and billing.get("name"):
                out["customer_address"] = billing["name"]
            if shipping and shipping.get("name"):
                out["shipping_address_name"] = shipping["name"]
    except Exception as e:
        # Never block conversion on autofill failure.
        frappe.log_error(
            title="quotation autofill resolution error",
            message=f"qr={qr.name}\n{e}",
        )
    return out


# ---------------------------------------------------------------------------
# Phase 7A -- Quotation -> Robot Quote Request sync (doc_events)
# ---------------------------------------------------------------------------
#
# Registered in hooks.py under doc_events. Keeps `quotation_status` and
# `proposal_amount_usd` on the Robot Quote Request in sync with the linked
# Quotation as staff edits it in Desk.

def sync_quotation_back_to_quote_request(doc, method=None):
    """Re-sync the back-linked Robot Quote Request's quotation fields.

    Called on Quotation.on_update, Quotation.on_submit, Quotation.on_cancel.
    Silently no-ops if no back-link exists, so the hook is safe to register
    on every Quotation in the system.

    Phase 7B safety: once the customer has Accepted or Rejected via the React
    dashboard, we DO NOT overwrite the customer-driven `quotation_status` from
    a subsequent staff edit on the Quotation in Desk -- doing so would erase
    the customer's response from view. The proposal_amount_usd is still kept
    in sync (it's a snapshot, not a decision).
    """
    try:
        qr_row = frappe.db.get_value(
            "Robot Quote Request",
            {"erpnext_quotation": doc.name},
            ["name", "customer_response"],
            as_dict=True,
        )
        if not qr_row:
            return
        qr_name = qr_row.name
        already_responded = (qr_row.customer_response or "").strip() in ("Accepted", "Rejected")

        # Map the ERPNext status into our customer-facing taxonomy. We treat
        # any unknown status as 'Sent' (the safest "staff issued something")
        # rather than leaving the value stale.
        erp_status = (doc.status or "").strip()
        mapped = _QUOTATION_STATUS_FROM_ERPNEXT.get(erp_status, "Sent")

        updates: dict = {"proposal_amount_usd": float(doc.grand_total or 0)}
        if not already_responded:
            updates["quotation_status"] = mapped

        frappe.db.set_value(
            "Robot Quote Request", qr_name,
            updates,
            update_modified=False,
        )
    except Exception as e:
        # Never let a sync failure block the underlying Quotation save.
        frappe.log_error(
            title="sync_quotation_back_to_quote_request error",
            message=f"quotation={doc.name}\n{e}",
        )


# ---------------------------------------------------------------------------
# Phase 7B -- customer-side Accept / Reject quotation
# ---------------------------------------------------------------------------
#
# A customer with a Sent ERPNext Quotation can accept or reject it from the
# React dashboard. No Sales Order is created and the ERPNext Quotation's
# docstatus is left alone -- we only record the customer's decision on the
# Robot Quote Request so Sales can see it in Desk and decide what to do next
# (Phase 7C will surface conversion-to-Sales-Order).

# The two actions the React UI may dispatch.
_RESPONSE_ACTIONS = ("accept", "reject")

# Quotation statuses that mean "the customer may now respond". We deliberately
# exclude Draft (staff still finalizing) and the post-response states.
_RESPONDABLE_QUOTATION_STATUSES = {"Sent"}

# Maximum allowed length for the customer's optional rejection / acceptance
# note. Stays well under the Small Text 140-char-or-less convention.
_MAX_RESPONSE_NOTE_LEN = 2000


def _can_customer_respond(qr_dict: dict) -> bool:
    """Pure-data predicate -- safe to call from `get_my_request_detail`. The
    server re-checks each gate again inside `respond_to_quotation`, so a stale
    cached `true` cannot turn into an unauthorized write."""
    if not qr_dict.get("erpnext_quotation"):
        return False
    if (qr_dict.get("quotation_status") or "").strip() not in _RESPONDABLE_QUOTATION_STATUSES:
        return False
    if (qr_dict.get("customer_response") or "").strip():
        return False
    return True


def _client_ip() -> str:
    """Best-effort IP for audit. Truncated to fit ERPNext's Data field cap."""
    try:
        req = getattr(frappe.local, "request", None)
        if req is None:
            return ""
        # Honour the standard X-Forwarded-For when behind a proxy.
        xff = req.headers.get("X-Forwarded-For")
        if xff:
            return (xff.split(",")[0] or "").strip()[:140]
        return (req.remote_addr or "")[:140]
    except Exception:
        return ""


@frappe.whitelist(allow_guest=True, methods=["POST"])
def respond_to_quotation(
    name: str | None = None,
    action: str | None = None,
    note: str | None = None,
):
    """Record a customer Accept/Reject on a Robot Quote Request's linked Quotation.

    Auth: customer must own the Robot Quote Request (Phase 6
    `_record_belongs_to_user` check). Guests return AUTH_REQUIRED via our
    envelope rather than Frappe's bare 403 so the SPA can render a useful
    message.

    State machine:
        quotation_status=Sent + customer_response='' -> accept | reject
        anything else                                  -> rejected with a code
    """
    if is_guest():
        return err("AUTH_REQUIRED", _("You must be logged in."))

    user_email = frappe.session.user
    target = (name or "").strip()
    if not target:
        return err("VALIDATION_ERROR", _("Quote Request name is required."))

    act = (action or "").strip().lower()
    if act not in _RESPONSE_ACTIONS:
        return err("INVALID_ACTION", _("Action must be 'accept' or 'reject'."))

    # Ownership: 404 (not 403) on cross-customer to avoid existence leak.
    cust_id = None
    try:
        _contact_id, cust_id = get_or_create_customer_for_user(user_email)
    except Exception as e:
        frappe.log_error(title="respond_to_quotation lookup", message=f"user={user_email}\n{e}")

    if not frappe.db.exists("Robot Quote Request", target):
        return err("NOT_FOUND", _("Quote Request not found."))
    if not _record_belongs_to_user("Robot Quote Request", target, user_email, cust_id):
        return err("NOT_FOUND", _("Quote Request not found."))

    qr = frappe.get_doc("Robot Quote Request", target)

    # Must have a linked Quotation.
    if not qr.erpnext_quotation:
        return err("QUOTATION_NOT_FOUND", _("This Quote Request has no linked Quotation."))
    if not frappe.db.exists("Quotation", qr.erpnext_quotation):
        return err("QUOTATION_NOT_FOUND", _("Linked Quotation no longer exists."))

    # ALREADY_RESPONDED takes priority over QUOTATION_NOT_READY: once we've
    # recorded the customer's decision (which also flips quotation_status to
    # Accepted/Rejected), the more informative error is "you already
    # responded" rather than "the quotation is not in Sent state".
    if (qr.customer_response or "").strip():
        return err(
            "ALREADY_RESPONDED",
            _("You have already responded to this Quotation ({0}).").format(qr.customer_response),
        )

    # Customer can only act on a Sent Quotation (NOT Draft -- staff still
    # finalizing -- and NOT post-response states reachable via staff edits).
    current_status = (qr.quotation_status or "").strip()
    if current_status not in _RESPONDABLE_QUOTATION_STATUSES:
        return err(
            "QUOTATION_NOT_READY",
            _("This Quotation is not yet ready for your response (status: {0}).").format(
                current_status or "Draft"
            ),
        )

    # Customer-supplied note: trim, normalize Persian digits, cap length.
    note_norm = _norm(note, _MAX_RESPONSE_NOTE_LEN).translate(_PERSIAN_DIGITS)

    # Apply the decision. Use db.set_value (not doc.save) for two reasons:
    #   * read-only fields are honoured by save() but db_set bypasses cleanly
    #   * we don't want to run the parent's validate() on these audit fields
    # We update `customer_response` first; if anything raises, the
    # `_already_responded` guard at the top of the sync hook still treats this
    # as "in-progress" rather than blocking future syncs.
    new_status = "Accepted" if act == "accept" else "Rejected"
    response_ts = frappe.utils.now_datetime()
    try:
        frappe.db.set_value(
            "Robot Quote Request",
            qr.name,
            {
                "customer_response": new_status,
                "customer_response_at": response_ts,
                "customer_response_user": user_email,
                "customer_response_note": note_norm,
                "customer_response_ip": _client_ip(),
                "quotation_status": new_status,
            },
            update_modified=True,
        )
        frappe.db.commit()
    except frappe.ValidationError as e:
        return err("VALIDATION_ERROR", str(e))
    except Exception as e:
        frappe.log_error(title="respond_to_quotation server error", message=f"qr={target}\n{e}")
        return err("SERVER_ERROR", _("Could not record your response."))

    return ok({
        "request_id": qr.name,
        "quotation_status": new_status,
        "customer_response": new_status,
        "customer_response_at": str(response_ts),
        "customer_response_note": note_norm,
    })


# ---------------------------------------------------------------------------
# Phase 7C -- Accepted Quotation -> ERPNext Sales Order
# ---------------------------------------------------------------------------
#
# Staff trigger this from a Desk button on Robot Quote Request once the
# customer has Accepted the linked Quotation. We delegate the heavy lifting to
# ERPNext's native `make_sales_order` mapper -- it builds an SO from a
# Quotation via `frappe.model.mapper.get_mapped_doc` with the right field
# map, runs `set_missing_values` + `calculate_taxes_and_totals`, and copies
# customer + address + contact + items + currency + selling price list. We
# only validate ownership / state and back-write the link.

# Acceptable customer-facing quotation_status values that allow conversion.
_SO_CONVERTIBLE_QUOTATION_STATUSES = {"Accepted"}


@frappe.whitelist(methods=["POST"])
def convert_accepted_quote_to_sales_order(name: str | None = None):
    """Create a Draft ERPNext Sales Order from an Accepted Robot Quote Request.

    Auth: Sales User / Sales Manager / System Manager only. Customers cannot
    call this -- they have no way to flip a Quote Request into Sales Order
    state on their own.
    """
    if is_guest():
        return err("AUTH_REQUIRED", _("You must be logged in."))

    user_email = frappe.session.user
    if not _has_sales_role(user_email):
        return err(
            "NOT_PERMITTED",
            _("Only Sales staff can convert an accepted Quote Request to a Sales Order."),
        )

    if not name:
        return err("VALIDATION_ERROR", _("Robot Quote Request name is required."))
    if not frappe.db.exists("Robot Quote Request", name):
        return err("NOT_FOUND", _("Robot Quote Request not found."))

    qr = frappe.get_doc("Robot Quote Request", name)

    if qr.erpnext_sales_order:
        return err(
            "ALREADY_CONVERTED",
            _("A Sales Order ({0}) has already been created from this Quote Request.").format(
                qr.erpnext_sales_order
            ),
        )

    if not qr.erpnext_quotation:
        return err(
            "QUOTATION_NOT_FOUND",
            _("This Quote Request has no linked Quotation; convert it to a Quotation first."),
        )
    if not frappe.db.exists("Quotation", qr.erpnext_quotation):
        return err("QUOTATION_NOT_FOUND", _("Linked Quotation no longer exists."))

    # ERPNext's make_sales_order helper requires docstatus=1 on the source
    # Quotation (its `get_mapped_doc` table_map asserts this). Translate that
    # internal requirement into a clean app-level error code so staff knows to
    # Submit the Quotation in Desk first.
    quotation_docstatus = frappe.db.get_value("Quotation", qr.erpnext_quotation, "docstatus")
    if quotation_docstatus != 1:
        return err(
            "QUOTATION_NOT_SUBMITTED",
            _("The linked Quotation is in Draft. Submit it in Desk before converting to a Sales Order."),
        )

    # State gate: customer must have Accepted AND the QR's quotation_status
    # must reflect that. We check both so a staff-side edit that leaves
    # customer_response='Accepted' while flipping quotation_status to something
    # else is treated as "not ready" -- the cleaner answer is to investigate
    # the discrepancy in Desk before converting.
    customer_response = (qr.customer_response or "").strip()
    quotation_status = (qr.quotation_status or "").strip()
    if customer_response != "Accepted" or quotation_status not in _SO_CONVERTIBLE_QUOTATION_STATUSES:
        return err(
            "QUOTATION_NOT_ACCEPTED",
            _("This Quotation has not been accepted by the customer (current state: {0}).").format(
                customer_response or quotation_status or "unknown"
            ),
        )

    # Delegate to ERPNext's canonical mapper -- it handles the customer link,
    # the items (qty / rate / uom / description), taxes-totals recompute, and
    # address/contact copy. We catch the `valid_till expired` throw and
    # surface a clean error.
    try:
        from erpnext.selling.doctype.quotation.quotation import _make_sales_order
        so_doc = _make_sales_order(
            qr.erpnext_quotation,
            target_doc=None,
            ignore_permissions=True,
        )
        # ERPNext does not set delivery_date for Quotation-mapped Sales Orders.
        # The SO controller validates delivery_date is set when at least one
        # line has stock; default to today+14 days so the insert succeeds in
        # Draft state. Staff edits this freely in Desk before submitting.
        if not so_doc.delivery_date:
            so_doc.delivery_date = frappe.utils.add_days(frappe.utils.today(), 14)
        for it in so_doc.items:
            if not it.delivery_date:
                it.delivery_date = so_doc.delivery_date
        so_doc.flags.ignore_permissions = True
        so_doc.insert(ignore_permissions=True)
        # Leave docstatus=0 (Draft). Staff submits in Desk.

        created_at = frappe.utils.now_datetime()
        qr.db_set("erpnext_sales_order", so_doc.name, update_modified=False)
        qr.db_set("sales_order_status", so_doc.status or "Draft", update_modified=False)
        qr.db_set(
            "sales_order_grand_total_usd",
            float(so_doc.grand_total or 0),
            update_modified=False,
        )
        qr.db_set("sales_order_created_at", created_at, update_modified=False)
        frappe.db.commit()
    except frappe.ValidationError as e:
        # Quotation valid_till expired, or some line item failed validation.
        return err("VALIDATION_ERROR", str(e))
    except Exception as e:
        frappe.log_error(
            title="convert_accepted_quote_to_sales_order error",
            message=f"qr={name} qid={qr.erpnext_quotation}\n{e}",
        )
        return err("SALES_ORDER_CREATION_FAILED", _("Could not create the Sales Order."))

    return ok({
        "sales_order_id": so_doc.name,
        "status": so_doc.status or "Draft",
        "grand_total_usd": float(so_doc.grand_total or 0),
    })


def sync_sales_order_back_to_quote_request(doc, method=None):
    """Phase 7C -- doc_events handler for Sales Order on_update/on_submit/
    on_cancel. Keeps Robot Quote Request.sales_order_status + grand_total in
    sync without touching the customer-driven response state. Silently no-ops
    when no Robot Quote Request back-links to this Sales Order.
    """
    try:
        qr_name = frappe.db.get_value(
            "Robot Quote Request",
            {"erpnext_sales_order": doc.name},
            "name",
        )
        if not qr_name:
            return
        frappe.db.set_value(
            "Robot Quote Request", qr_name,
            {
                "sales_order_status": doc.status or "Draft",
                "sales_order_grand_total_usd": float(doc.grand_total or 0),
            },
            update_modified=False,
        )
    except Exception as e:
        frappe.log_error(
            title="sync_sales_order_back_to_quote_request error",
            message=f"so={doc.name}\n{e}",
        )


# ---------------------------------------------------------------------------
# Phase 7D -- Sales Order -> ERPNext Sales Invoice + Payment Entry visibility
# ---------------------------------------------------------------------------
#
# Staff triggers this from a Desk button on Robot Quote Request once they're
# ready to bill. We delegate to ERPNext's native `make_sales_invoice` mapper
# from `erpnext/selling/doctype/sales_order/sales_order.py`. The new Sales
# Invoice is left in Draft -- staff finishes review and submits in Desk.
#
# Payment Entry is NEVER created here; staff records it manually in Desk via
# ERPNext's standard flow. We only listen for `Payment Entry` doc_events to
# bubble the latest PE name + a derived payment_status onto the Robot Quote
# Request so the customer dashboard can show "Paid", "Partly Paid", etc.

# ERPNext Sales Invoice statuses that mean "customer needs to know about
# payment progress". Anything else (Draft / Return / Credit Note Issued)
# also maps cleanly; see _derive_payment_status() below.
_PAYMENT_STATUS_FROM_INVOICE = {
    "Paid": "Paid",
    "Partly Paid": "Partly Paid",
    "Partly Paid and Discounted": "Partly Paid",
    "Unpaid": "Unpaid",
    "Unpaid and Discounted": "Unpaid",
    "Overdue": "Overdue",
    "Overdue and Discounted": "Overdue",
    "Cancelled": "Cancelled",
}


def _derive_payment_status(si_doc) -> str:
    """Project ERPNext Sales Invoice state into the 5-value customer-facing
    payment_status enum used on the QR + the React dashboard."""
    erp_status = (si_doc.status or "").strip()
    if erp_status in _PAYMENT_STATUS_FROM_INVOICE:
        return _PAYMENT_STATUS_FROM_INVOICE[erp_status]
    # ERPNext docstatus: 0=Draft, 1=Submitted, 2=Cancelled
    if si_doc.docstatus == 2:
        return "Cancelled"
    if si_doc.docstatus == 0:
        return "Unpaid"
    # Submitted but status didn't match the map (e.g. "Return"). Fall back to
    # outstanding-vs-grand-total heuristic.
    grand_total = float(si_doc.grand_total or 0)
    outstanding = float(si_doc.outstanding_amount or 0)
    if grand_total <= 0:
        return "Paid"
    if outstanding <= 0:
        return "Paid"
    if outstanding < grand_total:
        return "Partly Paid"
    return "Unpaid"


@frappe.whitelist(methods=["POST"])
def convert_sales_order_to_sales_invoice(name: str | None = None):
    """Create a Draft ERPNext Sales Invoice from a Robot Quote Request whose
    Sales Order has been Submitted.

    Auth: Sales User / Sales Manager / Accounts User / Accounts Manager /
    System Manager. Customers cannot call this. Staff finishes editing the
    Sales Invoice in Desk and submits there; Payment Entry is recorded
    manually using ERPNext's standard flow.
    """
    if is_guest():
        return err("AUTH_REQUIRED", _("You must be logged in."))

    user_email = frappe.session.user
    if not _has_invoice_role(user_email):
        return err(
            "NOT_PERMITTED",
            _("Only Sales / Accounts staff can create a Sales Invoice."),
        )

    if not name:
        return err("VALIDATION_ERROR", _("Robot Quote Request name is required."))
    if not frappe.db.exists("Robot Quote Request", name):
        return err("NOT_FOUND", _("Robot Quote Request not found."))

    qr = frappe.get_doc("Robot Quote Request", name)

    if qr.erpnext_sales_invoice:
        return err(
            "ALREADY_INVOICED",
            _("A Sales Invoice ({0}) has already been created from this Quote Request.").format(
                qr.erpnext_sales_invoice
            ),
        )

    if not qr.erpnext_sales_order:
        return err(
            "SALES_ORDER_REQUIRED",
            _("This Quote Request has no linked Sales Order; convert it first."),
        )
    if not frappe.db.exists("Sales Order", qr.erpnext_sales_order):
        return err("SALES_ORDER_NOT_FOUND", _("Linked Sales Order no longer exists."))

    so_docstatus = frappe.db.get_value("Sales Order", qr.erpnext_sales_order, "docstatus")
    if so_docstatus != 1:
        return err(
            "SALES_ORDER_NOT_SUBMITTED",
            _("The linked Sales Order is in Draft. Submit it in Desk before invoicing."),
        )

    try:
        from erpnext.selling.doctype.sales_order.sales_order import make_sales_invoice
        si_doc = make_sales_invoice(
            qr.erpnext_sales_order,
            target_doc=None,
            ignore_permissions=True,
        )
        si_doc.flags.ignore_permissions = True
        si_doc.insert(ignore_permissions=True)
        # Deliberately do NOT submit. Staff finishes review (tax codes, due
        # date, accounting period) and submits in Desk.

        created_at = frappe.utils.now_datetime()
        qr.db_set("erpnext_sales_invoice", si_doc.name, update_modified=False)
        qr.db_set("sales_invoice_status", si_doc.status or "Draft", update_modified=False)
        qr.db_set(
            "sales_invoice_grand_total_usd",
            float(si_doc.grand_total or 0),
            update_modified=False,
        )
        qr.db_set(
            "sales_invoice_outstanding_amount_usd",
            float(si_doc.outstanding_amount or si_doc.grand_total or 0),
            update_modified=False,
        )
        qr.db_set("sales_invoice_created_at", created_at, update_modified=False)
        qr.db_set("payment_status", _derive_payment_status(si_doc), update_modified=False)
        frappe.db.commit()
    except frappe.ValidationError as e:
        return err("VALIDATION_ERROR", str(e))
    except Exception as e:
        frappe.log_error(
            title="convert_sales_order_to_sales_invoice error",
            message=f"qr={name} so={qr.erpnext_sales_order}\n{e}",
        )
        return err("SALES_INVOICE_CREATION_FAILED", _("Could not create the Sales Invoice."))

    return ok({
        "sales_invoice_id": si_doc.name,
        "status": si_doc.status or "Draft",
        "grand_total_usd": float(si_doc.grand_total or 0),
        "outstanding_amount_usd": float(si_doc.outstanding_amount or si_doc.grand_total or 0),
    })


_INVOICE_ROLES = (
    "System Manager",
    "Sales User",
    "Sales Manager",
    "Accounts User",
    "Accounts Manager",
)


def _has_invoice_role(user_email: str | None) -> bool:
    if not user_email or user_email == "Guest":
        return False
    if user_email == "Administrator":
        return True
    roles = set(frappe.get_roles(user_email) or [])
    return bool(roles.intersection(_INVOICE_ROLES))


def sync_sales_invoice_back_to_quote_request(doc, method=None):
    """Phase 7D -- doc_events handler for Sales Invoice on_update / on_submit /
    on_cancel. Keeps the QR's invoice snapshot fields in sync. Never touches
    customer_response, quotation_status, sales_order_status, or any other
    upstream phase's state.
    """
    try:
        qr_name = frappe.db.get_value(
            "Robot Quote Request",
            {"erpnext_sales_invoice": doc.name},
            "name",
        )
        if not qr_name:
            return
        frappe.db.set_value(
            "Robot Quote Request", qr_name,
            {
                "sales_invoice_status": doc.status or "Draft",
                "sales_invoice_grand_total_usd": float(doc.grand_total or 0),
                "sales_invoice_outstanding_amount_usd": float(doc.outstanding_amount or 0),
                "payment_status": _derive_payment_status(doc),
            },
            update_modified=False,
        )
    except Exception as e:
        frappe.log_error(
            title="sync_sales_invoice_back_to_quote_request error",
            message=f"si={doc.name}\n{e}",
        )


def sync_payment_entry_back_to_quote_request(doc, method=None):
    """Phase 7D -- doc_events handler for Payment Entry on_submit / on_cancel.

    Walks the PE's `references` child table to find any Sales Invoice that's
    back-linked from a Robot Quote Request; if found, records the PE as the
    Robot Quote Request's `latest_payment_entry`, refreshes the SI snapshot
    fields (outstanding decreases when a PE is submitted), and re-derives
    payment_status. Silently no-ops when no SI in the references chain is
    back-linked to any of our Quote Requests.
    """
    try:
        # Inspect every reference row that points at a Sales Invoice.
        for ref in (doc.references or []):
            if ref.reference_doctype != "Sales Invoice":
                continue
            if not ref.reference_name:
                continue
            qr_name = frappe.db.get_value(
                "Robot Quote Request",
                {"erpnext_sales_invoice": ref.reference_name},
                "name",
            )
            if not qr_name:
                continue
            # Reload the linked Sales Invoice -- ERPNext updates its
            # outstanding_amount + status on PE submission, but doc_events on
            # Payment Entry fire BEFORE the SI sync inside ERPNext's
            # `update_outstanding_amt` runs to completion; we re-pull the
            # fresh values via get_doc to be safe.
            si = frappe.get_doc("Sales Invoice", ref.reference_name)
            frappe.db.set_value(
                "Robot Quote Request", qr_name,
                {
                    "latest_payment_entry": doc.name,
                    "sales_invoice_status": si.status or "Draft",
                    "sales_invoice_grand_total_usd": float(si.grand_total or 0),
                    "sales_invoice_outstanding_amount_usd": float(si.outstanding_amount or 0),
                    "payment_status": _derive_payment_status(si),
                },
                update_modified=False,
            )
    except Exception as e:
        frappe.log_error(
            title="sync_payment_entry_back_to_quote_request error",
            message=f"pe={getattr(doc, 'name', '?')}\n{e}",
        )
