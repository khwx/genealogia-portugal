#!/usr/bin/env python3
"""
Limpeza segura das imagens originais ja transcritas.
Por defeito faz DRY-RUN (nao apaga nada) — usa --confirm para apagar.

So apaga um .tiff se ja existir a transcricao correspondente em
output/htr_text/<stem>.json (ou --por-freguesia agrupa pelo mapeamento).
"""
import os
import argparse
from pathlib import Path

ROOT = Path(__file__).parent
IMG_DIR = ROOT / "output" / "full_images"
TEXT_DIR = ROOT / "output" / "htr_text"
MAP = ROOT / "output" / "data" / "freguesia_file_mapping.json"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--confirm", action="store_true", help="Apaga mesmo (sem isto, so mostra)")
    ap.add_argument("--por-freguesia", action="store_true",
                    help="So apaga se TODA a freguesia ja estiver transcrita")
    args = ap.parse_args()

    tiffs = sorted(IMG_DIR.rglob("*.tiff"))
    done = {p.stem for p in TEXT_DIR.glob("*.json")}
    candidatos = [p for p in tiffs if p.stem in done]

    if args.por_freguesia and MAP.exists():
        import json
        fmap = json.load(open(MAP))
        # fmap: file_id -> {freguesia: ...}  (ajustar se a estrutura diferir)
        frag_of = {}
        for fid, v in fmap.items():
            frag_of[fid] = v.get("freguesia") if isinstance(v, dict) else None
        frag_total = {}
        frag_done = {}
        for p in tiffs:
            f = frag_of.get(p.stem)
            if f is None:
                continue
            frag_total.setdefault(f, 0)
            frag_done.setdefault(f, 0)
            frag_total[f] += 1
            if p.stem in done:
                frag_done[f] += 1
        autorizadas = {f for f in frag_total if frag_done[f] == frag_total[f]}
        candidatos = [p for p in candidatos if frag_of.get(p.stem) in autorizadas]
        print(f"Freguesias completas: {len(autorizadas)}")

    print(f"Imagens .tiff total: {len(tiffs)}")
    print(f"Candidatas a apagar (ja transcritas): {len(candidatos)}")
    if not candidatos:
        return
    print("Exemplos:", [p.name for p in candidatos[:5]])
    if not args.confirm:
        print("\n[DRY-RUN] Nada apagado. Corre com --confirm para apagar.")
        return
    for p in candidatos:
        p.unlink()
    print(f"\nApagadas {len(candidatos)} imagens.")


if __name__ == "__main__":
    main()
