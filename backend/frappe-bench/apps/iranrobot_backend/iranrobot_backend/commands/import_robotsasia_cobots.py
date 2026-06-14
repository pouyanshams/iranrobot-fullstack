"""Import RobotsAsia 'cobots' products into the IranRobot catalog.

Reads a normalized dataset (`data/robotsasia_cobots.json`, authored from a
read-only scrape of https://www.robotsasia.com/Cobots.htm) and upserts each
product into Robot Product under the top-level `cobots` category.

Design mirrors `seed_catalog.py`:
  * Idempotent upsert keyed on `product_id` (the Robot Product doc name).
  * Child tables (images, specs) are fully REPLACED on update.
  * Remote hero image URLs are stored directly in the Image child `image`
    field (Attach Image accepts a URL) -- same approach as the seed importer;
    no files are downloaded/hotlinked.

Scope: standalone collaborative robot arms only. Accessories/grippers/kits are
out of scope and not present in the dataset. Provenance (source_url, source
price) lives in the dataset file, NOT on the customer-facing product (Robot
Product has no internal-notes field and we do not add one -- no migration).

This module is a CLI entry point, not a public API. No `@frappe.whitelist`.

Run (dry-run first):

    bench --site iranrobot.localhost execute \\
        iranrobot_backend.commands.import_robotsasia_cobots.run \\
        --kwargs "{'dry_run': True, 'limit': 5}"

    bench --site iranrobot.localhost execute \\
        iranrobot_backend.commands.import_robotsasia_cobots.run \\
        --kwargs "{'dry_run': False, 'update_existing': True}"

Then mirror to ERPNext Items via the existing one-way sync:

    bench --site iranrobot.localhost execute \\
        iranrobot_backend.commands.sync_to_erpnext.run
"""

import json
from pathlib import Path

import frappe

CATEGORY_SLUG = "cobots"
# Labels used ONLY if the category is missing; an existing category is never
# relabeled (matches the seed taxonomy: label_en "Cobots").
CATEGORY_LABEL_FA = "بازوهای همکار"
CATEGORY_LABEL_EN = "Cobots"

DEFAULT_DATASET = (
    Path(__file__).resolve().parents[1] / "data" / "robotsasia_cobots.json"
)

_QUOTE_LABEL_FA = "استعلام قیمت"
_QUOTE_LABEL_EN = "Request quote"
_DEFAULT_LEAD_TIME_DAYS = 45
# Push imported rows after the existing seeded catalog in default sort order.
_DISPLAY_ORDER_BASE = 500


def run(
    dataset_path=None,
    dry_run=False,
    limit=None,
    update_existing=True,
    publish=True,
    download_images=False,
):
    """Upsert RobotsAsia cobot arms into the catalog.

    Args:
        dataset_path:   override the normalized JSON path.
        dry_run:        validate + report only; write nothing, commit nothing.
        limit:          process only the first N products (None = all).
        update_existing: when False, existing product_ids are skipped (not updated).
        publish:        is_published flag for imported products.
        download_images: reserved. The schema stores remote image URLs directly
                         (the established seed pattern), so images are never
                         downloaded; True is accepted but logs a note and behaves
                         like False to avoid large local files / hotlink copies.
    """
    ds_path = Path(dataset_path) if dataset_path else DEFAULT_DATASET
    if not ds_path.exists():
        raise FileNotFoundError(f"Cobots dataset not found at {ds_path}.")

    dataset = json.loads(ds_path.read_text(encoding="utf-8"))
    products = dataset.get("products", [])
    if limit is not None:
        products = products[: int(limit)]

    stats = {
        "dataset_path": str(ds_path),
        "dry_run": bool(dry_run),
        "category": {"verb": None, "slug": CATEGORY_SLUG},
        "created": [],
        "updated": [],
        "skipped": [],
        "warnings": [],
    }
    if download_images:
        stats["warnings"].append(
            "download_images=True ignored: schema stores remote image URLs (seed pattern); no download performed."
        )

    # --- Step 4: ensure the cobots category exists (idempotent, non-destructive) ---
    stats["category"]["verb"] = _ensure_category(dry_run)

    # --- Step 5: upsert products ---
    for idx, prod in enumerate(products):
        pid = prod.get("product_id") or "<unknown>"
        try:
            verb, warnings = _upsert_product(
                prod, idx=idx, publish=publish,
                update_existing=update_existing, dry_run=dry_run,
            )
            if verb == "skipped":
                stats["skipped"].append((pid, "exists and update_existing=False"))
            else:
                stats[verb].append(pid)
            for w in warnings:
                stats["warnings"].append((pid, w))
        except Exception as e:
            stats["skipped"].append((pid, f"{type(e).__name__}: {e}"))

    if not dry_run:
        frappe.db.commit()

    stats["summary"] = {
        "created": len(stats["created"]),
        "updated": len(stats["updated"]),
        "skipped": len(stats["skipped"]),
        "total_in_dataset": len(products),
        "warnings": len(stats["warnings"]),
    }
    _print_report(stats)
    return stats


# ===========================================================================
# Category
# ===========================================================================

def _ensure_category(dry_run):
    """Create the top-level cobots category if missing. Never relabels an
    existing one. Returns 'exists' | 'created' | 'would-create'."""
    if frappe.db.exists("Robot Category", CATEGORY_SLUG):
        return "exists"
    if dry_run:
        return "would-create"
    doc = frappe.get_doc({
        "doctype": "Robot Category",
        "slug": CATEGORY_SLUG,
        "label_fa": CATEGORY_LABEL_FA,
        "label_en": CATEGORY_LABEL_EN,
        "parent_category": None,
        "is_published": 1,
        "display_order": 50,
    })
    doc.insert(ignore_permissions=True)
    return "created"


# ===========================================================================
# Product upsert
# ===========================================================================

def _upsert_product(prod, idx, publish, update_existing, dry_run):
    """Upsert one Robot Product + child tables. Returns (verb, warnings)."""
    warnings = []
    pid = prod["product_id"]
    exists = bool(frappe.db.exists("Robot Product", pid))

    if exists and not update_existing:
        return "skipped", warnings

    fields = {
        "slug":            prod.get("slug") or pid,
        "is_published":    1 if publish else 0,
        "is_featured":     0,
        "is_new_arrival":  1,
        "display_order":   _DISPLAY_ORDER_BASE + idx,
        "category":        CATEGORY_SLUG,
        "subcategory":     None,
        "product_name_fa": prod.get("product_name_fa") or "",
        "product_name_en": prod.get("product_name_en") or "",
        "brand":           prod.get("brand") or "",
        "model":           prod.get("model") or None,
        "origin_fa":       prod.get("origin_fa") or "—",
        "origin_en":       prod.get("origin_en") or "—",
        "tagline_fa":      prod.get("tagline_fa") or "",
        "tagline_en":      prod.get("tagline_en") or "",
        "description_fa":  prod.get("description_fa") or "",
        "description_en":  prod.get("description_en") or "",
        "in_stock":        1,
        "lead_time_days":  int(prod.get("lead_time_days") or _DEFAULT_LEAD_TIME_DAYS),
        # Quote-first: no firm USD price (source prices are CNY / placeholders).
        "mode_buy":        0,
        "mode_rent":       0,
        "mode_procure":    1,
        "price_usd":       None,
        "rent_per_day_usd": None,
        "price_label_fa":  _QUOTE_LABEL_FA,
        "price_label_en":  _QUOTE_LABEL_EN,
    }

    images_payload = _build_images(prod, warnings)
    specs_payload = _build_specs(prod, warnings)

    if dry_run:
        return ("updated" if exists else "created"), warnings

    if exists:
        doc = frappe.get_doc("Robot Product", pid)
        for k, v in fields.items():
            doc.set(k, v)
        doc.set("images", images_payload)
        doc.set("specs", specs_payload)
        doc.save(ignore_permissions=True)
        return "updated", warnings

    doc = frappe.get_doc({
        "doctype": "Robot Product",
        "product_id": pid,
        **fields,
        "images": images_payload,
        "specs": specs_payload,
    })
    doc.insert(ignore_permissions=True)
    return "created", warnings


def _build_images(prod, warnings):
    """One hero row from `hero_image` (a remote URL). Empty/missing -> no row
    (the PDP/PLP falls back to its illustration). Gallery URLs, if any, are
    added as non-hero rows."""
    rows = []
    hero = (prod.get("hero_image") or "").strip()
    name_fa = prod.get("product_name_fa") or ""
    name_en = prod.get("product_name_en") or ""
    if hero:
        rows.append({"image": hero, "is_hero": 1, "alt_fa": name_fa, "alt_en": name_en})
    else:
        warnings.append("no hero image available (left empty for manual review)")
    for url in (prod.get("gallery") or []):
        if url and url != hero:
            rows.append({"image": url, "is_hero": 0, "alt_fa": name_fa, "alt_en": name_en})
    return rows


def _build_specs(prod, warnings):
    """Bilingual spec rows. All four child fields are required by the doctype;
    incomplete rows are dropped with a warning rather than failing the import."""
    rows = []
    for s in (prod.get("specs") or []):
        lf, vf = (s.get("label_fa") or "").strip(), (s.get("value_fa") or "").strip()
        le, ve = (s.get("label_en") or "").strip(), (s.get("value_en") or "").strip()
        if not (lf and vf and le and ve):
            warnings.append(f"dropped incomplete spec row {s!r}")
            continue
        rows.append({"label_fa": lf, "value_fa": vf, "label_en": le, "value_en": ve})
    return rows


# ===========================================================================
# Reporting
# ===========================================================================

def _print_report(stats):
    s = stats["summary"]
    out = []
    out.append("=" * 70)
    out.append("RobotsAsia -> IranRobot cobots import" + ("  [DRY RUN]" if stats["dry_run"] else ""))
    out.append("=" * 70)
    out.append(f"Dataset : {stats['dataset_path']}")
    out.append(f"Category: {stats['category']['slug']} ({stats['category']['verb']})")
    out.append("")
    out.append(f"Robot Product  created={s['created']}  updated={s['updated']}  skipped={s['skipped']}  total={s['total_in_dataset']}")
    if stats["created"]:
        out.append("  created:")
        for p in stats["created"]:
            out.append(f"    + {p}")
    if stats["updated"]:
        out.append("  updated:")
        for p in stats["updated"]:
            out.append(f"    ~ {p}")
    if stats["skipped"]:
        out.append("  skipped:")
        for name, reason in stats["skipped"]:
            out.append(f"    - {name}: {reason}")
    if stats["warnings"]:
        out.append(f"  warnings ({len(stats['warnings'])}):")
        for w in stats["warnings"]:
            out.append(f"    ! {w}")
    out.append("=" * 70)
    print("\n".join(out))
