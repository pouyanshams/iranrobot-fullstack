"""Safe, targeted cleanup: clear brand-logo hero images on two RobotsAsia UGVs.

QA found that `robotsasia-ugv-guoxing-eod-gxbox510` and
`robotsasia-ugv-guoxing-mower-kt500` had the shared Guo Xing brand LOGO
(`guo_23.png` / `guo_27.png`, byte-identical) stored as their hero image
instead of a product photo. This clears ONLY the images child table for those
two products IF the hero is one of the known logo files, so the frontend falls
back to the default product illustration.

Hard safety:
  * Only the two explicitly-approved product_ids are ever considered.
  * A row is cleared ONLY when its hero image basename is a known logo
    (`_LOGO_BASENAMES`). If the hero is anything else, it is LEFT UNCHANGED and
    reported (per "if unsure whether logo or product photo, do not change").
  * Touches ONLY the `images` child table. No other field, product, Item, or
    commercial data is modified. Nothing is deleted from disk.
  * Idempotent: products already image-less report 'already_empty'.

Not a public API; no whitelist.

    bench --site iranrobot.localhost execute \\
        iranrobot_backend.commands.clear_robotsasia_logo_images.run
"""

import frappe

APPROVED = [
    "robotsasia-ugv-guoxing-eod-gxbox510",
    "robotsasia-ugv-guoxing-mower-kt500",
]
# Known Guo Xing brand-logo files (confirmed byte-identical, 14280 bytes).
_LOGO_BASENAMES = {"guo_23.png", "guo_27.png"}


def _basename(url):
    return (url or "").rstrip("/").split("/")[-1]


def run():
    result = {"cleared": [], "already_empty": [], "left_unchanged": [], "missing": []}
    for pid in APPROVED:
        if not frappe.db.exists("Robot Product", pid):
            result["missing"].append(pid)
            continue
        doc = frappe.get_doc("Robot Product", pid)
        if not doc.images:
            result["already_empty"].append(pid)
            continue
        hero = next((row.image for row in doc.images if row.is_hero), None) or (doc.images[0].image if doc.images else None)
        base = _basename(hero)
        if base in _LOGO_BASENAMES:
            before = hero
            doc.set("images", [])          # clear ONLY the images child table
            doc.save(ignore_permissions=True)
            result["cleared"].append({"product_id": pid, "before": before, "after": None})
        else:
            # Not a recognized logo -> do not touch; report for manual review.
            result["left_unchanged"].append({"product_id": pid, "hero": hero, "reason": "hero is not a known logo file"})

    if result["cleared"]:
        frappe.db.commit()
    print(result)
    return result
