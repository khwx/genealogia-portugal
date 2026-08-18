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

Idempotent and read-only: never writes to the HTR output dir. Writes a JSON
report to OUTPUT_REPORT (default output/htr_coverage.json) when --write is set.

Usage:
  python3 scripts/coverage_report.py            # print summary only
  python3 scripts/coverage_report.py --write    # also write JSON report
"""
import os
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from htr_cloud_v2 import parse_gemini_json

INPUT_DIR = Path(os.environ.get("INPUT_DIR", "/home/pxtkhw/projetos/obitos/output/htr_text"))
OUTPUT_REPORT = Path(os.environ.get("OUTPUT_REPORT", "/home/pxtkhw/projetos/obitos/output/htr_coverage.json"))


def _nonempty_transcription(text):
    if not text or not isinstance(text, str):
        return False
    t = text.strip().lower()
    if not t:
        return False
    # Treat known "nothing useful" markers as empty
    return t not in ("[ilegível]", "[ilegivel]", "null", "none", "[]", "{}")


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
    }


def load_htr_files(input_dir=INPUT_DIR):
    """Yield parsed HTR dicts from the output dir (read-only)."""
    for p in sorted(input_dir.glob("*.json")):
        try:
            yield json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue


def main():
    write = "--write" in sys.argv
    metrics = analyze(load_htr_files(INPUT_DIR))
    print("=== HTR coverage report ===")
    print(f"  total files          : {metrics['total']}")
    print(f"  parsed_ok            : {metrics['parsed_ok']} ({metrics['parse_rate_pct']}%)")
    print(f"  with transcription   : {metrics['with_transcription']} ({metrics['transcription_rate_pct']}%)")
    print(f"  with deceased struct : {metrics['with_deceased']} ({metrics['deceased_rate_pct']}%)")
    print(f"  deceased persons     : {metrics['deceased_persons']}")
    if write:
        OUTPUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_REPORT.write_text(json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\nReport written to {OUTPUT_REPORT}")
    return metrics


if __name__ == "__main__":
    main()
