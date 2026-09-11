#!/usr/bin/env python3
"""
Script para processar livros de Celorico usando Chrome no Docker.
Captura as últimas páginas (índice) de cada livro.
"""
import json
import subprocess
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

INVENTORY_FILE = Path(__file__).parent / 'output' / 'obitos_inventario.json'
IMAGES_DIR = Path(__file__).parent / 'output' / 'images'
IMAGES_DIR.mkdir(parents=True, exist_ok=True)

CHROME_CONTAINER = "chrome-ocr"


def capture_with_docker(url, doc_id, page_num=1):
    """Captura screenshot usando Chrome no Docker."""
    output_path = IMAGES_DIR / f"{doc_id}.png"
    
    cmd = [
        "docker", "run", "--rm",
        "--network", "bridge",
        "-v", f"{IMAGES_DIR}:/images",
        "chrome-ocr",
        "google-chrome",
        "--headless=new",
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--disable-gpu",
        "--virtual-time-budget=20000",
        f"--screenshot=/images/{doc_id}.png",
        "--window-size=1920,1080",
        url
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=60)
        if result.returncode == 0 and output_path.exists():
            size = output_path.stat().st_size
            if size > 50000:  # Screenshot válido
                print(f"   ✅ {output_path.name} ({size} bytes)")
                return True
    except Exception as e:
        print(f"   ❌ Erro: {e}")
    
    return False


def process_books(books):
    """Processa lista de livros."""
    print(f"=== A processar {len(books)} livros ===")
    
    processed = 0
    for i, book in enumerate(books):
        freguesia = book.get('freguesia', '')
        dates = book.get('datas', '')
        url = book.get('url_viewer', '')
        
        if 'fileViewer/' not in url:
            continue
        
        doc_id = url.split('fileViewer/')[1].split('?')[0]
        
        print(f"[{i+1}/{len(books)}] {freguesia} ({dates})")
        
        # Tentar capturr screenshot
        if capture_with_docker(url, doc_id, page_num=1):
            processed += 1
        
        time.sleep(1)
    
    return processed


def main():
    with open(INVENTORY_FILE, 'r', encoding='utf-8') as f:
        books = json.load(f)
    
    # Filtrar Celorico
    celorico = [b for b in books if 'Celorico' in b.get('freguesia', '')]
    celorico = celorico[:60]  # Limitar para teste
    
    processed = process_books(celorico)
    print(f"\n=== TOTAL: {processed} imagens ===")
    print(f"Pasta: {IMAGES_DIR}")


if __name__ == "__main__":
    main()