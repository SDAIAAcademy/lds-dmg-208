"""Form golden records from approved match clusters with survivorship rules. From labs/:

    uv run kit/golden.py files/golden/survivorship_start.yml
    uv run kit/golden.py my_survivorship.yml

For each cluster and each attribute the rule file names one rule:

    source_priority   the first source in `order` that holds a value
    most_recent       the value of the record updated last; `ignore_dates_from` lists sources
                      whose dates do not say when the supplier changed it
    most_frequent     the value most records agree on; a tie goes to `order`

Prints, for each attribute, how many of the 60 suppliers the stewards verified by telephone are
right, and how many clusters had sources that disagree. Writes out/golden_records.csv (with the
record each value came from), out/golden_xref.csv (golden id to source records) and appends what
changed since the last run to out/golden_history.csv.
"""
from __future__ import annotations

import argparse
import re
from collections import Counter

from common import FILES, OUT, log_run, read_csv, read_yaml, utf8, write_csv
import standardise as S

ATTRS = ["name_ar", "name_en", "cr_number", "vat_number", "city", "phone", "email"]
SOURCES = ["FIN", "MCP", "PMC"]
NORM = {"arabic": {"unify_alef": True, "taa_marbuta": True, "alef_maqsura": True, "remove_diacritics": True,
                   "remove_tatweel": True}, "latin": {"lowercase": True}, "strip_punctuation": True}


def city_lookup() -> dict[str, str]:
    """English and Arabic spellings of a city to its Arabic name (files/golden/cities.csv)."""
    out = {}
    for r in read_csv(FILES / "golden" / "cities.csv"):
        for k in (r["city_ar"], r["city_en"]):
            out[S.name(k, NORM)] = r["city_ar"]
    return out


def values(rec: dict, cities: dict, placeholders: set[str]) -> dict:
    """The attribute values one source record offers, in a comparable form."""
    names = [rec["name"], rec["name_alt"]]
    ar = next((n.strip() for n in names if n and S.is_arabic(n)), None)
    en = next((n.strip() for n in names if n and not S.is_arabic(n)), None)
    cr = S.digits(rec["cr_number"])
    city = cities.get(S.name(rec["city"], NORM) or "", rec["city"] or None)
    return {
        "name_ar": ar, "name_en": en,
        "cr_number": None if cr in placeholders else cr,
        "vat_number": S.digits(rec["vat_number"]),
        "city": city, "phone": S.phone(rec["phone"]),
        "email": (rec["email"] or "").strip().lower() or None,
    }


def comparable(attr: str, v: str | None) -> str | None:
    if v is None:
        return None
    if attr in ("name_ar", "name_en"):
        s = S.name(v, NORM)
        return re.sub(r"\s+", " ", s) if s else None
    return v


def choose(attr: str, rule: dict, offers: list[tuple[dict, dict]]) -> tuple[str | None, str | None]:
    """offers: (record, values). Returns (value, record_id)."""
    kind = rule.get("rule", "source_priority")
    order = rule.get("order", SOURCES)
    rank = {s: i for i, s in enumerate(order)}
    have = [(r, v[attr]) for r, v in offers if v[attr]]
    if not have:
        return None, None
    if kind == "source_priority":
        have.sort(key=lambda x: (rank.get(x[0]["source"], 99), x[0]["record_id"]))
        return have[0][1], have[0][0]["record_id"]
    if kind == "most_recent":
        ignore = set(rule.get("ignore_dates_from", []))
        def key(x):
            d = "0000-00-00" if x[0]["source"] in ignore else x[0]["last_updated"]
            return (d, -rank.get(x[0]["source"], 99))
        have.sort(key=key, reverse=True)
        return have[0][1], have[0][0]["record_id"]
    if kind == "most_frequent":
        cnt = Counter(comparable(attr, v) for _, v in have)
        best = max(cnt.values())
        tied = [(r, v) for r, v in have if cnt[comparable(attr, v)] == best]
        tied.sort(key=lambda x: (rank.get(x[0]["source"], 99), x[0]["record_id"]))
        return tied[0][1], tied[0][0]["record_id"]
    raise SystemExit(f"unknown rule for {attr}: {kind}")


def run(rule_path: str, quiet: bool = False, folder: str = "files/golden", out_prefix: str = "") -> dict:
    rules = read_yaml(rule_path)
    attrs = rules.get("attributes", {}) or {}
    placeholders = {str(x) for x in rules.get("placeholders", [])}
    missing = [a for a in ATTRS if a not in attrs]
    if missing:
        raise SystemExit(f"the rule file has no rule for: {', '.join(missing)}")
    cities = city_lookup()
    recs = read_csv(f"{folder}/cluster_records.csv")
    by_cluster: dict[str, list[dict]] = {}
    for r in recs:
        by_cluster.setdefault(r["cluster_id"], []).append(r)
    golden, xref, conflicts = {}, [], Counter()
    for cid in sorted(by_cluster):
        offers = [(r, values(r, cities, placeholders)) for r in by_cluster[cid]]
        g = {}
        for a in ATTRS:
            g[a] = choose(a, attrs[a], offers)
            distinct = {comparable(a, v[a]) for _, v in offers if v[a]}
            if len(distinct) > 1:
                conflicts[a] += 1
        golden[cid] = g
        xref += [[f"G-{cid[1:]}", r["record_id"], r["source"]] for r in by_cluster[cid]]

    verified = read_csv(f"{folder}/verified_sample.csv")
    right, empty = Counter(), Counter()
    wrong_examples: dict[str, list[str]] = {}
    for v in verified:
        g = golden[v["cluster_id"]]
        for a in ATTRS:
            truth = comparable(a, v[a])
            if g[a][0] is None:
                empty[a] += 1
            elif comparable(a, g[a][0]) == truth:
                right[a] += 1
            else:
                wrong_examples.setdefault(a, []).append(v["cluster_id"])
    wrong_examples = {a: ex for a, ex in wrong_examples.items()}
    n = len(verified)

    OUT.mkdir(exist_ok=True)
    header = ["golden_id", "cluster_id"] + [x for a in ATTRS for x in (a, f"{a}_from")]
    rows = [[f"G-{cid[1:]}", cid] + [x for a in ATTRS for x in g[a]] for cid, g in golden.items()]
    prev_path = OUT / f"{out_prefix}golden_records.csv"
    previous = {r["golden_id"]: r for r in read_csv(prev_path)} if prev_path.exists() else {}
    write_csv(prev_path, header, rows)
    write_csv(OUT / f"{out_prefix}golden_xref.csv", ["golden_id", "record_id", "source"], xref)
    hist_path = OUT / f"{out_prefix}golden_history.csv"
    hist = read_csv(hist_path) if hist_path.exists() else []
    run_no = 1 + max([int(h["run"]) for h in hist], default=0)
    changes = 0
    for row in rows:
        gid = row[0]
        old = previous.get(gid)
        for i, a in enumerate(ATTRS):
            new = row[2 + 2 * i]
            if old is None or (old[a] or None) != (new or None):
                hist.append({"run": run_no, "golden_id": gid, "attribute": a, "old": (old or {}).get(a, ""),
                             "new": new or "", "rule": attrs[a].get("rule"), "rule_file": rule_path})
                changes += old is not None
    write_csv(hist_path, ["run", "golden_id", "attribute", "old", "new", "rule", "rule_file"],
              [[h["run"], h["golden_id"], h["attribute"], h["old"], h["new"], h["rule"], h["rule_file"]] for h in hist])

    result = {"clusters": len(golden), "records": len(recs), "verified": n,
              "right": {a: right[a] for a in ATTRS}, "empty": {a: empty[a] for a in ATTRS}, "conflicts": {a: conflicts[a] for a in ATTRS},
              "changed_since_last_run": changes}
    log_run("golden", [rule_path], result)
    if not quiet:
        print(f"rule file: {rule_path}")
        print(f"golden records: {len(golden):,} from {len(recs):,} source records")
        print(f"{'attribute':<11} {'rule':<16} {'right':>6} {'wrong':>6} {'empty':>6} {'clusters in conflict':>21}")
        for a in ATTRS:
            print(f"{a:<11} {attrs[a].get('rule', ''):<16} {right[a]:>6} {n - right[a] - empty[a]:>6} {empty[a]:>6} "
                  f"{conflicts[a]:>21}")
        print(f"verified suppliers: {n}; values right: {sum(right.values())} of {n * len(ATTRS)}, "
              f"empty because no source holds them: {sum(empty.values())}")
        if previous:
            print(f"values changed since the last run: {changes:,} (out/{out_prefix}golden_history.csv, run {run_no})")
        for a, ex in wrong_examples.items():
            print(f"  wrong {a}: {', '.join(ex[:6])}{' ...' if len(ex) > 6 else ''}")
    return result


def main() -> None:
    utf8()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("rules")
    run(ap.parse_args().rules)


if __name__ == "__main__":
    main()
