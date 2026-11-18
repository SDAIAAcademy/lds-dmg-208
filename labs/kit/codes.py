"""Reference code lists, crosswalk and versions. From labs/, with your files in a folder (codes/ below):

    uv run kit/codes.py profile                      # the codes each system uses, with record counts
    uv run kit/codes.py check codes                  # checks the lists, the crosswalk and the change log
    uv run kit/codes.py check codes --sources files/codes/source_codes.csv files/capstone/rcp_source_codes.csv
    uv run kit/codes.py release codes 1.0            # freezes the folder as version 1.0 (out/releases/)
    uv run kit/codes.py diff 1.0 1.1                 # what changed between two released versions
    uv run kit/codes.py impact codes                 # records whose code changes with the latest version

The folder holds regions.csv, activities.csv, lists.csv, crosswalk.csv and change_log.csv, with the
columns of the templates in files/codes/. A spreadsheet works as well as git: save each file as CSV.
"""
from __future__ import annotations

import argparse
import re
import shutil
import sys
from collections import Counter

from common import FILES, OUT, LABS, log_run, read_csv, resolve, utf8

LIST_COLS = ["code", "name_ar", "name_en", "definition", "parent", "valid_from", "valid_to", "status"]
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def profile() -> None:
    rows = read_csv(FILES / "codes" / "source_codes.csv")
    for kind in ("region", "activity"):
        print(f"\n{kind} codes")
        for system in ("FIN", "MCP", "PMC"):
            sel = [r for r in rows if r["system"] == system and r["code_type"] == kind]
            total = sum(int(r["records"]) for r in sel)
            print(f"  {system}: {len(sel)} codes over {total:,} records")
            for r in sorted(sel, key=lambda r: -int(r["records"])):
                label = f"  {r['source_label']}" if r["source_label"] else ""
                print(f"      {r['source_code']:<18} {int(r['records']):>6}{label}")
    log_run("codes profile", [FILES / "codes" / "source_codes.csv"], {"codes": len(rows)})


def load(folder: str) -> dict:
    f = resolve(folder)
    need = ["regions.csv", "activities.csv", "lists.csv", "crosswalk.csv", "change_log.csv"]
    missing = [n for n in need if not (f / n).exists()]
    if missing:
        sys.exit(f"missing in {folder}: {', '.join(missing)} (start from the templates in files/codes/)")
    return {n[:-4]: read_csv(f / n) for n in need}


def check(folder: str, quiet: bool = False, sources: list[str] | None = None) -> dict:
    d = load(folder)
    problems: list[str] = []
    lists = {r["list_id"]: r for r in d["lists"]}
    codes = {}
    for list_id in ("regions", "activities"):
        rows = d[list_id]
        meta = lists.get(list_id)
        if not meta:
            problems.append(f"lists.csv: no row for {list_id}")
        else:
            for col in ("title", "kind", "owner", "steward", "version"):
                if not (meta.get(col) or "").strip():
                    problems.append(f"lists.csv: {list_id} has no {col}")
            if meta.get("kind") not in ("internal", "external"):
                problems.append(f"lists.csv: kind of {list_id} is internal or external")
            if meta.get("kind") == "external" and not (meta.get("external_source") or "").strip():
                problems.append(f"lists.csv: {list_id} is external: name its source")
        if rows and set(LIST_COLS) - set(rows[0]):
            problems.append(f"{list_id}.csv: missing columns {sorted(set(LIST_COLS) - set(rows[0]))}")
            continue
        seen, names = Counter(r["code"] for r in rows), Counter()
        for code, n in seen.items():
            if n > 1:
                problems.append(f"{list_id}.csv: code {code} appears {n} times")
        active = {r["code"]: r for r in rows if r["status"] == "active"}
        for r in rows:
            c = r["code"]
            if not c.strip():
                problems.append(f"{list_id}.csv: a row without a code")
            for col in ("name_ar", "name_en"):
                if not r[col].strip():
                    problems.append(f"{list_id}.csv: {c} has no {col}")
            if r["status"] == "active":
                names[r["name_ar"].strip()] += 1
            if list_id == "activities" and not r["definition"].strip():
                problems.append(f"activities.csv: {c} has no definition")
            if r["status"] not in ("active", "retired"):
                problems.append(f"{list_id}.csv: {c} status is active or retired")
            if not DATE.match(r["valid_from"] or ""):
                problems.append(f"{list_id}.csv: {c} needs valid_from as YYYY-MM-DD")
            if r["status"] == "retired" and not DATE.match(r["valid_to"] or ""):
                problems.append(f"{list_id}.csv: {c} is retired: give valid_to")
            if r["status"] == "active" and r["valid_to"]:
                problems.append(f"{list_id}.csv: {c} is active but has valid_to")
            if r["parent"]:
                if r["parent"] not in seen:
                    problems.append(f"{list_id}.csv: {c} has parent {r['parent']}, which is not in the list")
                elif list_id == "activities" and not c.startswith(r["parent"] + "-"):
                    problems.append(f"activities.csv: {c} sits under {r['parent']}, but its code says otherwise")
        for name, n in names.items():
            if n > 1:
                problems.append(f"{list_id}.csv: {n} active codes are named {name}")
        codes[list_id] = {"all": set(seen), "active": set(active)}

    src = [r for p in (sources or [str(FILES / "codes" / "source_codes.csv")]) for r in read_csv(resolve(p))]
    xw = {(r["system"], r["code_type"], r["source_code"]): r for r in d["crosswalk"]}
    covered = total = 0
    for s in src:
        key = (s["system"], s["code_type"], s["source_code"])
        n = int(s["records"])
        total += n
        row = xw.get(key)
        target_list = "regions" if s["code_type"] == "region" else "activities"
        if not row or not row["reference_code"].strip():
            problems.append(f"crosswalk.csv: {s['system']} {s['code_type']} '{s['source_code']}' ({n} records) "
                            f"has no reference code")
            continue
        targets = [t.strip() for t in row["reference_code"].split("|")]
        bad = [t for t in targets if t not in codes.get(target_list, {}).get("active", set())]
        if bad:
            problems.append(f"crosswalk.csv: '{s['source_code']}' points to {', '.join(bad)}, "
                            f"not an active code of {target_list}")
            continue
        if len(targets) > 1 and not row["rule_note"].strip():
            problems.append(f"crosswalk.csv: '{s['source_code']}' points to {len(targets)} codes: "
                            f"say in rule_note who decides and how")
            continue
        covered += n

    log = d["change_log"]
    versions = sorted({r["version"] for r in log}, key=lambda v: [int(x) for x in v.split(".") if x.isdigit()])
    for r in log:
        for col in ("version", "change_id", "change_type", "code", "description", "requested_by", "approved_by"):
            if not (r.get(col) or "").strip():
                problems.append(f"change_log.csv: {r.get('change_id') or '?'} has no {col}")
        if r["change_type"] not in ("add", "retire", "rename", "split", "merge", "redefine"):
            problems.append(f"change_log.csv: {r['change_id']} change_type is add, retire, rename, split, "
                            f"merge or redefine")
        known = codes.get("regions", {}).get("all", set()) | codes.get("activities", {}).get("all", set())
        for c in re.split(r"[|,\s]+", r["code"].strip()):
            if c and c != "*" and c not in known:
                problems.append(f"change_log.csv: {r['change_id']} names {c}, which is in no list")
    if versions:
        for list_id, meta in lists.items():
            if meta.get("version") and meta["version"] not in versions and list_id == "activities":
                problems.append(f"lists.csv: activities is at version {meta['version']}, "
                                f"which the change log does not have")
    result = {"problems": len(problems), "records_covered": covered, "records": total,
              "codes": {k: len(v["active"]) for k, v in codes.items()}, "versions": versions}
    log_run("codes check", [resolve(folder) / n for n in ("regions.csv", "activities.csv", "lists.csv",
                                                          "crosswalk.csv", "change_log.csv")], result)
    if not quiet:
        for p in problems:
            print("  FIX ", p)
        print(f"active codes: regions {result['codes'].get('regions', 0)}, "
              f"activities {result['codes'].get('activities', 0)}")
        print(f"source codes in use with a reference code: {covered:,} of {total:,} "
              f"(a region and an activity for each source record)")
        print(f"versions in the change log: {', '.join(versions) or 'none'}")
        print("PASS" if not problems else f"{len(problems)} to fix")
    return result


def release(folder: str, version: str) -> None:
    res = check(folder, quiet=True)
    if res["problems"]:
        sys.exit(f"{res['problems']} problems left: run check first")
    if version not in res["versions"]:
        sys.exit(f"the change log has no entry for version {version}")
    dest = OUT / "releases" / version
    if dest.exists():
        sys.exit(f"version {version} is already released: a released version never changes")
    shutil.copytree(resolve(folder), dest)
    log_run("codes release", [dest / "activities.csv", dest / "crosswalk.csv"], {"version": version})
    print(f"released {version} into out/releases/{version}")


def diff(a: str, b: str) -> None:
    missing = [v for v in (a, b) if not (OUT / "releases" / v / "crosswalk.csv").exists()]
    if missing:
        sys.exit(f"no release {', '.join(missing)} in out/releases: run "
                 f"'uv run kit/codes.py release my_codes <version>' for each version first")
    for list_id in ("regions", "activities"):
        old = {r["code"]: r for r in read_csv(OUT / "releases" / a / f"{list_id}.csv")}
        new = {r["code"]: r for r in read_csv(OUT / "releases" / b / f"{list_id}.csv")}
        for c in sorted(set(old) | set(new)):
            if c not in old:
                print(f"  {list_id}: added {c} {new[c]['name_ar']}")
            elif c not in new:
                print(f"  {list_id}: removed {c} (a code is retired, never removed)")
            else:
                ch = [k for k in LIST_COLS if old[c].get(k) != new[c].get(k)]
                if ch:
                    print(f"  {list_id}: {c} changed {', '.join(ch)}")
    oldx = {(r["system"], r["code_type"], r["source_code"]): r["reference_code"]
            for r in read_csv(OUT / "releases" / a / "crosswalk.csv")}
    for r in read_csv(OUT / "releases" / b / "crosswalk.csv"):
        k = (r["system"], r["code_type"], r["source_code"])
        if oldx.get(k) != r["reference_code"]:
            print(f"  crosswalk: {k[0]} '{k[2]}' {oldx.get(k)} -> {r['reference_code']}")


def impact(folder: str) -> dict:
    """Records whose reference code needs a person: crosswalk rows that point to more than one code."""
    d = load(folder)
    split = {(r["system"], r["source_code"]) for r in d["crosswalk"] if "|" in r["reference_code"]}
    recs = read_csv(FILES / "matching" / "records.csv")
    by_cr: dict[str, set[str]] = {}
    for r in recs:
        cr = re.sub(r"\D", "", r["cr_number"])
        if cr and cr != "0000000000":
            by_cr.setdefault(cr, set()).add(r["activity_code"])
    xw = {(r["system"], r["source_code"]): r["reference_code"] for r in d["crosswalk"] if r["code_type"] == "activity"}
    need, settled = 0, 0
    for r in recs:
        if (r["source"], r["activity_code"]) not in split:
            continue
        cr = re.sub(r"\D", "", r["cr_number"])
        others = {xw.get(("MCP", c), "") for c in by_cr.get(cr, set())} - {""}
        others = {o for o in others if "|" not in o}
        if len(others) == 1:
            settled += 1
        else:
            need += 1
    print(f"records on a split code: {need + settled:,}")
    print(f"  settled by the same registration number in a system that already tells the two apart: {settled:,}")
    print(f"  left for a steward to decide: {need:,}")
    res = {"split_records": need + settled, "settled": settled, "steward": need}
    log_run("codes impact", [resolve(folder) / "crosswalk.csv"], res)
    return res


def main() -> None:
    utf8()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("profile")
    sub.add_parser("impact").add_argument("folder")
    c = sub.add_parser("check")
    c.add_argument("folder")
    c.add_argument("--sources", nargs="+", help="source code files to cover (default: files/codes/source_codes.csv); "
                   "add files/capstone/rcp_source_codes.csv for the fourth source")
    r = sub.add_parser("release")
    r.add_argument("folder")
    r.add_argument("version")
    df = sub.add_parser("diff")
    df.add_argument("a")
    df.add_argument("b")
    a = ap.parse_args()
    if a.cmd == "profile":
        profile()
    elif a.cmd == "check":
        sys.exit(0 if check(a.folder, sources=a.sources)["problems"] == 0 else 1)
    elif a.cmd == "release":
        release(a.folder, a.version)
    elif a.cmd == "diff":
        diff(a.a, a.b)
    else:
        impact(a.folder)


if __name__ == "__main__":
    main()
