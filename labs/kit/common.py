"""Shared helpers of the LDS-DMG-208 lab kit: paths, files, the run log."""
from __future__ import annotations

import csv
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

LABS = Path(__file__).resolve().parents[1]
FILES = LABS / "files"
OUT = LABS / "out"


def utf8() -> None:
    """Print Arabic correctly in a Windows console."""
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8")
        except AttributeError:
            pass


def resolve(path: str | Path) -> Path:
    """A path given on the command line, relative to labs/ when it is not absolute."""
    p = Path(path)
    return p if p.is_absolute() else (LABS / p)


def read_csv(path: str | Path) -> list[dict]:
    with resolve(path).open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: str | Path, header: list[str], rows: list[list]) -> Path:
    p = resolve(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)
    return p


def read_yaml(path: str | Path) -> dict:
    return yaml.safe_load(resolve(path).read_text(encoding="utf-8")) or {}


def file_hash(path: str | Path) -> str:
    return hashlib.sha256(resolve(path).read_bytes()).hexdigest()[:12]


def log_run(tool: str, inputs: list[str | Path], result: dict) -> None:
    """Append one line to out/run_log.jsonl: the evidence that a participant ran the kit."""
    OUT.mkdir(exist_ok=True)
    line = {
        "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "tool": tool,
        "inputs": {str(Path(i).as_posix()): file_hash(i) for i in inputs},
        "result": result,
    }
    with (OUT / "run_log.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(line, ensure_ascii=False) + "\n")


def pct(x: float | None) -> str:
    return "-" if x is None else f"{100 * x:.1f}%"
