"""Phase 8D-1 -- Backfill approved wallet top-ups into ERPNext Payment Entry.

For every `Robot Wallet Top Up Request` row with status=Approved and an
empty `linked_payment_entry`, create + submit a Payment Entry using the
proven Test A top-up pattern from the 8D-0 spike, and link it on the
Top Up Request.

Defaults to a dry-run so accidental invocations don't post GL entries::

    # safe dry-run (default)
    bench --site iranrobot.localhost execute \\
        iranrobot_backend.commands.wallet_accounting_backfill.run

    # commit changes
    bench --site iranrobot.localhost execute \\
        iranrobot_backend.commands.wallet_accounting_backfill.run \\
        --kwargs '{"dry_run": false}'

Idempotency: a Payment Entry that already matches the top-up (same
`reference_no`, party, `paid_from`) is reused, not duplicated. Re-running
the backfill is therefore safe.

Guard: refuses to run on any site other than `iranrobot.localhost`.
"""

from __future__ import annotations

import json

import frappe

from iranrobot_backend.api import wallet as wallet_api


_ALLOWED_SITE = "iranrobot.localhost"


def _guard_site():
    actual = getattr(frappe.local, "site", None)
    if actual != _ALLOWED_SITE:
        frappe.throw(
            f"wallet_accounting_backfill refuses to run on site {actual!r}. "
            f"Only {_ALLOWED_SITE!r} is allowed (dev guardrail).",
            title="Site guard",
        )


def _emit(payload):
    print("PHASE8D1_BACKFILL::" + json.dumps(payload, default=str))


def _coerce_bool(value, default=True) -> bool:
    """Coerce kwargs to bool. `bench execute --kwargs '{"dry_run": false}'`
    delivers a real boolean; defensive against string forms like "false"."""
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return bool(value)
    s = str(value).strip().lower()
    if s in ("false", "0", "no", "off"):
        return False
    if s in ("true", "1", "yes", "on"):
        return True
    return default


def run(dry_run=True):
    """Backfill missing top-up Payment Entries. Dry-run by default."""
    print("\n=== Phase 8D-1 wallet top-up backfill ===\n")
    _guard_site()
    dry_run = _coerce_bool(dry_run, default=True)

    if not wallet_api._accounting_ready():
        frappe.throw(
            "Wallet accounting setup is missing. Run "
            "`bench execute iranrobot_backend.commands."
            "wallet_accounting_bootstrap.run` first.",
            title="Accounting setup missing",
        )

    rows = frappe.get_all(
        "Robot Wallet Top Up Request",
        filters={
            "status": "Approved",
            "linked_payment_entry": ["in", ["", None]],
        },
        fields=["name", "customer", "amount_usd", "approved_at", "approved_by", "wallet"],
        order_by="creation asc",
    )

    counts = {
        "found": len(rows),
        "would_create": 0,
        "created": 0,
        "linked_existing": 0,
        "failed": 0,
    }

    print(f"Found {len(rows)} Approved top-ups with no linked_payment_entry "
          f"(dry_run={dry_run})\n")

    for r in rows:
        request_name = r["name"]
        customer = r["customer"]
        amount = float(r["amount_usd"] or 0)
        try:
            existing = wallet_api._find_existing_topup_pe(request_name, customer)
            if existing:
                if dry_run:
                    _emit({
                        "step": "would_link_existing",
                        "request": request_name,
                        "pe": existing,
                        "amount_usd": amount,
                    })
                else:
                    frappe.db.set_value(
                        "Robot Wallet Top Up Request",
                        request_name,
                        "linked_payment_entry",
                        existing,
                        update_modified=False,
                    )
                    frappe.db.commit()
                    _emit({
                        "step": "linked_existing",
                        "request": request_name,
                        "pe": existing,
                        "amount_usd": amount,
                    })
                counts["linked_existing"] += 1
                continue

            if dry_run:
                _emit({
                    "step": "would_create_pe",
                    "request": request_name,
                    "customer": customer,
                    "amount_usd": amount,
                })
                counts["would_create"] += 1
                continue

            request_doc = frappe.get_doc("Robot Wallet Top Up Request", request_name)
            pe_name = wallet_api._create_topup_pe(request_doc)
            frappe.db.set_value(
                "Robot Wallet Top Up Request",
                request_name,
                "linked_payment_entry",
                pe_name,
                update_modified=False,
            )
            frappe.db.commit()
            _emit({
                "step": "created_pe",
                "request": request_name,
                "pe": pe_name,
                "amount_usd": amount,
                "customer": customer,
            })
            counts["created"] += 1
        except Exception as e:
            frappe.db.rollback()
            counts["failed"] += 1
            _emit({
                "step": "failed",
                "request": request_name,
                "error": str(e),
                "exception_type": type(e).__name__,
            })

    print(f"\nDone. dry_run={dry_run}")
    print(f"  found            = {counts['found']}")
    print(f"  would_create     = {counts['would_create']}")
    print(f"  created          = {counts['created']}")
    print(f"  linked_existing  = {counts['linked_existing']}")
    print(f"  failed           = {counts['failed']}")
    return counts
