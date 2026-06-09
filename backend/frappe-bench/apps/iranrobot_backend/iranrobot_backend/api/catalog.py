"""Phase 2 -- Public read-only catalog APIs.

All methods are guest-readable (`allow_guest=True`). They expose ONLY
`is_published=1` records and ONLY customer-safe fields (no internal notes,
no owner/modified_by, no audit log fields).

Dotted paths for invocation:
    iranrobot_backend.api.catalog.get_categories
    iranrobot_backend.api.catalog.get_products
    iranrobot_backend.api.catalog.get_product_detail
    iranrobot_backend.api.catalog.get_featured_product
    iranrobot_backend.api.catalog.get_homepage_catalog

Frappe wraps method return values in `{"message": <value>}` for /api/method/
calls; clients should unwrap one level to reach the {"ok": ..., "data": ...}
envelope.
"""

import frappe

from iranrobot_backend.api._response import ok, err


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_LIMIT = 24
MAX_LIMIT = 100
RELATED_PRODUCT_LIMIT = 4

# Lightweight card data returned in list responses + as the base of detail.
PRODUCT_CARD_FIELDS = [
    "product_id",
    "slug",
    "product_name_fa",
    "product_name_en",
    "tagline_fa",
    "tagline_en",
    "brand",
    "model",
    "category",
    "subcategory",
    "price_usd",
    "price_label_fa",
    "price_label_en",
    "in_stock",
    "lead_time_days",
    "is_new_arrival",
    "is_featured",
    "rating",
    "mode_buy",
    "mode_rent",
    "mode_procure",
    "rent_per_day_usd",
    "display_order",
]

# PDP-only extra fields layered on top of the card.
PRODUCT_DETAIL_EXTRA_FIELDS = [
    "description_fa",
    "description_en",
    "origin_fa",
    "origin_en",
]

CATEGORY_FIELDS = [
    "name",
    "slug",
    "label_fa",
    "label_en",
    "parent_category",
    "display_order",
    "is_published",
    "icon",
    "image",
]

BOOL_FIELDS_ON_PRODUCT = (
    "in_stock",
    "is_new_arrival",
    "is_featured",
    "mode_buy",
    "mode_rent",
    "mode_procure",
)

VALID_SORTS = {
    "display_order": "display_order asc, product_name_en asc",
    "newest":        "creation desc",
    "oldest":        "creation asc",
    "name_en":       "product_name_en asc",
    "name_fa":       "product_name_fa asc",
    "price_asc":     "price_usd asc",
    "price_desc":    "price_usd desc",
}

# Frontend "virtual" categories that don't correspond to a Robot Category row
# but to a flag on Robot Product. Currently only `new` / `new-arrivals`.
VIRTUAL_CATEGORIES = {"new", "new-arrivals"}


# ---------------------------------------------------------------------------
# Tiny query-string coercion helpers
# (Frappe puts query params into form_dict as strings; the whitelist decorator
# passes them to our kwargs as strings too, so we coerce defensively.)
# ---------------------------------------------------------------------------

def _to_int(val, default=None):
    if val is None or val == "":
        return default
    try:
        return int(val)
    except (TypeError, ValueError):
        return default


def _to_bool(val, default=None):
    if val is None or val == "":
        return default
    if isinstance(val, bool):
        return val
    s = str(val).strip().lower()
    if s in ("1", "true", "yes", "y", "on"):
        return True
    if s in ("0", "false", "no", "n", "off"):
        return False
    return default


def _clamp_limit(limit):
    """Bound limit to [1, MAX_LIMIT]; fall back to DEFAULT_LIMIT on bad input."""
    if limit is None or limit < 1:
        return DEFAULT_LIMIT
    return min(limit, MAX_LIMIT)


def _coerce_product_booleans(prod):
    """Mutates the dict: convert 0/1 ints to Python bools for the boolean fields."""
    for k in BOOL_FIELDS_ON_PRODUCT:
        if k in prod:
            prod[k] = bool(prod.get(k))
    return prod


def _attach_hero_images(products):
    """Mutate products in place to add `hero_image`. Two SQL queries total
    regardless of list length, to avoid N+1.

    Hero selection order:
      1. The row with is_hero=1, if any
      2. Else the first row by idx
      3. Else None
    """
    if not products:
        return products
    product_ids = [p["product_id"] for p in products]

    hero_rows = frappe.db.sql(
        """
        SELECT parent, image
        FROM `tabRobot Product Image`
        WHERE parent IN %(ids)s AND is_hero = 1
        """,
        {"ids": tuple(product_ids)},
        as_dict=True,
    )
    hero_by_parent = {r["parent"]: r["image"] for r in hero_rows}

    missing = [pid for pid in product_ids if pid not in hero_by_parent]
    if missing:
        fallback_rows = frappe.db.sql(
            """
            SELECT parent, image
            FROM `tabRobot Product Image`
            WHERE parent IN %(ids)s
            ORDER BY parent, idx
            """,
            {"ids": tuple(missing)},
            as_dict=True,
        )
        for r in fallback_rows:
            hero_by_parent.setdefault(r["parent"], r["image"])

    for p in products:
        p["hero_image"] = hero_by_parent.get(p["product_id"])
    return products


def _decorate_cards(products):
    """Apply the standard list-card decoration: bools + hero_image."""
    for p in products:
        _coerce_product_booleans(p)
    _attach_hero_images(products)
    return products


# ===========================================================================
# 1. get_categories
# ===========================================================================

@frappe.whitelist(allow_guest=True)
def get_categories():
    """Return the published category tree with product counts.

    Shape:
        {
          "categories": [
            { ...top-level cat fields..., "children": [ { ...sub fields... }, ... ] },
            ...
          ],
          "count": N (top-level count)
        }
    """
    rows = frappe.get_all(
        "Robot Category",
        filters={"is_published": 1},
        fields=CATEGORY_FIELDS,
        order_by="display_order asc, label_en asc",
        limit_page_length=0,
    )

    # Per-category product counts (only published products counted).
    # One GROUP BY sweep covers both top-level and sub buckets.
    counts_by_top = {}
    counts_by_sub = {}
    grouped = frappe.db.sql(
        """
        SELECT category, subcategory, COUNT(*) AS n
        FROM `tabRobot Product`
        WHERE is_published = 1
        GROUP BY category, subcategory
        """,
        as_dict=True,
    )
    for g in grouped:
        if g["category"]:
            counts_by_top[g["category"]] = counts_by_top.get(g["category"], 0) + g["n"]
        if g["subcategory"]:
            counts_by_sub[g["subcategory"]] = counts_by_sub.get(g["subcategory"], 0) + g["n"]

    # Attach product_count + coerce booleans.
    for row in rows:
        row["is_published"] = bool(row.get("is_published"))
        if row["parent_category"]:
            row["product_count"] = counts_by_sub.get(row["name"], 0)
        else:
            row["product_count"] = counts_by_top.get(row["name"], 0)

    # Build the 2-level tree.
    children_by_parent = {}
    for row in rows:
        if row["parent_category"]:
            children_by_parent.setdefault(row["parent_category"], []).append(row)

    tree = []
    for row in rows:
        if row["parent_category"] is None:
            kids = children_by_parent.get(row["name"], [])
            kids.sort(key=lambda c: (c.get("display_order") or 0, c.get("label_en") or ""))
            for k in kids:
                k["children"] = []  # depth is capped at 2 per Phase 1 schema
            row["children"] = kids
            tree.append(row)

    return ok({"categories": tree, "count": len(tree)})


# ===========================================================================
# 2. get_products
# ===========================================================================

@frappe.whitelist(allow_guest=True)
def get_products(
    category=None,
    subcategory=None,
    use_case=None,
    has_use_case=None,
    is_new_arrival=None,
    is_featured=None,
    search=None,
    limit=None,
    page=None,
    offset=None,
    sort=None,
):
    """PLP / shop list with filters, search, sort, and pagination.

    Query parameters (all optional):
      category       -- top-level category slug, OR a virtual name ("new" / "new-arrivals")
      subcategory    -- subcategory slug
      use_case       -- Robot Use Case slug (e.g. inspection, warehouse, security).
                        Filters products that have at least one matching row in
                        the use_cases child table. Unknown slugs return an empty
                        list, NOT an error.
      has_use_case   -- truthy: only products with at least one use case row
                        (powers the parent #/catalog/solutions route).
      is_new_arrival -- truthy filter
      is_featured    -- truthy filter
      search         -- substring match on name_fa, name_en, brand, slug
      limit          -- default 24, max 100
      page           -- 1-indexed page number (ignored if offset is provided)
      offset         -- 0-indexed row offset (takes precedence over page)
      sort           -- one of: display_order (default), newest, oldest, name_en,
                        name_fa, price_asc, price_desc
    """
    limit = _clamp_limit(_to_int(limit, DEFAULT_LIMIT))
    page = max(_to_int(page, 1) or 1, 1)
    explicit_offset = _to_int(offset, None)
    start = explicit_offset if (explicit_offset is not None and explicit_offset >= 0) else (page - 1) * limit

    sort_key = (sort or "display_order").strip().lower() if sort else "display_order"
    if sort_key not in VALID_SORTS:
        return err(
            "INVALID_SORT",
            f"Unknown sort: {sort_key!r}. Allowed: {sorted(VALID_SORTS.keys())}",
        )
    order_by = VALID_SORTS[sort_key]

    filters = {"is_published": 1}

    # Virtual category resolution must happen before plain category mapping.
    if category and category.strip().lower() in VIRTUAL_CATEGORIES:
        filters["is_new_arrival"] = 1
    elif category:
        filters["category"] = category.strip()

    if subcategory:
        filters["subcategory"] = subcategory.strip()

    new_arr = _to_bool(is_new_arrival)
    if new_arr is not None:
        filters["is_new_arrival"] = 1 if new_arr else 0

    feat = _to_bool(is_featured)
    if feat is not None:
        filters["is_featured"] = 1 if feat else 0

    or_filters = None
    if search:
        s = str(search).strip()
        if s:
            like = f"%{s}%"
            or_filters = [
                ["product_name_fa", "like", like],
                ["product_name_en", "like", like],
                ["brand",           "like", like],
                ["slug",            "like", like],
            ]

    # Use-case filter: switches the query to an explicit SQL form that joins
    # against the Robot Product Use Case child table. We only take this path
    # when needed because the simple frappe.get_all path covers every other
    # filter combination at full speed.
    uc_value = (use_case or "").strip() if isinstance(use_case, str) else use_case
    has_uc = _to_bool(has_use_case)
    if uc_value or has_uc:
        return _get_products_with_use_case(
            filters=filters,
            or_filters=or_filters,
            use_case=uc_value or None,
            has_use_case_any=bool(has_uc),
            order_by=order_by,
            start=start,
            limit=limit,
            page=page,
        )

    # Total count (for has_next + UI display). Two paths because frappe.db.count
    # doesn't accept or_filters.
    if or_filters:
        total = len(frappe.get_all(
            "Robot Product",
            filters=filters,
            or_filters=or_filters,
            fields=["name"],
            limit_page_length=0,
        ))
    else:
        total = frappe.db.count("Robot Product", filters=filters)

    rows = frappe.get_all(
        "Robot Product",
        filters=filters,
        or_filters=or_filters,
        fields=PRODUCT_CARD_FIELDS,
        order_by=order_by,
        start=start,
        page_length=limit,
    )
    _decorate_cards(rows)

    return ok({
        "products": rows,
        "pagination": {
            "total":    total,
            "page":     page,
            "limit":    limit,
            "offset":   start,
            "returned": len(rows),
            "has_next": (start + len(rows)) < total,
        },
        "filters_applied": {
            "category":       category,
            "subcategory":    subcategory,
            "use_case":       None,
            "has_use_case":   False,
            "is_new_arrival": new_arr,
            "is_featured":    feat,
            "search":         search,
            "sort":           sort_key,
        },
    })


# ---------------------------------------------------------------------------
# Use-case helpers
# ---------------------------------------------------------------------------

# `category`, `subcategory`, and `is_new_arrival` / `is_featured` are
# whitelisted scalar columns on `tabRobot Product`. The use-case branch
# composes a parameterised SQL string from these known columns only; user
# input is always bound via `%s`, never concatenated.
_SCALAR_FILTER_COLUMNS = {
    "is_published":   "rp.is_published",
    "category":       "rp.category",
    "subcategory":    "rp.subcategory",
    "is_new_arrival": "rp.is_new_arrival",
    "is_featured":    "rp.is_featured",
}

# Map of sort-key -> SQL ORDER BY fragment for the use-case query. Same
# semantics as VALID_SORTS but with the explicit `rp.` table alias.
_VALID_SORTS_PREFIXED = {
    "display_order": "rp.display_order asc, rp.product_name_en asc",
    "newest":        "rp.creation desc",
    "oldest":        "rp.creation asc",
    "name_en":       "rp.product_name_en asc",
    "name_fa":       "rp.product_name_fa asc",
    "price_asc":     "rp.price_usd asc",
    "price_desc":    "rp.price_usd desc",
}


def _get_products_with_use_case(
    *,
    filters,           # dict[str, scalar] -- scalar filters from get_products
    or_filters,        # list of [col, op, val] entries for the search clause, or None
    use_case,          # specific slug, or None when has_use_case_any is True
    has_use_case_any,  # bool: True for `has_use_case=1` (parent solutions route)
    order_by,          # original VALID_SORTS string (we re-resolve with rp. alias)
    start,
    limit,
    page,
):
    """Return the `ok({...})` envelope for a product list filtered by use case.

    Uses an INNER JOIN on the Robot Product Use Case child table. The query
    is fully parameterised: every value (including the use_case slug, the
    search like-pattern, and every scalar filter) is bound via `%s`. SELECT
    DISTINCT and COUNT(DISTINCT) guard against duplicates if a product has
    several rows that match (it can't here since one use_case per row, but
    DISTINCT keeps the contract obvious).
    """
    # Resolve the ORDER BY fragment. We rebuild it from the same key the
    # caller validated so we can use the rp. alias. Any unknown key would
    # have been rejected upstream.
    sort_key_inv = {v: k for k, v in VALID_SORTS.items()}
    sort_key = sort_key_inv.get(order_by, "display_order")
    order_by_sql = _VALID_SORTS_PREFIXED[sort_key]

    where_clauses = []
    params = []

    # Always: a child row must exist.
    where_clauses.append("rpuc.parent = rp.name")
    where_clauses.append("rpuc.parenttype = %s")
    params.append("Robot Product")

    # Specific use case OR any use case.
    if use_case:
        where_clauses.append("rpuc.use_case = %s")
        params.append(use_case)

    # Scalar filters: only known whitelisted columns can be used.
    for k, v in filters.items():
        col = _SCALAR_FILTER_COLUMNS.get(k)
        if col is None:
            continue  # silently ignore unknown filter keys
        where_clauses.append(f"{col} = %s")
        params.append(v)

    # Search OR-clause: each entry is [column, "like", value]; columns are
    # whitelisted so the SQL string is safe; values are bound.
    if or_filters:
        like_columns = {
            "product_name_fa": "rp.product_name_fa",
            "product_name_en": "rp.product_name_en",
            "brand":           "rp.brand",
            "slug":            "rp.slug",
        }
        like_parts = []
        for col_name, _op, val in or_filters:
            col_sql = like_columns.get(col_name)
            if col_sql is None:
                continue
            like_parts.append(f"{col_sql} LIKE %s")
            params.append(val)
        if like_parts:
            where_clauses.append("(" + " OR ".join(like_parts) + ")")

    where_sql = " AND ".join(where_clauses)

    # ---- count ----
    count_sql = (
        "SELECT COUNT(DISTINCT rp.name) "
        "FROM `tabRobot Product` rp "
        "JOIN `tabRobot Product Use Case` rpuc ON rpuc.parent = rp.name "
        f"WHERE {where_sql}"
    )
    total_row = frappe.db.sql(count_sql, tuple(params))
    total = int(total_row[0][0]) if total_row and total_row[0] else 0

    # ---- page ----
    select_cols = ", ".join(f"rp.{c}" for c in PRODUCT_CARD_FIELDS)
    page_sql = (
        f"SELECT DISTINCT {select_cols} "
        "FROM `tabRobot Product` rp "
        "JOIN `tabRobot Product Use Case` rpuc ON rpuc.parent = rp.name "
        f"WHERE {where_sql} "
        f"ORDER BY {order_by_sql} "
        "LIMIT %s OFFSET %s"
    )
    page_params = tuple(params) + (int(limit), int(start))
    rows = frappe.db.sql(page_sql, page_params, as_dict=True)
    rows = [dict(r) for r in rows]
    _decorate_cards(rows)

    return ok({
        "products": rows,
        "pagination": {
            "total":    total,
            "page":     page,
            "limit":    limit,
            "offset":   start,
            "returned": len(rows),
            "has_next": (start + len(rows)) < total,
        },
        "filters_applied": {
            "category":       filters.get("category"),
            "subcategory":    filters.get("subcategory"),
            "use_case":       use_case,
            "has_use_case":   has_use_case_any if not use_case else False,
            "is_new_arrival": filters.get("is_new_arrival"),
            "is_featured":    filters.get("is_featured"),
            "search":         None,
            "sort":           sort_key,
        },
    })


# ===========================================================================
# 3. get_product_detail
# ===========================================================================

@frappe.whitelist(allow_guest=True)
def get_product_detail(slug=None):
    """Return full PDP data by `slug`.

    Includes: all card fields + descriptions + origin + every image row + every
    spec row + up to 4 related products (same subcategory first, then same
    category, current product excluded).
    """
    if not slug:
        return err("INVALID_INPUT", "slug is required")

    rows = frappe.get_all(
        "Robot Product",
        filters={"slug": slug.strip(), "is_published": 1},
        fields=PRODUCT_CARD_FIELDS + PRODUCT_DETAIL_EXTRA_FIELDS,
        limit_page_length=1,
    )
    if not rows:
        return err("NOT_FOUND", f"No published product found for slug: {slug!r}")

    prod = rows[0]
    _coerce_product_booleans(prod)
    _attach_hero_images([prod])

    # Image gallery (full rows, idx order).
    images = frappe.get_all(
        "Robot Product Image",
        filters={"parent": prod["product_id"]},
        fields=["image", "is_hero", "alt_fa", "alt_en"],
        order_by="idx asc",
        limit_page_length=0,
    )
    for img in images:
        img["is_hero"] = bool(img.get("is_hero"))
    prod["images"] = images

    # Spec rows (bilingual label/value, idx order).
    prod["specs"] = frappe.get_all(
        "Robot Product Spec",
        filters={"parent": prod["product_id"]},
        fields=["label_fa", "value_fa", "label_en", "value_en"],
        order_by="idx asc",
        limit_page_length=0,
    )

    # Related: prefer same subcategory, fall back to same category.
    related = []
    seen = {prod["product_id"]}

    if prod.get("subcategory"):
        same_sub = frappe.get_all(
            "Robot Product",
            filters={
                "is_published": 1,
                "subcategory": prod["subcategory"],
                "name": ["!=", prod["product_id"]],
            },
            fields=PRODUCT_CARD_FIELDS,
            order_by="in_stock desc, creation desc",
            limit_page_length=RELATED_PRODUCT_LIMIT,
        )
        for r in same_sub:
            if r["product_id"] not in seen:
                related.append(r)
                seen.add(r["product_id"])

    if len(related) < RELATED_PRODUCT_LIMIT and prod.get("category"):
        need = RELATED_PRODUCT_LIMIT - len(related)
        more = frappe.get_all(
            "Robot Product",
            filters={
                "is_published": 1,
                "category": prod["category"],
                "name": ["!=", prod["product_id"]],
            },
            fields=PRODUCT_CARD_FIELDS,
            order_by="in_stock desc, creation desc",
            limit_page_length=need * 3,  # over-fetch to survive dedup
        )
        for r in more:
            if r["product_id"] not in seen:
                related.append(r)
                seen.add(r["product_id"])
                if len(related) >= RELATED_PRODUCT_LIMIT:
                    break

    _decorate_cards(related)
    prod["related_products"] = related[:RELATED_PRODUCT_LIMIT]
    return ok({"product": prod})


# ===========================================================================
# 4. get_featured_product
# ===========================================================================

@frappe.whitelist(allow_guest=True)
def get_featured_product():
    """Return the homepage featured product.

    Priority: first `is_featured=1, is_published=1` product (by display_order asc,
    creation desc). Falls back to the first published product if none flagged.
    """
    rows = frappe.get_all(
        "Robot Product",
        filters={"is_published": 1, "is_featured": 1},
        fields=PRODUCT_CARD_FIELDS + PRODUCT_DETAIL_EXTRA_FIELDS,
        order_by="display_order asc, creation desc",
        limit_page_length=1,
    )
    if not rows:
        rows = frappe.get_all(
            "Robot Product",
            filters={"is_published": 1},
            fields=PRODUCT_CARD_FIELDS + PRODUCT_DETAIL_EXTRA_FIELDS,
            order_by="display_order asc, creation desc",
            limit_page_length=1,
        )
    if not rows:
        return err("NOT_FOUND", "No published products available")

    prod = rows[0]
    _coerce_product_booleans(prod)
    _attach_hero_images([prod])
    return ok({"product": prod})


# ===========================================================================
# 5. get_homepage_catalog (bundled convenience method)
# ===========================================================================

@frappe.whitelist(allow_guest=True)
def get_homepage_catalog():
    """Return featured + new arrivals + category tree in one call.

    Saves the frontend three round-trips when rendering the homepage. The
    underlying queries are the same as the individual endpoints.
    """
    featured_resp = get_featured_product()
    featured = featured_resp["data"]["product"] if featured_resp.get("ok") else None

    new_arrivals_resp = get_products(is_new_arrival="1", limit="8", sort="display_order")
    new_arrivals = new_arrivals_resp["data"]["products"] if new_arrivals_resp.get("ok") else []

    cats_resp = get_categories()
    categories = cats_resp["data"]["categories"] if cats_resp.get("ok") else []

    return ok({
        "featured":     featured,
        "new_arrivals": new_arrivals,
        "categories":   categories,
        "counts": {
            "categories_top_level": len(categories),
            "new_arrivals":         len(new_arrivals),
        },
    })
