"""
Testa as rotas /validar e /api/pessoas (integracao, precisa de .env).

Seguranca:
  * NADA corre a nivel de modulo — o pytest recolhe sem fazer rede nem tocar
    na BD (o ficheiro antigo executava tudo no import e rebentava na recolha
    com `KeyError: 0` quando a API respondia 500 em vez de lista);
  * sem SUPABASE_URL/SUPABASE_KEY os testes sao ignorados (skip);
  * SO LEITURA: o teste antigo fazia POST /api/validar com nome='TESTE' e
    poluiu 2 registos em producao (ids 8762 e 126830) — nunca mais escrever
    na BD a partir dos testes.

Correr:  python3 -m pytest tests/test_validar.py -q
"""
import importlib.util
import os
from pathlib import Path

import pytest
import requests
from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

needs_backend = pytest.mark.skipif(
    not (SUPABASE_URL and SUPABASE_KEY),
    reason="SUPABASE_URL/SUPABASE_KEY em falta (correr na raiz do projeto com .env)",
)


def _get(url, timeout=30, **kwargs):
    """GET com skip em vez de erro quando o Supabase esta inacessivel."""
    try:
        return requests.get(url, timeout=timeout, **kwargs)
    except requests.exceptions.RequestException as exc:
        pytest.skip(f"Supabase inacessivel ({exc.__class__.__name__})")


def _headers():
    return {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}


@pytest.fixture(scope="module")
def client():
    spec = importlib.util.spec_from_file_location(
        "api_index", str(ROOT / "api" / "index.py")
    )
    api = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(api)
    return api.app.test_client()


@needs_backend
def test_colunas_qualidade_validado_existem():
    r = _get(f"{SUPABASE_URL}/rest/v1/pessoas?select=qualidade,validado&limit=1",
             headers=_headers())
    assert r.status_code == 200, r.text[:300]


@needs_backend
def test_rota_validar_responde(client):
    # Garante tambem que a fila de revisao nao leva statement timeout
    # (antes: order=criado_em.desc sem indice => ~21s e 500 em producao).
    _get(f"{SUPABASE_URL}/rest/v1/pessoas?select=id&limit=1", headers=_headers())
    r = client.get("/validar")
    assert r.status_code == 200


@needs_backend
def test_api_pessoas_devolve_lista(client):
    """Regressao: /api/pessoas devolve 500 se o order por coluna sem indice."""
    _get(f"{SUPABASE_URL}/rest/v1/pessoas?select=id&limit=1", headers=_headers())
    r = client.get("/api/pessoas?limit=1")
    payload = r.get_json()
    assert r.status_code == 200, payload
    # Um erro PostgREST chega como dict {"error": ...} — e isso que partia p[0]
    assert isinstance(payload, list), f"esperava lista, recebi: {payload}"
    if payload:
        assert "id" in payload[0]
