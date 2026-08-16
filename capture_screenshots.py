#!/usr/bin/env python3
"""
Script para capturar screenshots de páginas do Digitarq usando Docker Chrome.
Funciona capturando screenshots de cada página de um livro.
"""
import json
import os
import re
import time
import subprocess
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_DIR = Path(__file__).parent
OUTPUT_DIR = BASE_DIR / "output"
IMAGES_DIR = OUTPUT_DIR / "images"
INVENTARIO_FILE = OUTPUT_DIR / "inventario_completo_clb.json"
TEMP_DIR = Path("/tmp/chrome_images")

IMAGES_DIR.mkdir(parents=True, exist_ok=True)
TEMP_DIR.mkdir(parents=True, exist_ok=True)


def capture_screenshot(url, output_path, timeout=60):
    """Capturar screenshot usando Chrome no Docker."""
    temp_name = f"temp_{output_path.name}"
    cmd = [
        "docker", "run", "--rm",
        "-v", f"{TEMP_DIR}:/images",
        "selenium/standalone-chrome:120.0",
        "google-chrome",
        "--headless=new",
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--disable-gpu",
        "--virtual-time-budget=30000",
        f"--screenshot=/images/{temp_name}",
        "--window-size=1920,1080",
        url
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=timeout)
        temp_path = TEMP_DIR / temp_name
        if result.returncode == 0 and temp_path.exists():
            size = temp_path.stat().st_size
            if size > 50000:
                # Mover para pasta final
                import shutil
                shutil.move(str(temp_path), str(output_path))
                return True, size
            temp_path.unlink(missing_ok=True)
            return False, size
        temp_path.unlink(missing_ok=True)
        return False, 0
    except subprocess.TimeoutExpired:
        return False, 0
    except Exception as e:
        return False, str(e)


def get_total_pages(doc_id):
    """Obter número total de páginas via API do Digitarq."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Referer': 'https://digitarq.arquivos.pt/',
    }
    
    import requests
    api_url = f'https://digitarq.arquivos.pt/api/rdigital/{doc_id}?max=1'
    try:
        r = requests.get(api_url, headers=headers, timeout=30)
        r.raise_for_status()
        data = r.json()
        return data.get('total', 0)
    except:
        return 0


def process_book(book, max_pages=10):
    """Processar um livro - capturar screenshots das páginas."""
    titulo = book.get('titulo', '')
    freguesia = book.get('freguesia', '')
    url_viewer = book.get('url_viewer', '')
    
    if not url_viewer or 'fileViewer/' not in url_viewer:
        return 0, 0
    
    doc_id = url_viewer.split('fileViewer/')[1].split('?')[0]
    
    # Obter número total de páginas
    total_pages = get_total_pages(doc_id)
    if total_pages == 0:
        total_pages = max_pages
    
    # Limitar páginas para teste
    pages_to_capture = min(total_pages, max_pages)
    
    print(f"  {titulo}: {total_pages} páginas (capturando {pages_to_capture})")
    
    captured = 0
    errors = 0
    
    for page in range(1, pages_to_capture + 1):
        # URL com pageNumber
        url = f"{url_viewer.split('?')[0]}?isRepresentation=true&pageNumber={page}"
        
        output_name = f"{doc_id}_p{page:04d}.png"
        output_path = IMAGES_DIR / output_name
        
        if output_path.exists():
            captured += 1
            continue
        
        success, result = capture_screenshot(url, output_path)
        if success:
            captured += 1
            if captured % 5 == 0:
                print(f"    {captured}/{pages_to_capture} páginas capturadas")
        else:
            errors += 1
        
        time.sleep(1)
    
    return captured, errors


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Capturar screenshots de páginas do Digitarq')
    parser.add_argument('--freguesia', help='Filtrar por freguesia')
    parser.add_argument('--max-pages', type=int, default=10, help='Máximo de páginas por livro')
    parser.add_argument('--limit', type=int, default=0, help='Limitar número de livros')
    args = parser.parse_args()
    
    # Carregar inventário
    with open(INVENTARIO_FILE, encoding='utf-8') as f:
        inventario = json.load(f)
    
    # Filtrar por freguesia
    if args.freguesia:
        inventario = [i for i in inventario if i.get('freguesia') == args.freguesia]
    
    # Limitar número de livros
    if args.limit > 0:
        inventario = inventario[:args.limit]
    
    print(f"=== A capturar screenshots de {len(inventario)} livros ===")
    print(f"Máximo de páginas por livro: {args.max_pages}")
    
    total_captured = 0
    total_errors = 0
    
    for i, book in enumerate(inventario):
        print(f"\n[{i+1}/{len(inventario)}] {book.get('freguesia', '')} - {book.get('titulo', '')}")
        
        captured, errors = process_book(book, max_pages=args.max_pages)
        total_captured += captured
        total_errors += errors
        
        print(f"  Total: {captured} capturadas, {errors} erros")
    
    print(f"\n{'=' * 60}")
    print(f"CONCLUÍDO!")
    print(f"Total de screenshots: {total_captured}")
    print(f"Total de erros: {total_errors}")
    print(f"Pasta: {IMAGES_DIR}")
    print(f"{'=' * 60}")


if __name__ == '__main__':
    main()
