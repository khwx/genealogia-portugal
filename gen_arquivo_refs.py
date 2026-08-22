#!/usr/bin/env python3
"""Gera arquivo_refs.json: mapeia file_id -> referencia de livro paroquial.

Fonte: output/data/celorico_completo.json (ja versionado no repo).
Cada imagem (file_id) pertence a um unico documento/livro com um titulo
arquivistico (ex: PT/TT/PRQ/PCLB19/003/O1). Isto permite a web cruzar o
file_id dos registos com a referencia do Arquivo Distrital, sem expor
quaisquer segredos (mapeamento 100% publico/estatico).
"""
import json
from pathlib import Path

SRC = Path("output/data/celorico_completo.json")
OUT = Path("arquivo_refs.json")


def main():
    data = json.loads(SRC.read_text(encoding="utf-8"))
    documentos = data.get("documentos", [])
    refs = {}
    for doc in documentos:
        titulo = doc.get("titulo", "")
        freguesia = doc.get("freguesia", "")
        datas = doc.get("datas", "")
        tipo = doc.get("tipo", "")
        doc_id = doc.get("doc_id", "")
        for img in doc.get("imagens", []):
            fid = str(img.get("file_id", "")).strip()
            if not fid:
                continue
            refs[fid] = {
                "ref": titulo,
                "freguesia": freguesia,
                "datas": datas,
                "tipo": tipo,
                "doc_id": doc_id,
            }
    OUT.write_text(
        json.dumps({"total": len(refs), "refs": refs}, ensure_ascii=False, indent=0),
        encoding="utf-8",
    )
    print(f"Gerado {OUT} com {len(refs)} mapeamentos file_id -> livro.")


if __name__ == "__main__":
    main()
