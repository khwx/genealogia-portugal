#!/usr/bin/env python3
"""
Redact real Gemini API keys stored in output/htr_metadata/*.json.

Some older HTR runs wrote the full API key into each metadata file under the
`key` field. This script replaces that value with a redacted fingerprint
(first 4 + last 4 chars, middle masked) so the file stays useful for
monitoring without exposing the secret on disk.

Idempotent: already-redacted values are left untouched.
Dry-run by default; pass --apply to rewrite files.
"""
import json
import os
import sys
from pathlib import Path

METADATA_DIR = Path(os.environ.get(
    "METADATA_DIR", "/home/pxtkhw/projetos/obitos/output/htr_metadata"))
APPLY = "--apply" in sys.argv


def mask_key(key):
    if not key or not isinstance(key, str):
        return ""
    key = key.strip()
    if len(key) <= 8:
        return "*" * len(key)
    return f"{key[:4]}{'*' * (len(key) - 8)}{key[-4:]}"


def main():
    files = sorted(METADATA_DIR.glob("*.json"))
    redacted = 0
    skipped = 0
    for path in files:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        key = data.get("key")
        if not key or "*" in str(key):
            skipped += 1
            continue
        data["key"] = mask_key(key)
        if APPLY:
            path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        redacted += 1
        if APPLY and redacted % 500 == 0:
            print(f"  redacted {redacted}...")
    print(f"{'Would redact' if not APPLY else 'Redacted'}: {redacted} files")
    print(f"Already clean / skipped: {skipped} files")
    if not APPLY:
        print("Run with --apply to rewrite the files.")


if __name__ == "__main__":
    main()
