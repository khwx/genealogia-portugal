#!/usr/bin/env python3
"""Pre-commit security guard for the autonomous bot.

`scripts/scan_secrets.py` only inspects *tracked* files. A secret accidentally
written into a brand-new, untracked file that is NOT git-ignored would sail
through that gate and land on GitHub the moment `git add .` is run.

This guard closes that gap: it scans the exact set of files `git add .` would
stage — tracked files plus untracked files that are not git-ignored — and also
asserts that `.env` is git-ignored and untracked. It reuses the same patterns
and heuristics from `scan_secrets.py` so behaviour stays consistent.

Exit code 0 = safe to commit, 1 = a secret was found or `.env` is exposed.
"""
import subprocess
import sys
from pathlib import Path

from scan_secrets import PATTERNS, _is_allowed_path, _looks_like_placeholder, SKIP_EXT

ROOT = Path(__file__).resolve().parent.parent


def _run(cmd):
    try:
        return subprocess.run(
            cmd, capture_output=True, text=True, cwd=ROOT, check=False
        )
    except FileNotFoundError:
        return None


def candidate_files():
    """Files that `git add .` would stage: tracked + untracked-not-ignored."""
    tracked_out = _run(["git", "ls-files"])
    tracked = set(tracked_out.stdout.splitlines()) if tracked_out else set()

    status_out = _run(
        ["git", "status", "--porcelain", "--untracked-files=all"]
    )
    extra = set()
    if status_out:
        for line in status_out.stdout.splitlines():
            if not line.strip():
                continue
            status, path = line[:2], line[3:]
            if status != "??":
                continue  # modified/staged files are already in `tracked`
            ign = _run(["git", "check-ignore", "-q", path])
            if ign is not None and ign.returncode != 0 and Path(ROOT / path).is_file():
                extra.add(path)
    return sorted(tracked | extra)


def check_env_protected():
    """Return (ok, detail). .env must be git-ignored AND not tracked."""
    ign = _run(["git", "check-ignore", "-q", ".env"])
    ignored = ign is not None and ign.returncode == 0
    tracked_out = _run(["git", "ls-files", ".env"])
    tracked = bool(tracked_out and tracked_out.stdout.strip())
    if ignored and not tracked:
        return True, ".env is git-ignored and untracked"
    return False, f".env ignored={ignored} tracked={tracked}"


def scan_text(text):
    findings = []
    if not __import__("re").search(r"[A-Za-z0-9]", text):
        return findings
    for label, rx in PATTERNS:
        for m in rx.finditer(text):
            secret = m.group(0)
            if _looks_like_placeholder(secret):
                continue
            line_no = text.count("\n", 0, m.start()) + 1
            findings.append((label, line_no, secret))
    return findings


def main():
    files = candidate_files()
    total = 0
    for path in files:
        if _is_allowed_path(path):
            continue
        if Path(path).suffix in SKIP_EXT:
            continue
        try:
            text = Path(ROOT / path).read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for label, line_no, secret in scan_text(text):
            total += 1
            preview = secret if len(secret) <= 12 else secret[:6] + "…" + secret[-4:]
            print(f"[SECRET] {path}:{line_no}  {label}  {preview}")

    ok, detail = check_env_protected()
    if not ok:
        total += 1
        print(f"[SECURITY] {detail}")

    if total:
        print(f"\nFAILED: {total} issue(s) found — abort commit.")
        return 1
    print(f"OK: pre-commit guard scanned {len(files)} file(s); .env check: {detail}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
