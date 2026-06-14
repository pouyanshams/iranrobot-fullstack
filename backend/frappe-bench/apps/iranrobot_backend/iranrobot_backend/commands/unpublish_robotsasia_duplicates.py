"""SAFE unpublish of high-confidence RobotsAsia duplicate Robot Products.

Approved (by the operator) outcome of the dedup audit: hide the RobotsAsia
imports that duplicate an existing curated seed product, keeping the seed as
canonical. This command ONLY sets `is_published = 0` on the approved RobotsAsia
duplicates that have NO commercial references.

Hard safety rules (defense-in-depth, all enforced per product):
  * product_id MUST start with `robotsasia-` (never touch a seed product).
  * The product must be in the explicit APPROVED list (or an operator-supplied
    subset of it). Anything not on the list is ignored.
  * SKIP any product that has commercial references (quote / order / invoice)
    when require_no_refs is True (default).
  * Only `is_published` is changed. NOTHING is deleted. The ERPNext Item is
    never touched (not unpublished, not disabled, not deleted).
  * Idempotent: re-running reports already-unpublished and makes no change.

Not a public API; no whitelist.

    bench --site iranrobot.localhost execute \\
        iranrobot_backend.commands.unpublish_robotsasia_duplicates.run \\
        --kwargs "{'dry_run': True}"
    bench --site iranrobot.localhost execute \\
        iranrobot_backend.commands.unpublish_robotsasia_duplicates.run \\
        --kwargs "{'dry_run': False}"
"""

import frappe

# Explicit operator-approved list (8 high-confidence, no-ref RobotsAsia dups).
# ubtech-walker-s2 is intentionally EXCLUDED (canonical seed has commercial
# refs -> needs a merge plan). Keenon review cases and all variants excluded.
APPROVED_PRODUCT_IDS = [
    "robotsasia-drone-xag-p150-standard-7kw",
    "robotsasia-humanoid-unitree-g1-basic",
    "robotsasia-quadruped-magiclab-magicdog-w",
    "robotsasia-quadruped-agibot-d1-pro",
    "robotsasia-quadruped-unitree-b1",
    "robotsasia-quadruped-unitree-aliengo",
    "robotsasia-quadruped-unitree-b2",
    "robotsasia-quadruped-unitree-go2-air",
]

DEFAULT_REASON = "robotsasia duplicate of existing curated seed product"


def _commercial_refs(product_id, erpnext_item):
    """Return (refs_dict, has_any). Best-effort, read-only."""
    refs = {}
    try:
        refs["robot_quote_request_item"] = frappe.db.count(
            "Robot Quote Request Item", {"robot_product": product_id}
        )
    except Exception:
        refs["robot_quote_request_item"] = None
    if erpnext_item:
        for dt in ("Quotation Item", "Sales Order Item", "Sales Invoice Item"):
            try:
                refs[dt] = frappe.db.count(dt, {"item_code": erpnext_item})
            except Exception:
                refs[dt] = None
    has_any = any(bool(v) for v in refs.values())
    return refs, has_any


def run(dry_run=True, product_ids=None, reason=DEFAULT_REASON, require_no_refs=True):
    """Unpublish approved RobotsAsia duplicates (is_published=0 only).

    Args:
        dry_run:        when True (default), report only; change nothing.
        product_ids:    optional subset; MUST be within APPROVED_PRODUCT_IDS.
                        None => the full approved list.
        reason:         human-readable note (logged in output; not written to
                        the record since Robot Product has no notes field).
        require_no_refs: when True (default), skip any product with commercial
                        references instead of unpublishing it.
    """
    # Resolve the working list, never widening beyond the approved set.
    if product_ids is None:
        targets = list(APPROVED_PRODUCT_IDS)
    else:
        if isinstance(product_ids, str):
            product_ids = [product_ids]
        targets = [p for p in product_ids if p in APPROVED_PRODUCT_IDS]

    result = {
        "dry_run": bool(dry_run),
        "reason": reason,
        "require_no_refs": bool(require_no_refs),
        "candidates": [],
        "unpublished": [],
        "already_unpublished": [],
        "skipped_with_refs": [],
        "skipped_not_robotsasia": [],
        "missing": [],
        "errors": [],
    }

    for pid in targets:
        try:
            # Guard 1: must be a RobotsAsia product id.
            if not pid.startswith("robotsasia-"):
                result["skipped_not_robotsasia"].append(pid)
                continue
            # Guard 2: must exist.
            if not frappe.db.exists("Robot Product", pid):
                result["missing"].append(pid)
                continue

            row = frappe.db.get_value(
                "Robot Product", pid,
                ["is_published", "erpnext_item", "category", "subcategory"],
                as_dict=True,
            )
            # Guard 3: commercial references => skip (never unpublish).
            refs, has_refs = _commercial_refs(pid, row.erpnext_item)
            if require_no_refs and has_refs:
                result["skipped_with_refs"].append({"product_id": pid, "refs": refs})
                continue

            entry = {
                "product_id": pid,
                "category": row.category,
                "subcategory": row.subcategory,
                "erpnext_item": row.erpnext_item,
                "erpnext_item_untouched": True,
                "was_published": bool(row.is_published),
            }

            # Idempotency: already unpublished.
            if not row.is_published:
                result["already_unpublished"].append(pid)
                continue

            result["candidates"].append(entry)
            if dry_run:
                continue

            # The ONLY write: is_published -> 0. No delete, no Item change.
            frappe.db.set_value("Robot Product", pid, "is_published", 0)
            result["unpublished"].append(pid)
        except Exception as e:
            result["errors"].append({"product_id": pid, "error": f"{type(e).__name__}: {e}"})

    if not dry_run and result["unpublished"]:
        frappe.db.commit()

    result["summary"] = {
        "targets": len(targets),
        "candidates": len(result["candidates"]),
        "unpublished": len(result["unpublished"]),
        "already_unpublished": len(result["already_unpublished"]),
        "skipped_with_refs": len(result["skipped_with_refs"]),
        "missing": len(result["missing"]),
        "errors": len(result["errors"]),
    }
    _print(result)
    return result


def _print(r):
    out = []
    out.append("=" * 70)
    out.append("Unpublish RobotsAsia duplicates" + ("  [DRY RUN]" if r["dry_run"] else "  [APPLIED]"))
    out.append("=" * 70)
    out.append(f"reason: {r['reason']}")
    s = r["summary"]
    out.append(f"targets={s['targets']} candidates={s['candidates']} unpublished={s['unpublished']} "
               f"already={s['already_unpublished']} skipped_refs={s['skipped_with_refs']} "
               f"missing={s['missing']} errors={s['errors']}")
    if r["candidates"]:
        out.append(("would unpublish:" if r["dry_run"] else "unpublished:"))
        for c in r["candidates"]:
            out.append(f"   - {c['product_id']}  ({c['category']}/{c['subcategory']})  erpnext_item={c['erpnext_item']} [untouched]")
    if r["already_unpublished"]:
        out.append("already unpublished:")
        for p in r["already_unpublished"]:
            out.append(f"   = {p}")
    if r["skipped_with_refs"]:
        out.append("skipped (commercial refs):")
        for x in r["skipped_with_refs"]:
            out.append(f"   ! {x['product_id']}: {x['refs']}")
    if r["missing"]:
        out.append("missing: " + ", ".join(r["missing"]))
    if r["errors"]:
        out.append("errors:")
        for e in r["errors"]:
            out.append(f"   x {e['product_id']}: {e['error']}")
    out.append("=" * 70)
    print("\n".join(out))
