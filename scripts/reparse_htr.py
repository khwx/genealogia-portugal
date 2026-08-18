#!/usr/bin/env python3
"""
Reparse existing HTR output files to extract structured data from raw_text.

Files written before parse_gemini_json was added (2026-08-16) may contain valid
JSON in raw_text but have parsed_ok=False. This script re-parses them and
updates the output and metadata files with transcription/deceased/parsed_ok.

Idempotent: safe to run multiple times. Only updates files that need it.

Usage:
  python3 scripts/reparse_htr.py              # dry-run (default)
  python3 scripts/reparse_htr.py --apply      # actually write changes
"""
import os
import sys
import re
import json
from pathlib import Path

# Reuse parse_gemini_json from htr_cloud_v2
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from htr_cloud_v2 import parse_gemini_json

INPUT_DIR = Path(os.environ.get("INPUT_DIR", "/home/pxtkhw/projetos/obitos/output/htr_text"))
METADATA_DIR = Path(os.environ.get("METADATA_DIR", "/home/pxtkhw/projetos/obitos/output/htr_metadata"))

APPLY = "--apply" in sys.argv


def reparse_file(htr_path):
    """Reparse a single HTR output file. Returns (changed, file_id)."""
    file_id = htr_path.stem
    data = json.loads(htr_path.read_text(encoding="utf-8"))

    # Skip files already parsed successfully
    if data.get("parsed_ok"):
        return False, file_id

    raw_text = data.get("raw_text", "")
    if not raw_text:
        return False, file_id

    parsed = parse_gemini_json(raw_text)
    if parsed is None:
        return False, file_id

    # Update output file
    data["transcription"] = parsed.get("transcription")
    data["deceased"] = parsed.get("deceased")
    data["parsed_ok"] = True

    if APPLY:
        htr_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    # Update metadata file
    meta_path = METADATA_DIR / f"{file_id}.json"
    if meta_path.exists():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if not meta.get("parsed_ok"):
            meta["parsed_ok"] = True
            if APPLY:
                meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")

    return True, file_id


def main():
    htr_files = sorted(INPUT_DIR.glob("*.json"))
    print(f"Scanning {len(htr_files)} HTR output files...")

    reparsed = 0
    skipped = 0
    already_ok = 0

    for htr_path in htr_files:
        changed, file_id = reparse_file(htr_path)
        if changed:
            reparsed += 1
            if reparsed <= 5:
                print(f"  [REPARSE] {file_id}")
        else:
            data = json.loads(htr_path.read_text(encoding="utf-8"))
            if data.get("parsed_ok"):
                already_ok += 1
            else:
                skipped += 1

    mode = "APPLIED" if APPLY else "DRY-RUN"
    print(f"\n{mode}: {reparsed} files reparsed, {already_ok} already OK, {skipped} unparseable")
    if not APPLY and reparsed > 0:
        print("Run with --apply to write changes.")


if __name__ == "__main__":
    main()
