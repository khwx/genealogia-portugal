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


ROOT = Path(__file__).resolve().parent.parent
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


def test_extract_persons_relations_pt_keys():
    # Gemini sometimes returns Portuguese relation keys; they must be picked up.
    deceased = [
        {
            "name": "João de Sousa",
            "death_date": "1888-01-02",
            "pai": "Manuel de Sousa",
            "mae": "Maria da Luz",
            "cônjuge": "Ana Pires",
        }
    ]
    persons = sync.extract_persons_from_deceased(deceased)
    assert len(persons) == 1
    p0 = persons[0]
    assert p0["nome"] == "João de"
    assert p0["sobrenome"] == "Sousa"
    assert p0["pai"] == "Manuel de Sousa"
    assert p0["mae"] == "Maria da Luz"
    assert p0["conjuge"] == "Ana Pires"

    # English key takes precedence when both are present (no double-up).
    mixed = [{"name": "Pedro", "father": "Ingles", "pai": "Portugues"}]
    p1 = sync.extract_persons_from_deceased(mixed)[0]
    assert p1["pai"] == "Ingles"


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


def test_extract_persons_from_marriages():
    # Each marriage -> two persons (groom + bride), cross-linked via conjuge.
    marriages = [
        {
            "name": "Francisco Rodrigues Mina",
            "spouse": "Maria Paiva",
            "marriage_date": "1876-06-20",
            "father": "José Rodrigues",
            "mother": "Antonia do Olival",
            "spouse_father": "José Paiva",
            "spouse_mother": "Maria da Luiza",
            "naturalidade": "Linhares",
            "spouse_naturalidade": "Linhares",
            "estado_civil": "viúvo de Theresa Ferreira",
            "spouse_estado_civil": "viúva de Jozé da Cunha Borges",
            "idade": 57,
            "spouse_idade": 54,
            "ocupacao": "jornaleiro",
            "spouse_ocupacao": "jornaleira",
            "numero_assento": "4",
            "dispensa": "dispensa em 3.º e 4.º grau de consanguinidade",
            "testemunhas": ["João Joaquim Ferraz", "Antonio Augusto Paes de Faria"],
            "legitimacao": ["filho Joam nascido a 8 de Setembro de 1856"],
            "assinatura": "Prior Antonio Ribeiro Pessoa Cabral",
        }
    ]
    persons = sync.extract_persons_from_marriages(marriages)
    assert len(persons) == 2

    g = persons[0]
    assert g["nome"] == "Francisco Rodrigues"
    assert g["sobrenome"] == "Mina"
    assert g["conjuge"] == "Maria Paiva"
    assert g["pai"] == "José Rodrigues"
    assert g["mae"] == "Antonia do Olival"
    assert g["naturalidade"] == "Linhares"
    assert g["estado_civil"] == "viúvo de Theresa Ferreira"
    assert g["idade"] == 57
    assert g["profissao"] == "jornaleiro"
    assert g["marriage_date"] == "1876-06-20"
    assert g["numero_assento"] == "4"
    assert g["dispensa"] == "dispensa em 3.º e 4.º grau de consanguinidade"
    assert "João Joaquim Ferraz" in g["testemunhas"]
    assert g["assinatura"] == "Prior Antonio Ribeiro Pessoa Cabral"

    b = persons[1]
    assert b["nome"] == "Maria"
    assert b["sobrenome"] == "Paiva"
    assert b["conjuge"] == "Francisco Rodrigues Mina"
    assert b["pai"] == "José Paiva"
    assert b["mae"] == "Maria da Luiza"
    assert b["idade"] == 54
    assert b["profissao"] == "jornaleira"
    assert b["marriage_date"] == "1876-06-20"

    # Spouse null -> only one person (the groom), conjuge empty.
    lonely = [{"name": "João", "spouse": None, "marriage_date": "1800-01-01"}]
    p = sync.extract_persons_from_marriages(lonely)
    assert len(p) == 1
    assert p[0]["conjuge"] == ""

    # Empty / malformed -> no persons.
    assert sync.extract_persons_from_marriages([]) == []
    assert sync.extract_persons_from_marriages(None) == []
    assert sync.extract_persons_from_marriages([{"foo": "bar"}]) == []


if __name__ == "__main__":
    test_extract_persons_relations()
    test_extract_persons_relations_pt_keys()
    test_build_relation_patch()
    test_build_url_patch()
    test_normalize_death_date()
    test_extract_persons_from_marriages()
    print("OK: all sync_relations tests passed")
