#!/usr/bin/env python3
"""Build a SEPARATE normalized dataset for the ugvs + accessories batch.

Kept separate from robotsasia_products.json (Core-4) so the import can only
touch ugvs/accessories and never re-publishes the unpublished duplicates.
Authored bilingual copy merged with scraped hero/url/price.
"""
import json, pathlib
RAW = pathlib.Path('tmp/robotsasia-acc-ugv-raw.json')
OUT = pathlib.Path('backend/frappe-bench/apps/iranrobot_backend/iranrobot_backend/data/robotsasia_accessories_ugvs.json')
def S(lf,vf,le,ve): return {"label_fa":lf,"value_fa":vf,"label_en":le,"value_en":ve}
T_UGV=("نوع","خودرو زمینی بدون‌سرنشین (UGV)","Type","Unmanned ground vehicle (UGV)")
T_HAND=("نوع","دست رباتیک ماهر","Type","Dexterous robot hand")

A = {
 # ---------------- UGVs ----------------
 "robotsasia-ugv-husarion-panther": dict(brand="Husarion", model="Panther PTH12", origin=("لهستان","Poland"),
   name_fa="خودرو زمینی بدون‌سرنشین Husarion Panther PTH12", name_en="Husarion Panther PTH12 UGV",
   tagline_fa="پلتفرم متحرک بیرونی مقاوم با پشتیبانی ROS 2 / Nav2", tagline_en="Rugged outdoor mobile base with ROS 2 / Nav2 support",
   desc_fa="Husarion Panther PTH12 یک خودرو زمینی بدون‌سرنشین (UGV) صنعتی و مقاوم برای محیط‌های بیرونی پرگردوغبار و پرلرزش است. این پلتفرم به‌عنوان حامل بار برای حسگرها (لیدار، دوربین عمق/استریو) به کار می‌رود و با پشتیبانی ROS 2 و Nav2 برای بازرسی صنعتی و گشت‌زنی محیط مناسب است.",
   desc_en="The Husarion Panther PTH12 is a rugged industrial unmanned ground vehicle (UGV) for demanding, dusty, high-vibration outdoor environments. It serves as a payload carrier for sensors (LiDAR, stereo/depth cameras) and, with ROS 2 and Nav2 support, suits industrial inspection and perimeter patrol.",
   specs=[S(*T_UGV),S("ساختار","پایه‌ی متحرک بیرونی مقاوم","Form factor","Rugged outdoor mobile base"),S("نرم‌افزار","ROS 2 / Nav2","Software","ROS 2 / Nav2"),S("کاربرد","بازرسی صنعتی، گشت‌زنی","Use","Industrial inspection, patrol")]),
 "robotsasia-ugv-husarion-rosbot3": dict(brand="Husarion", model="ROSbot 3", origin=("لهستان","Poland"),
   name_fa="خودرو زمینی بدون‌سرنشین Husarion ROSbot 3", name_en="Husarion ROSbot 3 UGV",
   tagline_fa="UGV داخلی ROS 2 با چهارچرخ‌محرک و هسته‌ی Raspberry Pi 5", tagline_en="ROS 2 indoor UGV with 4-wheel drive and Raspberry Pi 5",
   desc_fa="Husarion ROSbot 3 یک خودرو زمینی بدون‌سرنشین داخلی و آماده‌به‌کار برای توسعه‌ی ROS 2 است. این ربات با چهارچرخ‌محرک، اِنکودر موتور، هسته‌ی پردازشی Raspberry Pi 5 و شاسی آلومینیومی ۱٫۵ میلی‌متری، برای SLAM، ناوبری و آموزش رباتیک طراحی شده است.",
   desc_en="The Husarion ROSbot 3 is an out-of-the-box indoor unmanned ground vehicle for ROS 2 development. With 4-wheel drive, motor encoders, a Raspberry Pi 5 compute core and a 1.5 mm aluminum chassis, it is built for SLAM, navigation and robotics education.",
   specs=[S(*T_UGV),S("رانش","چهارچرخ‌محرک","Drive","4-wheel drive"),S("پردازنده","Raspberry Pi 5","Compute","Raspberry Pi 5"),S("نرم‌افزار","ROS 2، SLAM","Software","ROS 2, SLAM"),S("شاسی","آلومینیوم ۱٫۵ میلی‌متر","Chassis","1.5 mm aluminum")],use_cases=["education"]),
 "robotsasia-ugv-husarion-rosbot3-pro": dict(brand="Husarion", model="ROSbot 3 PRO", origin=("لهستان","Poland"),
   name_fa="خودرو زمینی بدون‌سرنشین Husarion ROSbot 3 PRO", name_en="Husarion ROSbot 3 PRO UGV",
   tagline_fa="نسخه‌ی PRO با RPLIDAR S2 و دوربین OAK-D Pro برای SLAM", tagline_en="PRO build with RPLIDAR S2 and OAK-D Pro for SLAM",
   desc_fa="Husarion ROSbot 3 PRO نسخه‌ی ارتقایافته‌ی UGV داخلی ROS 2 است که پشته‌ی ادراک را با لیدار RPLIDAR S2 و دوربین OAK-D Pro تقویت می‌کند. ابعاد آن با دوربین و لیدار ۲۰۰×۲۳۳×۱۹۷ میلی‌متر و وزن حدود ۲٫۸ کیلوگرم است؛ مناسب آزمایشگاه‌ها و کلاس‌های داخلی.",
   desc_en="The Husarion ROSbot 3 PRO is the upgraded ROS 2 indoor UGV, enhancing the perception stack with an RPLIDAR S2 and an OAK-D Pro camera. It measures 200 × 233 × 197 mm with camera and LiDAR and weighs about 2.8 kg, suiting indoor labs and classrooms.",
   specs=[S(*T_UGV),S("ادراک","RPLIDAR S2، OAK-D Pro","Perception","RPLIDAR S2, OAK-D Pro"),S("پردازنده","Raspberry Pi 5","Compute","Raspberry Pi 5"),S("ابعاد","۲۰۰×۲۳۳×۱۹۷ میلی‌متر","Dimensions","200 × 233 × 197 mm"),S("وزن","حدود ۲٫۸ کیلوگرم","Weight","~2.8 kg")],use_cases=["education"]),
 "robotsasia-ugv-guoxing-rxr-m40d-880t": dict(brand="Guo Xing", model="RXR-M40D-880T", origin=("چین","China"),
   name_fa="ربات آتش‌نشان Guo Xing RXR-M40D-880T", name_en="Guo Xing RXR-M40D-880T Firefighting Robot",
   tagline_fa="ربات آتش‌نشانی زنجیری با بدنه‌ی پایدار و کارکردهای ضدواژگونی", tagline_en="Tracked firefighting robot with stable body and anti-capsize functions",
   desc_fa="Guo Xing RXR-M40D-880T یک خودرو زمینی بدون‌سرنشین آتش‌نشان برای واکنش صنعتی به آتش است. بدنه‌ی پایدار آن دارای کارکردهای ضدواژگونی، ضدبرخورد و خنک‌سازی خودکار است و برای کاهش حضور مستقیم آتش‌نشان در مناطق خطرناک به کار می‌رود.",
   desc_en="The Guo Xing RXR-M40D-880T is a firefighting unmanned ground vehicle for industrial fire response. Its stable body includes anti-capsizing, anti-collision and self-cooling functions, and it is used to reduce direct firefighter exposure in dangerous areas.",
   specs=[S(*T_UGV),S("کاربرد","آتش‌نشانی صنعتی","Use","Industrial firefighting"),S("ساختار","زنجیری (Tracked)","Form factor","Tracked"),S("ایمنی","ضدواژگونی، ضدبرخورد، خنک‌سازی خودکار","Safety","Anti-capsize, anti-collision, self-cooling")]),
 "robotsasia-ugv-guoxing-rxr-mc80bd": dict(brand="Guo Xing", model="RXR-MC80BD", origin=("چین","China"),
   name_fa="ربات شناسایی و اطفای حریق ضدانفجار Guo Xing RXR-MC80BD", name_en="Guo Xing RXR-MC80BD Explosion-Proof Fire Reconnaissance Robot",
   tagline_fa="ربات ضدانفجار شناسایی و اطفای حریق برای محیط‌های پرخطر", tagline_en="Explosion-proof fire extinguishing & reconnaissance robot for hazardous sites",
   desc_fa="Guo Xing RXR-MC80BD یک خودرو زمینی بدون‌سرنشین ضدانفجار برای شناسایی و اطفای حریق در محیط‌های صنعتی، شیمیایی و اضطراری پرخطر است. این ربات با بدنه‌ی پایدار، موتور DC پرتوان و شاسی مقاوم در برابر مانع، می‌تواند به خطر نزدیک شود، اطلاعات شناسایی را مخابره و در اطفای حریق کمک کند.",
   desc_en="The Guo Xing RXR-MC80BD is an explosion-proof unmanned ground vehicle for fire reconnaissance and extinguishing in hazardous industrial, chemical and emergency environments. With a stable body, a high-power DC motor and an obstacle-handling chassis, it can approach hazards, transmit reconnaissance data and assist firefighting.",
   specs=[S(*T_UGV),S("کاربرد","شناسایی و اطفای حریق","Use","Fire reconnaissance & extinguishing"),S("ویژگی","ضدانفجار","Feature","Explosion-proof"),S("موتور","DC پرتوان","Motor","High-power DC")]),
 "robotsasia-ugv-guoxing-eod-gxbox510": dict(brand="Guo Xing", model="GX BOX510", origin=("چین","China"),
   name_fa="ربات خنثی‌سازی بمب Guo Xing GX BOX510", name_en="Guo Xing GX BOX510 EOD Robot",
   tagline_fa="ربات زمینی بدون‌سرنشین خنثی‌سازی مواد منفجره (EOD)", tagline_en="Unmanned ground vehicle for explosive ordnance disposal (EOD)",
   desc_fa="Guo Xing GX BOX510 یک خودرو زمینی بدون‌سرنشین برای خنثی‌سازی مواد منفجره (EOD) است که برای بازرسی و دفع تهدیدهای انفجاری از راه دور به کار می‌رود و حضور مستقیم اپراتور در صحنه‌ی خطرناک را حذف می‌کند.",
   desc_en="The Guo Xing GX BOX510 is an unmanned ground vehicle for explosive ordnance disposal (EOD), used to remotely inspect and neutralize explosive threats, removing the need for direct operator presence in the hazardous scene.",
   specs=[S(*T_UGV),S("کاربرد","خنثی‌سازی مواد منفجره (EOD)","Use","Explosive ordnance disposal (EOD)"),S("کنترل","از راه دور","Control","Remote-operated")]),
 "robotsasia-ugv-guoxing-rxr-c6bd": dict(brand="Guo Xing", model="RXR-C6BD", origin=("چین","China"),
   name_fa="ربات بازرسی و گشت ضدانفجار Guo Xing RXR-C6BD", name_en="Guo Xing RXR-C6BD Explosion-Proof Inspection & Patrol Robot",
   tagline_fa="ربات ضدانفجار بازرسی/گشت با دوربین چرخان و آشکارساز گاز سمی", tagline_en="Explosion-proof inspection/patrol robot with rotating camera and toxic-gas detection",
   desc_fa="Guo Xing RXR-C6BD یک خودرو زمینی بدون‌سرنشین ضدانفجار (درجه‌ی EX d ib IIB+H2 T6 Gb) برای بازرسی و گشت‌زنی در محیط‌های پرخطر، اشتعال‌زا و سمی است. این ربات با دوربین چرخان ۳۶۰ درجه و چرخش عمودی ۹۰ درجه و آشکارسازی ۶ نوع گاز سمی، برای شناسایی و امداد به کار می‌رود.",
   desc_en="The Guo Xing RXR-C6BD is an explosion-proof unmanned ground vehicle (EX d ib IIB+H2 T6 Gb rated) for inspection and patrol in hazardous, flammable and toxic environments. With a 360° rotating, 90° pitching camera and 6-type toxic-gas detection, it is used for reconnaissance and rescue.",
   specs=[S(*T_UGV),S("کاربرد","بازرسی، گشت، امداد","Use","Inspection, patrol, rescue"),S("درجه‌ی ضدانفجار","EX d ib IIB+H2 T6 Gb","Ex rating","EX d ib IIB+H2 T6 Gb"),S("دوربین","چرخش ۳۶۰° / شیب ۹۰°","Camera","360° rotation / 90° pitch"),S("آشکارساز گاز","۶ نوع گاز سمی","Gas detection","6 toxic-gas types")]),
 "robotsasia-ugv-guoxing-mower-kt500": dict(brand="Guo Xing", model="KT500", origin=("چین","China"),
   name_fa="ماشین چمن‌زن کنترل‌از‌دور شیب جنگلی Guo Xing KT500", name_en="Guo Xing KT500 RC Forest-Terrain Slope Mower",
   tagline_fa="ماشین چمن‌زن زنجیری کنترل‌از‌دور برای شیب و زمین جنگلی", tagline_en="Tracked RC slope mower for forest and rough terrain",
   desc_fa="Guo Xing KT500 یک خودرو زمینی بدون‌سرنشین چمن‌زنِ کنترل‌از‌دور است که برای کار روی شیب‌ها و زمین‌های جنگلی دشوار طراحی شده است. شاسی زنجیری آن چسبندگی و پایداری لازم برای علف‌زنی ایمن در شیب‌های تند را فراهم می‌کند.",
   desc_en="The Guo Xing KT500 is a remote-controlled mowing unmanned ground vehicle built for slopes and difficult forest terrain. Its tracked chassis provides the traction and stability needed for safe mowing on steep grades.",
   specs=[S(*T_UGV),S("کاربرد","علف‌زنی شیب/جنگل","Use","Slope/forest mowing"),S("ساختار","زنجیری","Form factor","Tracked"),S("کنترل","از راه دور (RC)","Control","Remote-controlled (RC)")]),
 "robotsasia-ugv-topsky-rxr-c10d": dict(brand="Topsky", model="RXR-C10D", origin=("چین","China"),
   name_fa="ربات کوچک شناسایی حریق و امداد Topsky RXR-C10D", name_en="Topsky RXR-C10D Small Fire Reconnaissance Robot",
   tagline_fa="ربات زنجیری چندمنظوره‌ی شناسایی و امداد با ظرفیت بار بالا", tagline_en="Multi-function tracked reconnaissance & rescue robot with high load capacity",
   desc_fa="Topsky RXR-C10D یک خودرو زمینی بدون‌سرنشین چندمنظوره برای شناسایی حریق و امداد زلزله است که برای حمل تجهیزات و مواد امدادی (مانند شیلنگ آب) به کار می‌رود. ابعاد آن ۱۵۰۰×۱۱۵۰×۱۲۰۰ میلی‌متر، وزن ≤۴۵۰ کیلوگرم، ظرفیت بار ≥۴۵۰ کیلوگرم و نیروی کشش ≥۴۵۰۰ نیوتن است؛ شاسی زنجیری با بازوی نوسانی جلویی، عبور از مانع عمودی تا ۲۸۰ میلی‌متر را ممکن می‌کند.",
   desc_en="The Topsky RXR-C10D is a multi-function unmanned ground vehicle for fire reconnaissance and earthquake rescue, used to transport equipment and rescue materials such as water hoses. It measures 1500 × 1150 × 1200 mm, weighs ≤ 450 kg, carries ≥ 450 kg with ≥ 4500 N traction; its tracked chassis with a front swing arm clears vertical obstacles up to 280 mm.",
   specs=[S(*T_UGV),S("ابعاد","۱۵۰۰×۱۱۵۰×۱۲۰۰ میلی‌متر","Dimensions","1500 × 1150 × 1200 mm"),S("وزن","≤۴۵۰ کیلوگرم","Weight","≤ 450 kg"),S("ظرفیت بار","≥۴۵۰ کیلوگرم","Load capacity","≥ 450 kg"),S("نیروی کشش","≥۴۵۰۰ نیوتن","Traction force","≥ 4500 N"),S("عبور از مانع","تا ۲۸۰ میلی‌متر","Obstacle clearance","Up to 280 mm")]),
 "robotsasia-ugv-topsky-ugv": dict(brand="Topsky", model="UGV", origin=("چین","China"),
   name_fa="خودرو زمینی بدون‌سرنشین زنجیری Topsky", name_en="Topsky Tracked UGV",
   tagline_fa="پلتفرم زنجیری حمل و واکنش با ظرفیت بار بالا", tagline_en="Tracked transport & response platform with high load capacity",
   desc_fa="Topsky UGV یک خودرو زمینی بدون‌سرنشین زنجیری و فشرده برای حمل تجهیزات و واکنش میدانی است که بر کشش، ظرفیت بار و عبور از مانع تأکید دارد. ابعاد آن ۱۵۰۰×۱۱۵۰×۱۲۰۰ میلی‌متر و وزن ≤۴۵۰ کیلوگرم است.",
   desc_en="The Topsky UGV is a compact tracked unmanned ground vehicle for equipment transport and field response, emphasizing traction, payload capacity and obstacle handling. It measures 1500 × 1150 × 1200 mm and weighs ≤ 450 kg.",
   specs=[S(*T_UGV),S("ساختار","زنجیری","Form factor","Tracked"),S("ابعاد","۱۵۰۰×۱۱۵۰×۱۲۰۰ میلی‌متر","Dimensions","1500 × 1150 × 1200 mm"),S("وزن","≤۴۵۰ کیلوگرم","Weight","≤ 450 kg")]),
 # ---------------- Accessories ----------------
 "robotsasia-accessory-inspire-rh56f1-e2r": dict(brand="Inspire Robots", model="RH56F1-E2R", origin=("چین","China"),
   name_fa="دست رباتیک ماهر Inspire RH56F1-E2R (راست)", name_en="Inspire RH56F1-E2R Dexterous Right Hand",
   tagline_fa="دست پنج‌انگشتی شش‌درجه‌آزادی با کنترل RS485 و حسگری", tagline_en="Five-finger 6-DOF hand with RS485 control and sensing",
   desc_fa="Inspire RH56F1-E2R یک دست رباتیک ماهر راست با پنج انگشت و شش درجه‌ی آزادی است که با رابط RS485 کنترل می‌شود. این دست از محرک‌های ریز همراه با حسگری و کنترل ترکیبی نیرو/موقعیت بهره می‌برد تا گرفتن پایدار اشیا را بهبود دهد و معمولاً به‌صورت جفت چپ/راست به کار می‌رود.",
   desc_en="The Inspire RH56F1-E2R is a five-finger, 6-DOF dexterous right hand controlled over RS485. It combines miniature actuators with sensing and mixed force/position control to improve grasp stability, and is typically deployed as a matched left/right pair.",
   specs=[S(*T_HAND),S("انگشت‌ها","۵ انگشت","Fingers","5 fingers"),S("درجات آزادی","۶ درجه آزادی","Degrees of freedom","6 DOF"),S("کنترل/واسط","RS485","Control / interface","RS485")]),
 "robotsasia-accessory-linkerbot-l10": dict(brand="Linkerbot", model="Linker Hand L10", origin=("چین","China"),
   name_fa="دست رباتیک ماهر Linkerbot Linker Hand L10", name_en="Linkerbot Linker Hand L10",
   tagline_fa="دست با ۱۰ درجه‌آزادی فعال + ۱۰ غیرفعال و واسط CAN/EtherCAT", tagline_en="Hand with 10 active + 10 passive DOF, CAN/EtherCAT",
   desc_fa="Linkerbot Linker Hand L10 یک دست رباتیک ماهر پرکارایی با ۱۰ درجه‌ی آزادی فعال و ۱۰ غیرفعال است که برای دستکاری درون‌دستی و تعامل با ابزار طراحی شده است. معماری لینکیج (به‌جای کابلی) بسته‌بندی را ساده و استحکام را بیشتر می‌کند و از گزینه‌های چندحسگری و یکپارچگی CAN/EtherCAT پشتیبانی می‌کند.",
   desc_en="The Linkerbot Linker Hand L10 is a high-performance dexterous hand with 10 active + 10 passive degrees of freedom, designed for in-hand manipulation and tool interaction. Its linkage-driven architecture (rather than cable-driven) simplifies packaging and improves robustness, with multi-sensor options and CAN/EtherCAT integration.",
   specs=[S(*T_HAND),S("درجات آزادی","۱۰ فعال + ۱۰ غیرفعال","Degrees of freedom","10 active + 10 passive"),S("معماری","لینکیج","Architecture","Linkage-driven"),S("واسط","CAN / EtherCAT","Interface","CAN / EtherCAT")]),
 "robotsasia-accessory-robotera-xhand1": dict(brand="Robotera", model="XHAND1", origin=("چین","China"),
   name_fa="دست رباتیک ماهر Robotera XHAND1 (راست)", name_en="Robotera XHAND1 Dexterous Right Hand",
   tagline_fa="دست پنج‌انگشتی ۱۲ درجه‌آزادی با حسگر لمسی و نیروی گرفتن تا ۸۰ نیوتن", tagline_en="Five-finger 12-DOF hand, tactile sensing, up to 80 N grip",
   desc_fa="Robotera XHAND1 یک دست رباتیک پنج‌انگشتی پیشرفته با ۱۲ درجه‌ی آزادیِ کاملاً محرک، حسگرهای لمسی با رزولوشن بالا و نیروی گرفتن تا ۸۰ نیوتن است. این دست از انتقال Quasi-Direct Drive با چرخ‌دنده‌ی کامل بهره می‌برد و برای دستکاری دقیق انسان‌وار طراحی شده است.",
   desc_en="The Robotera XHAND1 is an advanced five-finger robotic hand with 12 fully actuated degrees of freedom, high-resolution tactile sensors and up to 80 N grip strength. It uses full-gear Quasi-Direct Drive transmission and targets human-like precision manipulation.",
   specs=[S(*T_HAND),S("انگشت‌ها","۵ انگشت","Fingers","5 fingers"),S("درجات آزادی","۱۲ درجه آزادی (کاملاً محرک)","Degrees of freedom","12 DOF (fully actuated)"),S("نیروی گرفتن","تا ۸۰ نیوتن","Grip strength","Up to 80 N"),S("حسگر","لمسی با رزولوشن بالا","Sensing","High-resolution tactile")]),
 "robotsasia-accessory-unitree-dex3-1": dict(brand="Unitree", model="G1 Dex3-1", origin=("چین","China"),
   name_fa="دست رباتیک ماهر Unitree G1 Dex3-1", name_en="Unitree G1 Dex3-1 Dexterous Hand",
   tagline_fa="دست سه‌انگشتی نیرو-کنترل با ۷ درجه‌آزادی و ۳۳ حسگر لمسی", tagline_en="Three-finger force-control hand, 7 DOF, 33 tactile sensors",
   desc_fa="Unitree G1 Dex3-1 یک دست رباتیک ماهر سه‌انگشتی با کنترل نیرو، هفت درجه‌ی آزادی و ۳۳ حسگر لمسی است که به‌عنوان دست اختیاری پیشرفته برای ربات انسان‌نمای G1 ارائه می‌شود. طراحی آن بر مفصل‌بندی چندگانه، کنترل نیرو و حسگری لمسی برای گرفتن کنترل‌شده‌ی اشیا تأکید دارد.",
   desc_en="The Unitree G1 Dex3-1 is a three-finger force-control dexterous hand with 7 DOF and 33 tactile sensors, offered as an advanced optional hand for the Unitree G1 humanoid. It emphasizes multi-joint articulation, force control and tactile sensing for controlled object grasping.",
   specs=[S(*T_HAND),S("انگشت‌ها","۳ انگشت","Fingers","3 fingers"),S("درجات آزادی","۷ درجه آزادی","Degrees of freedom","7 DOF"),S("حسگر لمسی","۳۳ حسگر","Tactile sensors","33"),S("کنترل","نیرو-کنترل","Control","Force control")]),
 "robotsasia-accessory-unitree-h1-2-hand": dict(brand="Unitree", model="H1-2 Dexterous Hand", origin=("چین","China"),
   name_fa="دست رباتیک ماهر Unitree H1-2", name_en="Unitree H1-2 Dexterous Hand",
   tagline_fa="دست پنج‌انگشتی انسان‌وار برای ربات‌های انسان‌نمای H1/H1-2", tagline_en="Five-finger anthropomorphic hand for H1/H1-2 humanoids",
   desc_fa="Unitree H1-2 Dexterous Hand یک دست رباتیک پنج‌انگشتی انسان‌وار (خانواده‌ی Dex5-1) برای ربات‌های انسان‌نمای H1/H1-2 است که شست، اشاره، میانی، حلقه و کوچک را به‌صورت مستقل به حرکت درمی‌آورد. ارتقای H1-2 با بازوهای هفت‌درجه‌آزادی و مچ، پیش‌نیاز جهت‌گیری کاربردی دست را فراهم کرده است.",
   desc_en="The Unitree H1-2 Dexterous Hand is a five-finger anthropomorphic hand (Dex5-1 family) for the H1/H1-2 humanoids, independently actuating thumb, index, middle, ring and little fingers. The H1-2 upgrade added 7-DOF arms with a wrist, providing the kinematic prerequisite for functional hand orientation.",
   specs=[S(*T_HAND),S("انگشت‌ها","۵ انگشت (انسان‌وار)","Fingers","5 fingers (anthropomorphic)"),S("خانواده","Dex5-1","Family","Dex5-1"),S("سازگاری","ربات‌های H1 / H1-2","Compatibility","H1 / H1-2 humanoids")]),
 "robotsasia-accessory-shadow-dh": dict(brand="Shadow Robot", model="Dexterous Hand (DH)", origin=("بریتانیا","United Kingdom"),
   name_fa="دست رباتیک ماهر Shadow Dexterous Hand (DH)", name_en="Shadow Dexterous Hand (DH)",
   tagline_fa="دست تاندون‌محرک پردرجه‌آزادی با ۲۰ محرک و حسگری لمسی", tagline_en="High-DOF tendon-driven hand, 20 actuators, tactile sensing",
   desc_fa="Shadow Dexterous Hand (DH) یک دست رباتیک تاندون‌محرک و انسان‌وار است که اندازه، سینماتیک و گستره‌ی کاری دست انسان را تقریب می‌زند و در پژوهش رباتیک به‌طور گسترده به کار می‌رود. نسخه‌ی کلاسیک پنج‌انگشتی آن دارای ۲۰ محرک و پشتیبانی از ۲۴ حرکت مفصلی به همراه حسگری لمسی و یکپارچگی EtherCAT/ROS است.",
   desc_en="The Shadow Dexterous Hand (DH) is a tendon-driven, anthropomorphic robot hand that approximates the size, kinematics and functional range of a human hand and is widely used in robotics research. The classic five-finger version has 20 actuators and supports 24 joint movements, with tactile sensing and EtherCAT/ROS integration.",
   specs=[S(*T_HAND),S("محرک‌ها","۲۰ محرک","Actuators","20 actuators"),S("حرکات مفصلی","۲۴ حرکت","Joint movements","24"),S("درایو","تاندون‌محرک","Drive","Tendon-driven"),S("یکپارچگی","EtherCAT / ROS، حسگر لمسی","Integration","EtherCAT / ROS, tactile sensing")]),
 "robotsasia-accessory-agibot-omnipicker": dict(brand="AgiBot", model="OmniPicker", origin=("چین","China"),
   name_fa="گریپر صنعتی AgiBot OmniPicker", name_en="AgiBot OmniPicker Gripper",
   tagline_fa="گریپر رباتیک با نیروی گرفتن ۱۴۰ نیوتن و دوام یک‌میلیون چرخه", tagline_en="Robot gripper with 140 N grip force and 1M-cycle durability",
   desc_fa="AgiBot OmniPicker یک گریپر رباتیک صنعتی است که در ابتدا به‌عنوان لوازم جانبی اختیاری برای ربات انسان‌نمای فشرده‌ی AgiBot X2 معرفی شد. نسل OmniPicker 3 با نیروی گرفتن ۱۴۰ نیوتن و دوام نامی یک‌میلیون چرخه، برای کاربردهای گرفتن و جابه‌جایی مناسب است.",
   desc_en="The AgiBot OmniPicker is an industrial robot gripper, originally introduced as an optional accessory for the AgiBot X2 compact humanoid. The OmniPicker 3 generation offers 140 N of grip force and a 1,000,000-cycle rated durability, suiting grasping and handling applications.",
   specs=[S("نوع","گریپر رباتیک","Type","Robot gripper"),S("نیروی گرفتن","۱۴۰ نیوتن","Grip force","140 N"),S("دوام","۱٬۰۰۰٬۰۰۰ چرخه","Durability","1,000,000 cycles")]),
 "robotsasia-accessory-agibot-x2-battery": dict(brand="AgiBot", model="X2 Spare Battery", origin=("چین","China"),
   name_fa="باتری یدک AgiBot X2", name_en="AgiBot X2 Spare Battery",
   tagline_fa="باتری یدک برای ربات انسان‌نمای AgiBot X2", tagline_en="Spare battery for the AgiBot X2 humanoid",
   desc_fa="باتری یدک AgiBot X2 یک بسته‌ی باتری جایگزین برای ربات انسان‌نمای AgiBot X2 است که با فراهم‌کردن یک باتری اضافی برای تعویض سریع، زمان کارکرد میدانی را افزایش می‌دهد و توقف ناشی از شارژ را کاهش می‌دهد.",
   desc_en="The AgiBot X2 Spare Battery is a replacement battery pack for the AgiBot X2 humanoid, extending field uptime by providing an extra pack for quick swaps and reducing charging downtime.",
   specs=[S("نوع","باتری یدک","Type","Spare battery"),S("سازگاری","ربات انسان‌نمای AgiBot X2","Compatibility","AgiBot X2 humanoid")]),
 "robotsasia-accessory-unitree-r1-charger": dict(brand="Unitree", model="R1 Battery Charger", origin=("چین","China"),
   name_fa="شارژر باتری Unitree R1", name_en="Unitree R1 Battery Charger",
   tagline_fa="شارژر اختصاصی باتری برای ربات انسان‌نمای Unitree R1", tagline_en="Dedicated battery charger for the Unitree R1 humanoid",
   desc_fa="شارژر باتری Unitree R1 یک شارژر اختصاصی تک‌تکه برای ربات انسان‌نمای Unitree R1 است. این شارژر به‌صورت یک آداپتور برق متناوب (AC) بیرونی عرضه می‌شود و بخشی از اکوسیستم توان است که بر زمان کارکرد و آماده‌به‌کاری ربات اثر می‌گذارد.",
   desc_en="The Unitree R1 Battery Charger is a dedicated single-piece charger for the Unitree R1 humanoid. Supplied as an external AC-powered adapter, it is part of the power ecosystem that affects robot uptime and readiness.",
   specs=[S("نوع","شارژر باتری","Type","Battery charger"),S("سازگاری","ربات انسان‌نمای Unitree R1","Compatibility","Unitree R1 humanoid"),S("فرم","آداپتور برق AC","Form","AC power adapter")]),
 "robotsasia-accessory-bwsensing-bws2700": dict(brand="BWSENSING", model="BWS2700", origin=("چین","China"),
   name_fa="شیب‌سنج دومحوره دقت‌بالا BWSENSING BWS2700", name_en="BWSENSING BWS2700 High-Precision Dual-Axis Inclinometer",
   tagline_fa="شیب‌سنج دومحوره‌ی MEMS با خروجی Modbus و بازه‌ی ±۳۰ درجه", tagline_en="Dual-axis MEMS inclinometer with Modbus output and ±30° range",
   desc_fa="BWSENSING BWS2700 یک شیب‌سنج (اینکلینومتر) دومحوره‌ی دقت‌بالا بر پایه‌ی فناوری MEMS با خروجی دیجیتال Modbus است. بازه‌ی اندازه‌گیری آن ±۳۰ درجه است و برای پایش زاویه و تراز در سامانه‌های رباتیک و صنعتی به کار می‌رود.",
   desc_en="The BWSENSING BWS2700 is a high-precision dual-axis inclinometer based on MEMS technology with Modbus digital output. It has a ±30° measurement range and is used for angle and level monitoring in robotic and industrial systems.",
   specs=[S("نوع","شیب‌سنج (اینکلینومتر)","Type","Inclinometer"),S("محورها","دومحوره","Axes","Dual-axis"),S("فناوری","MEMS","Technology","MEMS"),S("خروجی","Modbus دیجیتال","Output","Modbus digital"),S("بازه","±۳۰ درجه","Range","±30°")]),
}

raw=json.loads(RAW.read_text(encoding='utf-8'))
out=[]; missing=[]
for p in raw['products']:
    pid=p['product_id']; a=A.get(pid)
    if not a: missing.append(pid); continue
    out.append({"source":"robotsasia","source_url":p.get('url') or p.get('sourceUrl'),"source_price_raw":p.get('priceRaw') or None,
        "product_id":pid,"slug":pid,"category":p['category'],"subcategory":p.get('subcategory') or None,
        "brand":a['brand'],"model":a['model'],"origin_fa":a['origin'][0],"origin_en":a['origin'][1],
        "product_name_fa":a['name_fa'],"product_name_en":a['name_en'],"tagline_fa":a['tagline_fa'],"tagline_en":a['tagline_en'],
        "description_fa":a['desc_fa'],"description_en":a['desc_en'],"lead_time_days":45,
        "hero_image":p.get('ogImage') or "","specs":a['specs'],"use_cases":a.get('use_cases',[])})
assert not missing, f"missing authored: {missing}"
# blank out logo/placeholder hero images
for o in out:
    if 'logo' in (o['hero_image'] or '').lower(): o['hero_image']=""
doc={"_meta":{"source":"robotsasia","scope":"ugvs + accessories batch into existing browsable categories only; non-duplicate of seed","note":"Paraphrased copy, factual specs, quote-based pricing. Separate file so import never touches Core-4 or the unpublished duplicates."},"products":out}
OUT.write_text(json.dumps(doc,ensure_ascii=False,indent=2),encoding='utf-8')
from collections import Counter
print("wrote",OUT,"with",len(out),"products | by category:",dict(Counter(p['category'] for p in out)))
print("by subcategory:",dict(Counter(p['subcategory'] for p in out)))
print("empty hero images:",[o['product_id'] for o in out if not o['hero_image']])
