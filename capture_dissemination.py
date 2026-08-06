#!/usr/bin/env python3
"""
Captura imagens TIFF do Digitarq via endpoint de disseminação.

Descobre automaticamente o endpoint correto:
  https://digitarq.arquivos.pt/rdigital/dissemination?fileId={pageId}&download=true

Uso:
    python capture_dissemination.py                          # Captura todos os livros do inventário
    python capture_dissemination.py --doc-id 1d7ea...        # Captura um livro específico
    python capture_dissemination.py --last-pages 3           # Captura últimas 3 páginas
    python capture_dissemination.py --pages 1-5,10           # Captura páginas específicas
"""
import json
import time
import argparse
import requests
from pathlib import Path

BASE_DIR = Path(__file__).parent
OUTPUT_DIR = BASE_DIR / "output"
INVENTORY_FILE = OUTPUT_DIR / "inventario_completo_clb.json"
TIFF_DIR = OUTPUT_DIR / "images" / "tiff"
JPEG_DIR = OUTPUT_DIR / "images" / "jpeg"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://digitarq.arquivos.pt/",
}

DIGITARQ_API = "https://digitarq.arquivos.pt/api/rdigital"
DISSEMINATION_URL = "https://digitarq.arquivos.pt/rdigital/dissemination"


def get_page_list(doc_id: str, max_pages: int = 200) -> list[dict]:
    """Obter lista de páginas de um documento via API."""
    url = f"{DIGITARQ_API}/{doc_id}?max={max_pages}"
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    data = r.json()
    return data.get("results", [])


def download_tiff(page_id: str, output_path: Path) -> bool:
    """Descarregar imagem TIFF via disseminação."""
    url = f"{DISSEMINATION_URL}?fileId={page_id}&download=true"
    try:
        r = requests.get(url, headers=HEADERS, timeout=60, allow_redirects=True)
        if r.status_code == 200 and "image" in r.headers.get("Content-Type", ""):
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(r.content)
            return True
    except Exception as e:
        print(f"  ❌ Erro: {e}")
    return False


def convert_tiff_to_jpeg(tiff_path: Path, jpeg_path: Path, quality: int = 85) -> bool:
    """Converter TIFF para JPEG."""
    try:
        from PIL import Image
        img = Image.open(tiff_path)
        jpeg_path.parent.mkdir(parents=True, exist_ok=True)
        img.convert("RGB").save(jpeg_path, "JPEG", quality=quality)
        return True
    except Exception as e:
        print(f"  ❌ Erro conversão: {e}")
        return False


def parse_page_range(pages_str: str) -> list[int]:
    """Parse '1-5,10,15-20' para lista de números."""
    pages = []
    for part in pages_str.split(","):
        part = part.strip()
        if "-" in part:
            a, b = part.split("-", 1)
            try:
                pages.extend(range(int(a.strip()), int(b.strip()) + 1))
            except ValueError:
                pass
        elif part.isdigit():
            pages.append(int(part))
    return pages


def main():
    parser = argparse.ArgumentParser(description="Capturar imagens TIFF do Digitarq")
    parser.add_argument("--doc-id", help="Doc ID específico para capturar")
    parser.add_argument("--last-pages", type=int, default=3,
                        help="Número de últimas páginas a capturar (default: 3)")
    parser.add_argument("--pages", help="Páginas específicas (ex: 1-5,10)")
    parser.add_argument("--all-pages", action="store_true",
                        help="Capturar todas as páginas")
    parser.add_argument("--skip-convert", action="store_true",
                        help="Não converter TIFF para JPEG")
    args = parser.parse_args()

    TIFF_DIR.mkdir(parents=True, exist_ok=True)
    JPEG_DIR.mkdir(parents=True, exist_ok=True)

    # Carregar inventário
    if args.doc_id:
        books = [{"doc_id": args.doc_id}]
    else:
        with open(INVENTORY_FILE, encoding="utf-8") as f:
            all_books = json.load(f)
        books = [b for b in all_books if b.get("url_viewer", "").find("fileViewer/") >= 0]

    print(f"📚 {len(books)} livros para processar\n")

    total_tiff = 0
    total_jpeg = 0

    for i, book in enumerate(books):
        doc_id = book.get("doc_id", "")
        if not doc_id:
            url_viewer = book.get("url_viewer", "")
            if "fileViewer/" in url_viewer:
                doc_id = url_viewer.split("fileViewer/")[1].split("?")[0]

        if not doc_id:
            continue

        titulo = book.get("titulo", book.get("codigo", "?"))
        freguesia = book.get("freguesia", "")

        print(f"[{i+1}/{len(books)}] {titulo} ({freguesia})")

        # Obter páginas
        try:
            pages = get_page_list(doc_id)
        except Exception as e:
            print(f"  ❌ Erro API: {e}")
            continue

        print(f"  Total páginas: {len(pages)}")

        # Determinar quais páginas capturar
        if args.all_pages:
            pages_to_capture = pages
        elif args.pages:
            page_nums = parse_page_range(args.pages)
            pages_to_capture = [p for p in pages if int(p["name"].split("_m")[-1].split(".")[0]) in page_nums]
        else:
            pages_to_capture = pages[-args.last_pages:]

        print(f"  Capturando {len(pages_to_capture)} páginas")

        for page in pages_to_capture:
            page_id = page["id"]
            page_name = page["name"]

            tiff_path = TIFF_DIR / f"{doc_id}_{page_name}"
            jpeg_path = JPEG_DIR / f"{doc_id}_{page_name}".replace(".jpg", ".jpeg")

            # Download TIFF
            if tiff_path.exists():
                print(f"  ✓ {page_name} (TIFF já existe)")
            else:
                if download_tiff(page_id, tiff_path):
                    print(f"  ✅ {page_name} ({tiff_path.stat().st_size} bytes)")
                    total_tiff += 1
                else:
                    print(f"  ❌ {page_name}")
                time.sleep(1)

            # Converter para JPEG
            if not args.skip_convert and not jpeg_path.exists() and tiff_path.exists():
                if convert_tiff_to_jpeg(tiff_path, jpeg_path):
                    total_jpeg += 1

        time.sleep(2)

    print(f"\n{'='*60}")
    print(f"CONCLUÍDO!")
    print(f"TIFF: {total_tiff} novas imagens em {TIFF_DIR}")
    print(f"JPEG: {total_jpeg} novas conversões em {JPEG_DIR}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
