"""General RobotsAsia -> IranRobot catalog importer (multi-category).

Reads a consolidated normalized dataset (`data/robotsasia_products.json`,
authored from a read-only scrape of robotsasia.com) and upserts each product
into Robot Product under its own (already-mapped) `category` / `subcategory`.

This is the multi-category generalization of `import_robotsasia_cobots.py`.
It deliberately does NOT manage the cobots batch (that stays in its own
command + `data/robotsasia_cobots.json`) so the existing 10 cobots are
untouched.

Design (same guarantees as the cobots importer):
  * Idempotent upsert keyed on `product_id` (the Robot Product doc name).
  * Child tables (images, specs, use_cases) fully REPLACED on update.
  * Remote hero image URLs stored directly in the Image child `image` field
    (Attach Image accepts a URL) -- no downloads/hotlinking.
  * Every product carries its own browsable `category` (+ optional
    `subcategory`); the dataset is pre-filtered to standalone robots.
  * Quote-first pricing: source prices are CNY/placeholder, so no USD price is
    set; `source_price_raw` is kept in the dataset for staff review only.

Categories are created only if missing (non-destructive, never relabeled).

Run:
    bench --site iranrobot.localhost execute \\
        iranrobot_backend.commands.import_robotsasia_products.run \\
        --kwargs "{'dry_run': True, 'limit_per_category': 10}"

    bench --site iranrobot.localhost execute \\
        iranrobot_backend.commands.import_robotsasia_products.run \\
        --kwargs "{'dry_run': False, 'category': 'humanoids', 'limit_per_category': 10, 'update_existing': True}"

Then mirror to ERPNext Items via the existing one-way sync:
    bench --site iranrobot.localhost execute iranrobot_backend.commands.sync_to_erpnext.run
"""

import json
from collections import defaultdict
from pathlib import Path

import frappe

DEFAULT_DATASET = (
    Path(__file__).resolve().parents[1] / "data" / "robotsasia_products.json"
)

_QUOTE_LABEL_FA = "استعلام قیمت"
_QUOTE_LABEL_EN = "Request quote"
_DEFAULT_LEAD_TIME_DAYS = 45
_DISPLAY_ORDER_BASE = 600

# Fallback labels for auto-created top-level categories (used only if missing).
_CATEGORY_FALLBACK_LABELS = {
    "humanoids":  ("انسان‌نماها", "Humanoids"),
    "quadrupeds": ("چهارپاها", "Quadrupeds"),
    "amrs":       ("ربات‌های متحرک خودران", "AMRs"),
    "drones":     ("پهپادها", "Drones"),
    "ugvs":       ("خودروهای زمینی", "UGVs"),
    "cobots":     ("بازوهای همکار", "Cobots"),
    "accessories": ("لوازم جانبی", "Accessories"),
}


def run(
    dataset_path=None,
    dry_run=False,
    category=None,
    limit_per_category=10,
    update_existing=True,
    publish=True,
    download_images=False,
):
    """Upsert RobotsAsia products into their mapped catalog categories.

    Args:
        dataset_path:       override the consolidated JSON path.
        dry_run:            validate + report only; write nothing.
        category:           import only this category (None = all in dataset).
        limit_per_category: cap products imported per category.
        update_existing:    when False, existing product_ids are skipped.
        publish:            is_published flag for imported products.
        download_images:    reserved/no-op (remote URLs are stored directly).
    """
    ds_path = Path(dataset_path) if dataset_path else DEFAULT_DATASET
    if not ds_path.exists():
        raise FileNotFoundError(f"Products dataset not found at {ds_path}.")

    dataset = json.loads(ds_path.read_text(encoding="utf-8"))
    all_products = dataset.get("products", [])

    # Group by category, honoring the optional category filter + per-cat limit.
    grouped = defaultdict(list)
    for p in all_products:
        cat = p.get("category")
        if not cat:
            continue
        if category and cat != category:
            continue
        grouped[cat].append(p)

    try:
        per_cat_limit = int(limit_per_category)
    except (TypeError, ValueError):
        per_cat_limit = 10

    stats = {
        "dataset_path": str(ds_path),
        "dry_run": bool(dry_run),
        "category_filter": category,
        "limit_per_category": per_cat_limit,
        "categories_ensured": {},
        "per_category": {},
        "warnings": [],
    }
    if download_images:
        stats["warnings"].append("download_images=True ignored: remote image URLs are stored directly (seed pattern).")

    for cat, prods in grouped.items():
        # Ensure the (browsable) category exists; never relabel an existing one.
        stats["categories_ensured"][cat] = _ensure_category(cat, dry_run)
        bucket = {"created": [], "updated": [], "skipped": []}
        for idx, prod in enumerate(prods[:per_cat_limit]):
            pid = prod.get("product_id") or "<unknown>"
            try:
                verb, warnings = _upsert_product(
                    prod, idx=idx, publish=publish,
                    update_existing=update_existing, dry_run=dry_run,
                )
                if verb == "skipped":
                    bucket["skipped"].append((pid, "exists and update_existing=False"))
                else:
                    bucket[verb].append(pid)
                for w in warnings:
                    stats["warnings"].append((pid, w))
            except Exception as e:
                bucket["skipped"].append((pid, f"{type(e).__name__}: {e}"))
        stats["per_category"][cat] = {
            "created": bucket["created"],
            "updated": bucket["updated"],
            "skipped": bucket["skipped"],
            "available_in_dataset": len(prods),
            "considered": min(len(prods), per_cat_limit),
        }

    if not dry_run:
        frappe.db.commit()

    stats["summary"] = {
        cat: {
            "created": len(v["created"]),
            "updated": len(v["updated"]),
            "skipped": len(v["skipped"]),
            "available": v["available_in_dataset"],
        }
        for cat, v in stats["per_category"].items()
    }
    _print_report(stats)
    return stats


# ===========================================================================
# Category
# ===========================================================================

def _ensure_category(slug, dry_run):
    """Create a top-level category if missing; never relabel an existing one.
    Returns 'exists' | 'created' | 'would-create'."""
    if frappe.db.exists("Robot Category", slug):
        return "exists"
    if dry_run:
        return "would-create"
    label_fa, label_en = _CATEGORY_FALLBACK_LABELS.get(slug, (slug, slug.title()))
    doc = frappe.get_doc({
        "doctype": "Robot Category",
        "slug": slug,
        "label_fa": label_fa,
        "label_en": label_en,
        "parent_category": None,
        "is_published": 1,
        "display_order": 90,
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
    cat = prod["category"]
    sub = prod.get("subcategory") or None
    exists = bool(frappe.db.exists("Robot Product", pid))
    if exists and not update_existing:
        return "skipped", warnings

    fields = {
        "slug":            prod.get("slug") or pid,
        "is_published":    1 if publish else 0,
        "is_featured":     0,
        "is_new_arrival":  1,
        "display_order":   _DISPLAY_ORDER_BASE + idx,
        "category":        cat,
        "subcategory":     sub,
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
    use_cases_payload = _build_use_cases(prod)

    if dry_run:
        return ("updated" if exists else "created"), warnings

    if exists:
        doc = frappe.get_doc("Robot Product", pid)
        for k, v in fields.items():
            doc.set(k, v)
        doc.set("images", images_payload)
        doc.set("specs", specs_payload)
        doc.set("use_cases", use_cases_payload)
        doc.save(ignore_permissions=True)
        return "updated", warnings

    doc = frappe.get_doc({
        "doctype": "Robot Product",
        "product_id": pid,
        **fields,
        "images": images_payload,
        "specs": specs_payload,
        "use_cases": use_cases_payload,
    })
    doc.insert(ignore_permissions=True)
    return "created", warnings


def _build_images(prod, warnings):
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
    rows = []
    for s in (prod.get("specs") or []):
        lf, vf = (s.get("label_fa") or "").strip(), (s.get("value_fa") or "").strip()
        le, ve = (s.get("label_en") or "").strip(), (s.get("value_en") or "").strip()
        if not (lf and vf and le and ve):
            warnings.append(f"dropped incomplete spec row {s!r}")
            continue
        rows.append({"label_fa": lf, "value_fa": vf, "label_en": le, "value_en": ve})
    return rows


def _build_use_cases(prod):
    """Use-case child rows (e.g. tag educational units with use_case=education).
    Unknown slugs are skipped rather than failing the import."""
    rows, seen = [], set()
    for uc in (prod.get("use_cases") or []):
        if not isinstance(uc, str):
            continue
        slug = uc.strip().lower()
        if not slug or slug in seen:
            continue
        if not frappe.db.exists("Robot Use Case", slug):
            continue
        seen.add(slug)
        rows.append({"use_case": slug})
    return rows


# ===========================================================================
# Reporting
# ===========================================================================

def _print_report(stats):
    out = []
    out.append("=" * 72)
    out.append("RobotsAsia -> IranRobot multi-category import" + ("  [DRY RUN]" if stats["dry_run"] else ""))
    out.append("=" * 72)
    out.append(f"Dataset : {stats['dataset_path']}")
    out.append(f"Filter  : category={stats['category_filter']}  limit_per_category={stats['limit_per_category']}")
    out.append(f"Categories ensured: {stats['categories_ensured']}")
    out.append("")
    for cat, v in stats["per_category"].items():
        out.append(f"[{cat}]  created={len(v['created'])}  updated={len(v['updated'])}  skipped={len(v['skipped'])}  (available={v['available_in_dataset']})")
        for p in v["created"]:
            out.append(f"    + {p}")
        for p in v["updated"]:
            out.append(f"    ~ {p}")
        for name, reason in v["skipped"]:
            out.append(f"    - {name}: {reason}")
    if stats["warnings"]:
        out.append("")
        out.append(f"warnings ({len(stats['warnings'])}):")
        for w in stats["warnings"]:
            out.append(f"    ! {w}")
    out.append("=" * 72)
    print("\n".join(out))
