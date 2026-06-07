"""Backend smoke for the catalog use-case filter (Solutions axis).

Covers:
  - get_products?use_case=<slug>  returns > 0 products if seeded
  - get_products?has_use_case=1   returns the union (>= each per-use-case count)
  - get_products?category=<slug>  regressions (drones, humanoids)
  - get_products?subcategory=<slug> regression
  - search + use_case combined
  - sort + use_case combined
  - pagination + use_case combined
  - category + use_case combined
  - use_case=does-not-exist returns empty, not an error
  - response shape carries `filters_applied.use_case`
"""

import http.client, json, sys, urllib.parse


HOST, PORT = "iranrobot.localhost", 8000


def call(path):
    conn = http.client.HTTPConnection(HOST, PORT, timeout=15)
    conn.request("GET", path, headers={"Accept": "application/json"})
    resp = conn.getresponse()
    body = resp.read().decode("utf-8", errors="replace")
    try:
        return resp.status, json.loads(body)
    except Exception:
        return resp.status, {"_raw": body[:300]}


def msg_data(body):
    return (body or {}).get("message", {}).get("data") or {}


def msg_ok(body):
    return ((body or {}).get("message") or {}).get("ok") is True


PASS, FAIL = [], []


def check(label, ok, extra=""):
    if ok:
        PASS.append(label)
        print(f"  ✅ {label}")
    else:
        FAIL.append(label)
        print(f"  ❌ {label} {extra}")


def get_products(qs):
    return call(f"/api/method/iranrobot_backend.api.catalog.get_products?{qs}")


def count_for(qs):
    st, body = get_products(qs)
    return (msg_data(body).get("pagination") or {}).get("total", 0)


print("============================================================")
print("Catalog Use-Case smoke")
print("============================================================\n")


# ---------------------------------------------------------------- [1] per-use-case
print("[1] per-use-case filtering")
inspection_count = count_for("use_case=inspection&limit=100")
security_count   = count_for("use_case=security&limit=100")
warehouse_count  = count_for("use_case=warehouse&limit=100")
education_count  = count_for("use_case=education&limit=100")
healthcare_count = count_for("use_case=healthcare&limit=100")
custom_count     = count_for("use_case=custom&limit=100")
print(f"    inspection={inspection_count} security={security_count} warehouse={warehouse_count} "
      f"education={education_count} healthcare={healthcare_count} custom={custom_count}")
check("use_case=inspection returns > 0", inspection_count > 0)
check("use_case=security returns > 0", security_count > 0)
check("use_case=warehouse returns > 0", warehouse_count > 0)
check("use_case=education returns > 0", education_count > 0)


# ---------------------------------------------------------------- [2] has_use_case (parent solutions)
print("\n[2] has_use_case=1 (parent solutions route)")
any_count = count_for("has_use_case=1&limit=100")
print(f"    has_use_case=1 total = {any_count}")
check(
    "has_use_case=1 >= every per-use-case count",
    any_count >= max(inspection_count, security_count, warehouse_count,
                     education_count, healthcare_count, custom_count, 1),
    extra=f"got {any_count}",
)
check(
    "has_use_case=1 <= sum of per-use-case counts (union, no duplicates)",
    any_count <= (inspection_count + security_count + warehouse_count +
                  education_count + healthcare_count + custom_count),
    extra=f"got {any_count}",
)


# ---------------------------------------------------------------- [3] category regressions
print("\n[3] category regressions")
drones_count    = count_for("category=drones&limit=100")
humanoids_count = count_for("category=humanoids&limit=100")
print(f"    drones={drones_count} humanoids={humanoids_count}")
check("category=drones still returns > 0", drones_count > 0)
check("category=humanoids still returns > 0", humanoids_count > 0)


# ---------------------------------------------------------------- [4] subcategory regression
print("\n[4] subcategory regression")
bipedal_count = count_for("subcategory=bipedal-humanoids&limit=100")
print(f"    bipedal-humanoids={bipedal_count}")
check("subcategory=bipedal-humanoids still returns > 0", bipedal_count > 0)


# ---------------------------------------------------------------- [5] combined search + use_case
print("\n[5] combined: search + use_case")
# Common terms that exist on inspection products in the catalog. We don't
# assert >0 strictly (depends on naming), but the call must not error and
# must return a numeric total.
st, body = get_products("use_case=inspection&search=robot&limit=100")
check("use_case + search returns ok envelope", msg_ok(body), extra=f"body={body}")
pgn = msg_data(body).get("pagination") or {}
check("use_case + search response has numeric total", isinstance(pgn.get("total"), int))


# ---------------------------------------------------------------- [6] combined sort + use_case
print("\n[6] combined: sort + use_case")
st, body = get_products("use_case=inspection&sort=name_en&limit=100")
data = msg_data(body)
items = data.get("products") or []
check("use_case + sort=name_en returns ok envelope", msg_ok(body))
if len(items) >= 2:
    names = [(it.get("product_name_en") or "") for it in items]
    sorted_names = sorted(names, key=lambda s: s.lower())
    check("use_case + sort=name_en results are alphabetical", names == sorted_names,
          extra=f"first 3: {names[:3]}")


# ---------------------------------------------------------------- [7] pagination + use_case
print("\n[7] pagination + use_case")
st, body = get_products("use_case=inspection&limit=2&page=1")
data = msg_data(body)
pgn = data.get("pagination") or {}
returned = len(data.get("products") or [])
check("use_case + limit=2 returns <= 2 rows", returned <= 2, extra=f"got {returned}")
check("use_case + limit=2 sets has_next correctly",
      pgn.get("has_next") == ((pgn.get("offset", 0) + returned) < pgn.get("total", 0)))


# ---------------------------------------------------------------- [8] combined category + use_case
print("\n[8] combined: category + use_case")
# We pick a category likely to overlap with a use case (quadrupeds + inspection)
both_count = count_for("category=quadrupeds&use_case=inspection&limit=100")
print(f"    category=quadrupeds + use_case=inspection = {both_count}")
quad_count = count_for("category=quadrupeds&limit=100")
check("category + use_case <= category-only count (intersection)",
      both_count <= quad_count, extra=f"both={both_count} quad={quad_count}")
check("category + use_case <= use_case-only count (intersection)",
      both_count <= inspection_count, extra=f"both={both_count} insp={inspection_count}")


# ---------------------------------------------------------------- [9] unknown use_case
print("\n[9] unknown use_case returns empty, not error")
st, body = get_products("use_case=does-not-exist&limit=100")
data = msg_data(body)
check("unknown use_case envelope ok=true", msg_ok(body))
check("unknown use_case total=0",
      (data.get("pagination") or {}).get("total") == 0)
check("unknown use_case products=[]",
      (data.get("products") or []) == [])


# ---------------------------------------------------------------- [10] response carries filters_applied
print("\n[10] filters_applied surfaces use_case + has_use_case")
st, body = get_products("use_case=inspection&limit=1")
fa = msg_data(body).get("filters_applied") or {}
check("filters_applied.use_case == 'inspection'", fa.get("use_case") == "inspection")
st, body = get_products("has_use_case=1&limit=1")
fa = msg_data(body).get("filters_applied") or {}
check("filters_applied.has_use_case == True (when has_use_case=1)",
      fa.get("has_use_case") is True)


# ---------------------------------------------------------------- summary
print()
print(f"{len(PASS)}/{len(PASS) + len(FAIL)} PASSED")
sys.exit(0 if not FAIL else 1)
