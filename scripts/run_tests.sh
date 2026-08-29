#!/usr/bin/env bash
# Local test runner for the autonomous bot.
# Runs all safe, network-free unit tests + the secret-scan gate.
# Exits non-zero if any test fails (so CI blocks regressions).
set -u

cd "$(dirname "$0")/.." || exit 1

fail=0

run() {
    echo "=== $1 ==="
    if python3 "$1"; then
        echo "OK: $1"
    else
        echo "FAIL: $1"
        fail=1
    fi
}

# Security gate (must always run)
run scripts/scan_secrets.py
run scripts/precommit_secrets.py

# Pure unit tests (no network / no credentials)
run scripts/test_coverage_report.py
run scripts/test_scan_secrets.py
run scripts/test_precommit_secrets.py
run test_sync_pagination.py
run test_sync_relations.py
run test_htr_type_aware.py
run test_migrations.py
run test_name_phonetics.py
run test_api_quality_filter.py

if [ "$fail" -ne 0 ]; then
    echo "RESULT: FAILED"
    exit 1
fi
echo "RESULT: ALL TESTS PASSED"
