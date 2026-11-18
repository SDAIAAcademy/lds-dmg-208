"""Write the stewardship queue of lab 2.2 from a reference matching run. From labs/, after prepare_files.py:

    uv run _tools/prepare_queue.py

It runs the reference rule file with the course kit, takes 14 uncertain pairs whose truth the
generator knows and 6 suppliers on the split medical code, and writes:
  files/queue/queue_cases.csv      the steward's view (with telephone and e-mail)
  files/queue/model_view.csv       the extract the model is allowed to see (classified Public)
  files/queue/model_suggestions.csv  scripted stand-in suggestions, five of them wrong on purpose
  solutions/reference/queue_key.csv  the answers, for the trainer
The suggestions are written for this course in place of a model's output; no model is called.
"""
from __future__ import annotations

import random
import re
import sys
from pathlib import Path

LABS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LABS / "kit"))
from common import FILES, OUT, read_csv, utf8, write_csv  # noqa: E402
import match  # noqa: E402

REF = LABS / "solutions" / "reference"
PUBLIC = ["name", "name_alt", "cr_number", "vat_number", "city", "activity_code"]


def digits(x: str) -> str:
    return re.sub(r"\D", "", x or "")


CITY = {}


def evidence(a: dict, b: dict) -> str:
    """What agrees and what differs between two records, in words, from the data itself."""
    if not CITY:
        for r in read_csv(FILES / "golden" / "cities.csv"):
            CITY[r["city_ar"]] = CITY[r["city_en"]] = r["city_ar"]
    same, diff = [], []
    for col, label in (("cr_number", "رقم السجل"), ("vat_number", "الرقم الضريبي"), ("phone", "الهاتف")):
        x, y = digits(a[col]), digits(b[col])
        if col == "phone":
            x, y = ("0" + x[3:] if x.startswith("966") else x), ("0" + y[3:] if y.startswith("966") else y)
        if x and y and x != "0000000000" and y != "0000000000":
            (same if x == y else diff).append(label)
    ea, eb = a["email"].lower(), b["email"].lower()
    if ea and eb:
        (same if ea == eb else diff).append("البريد")
    ca, cb = CITY.get(a["city"], a["city"]), CITY.get(b["city"], b["city"])
    if ca and cb:
        (same if ca == cb else diff).append("المدينة")
    out = []
    if same:
        out.append("يتفق: " + "، ".join(same))
    if diff:
        out.append("يختلف: " + "، ".join(diff))
    return "؛ ".join(out) if out else "لا معرّف مشترك"


def main() -> None:
    utf8()
    rng = random.Random(2208)
    match.run(str(REF / "rules_reference.yml"), quiet=True, out_prefix="queue_")
    band = read_csv(OUT / "queue_review_band.csv")
    recs = {r["record_id"]: r for r in read_csv(FILES / "matching" / "records.csv")}
    truth = {r["record_id"]: r for r in read_csv(REF / "record_truth.csv")}
    used = {(p["record_id_l"], p["record_id_r"]) for p in read_csv(FILES / "matching" / "labelled_pairs.csv")}

    def kind(p: dict) -> str:
        a, b = truth[p["record_id_l"]], truth[p["record_id_r"]]
        ra, rb = recs[p["record_id_l"]], recs[p["record_id_r"]]
        if a["supplier_id"] == b["supplier_id"]:
            if digits(ra["cr_number"]) and digits(rb["cr_number"]) and digits(ra["cr_number"]) != digits(rb["cr_number"]):
                return "same_cr_typo"
            if (ra["name"] and rb["name"]) and (bool(re.search("[؀-ۿ]", ra["name"]))
                                               != bool(re.search("[؀-ۿ]", rb["name"]))):
                return "same_cross"
            return "same_other"
        if a["sister_of"] == b["supplier_id"] or b["sister_of"] == a["supplier_id"]:
            return "sister"
        return "other_diff"

    import standardise as S
    norm = {"arabic": {"unify_alef": True, "taa_marbuta": True, "alef_maqsura": True, "remove_diacritics": True,
                       "remove_tatweel": True}, "latin": {"lowercase": True}, "strip_punctuation": True}

    def defensible(p: dict) -> bool:
        """A steward can reach the right answer from what the two records show."""
        a, b = recs[p["record_id_l"]], recs[p["record_id_r"]]
        ev = evidence(a, b)
        agree = ev.split("؛")[0] if ev.startswith("يتفق") else ""
        if any(w in agree for w in ("الرقم الضريبي", "الهاتف", "البريد")):
            return True
        na = {S.name(x, norm) for x in (a["name"], a["name_alt"]) if x}
        nb = {S.name(x, norm) for x in (b["name"], b["name_alt"]) if x}
        return bool(na & nb)

    pools: dict[str, list[dict]] = {}
    for p in band:
        if (p["record_id_l"], p["record_id_r"]) in used:
            continue
        k = kind(p)
        if k.startswith("same") and not defensible(p):
            continue
        if k == "sister" and "رقم السجل" not in evidence(recs[p["record_id_l"]], recs[p["record_id_r"]]):
            continue
        pools.setdefault(k, []).append(p)
    want = {"sister": 5, "same_cross": 3, "same_cr_typo": 2, "same_other": 2, "other_diff": 2}
    chosen = []
    for k, n in want.items():
        pool = sorted(pools.get(k, []), key=lambda p: (p["record_id_l"], p["record_id_r"]))
        assert len(pool) >= n, (k, len(pool))
        chosen += [(k, p) for p in rng.sample(pool, n)]
    rng.shuffle(chosen)

    # Six suppliers on the split code that no other system settles
    split = [r for r in recs.values() if r["source"] == "FIN" and r["activity_code"] == "A-310"]
    mcp_by_cr = {digits(r["cr_number"]): r for r in recs.values() if r["source"] == "MCP" and digits(r["cr_number"])}
    unsettled = sorted((r for r in split if digits(r["cr_number"]) not in mcp_by_cr), key=lambda r: r["record_id"])
    cons = [r for r in unsettled if truth[r["record_id"]]["activity"] == "medcons"]
    devs = [r for r in unsettled if truth[r["record_id"]]["activity"] == "meddev"]
    codes = rng.sample(cons, 3) + rng.sample(devs, 3)
    rng.shuffle(codes)

    cases, model_view, sugg, key = [], [], [], []
    wrong_plan = {"sister": 2, "same_cross": 1, "same_cr_typo": 1}
    wrong_used = {k: 0 for k in wrong_plan}
    code_wrong_done = False
    items = [("match", k, p) for k, p in chosen[:7]] + [("code", None, codes[0]), ("code", None, codes[1])] + \
            [("match", k, p) for k, p in chosen[7:]] + [("code", None, r) for r in codes[2:]]
    for i, (ctype, k, x) in enumerate(items, start=1):
        cid = f"Q{i:02d}"
        days = rng.randint(1, 9)
        if ctype == "match":
            a, b = recs[x["record_id_l"]], recs[x["record_id_r"]]
            prob = float(x["match_probability"])
            reason = "registration numbers differ" if prob == 0.5 and digits(a["cr_number"]) and digits(b["cr_number"]) \
                else "probability between the thresholds"
            cases.append([cid, "match", reason, days, f"{prob:.2f}"] +
                         [a[c] for c in ["record_id", "source"] + PUBLIC + ["phone", "email"]] +
                         [b[c] for c in ["record_id", "source"] + PUBLIC + ["phone", "email"]])
            model_view.append([cid, "match"] + [a[c] for c in PUBLIC] + [b[c] for c in PUBLIC])
            right = "merge" if k.startswith("same") else "separate"
            wrong = wrong_used.get(k, 0) < wrong_plan.get(k, 0)
            if wrong:
                wrong_used[k] += 1
            said = ("separate" if right == "merge" else "merge") if wrong else right
            if k == "sister":
                why_key = "شركتان شقيقتان بنشاطين مختلفين"
                rat = ("الاسم التجاري نفسه، والاختلاف في كلمة النشاط فقط" if wrong
                       else "الاسم التجاري نفسه لكن النشاط ورقم السجل مختلفان، فهما منشأتان")
            elif k == "same_cross":
                why_key = "المورد نفسه، اسمه بالعربية في سجل وبالإنجليزية في الآخر"
                rat = ("الاسمان بلغتين مختلفتين ولا يتطابقان حرفيًا" if wrong
                       else "الاسم الإنجليزي نقل حرفي للاسم العربي")
            elif k == "same_cr_typo":
                why_key = "المورد نفسه، ورقما السجل يختلفان بخطأ إدخال"
                rat = ("رقما السجل التجاري مختلفان، فهما منشأتان" if wrong
                       else "رقما السجل يختلفان في خانتين متجاورتين فقط، والأرجح خطأ إدخال")
            elif k == "same_other":
                why_key = "المورد نفسه بصيغتين للاسم"
                rat = "الاسمان صيغتان للاسم نفسه، والمعرفات المتاحة لا تتعارض"
            else:
                why_key = "موردان مختلفان يشتركان في الكلمة التجارية فقط"
                rat = "الكلمة التجارية مشتركة، لكن بقية الاسم والمعرفات المتاحة لا تتفق"
            conf = "عالية" if wrong or prob > .8 else "متوسطة"
            sugg.append([cid, said, conf, rat])
            key.append([cid, right, f"{why_key} ({evidence(a, b)})", "yes" if wrong else "no"])
        else:
            r = x
            act = truth[r["record_id"]]["activity"]
            right = "GD-MED-CON" if act == "medcons" else "GD-MED-DEV"
            cases.append([cid, "code", "code split in version 1.1", days, ""] +
                         [r[c] for c in ["record_id", "source"] + PUBLIC + ["phone", "email"]] + [""] * 10)
            model_view.append([cid, "code"] + [r[c] for c in PUBLIC] + [""] * len(PUBLIC))
            wrong = not code_wrong_done and act == "medcons"
            if wrong:
                code_wrong_done = True
            said = ("GD-MED-DEV" if right == "GD-MED-CON" else "GD-MED-CON") if wrong else right
            rat = ("كلمة «الطبية» في الاسم تدل على أجهزة طبية" if wrong
                   else ("الاسم يذكر المستلزمات الطبية، وهي مواد مستهلكة" if right == "GD-MED-CON"
                         else "الاسم يذكر الأجهزة الطبية، وهي معدات معمرة"))
            sugg.append([cid, said, "عالية" if wrong else "متوسطة", rat])
            key.append([cid, right, "اسم المورد يحدد النوع: " + ("مستلزمات" if right == "GD-MED-CON" else "أجهزة"),
                        "yes" if wrong else "no"])
    assert sum(1 for k in key if k[3] == "yes") == 5, key
    side = ["record_id", "source"] + PUBLIC + ["phone", "email"]
    write_csv(FILES / "queue" / "queue_cases.csv",
              ["case_id", "case_type", "reason", "days_waiting", "match_probability"] +
              [f"{c}_1" for c in side] + [f"{c}_2" for c in side], cases)
    write_csv(FILES / "queue" / "model_view.csv",
              ["case_id", "case_type"] + [f"{c}_1" for c in PUBLIC] + [f"{c}_2" for c in PUBLIC], model_view)
    write_csv(FILES / "queue" / "model_suggestions.csv", ["case_id", "suggestion", "confidence", "reason"], sugg)
    write_csv(REF / "queue_key.csv", ["case_id", "decision", "why", "model_wrong"], key)
    said = {x[0]: x[1] for x in sugg}
    role = {"code": "business_steward"}
    log = []
    for (cid, decision, why, _), case in zip(key, cases):
        who = "business_steward" if case[1] == "code" or case[2] != "registration numbers differ" else "technical_steward"
        log.append([cid, decision, said[cid], decision, "yes" if decision != said[cid] else "no", why, who, ""])
    write_csv(REF / "decision_log_reference.csv", ["case_id", "first_decision", "model_suggestion", "final_decision",
                                                   "overruled_model", "evidence", "decided_by", "escalated_to"], log)
    for f in ("queue_review_band.csv", "queue_match_quality.csv"):
        (OUT / f).unlink(missing_ok=True)
    print(f"queue: {len(cases)} cases, model wrong on {sum(1 for k in key if k[3] == 'yes')}")


if __name__ == "__main__":
    main()
