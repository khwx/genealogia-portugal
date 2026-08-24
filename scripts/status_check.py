#!/usr/bin/env python3
"""
Autonomous 8h state check for the obitos bot.

Network-free, read-only verification that the repository is safe and healthy:
  - secret scan over tracked files
  - pre-commit secret guard (staged + untracked, non-ignored)
  - unit-test suite (run_tests.sh)
  - .env not accidentally tracked by git

Prints a machine-readable JSON summary and exits non-zero if anything is off,
so a scheduled CI run (every 8h) can alert on regressions.
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def run(cmd):
    try:
        r = subprocess.run(
            cmd, capture_output=True, text=True, cwd=str(ROOT),
        )
        return r.returncode, r.stdout, r.stderr
    except Exception as e:  # pragma: no cover - defensive
        return 1, "", str(e)


def git_ls_files():
    rc, out, _ = run(["git", "ls-files"])
    return [f for f in out.splitlines() if f] if rc == 0 else []


def _state(rc):
    return "clean" if rc == 0 else "FAILED"


def main() -> int:
    report = {}

    rc, _, _ = run([sys.executable, "scripts/scan_secrets.py"])
    report["secret_scan"] = _state(rc)

    rc, _, _ = run([sys.executable, "scripts/precommit_secrets.py"])
    report["precommit_guard"] = _state(rc)

    rc, _, _ = run(["bash", "scripts/run_tests.sh"])
    report["unit_tests"] = "PASSED" if rc == 0 else "FAILED"

    tracked = git_ls_files()
    report["env_exposed"] = ".env" in tracked
    report["tracked_files"] = len(tracked)

    ok = (
        report["secret_scan"] == "clean"
        and report["precommit_guard"] == "clean"
        and report["unit_tests"] == "PASSED"
        and not report["env_exposed"]
    )
    report["status"] = "OK" if ok else "PROBLEM"

    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
