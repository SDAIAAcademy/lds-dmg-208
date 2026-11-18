"""The stewardship queue of lab 2.2. From labs/:

    uv run kit/steward.py show                          # the twenty cases, as a steward sees them
    uv run kit/steward.py model                         # the model's suggestions (open them after your first decision)
    uv run kit/steward.py score my_decisions.csv        # your decision log: overrules and agreement
    uv run kit/steward.py test my_workflow.yml          # who decides each case, and which cases are late

The model saw only files/queue/model_view.csv: the columns classified Public. Its suggestions in
files/queue/model_suggestions.csv were written for this course in place of a model's output.
"""
from __future__ import annotations

import argparse
import sys

from common import FILES, log_run, read_csv, read_yaml, resolve, utf8

CASES = FILES / "queue" / "queue_cases.csv"
SUGG = FILES / "queue" / "model_suggestions.csv"
DECISIONS = {"merge", "separate", "GD-MED-CON", "GD-MED-DEV", "refer"}


def show() -> None:
    for c in read_csv(CASES):
        print(f"\n{c['case_id']} · {c['case_type']} · {c['reason']} · waiting {c['days_waiting']} days"
              + (f" · probability {c['match_probability']}" if c["match_probability"] else ""))
        for side in ("1", "2"):
            if not c[f"record_id_{side}"]:
                continue
            print(f"  {c[f'record_id_{side}']}: {c[f'name_{side}']}"
                  + (f" | {c[f'name_alt_{side}']}" if c[f"name_alt_{side}"] else ""))
            print(f"      registration {c[f'cr_number_{side}'] or '-'} · tax {c[f'vat_number_{side}'] or '-'} · "
                  f"{c[f'city_{side}'] or '-'} · activity {c[f'activity_code_{side}']} · "
                  f"phone {c[f'phone_{side}'] or '-'} · e-mail {c[f'email_{side}'] or '-'}")


def model() -> None:
    for s in read_csv(SUGG):
        print(f"{s['case_id']}: {s['suggestion']:<11} ({s['confidence']}) {s['reason']}")


def score(path: str, key_path: str | None = None, quiet: bool = False) -> dict:
    log = read_csv(path)
    sugg = {s["case_id"]: s["suggestion"] for s in read_csv(SUGG)}
    cases = {c["case_id"] for c in read_csv(CASES)}
    problems, overruled, changed, agree = [], 0, 0, 0
    for r in log:
        cid = r["case_id"]
        if cid not in cases:
            problems.append(f"{cid}: not a case of the queue")
            continue
        for col in ("first_decision", "final_decision"):
            if r[col] not in DECISIONS:
                problems.append(f"{cid}: {col} is one of {', '.join(sorted(DECISIONS))}")
        if not r.get("evidence", "").strip():
            problems.append(f"{cid}: write the evidence the decision rests on")
        if not r.get("decided_by", "").strip():
            problems.append(f"{cid}: say which role decided")
        model_says = sugg.get(cid)
        if r["final_decision"] == model_says:
            agree += 1
        else:
            overruled += 1
            if (r.get("overruled_model") or "").strip().lower() not in ("yes", "نعم"):
                problems.append(f"{cid}: your final decision differs from the model: mark overruled_model yes")
        if r["first_decision"] != r["final_decision"]:
            changed += 1
    missing = sorted(cases - {r["case_id"] for r in log})
    result = {"decided": len(log), "missing": missing, "agree_with_model": agree, "overruled_model": overruled,
              "changed_after_seeing_model": changed, "problems": len(problems)}
    if key_path:
        key = {k["case_id"]: k for k in read_csv(key_path)}
        result["right"] = sum(1 for r in log if key.get(r["case_id"], {}).get("decision") == r["final_decision"])
        result["model_right"] = sum(1 for cid, s in sugg.items() if key[cid]["decision"] == s)
        result["changed_to_model_and_wrong"] = sum(
            1 for r in log if r["first_decision"] != r["final_decision"] and r["final_decision"] == sugg.get(r["case_id"])
            and key[r["case_id"]]["decision"] != r["final_decision"])
    log_run("queue score", [path], result)
    if not quiet:
        for p in problems:
            print("  FIX ", p)
        print(f"decided {len(log)} of {len(cases)}" + (f"; missing: {', '.join(missing)}" if missing else ""))
        print(f"agree with the model: {agree} · overruled the model: {overruled} · "
              f"changed your first decision after seeing the model: {changed}")
        if key_path:
            print(f"right against the key: {result['right']} · the model was right on {result['model_right']} of 20 · "
                  f"changed to the model's wrong answer: {result['changed_to_model_and_wrong']}")
        print("PASS" if not problems and not missing else "to fix")
    return result


def matches(rule: dict, case: dict) -> bool:
    for k, v in (rule.get("when") or {}).items():
        if k == "min_probability":
            if not case["match_probability"] or float(case["match_probability"]) < float(v):
                return False
        elif k == "max_probability":
            if not case["match_probability"] or float(case["match_probability"]) >= float(v):
                return False
        elif str(case.get(k, "")) != str(v):
            return False
    return True


def test(path: str, quiet: bool = False) -> dict:
    wf = read_yaml(path)
    roles = wf.get("roles") or {}
    routes = wf.get("routes") or []
    problems = []
    for i, r in enumerate(routes, start=1):
        if r.get("decides") not in roles:
            problems.append(f"route {i}: decides names a role that is not in roles")
        if r.get("approves") and r["approves"] not in roles:
            problems.append(f"route {i}: approves names a role that is not in roles")
        if not isinstance(r.get("sla_days"), (int, float)):
            problems.append(f"route {i}: give sla_days as a number of working days")
    esc = wf.get("escalation") or {}
    if esc and esc.get("to") not in roles:
        problems.append("escalation: to names a role that is not in roles")
    ind = wf.get("indicators") or []
    if len(ind) < 4:
        problems.append("indicators: name at least four, each with a target")
    for x in ind:
        if not (isinstance(x, dict) and x.get("name") and x.get("target")):
            problems.append("indicators: each one has a name and a target")
            break
    rows, late, unrouted, load = [], 0, 0, {}
    for c in read_csv(CASES):
        route = next((r for r in routes if matches(r, c)), None)
        if not route:
            unrouted += 1
            rows.append((c["case_id"], c["case_type"], "no route", "", ""))
            continue
        left = float(route.get("sla_days", 0)) - int(c["days_waiting"])
        who = route.get("decides")
        load[who] = load.get(who, 0) + 1
        status = "late" if left < 0 else ("escalate" if esc and int(c["days_waiting"]) >= esc.get("after_days", 99)
                                          else "on time")
        late += left < 0
        rows.append((c["case_id"], c["case_type"], roles.get(who, who), status, f"{left:+.0f} days"))
    if unrouted:
        problems.append(f"{unrouted} cases match no route")
    result = {"routed": 20 - unrouted, "late": late, "load": load, "problems": len(problems)}
    log_run("queue test", [path], result)
    if not quiet:
        for r in rows:
            print(f"  {r[0]} {r[1]:<6} {r[2]:<28} {r[3]:<9} {r[4]}")
        print("load: " + ", ".join(f"{roles.get(k, k)} {v}" for k, v in load.items()))
        print(f"late against your service levels: {late} of 20")
        for p in problems:
            print("  FIX ", p)
        print("PASS" if not problems else "to fix")
    return result


def main() -> None:
    utf8()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("show")
    sub.add_parser("model")
    s = sub.add_parser("score")
    s.add_argument("log")
    s.add_argument("--key", help="the trainer's key (solutions/reference/queue_key.csv)")
    t = sub.add_parser("test")
    t.add_argument("workflow")
    a = ap.parse_args()
    if a.cmd == "show":
        show()
    elif a.cmd == "model":
        model()
    elif a.cmd == "score":
        if not resolve(a.log).exists():
            sys.exit(f"no such file: {a.log}")
        score(a.log, a.key)
    else:
        test(a.workflow)


if __name__ == "__main__":
    main()
