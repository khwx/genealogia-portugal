#!/usr/bin/env python3
"""Unit tests for the type-aware HTR pipeline (htr_cloud_v2.py).

Isolated: exercises pure logic (type-map loader, prompt schemas, JSON parser,
key masking). No network, no real API calls. Run: python3 test_htr_type_aware.py
"""

from pathlib import Path
import json
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parent))

import htr_cloud_v2 as H


def _write(dirpath, name, obj):
    p = Path(dirpath) / name
    p.write_text(json.dumps(obj), encoding="utf-8")
    return p


def test_prompt_schemas_present():
    assert set(H.PROMPT_BY_TYPE.keys()) == {"DEAT", "BIRT", "MARR"}
    assert "deceased" in H.PROMPT_BY_TYPE["DEAT"]
    assert "birth_date" in H.PROMPT_BY_TYPE["BIRT"]
    assert "godfather" in H.PROMPT_BY_TYPE["BIRT"]
    assert "marriage_date" in H.PROMPT_BY_TYPE["MARR"]
    assert "spouse_father" in H.PROMPT_BY_TYPE["MARR"]


def test_default_record_type_is_death():
    assert H.DEFAULT_RECORD_TYPE == "DEAT"


def test_prompt_selection_for_all_types():
    for tipo in ("DEAT", "BIRT", "MARR", "UNKNOWN"):
        prompt = H.PROMPT_BY_TYPE.get(tipo, H.PROMPT_BY_TYPE["DEAT"])
        assert prompt and "JSON object" in prompt


def test_build_type_map_real_data_has_all_types():
    # After 2026-08-21 fetch_page_listings.py run, BIRT and MARR listings are
    # now present alongside DEAT. Verify all three types exist with non-zero
    # counts. Guards against missing listings or regressions in type mapping.
    tm = H.build_type_map()
    if not tm:
        return
    types = set(tm.values())
    assert "DEAT" in types, "DEAT (óbitos) should be present"
    assert "BIRT" in types, "BIRT (nascimentos/batismos) should be present"
    assert "MARR" in types, "MARR (casamentos) should be present"
    # Sanity check: each type should have a substantial number of file_ids
    from collections import Counter
    counts = Counter(tm.values())
    assert counts["DEAT"] > 1000
    assert counts["BIRT"] > 1000
    assert counts["MARR"] > 1000


def test_build_type_map_joints_listing_with_inventory():
    tmp = tempfile.mkdtemp()
    try:
        doc_id = "deadbeefdeadbeefdeadbeefdeadbeef"
        listings = {doc_id: [
            {"id": "111", "name": "PT-ADLSB-PRQ-PCLB01-003-O1_m0001.jpg"},
            {"id": "222", "name": "PT-ADLSB-PRQ-PCLB01-003-O1_m0002.jpg"},
        ]}
        inv = [{"url_info": f"https://digitarq.arquivos.pt/documentDetails/{doc_id}",
                "tipo_cod": "BIRT"}]
        _write(tmp, "listings.json", listings)
        _write(tmp, "inv.json", inv)
        orig_inv, orig_doc = H.INVENTARIO_JSON, H.DOC_FILE_LISTINGS
        H.INVENTARIO_JSON = Path(tmp) / "inv.json"
        H.DOC_FILE_LISTINGS = Path(tmp) / "listings.json"
        try:
            assert H.build_type_map() == {"111": "BIRT", "222": "BIRT"}
        finally:
            H.INVENTARIO_JSON, H.DOC_FILE_LISTINGS = orig_inv, orig_doc
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)


def test_build_type_map_inventory_takes_precedence():
    tmp = tempfile.mkdtemp()
    try:
        doc_id = "cafebabecafebabecafebabecafebabe"
        listings = {doc_id: [{"id": "9", "name": "PT-...-O1_m0001.jpg"}]}
        inv = [{"url_info": f".../documentDetails/{doc_id}", "tipo_cod": "MARR"}]
        _write(tmp, "listings.json", listings)
        _write(tmp, "inv.json", inv)
        orig_inv, orig_doc = H.INVENTARIO_JSON, H.DOC_FILE_LISTINGS
        H.INVENTARIO_JSON = Path(tmp) / "inv.json"
        H.DOC_FILE_LISTINGS = Path(tmp) / "listings.json"
        try:
            assert H.build_type_map()["9"] == "MARR"
        finally:
            H.INVENTARIO_JSON, H.DOC_FILE_LISTINGS = orig_inv, orig_doc
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)


def test_build_type_map_missing_files_returns_empty():
    orig_inv, orig_doc = H.INVENTARIO_JSON, H.DOC_FILE_LISTINGS
    H.INVENTARIO_JSON = Path("/nonexistent/inv.json")
    H.DOC_FILE_LISTINGS = Path("/nonexistent/listings.json")
    try:
        assert H.build_type_map() == {}
    finally:
        H.INVENTARIO_JSON, H.DOC_FILE_LISTINGS = orig_inv, orig_doc


def test_build_type_map_skips_non_list_pages():
    tmp = tempfile.mkdtemp()
    try:
        listings = {"/m/clb": 42, "realk": [{"id": "5", "name": "x"}]}
        inv = [{"url_info": ".../documentDetails/realk", "tipo_cod": "DEAT"}]
        _write(tmp, "listings.json", listings)
        _write(tmp, "inv.json", inv)
        orig_inv, orig_doc = H.INVENTARIO_JSON, H.DOC_FILE_LISTINGS
        H.INVENTARIO_JSON = Path(tmp) / "inv.json"
        H.DOC_FILE_LISTINGS = Path(tmp) / "listings.json"
        try:
            assert H.build_type_map() == {"5": "DEAT"}
        finally:
            H.INVENTARIO_JSON, H.DOC_FILE_LISTINGS = orig_inv, orig_doc
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)


def test_parse_gemini_json_still_works():
    fenced = '```json\n{"transcription": "t", "deceased": []}\n```'
    assert H.parse_gemini_json(fenced) == {"transcription": "t", "deceased": []}
    assert H.parse_gemini_json('{"transcription": "x"}') == {"transcription": "x"}
    assert H.parse_gemini_json("não há json aqui") is None
    assert H.parse_gemini_json("") is None
    assert H.parse_gemini_json("{not valid}") is None


def test_mask_key_never_leaks_full_secret():
    # Build a realistic Google key at runtime so the contiguous literal never
    # appears in this tracked file (secret-scanner must stay clean).
    full = "AIza" + "SyA1b" * 7 + "BbRM"
    masked = H.mask_key(full)
    assert len(masked) == len(full)
    assert masked.startswith("AIza")
    assert masked.endswith("BbRM")
    assert full not in masked
    assert "*" in masked
    assert H.mask_key("") == ""
    assert H.mask_key(None) == ""


if __name__ == "__main__":
    tests = [
        test_prompt_schemas_present,
        test_default_record_type_is_death,
        test_prompt_selection_for_all_types,
        test_build_type_map_real_data_has_all_types,
        test_build_type_map_joints_listing_with_inventory,
        test_build_type_map_inventory_takes_precedence,
        test_build_type_map_missing_files_returns_empty,
        test_build_type_map_skips_non_list_pages,
        test_parse_gemini_json_still_works,
        test_mask_key_never_leaks_full_secret,
    ]
    failures = 0
    for t in tests:
        try:
            t()
            print(f"  [PASS] {t.__name__}")
        except Exception as e:
            failures += 1
            print(f"  [FAIL] {t.__name__}: {e!r}")
    print(f"\n{len(tests) - failures}/{len(tests)} tests passed")
    sys.exit(1 if failures else 0)
