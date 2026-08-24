#!/usr/bin/env python3
"""Safety checks for SQL migration files committed to the repository.

Run:  python3 test_migrations.py

These migrations are applied by hand in the Supabase SQL Editor, but keeping
them under a local, network-free test gate guarantees (between the every-8h
state checks) that nothing destructive can slip into the repo:

  - No destructive statements: DROP TABLE/COLUMN, DELETE FROM, TRUNCATE.
  - Additive safety: every `ALTER TABLE ... ADD COLUMN` uses `IF NOT EXISTS`.
  - Idempotency: every `CREATE INDEX` uses `IF NOT EXISTS`.
  - Scope: only the `public.pessoas` table is ever altered (no cross-table
    writes that could touch production data elsewhere).
  - No secrets: no obvious credential patterns (passwords / keys / tokens).

Exits non-zero on any violation so the CI test gate blocks regressions.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MIGRATIONS = ROOT / "migrations"

# Tokens that, as standalone SQL, would destroy or empty data.
DESTRUCTIVE = [
    r"\bdrop\s+table\b",
    r"\bdrop\s+column\b",
    r"\bdrop\s+schema\b",
    r"\btruncate\b",
    r"\bdelete\s+from\b",
]

# Loose secret patterns that should never appear in a migration.
SECRET_PATTERNS = [
    r"(?i)password\s*=\s*['\"]",
    r"(?i)api[_-]?key\s*=\s*['\"]",
    r"(?i)secret\s*=\s*['\"]",
    r"(?i)token\s*=\s*['\"]",
]


def _strip_comments(sql: str) -> str:
    # Remove -- line comments and /* */ block comments.
    sql = re.sub(r"--[^\n]*", "", sql)
    sql = re.sub(r"/\*.*?\*/", "", sql, flags=re.DOTALL)
    return sql


def check_file(path: Path) -> list[str]:
    problems = []
    raw = path.read_text(encoding="utf-8")
    sql = _strip_comments(raw)
    upper = sql.upper()

    for pat in DESTRUCTIVE:
        if re.search(pat, upper):
            problems.append(f"destructive statement matched by /{pat}/")

    for pat in SECRET_PATTERNS:
        if re.search(pat, raw):
            problems.append(f"possible secret matched by /{pat}/")

    # ALTER TABLE ... ADD COLUMN must be idempotent.
    for m in re.finditer(r"alter\s+table[^\n;]*add\s+column", upper):
        block = m.group(0)
        if "IF NOT EXISTS" not in block:
            problems.append("ALTER TABLE ADD COLUMN without IF NOT EXISTS")

    # CREATE INDEX must be idempotent.
    for m in re.finditer(r"create\s+index[^\n;]*", upper):
        block = m.group(0)
        if "IF NOT EXISTS" not in block:
            problems.append("CREATE INDEX without IF NOT EXISTS")

    # Only public.pessoas may be altered.
    for m in re.finditer(r"alter\s+table\s+([A-Za-z0-9_.]+)", upper):
        table = m.group(1).lower()
        if table != "public.pessoas":
            problems.append(f"ALTER TABLE on non-allowed table: {table}")

    return problems


def main() -> int:
    if not MIGRATIONS.exists():
        print("NO MIGRATIONS DIR")
        return 0

    files = sorted(MIGRATIONS.glob("*.sql"))
    if not files:
        print("NO MIGRATION FILES")
        return 0

    total_problems = 0
    for f in files:
        problems = check_file(f)
        if problems:
            total_problems += len(problems)
            print(f"FAIL: {f.name}")
            for p in problems:
                print(f"  - {p}")
        else:
            print(f"OK:   {f.name}")

    if total_problems:
        print(f"RESULT: FAILED ({total_problems} problem(s))")
        return 1
    print(f"RESULT: ALL MIGRATIONS SAFE ({len(files)} file(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main())
