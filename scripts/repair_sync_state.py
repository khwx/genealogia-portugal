#!/usr/bin/env python3
"""Reconstrói o `synced_ids` do state do sync a partir da tabela `pessoas`.

MOTIVO
  Até 26/11/2026 o sync_htr_supabase.py gravava o state mesmo em DRY_RUN:
  um dry-run marcava ficheiros como sincronizados sem os inserir na BD e o
  sync real seguinte saltava-os para sempre (páginas nunca chegavam ao site).
  O mesmo podia deixar o state com IDs de ficheiros que já não existem.

O QUE FAZ
  Lê a coluna `imagem_url` de `pessoas` (contém `fileId=<id>`), cruza com os
  JSON em output/htr_text(_tcs)/ e grava um `synced_ids` que só contém
  ficheiros realmente presentes na BD. Os restantes voltam à fila do sync.
  Faz backup do state antes de escrever.

USO
  python3 scripts/repair_sync_state.py --concelho Trancoso --dry-run
  python3 scripts/repair_sync_state.py --concelho Trancoso
  python3 scripts/repair_sync_state.py --concelho "Celorico da Beira"
"""
import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FILE_ID_RE = re.compile(r"fileId=(\d+)")

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


def file_ids_na_bd():
    """Set de fileIds que já têm registo em pessoas (keyset pagination)."""
    ids, last, total = set(), 0, 0
    while True:
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/pessoas",
            headers=HEADERS,
            params={"select": "id,imagem_url", "id": f"gt.{last}",
                    "limit": 1000, "order": "id.asc"},
            timeout=120,
        )
        if r.status_code != 200:
            sys.exit(f"Supabase {r.status_code}: {r.text[:300]}")
        batch = r.json()
        if not batch:
            break
        last = batch[-1]["id"]
        total += len(batch)
        for row in batch:
            m = FILE_ID_RE.search(row.get("imagem_url") or "")
            if m:
                ids.add(m.group(1))
        if total % 20000 < 1000:
            print(f"  ... {total} registos lidos", flush=True)
    print(f"BD: {total} registos, {len(ids)} fileIds distintos")
    return ids


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--concelho", default="Trancoso")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if args.concelho == "Trancoso":
        input_dir = ROOT / "output" / "htr_text_tcs"
        state_file = ROOT / "output" / "sync_htr_state_tcs.json"
    else:
        input_dir = ROOT / "output" / "htr_text"
        state_file = ROOT / "output" / "sync_htr_state.json"

    ficheiros = {p.stem for p in input_dir.glob("*.json")}
    print(f"{args.concelho}: {len(ficheiros)} JSON em {input_dir.name}")

    bd = file_ids_na_bd()
    presentes = ficheiros & bd
    em_falta = ficheiros - bd
    print(f"Ficheiros com registo na BD: {len(presentes)}")
    print(f"Ficheiros em falta (a sincronizar): {len(em_falta)}")

    try:
        state = json.loads(state_file.read_text())
    except Exception:
        state = {}
    antigos = set(state.get("synced_ids", []))
    fantasma = antigos - bd
    print(f"State atual: {len(antigos)} IDs | sem correspondência na BD: {len(fantasma)}")

    if args.dry_run:
        print("--dry-run: nada escrito.")
        return

    if state_file.exists():
        bak = state_file.with_suffix(f".bak_{time.strftime('%Y%m%d_%H%M')}.json")
        bak.write_text(state_file.read_text())
        print(f"Backup: {bak.name}")

    state["synced_ids"] = sorted(presentes)
    state["repaired_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    state["repaired_from_db"] = True
    state_file.write_text(json.dumps(state, ensure_ascii=False))
    print(f"State reparado: {len(presentes)} IDs ({state_file.name})")


if __name__ == "__main__":
    main()
