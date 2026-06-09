"""Phase 3.5 -- Mirror Robot Category / Robot Product into ERPNext Item Group / Item.

Storefront stays the source of truth (Robot Product holds bilingual names,
taglines, hero images, etc.). ERPNext receives a lean mirror used for
commercial operations (Quotations, Sales Orders, ...). This script is the
one-way sync: Robot Product -> Item, Robot Category -> Item Group.

Run from the bench root:

    bench --site iranrobot.localhost execute \\
        iranrobot_backend.commands.sync_to_erpnext.run

Idempotent: re-running upserts (no duplicates, no skipped rows on healthy data).
"""

from typing import Optional

import frappe


COMPANY_NAME = "IranRobot"


# ===========================================================================
# Entry point
# ===========================================================================

def run():
    print("=" * 70)
    print("Phase 3.5 -- Robot Product -> ERPNext Item sync")
    print("=" * 70)

    _guard_erpnext_ready()

    stats = {
        "item_groups": {"created": [], "updated": [], "skipped": []},
        "items":       {"created": [], "updated": [], "skipped": []},
        "warnings":    [],
    }

    # Phase A: Item Groups (top-level first, then children).
    cats = frappe.get_all(
        "Robot Category",
        fields=["name", "slug", "label_fa", "label_en", "parent_category",
                "display_order", "is_published", "erpnext_item_group"],
        order_by="parent_category asc, display_order asc",
        limit_page_length=0,
    )
    # Re-order: rows with parent_category IS NULL first (top-level), then children.
    cats.sort(key=lambda c: (1 if c["parent_category"] else 0, c.get("display_order") or 0))

    print(f"\n--- Item Groups ({len(cats)} categories to mirror) ---")
    cat_to_ig = {}  # robot_category.name -> Item Group name
    for cat in cats:
        try:
            verb, ig_name = _upsert_item_group(cat, cat_to_ig)
            cat_to_ig[cat["name"]] = ig_name
            stats["item_groups"][verb].append((cat["name"], ig_name))
        except Exception as e:
            stats["item_groups"]["skipped"].append((cat["name"], f"{type(e).__name__}: {e}"))

    # Phase B: Items.
    prods = frappe.get_all(
        "Robot Product",
        fields=["name", "product_id", "slug", "product_name_en", "product_name_fa",
                "category", "subcategory", "brand", "model",
                "origin_en", "description_en",
                "in_stock", "lead_time_days",
                "mode_buy", "mode_rent", "mode_procure",
                "price_usd", "rent_per_day_usd",
                "is_published", "erpnext_item"],
        order_by="product_id asc",
        limit_page_length=0,
    )
    print(f"\n--- Items ({len(prods)} products to mirror) ---")
    for prod in prods:
        try:
            verb, item_code = _upsert_item(prod, cat_to_ig)
            stats["items"][verb].append((prod["product_id"], item_code))
        except Exception as e:
            stats["items"]["skipped"].append((prod["product_id"], f"{type(e).__name__}: {e}"))

    frappe.db.commit()

    summary = _print_report(stats)
    return summary


# ===========================================================================
# Item Group upsert
# ===========================================================================

def _upsert_item_group(cat: dict, cat_to_ig: dict) -> tuple[str, str]:
    """Upsert an Item Group mirroring a Robot Category. Returns ('created'|'updated', item_group_name)."""
    ig_name = (cat["label_en"] or cat["slug"]).strip()
    parent_ig = cat_to_ig.get(cat["parent_category"]) if cat["parent_category"] else "All Item Groups"
    is_group = 1 if _has_children(cat["name"]) else 0

    fields = {
        "item_group_name": ig_name,
        "parent_item_group": parent_ig,
        "is_group": is_group,
    }

    # 1. Prefer the previously-saved link on Robot Category.
    target = cat.get("erpnext_item_group")
    if target and frappe.db.exists("Item Group", target):
        ig = frappe.get_doc("Item Group", target)
        for k, v in fields.items():
            ig.set(k, v)
        ig.save(ignore_permissions=True)
        _set_field("Robot Category", cat["name"], "erpnext_item_group", ig.name)
        return "updated", ig.name

    # 2. Otherwise look up by the canonical name.
    existing = frappe.db.exists("Item Group", ig_name)
    if existing:
        ig = frappe.get_doc("Item Group", existing)
        for k, v in fields.items():
            ig.set(k, v)
        ig.save(ignore_permissions=True)
        _set_field("Robot Category", cat["name"], "erpnext_item_group", ig.name)
        return "updated", ig.name

    # 3. Create.
    ig = frappe.get_doc({"doctype": "Item Group", **fields})
    ig.insert(ignore_permissions=True)
    _set_field("Robot Category", cat["name"], "erpnext_item_group", ig.name)
    return "created", ig.name


def _has_children(robot_category_name: str) -> bool:
    return bool(frappe.db.exists("Robot Category", {"parent_category": robot_category_name}))


# ===========================================================================
# Item upsert
# ===========================================================================

def _upsert_item(prod: dict, cat_to_ig: dict) -> tuple[str, str]:
    """Upsert an Item mirroring a Robot Product. Returns ('created'|'updated', item_code)."""
    item_code = prod["product_id"]
    item_name = (prod["product_name_en"] or prod["product_name_fa"] or item_code).strip()
    if len(item_name) > 140:
        item_name = item_name[:137] + "..."

    # Pick the Item Group: prefer the subcategory mirror, then the category mirror.
    item_group = (
        (prod.get("subcategory") and cat_to_ig.get(prod["subcategory"]))
        or (prod.get("category") and cat_to_ig.get(prod["category"]))
        or "All Item Groups"
    )

    standard_rate = float(prod["price_usd"]) if prod.get("price_usd") else 0.0

    fields = {
        "item_code": item_code,
        "item_name": item_name,
        "item_group": item_group,
        "stock_uom": "Nos",
        "is_stock_item": 0,             # no inventory tracking until Phase 7 rental
        "has_serial_no": 0,
        "is_sales_item": 1,
        "is_purchase_item": 0,
        "disabled": 0 if prod.get("is_published") else 1,
        "country_of_origin": prod.get("origin_en") or None,
        "description": prod.get("description_en") or item_name,
        "standard_rate": standard_rate,
    }

    # 1. Prefer the previously-saved link on Robot Product.
    target = prod.get("erpnext_item")
    if target and frappe.db.exists("Item", target):
        item = frappe.get_doc("Item", target)
        for k, v in fields.items():
            item.set(k, v)
        item.save(ignore_permissions=True)
        _set_field("Robot Product", prod["name"], "erpnext_item", item.name)
        return "updated", item.name

    # 2. Otherwise look up by item_code (the canonical Item identifier).
    existing = frappe.db.exists("Item", item_code)
    if existing:
        item = frappe.get_doc("Item", existing)
        for k, v in fields.items():
            item.set(k, v)
        item.save(ignore_permissions=True)
        _set_field("Robot Product", prod["name"], "erpnext_item", item.name)
        return "updated", item.name

    # 3. Create.
    item = frappe.get_doc({"doctype": "Item", **fields})
    item.insert(ignore_permissions=True)
    _set_field("Robot Product", prod["name"], "erpnext_item", item.name)
    return "created", item.name


# ===========================================================================
# Helpers
# ===========================================================================

def _set_field(doctype: str, name: str, fieldname: str, value: Optional[str]):
    """Persist a single field on a Document, bypassing validate() (we don't want the
    slug-normalizer + parent-depth checks to re-fire just to set a Link target)."""
    frappe.db.set_value(doctype, name, fieldname, value, update_modified=False)


def _guard_erpnext_ready():
    if not frappe.db.exists("DocType", "Item"):
        raise RuntimeError("ERPNext is not installed -- run `bench install-app erpnext` first.")
    if not frappe.db.exists("Company", COMPANY_NAME):
        raise RuntimeError(
            f"Company '{COMPANY_NAME}' not found -- run "
            "`bench --site iranrobot.localhost execute "
            "iranrobot_backend.commands.erpnext_bootstrap.run` first."
        )
    if not frappe.db.exists("Item Group", "All Item Groups"):
        raise RuntimeError("Default 'All Item Groups' missing -- ERPNext setup wizard not complete.")


def _print_report(stats: dict):
    ig = stats["item_groups"]
    it = stats["items"]

    def n(bucket): return {k: len(v) for k, v in bucket.items()}

    summary = {
        "item_groups": n(ig),
        "items": n(it),
        "warnings": len(stats["warnings"]),
    }

    print("\n" + "=" * 70)
    print("REPORT")
    print("=" * 70)
    print(f"Item Groups  created={summary['item_groups']['created']}  "
          f"updated={summary['item_groups']['updated']}  "
          f"skipped={summary['item_groups']['skipped']}")
    print(f"Items        created={summary['items']['created']}  "
          f"updated={summary['items']['updated']}  "
          f"skipped={summary['items']['skipped']}")

    if ig["skipped"]:
        print("\nSkipped Item Groups:")
        for name, reason in ig["skipped"]:
            print(f"  - {name}: {reason}")
    if it["skipped"]:
        print("\nSkipped Items:")
        for name, reason in it["skipped"]:
            print(f"  - {name}: {reason}")
    if stats["warnings"]:
        print(f"\nWarnings ({len(stats['warnings'])}):")
        for w in stats["warnings"][:20]:
            print(f"  - {w}")

    print("=" * 70)
    return summary
