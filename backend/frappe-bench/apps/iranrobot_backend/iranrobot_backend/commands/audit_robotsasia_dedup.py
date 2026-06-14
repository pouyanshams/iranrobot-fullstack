"""READ-ONLY dedup audit: RobotsAsia-imported products vs existing seed/manual.

Compares Robot Products whose product_id starts with `robotsasia-` against the
other (seed/manual) Robot Products in the SAME category, using normalized
name + brand + model token matching. Reports likely-duplicate groups with a
confidence level, provenance signals (ERPNext Item, quote/order/invoice
references), and a SAFE recommended action.

STRICTLY READ-ONLY: only SELECT/get_all/get_value. No insert/update/delete,
no commit. Not a public API; no whitelist.

    bench --site iranrobot.localhost execute \\
        iranrobot_backend.commands.audit_robotsasia_dedup.run
"""

import re
import frappe

RA_PREFIX = "robotsasia-"

# Tokens dropped during name normalization (form-factor / marketing filler).
# Pure form-factor / marketing filler only. Variant-discriminating words
# (standard, basic, premium, pro, edu, max, ultra, lite, air, w, ...) are
# intentionally KEPT so same-family-different-variant pairs are not collapsed
# into false duplicates.
_STOP = {
    "robot", "robots", "humanoid", "humanoids", "cobot", "cobots", "collaborative",
    "quadruped", "quadrupeds", "dog", "drone", "drones", "uav", "amr", "amrs",
    "autonomous", "mobile", "delivery", "courier", "industrial", "agricultural",
    "edition", "kit", "with", "the", "free", "shipping", "platform", "arm",
    "robotic", "service", "wheeled", "bipedal", "intelligent", "ai", "powered",
    "general", "purpose", "open", "source",
}
# Distinctive model-token pattern (e.g. g1, go2, s2, h1, b2, x30, lite3, fr10, rm65).
_MODEL_TOK = re.compile(r"^[a-z]{0,4}\d[\w-]*$")


def _norm_tokens(name, brand=None):
    s = (name or "").lower()
    s = re.sub(r"[^a-z0-9]+", " ", s)
    toks = [t for t in s.split() if t and t not in _STOP]
    brand_toks = set(re.sub(r"[^a-z0-9]+", " ", (brand or "").lower()).split())
    return toks, brand_toks


def _model_tokens(toks):
    return {t for t in toks if _MODEL_TOK.match(t)}


def _jaccard(a, b):
    a, b = set(a), set(b)
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _has_refs(product_id, erpnext_item):
    """Best-effort: is this product referenced anywhere commercial?"""
    refs = {}
    try:
        refs["quote_request_items"] = frappe.db.count(
            "Robot Quote Request Item", {"robot_product": product_id}
        )
    except Exception:
        refs["quote_request_items"] = None
    if erpnext_item:
        for dt in ("Quotation Item", "Sales Order Item", "Sales Invoice Item"):
            try:
                refs[dt] = frappe.db.count(dt, {"item_code": erpnext_item})
            except Exception:
                refs[dt] = None
    return refs, any(bool(v) for v in refs.values())


def _score(ra, other):
    """Return (confidence, kind, reason).

    kind is 'duplicate' (same product) or 'variant' (same family, different
    model/variant -> keep both). Near-exact name match => duplicate; shared
    family/model token but distinct name => variant.
    """
    ra_t, ra_b = _norm_tokens(ra["product_name_en"], ra["brand"])
    o_t, o_b = _norm_tokens(other["product_name_en"], other["brand"])
    brand_match = bool(ra_b and o_b and (ra_b & o_b)) or (
        (ra["brand"] or "").lower().strip() == (other["brand"] or "").lower().strip() and ra["brand"]
    )
    ra_models, o_models = _model_tokens(ra_t), _model_tokens(o_t)
    shared_models = ra_models & o_models
    jac = _jaccard(ra_t, o_t)
    # Variant/edition markers that distinguish siblings in the same family.
    variant_words = {"air", "pro", "plus", "max", "ultra", "lite", "standard",
                     "edu", "basic", "premium", "mini", "w", "d"}
    disc = (set(ra_t) ^ set(o_t)) & (ra_models | o_models | variant_words)

    if not brand_match:
        if shared_models and jac >= 0.4:
            return "low", "review", f"shared model token {sorted(shared_models)} but brand differs; jaccard={jac:.2f}"
        return None, None, None

    # Near-identical remaining name => genuine duplicate (only confident "act" case).
    if jac >= 0.85:
        return "high", "duplicate", f"brand match + near-identical name (jaccard={jac:.2f}, models={sorted(shared_models) or '—'})"
    # A meaningful relation requires a SHARED family/model token (Go2-Air vs
    # Go2-Pro) or a strong name overlap. Same brand but unrelated models
    # (S300 vs T8, X30 vs D5, H1 vs G1) are NOT a match -> no group.
    if shared_models:
        if disc:
            return "medium", "variant", f"same {sorted(shared_models)} family, different variant markers {sorted(disc)} => keep both"
        return "medium", "review", f"shared model token {sorted(shared_models)}, names differ (jaccard={jac:.2f}) -- verify duplicate vs variant"
    if jac >= 0.55:
        return "medium", "review", f"same brand, strong name overlap (jaccard={jac:.2f}), no model token -- verify"
    return None, None, None


def _img_kind(images):
    hero = next((i for i in images if i.get("is_hero")), None)
    if not hero:
        return "none"
    url = hero.get("image") or ""
    return "remote" if url.startswith("http") else "local-asset"


def run():
    cats = frappe.db.sql(
        "SELECT DISTINCT category FROM `tabRobot Product` WHERE product_id LIKE %s",
        (RA_PREFIX + "%",), as_list=True,
    )
    cats = [c[0] for c in cats]

    fields = ["name", "product_id", "product_name_en", "product_name_fa",
              "brand", "model", "category", "subcategory", "erpnext_item",
              "description_fa", "is_published"]

    report = {"by_category": {}, "summary": {}}
    totals = {"ra": 0, "other": 0, "groups": 0, "high": 0, "medium": 0, "low": 0, "keep_both_hint": 0}

    for cat in cats:
        rows = frappe.get_all("Robot Product", filters={"category": cat}, fields=fields,
                              limit_page_length=0)
        ra = [r for r in rows if (r["product_id"] or "").startswith(RA_PREFIX)]
        other = [r for r in rows if not (r["product_id"] or "").startswith(RA_PREFIX)]
        totals["ra"] += len(ra)
        totals["other"] += len(other)
        if not other:
            report["by_category"][cat] = {"robotsasia": len(ra), "existing": 0,
                                          "groups": [], "note": "no non-robotsasia products; no duplicates possible"}
            continue

        groups = []
        for r in ra:
            best = None
            for o in other:
                conf, kind, reason = _score(r, o)
                if not conf:
                    continue
                # At equal confidence prefer duplicate > review(possible dup) > variant.
                rank = {"high": 3, "medium": 2, "low": 1}[conf] + {"duplicate": 0.6, "review": 0.3, "variant": 0.0}[kind]
                if not best or rank > best["rank"]:
                    best = {"o": o, "conf": conf, "kind": kind, "reason": reason, "rank": rank}
            if not best:
                continue
            o = best["o"]
            # specs counts + provenance (read-only)
            r_specs = frappe.db.count("Robot Product Spec", {"parent": r["name"]})
            o_specs = frappe.db.count("Robot Product Spec", {"parent": o["name"]})
            r_imgs = frappe.get_all("Robot Product Image", filters={"parent": r["name"]}, fields=["image", "is_hero"])
            o_imgs = frappe.get_all("Robot Product Image", filters={"parent": o["name"]}, fields=["image", "is_hero"])
            r_refs, r_has = _has_refs(r["product_id"], r["erpnext_item"])
            o_refs, o_has = _has_refs(o["product_id"], o["erpnext_item"])

            better_image = "existing" if _img_kind(o_imgs) == "local-asset" and _img_kind(r_imgs) != "local-asset" else (
                "robotsasia" if _img_kind(r_imgs) != "none" and _img_kind(o_imgs) == "none" else "comparable")
            better_specs = "robotsasia" if r_specs > o_specs else ("existing" if o_specs > r_specs else "equal")
            better_fa = "robotsasia" if len(r["description_fa"] or "") > len(o["description_fa"] or "") else (
                "existing" if len(o["description_fa"] or "") > len(r["description_fa"] or "") else "equal")

            # Recommended action (SAFE; never delete by default)
            if best["kind"] == "variant":
                action = "keep both because they are different variants"
                canonical = "keep both (different variants)"
                totals["keep_both_hint"] += 1
            elif best["kind"] == "duplicate" and best["conf"] in ("high", "medium"):
                if o_has or r_has:
                    action = "keep existing seed/manual product, merge RobotsAsia specs/images later"
                else:
                    action = "keep existing seed/manual product, unpublish RobotsAsia duplicate later (after approval)"
                canonical = o["product_id"]
            else:
                action = "manual review required"
                canonical = "manual review"

            totals[best["conf"]] += 1
            groups.append({
                "confidence": best["conf"],
                "kind": best["kind"],
                "reason": best["reason"],
                "canonical_recommendation": canonical,
                "existing": {"product_id": o["product_id"], "name_en": o["product_name_en"],
                             "subcategory": o["subcategory"], "erpnext_item": bool(o["erpnext_item"]),
                             "has_commercial_refs": o_has, "refs": o_refs, "specs": o_specs,
                             "image": _img_kind(o_imgs), "published": bool(o["is_published"])},
                "robotsasia": {"product_id": r["product_id"], "name_en": r["product_name_en"],
                               "subcategory": r["subcategory"], "erpnext_item": bool(r["erpnext_item"]),
                               "has_commercial_refs": r_has, "specs": r_specs,
                               "image": _img_kind(r_imgs), "published": bool(r["is_published"])},
                "better_image": better_image, "better_specs": better_specs, "better_persian_copy": better_fa,
                "recommended_action": action,
            })
        report["by_category"][cat] = {"robotsasia": len(ra), "existing": len(other), "groups": groups}
        totals["groups"] += len(groups)

    report["summary"] = totals
    _print_report(report)
    return report


def _print_report(report):
    t = report["summary"]
    out = []
    out.append("=" * 74)
    out.append("RobotsAsia dedup audit (READ-ONLY)")
    out.append("=" * 74)
    out.append(f"robotsasia scanned={t['ra']}  existing(non-ra) scanned={t['other']}")
    out.append(f"match groups={t['groups']}  (high={t['high']} medium={t['medium']} low={t['low']})  variant/keep-both={t['keep_both_hint']}")
    out.append("")
    for cat, c in report["by_category"].items():
        g = c.get("groups", [])
        out.append(f"[{cat}] robotsasia={c['robotsasia']} existing={c['existing']} match_groups={len(g)}" + (f"  -- {c['note']}" if c.get("note") else ""))
        for grp in g:
            out.append(f"   ({grp['confidence']}/{grp['kind']}) {grp['robotsasia']['product_id']}")
            out.append(f"        ↔ existing {grp['existing']['product_id']}  [canonical: {grp['canonical_recommendation']}]")
            out.append(f"        reason: {grp['reason']}")
            out.append(f"        existing: specs={grp['existing']['specs']} img={grp['existing']['image']} refs={grp['existing']['has_commercial_refs']} pub={grp['existing']['published']}")
            out.append(f"        robotsasia: specs={grp['robotsasia']['specs']} img={grp['robotsasia']['image']} refs={grp['robotsasia']['has_commercial_refs']} pub={grp['robotsasia']['published']}")
            out.append(f"        better → image:{grp['better_image']} specs:{grp['better_specs']} fa:{grp['better_persian_copy']}")
            out.append(f"        action: {grp['recommended_action']}")
        out.append("")
    out.append("=" * 74)
    print("\n".join(out))
