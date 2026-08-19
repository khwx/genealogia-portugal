#!/usr/bin/env python3
"""Isolated unit tests for the structured `deceased` sync helpers.

Run:  python3 test_sync_relations.py
"""
import importlib.util
import os
from pathlib import Path


def _load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ROOT = Path(__file__).resolve().parent
sync = _load_module("sync_htr_supabase", ROOT / "sync_htr_supabase.py")


def test_extract_persons_relations():
    deceased = [
        {
            "name": "Dom João da Silva",
            "death_date": "1901-05-03",
            "age": 72,
            "father": "Manuel da Silva",
            "mother": "Maria de Jesus",
            "spouse": "Ana Rodrigues",
        },
        {"nome": "Maria", "death_date": "1899-12-05"},  # no relations
    ]
    persons = sync.extract_persons_from_deceased(deceased)
    assert len(persons) == 2

    p0 = persons[0]
    # Honorific 'Dom' dropped; 'da' kept as part of given name.
    assert p0["nome"] == "João da"
    assert p0["sobrenome"] == "Silva"
    assert p0["pai"] == "Manuel da Silva"
    assert p0["mae"] == "Maria de Jesus"
    assert p0["conjuge"] == "Ana Rodrigues"
    assert p0["death_date"] == "1901-05-03"

    p1 = persons[1]
    assert p1["nome"] == "Maria"
    assert p1["pai"] == ""
    assert p1["mae"] == ""
    assert p1["conjuge"] == ""


def test_build_relation_patch():
    # Empty / no person -> None (nothing to write)
    assert sync.build_relation_patch([]) is None
    assert sync.build_relation_patch(None) is None

    # Person with no relations -> None
    persons = [{"nome": "Maria", "pai": "", "mae": "", "conjuge": ""}]
    assert sync.build_relation_patch(persons) is None

    # Person with relations -> patch dict (only first person used)
    persons = [
        {
            "nome": "João",
            "pai": "Manuel",
            "mae": "Maria",
            "conjuge": "Ana",
        },
        {
            "nome": "Outro",
            "pai": "Ignorado",
            "mae": "",
            "conjuge": "",
        },
    ]
    patch = sync.build_relation_patch(persons)
    assert patch == {"pai": "Manuel", "mae": "Maria", "conjuge": "Ana"}


def test_build_url_patch():
    # No file_id -> nothing to write
    assert sync.build_url_patch({"id": 1, "imagem_url": None}) is None
    assert sync.build_url_patch({"id": 1}) is None

    # Missing imagem_url -> patch with dissemination link
    patch = sync.build_url_patch({"id": 1, "file_id": "ABC123"})
    assert patch == {
        "imagem_url": "https://digitarq.arquivos.pt/rdigital/dissemination?fileId=ABC123"
    }

    # Already set to the exact link -> skip (None)
    url = "https://digitarq.arquivos.pt/rdigital/dissemination?fileId=ABC123"
    assert sync.build_url_patch({"id": 1, "file_id": "ABC123", "imagem_url": url}) is None

    # Wrong/empty imagem_url -> patch (correct it)
    patch = sync.build_url_patch({"id": 1, "file_id": "ABC123", "imagem_url": ""})
    assert patch["imagem_url"].endswith("fileId=ABC123")


def test_normalize_death_date():
    assert sync.normalize_death_date("2020-3-5") == "2020-03-05"
    assert sync.normalize_death_date("05/12/1899") == "1899-12-05"
    assert sync.normalize_death_date("3 de Maio de 1901") == "1901-05-03"
    assert sync.normalize_death_date("13/13/1901") is None  # invalid month
    assert sync.normalize_death_date("1499-05-03") is None  # year out of range (own check)
    assert sync.normalize_death_date("") is None
    assert sync.normalize_death_date(None) is None


if __name__ == "__main__":
    test_extract_persons_relations()
    test_build_relation_patch()
    test_build_url_patch()
    test_normalize_death_date()
    print("OK: all sync_relations tests passed")
