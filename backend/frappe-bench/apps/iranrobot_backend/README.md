# iranrobot_backend

Phase 1 of the IranRobot backend. Ships the **product catalog DocTypes only** — no APIs, no auth, no quote/wallet/rental flows. All admin operations on this data happen inside Frappe Desk.

This app is intentionally minimal: it is the schema foundation that Phase 2 (public product APIs) and Phase 3 (frontend wiring) will build on.

---

## What's inside

**DocTypes (all in module `Catalog`):**

| DocType | Type | Purpose |
|---|---|---|
| `Robot Category` | Main | Top-level form-factor categories AND their subcategories, via a self-referencing `parent_category` Link. Depth capped at 2 in Phase 1. |
| `Robot Product` | Main | The catalog product entity. Paired bilingual fields (`*_fa` / `*_en`) for every localized string. Mode flags (Buy / Rent / Procure) drive pricing rules. |
| `Robot Product Image` | Child table | Gallery rows. One row may be marked `is_hero` per product. |
| `Robot Product Spec` | Child table | Bilingual spec rows (label_fa / value_fa / label_en / value_en). |

**Controllers (`*.py`):**

- `RobotCategory.validate` — slug format, parent-not-self, depth ≤ 2, strip whitespace.
- `RobotProduct.validate` — slug + product_id format, category-is-top-level, subcategory-under-category, at least one mode, pricing-vs-mode, quote labels when no price, single hero image, rating 0–5.

**Explicitly NOT in this phase:**

- No `Quote Request`, `Procurement Request`, `Rental Request`, `Support Ticket`, `Cart`, `Order`, `Wallet`, or `Wallet Transaction` DocTypes.
- No public API endpoints (no `iranrobot_backend.api.*` whitelisted methods).
- No `Robot Use Case`, tags, highlights, editorial bullets, or `bestFor` child tables. The frontend has these on a tiny number of products; they will be added in later phases when the corresponding features land.
- No fixtures / seed data. Importing the 74 products from `../iranrobot/src/data/robots.ts` is a separate task (Phase 1.5).
- No customer-facing roles. Permissions are System Manager only on the main DocTypes. The Phase 2 API layer will mediate guest/customer access via whitelisted methods.

---

## Install (Frappe bench)

This source tree is bench-ready. To install on an existing bench:

```bash
# From your bench root (e.g. ~/frappe-bench)
bench get-app /path/to/iran-robota/iranrobot_backend
bench --site <site-name> install-app iranrobot_backend
bench --site <site-name> migrate
```

If you don't have a bench yet:

```bash
# One-time bench setup (Frappe v15 example)
bench init iranrobot-bench --frappe-branch version-15
cd iranrobot-bench
bench new-site iranrobot.local
bench get-app /path/to/iran-robota/iranrobot_backend
bench --site iranrobot.local install-app iranrobot_backend
bench start
```

Then open the Desk at `http://iranrobot.local:8000/app` and look under **Modules → Catalog**.

---

## Data model at a glance

```
Robot Category (parent_category ──┐
   ▲                              │
   └──────── self-reference ──────┘   depth ≤ 2

Robot Product
 ├─ category       → Link → Robot Category   (must be top-level)
 ├─ subcategory    → Link → Robot Category   (must have parent_category = category)
 ├─ images[]       → Robot Product Image     (≤ 1 row with is_hero)
 └─ specs[]        → Robot Product Spec      (bilingual label/value rows)
```

Bilingual fields use paired columns (`name_fa` + `name_en`, etc.). The frontend's `t(fa, en)` helper picks one based on the active language; the backend returns both so the client can switch without a round-trip.

Mode flags:
- `mode_buy = 1` requires `price_usd > 0`
- `mode_rent = 1` requires `rent_per_day_usd > 0`
- `mode_procure = 1` is the default; no price required
- At least one mode must be on

When `price_usd` is empty, both `price_label_fa` and `price_label_en` are required (default "استعلام قیمت" / "Request quote").

---

## Phase 1 acceptance criteria

- [x] App installs cleanly into a Frappe bench.
- [x] All 4 DocTypes appear under the `Catalog` module in Desk.
- [x] A System Manager can create a top-level `Robot Category`, then a subcategory pointing at it, then a `Robot Product` linking both with images + specs.
- [x] Creating a Robot Product without `category` is rejected.
- [x] Picking a subcategory whose parent is not the chosen category is rejected.
- [x] Checking Sellable (Buy) without setting `price_usd` is rejected.
- [x] Marking two image rows as `is_hero` is rejected.

---

## What comes next

Per the locked backend strategy:

| Phase | Scope |
|---|---|
| **Phase 1 (this app)** | DocTypes only |
| Phase 1.5 (separate prompt) | Seed migration from `../iranrobot/src/data/robots.ts` |
| Phase 2 | Public product APIs (`get_categories`, `get_products`, `get_product_detail`, `get_related_products`) |
| Phase 3 | Wire React frontend to those APIs (retire `src/data/*` runtime imports) |
| Phase 4 | Auth + customer identity |
| Phase 5 | Quote / Procurement / Support flows |
| Phase 6 | Customer Dashboard in React |
| Phase 7 | Wallet, Rental, Orders, Payments |

See `../iranrobot/docs/frappe-backend-requirements.md` for the full schema spec.
