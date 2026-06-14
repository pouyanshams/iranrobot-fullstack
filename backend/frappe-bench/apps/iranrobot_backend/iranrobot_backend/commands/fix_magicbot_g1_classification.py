"""One-off, idempotent data fix: MagicLab MagicBot G1 humanoid subtype.

Root cause: the seed data mislabeled `magiclab-magicbot-g1` as a WHEELED
humanoid (subcategory `wheeled-humanoids`, Robot Type spec "Wheeled Humanoid",
wheeled tagline/description), but the RobotsAsia source page and the product
image show a human-scale BIPEDAL humanoid (42 DoF, 20 kg payload, dynamic
walking / biped gait). The sibling MagicBot Z1 is correctly bipedal and is
left untouched.

This corrects ONLY the wrong-locomotion fields on the single product:
subcategory, the Robot Type spec row (fa/en), tagline (fa/en), and the wheeled
phrasing in the description (fa/en). Category stays `humanoids`; the (correct,
bipedal) hero image is left as-is.

Idempotent: re-running after the fix is a no-op. Not a public API; no whitelist.

    bench --site iranrobot.localhost execute \\
        iranrobot_backend.commands.fix_magicbot_g1_classification.run
"""

import frappe

PRODUCT_ID = "magiclab-magicbot-g1"

NEW = {
    "subcategory": "bipedal-humanoids",
    # product_name_fa wrongly read "انسان‌نمای چرخ‌دار" (wheeled humanoid); en name is generic.
    "product_name_fa": "ربات انسان‌نمای دوپای MagicLab MagicBot G1 Standard Edition",
    "tagline_fa": "پلتفرم انسان‌نمای دوپای هم‌اندازه‌ی انسان از MagicLab برای پژوهش، توسعه‌ی نرم‌افزار رباتیک و کاربردهای تعامل انسانی.",
    "tagline_en": "A MagicLab human-scale bipedal humanoid platform for robotics research, software development, and human-interaction applications.",
    "description_fa": (
        "MagicLab MagicBot G1 Standard Edition نسخه‌ی پایه از خانواده‌ی ربات‌های انسان‌نمای "
        "MagicBot G1 شرکت MagicLab است؛ یک انسان‌نمای دوپای هم‌اندازه‌ی انسان که در کنار مدل "
        "MagicBot Z1 از همین برند ارائه می‌شود. این پلتفرم انسان‌نمای دوپا برای پژوهش، نمایش "
        "رباتیک و توسعه‌ی کاربردهای تعامل انسان و ربات در فضاهای داخلی طراحی شده است."
    ),
    "description_en": (
        "The MagicLab MagicBot G1 Standard Edition is the entry-level configuration of MagicLab's "
        "MagicBot G1 humanoid family, a human-scale bipedal humanoid offered alongside the MagicBot "
        "Z1 from the same brand. This bipedal humanoid platform is aimed at robotics research, "
        "demonstrations, and human-robot interaction development in indoor environments."
    ),
}
# Robot Type spec correction (matched by English label).
SPEC_TYPE_LABEL_EN = "Robot Type"
SPEC_TYPE_NEW_FA = "انسان‌نمای دو پا"
SPEC_TYPE_NEW_EN = "Bipedal Humanoid"


def run():
    if not frappe.db.exists("Robot Product", PRODUCT_ID):
        return {"status": "not_found", "product_id": PRODUCT_ID}

    doc = frappe.get_doc("Robot Product", PRODUCT_ID)
    before = {
        "subcategory": doc.subcategory,
        "tagline_en": doc.tagline_en,
        "robot_type": next(
            (s.value_en for s in doc.specs if (s.label_en or "") == SPEC_TYPE_LABEL_EN), None
        ),
    }

    changed = []
    for field, value in NEW.items():
        if doc.get(field) != value:
            doc.set(field, value)
            changed.append(field)

    for s in doc.specs:
        if (s.label_en or "") == SPEC_TYPE_LABEL_EN or (s.label_fa or "") == "نوع ربات":
            if s.value_en != SPEC_TYPE_NEW_EN or s.value_fa != SPEC_TYPE_NEW_FA:
                s.value_en = SPEC_TYPE_NEW_EN
                s.value_fa = SPEC_TYPE_NEW_FA
                changed.append("specs.Robot Type")

    if not changed:
        return {"status": "already_correct", "product_id": PRODUCT_ID, "after": before}

    doc.save(ignore_permissions=True)
    frappe.db.commit()

    after = {
        "category": doc.category,
        "subcategory": doc.subcategory,
        "tagline_en": doc.tagline_en,
        "robot_type": next(
            (s.value_en for s in doc.specs if (s.label_en or "") == SPEC_TYPE_LABEL_EN), None
        ),
        "hero_image": next((i.image for i in doc.images if i.is_hero), None),
    }
    result = {"status": "fixed", "product_id": PRODUCT_ID, "changed": changed,
              "before": before, "after": after}
    print(result)
    return result
