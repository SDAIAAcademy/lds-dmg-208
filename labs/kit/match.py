"""Run a matching rule file on supplier records and measure it on labelled pairs. From labs/:

    uv run kit/match.py files/matching/rules_start.yml
    uv run kit/match.py my_rules.yml --dashboard

Reads the records and the labelled pairs (files/matching/ unless the rule file names others),
standardises names and numbers as the rule file says, trains a probabilistic model with Splink
(expectation maximisation, no labels used), adds the deterministic rules, and prints precision and
recall at the rule file's two thresholds, for each script class (ar-ar, en-en, ar-en) and overall.
Writes out/match_quality.csv, out/review_band.csv (the pairs between the two thresholds) and, with
--dashboard, out/cluster_studio.html (Splink's cluster viewer, opened in a browser).
"""
from __future__ import annotations

import argparse
import logging
import sys
import time

import duckdb
import pyarrow as pa

from common import OUT, log_run, pct, read_csv, read_yaml, resolve, utf8, write_csv
import standardise as S

COLUMNS = ["name_std", "alt_std", "name_key", "alt_key", "cr_number", "vat_number", "phone", "email", "city_key"]


def prepare(rules: dict, records: list[dict]) -> list[dict]:
    st = rules.get("standardise", {}) or {}
    num = rules.get("numbers", {}) or {}
    remove = S.remove_set(st)
    key_remove = S.remove_set({**st, "remove_words": st.get("key_remove_words") or []}) | remove
    holders = [str(x) for x in (num.get("placeholders") or [])]
    out = []
    for r in records:
        ns = S.name(r["name"], st, remove)
        al = S.name(r["name_alt"], st, remove)
        if num.get("digits_only"):
            cr, vat = S.digits(r["cr_number"], holders), S.digits(r["vat_number"], holders)
        else:
            cr = r["cr_number"] or None
            vat = r["vat_number"] or None
            if cr in holders:
                cr = None
        ph = S.phone(r["phone"]) if num.get("phone_local") else (r["phone"] or None)
        city_std = S.name(r["city"], {"arabic": {"unify_alef": True, "taa_marbuta": True}, "latin": {}})
        ck = (S.skeleton(city_std) or "").split(" ")[0] or None if rules.get("compare", {}).get("city") == "key" \
            else (r["city"] or None)
        key = st.get("cross_script_key")
        out.append({
            "record_id": r["record_id"], "source": r["source"], "name": r["name"],
            "script": "ar" if S.is_arabic(r["name"]) else "en",
            "name_std": ns, "alt_std": al,
            "name_key": S.skeleton(S.name(r["name"], st, key_remove)) if key else None,
            "alt_key": S.skeleton(S.name(r["name_alt"], st, key_remove)) if key else None,
            "cr_number": cr, "vat_number": vat, "phone": ph, "email": (r["email"] or "").lower() or None,
            "city_key": ck,
        })
    return out


def exact(col: str, label: str) -> dict:
    return {"output_column_name": label, "comparison_levels": [
        {"sql_condition": f'"{col}_l" IS NULL OR "{col}_r" IS NULL', "label_for_charts": "missing", "is_null_level": True},
        {"sql_condition": f'"{col}_l" = "{col}_r"', "label_for_charts": "same"},
        {"sql_condition": "ELSE", "label_for_charts": "different"},
    ]}


def name_comparison(levels: list[float]) -> dict:
    best = ("greatest(coalesce(jaro_winkler_similarity(name_std_l, name_std_r), 0), "
            "coalesce(jaro_winkler_similarity(name_std_l, alt_std_r), 0), "
            "coalesce(jaro_winkler_similarity(alt_std_l, name_std_r), 0), "
            "coalesce(jaro_winkler_similarity(alt_std_l, alt_std_r), 0))")
    lv = [{"sql_condition": "name_std_l IS NULL OR name_std_r IS NULL", "label_for_charts": "missing",
           "is_null_level": True},
          {"sql_condition": "name_std_l = name_std_r OR name_std_l = alt_std_r OR alt_std_l = name_std_r",
           "label_for_charts": "same name"}]
    for t in sorted(levels, reverse=True):
        lv.append({"sql_condition": f"{best} >= {float(t)}", "label_for_charts": f"similarity {t}"})
    lv.append({"sql_condition": "ELSE", "label_for_charts": "different"})
    return {"output_column_name": "name", "comparison_levels": lv}


def key_comparison() -> dict:
    return {"output_column_name": "name_key", "comparison_levels": [
        {"sql_condition": "coalesce(name_key_l, alt_key_l) IS NULL OR coalesce(name_key_r, alt_key_r) IS NULL",
         "label_for_charts": "missing", "is_null_level": True},
        {"sql_condition": "name_key_l = name_key_r OR name_key_l = alt_key_r OR alt_key_l = name_key_r "
                          "OR alt_key_l = alt_key_r", "label_for_charts": "same key"},
        {"sql_condition": "ELSE", "label_for_charts": "different"},
    ]}


def settings(rules: dict):
    from splink import block_on

    cmp = rules.get("compare", {}) or {}
    comps = [name_comparison(cmp.get("name") or [0.9])]
    if cmp.get("name_key"):
        comps.append(key_comparison())
    for col in ("cr_number", "vat_number", "phone", "email"):
        if cmp.get(col):
            comps.append(exact(col, col))
    if cmp.get("city"):
        comps.append(exact("city_key", "city"))
    blocks = [block_on(*b) for b in rules.get("blocking", [])]
    return {
        "link_type": "dedupe_only",
        "unique_id_column_name": "record_id",
        "blocking_rules_to_generate_predictions": blocks,
        "comparisons": comps,
        "additional_columns_to_retain": ["source", "script", "name"],
        "retain_intermediate_calculation_columns": True,
    }


def deterministic_pairs(con, rules: dict) -> set[tuple[str, str]]:
    pairs: set[tuple[str, str]] = set()
    for cols in rules.get("deterministic", []) or []:
        cond = " AND ".join(f'l."{c}" IS NOT NULL AND l."{c}" = r."{c}"' for c in cols)
        q = f"SELECT l.record_id, r.record_id FROM recs l JOIN recs r ON {cond} AND l.record_id < r.record_id"
        pairs.update(con.execute(q).fetchall())
    return pairs


def run(rule_path: str, dashboard: bool = False, quiet: bool = False, records_path: str | None = None,
        labels_path: str | None = None, out_prefix: str = "") -> dict:
    from splink import DuckDBAPI, Linker, block_on

    t0 = time.time()
    rules = read_yaml(rule_path)
    data = rules.get("data", {}) or {}
    records_path = records_path or data.get("records", "files/matching/records.csv")
    labels_path = labels_path or data.get("labels", "files/matching/labelled_pairs.csv")
    record_files = records_path if isinstance(records_path, list) else [records_path]
    recs = prepare(rules, [r for f in record_files for r in read_csv(f)])
    labels = read_csv(labels_path)

    con = duckdb.connect()
    cols = ["record_id", "source", "name", "script"] + COLUMNS
    table = pa.Table.from_pylist([{c: r[c] for c in cols} for r in recs],
                                 schema=pa.schema([(c, pa.string()) for c in cols]))
    con.register("recs_arrow", table)
    con.execute("CREATE TABLE recs AS SELECT * FROM recs_arrow")
    con.unregister("recs_arrow")
    det = deterministic_pairs(con, rules)
    low, high = sorted(float(x) for x in rules.get("thresholds", [0.5, 0.9]))

    logging.getLogger("splink").setLevel(logging.ERROR)
    db = DuckDBAPI(connection=con)
    df = db.register("recs")
    linker = Linker(df, settings(rules), log_level=logging.ERROR)
    linker.training.estimate_probability_two_random_records_match([block_on("phone"), block_on("email")], recall=0.6)
    linker.training.estimate_u_using_random_sampling(max_pairs=1e6, seed=208)
    for col in ("phone", "email"):
        linker.training.estimate_parameters_using_expectation_maximisation(block_on(col))
    pred = linker.inference.predict(threshold_match_probability=0.001)
    pred_rows = con.execute(f"SELECT record_id_l, record_id_r, match_probability FROM {pred.physical_name}").fetchall()
    prob = {(a, b) if a < b else (b, a): p for a, b, p in pred_rows}
    # Hold-back rules: a pair that disagrees on any listed column never becomes an automatic match;
    # at most it waits in the review band.
    held = 0
    hold_cols = [c for cols in (rules.get("hold_back", []) or []) for c in cols]
    if hold_cols:
        val = {r["record_id"]: r for r in recs}
        for k, pv in prob.items():
            a, b = val[k[0]], val[k[1]]
            if pv >= low and any(a[c] and b[c] and a[c] != b[c] for c in hold_cols):
                prob[k] = min(pv, low)
                held += 1
        det = {k for k in det if not any(val[k[0]][c] and val[k[1]][c] and val[k[0]][c] != val[k[1]][c]
                                         for c in hold_cols)}

    rows, result = [], {"thresholds": [low, high], "deterministic_pairs": len(det), "compared_pairs": len(prob),
                        "held_back": held}
    for t in (low, high):
        for cls in ("ar-ar", "en-en", "ar-en", "all"):
            tp = fp = fn = tn = 0
            for lab in labels:
                if cls != "all" and lab["script_class"] != cls:
                    continue
                key = tuple(sorted((lab["record_id_l"], lab["record_id_r"])))
                said = key in det or prob.get(key, 0.0) >= t
                truth = lab["is_match"] == "1"
                tp += said and truth
                fp += said and not truth
                fn += (not said) and truth
                tn += (not said) and not truth
            p = tp / (tp + fp) if tp + fp else None
            r = tp / (tp + fn) if tp + fn else None
            rows.append([t, cls, tp, fp, fn, tn, "" if p is None else round(p, 4), "" if r is None else round(r, 4)])
            result[f"{cls}@{t}"] = {"precision": p, "recall": r, "tp": tp, "fp": fp, "fn": fn}
    OUT.mkdir(exist_ok=True)
    write_csv(OUT / f"{out_prefix}match_quality.csv",
              ["threshold", "script_class", "tp", "fp", "fn", "tn", "precision", "recall"], rows)
    band = [(a, b, p) for (a, b), p in prob.items() if low <= p < high and (a, b) not in det]
    above = sum(1 for k, p in prob.items() if p >= high) + sum(1 for k in det if prob.get(k, 0) < high)
    write_csv(OUT / f"{out_prefix}review_band.csv", ["record_id_l", "record_id_r", "match_probability"],
              [[a, b, round(p, 4)] for a, b, p in sorted(band)])
    result["review_band"] = len(band)
    result["auto_matches"] = above
    if dashboard:
        clusters = linker.clustering.cluster_pairwise_predictions_at_threshold(pred, high)
        linker.visualisations.cluster_studio_dashboard(
            pred, clusters, str(OUT / f"{out_prefix}cluster_studio.html"), sampling_method="by_cluster_size",
            sample_size=12, overwrite=True)
        result["dashboard"] = f"out/{out_prefix}cluster_studio.html"
    result["seconds"] = round(time.time() - t0, 1)
    log_run("match", [rule_path, *record_files, labels_path], {k: v for k, v in result.items()})
    if not quiet:
        print(f"rule file: {rule_path}")
        print(f"pairs compared: {len(prob):,} · deterministic matches: {len(det):,} · held back: {held:,}")
        print(f"{'threshold':>9} {'script':>6} {'TP':>4} {'FP':>4} {'FN':>4} {'precision':>10} {'recall':>8}")
        for t, cls, tp, fp, fn, tn, p, r in rows:
            print(f"{t:>9} {cls:>6} {tp:>4} {fp:>4} {fn:>4} {pct(p if p != '' else None):>10} "
                  f"{pct(r if r != '' else None):>8}")
        print(f"auto matches at {high}: {above:,} · pairs between the thresholds (to review): {len(band):,}")
        if dashboard:
            print(f"dashboard: {result['dashboard']}")
    con.close()
    return result


def main() -> None:
    utf8()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("rules")
    ap.add_argument("--dashboard", action="store_true")
    a = ap.parse_args()
    if not resolve(a.rules).exists():
        sys.exit(f"no such rule file: {a.rules}")
    run(a.rules, dashboard=a.dashboard)


if __name__ == "__main__":
    main()
