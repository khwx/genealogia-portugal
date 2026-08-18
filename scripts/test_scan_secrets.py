#!/usr/bin/env python3
"""Isolated unit tests for the security secret-scanner (scripts/scan_secrets.py).

Run:  python3 scripts/test_scan_secrets.py

These tests verify that the CI security gate (run on every push/PR) actually
fires on real-looking secrets and stays quiet on placeholders, allowed paths and
binary blobs. No real secrets are committed: every secret string is assembled at
runtime from pieces, so its contiguous form never appears in this source file
(which the scanner also inspects when scanning tracked files).
"""
import importlib.util
import os
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def _load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


scan = _load_module("scan_secrets", ROOT / "scripts" / "scan_secrets.py")


# --- runtime secret builders -------------------------------------------------
# Each returns a secret whose contiguous form exists only at runtime, never as a
# literal in this source file (so the scanner scanning this file sees no match).

def _google_key():
    # AIza + 35 chars, 5 unique -> not a placeholder
    return "AIza" + "SyA1b" * 7


def _openai_key():
    return "sk-" + "A1b2c3D4" * 5


def _slack_key():
    return "xox" + "b-" + "1" * 18


def _supabase_secret():
    return "sb_secret_" + "AbCd12" * 6


def _aws_key():
    return "AKIA" + "ABCD1234EFGH5678"


def _private_key():
    return "-----" + "BEGIN RSA PRIVATE KEY-----"


def _write_tmp(text, suffix=".py"):
    f = tempfile.NamedTemporaryFile("w", suffix=suffix, delete=False, encoding="utf-8")
    f.write(text)
    f.close()
    return f.name


def test_scan_detects_real_secrets():
    lines = [
        "config = {",
        f"    'google': '{_google_key()}'",
        f"    'openai': '{_openai_key()}'",
        f"    'slack': '{_slack_key()}'",
        f"    'supabase': '{_supabase_secret()}'",
        f"    'aws': '{_aws_key()}'",
        f"    'privkey': '{_private_key()}'",
        "}",
    ]
    path = _write_tmp("\n".join(lines) + "\n")
    try:
        findings = scan.scan_file(path)
        labels = sorted(f[0] for f in findings)
        assert "Google API key" in labels, labels
        assert "OpenAI API key" in labels, labels
        assert "Slack token" in labels, labels
        assert "Supabase service-role key" in labels, labels
        assert "AWS access key id" in labels, labels
        assert "Private key block" in labels, labels
        # The google key is on line 2.
        google_finding = [f for f in findings if f[0] == "Google API key"][0]
        assert google_finding[1] == 2, google_finding
    finally:
        os.unlink(path)


def test_scan_skips_placeholders():
    # The scanner's placeholder heuristic (_looks_like_placeholder) only catches
    # low-entropy secrets: (<=3 unique chars) OR a body made entirely of
    # [xX0_-] for 8+ chars. Build exactly those shapes so the keys are matched by
    # the regex but then deliberately skipped.
    parts = [
        "k1 = 'AIza" + ("x" * 40) + "'",               # <=3 unique -> placeholder
        "k2 = 'AIza" + ("X" * 40) + "'",               # single-char body -> placeholder
        "k3 = 'AIza" + ("xX0_" * 10) + "'",            # all [xX0_-], 8+ -> placeholder
    ]
    content = "\n".join(parts) + "\n"
    path = _write_tmp(content)
    try:
        findings = scan.scan_file(path)
        assert findings == [], findings
    finally:
        os.unlink(path)


def test_looks_like_placeholder_logic():
    assert scan._looks_like_placeholder("AIza" + "x" * 35) is True   # all same char
    assert scan._looks_like_placeholder("AIza" + "X" * 35) is True
    assert scan._looks_like_placeholder("AIza" + "y" * 35) is True
    assert scan._looks_like_placeholder(_google_key()) is False     # real entropy
    assert scan._looks_like_placeholder(_openai_key()) is False
    assert scan._looks_like_placeholder(_slack_key()) is False


def test_is_allowed_path():
    assert scan._is_allowed_path("foo/.env.example") is True
    assert scan._is_allowed_path("scripts/scan_secrets.py") is True
    assert scan._is_allowed_path("normal.py") is False
    assert scan._is_allowed_path("src/app.py") is False


def test_scan_skips_binary_extension():
    path = _write_tmp("AIza" + "A" * 40, suffix=".png")
    try:
        assert scan.scan_file(path) == []
    finally:
        os.unlink(path)


def test_scan_no_false_positive_on_clean():
    content = "import os\n\ndef hello():\n    return 'hello world'\n"
    path = _write_tmp(content)
    try:
        assert scan.scan_file(path) == []
    finally:
        os.unlink(path)


def test_main_clean_repo():
    # End-to-end on the real tracked tree: must stay clean (no secrets committed).
    rc = scan.main()
    assert rc == 0


if __name__ == "__main__":
    tests = [
        test_scan_detects_real_secrets,
        test_scan_skips_placeholders,
        test_looks_like_placeholder_logic,
        test_is_allowed_path,
        test_scan_skips_binary_extension,
        test_scan_no_false_positive_on_clean,
        test_main_clean_repo,
    ]
    for t in tests:
        t()
    print(f"OK: all {len(tests)} scan_secrets tests passed")
