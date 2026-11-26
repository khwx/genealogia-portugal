#!/usr/bin/env python3
"""Page listings (fids por livro) de um concelho via API Digitarq.

Lê o inventário do concelho, saca as páginas de cada livro e grava um
ficheiro de listings separado por concelho.

Uso:
  python3 scripts/fetch_listings_tcs.py                        # Trancoso
  python3 scripts/fetch_listings_tcs.py \
      --inventario output/pinhel_inventario.json \
      --out output/data/doc_file_listings_pnh.json             # Pinhel

Só leitura. Idempotente (salta docs já listados).
"""

import argparse
import json
import os
import re
import time
import urllib.request
import urllib.error

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INV = os.path.join(ROOT, "output", "trancoso_inventario.json")
OUT = os.path.join(ROOT, "output", "data", "doc_file_listings_tcs.json")
API = "https://digitarq.arquivos.pt/api/rdigital"


def fetch_pages(doc_id, tries=3):
    for a in range(tries):
        try:
            req = urllib.request.Request(
                f"{API}/{doc_id}?max=1000",
                headers={"User-Agent": "Mozilla/5.0", "Referer": "https://digitarq.arquivos.pt/"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read()).get("results", [])
        except Exception as e:
            print(f"  retry {doc_id} ({e})")
            time.sleep(3)
    return []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inventario", default=INV,
                    help="inventário do concelho (JSON)")
    ap.add_argument("--out", default=OUT,
                    help="ficheiro de listings a escrever (JSON)")
    args = ap.parse_args()

    inv = json.load(open(args.inventario, encoding="utf-8"))
    out = {}
    docs = {}
    for b in inv:
        m = re.search(r"documentDetails/([0-9a-fA-F]+)", b.get("url_info", ""))
        if m:
            docs[m.group(1).lower()] = b.get("tipo_cod")
    print(f"Livros: {len(inv)} -> docs únicos: {len(docs)}")
    if os.path.exists(args.out):
        out = json.load(open(args.out, encoding="utf-8"))
    print(f"Já listados: {len(out)}")
    todo = sorted(d for d in docs if d not in out)
    print(f"Por listar: {len(todo)}")
    for i, doc_id in enumerate(todo, 1):
        pages = fetch_pages(doc_id)
        if pages:
            out[doc_id] = pages
            print(f"[{i}/{len(todo)}] {doc_id} ({docs[doc_id]}): {len(pages)} págs", flush=True)
        else:
            print(f"[{i}/{len(todo)}] {doc_id}: VAZIO/ERRO", flush=True)
        if i % 50 == 0:
            json.dump(out, open(args.out, "w", encoding="utf-8"), ensure_ascii=False)
        time.sleep(0.4)
    json.dump(out, open(args.out, "w", encoding="utf-8"), ensure_ascii=False)
    total = sum(len(v) for v in out.values())
    print(f"\nCompletos: {len(out)} docs, {total} páginas em {args.out}")


if __name__ == "__main__":
    main()
