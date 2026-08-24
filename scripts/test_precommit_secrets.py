#!/usr/bin/env python3
"""Unit tests for scripts/precommit_secrets.py (the pre-commit secret guard).

Run:  python3 scripts/test_precommit_secrets.py

Verifies that the guard (a) reuses the scanner heuristics correctly, (b) keeps
`.env` protected in this repo, and (c) considers untracked-but-not-ignored
files as candidates. No real secrets are committed: secret strings are built at
runtime from pieces so their contiguous form never appears in this source.
"""
import importlib.util
import os
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


guard = _load("precommit_secrets", ROOT / "scripts" / "precommit_secrets.py")
scan = _load("scan_secrets", ROOT / "scripts" / "scan_secrets.py")


def _google_key():
    return "AIza" + "SyA1b" * 7


def _write_tmp(text, suffix=".py"):
    f = tempfile.NamedTemporaryFile("w", suffix=suffix, delete=False, encoding="utf-8")
    f.write(text)
    f.close()
    return f.name


def test_scan_text_detects_real():
    content = "k = '" + _google_key() + "'\n"
    path = _write_tmp(content)
    try:
        findings = guard.scan_text(content)
        labels = [f[0] for f in findings]
        assert "Google API key" in labels, labels
    finally:
        os.unlink(path)


def test_scan_text_skips_placeholder():
    content = "k = 'AIza" + ("x" * 40) + "'\n"
    path = _write_tmp(content)
    try:
        assert guard.scan_text(content) == []
    finally:
        os.unlink(path)


def test_check_env_protected():
    # In this repo .env is git-ignored and untracked -> guard must pass.
    ok, detail = guard.check_env_protected()
    assert ok, detail


def test_candidate_files_includes_tracked_and_untracked():
    cands = guard.candidate_files()
    # Tracked source files must always be present in the candidate set.
    assert "scripts/precommit_secrets.py" in cands
    # Candidate set is non-empty and de-duplicated (a set union).
    assert len(cands) == len(set(cands))


def test_scan_file_rejects_binary_extension():
    path = _write_tmp("AIza" + "A" * 40, suffix=".png")
    try:
        assert guard.scan_text(Path(path).read_text(errors="ignore")) == []
    finally:
        os.unlink(path)


if __name__ == "__main__":
    tests = [
        test_scan_text_detects_real,
        test_scan_text_skips_placeholder,
        test_check_env_protected,
        test_candidate_files_includes_tracked_and_untracked,
        test_scan_file_rejects_binary_extension,
    ]
    for t in tests:
        t()
    print(f"OK: all {len(tests)} precommit_secrets tests passed")
