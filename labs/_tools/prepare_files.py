# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Write every case file of LDS-DMG-208 (Al-Samur University, a fictional public university).

Standard library only, fixed seed: the same bytes on every run. From the labs/ folder:

    uv run --no-project _tools/prepare_files.py

It writes labs/files/ (what participants get) and labs/solutions/reference/ (the truth the
generator planted, which the trainer and solutions/check.py read). Every supplier, name, number,
telephone and address is synthetic: registration numbers start with 99, tax numbers with 399,
telephones with 0599, e-mail addresses use example.com, and brand words are common Arabic words,
never a family name, so that no supplier name carries a person's name.
"""
from __future__ import annotations

import csv
import json
import random
from datetime import date, timedelta
from pathlib import Path

LABS = Path(__file__).resolve().parents[1]
FILES = LABS / "files"
REF = LABS / "solutions" / "reference"
SEED = 208

# --------------------------------------------------------------------------------------------
# Vocabulary
# --------------------------------------------------------------------------------------------

BRANDS = [  # (Arabic with article, Latin base without article)
    ("الأفق", "ufuq"), ("الريادة", "riyada"), ("النخبة", "nukhba"), ("الإتقان", "itqan"),
    ("النجمة", "najma"), ("الضياء", "diyaa"), ("الصفوة", "safwa"), ("الرواد", "ruwad"),
    ("الإبداع", "ibdaa"), ("الأمانة", "amana"), ("الجودة", "jawda"), ("الشروق", "shurooq"),
    ("البيان", "bayan"), ("الإشراق", "ishraq"), ("الفجر", "fajr"), ("المسار", "masar"),
    ("الركائز", "rakaiz"), ("الأساس", "asas"), ("الدانة", "dana"), ("اللؤلؤة", "luluah"),
    ("الغيث", "ghaith"), ("الأصالة", "asala"), ("الوفاء", "wafaa"), ("الرخاء", "rakhaa"),
    ("التميز", "tamayyuz"), ("القمة", "qimma"), ("الأثير", "atheer"), ("الندى", "nada"),
    ("البشائر", "bashair"), ("الربيع", "rabee"), ("الياسمين", "yasmeen"), ("الخزامى", "khuzama"),
    ("الجوهرة", "jawhara"), ("الكوثر", "kawthar"), ("المعالي", "maali"), ("الحصن", "hisn"),
    ("الضاحية", "dahiya"), ("المروج", "murooj"), ("الشفق", "shafaq"), ("السراج", "siraj"),
    ("الدرة", "durra"), ("الأماني", "amani"), ("الجسور", "jusoor"), ("الوئام", "wiam"),
    ("البريق", "bareeq"), ("السدرة", "sidra"), ("النسيم", "naseem"), ("المتانة", "matana"),
    ("الإنجاز", "injaz"), ("العطاء", "ataa"), ("الثقة", "thiqa"), ("الضفاف", "difaf"),
    ("الواعد", "waed"), ("الرائد", "raed"), ("الأمجاد", "amjad"), ("الفرقد", "farqad"),
    ("المدى", "mada"), ("الرحاب", "rehab"), ("البوادي", "bawadi"), ("الكرمة", "karma"),
    ("الصرح", "sarh"), ("الإيمان", "iman"), ("الهدى", "huda"), ("الشموخ", "shumookh"),
    ("الوثبة", "wathba"), ("الإنماء", "inmaa"), ("المنار", "minar"), ("السلام", "salam"),
    ("الثريا", "thuraya"), ("الأريكة", "arika"), ("الزهور", "zuhoor"), ("البستان", "bustaan"),
    ("الأنوار", "anwar"), ("الإحسان", "ihsan"), ("البركة", "baraka"), ("الجنى", "jana"), ("الحياة", "hayat"),
    ("الخير", "khair"), ("الدليل", "daleel"), ("الرفيع", "rafee"), ("الزاد", "zad"), ("السبيل", "sabeel"),
    ("السحر", "sahar"), ("الشامخ", "shamikh"), ("الصباح", "sabah"), ("الطموح", "tumooh"), ("العزم", "azm"),
    ("الفلك", "falak"), ("القلعة", "qalaa"), ("الكنز", "kanz"), ("اللواء", "liwaa"),
    ("المجد", "majd"), ("المرقاب", "mirqab"), ("المنهج", "manhaj"), ("النبراس", "nibras"), ("النور", "noor"),
    ("الهمة", "himma"), ("الوسام", "wisam"), ("الأصيل", "aseel"),
    ("التاج", "taj"), ("الجبل", "jabal"), ("الحراء", "hiraa"), ("الربوة", "rabwa"), ("السهم", "sahm"),
    ("الشعلة", "shuala"), ("الصقر", "saqr"), ("الطلائع", "talaie"), ("العريق", "areeq"), ("الفارس", "faris"),
    ("القبس", "qabas"), ("الكرم", "karam"), ("المصباح", "misbah"),
]
# The adjective is translated in some English names and transliterated in others.
ADJECTIVES = [  # (Arabic, transliteration, translation)
    ("الحديثة", "haditha", "Modern"), ("المتحدة", "muttahida", "United"),
    ("الوطنية", "wataniya", "National"), ("العربية", "arabiya", "Arabian"),
    ("الدولية", "dawliya", "International"), ("الخليجية", "khalijiya", "Gulf"),
    ("المتقدمة", "mutaqaddima", "Advanced"), ("الأولى", "oula", "First"),
]
ACTIVITIES = [  # key, Arabic phrase in names, English phrase, reference code (v1.1), MCP code, FIN code
    ("trade", "للتجارة", "Trading", "GD-GEN", "GENTRD", "A-100"),
    ("contract", "للمقاولات", "Contracting", "WK-CON", "CIVIL", "A-610"),
    ("medserv", "للخدمات الطبية", "Medical Services", "SV-MED", "MEDSRV", "A-320"),
    ("medcons", "للمستلزمات الطبية", "Medical Supplies", "GD-MED-CON", "MEDCONS", "A-310"),
    ("meddev", "للأجهزة الطبية", "Medical Equipment", "GD-MED-DEV", "MEDEQP", "A-310"),
    ("pharma", "للأدوية", "Pharmaceuticals", "GD-PHA", "PHARM", "A-330"),
    ("lab", "للأجهزة المخبرية", "Laboratory Equipment", "GD-LAB", "LABEQ", "A-340"),
    ("tech", "للتقنية", "Technology", "GD-ICT", "IT", "A-410"),
    ("om", "للتشغيل والصيانة", "Operation and Maintenance", "SV-OM", "FM", "A-620"),
    ("catering", "للتموين", "Catering", "SV-CAT", "FOOD", "A-520"),
    ("clean", "للنظافة", "Cleaning Services", "SV-CLN", "CLEAN", "A-510"),
    ("furn", "للأثاث المكتبي", "Office Furniture", "GD-FUR", "FURN", "A-130"),
    ("print", "للمطبوعات", "Printing", "GD-PRN", "PRINT", "A-140"),
    ("engcons", "للاستشارات الهندسية", "Engineering Consultants", "SV-ENG", "CONSULT", "A-630"),
    ("safety", "للأمن والسلامة", "Safety and Security", "SV-SEC", "SEC", "A-530"),
    ("chem", "للمواد الكيميائية", "Chemicals", "GD-CHM", "CHEM", "A-150"),
    ("transport", "للنقل", "Transport", "SV-TRN", "LOGI", "A-540"),
    ("travel", "للسفر والسياحة", "Travel and Tourism", "SV-TRV", "TRAVEL", "A-550"),
]
ACT = {a[0]: a for a in ACTIVITIES}
# How often each activity occurs among the suppliers, and how likely each system holds it.
ACT_WEIGHT = {"trade": 12, "contract": 8, "medserv": 4, "medcons": 9, "meddev": 6, "pharma": 5,
              "lab": 4, "tech": 8, "om": 7, "catering": 4, "clean": 4, "furn": 4, "print": 4,
              "engcons": 5, "safety": 4, "chem": 3, "transport": 4, "travel": 4}
IN_MCP = {"medserv": .9, "medcons": .95, "meddev": .95, "pharma": .95, "lab": .8, "clean": .5,
          "catering": .5, "tech": .4, "trade": .3, "chem": .5, "safety": .4, "om": .35, "furn": .3,
          "print": .25, "transport": .35, "travel": .15, "engcons": .15, "contract": .1}
IN_PMC = {"contract": .9, "om": .9, "engcons": .85, "safety": .55, "clean": .45, "tech": .25,
          "trade": .2, "furn": .3, "transport": .2, "catering": .15, "chem": .15, "print": .1,
          "travel": .05, "lab": .05, "medserv": .08, "medcons": .04, "meddev": .08, "pharma": .02}
FORMS = [("شركة", "Co.", "Company"), ("مؤسسة", "Est.", "Establishment")]

# Cities with their region (ISO 3166-2:SA code). Real place names, used only as addresses.
CITIES = [
    ("الرياض", "Riyadh", "SA-01", 30), ("جدة", "Jeddah", "SA-02", 16), ("مكة المكرمة", "Makkah", "SA-02", 5),
    ("الطائف", "Taif", "SA-02", 3), ("المدينة المنورة", "Madinah", "SA-03", 5), ("ينبع", "Yanbu", "SA-03", 2),
    ("الدمام", "Dammam", "SA-04", 9), ("الخبر", "Khobar", "SA-04", 5), ("الجبيل", "Jubail", "SA-04", 2),
    ("الأحساء", "Al Ahsa", "SA-04", 3), ("بريدة", "Buraidah", "SA-05", 3), ("عنيزة", "Unaizah", "SA-05", 1),
    ("حائل", "Hail", "SA-06", 2), ("تبوك", "Tabuk", "SA-07", 2), ("عرعر", "Arar", "SA-08", 1),
    ("جازان", "Jazan", "SA-09", 2), ("نجران", "Najran", "SA-10", 1), ("الباحة", "Al Baha", "SA-11", 1),
    ("سكاكا", "Sakaka", "SA-12", 1), ("أبها", "Abha", "SA-14", 3), ("خميس مشيط", "Khamis Mushait", "SA-14", 2),
]
CITY = {c[0]: c for c in CITIES}
REGIONS = [  # ISO 3166-2:SA code, Arabic, English; SA-13 is not used by the standard
    ("SA-01", "منطقة الرياض", "Riyadh"), ("SA-02", "منطقة مكة المكرمة", "Makkah"),
    ("SA-03", "منطقة المدينة المنورة", "Madinah"), ("SA-04", "المنطقة الشرقية", "Eastern"),
    ("SA-05", "منطقة القصيم", "Qassim"), ("SA-06", "منطقة حائل", "Hail"), ("SA-07", "منطقة تبوك", "Tabuk"),
    ("SA-08", "منطقة الحدود الشمالية", "Northern Borders"), ("SA-09", "منطقة جازان", "Jazan"),
    ("SA-10", "منطقة نجران", "Najran"), ("SA-11", "منطقة الباحة", "Al Baha"), ("SA-12", "منطقة الجوف", "Al Jouf"),
    ("SA-14", "منطقة عسير", "Asir"),
]
FIN_REGION = {"SA-01": "RYD", "SA-02": "MKH", "SA-03": "MDN", "SA-04": "EST", "SA-05": "QSM", "SA-06": "HAL",
              "SA-07": "TBK", "SA-08": "NBR", "SA-09": "JZN", "SA-10": "NJR", "SA-11": "BHA", "SA-12": "JWF",
              "SA-14": "ASR"}
# The portal numbers regions 1 to 13 in its own order: 13 is Asir (ISO has 14 for Asir, and no 13).
MCP_REGION = {"SA-01": "1", "SA-02": "2", "SA-03": "3", "SA-04": "4", "SA-05": "5", "SA-06": "6", "SA-07": "7",
              "SA-08": "8", "SA-09": "9", "SA-10": "10", "SA-11": "11", "SA-12": "12", "SA-14": "13"}
PMC_REGION_TEXT = {
    "SA-01": ["الرياض", "منطقة الرياض", "Riyadh", "RIYADH"],
    "SA-02": ["مكة المكرمة", "منطقة مكة", "Makkah", "جدة"],
    "SA-03": ["المدينة المنورة", "Madinah", "Medina"],
    "SA-04": ["الشرقية", "المنطقة الشرقية", "Eastern Province", "الدمام"],
    "SA-05": ["القصيم", "Qassim"], "SA-06": ["حائل", "Hail"], "SA-07": ["تبوك", "Tabuk"],
    "SA-08": ["الحدود الشمالية", "Northern Borders"], "SA-09": ["جازان", "Jizan"],
    "SA-10": ["نجران", "Najran"], "SA-11": ["الباحة", "Baha"], "SA-12": ["الجوف", "Al Jouf"],
    "SA-14": ["عسير", "Asir", "أبها"],
}
PMC_ACT_TEXT = {
    "contract": ["مقاولات عامة", "Civil Works", "مقاولات"], "om": ["صيانة", "تشغيل وصيانة", "O&M"],
    "engcons": ["استشارات هندسية", "Consultancy"], "safety": ["أمن وسلامة", "Safety"],
    "clean": ["نظافة", "Cleaning"], "tech": ["تقنية معلومات", "IT"], "trade": ["توريدات", "Supplies"],
    "furn": ["أثاث", "Furniture"], "transport": ["نقل", "Transport"], "catering": ["إعاشة", "Catering"],
    "chem": ["كيماويات", "Chemicals"], "print": ["مطبوعات"], "travel": ["سفر"], "lab": ["مختبرات"],
    "medserv": ["خدمات طبية"], "medcons": ["مستلزمات طبية"], "meddev": ["أجهزة طبية"], "pharma": ["أدوية"],
}
FIN_ACT_LABEL = {"A-100": "توريدات عامة", "A-130": "أثاث", "A-140": "مطبوعات وقرطاسية", "A-150": "مواد كيميائية",
                 "A-310": "مستلزمات وأجهزة طبية", "A-320": "خدمات طبية", "A-330": "أدوية", "A-340": "تجهيزات مخبرية",
                 "A-410": "حاسبات وتقنية", "A-510": "نظافة", "A-520": "تموين وإعاشة", "A-530": "أمن وسلامة",
                 "A-540": "نقل", "A-550": "سفر وسياحة", "A-610": "مقاولات إنشائية", "A-620": "تشغيل وصيانة",
                 "A-630": "استشارات هندسية", "A-621": "صيانة أجهزة"}
MCP_ACT_LABEL = {"GENTRD": "General trading", "CIVIL": "Civil works", "MEDSRV": "Medical services",
                 "MEDCONS": "Medical consumables", "MEDEQP": "Medical equipment", "PHARM": "Pharmaceuticals",
                 "LABEQ": "Laboratory equipment", "IT": "Information technology", "FM": "Facility management",
                 "FOOD": "Food and catering", "CLEAN": "Cleaning", "FURN": "Furniture", "PRINT": "Printing",
                 "CONSULT": "Consultancy", "SEC": "Security and safety", "CHEM": "Chemicals", "LOGI": "Logistics",
                 "TRAVEL": "Travel"}

MIGRATION_DAY = date(2025, 3, 16)  # the day PMC was loaded from spreadsheets: every PMC row carries it
TODAY = date(2026, 10, 31)

AR_DIAC = "َُِّْ"
TATWEEL = "ـ"

# --------------------------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------------------------


def write_csv(path: Path, header: list[str], rows: list[list]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.strip() + "\n", encoding="utf-8", newline="\n")


def weighted(rng: random.Random, items: dict) -> str:
    keys = sorted(items)
    return rng.choices(keys, weights=[items[k] for k in keys])[0]


def latin_word(base: str, rng: random.Random, p: float) -> str:
    """One transliteration variant of a Latin base word."""
    w = base
    if rng.random() < p:
        swaps = [("oo", "u"), ("u", "o"), ("ee", "i"), ("i", "e"), ("q", "k"), ("aa", "a"), ("th", "s"),
                 ("kh", "k"), ("dh", "z"), ("ya", "iya"), ("yy", "y"), ("ah", "a")]
        rng.shuffle(swaps)
        for a, b in swaps[: rng.randint(1, 2)]:
            if a in w:
                w = w.replace(a, b, 1)
    if w.endswith("a") and rng.random() < p * 0.6:
        w += "h"
    return w


def article(rng: random.Random, p: float) -> str:
    if rng.random() >= p:
        return "Al "
    return rng.choice(["Al-", "El ", "Al", "", "AL "])


def ar_variant(name: str, rng: random.Random, p: float) -> str:
    """Arabic orthographic variants: hamza on alef, taa marbuta, alef maqsura, diacritics, tatweel."""
    out = name
    if rng.random() < p:
        out = out.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
    if rng.random() < p:
        out = " ".join(t[:-1] + "ه" if t.endswith("ة") else t for t in out.split(" "))
    if rng.random() < p * 0.7:
        out = " ".join(t[:-1] + "ى" if t.endswith("ي") and len(t) > 3 else t for t in out.split(" "))
    if rng.random() < p * 0.5:
        chars = list(out)
        for _ in range(rng.randint(1, 3)):
            i = rng.randrange(1, len(chars))
            if "ء" <= chars[i - 1] <= "ي":
                chars.insert(i, rng.choice(AR_DIAC))
        out = "".join(chars)
    if rng.random() < p * 0.3:
        toks = out.split(" ")
        i = rng.randrange(len(toks))
        if len(toks[i]) > 3:
            toks[i] = toks[i][:2] + TATWEEL + toks[i][2:]
        out = " ".join(toks)
    if rng.random() < p * 0.25:
        out = out.replace("  ", " ") + " "  # trailing space
    return out


def ar_typo(name: str, rng: random.Random) -> str:
    toks = name.split(" ")
    i = rng.randrange(len(toks))
    t = toks[i]
    if len(t) > 4:
        j = rng.randrange(2, len(t) - 1)
        t = t[:j] + t[j + 1:] if rng.random() < .5 else t[:j] + t[j] + t[j:]
    toks[i] = t
    return " ".join(toks)


def fmt_cr(cr: str, rng: random.Random) -> str:
    style = rng.random()
    if style < .5:
        return cr
    if style < .8:
        return f"{cr[:4]} {cr[4:7]} {cr[7:]}"
    return f"{cr[:4]}-{cr[4:]}"


def transpose(s: str, rng: random.Random) -> str:
    i = rng.randrange(2, len(s) - 1)
    return s[:i] + s[i + 1] + s[i] + s[i + 2:] if s[i] != s[i + 1] else s[:i] + str((int(s[i]) + 1) % 10) + s[i + 1:]


def fmt_phone(ph: str, rng: random.Random) -> str:
    r = rng.random()
    if r < .45:
        return ph
    if r < .75:
        return "+966" + ph[1:]
    if r < .9:
        return f"966 {ph[1:3]} {ph[3:6]} {ph[6:]}"
    return f"{ph[:3]}-{ph[3:]}"


def rand_day(rng: random.Random, start: date, end: date) -> date:
    return start + timedelta(days=rng.randrange((end - start).days + 1))


# --------------------------------------------------------------------------------------------
# Suppliers (the truth)
# --------------------------------------------------------------------------------------------


def make_suppliers(rng: random.Random, n: int) -> list[dict]:
    used_names: set[str] = set()
    used_cr: set[str] = set()
    used_phone: set[str] = set()
    sups = []
    city_w = {c[0]: c[3] for c in CITIES}
    while len(sups) < n:
        act = weighted(rng, ACT_WEIGHT)
        b_ar, b_lat = rng.choice(BRANDS)
        adj = rng.choice(ADJECTIVES) if rng.random() < .35 else None
        form = FORMS[0] if rng.random() < .62 else FORMS[1]
        ltd = form[0] == "شركة" and rng.random() < .45
        a = ACT[act]
        brand_ar = b_ar + (" " + adj[0] if adj else "")
        name_ar = f"{form[0]} {brand_ar} {a[1]}" + (" المحدودة" if ltd else "")
        trade = f"{brand_ar} {a[1]}"  # a trade name is unique: the legal form does not make a second one
        if trade in used_names:
            continue
        used_names.add(trade)
        adj_translated = bool(adj) and rng.random() < .5
        en_brand = "Al " + b_lat.capitalize()
        if adj:
            en_brand = (f"{adj[2]} " + b_lat.capitalize()) if adj_translated else en_brand + " Al " + adj[1].capitalize()
        en_form = ("LLC" if ltd else form[1]) if rng.random() < .8 else form[2]
        name_en = f"{en_brand} {a[2]} {en_form}"
        while True:
            cr = "99" + "".join(rng.choice("0123456789") for _ in range(8))
            if cr not in used_cr:
                used_cr.add(cr)
                break
        while True:
            phone = "0599" + "".join(rng.choice("0123456789") for _ in range(6))
            if phone not in used_phone:
                used_phone.add(phone)
                break
        vat = "399" + "".join(rng.choice("0123456789") for _ in range(11)) + "3"
        city = weighted(rng, city_w)
        moved = rng.random() < .22
        old_city = weighted(rng, city_w) if moved else city
        if old_city == city:
            moved = False
        phone_changed = rng.random() < .2
        old_phone = "0598" + phone[4:] if phone_changed else phone
        slug = b_lat.replace(" ", "") + (adj[1][:3] if adj else "") + act[:3] + cr[-3:]
        sups.append(dict(sid=f"S{len(sups) + 1:05d}", act=act, trade=trade, brand_ar=b_ar, brand_lat=b_lat, adj=adj,
                         adj_translated=adj_translated, form=form, ltd=ltd, name_ar=name_ar, name_en=name_en,
                         cr=cr, vat=vat, city=city, old_city=old_city, moved=moved, phone=phone,
                         old_phone=old_phone, phone_changed=phone_changed, email=f"info@{slug}.example.com"))
    return sups


def add_sisters(rng: random.Random, sups: list[dict], share: float) -> None:
    """Sister companies: the same brand and owner, another activity, the same telephone and mailbox."""
    names = {s["trade"] for s in sups}
    crs = {s["cr"] for s in sups}
    base = list(sups)
    for s in base:
        if rng.random() >= share:
            continue
        act = rng.choice([k for k in ACT_WEIGHT if k != s["act"]])
        a = ACT[act]
        brand_ar = s["brand_ar"] + (" " + s["adj"][0] if s["adj"] else "")
        form = FORMS[0] if rng.random() < .5 else FORMS[1]
        ltd = form[0] == "شركة" and rng.random() < .45
        name_ar = f"{form[0]} {brand_ar} {a[1]}" + (" المحدودة" if ltd else "")
        if f"{brand_ar} {a[1]}" in names:
            continue
        names.add(f"{brand_ar} {a[1]}")
        en_brand = s["name_en"].split(f" {ACT[s['act']][2]} ")[0]
        name_en = f"{en_brand} {a[2]} " + (("LLC" if ltd else form[1]) if rng.random() < .8 else form[2])
        while True:
            cr = "99" + "".join(rng.choice("0123456789") for _ in range(8))
            if cr not in crs:
                crs.add(cr)
                break
        sis = dict(s, sid=f"S{len(sups) + 1:05d}", act=act, trade=f"{brand_ar} {a[1]}", form=form, ltd=ltd, name_ar=name_ar, name_en=name_en,
                   cr=cr, vat="399" + "".join(rng.choice("0123456789") for _ in range(11)) + "3",
                   sister_of=s["sid"])
        s["sister_of"] = sis["sid"]
        sups.append(sis)


def en_variant(s: dict, rng: random.Random, p: float) -> str:
    """An English name of the supplier as a person typed it in a system."""
    b = s["brand_lat"]
    if s["adj"] and s["adj_translated"]:
        brand = f"{s['adj'][2]} {latin_word(b, rng, p).capitalize()}"
    else:
        brand = article(rng, p) + latin_word(b, rng, p).capitalize()
        if s["adj"]:
            brand += " " + article(rng, p).strip() + " " + latin_word(s["adj"][1], rng, p).capitalize()
            brand = brand.replace("  ", " ")
    act = ACT[s["act"]][2]
    if rng.random() < p * .4:
        act = act.replace(" and ", " & ")
    form = rng.choice(["Co.", "Co", "Company", "Co. Ltd", "LLC", "L.L.C"]) if s["form"][0] == "شركة" else rng.choice(
        ["Est.", "Est", "Establishment", "EST"])
    if rng.random() < p * .3:
        form = ""
    name = f"{brand} {act} {form}".strip()
    if rng.random() < p * .4:
        name = name.upper()
    return name


def ar_name_variant(s: dict, rng: random.Random, p: float) -> str:
    name = s["name_ar"]
    if rng.random() < p * .5:  # legal form dropped or moved
        name = name.replace(s["form"][0] + " ", "", 1)
    if rng.random() < p * .4 and "المحدودة" not in name and s["form"][0] == "شركة":
        name += rng.choice([" المحدودة", " ذ.م.م", " ذات مسؤولية محدودة"])
    if rng.random() < p * .3:
        name = name.replace(" المحدودة", "")
    name = ar_variant(name, rng, p)
    if rng.random() < p * .15:
        name = ar_typo(name, rng)
    return name


# --------------------------------------------------------------------------------------------
# Source records
# --------------------------------------------------------------------------------------------

HEADER = ["record_id", "source", "name", "name_alt", "cr_number", "vat_number", "city", "region_code",
          "activity_code", "phone", "email", "last_updated"]


def make_records(rng: random.Random, sups: list[dict]) -> list[dict]:
    recs: list[dict] = []
    counters = {"FIN": 0, "MCP": 0, "PMC": 0}

    def add(src: str, s: dict, **kw) -> None:
        counters[src] += 1
        r = dict(record_id=f"{src}-{counters[src]:05d}", source=src, sid=s["sid"], **kw)
        recs.append(r)

    for s in sups:
        act = s["act"]
        a = ACT[act]
        in_mcp = rng.random() < IN_MCP[act]
        in_pmc = rng.random() < IN_PMC[act]
        in_fin = rng.random() < (.62 if (in_mcp or in_pmc) else 1.0)
        s["systems"] = [x for x, y in (("FIN", in_fin), ("MCP", in_mcp), ("PMC", in_pmc)) if y]
        if in_fin:
            for k in range(2 if rng.random() < .035 else 1):
                old = s["moved"] and rng.random() < .85
                city = s["old_city"] if old else s["city"]
                reg = FIN_REGION[CITY[city][2]]
                if reg == "EST" and rng.random() < .25:
                    reg = "DMM"  # legacy code for the Eastern Province
                cr = s["cr"] if rng.random() < .92 else ""
                if cr and rng.random() < .01:
                    cr = transpose(cr, rng)
                fin_act = a[5]
                if act == "om" and rng.random() < .3:
                    fin_act = "A-621"
                add("FIN", s, name=ar_name_variant(s, rng, .05 if k == 0 else .5),
                    name_alt=en_variant(s, rng, .3) if rng.random() < .3 else "",
                    cr_number=cr, vat_number=s["vat"] if rng.random() < .8 else "", city=city, region_code=reg,
                    activity_code=fin_act,
                    phone=fmt_phone(s["old_phone"] if s["phone_changed"] and rng.random() < .8 else s["phone"], rng),
                    email=s["email"] if rng.random() < .6 else "",
                    last_updated=rand_day(rng, date(2020, 1, 1), date(2023, 12, 31)) if old or s["phone_changed"]
                    else rand_day(rng, date(2021, 1, 1), date(2025, 6, 30)))
        if in_mcp:
            for k in range(2 if rng.random() < .025 else 1):
                cr = fmt_cr(s["cr"], rng) if rng.random() < .85 else ""
                if cr and rng.random() < .02:
                    cr = transpose(cr.replace(" ", "").replace("-", ""), rng)
                add("MCP", s, name=s["name_en"] if k == 0 and rng.random() < .85 else en_variant(s, rng, .7),
                    name_alt=ar_name_variant(s, rng, .8) if rng.random() < .35 else "",
                    cr_number=cr, vat_number=s["vat"] if rng.random() < .75 else "", city=CITY[s["city"]][1],
                    region_code=MCP_REGION[CITY[s["city"]][2]], activity_code=a[4],
                    phone=fmt_phone(s["phone"], rng), email=s["email"] if rng.random() < .9 else "",
                    last_updated=rand_day(rng, date(2024, 1, 1), TODAY))
        if in_pmc:
            for k in range(2 if rng.random() < .05 else 1):
                arabic = rng.random() < .55
                city = s["old_city"] if (s["moved"] and rng.random() < .8) else s["city"]
                r = rng.random()
                cr = "0000000000" if r < .07 else (s["cr"] if r < .62 else "")
                reg_text = rng.choice(PMC_REGION_TEXT[CITY[city][2]])
                add("PMC", s, name=ar_name_variant(s, rng, .7) if arabic else en_variant(s, rng, .7),
                    name_alt="", cr_number=cr, vat_number=s["vat"] if rng.random() < .3 else "",
                    city=city if arabic else CITY[city][1], region_code=reg_text,
                    activity_code=rng.choice(PMC_ACT_TEXT[act]),
                    phone=fmt_phone(s["old_phone"] if s["phone_changed"] and rng.random() < .8 else s["phone"], rng),
                    email=s["email"] if rng.random() < .3 else "", last_updated=MIGRATION_DAY)
    return recs


def script_of(name: str) -> str:
    return "ar" if any("؀" <= ch <= "ۿ" for ch in name) else "en"


# --------------------------------------------------------------------------------------------
# Labelled pairs
# --------------------------------------------------------------------------------------------


def make_pairs(rng: random.Random, recs: list[dict], n_by_class: dict, pos_share: float, prefix: str,
               exclude: set | None = None) -> list[list]:
    exclude = exclude or set()
    by_sid: dict[str, list[dict]] = {}
    by_brand: dict[str, list[dict]] = {}
    sup_brand = {}
    for r in recs:
        by_sid.setdefault(r["sid"], []).append(r)
    for r in recs:
        sup_brand.setdefault(r["sid"], r["brand"])
        by_brand.setdefault(r["brand"], []).append(r)
    multi = sorted(sid for sid, rs in by_sid.items() if len(rs) > 1)
    sisters = []
    for r in recs:
        if r.get("sister_of") and r["sister_of"] in by_sid and r["sid"] < r["sister_of"]:
            for x in by_sid[r["sister_of"]]:
                sisters.append((r, x))
    holders = [r for r in recs if r["cr_number"] == "0000000000"]
    out, seen = [], set(exclude)
    for cls, n in n_by_class.items():
        n_pos = round(n * pos_share)
        got_pos = got_neg = 0
        guard = 0
        while (got_pos < n_pos or got_neg < n - n_pos) and guard < 400000:
            guard += 1
            if got_pos < n_pos:
                rs = by_sid[rng.choice(multi)]
                a, b = rng.sample(rs, 2)
                want = 1
            else:
                u = rng.random()
                if u < .14 and sisters:
                    a, b = rng.choice(sisters)
                elif u < .22 and holders:
                    a, b = rng.sample(holders, 2)
                else:
                    a = rng.choice(recs)
                    pool = by_brand[a["brand"]] if rng.random() < .8 else recs
                    b = rng.choice(pool)
                if a["sid"] == b["sid"]:
                    continue
                want = 0
            c = "-".join(sorted((script_of(a["name"]), script_of(b["name"]))))
            c = {"ar-ar": "ar-ar", "en-en": "en-en", "ar-en": "ar-en"}[c]
            if c != cls:
                continue
            key = tuple(sorted((a["record_id"], b["record_id"])))
            if key in seen or a["record_id"] == b["record_id"]:
                continue
            seen.add(key)
            out.append([key[0], key[1], cls, want])
            if want:
                got_pos += 1
            else:
                got_neg += 1
    rng.shuffle(out)
    return [[f"{prefix}{i + 1:03d}", *p] for i, p in enumerate(out)]


# --------------------------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------------------------


ACT_GROUPS = [("GD", "سلع", "Goods"), ("SV", "خدمات", "Services"), ("WK", "أشغال", "Works")]
ACT_REF = [  # code, Arabic, English, definition; GD-MED is v1.0 only, the two GD-MED-* codes come in v1.1
    ("GD-GEN", "توريدات عامة", "General supplies", "سلع متنوعة لا تقع في فئة أخرى من فئات السلع في هذه القائمة"),
    ("GD-MED", "مستلزمات وأجهزة طبية", "Medical supplies and equipment", "مواد طبية مستهلكة وأجهزة طبية معمرة"),
    ("GD-MED-CON", "مستلزمات طبية استهلاكية", "Medical consumables",
     "مواد طبية تُستعمل مرة واحدة أو تُستهلك في الرعاية، مثل الضمادات والمحاقن والقفازات"),
    ("GD-MED-DEV", "أجهزة طبية", "Medical equipment",
     "أجهزة ومعدات طبية تُستعمل مرات كثيرة وتحتاج إلى تركيب أو صيانة أو معايرة"),
    ("GD-PHA", "أدوية", "Pharmaceuticals", "مستحضرات دوائية مسجلة تُصرف في المدينة الطبية"),
    ("GD-LAB", "أجهزة ومستلزمات مخبرية", "Laboratory equipment and supplies",
     "أجهزة المختبرات البحثية والتعليمية ومستلزماتها غير الكيميائية"),
    ("GD-ICT", "حاسبات وتقنية معلومات", "Computers and IT", "أجهزة الحاسب والشبكات والبرمجيات الجاهزة وملحقاتها"),
    ("GD-FUR", "أثاث مكتبي", "Office furniture", "أثاث المكاتب والقاعات والمعامل"),
    ("GD-PRN", "مطبوعات وقرطاسية", "Printing and stationery", "المطبوعات والقرطاسية ولوازم المكاتب المستهلكة"),
    ("GD-CHM", "مواد كيميائية", "Chemicals", "مواد كيميائية للمختبرات والتشغيل، ولها اشتراطات تخزين ونقل"),
    ("SV-MED", "خدمات طبية", "Medical services", "خدمات سريرية أو تشخيصية يقدمها مورد في المدينة الطبية"),
    ("SV-OM", "تشغيل وصيانة", "Operation and maintenance", "تشغيل المرافق وصيانة المباني والأجهزة بعقود دورية"),
    ("SV-CAT", "تموين وإعاشة", "Catering", "إعداد الوجبات وتقديمها للطلاب والمرضى والموظفين"),
    ("SV-CLN", "نظافة", "Cleaning", "نظافة المباني والمرافق والتخلص من النفايات غير الطبية"),
    ("SV-ENG", "استشارات هندسية", "Engineering consultancy", "تصميم المشاريع والإشراف عليها ودراساتها"),
    ("SV-SEC", "أمن وسلامة", "Security and safety", "الحراسة وأنظمة السلامة والإطفاء وصيانتها"),
    ("SV-TRN", "نقل", "Transport", "نقل الأفراد والبضائع بعقود"),
    ("SV-TRV", "سفر وسياحة", "Travel", "حجوزات السفر والإقامة للمهمات والمؤتمرات"),
    ("WK-CON", "مقاولات إنشائية", "Construction works", "تشييد المباني والطرق والبنية التحتية وترميمها"),
]
ISO_SA = [  # ISO 3166-2:SA codes, with the names listed beside them for reference; SA-13 is not used
    ("SA-01", "الرياض", "Riyadh"), ("SA-02", "مكة", "Mecca"), ("SA-03", "المدينة المنورة", "Medina"),
    ("SA-04", "الشرقية", "Eastern"), ("SA-05", "القصيم", "Qassim"), ("SA-06", "حائل", "Ha'il"),
    ("SA-07", "تبوك", "Tabuk"), ("SA-08", "الحدود الشمالية", "Northern Borders"), ("SA-09", "جازان", "Jizan"),
    ("SA-10", "نجران", "Najran"), ("SA-11", "الباحة", "Baha"), ("SA-12", "الجوف", "Jouf"), ("SA-14", "عسير", "Asir"),
]


def read_back(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_codes() -> None:
    """Lab 2.1: the external region list, a draft activity list with planted faults, templates."""
    write_csv(FILES / "codes" / "iso_3166_2_sa.csv", ["code", "name_ar", "name_en"], [list(x) for x in ISO_SA])
    draft = [[g, a, e, "مجموعة " + a, "", "2027-01-01", "", "active"] for g, a, e in ACT_GROUPS]
    for code, a, e, d in ACT_REF:
        if code.startswith("GD-MED-"):
            continue
        draft.append([code, a, e, d, code.split("-")[0], "2027-01-01", "", "active"])
    # planted faults: five definitions missing, a wrong parent, a second code for maintenance, a catch-all
    for row in draft:
        if row[0] in ("GD-LAB", "SV-MED", "SV-SEC", "GD-CHM", "SV-TRV"):
            row[3] = ""
        if row[0] == "GD-FUR":
            row[4] = "SV"
    draft.append(["SV-MNT", "تشغيل وصيانة", "Maintenance", "صيانة المباني والأجهزة", "SV", "2027-01-01", "", "active"])
    draft.append(["GD-MISC", "أخرى", "Other", "", "GD", "2027-01-01", "", "active"])
    write_csv(FILES / "codes" / "activities_draft.csv",
              ["code", "name_ar", "name_en", "definition", "parent", "valid_from", "valid_to", "status"], draft)
    src = read_back(FILES / "codes" / "source_codes.csv")
    write_csv(FILES / "codes" / "crosswalk_template.csv",
              ["system", "code_type", "source_code", "source_label", "records", "reference_code", "rule_note"],
              [[r["system"], r["code_type"], r["source_code"], r["source_label"], r["records"], "", ""] for r in src])
    write_csv(FILES / "codes" / "lists_template.csv",
              ["list_id", "title", "kind", "external_source", "owner", "steward", "version", "released"],
              [["regions", "", "", "", "", "", "", ""], ["activities", "", "", "", "", "", "", ""]])
    write_csv(FILES / "codes" / "change_log_template.csv",
              ["version", "change_id", "change_type", "code", "description", "requested_by", "approved_by",
               "records_affected"], [])


def write_reference_codes(xw: list[list], code_rows: list[list]) -> None:
    """Reference solution of lab 2.1: the folder at version 1.0 and at version 1.1."""
    head = ["code", "name_ar", "name_en", "definition", "parent", "valid_from", "valid_to", "status"]
    regions = [[c, a, e, f"المنطقة الإدارية {a} (ISO 3166-2:SA {c})", "", "2027-01-01", "", "active"]
               for c, a, e in ISO_SA]
    records = {(r[0], r[2]): r[4] for r in code_rows}
    a310 = records[("FIN", "A-310")]
    med_mcp = records[("MCP", "MEDCONS")] + records[("MCP", "MEDEQP")]
    for version in ("1.0", "1.1"):
        acts = [[g, a, e, "مجموعة " + a, "", "2027-01-01", "", "active"] for g, a, e in ACT_GROUPS]
        for code, a, e, d in ACT_REF:
            parent = code.split("-")[0]
            if code == "GD-MED":
                acts.append([code, a, e, d, parent, "2027-01-01", "" if version == "1.0" else "2027-03-31",
                             "active" if version == "1.0" else "retired"])
            elif code.startswith("GD-MED-"):
                if version == "1.1":
                    acts.append([code, a, e, d, parent, "2027-04-01", "", "active"])
            elif code == "SV-TRN" and version == "1.1":
                acts.append([code, "نقل وخدمات لوجستية", "Transport and logistics",
                             d + "، والتخزين المؤقت المرتبط به", parent, "2027-01-01", "", "active"])
            else:
                acts.append([code, a, e, d, parent, "2027-01-01", "", "active"])
        cross = []
        for src, kind, code, ref, note in xw:
            label = next((r[3] for r in code_rows if r[0] == src and r[1] == kind and r[2] == code), "")
            n = records[(src, code)]
            if version == "1.0" and ref in ("GD-MED-CON", "GD-MED-DEV", "GD-MED-CON|GD-MED-DEV"):
                ref, note = "GD-MED", ""
            elif ref == "GD-MED-CON|GD-MED-DEV":
                note = "يقرر مشرف بيانات الأعمال لكل مورد، ويبدأ بما يقوله رمز البوابة للمورد نفسه"
            elif src == "FIN" and code == "DMM":
                note = "رمز قديم للمنطقة الشرقية"
            elif src == "MCP" and code == "13":
                note = "البوابة ترقم عسير 13، ورمزها في المعيار SA-14"
            elif src == "PMC" and kind == "region" and code in ("جدة", "الدمام", "أبها"):
                note = "اسم مدينة في حقل المنطقة"
            else:
                note = ""
            cross.append([src, kind, code, label, n, ref, note])
        lists = [["regions", "المناطق الإدارية", "external", "ISO 3166-2:SA", "ISO (خارجي)، والنسخة المحلية لمكتب إدارة البيانات",
                  "يزيد العقيلي", "1.0", "2027-01-01"],
                 ["activities", "أنشطة الموردين", "internal", "", "مشعل الزنيدي، مدير المشتريات", "جود الدعيليج",
                  version, "2027-01-01" if version == "1.0" else "2027-04-01"]]
        log = [["1.0", "CH-001", "add", "*", "الإصدار الأول لقائمتي المناطق والأنشطة وجدول المقابلة", "مكتب إدارة البيانات",
                "مشعل الزنيدي", ""]]
        if version == "1.1":
            log += [["1.1", "CH-002", "split", "GD-MED|GD-MED-CON|GD-MED-DEV",
                     "تقسيم المستلزمات والأجهزة الطبية إلى رمزين بطلب المدينة الطبية (CR-02)", "نوف المزروع",
                     "مشعل الزنيدي", a310 + med_mcp],
                    ["1.1", "CH-003", "rename", "SV-TRN", "تغيير اسم النقل إلى «نقل وخدمات لوجستية» وتوسيع تعريفه (CR-03)",
                     "جود الدعيليج", "مشعل الزنيدي", records[("FIN", "A-540")] + records[("MCP", "LOGI")]]]
        folder = REF / "codes" / f"v{version}"
        write_csv(folder / "regions.csv", head, regions)
        write_csv(folder / "activities.csv", head, acts)
        write_csv(folder / "crosswalk.csv", ["system", "code_type", "source_code", "source_label", "records",
                                            "reference_code", "rule_note"], cross)
        write_csv(folder / "lists.csv", ["list_id", "title", "kind", "external_source", "owner", "steward",
                                        "version", "released"], lists)
        write_csv(folder / "change_log.csv", ["version", "change_id", "change_type", "code", "description",
                                              "requested_by", "approved_by", "records_affected"], log)


RCP_ACT = {"lab": "Lab supplies", "chem": "Chemicals", "tech": "IT equipment", "trade": "General",
           "furn": "Furniture", "print": "Printing", "travel": "Travel", "meddev": "Research equipment",
           "medcons": "Consumables", "transport": "Courier"}
RCP_REGION = {"SA-01": "RUH", "SA-02": "JED", "SA-03": "MED", "SA-04": "DMM", "SA-05": "ELQ", "SA-06": "HAS",
              "SA-07": "TUU", "SA-08": "RAE", "SA-09": "GIZ", "SA-10": "EAM", "SA-11": "ABT", "SA-12": "AJF",
              "SA-14": "AHB"}


def make_rcp(sups: list[dict], recs: list[dict]) -> int:
    """Capstone: the research centres' purchasing system, a fourth source of 2,400 records."""
    rng = random.Random(SEED + 7)
    pool = [s for s in sups if s["act"] in RCP_ACT]
    known_pool = pool
    names = {s["trade"] for s in sups}
    fresh = []
    for s in make_suppliers(random.Random(SEED + 8), 6000):
        if s["act"] in RCP_ACT and s["trade"] not in names and len(fresh) < 750:
            s["sid"] = "N" + s["sid"][1:]
            # new suppliers: their own number ranges, so no value collides with a known supplier
            s["phone"] = s["old_phone"] = "0597" + s["phone"][4:]
            s["phone_changed"], s["cr"] = False, "98" + s["cr"][2:]
            fresh.append(s)
    rows, truth = [], []
    known = rng.sample(known_pool, 2400 - len(fresh))
    for i, s in enumerate(sorted(known + fresh, key=lambda x: (rng.random(), x["sid"]))):
        arabic = rng.random() < .4
        r = rng.random()
        cr = "N/A" if r < .05 else (fmt_cr(s["cr"], rng) if r < .8 else "")
        rid = f"RCP-{i + 1:05d}"
        rows.append([rid, "RCP", ar_name_variant(s, rng, .5) if arabic else en_variant(s, rng, .5), "", cr,
                     s["vat"] if rng.random() < .5 else "", s["city"] if arabic else CITY[s["city"]][1],
                     RCP_REGION[CITY[s["city"]][2]], RCP_ACT[s["act"]], fmt_phone(s["phone"], rng),
                     s["email"] if rng.random() < .7 else "", rand_day(rng, date(2024, 6, 1), TODAY).isoformat()])
        truth.append([rid, s["sid"]])
    rows, truth = rows[:2400], truth[:2400]
    write_csv(FILES / "capstone" / "rcp_records.csv", HEADER, rows)
    write_csv(REF / "rcp_truth.csv", ["record_id", "supplier_id"], truth)
    by_sid: dict[str, list[dict]] = {}
    by_brand: dict[str, list[dict]] = {}
    for x in recs:
        by_sid.setdefault(x["sid"], []).append(x)
        by_brand.setdefault(x["brand"], []).append(x)
    sup = {s["sid"]: s for s in sups + fresh}
    out, seen = [], set()
    rcp = [dict(zip(HEADER, r), sid=t[1]) for r, t in zip(rows, truth)]
    guard = 0
    while len(out) < 150 and guard < 100000:
        guard += 1
        a = rng.choice(rcp)
        want = len(out) % 2 == 0
        if want:
            if a["sid"] not in by_sid:
                continue
            b = rng.choice(by_sid[a["sid"]])
        else:
            cand = [x for x in by_brand.get(sup[a["sid"]]["brand_lat"], []) if x["sid"] != a["sid"]]
            if not cand:
                continue
            b = rng.choice(cand)
        key = (a["record_id"], b["record_id"])
        if key in seen:
            continue
        seen.add(key)
        cls = "-".join(sorted((script_of(a["name"]), script_of(b["name"]))))
        out.append([f"R{len(out) + 1:03d}", a["record_id"], b["record_id"], cls, int(want)])
    write_csv(FILES / "capstone" / "rcp_labelled_pairs.csv",
              ["pair_id", "record_id_l", "record_id_r", "script_class", "is_match"], out)
    codes: dict[tuple, int] = {}
    for x in rcp:
        for kind, col in (("region", "region_code"), ("activity", "activity_code")):
            codes[(kind, x[col])] = codes.get((kind, x[col]), 0) + 1
    write_csv(FILES / "capstone" / "rcp_source_codes.csv", ["system", "code_type", "source_code", "records"],
              [["RCP", k[0], k[1], n] for k, n in sorted(codes.items())])
    return len(rows)


def main() -> None:
    rng = random.Random(SEED)
    sups = make_suppliers(rng, 12600)
    add_sisters(rng, sups, .05)
    recs = make_records(rng, sups)
    # Keep exactly 20,000 records: drop single-system suppliers from the end until the total fits.
    sid_count: dict[str, int] = {}
    for r in recs:
        sid_count[r["sid"]] = sid_count.get(r["sid"], 0) + 1
    excess = len(recs) - 20000
    drop: set[str] = set()
    for s in reversed(sups):
        if excess <= 0:
            break
        if sid_count[s["sid"]] == 1 and not s.get("sister_of"):
            drop.add(s["sid"])
            excess -= 1
    assert excess == 0, f"need {excess} more records: raise the number of suppliers"
    recs = [r for r in recs if r["sid"] not in drop]
    sups = [s for s in sups if s["sid"] not in drop]
    sup = {s["sid"]: s for s in sups}
    for r in recs:
        r["brand"] = sup[r["sid"]]["brand_lat"]
        r["sister_of"] = sup[r["sid"]].get("sister_of")
    # Renumber per source so the ids run without gaps after the drop.
    order = {"FIN": 0, "MCP": 1, "PMC": 2}
    recs.sort(key=lambda r: (order[r["source"]], int(r["record_id"][4:])))
    cnt = {"FIN": 0, "MCP": 0, "PMC": 0}
    for r in recs:
        cnt[r["source"]] += 1
        r["record_id"] = f"{r['source']}-{cnt[r['source']]:05d}"

    rows = [[r[h] if h != "last_updated" else r[h].isoformat() for h in HEADER] for r in recs]
    write_csv(FILES / "matching" / "records.csv", HEADER, rows)
    write_csv(REF / "record_truth.csv", ["record_id", "supplier_id", "sister_of", "activity"],
              [[r["record_id"], r["sid"], r["sister_of"] or "", sup[r["sid"]]["act"]] for r in recs])

    pairs = make_pairs(random.Random(SEED + 1), recs, {"ar-ar": 200, "en-en": 150, "ar-en": 150}, .52, "P")
    write_csv(FILES / "matching" / "labelled_pairs.csv",
              ["pair_id", "record_id_l", "record_id_r", "script_class", "is_match"], pairs)

    # ----- golden-record batch: approved clusters of 3,000 suppliers held by two systems or more
    grng = random.Random(SEED + 2)
    recs_by_sid: dict[str, list[dict]] = {}
    for r in recs:
        recs_by_sid.setdefault(r["sid"], []).append(r)
    multi = sorted(sid for sid, rs in recs_by_sid.items() if len({x["source"] for x in rs}) >= 2)
    batch = sorted(grng.sample(multi, 3000))
    clusters, golden_src = [], []
    for i, sid in enumerate(batch):
        cid = f"C{i + 1:04d}"
        for r in recs_by_sid[sid]:
            clusters.append([r["record_id"], cid])
            golden_src.append([cid] + [r[h] if h != "last_updated" else r[h].isoformat() for h in HEADER])
    write_csv(FILES / "golden" / "clusters.csv", ["record_id", "cluster_id"], clusters)
    write_csv(FILES / "golden" / "cluster_records.csv", ["cluster_id"] + HEADER, golden_src)
    three = [sid for sid in batch if len({x["source"] for x in recs_by_sid[sid]}) == 3]
    moved = [sid for sid in batch if sup[sid]["moved"] or sup[sid]["phone_changed"]]
    picked = set(grng.sample(three, 30))
    verified = sorted(picked | set(grng.sample(sorted(set(moved) - picked), 30)))
    cid_of = {sid: f"C{i + 1:04d}" for i, sid in enumerate(batch)}
    vrows = []
    for sid in verified:
        s = sup[sid]
        vrows.append([cid_of[sid], s["name_ar"], s["name_en"], s["cr"], s["vat"], s["city"], s["phone"], s["email"]])
    write_csv(FILES / "golden" / "verified_sample.csv",
              ["cluster_id", "name_ar", "name_en", "cr_number", "vat_number", "city", "phone", "email"], vrows)
    write_csv(FILES / "golden" / "cities.csv", ["city_ar", "city_en", "region_iso"],
              [[c[0], c[1], c[2]] for c in CITIES])
    write_csv(FILES / "golden" / "trust_matrix.csv", ["attribute", "FIN", "MCP", "PMC", "note"], [
        ["name_ar", 1, 3, 2, "المالية تنسخ الاسم العربي من شهادة السجل التجاري عند تسجيل المورد"],
        ["name_en", 2, 1, 3, "بوابة المدينة الطبية تطلب من المورد اسمه الإنجليزي كما في مستنداته"],
        ["cr_number", 1, 2, 3, "المالية تتحقق من الرقم عند كل دفعة؛ وفي سجل المشاريع أرقام بديلة"],
        ["vat_number", 1, 1, 3, "المالية والبوابة تتحققان من الرقم في الفواتير"],
        ["city", 2, 1, 3, "المورد يحدّث عنوانه في البوابة بنفسه"],
        ["phone", 2, 1, 3, "المورد يحدّث بيانات الاتصال في البوابة بنفسه"],
        ["email", 2, 1, 3, "البوابة ترسل أوامر الشراء بالبريد، فيُكتشف العنوان الخاطئ سريعًا"],
    ])
    write_csv(REF / "golden_truth.csv", ["cluster_id", "supplier_id", "name_ar", "name_en", "cr_number",
                                         "vat_number", "city", "phone", "email"],
              [[cid_of[sid], sid, sup[sid]["name_ar"], sup[sid]["name_en"], sup[sid]["cr"], sup[sid]["vat"],
                sup[sid]["city"], sup[sid]["phone"], sup[sid]["email"]] for sid in batch])

    # ----- reference codes: what each system holds, with record counts
    code_rows = []
    for src, col in (("FIN", "region_code"), ("MCP", "region_code"), ("PMC", "region_code"),
                     ("FIN", "activity_code"), ("MCP", "activity_code"), ("PMC", "activity_code")):
        counts: dict[str, int] = {}
        for r in recs:
            if r["source"] == src:
                counts[r[col]] = counts.get(r[col], 0) + 1
        for code in sorted(counts):
            label = ""
            if col == "activity_code":
                label = FIN_ACT_LABEL.get(code, "") if src == "FIN" else MCP_ACT_LABEL.get(code, "") if src == "MCP" else ""
            code_rows.append([src, "region" if col == "region_code" else "activity", code, label, counts[code]])
    write_csv(FILES / "codes" / "source_codes.csv", ["system", "code_type", "source_code", "source_label",
                                                     "records"], code_rows)
    # truth of the crosswalk for the trainer: source code -> reference code (with the split rule)
    xw = []
    for src, code_type, code, label, n in code_rows:
        if code_type == "region":
            if src == "FIN":
                ref = {v: k for k, v in FIN_REGION.items()}.get(code, "SA-04" if code == "DMM" else "")
            elif src == "MCP":
                ref = {v: k for k, v in MCP_REGION.items()}[code]
            else:
                ref = next(k for k, v in PMC_REGION_TEXT.items() if code in v)
            xw.append([src, code_type, code, ref, "1:1" if src != "PMC" else "text"])
        else:
            if src == "FIN":
                if code == "A-310":
                    xw.append([src, code_type, code, "GD-MED-CON|GD-MED-DEV", "split: steward decides per supplier"])
                    continue
                ref = "SV-OM" if code == "A-621" else next(a[3] for a in ACTIVITIES if a[5] == code)
            elif src == "MCP":
                ref = next(a[3] for a in ACTIVITIES if a[4] == code)
            else:
                ref = next(ACT[k][3] for k, v in PMC_ACT_TEXT.items() if code in v)
            xw.append([src, code_type, code, ref, "1:1"])
    write_csv(REF / "crosswalk_truth.csv", ["system", "code_type", "source_code", "reference_code", "kind"], xw)

    write_codes()
    write_reference_codes(xw, code_rows)
    rcp = make_rcp(sups, recs)

    meta = {
        "rcp_records": rcp,
        "records": len(recs), "suppliers": len(sups),
        "by_source": {k: sum(1 for r in recs if r["source"] == k) for k in ("FIN", "MCP", "PMC")},
        "pmc_placeholder_cr": sum(1 for r in recs if r["cr_number"] == "0000000000"),
        "fin_dmm": sum(1 for r in recs if r["source"] == "FIN" and r["region_code"] == "DMM"),
        "mcp_13": sum(1 for r in recs if r["source"] == "MCP" and r["region_code"] == "13"),
        "fin_a310": sum(1 for r in recs if r["source"] == "FIN" and r["activity_code"] == "A-310"),
        "pairs": {c: [sum(1 for p in pairs if p[3] == c and p[4] == 1), sum(1 for p in pairs if p[3] == c and p[4] == 0)]
                  for c in ("ar-ar", "en-en", "ar-en")},
        "golden_batch": len(batch), "golden_records": len(clusters), "verified": len(vrows),
    }
    REF.mkdir(parents=True, exist_ok=True)
    (REF / "data_facts.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(meta, ensure_ascii=False))


if __name__ == "__main__":
    main()
