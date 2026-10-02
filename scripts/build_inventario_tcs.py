#!/usr/bin/env python3
"""Constrói output/trancoso_inventario.json a partir do Tombo.pt.

Para cada paróquia /f/tcsXX (43), lê as tabelas BIRT/MARR/DEAT e extrai
os livros (título PT/..., datas, URLs Digitarq). Mesmo schema de
output/obitos_inventario.json (só muda concelho_codigo='tcs').

Só leitura (Tombo.pt + nenhum OCR). Idempotente.
"""

import json
import os
import re
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "output", "trancoso_inventario.json")

TIPOS = (
    ("BIRT", "Registos de nascimentos"),
    ("MARR", "Registos de casamentos"),
    ("DEAT", "Registos de óbitos"),
)


def fetch(url, tries=3):
    for a in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            return urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "ignore")
        except Exception as e:
            print(f"  retry {url} ({e})")
            time.sleep(3)
    return ""


def parse_parish(code):
    """Devolve (nome_freguesia, [entradas]) para /f/<code>."""
    h = fetch(f"https://tombo.pt/f/{code}")
    if not h:
        return None, []
    m = re.search(r"<title>(.*?)\s*\|\s*tombo\.pt", h)
    nome = m.group(1).strip() if m else code
    entries = []
    for tipo_cod, caption in TIPOS:
        # tabela <table id="BIRT" ...> ... </table>
        tm = re.search(
            r'<table id="%s".*?</table>' % tipo_cod, h, re.DOTALL | re.IGNORECASE)
        if not tm:
            continue
        table = tm.group(0)
        # linhas: <td><a href="...fileViewer/DOCID?..." title="PT/...">Nome</a></td><td>datas</td>
        for rm in re.finditer(
                r'<td>\s*<a\s+href="(https://digitarq\.arquivos\.pt/fileViewer/([0-9a-f]{32})[^"]*)"[^>]*title="([^"]+)"[^>]*>.*?</a>\s*</td>\s*<td>(.*?)</td>',
                table, re.DOTALL | re.IGNORECASE):
            viewer, doc_id, titulo, datas = rm.groups()
            datas = re.sub(r"<[^>]+>", "", datas).strip()
            entries.append({
                "freguesia": nome,
                "freguesia_codigo": code,
                "tipo": caption,
                "tipo_cod": tipo_cod,
                "titulo": titulo.strip(),
                "datas": datas,
                "url_viewer": viewer.split("?")[0] + "?isRepresentation=false",
                "url_info": f"https://digitarq.arquivos.pt/documentDetails/{doc_id}",
                "concelho_codigo": "tcs",
            })
    return nome, entries


def main():
    codes = [f"tcs{i:02d}" for i in range(1, 44)]
    all_entries = []
    for code in codes:
        nome, entries = parse_parish(code)
        print(f"{code} {nome}: {len(entries)} livros", flush=True)
        all_entries.extend(entries)
        time.sleep(1.0)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(all_entries, f, ensure_ascii=False, indent=1)
    print(f"\nTotal: {len(all_entries)} livros em {OUT}")


if __name__ == "__main__":
    main()
