"""Phase 1.5 -- Catalog Seed / Import.

Reads `data/catalog_snapshot.json` (produced by `scripts/export_catalog.mts`) and
upserts categories + products into the Frappe site.

Invocation:

    bench --site iranrobot.localhost execute iranrobot_backend.commands.seed_catalog.run

Idempotent: re-running updates existing rows; never duplicates. Child tables
(images, specs) are fully replaced on update so they always reflect the latest
snapshot.

This module is a CLI entry point, not a public API. No `@frappe.whitelist`.
"""

import json
import os
from pathlib import Path

import frappe
from frappe import _


# ---------------------------------------------------------------------------
# Snapshot path
# ---------------------------------------------------------------------------

DEFAULT_SNAPSHOT = (
    Path(__file__).resolve().parents[2] / "data" / "catalog_snapshot.json"
)


# ---------------------------------------------------------------------------
# Category seed (24 rows = 8 top-level + 16 subs)
# Order matters: top-level rows insert before their children so the
# parent_category FK exists.
# fa/en labels + icons are sourced from PLP_CATEGORIES in the frontend.
# ---------------------------------------------------------------------------

CATEGORY_SEED = [
    # ---- top-level ----
    {"slug": "solutions",   "label_fa": "راهکارها",                  "label_en": "Solutions",   "parent": None, "icon": "🧩", "order": 10},
    {"slug": "humanoids",   "label_fa": "انسان‌نماها",          "label_en": "Humanoids",   "parent": None, "icon": "🤖", "order": 20},
    {"slug": "quadrupeds",  "label_fa": "چهارپاها",                  "label_en": "Quadrupeds",  "parent": None, "icon": "🐕", "order": 30},
    {"slug": "amrs",        "label_fa": "ربات‌های متحرک خودران", "label_en": "AMRs",        "parent": None, "icon": "🛻", "order": 40},
    {"slug": "cobots",      "label_fa": "بازوهای همکار",             "label_en": "Cobots",      "parent": None, "icon": "🦾", "order": 50},
    {"slug": "drones",      "label_fa": "پهپادها",                   "label_en": "Drones",      "parent": None, "icon": "🛸", "order": 60},
    {"slug": "ugvs",        "label_fa": "خودروهای زمینی",            "label_en": "UGVs",        "parent": None, "icon": "🚙", "order": 70},
    {"slug": "accessories", "label_fa": "لوازم جانبی",               "label_en": "Accessories", "parent": None, "icon": "🔌", "order": 80},
    # ---- humanoids children ----
    {"slug": "bipedal-humanoids",    "label_fa": "انسان‌نمای دو پا",        "label_en": "Bipedal Humanoids",     "parent": "humanoids",   "icon": "🤖", "order": 10},
    {"slug": "wheeled-humanoids",    "label_fa": "انسان‌نمای چرخ‌دار", "label_en": "Wheeled Humanoids",     "parent": "humanoids",   "icon": "🤖", "order": 20},
    {"slug": "upper-body-humanoids", "label_fa": "انسان‌نمای بالاتنه",      "label_en": "Upper Body Humanoids",  "parent": "humanoids",   "icon": "🤖", "order": 30},
    # ---- quadrupeds children ----
    {"slug": "standard-quadrupeds",  "label_fa": "چهارپای استاندارد",            "label_en": "Standard Quadrupeds",   "parent": "quadrupeds",  "icon": "🐕", "order": 10},
    {"slug": "wheeled-quadrupeds",   "label_fa": "چهارپای چرخ‌دار",         "label_en": "Wheeled Quadrupeds",    "parent": "quadrupeds",  "icon": "🐕", "order": 20},
    # ---- accessories children ----
    {"slug": "robot-arms",      "label_fa": "بازوهای ربات",       "label_en": "Robot Arms",       "parent": "accessories", "icon": "🦾",   "order": 10},
    {"slug": "robot-batteries", "label_fa": "باتری ربات",         "label_en": "Robot Batteries",  "parent": "accessories", "icon": "🔋",  "order": 20},
    {"slug": "robot-chargers",  "label_fa": "شارژر ربات",         "label_en": "Robot Chargers",   "parent": "accessories", "icon": "⚡", "order": 30},
    {"slug": "robot-hands",     "label_fa": "دست‌های ربات",  "label_en": "Robot Hands",      "parent": "accessories", "icon": "🖐️", "order": 40},
    {"slug": "sensors",         "label_fa": "سنسورها",            "label_en": "Sensors",          "parent": "accessories", "icon": "📡",  "order": 50},
    # ---- solutions children (use-case taxonomy; no products link to these in Phase 1) ----
    {"slug": "education",  "label_fa": "آموزش و پژوهش",        "label_en": "Education & Research",     "parent": "solutions",  "icon": "🎓", "order": 10},
    {"slug": "warehouse",  "label_fa": "انبارداری و لجستیک",   "label_en": "Warehouse & Logistics",    "parent": "solutions",  "icon": "📦", "order": 20},
    {"slug": "inspection", "label_fa": "بازرسی و پایش",        "label_en": "Inspection & Monitoring",  "parent": "solutions",  "icon": "🔍", "order": 30},
    {"slug": "security",   "label_fa": "امنیت و گشت‌زنی", "label_en": "Security & Patrol",        "parent": "solutions",  "icon": "🛡️", "order": 40},
    {"slug": "healthcare", "label_fa": "سلامت و خدمات",        "label_en": "Healthcare & Services",    "parent": "solutions",  "icon": "🏥", "order": 50},
    {"slug": "custom",     "label_fa": "راهکار سفارشی",        "label_en": "Custom Solution",          "parent": "solutions",  "icon": "🧩", "order": 60},
]


# ---------------------------------------------------------------------------
# Category mapping: frontend Robot.category (singular) -> Frappe category slug.
# ---------------------------------------------------------------------------

CATEGORY_SLUG_MAP = {
    "humanoid":    "humanoids",
    "quadruped":   "quadrupeds",
    "amr":         "amrs",
    "cobots":      "cobots",
    "accessories": "accessories",
    "ugv":         "ugvs",
    "drone":       "drones",
}


# ---------------------------------------------------------------------------
# Per-product overrides for products whose frontend `category` doesn't fit the
# Phase 1 taxonomy. Decided in conversation: reclassify into the 8 standard cats.
# ---------------------------------------------------------------------------

PRODUCT_CATEGORY_OVERRIDES = {
    # id: (category, subcategory or None)
    "brainco-revo-2-touch":         ("accessories", "robot-hands"),  # biomimetic robot hand
    "deyee-polyenergy-king-dy-h3":  ("amrs",        None),           # AI physiotherapy robot (loose fit)
    "senad-parcel-weighing-sorter": ("amrs",        None),           # warehouse sorting machine (loose fit)
    "senad-dws-small-item-sorter":  ("amrs",        None),           # e-commerce sorting machine (loose fit)
}


# ---------------------------------------------------------------------------
# Use Case seed (6 application/use-case rows).
# Solutions are an orthogonal taxonomy to product type (category): a single
# product can belong to one category and multiple use cases at the same time.
# Labels mirror the frontend Solutions sub-categories.
# ---------------------------------------------------------------------------

USE_CASE_SEED = [
    {"slug": "warehouse",  "label_fa": "انبارداری و لجستیک",   "label_en": "Warehouse & Logistics",    "icon": "📦", "order": 10},
    {"slug": "security",   "label_fa": "امنیت و گشت‌زنی",      "label_en": "Security & Patrol",        "icon": "🛡️", "order": 20},
    {"slug": "inspection", "label_fa": "بازرسی و پایش",        "label_en": "Inspection & Monitoring",  "icon": "🔍", "order": 30},
    {"slug": "healthcare", "label_fa": "سلامت و خدمات",        "label_en": "Healthcare & Services",    "icon": "🏥", "order": 40},
    {"slug": "education",  "label_fa": "آموزش و پژوهش",        "label_en": "Education & Research",     "icon": "🎓", "order": 50},
    {"slug": "custom",     "label_fa": "راهکار سفارشی",        "label_en": "Custom Solution",          "icon": "🧩", "order": 60},
]

USE_CASE_SLUGS = {u["slug"] for u in USE_CASE_SEED}


# Frontend fields explicitly dropped during import. `useCases` was historically
# here but is now persisted via the Robot Product Use Case child table.
DROPPED_FIELDS = (
    "editorialBullets", "editorialBulletsEn",
    "bestFor", "bestForEn", "highlights", "highlightsEn",
    "tags", "accent",
)


# ===========================================================================
# Entry point
# ===========================================================================

def run(snapshot_path=None):
    """Upsert the catalog into the current Frappe site.

    Returns a dict report. When invoked via `bench execute`, bench prints the
    return value as the command output.
    """
    snap_path = Path(snapshot_path) if snapshot_path else DEFAULT_SNAPSHOT
    if not snap_path.exists():
        raise FileNotFoundError(
            f"Catalog snapshot not found at {snap_path}. "
            "Regenerate with: npx --yes tsx scripts/export_catalog.mts"
        )

    snapshot = json.loads(snap_path.read_text())
    products = snapshot.get("products", [])

    stats = {
        "snapshot_path": str(snap_path),
        "snapshot_exported_at": snapshot.get("exportedAt"),
        "categories": {"created": [], "updated": [], "skipped": []},
        "use_cases":  {"created": [], "updated": [], "skipped": []},
        "products":   {"created": [], "updated": [], "skipped": []},
        "products_with_use_cases": 0,
        "use_case_assignments": 0,
        "unknown_use_cases": [],
        "warnings": [],
        "reclassifications": [],
    }

    # Phase A1: categories (top-level first by virtue of CATEGORY_SEED ordering)
    for cat in CATEGORY_SEED:
        try:
            verb = _upsert_category(cat)
            stats["categories"][verb].append(cat["slug"])
        except Exception as e:
            stats["categories"]["skipped"].append((cat["slug"], f"{type(e).__name__}: {e}"))

    # Phase A2: use cases (must exist before any product references them).
    for uc in USE_CASE_SEED:
        try:
            verb = _upsert_use_case(uc)
            stats["use_cases"][verb].append(uc["slug"])
        except Exception as e:
            stats["use_cases"]["skipped"].append((uc["slug"], f"{type(e).__name__}: {e}"))

    # Phase B: products
    for idx, prod in enumerate(products):
        prod_id = prod.get("id") or "<unknown>"
        try:
            verb, warnings, uc_assigned, unknown_ucs = _upsert_product(
                prod, idx=idx, is_featured=(idx == 0),
            )
            stats["products"][verb].append(prod_id)
            if uc_assigned:
                stats["products_with_use_cases"] += 1
                stats["use_case_assignments"] += uc_assigned
            for uc in unknown_ucs:
                stats["unknown_use_cases"].append((prod_id, uc))
            for w in warnings:
                stats["warnings"].append((prod_id, w))
            if prod_id in PRODUCT_CATEGORY_OVERRIDES:
                cat, sub = PRODUCT_CATEGORY_OVERRIDES[prod_id]
                stats["reclassifications"].append({
                    "id": prod_id,
                    "frontend_category": prod.get("category"),
                    "frontend_subcategory": prod.get("subcategory"),
                    "frappe_category": cat,
                    "frappe_subcategory": sub,
                })
        except Exception as e:
            stats["products"]["skipped"].append((prod_id, f"{type(e).__name__}: {e}"))

    frappe.db.commit()

    # Counts (numbers are easier to scan than lists)
    stats["summary"] = {
        "categories": {
            "created": len(stats["categories"]["created"]),
            "updated": len(stats["categories"]["updated"]),
            "skipped": len(stats["categories"]["skipped"]),
            "total_in_seed": len(CATEGORY_SEED),
        },
        "use_cases": {
            "created": len(stats["use_cases"]["created"]),
            "updated": len(stats["use_cases"]["updated"]),
            "skipped": len(stats["use_cases"]["skipped"]),
            "total_in_seed": len(USE_CASE_SEED),
        },
        "products": {
            "created": len(stats["products"]["created"]),
            "updated": len(stats["products"]["updated"]),
            "skipped": len(stats["products"]["skipped"]),
            "total_in_snapshot": len(products),
            "products_with_use_cases": stats["products_with_use_cases"],
            "use_case_assignments":   stats["use_case_assignments"],
            "unknown_use_cases":      len(stats["unknown_use_cases"]),
        },
        "warnings": len(stats["warnings"]),
        "reclassifications": len(stats["reclassifications"]),
        "dropped_fields_per_product": list(DROPPED_FIELDS),
    }

    _print_report(stats)
    return stats


# ===========================================================================
# Category upsert
# ===========================================================================

def _upsert_use_case(uc):
    """Upsert a Robot Use Case row. Returns 'created' or 'updated'."""
    slug = uc["slug"]
    fields = {
        "label_fa":      uc["label_fa"],
        "label_en":      uc["label_en"],
        "icon":          uc.get("icon"),
        "display_order": uc.get("order", 0),
        "is_published":  1,
    }
    if frappe.db.exists("Robot Use Case", slug):
        doc = frappe.get_doc("Robot Use Case", slug)
        for k, v in fields.items():
            doc.set(k, v)
        doc.save(ignore_permissions=True)
        return "updated"
    doc = frappe.get_doc({"doctype": "Robot Use Case", "slug": slug, **fields})
    doc.insert(ignore_permissions=True)
    return "created"


def _upsert_category(cat):
    """Upsert a Robot Category row. Returns 'created' or 'updated'."""
    slug = cat["slug"]
    fields = {
        "label_fa":        cat["label_fa"],
        "label_en":        cat["label_en"],
        "parent_category": cat["parent"],
        "icon":            cat.get("icon"),
        "display_order":   cat.get("order", 0),
        "is_published":    1,
    }
    if frappe.db.exists("Robot Category", slug):
        doc = frappe.get_doc("Robot Category", slug)
        for k, v in fields.items():
            doc.set(k, v)
        doc.save(ignore_permissions=True)
        return "updated"
    doc = frappe.get_doc({"doctype": "Robot Category", "slug": slug, **fields})
    doc.insert(ignore_permissions=True)
    return "created"


# ===========================================================================
# Product upsert
# ===========================================================================

def _upsert_product(prod, idx, is_featured):
    """Upsert a Robot Product row + its child tables.

    Returns ('created'|'updated', warnings_list, use_cases_assigned,
    unknown_use_cases). Use case child rows are built from
    ``prod.get("useCases", [])``; unknown slugs (not in USE_CASE_SEED) are
    surfaced in the report and skipped rather than crashing the import.
    """
    warnings = []
    prod_id = prod["id"]

    # Resolve category. Use per-product override if present, else the slug map.
    if prod_id in PRODUCT_CATEGORY_OVERRIDES:
        cat, sub = PRODUCT_CATEGORY_OVERRIDES[prod_id]
    else:
        front_cat = prod.get("category")
        cat = CATEGORY_SLUG_MAP.get(front_cat)
        if cat is None:
            raise frappe.ValidationError(
                f"category '{front_cat}' not in Phase 1 taxonomy (no map entry, no override)"
            )
        sub = prod.get("subcategory") or None

    # Modes -> boolean flags.
    modes = set(prod.get("modes") or [])
    mode_buy     = 1 if "buy" in modes else 0
    mode_rent    = 1 if "rent" in modes else 0
    mode_procure = 1 if "procure" in modes else 0
    if not (mode_buy or mode_rent or mode_procure):
        # Defensive: every product must have at least one mode. If none, default
        # to procure (matches the frontend's de facto behavior).
        mode_procure = 1
        warnings.append("no modes in source; defaulted to procure=1")

    # Pricing labels with sensible defaults when no price_usd is set.
    price_usd         = prod.get("priceUsd") or None
    rent_per_day_usd  = prod.get("rentPerDayUsd") or None
    price_label_fa    = prod.get("priceLabel") or ("استعلام قیمت" if not price_usd else None)
    price_label_en    = prod.get("priceLabelEn") or ("Request quote" if not price_usd else None)

    fields = {
        "slug":              prod.get("slug") or prod_id,
        "is_published":      1,
        "is_featured":       1 if is_featured else 0,
        "is_new_arrival":    1 if prod.get("isNewArrival") else 0,
        "display_order":     idx,
        "category":          cat,
        "subcategory":       sub,
        "product_name_fa":   prod.get("name") or "",
        "product_name_en":   prod.get("nameEn") or "",
        "brand":             prod.get("brand") or "",
        "model":             prod.get("model") or None,
        "origin_fa":         prod.get("origin") or "—",
        "origin_en":         prod.get("originEn") or "—",
        "tagline_fa":        prod.get("tagline") or "",
        "tagline_en":        prod.get("taglineEn") or "",
        "description_fa":    prod.get("description") or "",
        "description_en":    prod.get("descriptionEn") or "",
        "in_stock":          1 if prod.get("inStock") else 0,
        "lead_time_days":    int(prod.get("leadTimeDays") or 30),
        "rating":            prod.get("rating"),
        "mode_buy":          mode_buy,
        "mode_rent":         mode_rent,
        "mode_procure":      mode_procure,
        "price_usd":         price_usd,
        "rent_per_day_usd":  rent_per_day_usd,
        "price_label_fa":    price_label_fa,
        "price_label_en":    price_label_en,
    }

    images_payload, hero_warnings = _build_images_payload(prod)
    warnings.extend(hero_warnings)

    specs_payload, spec_warnings = _build_specs_payload(prod)
    warnings.extend(spec_warnings)

    use_cases_payload, unknown_use_cases = _build_use_cases_payload(prod)

    if frappe.db.exists("Robot Product", prod_id):
        doc = frappe.get_doc("Robot Product", prod_id)
        for k, v in fields.items():
            doc.set(k, v)
        doc.set("images", images_payload)
        doc.set("specs", specs_payload)
        doc.set("use_cases", use_cases_payload)
        doc.save(ignore_permissions=True)
        return "updated", warnings, len(use_cases_payload), unknown_use_cases

    doc = frappe.get_doc({
        "doctype":    "Robot Product",
        "product_id": prod_id,
        **fields,
        "images":     images_payload,
        "specs":      specs_payload,
        "use_cases":  use_cases_payload,
    })
    doc.insert(ignore_permissions=True)
    return "created", warnings, len(use_cases_payload), unknown_use_cases


# ===========================================================================
# Child table payload builders
# ===========================================================================

def _build_images_payload(prod):
    """Return ([image_rows], warnings).

    image -> 1 row with is_hero=1.
    gallery -> additional rows with is_hero=0, in array order.
    Hero URL is de-duplicated against the gallery to avoid validation failure
    (the parent controller rejects >1 hero row).
    """
    warnings = []
    rows = []
    hero_url = prod.get("image")
    gallery  = prod.get("gallery") or []

    if hero_url:
        rows.append({
            "image":   hero_url,
            "is_hero": 1,
            "alt_fa":  prod.get("name") or "",
            "alt_en":  prod.get("nameEn") or "",
        })

    for url in gallery:
        if not url:
            continue
        if url == hero_url:
            continue  # de-dup
        rows.append({
            "image":   url,
            "is_hero": 0,
            "alt_fa":  prod.get("name") or "",
            "alt_en":  prod.get("nameEn") or "",
        })

    return rows, warnings


def _build_use_cases_payload(prod):
    """Return ([{use_case: <slug>}, ...], [unknown_slug, ...]).

    Reads from ``prod.get("useCases", [])`` (the frontend array). Unknown
    slugs (not in USE_CASE_SEED) are skipped and surfaced in the seed report
    so a typo in the snapshot doesn't crash the import or silently land in
    the DB.

    Order is preserved; duplicates within the same product are de-duped.
    """
    rows = []
    unknown = []
    seen = set()
    raw = prod.get("useCases")
    if not raw:
        return rows, unknown
    for uc in raw:
        if not isinstance(uc, str):
            continue
        slug = uc.strip().lower()
        if not slug or slug in seen:
            continue
        seen.add(slug)
        if slug not in USE_CASE_SLUGS:
            unknown.append(slug)
            continue
        rows.append({"use_case": slug})
    return rows, unknown


def _build_specs_payload(prod):
    """Return ([spec_rows], warnings).

    Zip `specs` (fa) and `specsEn` (en) by index. If lengths mismatch, take the
    shorter and warn -- don't fabricate translations.
    """
    warnings = []
    specs_fa = prod.get("specs") or []
    specs_en = prod.get("specsEn") or []

    if len(specs_fa) != len(specs_en):
        warnings.append(
            f"spec length mismatch: fa={len(specs_fa)} en={len(specs_en)}; "
            f"truncated to {min(len(specs_fa), len(specs_en))} rows"
        )

    pairs = list(zip(specs_fa, specs_en))
    rows = []
    for fa, en in pairs:
        label_fa = (fa or {}).get("label") or ""
        value_fa = (fa or {}).get("value") or ""
        label_en = (en or {}).get("label") or ""
        value_en = (en or {}).get("value") or ""
        if not (label_fa and value_fa and label_en and value_en):
            # All four child fields are required by the doctype -- skip rather than
            # write empty strings that would fail validation.
            warnings.append(
                f"dropped incomplete spec row "
                f"(fa={label_fa!r}/{value_fa!r}, en={label_en!r}/{value_en!r})"
            )
            continue
        rows.append({
            "label_fa": label_fa,
            "value_fa": value_fa,
            "label_en": label_en,
            "value_en": value_en,
        })
    return rows, warnings


# ===========================================================================
# Reporting
# ===========================================================================

def _print_report(stats):
    """Pretty-print the report to stdout. bench execute will surface this."""
    s = stats["summary"]
    lines = []
    lines.append("=" * 70)
    lines.append("Phase 1.5 -- Catalog Seed / Import")
    lines.append("=" * 70)
    lines.append(f"Snapshot: {stats['snapshot_path']}")
    lines.append(f"Exported: {stats['snapshot_exported_at']}")
    lines.append("")
    lines.append("Robot Category:")
    lines.append(f"  created : {s['categories']['created']}")
    lines.append(f"  updated : {s['categories']['updated']}")
    lines.append(f"  skipped : {s['categories']['skipped']}")
    lines.append(f"  total   : {s['categories']['total_in_seed']}")
    lines.append("")
    lines.append("Robot Use Case:")
    lines.append(f"  created : {s['use_cases']['created']}")
    lines.append(f"  updated : {s['use_cases']['updated']}")
    lines.append(f"  skipped : {s['use_cases']['skipped']}")
    lines.append(f"  total   : {s['use_cases']['total_in_seed']}")
    lines.append("")
    lines.append("Robot Product:")
    lines.append(f"  created                : {s['products']['created']}")
    lines.append(f"  updated                : {s['products']['updated']}")
    lines.append(f"  skipped                : {s['products']['skipped']}")
    lines.append(f"  total                  : {s['products']['total_in_snapshot']}")
    lines.append(f"  with use cases         : {s['products']['products_with_use_cases']}")
    lines.append(f"  use-case assignments   : {s['products']['use_case_assignments']}")
    lines.append(f"  unknown use-case slugs : {s['products']['unknown_use_cases']}")
    lines.append("")
    if stats.get("unknown_use_cases"):
        lines.append("Unknown use-case slugs (skipped):")
        seen_unknown = {}
        for prod_id, uc in stats["unknown_use_cases"]:
            seen_unknown.setdefault(uc, []).append(prod_id)
        for uc, prods in sorted(seen_unknown.items()):
            preview = ", ".join(prods[:5])
            more = "" if len(prods) <= 5 else f" (+{len(prods) - 5} more)"
            lines.append(f"  - {uc!r}: {preview}{more}")
        lines.append("")
    if stats["categories"]["skipped"]:
        lines.append("Skipped categories:")
        for name, reason in stats["categories"]["skipped"]:
            lines.append(f"  - {name}: {reason}")
        lines.append("")
    if stats["products"]["skipped"]:
        lines.append("Skipped products:")
        for name, reason in stats["products"]["skipped"]:
            lines.append(f"  - {name}: {reason}")
        lines.append("")
    if stats["reclassifications"]:
        lines.append(f"Per-product category reclassifications ({len(stats['reclassifications'])}):")
        for r in stats["reclassifications"]:
            lines.append(
                f"  - {r['id']}: "
                f"{r['frontend_category']}/{r['frontend_subcategory']} "
                f"-> {r['frappe_category']}/{r['frappe_subcategory']}"
            )
        lines.append("")
    if stats["warnings"]:
        lines.append(f"Warnings ({len(stats['warnings'])}):")
        for prod_id, w in stats["warnings"][:50]:
            lines.append(f"  - {prod_id}: {w}")
        if len(stats["warnings"]) > 50:
            lines.append(f"  ... and {len(stats['warnings']) - 50} more")
        lines.append("")
    lines.append("Frontend fields dropped per product (not in Phase 1 schema):")
    lines.append("  " + ", ".join(DROPPED_FIELDS))
    lines.append("=" * 70)
    print("\n".join(lines))
