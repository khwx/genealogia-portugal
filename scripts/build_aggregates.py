#!/usr/bin/env python3
"""Gera api/aggregates_data.py — agregados pré-calculados numa só passagem.

PROBLEMA QUE RESOLVE
  /api/mapa, /api/seculos, /api/decadas, /api/apelidos e /api/stats-extras
  percorriam a tabela `pessoas` inteira em páginas de 1000 (≈148 pedidos a
  ~1s cada) em CADA invocação: 40–45s locais. Na Vercel isso passa o limite
  de execução da função (email "hit execution-time limit", 6,8% das
  invocações) e a página do mapa/stats fica sem dados.

  O PostgREST deste projeto tem as agregações desactivadas
  ("Use of aggregate functions is not allowed"), por isso não há GROUP BY
  server-side. A alternativa é calcular offline e servir o snapshot.

USO
  python3 scripts/build_aggregates.py            # gera api/aggregates_data.py
  python3 scripts/build_aggregates.py --dry-run  # só imprime o resumo

  Correr DEPOIS de cada sync para o Supabase (sync_htr_supabase.py), para os
  números do mapa/estatísticas acompanharem os dados novos. Só faz leitura
  pública (publishable/secret key do .env); não escreve na BD.

O resultado é um módulo Python (e não um .json) de propósito: o builder
`@vercel/python` inclui os módulos importados no bundle da função, mas não
garante ficheiros de dados avulsos.
"""
import json
import os
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "api" / "aggregates_data.py"
COLS = "id,freguesia,concelho,tipo_registo,data_obito,data_nascimento,sobrenome,idade"
PAGE = 1000

# --- credenciais (mesmo padrão do resto do projeto) -------------------------
for line in (ROOT / ".env").read_text().splitlines():
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
KEY = (os.environ.get("SUPABASE_SECRET_KEY") or os.environ.get("SUPABASE_KEY")
       or os.environ.get("SUPABASE_ANON_KEY") or "")
if not SUPABASE_URL or not KEY:
    sys.exit("SUPABASE_URL/SUPABASE_KEY em falta (.env)")

import requests  # noqa: E402

HEADERS = {"apikey": KEY, "Authorization": f"Bearer {KEY}"}
ILEGIVEIS = {"[ilegível]", "[ileg]", "[não consta]"}


def _ano(valor):
    """Ano (int) de 'YYYY-MM-DD' ou 'YYYY-MM-DDTHH:MM:SS', ou None."""
    if not valor:
        return None
    s = str(valor)
    if "T" in s:
        s = s.split("T")[0]
    cabeca = s.split("-")[0]
    if not cabeca.isdigit():
        return None
    ano = int(cabeca)
    return ano if 1000 <= ano <= 2100 else None


def recolher():
    """Percorre `pessoas` uma vez e agrega tudo.

    Usa keyset pagination (id > último) em vez de offset: com offset alto o
    PostgREST faz sort/scan de 148k linhas e estoura o statement timeout.
    """
    stats = {}  # freguesia -> {count, concelho, tipos, periodos}
    seculos, decadas = Counter(), Counter()
    sobrenomes, idades = Counter(), Counter()
    total = 0
    last_id = 0
    t0 = time.time()
    while True:
        resp = requests.get(
            f"{SUPABASE_URL}/rest/v1/pessoas",
            headers=HEADERS,
            params={"select": COLS, "id": f"gt.{last_id}", "limit": PAGE, "order": "id.asc"},
            timeout=120,
        )
        if resp.status_code != 200:
            sys.exit(f"Supabase {resp.status_code}: {resp.text[:300]}")
        batch = resp.json()
        if not batch:
            break
        last_id = batch[-1]["id"]
        for r in batch:
            total += 1
            f = (r.get("freguesia") or "Outras").strip() or "Outras"
            st = stats.setdefault(f, {"count": 0, "concelho": {}, "tipos": {}, "periodos": {}})
            st["count"] += 1
            tipo = (r.get("tipo_registo") or "DEAT").upper()
            st["tipos"][tipo] = st["tipos"].get(tipo, 0) + 1
            conc = (r.get("concelho") or "Celorico da Beira").strip() or "Celorico da Beira"
            st["concelho"][conc] = st["concelho"].get(conc, 0) + 1

            ano_morte = _ano(r.get("data_obito"))
            if ano_morte:
                seculos[(ano_morte - 1) // 100 + 1] += 1
                decadas[(ano_morte // 10) * 10] += 1
            ano_mapa = ano_morte or _ano(r.get("data_nascimento"))
            if ano_mapa:
                sec = (ano_mapa - 1) // 100 + 1
                st["periodos"][sec] = st["periodos"].get(sec, 0) + 1

            s = (r.get("sobrenome") or "").strip()
            if s and s.lower() not in ILEGIVEIS:
                sobrenomes[s] += 1

            idade = r.get("idade")
            if isinstance(idade, int) and 0 < idade < 110:
                idades[f"{(idade // 10) * 10}-{(idade // 10) * 10 + 9}"] += 1

        if len(batch) < PAGE:
            break
        if total % 20000 < PAGE:
            print(f"  ... {total} linhas ({time.time() - t0:.0f}s)", flush=True)

    # reduzir cada freguesia ao essencial (concelho maioritário, séculos ordenados)
    freguesia_stats = {}
    for f, st in stats.items():
        concelhos = st["concelho"]
        freguesia_stats[f] = {
            "count": st["count"],
            "concelho": max(concelhos, key=concelhos.get) if concelhos else "Celorico da Beira",
            "tipos": st["tipos"],
            "periodos": {str(s): st["periodos"][s] for s in sorted(st["periodos"]) if st["periodos"][s] > 0},
        }

    return {
        "gerado_em": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "linhas": total,
        "freguesia_stats": freguesia_stats,
        "seculos": {str(s): seculos[s] for s in sorted(seculos)},
        "decadas": {str(d): decadas[d] for d in sorted(decadas)},
        "apelidos": {
            "apelidos": [{"nome": k, "count": v} for k, v in sobrenomes.most_common(100)],
            "total": len(sobrenomes),
        },
        "stats_extras": {
            "top_sobrenomes": [{"nome": k, "count": v} for k, v in sobrenomes.most_common(10)],
            "idade_dist": [{"faixa": k, "count": v} for k, v in sorted(idades.items())],
        },
    }


def escrever(data, destino=OUT):
    corpo = (
        "# Gerado por scripts/build_aggregates.py — NÃO EDITAR À MÃO.\n"
        f"# Gerado em: {data['gerado_em']} | linhas: {data['linhas']}\n"
        "import json\n\n"
        f"DATA = json.loads({json.dumps(json.dumps(data, ensure_ascii=False))})\n"
    )
    destino.write_text(corpo, encoding="utf-8")
    return destino


def main():
    dry = "--dry-run" in sys.argv
    print("A recolher agregados de pessoas (uma passagem)...", flush=True)
    data = recolher()
    print(f"OK: {data['linhas']} linhas, {len(data['freguesia_stats'])} freguesias, "
          f"{data['apelidos']['total']} apelidos distintos")
    if dry:
        print("--dry-run: nada escrito.")
        return
    destino = escrever(data)
    print(f"Escrito {destino} ({destino.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
