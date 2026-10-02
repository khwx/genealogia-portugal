#!/usr/bin/env python3
"""Page listings de Trancoso: fids por livro via API Digitarq.

Lê output/trancoso_inventario.json (BIRT+MARR+DEAT), saca as páginas de
cada livro e grava output/data/doc_file_listings_tcs.json (separado de
Celorico). Só leitura. Idempotente (salta docs já listados).
"""

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
    inv = json.load(open(INV, encoding="utf-8"))
    docs = {}
    for b in inv:
        m = re.search(r"documentDetails/([0-9a-fA-F]+)", b.get("url_info", ""))
        if m:
            docs[m.group(1).lower()] = b.get("tipo_cod")
    print(f"Livros: {len(inv)} -> docs únicos: {len(docs)}")
    out = {}
    if os.path.exists(OUT):
        out = json.load(open(OUT, encoding="utf-8"))
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
            json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False)
        time.sleep(0.4)
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False)
    total = sum(len(v) for v in out.values())
    print(f"\nCompletos: {len(out)} docs, {total} páginas em {OUT}")


if __name__ == "__main__":
    main()
