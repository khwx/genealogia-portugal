#!/usr/bin/env python3
"""
Security gate: scan git-tracked files for accidentally committed secrets.

Designed to be run (a) locally by the autonomous bot before each commit and
(b) in CI on every push/PR so a real secret can never reach GitHub.

It only inspects files tracked by git (`git ls-files`), so the local `.env`
(untracked, ignored) is never read. Known placeholders (`.env.example`, keys
that are obviously fake) are skipped to avoid false positives.

Exit code 0 = clean, 1 = one or more secrets found.
"""
import os
import re
import subprocess
import sys
from pathlib import Path

# --- Secret patterns --------------------------------------------------------
# Order matters: more specific first. Publishable Supabase keys (sb_publishable_)
# are intentionally NOT flagged — they are designed to be public.
PATTERNS = [
    ("Google API key", re.compile(r"AIza[0-9A-Za-z_\-]{35}")),
    ("Google OAuth token", re.compile(r"ya29\.[0-9A-Za-z_\-]+")),
    ("OpenAI API key", re.compile(r"sk-[0-9A-Za-z]{20,}")),
    ("Slack token", re.compile(r"xox[baprs]-[0-9A-Za-z\-]+")),
    ("Supabase service-role key", re.compile(r"sb_secret_[0-9A-Za-z]+")),
    ("AWS access key id", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("Private key block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("Generic bearer secret", re.compile(r"Bearer\s+(?:eyJ|AIza|ya29|sb_secret)[0-9A-Za-z_\-\.=]{20,}")),
]

# Heuristic to skip obviously fake / placeholder secrets (e.g. "AIzaSyxxx…").
def _looks_like_placeholder(match: str) -> bool:
    body = match[4:] if match.startswith("AIza") else match
    unique = set(body)
    # A real key has lots of entropy; a placeholder is mostly repeated chars.
    if len(unique) <= 3:
        return True
    # Explicit "x"/"0" padding placeholders.
    if re.fullmatch(r"[xX0_\-]{8,}", body):
        return True
    return False

# Files that are allowed to contain sample keys (documentation / examples).
def _is_allowed_path(path: str) -> bool:
    name = os.path.basename(path)
    return (
        name.endswith(".example")
        or name == ".env.example"
        or ".env.example" in path
        or path.endswith("scan_secrets.py")
    )

# Binary-ish extensions we never want to scan.
SKIP_EXT = {
    ".png", ".jpg", ".jpeg", ".gif", ".tiff", ".tif", ".pdf", ".zip",
    ".gz", ".tar", ".deb", ".whl", ".so", ".pyc", ".db", ".sqlite",
    ".sqlite3", ".mp4", ".mov",
}


def tracked_files() -> list[str]:
    try:
        out = subprocess.run(
            ["git", "ls-files"],
            capture_output=True, text=True, check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        # Not a git repo: fall back to scanning the whole tree minus .env.
        root = Path(".")
        files = [
            str(p) for p in root.rglob("*")
            if p.is_file() and ".git" not in p.parts
            and p.name != ".env" and p.suffix not in SKIP_EXT
        ]
        return files
    return [f for f in out.stdout.splitlines() if f.strip()]


def scan_file(path: str) -> list[tuple[str, int, str]]:
    if _is_allowed_path(path):
        return []
    if Path(path).suffix in SKIP_EXT:
        return []
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read()
    except OSError:
        return []
    # Quick reject: skip files with no alphanumerics at all.
    if not re.search(r"[A-Za-z0-9]", text):
        return []
    findings = []
    for label, rx in PATTERNS:
        for m in rx.finditer(text):
            secret = m.group(0)
            if _looks_like_placeholder(secret):
                continue
            line_no = text.count("\n", 0, m.start()) + 1
            findings.append((label, line_no, secret))
    return findings


def main() -> int:
    files = tracked_files()
    total = 0
    for path in files:
        found = scan_file(path)
        for label, line_no, secret in found:
            total += 1
            preview = secret if len(secret) <= 12 else secret[:6] + "…" + secret[-4:]
            print(f"[SECRET] {path}:{line_no}  {label}  {preview}")
    if total:
        print(f"\nFAILED: {total} potential secret(s) found in tracked files.")
        return 1
    print(f"OK: scanned {len(files)} tracked file(s), no secrets found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
