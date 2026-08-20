#!/usr/bin/env python3
"""Unit tests for scripts/coverage_report.py (no network, no I/O)."""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.coverage_report import (
    analyze,
    _nonempty_transcription,
    _nonempty_relation,
    record_trend,
)

SAMPLE = [
    {"file_id": "1", "parsed_ok": True, "transcription": "João faleceu",
     "deceased": [{"name": "João", "father": "Manuel", "mother": "", "spouse": None}]},
    {"file_id": "2", "parsed_ok": True, "transcription": "[ilegível]", "deceased": []},
    {"file_id": "3", "parsed_ok": False, "transcription": "", "deceased": None},
    {"file_id": "4", "parsed_ok": True, "transcription": "Maria e Pedro",
     "deceased": [{"name": "Maria", "spouse": "Pedro"}, {"name": "Pedro"}]},
]

TYPE_SAMPLE = [
    {"file_id": "a", "record_type": "DEAT", "parsed_ok": True, "transcription": "óbito",
     "deceased": [{"name": "A", "father": "F"}]},
    {"file_id": "b", "record_type": "BIRT", "parsed_ok": True, "transcription": "batismo",
     "deceased": []},
    {"file_id": "c", "record_type": "MARR", "parsed_ok": False, "transcription": "",
     "deceased": []},
    {"file_id": "d", "parsed_ok": True, "transcription": "sem tipo", "deceased": []},  # -> DEAT default
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


def test_analyze_by_type():
    m = analyze(TYPE_SAMPLE)
    bt = m["by_type"]
    assert set(bt) == {"DEAT", "BIRT", "MARR"}
    # DEAT: files a + d(default) = 2 total, 2 parsed, 2 transcription
    assert bt["DEAT"]["total"] == 2
    assert bt["DEAT"]["parsed_ok"] == 2
    assert bt["DEAT"]["with_transcription"] == 2
    assert bt["DEAT"]["with_deceased"] == 1
    assert bt["DEAT"]["deceased_persons"] == 1
    assert bt["DEAT"]["relation_readiness_pct"] == 100.0
    # BIRT: 1 file, parsed
    assert bt["BIRT"]["total"] == 1 and bt["BIRT"]["parsed_ok"] == 1
    # MARR: 1 file, not parsed
    assert bt["MARR"]["total"] == 1 and bt["MARR"]["parsed_ok"] == 0
    # unknown type falls back to DEAT default
    assert bt["BIRT"]["total"] + bt["MARR"]["total"] + bt["DEAT"]["total"] == 4


def test_analyze_relations():
    m = analyze(SAMPLE)
    # João has father; Maria has spouse; Pedro has none -> 2 with any relation
    assert m["persons_with_father"] == 1
    assert m["persons_with_mother"] == 0
    assert m["persons_with_spouse"] == 1
    assert m["persons_with_any_relation"] == 2
    assert m["relation_readiness_pct"] == round(100.0 * 2 / 3, 1)


def test_nonempty_relation():
    assert _nonempty_relation("Manuel")
    assert not _nonempty_relation("")
    assert not _nonempty_relation(None)
    assert not _nonempty_relation(42)


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


def test_record_trend(tmp_path=None):
    path = tmp_path or Path(tempfile.mkdtemp()) / "trend.json"
    h1 = record_trend({"total": 1, "deceased_persons": 3}, trend_path=path)
    assert len(h1) == 1 and "timestamp" in h1[0]
    h2 = record_trend({"total": 2, "deceased_persons": 5}, trend_path=path)
    assert len(h2) == 2
    assert h2[0]["deceased_persons"] == 3 and h2[1]["deceased_persons"] == 5


if __name__ == "__main__":
    test_analyze_counts()
    test_analyze_relations()
    test_nonempty_relation()
    test_empty_input()
    test_nonempty_transcription_markers()
    test_record_trend()
    test_analyze_by_type()
    print("ALL TESTS PASSED")
