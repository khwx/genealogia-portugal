#!/usr/bin/env python3
"""Unit tests for scripts/coverage_report.py (no network, no I/O)."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.coverage_report import analyze, _nonempty_transcription

SAMPLE = [
    {"file_id": "1", "parsed_ok": True, "transcription": "João faleceu", "deceased": [{"name": "João"}]},
    {"file_id": "2", "parsed_ok": True, "transcription": "[ilegível]", "deceased": []},
    {"file_id": "3", "parsed_ok": False, "transcription": "", "deceased": None},
    {"file_id": "4", "parsed_ok": True, "transcription": "Maria e Pedro", "deceased": [{"name": "Maria"}, {"name": "Pedro"}]},
]


def test_analyze_counts():
    m = analyze(SAMPLE)
    assert m["total"] == 4
    assert m["parsed_ok"] == 3
    assert m["parse_rate_pct"] == 75.0
    assert m["with_transcription"] == 2  # file 2 is [ilegível] -> empty
    assert m["with_deceased"] == 2
    assert m["deceased_persons"] == 3
    assert m["transcription_rate_pct"] == 50.0
    assert m["deceased_rate_pct"] == 50.0


def test_empty_input():
    m = analyze([])
    assert m["total"] == 0
    assert m["parse_rate_pct"] == 0.0


def test_nonempty_transcription_markers():
    assert not _nonempty_transcription("")
    assert not _nonempty_transcription("[ilegível]")
    assert not _nonempty_transcription("null")
    assert _nonempty_transcription("João")
    assert _nonempty_transcription("texto real")


if __name__ == "__main__":
    test_analyze_counts()
    test_empty_input()
    test_nonempty_transcription_markers()
    print("ALL TESTS PASSED")
