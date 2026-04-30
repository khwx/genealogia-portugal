#!/usr/bin/env python3
"""
Script para extrair imagens dos livros de registos de óbito do Digitarq.
Usa chromium-browser diretamente via subprocess.
"""
import json
import time
import sys
import subprocess
import re
from pathlib import Path
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

INVENTORY_FILE = Path(__file__).parent / 'output' / 'obitos_inventario.json'
IMAGES_DIR = Path(__file__).parent / 'output' / 'images'
IMAGES_DIR.mkdir(parents=True, exist_ok=True)

CHROME_BIN = '/usr/bin/chromium-browser'

session = requests.Session()
retry = Retry(total=3, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
session.mount('https://', HTTPAdapter(max_retries=retry))


def download_image(url, path):
    """Descarrega uma imagem."""
    try:
        resp = session.get(url, timeout=60, headers={'User-Agent': 'Mozilla/5.0'})
        if resp.status_code == 200 and len(resp.content) > 10000:
            with open(path, 'wb') as f:
                f.write(resp.content)
            return True
    except:
        pass
    return False


def process_book(book, max_pages=5):
    """Processa um livro - tira screenshots das últimas páginas (índice)."""
    url = book.get('url_viewer', '')
    freguesia = book.get('freguesia', '')
    dates = book.get('datas', '')
    
    if 'fileViewer/' not in url:
        return 0
    
    doc_id = url.split('fileViewer/')[1].split('?')[0]
    downloaded = 0
    
    # Para cada página, navegar e tirar screenshot
    for page_num in range(1, max_pages + 1):
        screenshot_path = IMAGES_DIR / f"{doc_id}_page_{page_num}.png"
        
        cmd = [
            CHROME_BIN,
            '--headless=new',
            '--no-sandbox',
            '--disable-dev-shm-usage',
            f'--screenshot={screenshot_path}',
            '--window-size=1920,1080',
            '--virtual-time-budget=20000',
            url
        ]
        
        try:
            # Primeira vez, vai para o livro
            # następicas vezes, pode navegar mas por agora apenas 1 screenshot por livro
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            
            if result.returncode == 0 and screenshot_path.exists():
                size = screenshot_path.stat().st_size
                if size > 50000:  # Screenshot válido
                    downloaded += 1
                    print(f"   📸 Página {page_num}: {screenshot_path.name} ({size} bytes)")
                    break  # Por agora, só 1 screenshot por livro
            else:
                break
                
        except Exception as e:
            print(f"   ⚠️  Erro na página {page_num}: {e}")
            break
        
        time.sleep(1)
    
    return downloaded


def process_book_images(book, max_images=10):
    """Processa um livro - tenta encontrar e baixar imagens."""
    url = book.get('url_viewer', '')
    freguesia = book.get('freguesia', '')
    dates = book.get('datas', '')
    
    if 'fileViewer/' not in url:
        return 0
    
    doc_id = url.split('fileViewer/')[1].split('?')[0]
    
    # Primeiro, tentar extrair URLs do HTML (depois de JavaScript)
    cmd = [
        CHROME_BIN,
        '--headless=new',
        '--no-sandbox',
        '--disable-dev-shm-usage',
        '--dump-dom',
        '--virtual-time-budget=15000',
        url
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        
        if result.returncode != 0:
            return 0
        
        # Procurar URLs de imagens no HTML
        image_urls = set()
        doc_id_short = doc_id[:12]
        
        # Padrões comuns
        patterns = [
            r'(https?://[^\s"\'<]+(?:jpg|jpeg|png|gif|tiff|webp)[^\s"\']*)',
            r'"(https?://[^"\']+(?:image|img)[^"\']*)"',
            r'data-src="([^"]+)"',
            r'src="([^"]+)"',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, result.stdout, re.I)
            for match in matches[:50]:  # Limitar
                if match.startswith('http') and any(ext in match.lower() for ext in ['.jpg', '.jpeg', '.png', 'image', 'tiff']):
                    # Filtrar apenas URLs relevantes (com o doc_id ou do digitarq)
                    if doc_id in match or 'digitarq' in match:
                        image_urls.add(match)
        
        image_urls = list(image_urls)
        
        if image_urls:
            print(f"   🖼️  {len(image_urls)} imagens encontradas")
            
            downloaded = 0
            for i, img_url in enumerate(image_urls[:max_images]):
                ext = '.jpg'
                for e in ['.jpg', '.jpeg', '.png']:
                    if e in img_url.lower():
                        ext = e
                        break
                
                path = IMAGES_DIR / f"{doc_id}_{i+1}{ext}"
                if download_image(img_url, path):
                    downloaded += 1
                    print(f"   ✅ {path.name}")
            
            return downloaded
        else:
            # Se não encontrou imagens, fazer screenshot
            return process_book(book, max_pages=1)
            
    except Exception as e:
        print(f"   ❌ Erro: {e}")
        return 0


def main():
    with open(INVENTORY_FILE, 'r', encoding='utf-8') as f:
        books = json.load(f)
    
    filter_arg = sys.argv[1] if len(sys.argv) > 1 else None
    if filter_arg:
        books = [b for b in books if filter_arg.lower() in b.get('freguesia', '').lower()]
    
    print(f"=== A processar {len(books)} livros ===")
    print(f"Imagens serão guardadas em: {IMAGES_DIR}")
    
    downloaded_total = 0
    
    for i, book in enumerate(books):
        freguesia = book.get('freguesia', '')
        dates = book.get('datas', '')
        
        print(f"\n[{i+1}/{len(books)}] {freguesia} ({dates})")
        
        downloaded = process_book_images(book)
        downloaded_total += downloaded
        
        if downloaded > 0:
            print(f"   ✅ {downloaded} imagens guardadas")
        
        time.sleep(2)  # Rate limit
    
    print(f"\n=== TOTAL: {downloaded_total} imagens ===")
    print(f"Pasta: {IMAGES_DIR}")
    
    # Listar ficheiros
    images = list(IMAGES_DIR.glob('*.png')) + list(IMAGES_DIR.glob('*.jpg'))
    print(f"Total de ficheiros: {len(images)}")


if __name__ == "__main__":
    main()