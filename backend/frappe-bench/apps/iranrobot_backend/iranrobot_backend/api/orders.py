"""Phase 7C -- Customer-facing Sales Order read APIs.

    iranrobot_backend.api.orders.get_my_orders        GET   auth required
    iranrobot_backend.api.orders.get_my_order_detail  GET   auth required

Ownership model mirrors Phase 6: the customer can only see Sales Orders
linked to their ERPNext Customer (resolved via the Phase 4 lazy-creation
helper). Cross-customer access returns NOT_FOUND (not 403) so the record-id
namespace can't be enumerated by guessing.

Field projection is strict:
    - No cost / margin / valuation columns.
    - No `base_*` company-currency snapshots.
    - No taxes child table.
    - No address text dump (only optional address NAMES, which the customer
      already owns via Phase 7A.1 -- they can pull the body via that API).
    - No internal notes, no audit fields, no owner / modified_by.
"""

from __future__ import annotations

import frappe
from frappe import _

from iranrobot_backend.api._response import err, ok
from iranrobot_backend.api._session import (
    get_or_create_customer_for_user,
    is_guest,
)


# Allow-list -- both list and detail. Keep it tight; expand only when an
# explicit customer-facing need is identified.
_SO_LIST_FIELDS = (
    "name",
    "status",
    "transaction_date",
    "delivery_date",
    "customer_name",
    "grand_total",
    "currency",
    "creation",
)

_SO_DETAIL_FIELDS = (
    "name",
    "status",
    "transaction_date",
    "delivery_date",
    "customer_name",
    "grand_total",
    "total",
    "net_total",
    "currency",
    "po_no",
    "creation",
    "modified",
)

_SO_ITEM_DETAIL_FIELDS = (
    "idx",
    "item_code",
    "item_name",
    "description",
    "qty",
    "uom",
    "rate",
    "amount",
)


def _project(doc: dict, allow_list: tuple) -> dict:
    return {k: doc.get(k) for k in allow_list if k in doc}


def _resolve_customer() -> str | None:
    """Return the ERPNext Customer for the session user, or None for guests /
    staff users who have no Customer record."""
    if is_guest():
        return None
    try:
        _contact_id, cust_id = get_or_create_customer_for_user(frappe.session.user)
        return cust_id
    except Exception as e:
        frappe.log_error(title="orders._resolve_customer", message=str(e))
        return None


def _so_back_links(so_name: str) -> dict:
    """Best-effort look-up: does any Robot Quote Request back-link to this SO?
    If so, surface the QR name + linked Quotation so the customer can pivot
    back to the conversation that started this order."""
    row = frappe.db.get_value(
        "Robot Quote Request",
        {"erpnext_sales_order": so_name},
        ["name", "erpnext_quotation"],
        as_dict=True,
    )
    if not row:
        return {}
    return {
        "linked_quote_request": row.name,
        "linked_quotation": row.erpnext_quotation,
    }


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_my_orders(limit: int = 20):
    """Return the current customer's Sales Orders (customer-safe projection).

    `allow_guest=True` so Frappe doesn't return a bare 403 -- we send our
    AUTH_REQUIRED envelope from the body. Staff users without a Customer
    record get an empty list (not an error) so the React UI can render the
    empty state cleanly.
    """
    if is_guest():
        return err("AUTH_REQUIRED", _("You must be logged in."))

    cust_id = _resolve_customer()
    if not cust_id:
        return ok({"orders": []})

    try:
        limit_n = max(1, min(int(limit), 100))
    except (TypeError, ValueError):
        limit_n = 20

    try:
        rows = frappe.get_all(
            "Sales Order",
            filters={"customer": cust_id},
            fields=list(_SO_LIST_FIELDS),
            order_by="transaction_date desc, creation desc",
            limit_page_length=limit_n,
            ignore_permissions=True,
        )
    except Exception as e:
        frappe.log_error(title="get_my_orders list", message=str(e))
        return err("SERVER_ERROR", _("Could not load your orders."))

    # Enrich with `items_count` + the back-link to the originating Quote
    # Request / Quotation when present. Two lightweight extra queries per row
    # is acceptable at the typical < 50-orders-per-customer scale; we can
    # batch later if usage proves heavier.
    enriched: list[dict] = []
    for r in rows:
        try:
            items_count = frappe.db.count(
                "Sales Order Item",
                {"parent": r["name"], "parenttype": "Sales Order"},
            )
        except Exception:
            items_count = 0
        record = _project(r, _SO_LIST_FIELDS)
        record["items_count"] = items_count
        record.update(_so_back_links(r["name"]))
        enriched.append(record)
    return ok({"orders": enriched})


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_my_order_detail(name: str | None = None):
    """Fetch a single Sales Order owned by the current customer.

    Cross-customer access returns NOT_FOUND.
    """
    if is_guest():
        return err("AUTH_REQUIRED", _("You must be logged in."))

    if not name:
        return err("VALIDATION_ERROR", _("Order name is required."))

    cust_id = _resolve_customer()
    if not cust_id:
        # Mirror Phase 6's existence-leak guard. Staff / users without a
        # Customer record can't read order detail through this surface.
        return err("NOT_FOUND", _("Order not found."))

    if not frappe.db.exists("Sales Order", name):
        return err("NOT_FOUND", _("Order not found."))

    so_customer = frappe.db.get_value("Sales Order", name, "customer")
    if so_customer != cust_id:
        return err("NOT_FOUND", _("Order not found."))

    try:
        doc = frappe.get_doc("Sales Order", name)
    except Exception as e:
        frappe.log_error(title="get_my_order_detail load", message=str(e))
        return err("SERVER_ERROR", _("Could not load the order."))

    as_dict = doc.as_dict()
    payload = _project(as_dict, _SO_DETAIL_FIELDS)
    payload["items"] = [
        _project(row, _SO_ITEM_DETAIL_FIELDS)
        for row in (as_dict.get("items") or [])
    ]
    payload.update(_so_back_links(name))
    return ok({"record": payload})
