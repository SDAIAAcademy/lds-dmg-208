"""Run every lab's reference solution and assert its numbers. From the labs/ folder:

    uv run solutions/check.py            # every lab and the capstone
    uv run solutions/check.py 1.1 2.2    # some of them

Lab 1.1 and the capstone run the real matching (Splink on DuckDB, trained without labels); the
other labs run the course kit on the reference files. It prints the numbers the debriefs quote and
PASS per lab, and checks that the starting files still hold their planted problems. No lab calls a
language model. Outputs go to out/, which git ignores; delete it afterwards.
"""
from __future__ import annotations

import copy
import json
import re
import shutil
import sys
from pathlib import Path

LABS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LABS / "kit"))
from common import FILES, OUT, read_csv, read_yaml, utf8  # noqa: E402
import codes  # noqa: E402
import golden  # noqa: E402
import match  # noqa: E402
import steward  # noqa: E402

import yaml  # noqa: E402

REF = LABS / "solutions" / "reference"
TMP = OUT / "check"


def write_rules(name: str, rules: dict) -> str:
    TMP.mkdir(parents=True, exist_ok=True)
    p = TMP / name
    p.write_text(yaml.safe_dump(rules, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return str(p.relative_to(LABS))


def line(res: dict, t: float) -> str:
    def f(x):
        return "-" if x is None else f"{100 * x:.1f}%"
    parts = []
    for cls in ("ar-ar", "en-en", "ar-en", "all"):
        r = res[f"{cls}@{t}"]
        parts.append(f"{cls} P {f(r['precision'])} R {f(r['recall'])}")
    return " | ".join(parts)


def lab_1_1() -> None:
    start = read_yaml(FILES / "matching" / "rules_start.yml")
    ref = read_yaml(REF / "rules_reference.yml")
    stages = []
    s0 = copy.deepcopy(start)
    stages.append(("0 start", s0))
    s1 = copy.deepcopy(s0)
    s1["standardise"]["arabic"] = ref["standardise"]["arabic"]
    stages.append(("1 Arabic normalisation", s1))
    s2 = copy.deepcopy(s1)
    for k in ("latin", "strip_punctuation", "remove_words"):
        s2["standardise"][k] = ref["standardise"][k]
    stages.append(("2 Latin, punctuation, legal forms", s2))
    s3 = copy.deepcopy(s2)
    s3["standardise"]["cross_script_key"] = True
    s3["standardise"]["key_remove_words"] = ref["standardise"]["key_remove_words"]
    s3["blocking"] = [["name_key"], ["alt_key"], ["cr_number"]]
    s3["compare"]["name_key"] = True
    s3["compare"]["city"] = "key"
    stages.append(("3 cross-script key and blocking", s3))
    s4 = copy.deepcopy(s3)
    s4["numbers"] = ref["numbers"]
    stages.append(("4 numbers and placeholders", s4))
    s5 = copy.deepcopy(s4)
    for k in ("blocking", "deterministic", "hold_back", "compare"):
        s5[k] = ref[k]
    stages.append(("5 blocking on phone and e-mail, hold-back on registration", s5))
    s6 = copy.deepcopy(s5)
    s6["thresholds"] = ref["thresholds"]
    stages.append(("6 thresholds 0.50 and 0.95 (the reference file)", s6))
    results = {}
    for i, (label, rules) in enumerate(stages):
        res = match.run(write_rules(f"stage{i}.yml", rules), quiet=True, out_prefix=f"check_s{i}_")
        results[label] = res
        lo, hi = res["thresholds"]
        print(f"  {label}: compared {res['compared_pairs']:,}, deterministic {res['deterministic_pairs']:,}, "
              f"auto {res['auto_matches']:,}, review band {res['review_band']:,}")
        print(f"      at {lo}: {line(res, lo)}")
        print(f"      at {hi}: {line(res, hi)}")
    ref_res = match.run(str((REF / "rules_reference.yml").relative_to(LABS)), quiet=True, out_prefix="check_ref_")
    first, last = results[stages[0][0]], ref_res
    assert first["all@0.9"]["recall"] < 0.5, "the starting rules should miss more than half of the matches"
    assert first["deterministic_pairs"] > 20000, "the placeholder trap should create tens of thousands of pairs"
    assert last["all@0.95"]["precision"] >= 0.95 and last["all@0.95"]["recall"] >= 0.93, last["all@0.95"]
    assert last["ar-en@0.95"]["recall"] >= 0.9, last["ar-en@0.95"]
    assert last["all@0.5"]["precision"] < last["all@0.95"]["precision"], "the lower threshold trades precision"
    again = match.run(str((REF / "rules_reference.yml").relative_to(LABS)), quiet=True, out_prefix="check_again_")
    assert again["all@0.95"] == last["all@0.95"] and again["review_band"] == last["review_band"], "not repeatable"
    print(f"  reference, repeated: identical ({last['review_band']:,} pairs in the review band)")


def lab_1_2() -> None:
    start = golden.run(str((FILES / "golden" / "survivorship_start.yml").relative_to(LABS)), quiet=True,
                       out_prefix="check_start_")
    naive = read_yaml(FILES / "golden" / "survivorship_start.yml")
    naive["attributes"]["city"] = {"rule": "most_recent"}
    naive["attributes"]["phone"] = {"rule": "most_recent"}
    nres = golden.run(write_rules("survivorship_naive.yml", naive), quiet=True, out_prefix="check_naive_")
    ref = golden.run(str((REF / "survivorship_reference.yml").relative_to(LABS)), quiet=True, out_prefix="check_ref_")
    for label, r in (("start", start), ("most recent, PMC dates trusted", nres), ("reference", ref)):
        print(f"  {label}: right of 60 " + ", ".join(f"{a} {r['right'][a]}" for a in golden.ATTRS)
              + f"; all {sum(r['right'].values())} of 420")
    total = {k: sum(r["right"].values()) for k, r in (("start", start), ("naive", nres), ("ref", ref))}
    assert total["ref"] > total["naive"] > total["start"], total
    assert ref["right"]["city"] > nres["right"]["city"] > start["right"]["city"], (start, nres, ref)
    assert ref["right"]["phone"] >= start["right"]["phone"] + 10
    assert ref["right"]["name_en"] > start["right"]["name_en"]
    assert total["ref"] >= 375, ref["right"]
    xref = read_csv(OUT / "check_ref_golden_xref.csv")
    assert len(xref) == ref["records"] and len({x["golden_id"] for x in xref}) == 3000
    print(f"  conflicts in the 3,000 clusters: " + ", ".join(f"{a} {ref['conflicts'][a]}" for a in golden.ATTRS))


def lab_2_1() -> None:
    work = TMP / "codes"
    shutil.rmtree(OUT / "releases", ignore_errors=True)
    for v in ("1.0", "1.1"):
        res = codes.check(str((REF / "codes" / f"v{v}").relative_to(LABS)), quiet=True)
        assert res["problems"] == 0, res
        assert res["records_covered"] == res["records"] == 40000, res
        codes.release(str((REF / "codes" / f"v{v}").relative_to(LABS)), v)
    imp = codes.impact(str((REF / "codes" / "v1.1").relative_to(LABS)))
    facts = json.loads((REF / "data_facts.json").read_text(encoding="utf-8"))
    assert imp["split_records"] == facts["fin_a310"], (imp, facts)
    print(f"  version 1.1: {codes.check(str((REF / 'codes' / 'v1.1').relative_to(LABS)), quiet=True)['codes']} active codes")
    # the starting draft still holds its planted faults
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True)
    shutil.copy(FILES / "codes" / "activities_draft.csv", work / "activities.csv")
    shutil.copy(REF / "codes" / "v1.0" / "regions.csv", work / "regions.csv")
    shutil.copy(REF / "codes" / "v1.0" / "lists.csv", work / "lists.csv")
    shutil.copy(REF / "codes" / "v1.0" / "crosswalk.csv", work / "crosswalk.csv")
    shutil.copy(REF / "codes" / "v1.0" / "change_log.csv", work / "change_log.csv")
    draft = codes.check(str(work.relative_to(LABS)), quiet=True)
    print(f"  the draft activity list, checked: {draft['problems']} problems")
    assert draft["problems"] >= 8, draft


def lab_2_2() -> None:
    res = steward.score(str((REF / "decision_log_reference.csv").relative_to(LABS)),
                        str(REF / "queue_key.csv"), quiet=True)
    assert res["problems"] == 0 and res["right"] == 20 and res["model_right"] == 15 and res["overruled_model"] == 5, res
    wf = steward.test(str((REF / "workflow_reference.yml").relative_to(LABS)), quiet=True)
    assert wf["problems"] == 0 and wf["routed"] == 20, wf
    view = read_csv(FILES / "queue" / "model_view.csv")
    assert not any(k.startswith(("phone", "email")) for k in view[0]), "the model view must hold Public columns only"
    print(f"  reference log: right 20 of 20, model right {res['model_right']} of 20, overruled {res['overruled_model']}")
    print(f"  reference workflow: load {wf['load']}, late {wf['late']} of 20")


def capstone() -> None:
    rules = read_yaml(REF / "rules_reference.yml")
    rules["data"] = {"records": ["files/matching/records.csv", "files/capstone/rcp_records.csv"],
                     "labels": "files/capstone/rcp_labelled_pairs.csv"}
    res = match.run(write_rules("capstone.yml", rules), quiet=True, out_prefix="check_cap_")
    print(f"  fourth source at 0.50: {line(res, 0.5)}")
    print(f"  fourth source at 0.95: {line(res, 0.95)}")
    rules["thresholds"] = [0.5, 0.8]
    res8 = match.run(write_rules("capstone_08.yml", rules), quiet=True, out_prefix="check_cap8_")
    print(f"  the assessor's change, high threshold 0.80: {line(res8, 0.8)}; review band {res8['review_band']:,} "
          f"(was {res['review_band']:,}); auto matches {res8['auto_matches']:,} (was {res['auto_matches']:,})")
    assert res["all@0.95"]["recall"] >= 0.85, res["all@0.95"]
    assert res8["review_band"] < res["review_band"], "a lower high threshold empties part of the review band"
    # the fourth source code mapping: version 1.1 plus the RCP rows covers every code of the four systems
    work = TMP / "capstone_codes"
    shutil.rmtree(work, ignore_errors=True)
    shutil.copytree(REF / "codes" / "v1.1", work)
    rows = (REF / "capstone" / "rcp_crosswalk_rows.csv").read_text(encoding="utf-8").splitlines()[1:]
    with (work / "crosswalk.csv").open("a", encoding="utf-8", newline=chr(10)) as f:
        f.write(chr(10).join(rows) + chr(10))
    cc = codes.check(str(work.relative_to(LABS)), quiet=True,
                     sources=["files/codes/source_codes.csv", "files/capstone/rcp_source_codes.csv"])
    assert cc["problems"] == 0 and cc["records_covered"] == cc["records"] == 44800, cc
    print(f"  codes for the four systems: {cc['records_covered']:,} of {cc['records']:,} code values covered (a region and an activity for each record)")
    rcp = read_csv(FILES / "capstone" / "rcp_records.csv")
    labelled = sum(1 for r in rcp if r["activity_code"] == "Research equipment")
    plain = lambda s: re.sub("[\u064b-\u0652\u0640]", "", s.lower())   # without diacritics and tatweel
    medical = sum(1 for r in rcp if r["activity_code"] == "Research equipment"
                  and any(w in plain(r["name"]) for w in ("medical", "الطبية", "الطبيه")))
    assert medical == labelled == 231, (medical, labelled)
    print(f"  RCP 'Research equipment': {labelled} records, {medical} of them with a medical word in the name")


LABS_RUN = {"1.1": lab_1_1, "1.2": lab_1_2, "2.1": lab_2_1, "2.2": lab_2_2, "capstone": capstone}


def main() -> None:
    utf8()
    want = sys.argv[1:] or list(LABS_RUN)
    failed = []
    for k in want:
        print(f"lab {k}")
        try:
            LABS_RUN[k]()
            print(f"PASS {k}")
        except AssertionError as e:
            failed.append(k)
            print(f"FAIL {k}: {e}")
    shutil.rmtree(TMP, ignore_errors=True)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
