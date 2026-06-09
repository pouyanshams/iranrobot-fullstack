"""Phase 5 development helper -- a few one-shot checks invoked through
`bench execute iranrobot_backend.commands._phase5_smoke.<name>`.

Not intended for production use."""

import frappe


def check_tables():
    for dt in ["Robot Quote Request", "Robot Quote Request Item", "Robot Procurement Request"]:
        tbl = f"tab{dt}"
        try:
            cnt = frappe.db.sql(f"SELECT COUNT(*) FROM `{tbl}`")[0][0]
            print(f"{tbl}: {cnt} rows")
        except Exception as e:
            print(f"{tbl}: ERROR -- {type(e).__name__}: {e}")


def list_recent_requests():
    """Quick visibility into recently-submitted records (dev only)."""
    print("Quote Requests:")
    for r in frappe.get_all(
        "Robot Quote Request",
        fields=["name", "customer", "customer_name", "status", "submitted_at"],
        order_by="creation desc",
        limit=10,
    ):
        print(f"  {r.name}  customer={r.customer or 'GUEST'}  status={r.status}  at={r.submitted_at}")
    print("\nProcurement Requests:")
    for r in frappe.get_all(
        "Robot Procurement Request",
        fields=["name", "customer", "contact_name", "status", "submitted_at"],
        order_by="creation desc",
        limit=10,
    ):
        print(f"  {r.name}  customer={r.customer or 'GUEST'}  status={r.status}  at={r.submitted_at}")
    print("\nIssues (from website):")
    for r in frappe.get_all(
        "Issue",
        filters={"raised_by_email": ["is", "set"]},
        fields=["name", "subject", "status", "customer", "raised_by"],
        order_by="creation desc",
        limit=10,
    ):
        print(f"  {r.name}  status={r.status}  customer={r.customer or 'GUEST'}  raised_by={r.raised_by}")


def verify_linkages():
    """Verify Phase 5 records linked properly to ERPNext Customer/Contact/Item."""
    # Most recent logged-in quote
    quotes = frappe.get_all(
        "Robot Quote Request",
        filters={"user_email": "customer1@example.com"},
        order_by="creation desc",
        limit=1,
    )
    if not quotes:
        print("No logged-in quote requests found")
        return
    q = frappe.get_doc("Robot Quote Request", quotes[0].name)
    print(f"Quote {q.name}:")
    print(f"  customer       = {q.customer}")
    print(f"  contact        = {q.contact}")
    print(f"  user_email     = {q.user_email}")
    print(f"  customer_name  = {q.customer_name}")
    print(f"  total_estimate = ${q.total_estimate_usd:.2f}" if q.total_estimate_usd else "  total_estimate = $0")
    print(f"  items ({len(q.items)}):")
    for it in q.items:
        print(f"    - {it.product_name}  qty={it.quantity}  mode={it.mode}  "
              f"robot_product={it.robot_product}  erpnext_item={it.erpnext_item}  "
              f"unit=${it.unit_price_usd or 0}  line=${it.line_total_usd or 0}")

    # Most recent logged-in procurement
    procs = frappe.get_all(
        "Robot Procurement Request",
        filters={"user_email": "customer1@example.com"},
        order_by="creation desc",
        limit=1,
    )
    if procs:
        p = frappe.get_doc("Robot Procurement Request", procs[0].name)
        print(f"\nProcurement {p.name}:")
        print(f"  customer     = {p.customer}")
        print(f"  contact      = {p.contact}")
        print(f"  user_email   = {p.user_email}")
        print(f"  product_name = {p.product_name}")

    # Most recent logged-in issue
    issues = frappe.get_all(
        "Issue",
        filters={"raised_by": "customer1@example.com"},
        order_by="creation desc",
        limit=1,
    )
    if issues:
        i = frappe.get_doc("Issue", issues[0].name)
        print(f"\nIssue {i.name}:")
        print(f"  customer   = {i.customer}")
        print(f"  contact    = {i.contact}")
        print(f"  raised_by  = {i.raised_by}")
        print(f"  subject    = {i.subject}")
        print(f"  status     = {i.status}")
