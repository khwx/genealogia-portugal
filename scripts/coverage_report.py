#!/usr/bin/env python3
"""
Coverage / quality report for HTR output (óbitos, nascimentos, casamentos).

Scans output/htr_text/*.json and computes measurable progress metrics so each
autonomous 8h cycle can quantify OCR quality without touching the running
pipeline, the network, or any secret/credential.

Metrics produced:
  - total / parsed_ok counts and parse rate
  - transcription coverage (% files with non-empty transcription)
  - deceased coverage (% files with >=1 structured deceased entry)
  - aggregate deceased person count
  - relation-readiness (% deceased persons carrying father/mother/spouse),
    which quantifies the value of the pending relation-backfill migration
    (see migrations/add_pessoa_relation_columns.sql)

Idempotent and read-only: never writes to the HTR output dir. Writes a JSON
report to OUTPUT_REPORT (default output/htr_coverage.json) when --write is set,
and optionally appends a timestamped entry to a local trend history
(output/htr_coverage_history.json) when --trend is set — so each autonomous
8h cycle can measure progress over time.

Usage:
  python3 scripts/coverage_report.py            # print summary only
  python3 scripts/coverage_report.py --write    # also write JSON report
  python3 scripts/coverage_report.py --write --trend   # + append trend history
"""
import os
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from htr_cloud_v2 import parse_gemini_json

INPUT_DIR = Path(os.environ.get("INPUT_DIR", "/home/pxtkhw/projetos/obitos/output/htr_text"))
OUTPUT_REPORT = Path(os.environ.get("OUTPUT_REPORT", "/home/pxtkhw/projetos/obitos/output/htr_coverage.json"))
OUTPUT_TREND = Path(os.environ.get("OUTPUT_TREND", "/home/pxtkhw/projetos/obitos/output/htr_coverage_history.json"))

RELATION_KEYS = ("father", "mother", "spouse")


def _nonempty_transcription(text):
    if not text or not isinstance(text, str):
        return False
    t = text.strip().lower()
    if not t:
        return False
    # Treat known "nothing useful" markers as empty
    return t not in ("[ilegível]", "[ilegivel]", "null", "none", "[]", "{}")


def _nonempty_relation(value):
    """A relation value counts only if it is a non-empty string."""
    return isinstance(value, str) and value.strip() != ""


def analyze(files):
    """Compute coverage metrics from an iterable of parsed HTR dicts.

    Each element must be a dict with keys: file_id, parsed_ok, transcription,
    deceased. Returns a metrics dict. Pure / deterministic (no I/O).
    """
    total = 0
    parsed = 0
    with_transcription = 0
    with_deceased = 0
    deceased_persons = 0
    persons_with_father = 0
    persons_with_mother = 0
    persons_with_spouse = 0
    persons_with_any_relation = 0

    for d in files:
        total += 1
        if d.get("parsed_ok"):
            parsed += 1
        if _nonempty_transcription(d.get("transcription")):
            with_transcription += 1
        deceased = d.get("deceased") or []
        if isinstance(deceased, list) and len(deceased) > 0:
            with_deceased += 1
            deceased_persons += len(deceased)
            for person in deceased:
                if not isinstance(person, dict):
                    continue
                has_father = _nonempty_relation(person.get("father"))
                has_mother = _nonempty_relation(person.get("mother"))
                has_spouse = _nonempty_relation(person.get("spouse"))
                if has_father:
                    persons_with_father += 1
                if has_mother:
                    persons_with_mother += 1
                if has_spouse:
                    persons_with_spouse += 1
                if has_father or has_mother or has_spouse:
                    persons_with_any_relation += 1

    def pct(n, d):
        return round(100.0 * n / d, 1) if d else 0.0

    return {
        "total": total,
        "parsed_ok": parsed,
        "parse_rate_pct": pct(parsed, total),
        "with_transcription": with_transcription,
        "transcription_rate_pct": pct(with_transcription, total),
        "with_deceased": with_deceased,
        "deceased_rate_pct": pct(with_deceased, total),
        "deceased_persons": deceased_persons,
        "persons_with_father": persons_with_father,
        "persons_with_mother": persons_with_mother,
        "persons_with_spouse": persons_with_spouse,
        "persons_with_any_relation": persons_with_any_relation,
        "relation_readiness_pct": pct(persons_with_any_relation, deceased_persons),
    }


def load_htr_files(input_dir=INPUT_DIR):
    """Yield parsed HTR dicts from the output dir (read-only)."""
    for p in sorted(input_dir.glob("*.json")):
        try:
            yield json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue


def record_trend(metrics, trend_path=OUTPUT_TREND):
    """Append a timestamped snapshot to the local trend history (no network).

    Idempotent over reruns only in the sense that each run adds a new point;
    safe to call repeatedly. Returns the updated history list.
    """
    import datetime

    history = []
    if trend_path.exists():
        try:
            history = json.loads(trend_path.read_text(encoding="utf-8"))
            if not isinstance(history, list):
                history = []
        except (json.JSONDecodeError, OSError):
            history = []
    snapshot = dict(metrics)
    snapshot["timestamp"] = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    history.append(snapshot)
    trend_path.parent.mkdir(parents=True, exist_ok=True)
    trend_path.write_text(json.dumps(history, indent=2, ensure_ascii=False), encoding="utf-8")
    return history


def main():
    write = "--write" in sys.argv
    trend = "--trend" in sys.argv
    metrics = analyze(load_htr_files(INPUT_DIR))
    print("=== HTR coverage report ===")
    print(f"  total files          : {metrics['total']}")
    print(f"  parsed_ok            : {metrics['parsed_ok']} ({metrics['parse_rate_pct']}%)")
    print(f"  with transcription   : {metrics['with_transcription']} ({metrics['transcription_rate_pct']}%)")
    print(f"  with deceased struct : {metrics['with_deceased']} ({metrics['deceased_rate_pct']}%)")
    print(f"  deceased persons     : {metrics['deceased_persons']}")
    print(f"  persons w/ father    : {metrics['persons_with_father']}")
    print(f"  persons w/ mother    : {metrics['persons_with_mother']}")
    print(f"  persons w/ spouse    : {metrics['persons_with_spouse']}")
    print(f"  persons w/ relation  : {metrics['persons_with_any_relation']} ({metrics['relation_readiness_pct']}%)")
    if write:
        OUTPUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_REPORT.write_text(json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\nReport written to {OUTPUT_REPORT}")
    if trend:
        history = record_trend(metrics)
        print(f"Trend history updated: {len(history)} snapshot(s) in {OUTPUT_TREND}")
    return metrics


if __name__ == "__main__":
    main()
