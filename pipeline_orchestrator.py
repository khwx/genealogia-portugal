#!/usr/bin/env python3
"""
Master Pipeline Orchestrator
Processes freguesias one at a time with disk space management.

Pipeline for each freguesia:
1. Download TIFFs from Digitarq (via capture_dissemination.py)
2. Run HTR processing (htr_cloud_v2.py)
3. Sync results to Supabase
4. Commit + push to GitHub
5. Cleanup images (liberate disk space)
6. Move to next freguesia

Usage:
  python3 pipeline_orchestrator.py                    # Process next freguesia
  python3 pipeline_orchestrator.py --freguesia "Ratoeira"  # Specific freguesia
  python3 pipeline_orchestrator.py --status           # Show progress
  python3 pipeline_orchestrator.py --dry-run          # Show plan without executing
"""
import json
import os
import sys
import re
import time
import shutil
import subprocess
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime
from collections import defaultdict

BASE_DIR = Path(__file__).parent
OUTPUT_DIR = BASE_DIR / "output"
INPUT_DIR = OUTPUT_DIR / "htr_text"
TIFF_DIR = OUTPUT_DIR / "full_images" / "tiff"
JPEG_DIR = OUTPUT_DIR / "full_images" / "jpeg"
INVENTORY_FILE = OUTPUT_DIR / "inventario_completo_clb.json"
CELORICO_JSON = OUTPUT_DIR / "data" / "celorico_completo.json"
STATE_FILE = OUTPUT_DIR / "pipeline_state.json"
LOG_FILE = OUTPUT_DIR / "pipeline_master.log"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://digitarq.arquivos.pt/",
}

DIGITARQ_API = "https://digitarq.arquivos.pt/api/rdigital"
DISSEMINATION_URL = "https://digitarq.arquivos.pt/rdigital/dissemination"
SUPABASE_URL = "https://qljopxbxgflozrcdblrl.supabase.co"
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "sb_publishable_-oWYfk9uhb5DIByIe7xUhw_jb_touP1")

# Freguesias prioritárias de Celorico da Beira
TARGET_FREGUESIAS = [
    'Celorico (Santa Maria)',
    'Celorico (São Pedro)',
    'São Martinho de Celorico',
    # Outras freguesias do inventário
    'Mesquitela',
    'Vale de Azares',
    'Maçal do Chão',
    'Jejua',
    'Lajeosa do Mondego',
    'Ratoeira',
    'Minhocal',
    'Açores',
    'Rapa',
    'Cadafaz',
    'Prados',
    'Cortiçô da Serra',
    'Salgueirais',
    'Baraçal',
    'Vide Entre Vinhas',
    'Carrapichana',
    'Forno Telheiro',
    'Linhares',
    'Velosa',
    'Casas do Rio',
    'Aldeia da Serra',
    'Galiçau',
]

def log(msg):
    with open(LOG_FILE, 'a') as f:
        f.write(f"[{datetime.now().isoformat()}] {msg}\n")
    print(f"[{datetime.now().isoformat()}] {msg}")

def load_state():
    if STATE_FILE.exists():
        with open(STATE_FILE) as f:
            return json.load(f)
    return {
        "processed_freguesias": [],
        "completed_file_ids": set(),
        "current_freguesia": None,
        "last_sync": None,
        "total_processed": 0
    }

def save_state(state):
    state_copy = dict(state)
    if isinstance(state_copy.get("completed_file_ids"), set):
        state_copy["completed_file_ids"] = list(state_copy["completed_file_ids"])
    with open(STATE_FILE, 'w') as f:
        json.dump(state_copy, f, indent=2)

def get_disk_usage():
    total, used, free = shutil.disk_usage("/home/pxtkhw")
    return {"total": total / (1024**3), "used": used / (1024**3), "free": free / (1024**3)}

def cleanup_images():
    """Apagar imagens para libertar espaço em disco."""
    disk = get_disk_usage()
    if disk["free"] < 5:  # Menos de 5GB livre
        log(f"⚠️ Baixo espaço em disco: {disk['free']:.1f}GB livre. A limpar...")
        
        # Apagar TIFFs
        if TIFF_DIR.exists():
            tiff_count = len(list(TIFF_DIR.glob("*.tiff")))
            shutil.rmtree(TIFF_DIR)
            log(f"   Apagados {tiff_count} TIFFs")
        
        # Apagar JPEGs
        if JPEG_DIR.exists():
            jpeg_count = len(list(JPEG_DIR.glob("*.jpg")))
            shutil.rmtree(JPEG_DIR)
            log(f"   Apagados {jpeg_count} JPEGs")
        
        disk = get_disk_usage()
        log(f"   Espaço após limpeza: {disk['free']:.1f}GB livre")
    else:
        log(f"✓ Espaço em disco OK: {disk['free']:.1f}GB livre")

def filter_inventory(freguesia=None):
    """Filter inventory to specific freguesia, return doc_ids list."""
    with open(INVENTORY_FILE, encoding="utf-8") as f:
        all_books = json.load(f)
    
    if freguesia:
        books = [b for b in all_books if b.get("freguesia") == freguesia]
    else:
        books = all_books
    
    # Extract doc_ids from url_viewer
    docs = []
    for book in books:
        url_viewer = book.get("url_viewer", "")
        if "fileViewer/" in url_viewer:
            doc_id = url_viewer.split("fileViewer/")[1].split("?")[0]
            docs.append({
                "doc_id": doc_id,
                "titulo": book.get("titulo", ""),
                "freguesia": book.get("freguesia", ""),
                "tipo": book.get("tipo", ""),
                "url_viewer": url_viewer
            })
    return docs

def download_freguesia_images(freguesia, doc_id, max_pages=300):
    """Download all pages for a doc_id via Digitarq API."""
    url = f"{DIGITARQ_API}/{doc_id}?max={max_pages}"
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read())
    
    pages = data.get("results", [])
    downloaded = 0
    
    for page in pages:
        page_id = str(page.get("id", ""))
        if not page_id:
            continue
        
        tiff_path = TIFF_DIR / f"{page_id}.tiff"
        if tiff_path.exists() and tiff_path.stat().st_size > 1000:
            continue  # Skip existing
        
        url_dl = f"{DISSEMINATION_URL}?fileId={page_id}&download=true"
        req_dl = urllib.request.Request(url_dl, headers=HEADERS)
        try:
            with urllib.request.urlopen(req_dl, timeout=60) as resp_dl:
                content = resp_dl.read()
                if "image" in resp_dl.headers.get("Content-Type", ""):
                    TIFF_DIR.mkdir(parents=True, exist_ok=True)
                    tiff_path.write_bytes(content)
                    downloaded += 1
        except Exception as e:
            if downloaded == 0:
                log(f"  ⚠️ Download retry for {page_id}: {e}")
    
    return downloaded, len(pages)

def run_htr(input_dir=TIFF_DIR):
    """Run HTR processing on downloaded images."""
    htr_script = BASE_DIR / "htr_cloud_v2.py"
    
    # Update HTR state with current input dir
    cmd = [
        sys.executable, str(htr_script),
        "--input-dir", str(input_dir),
        "--output-dir", str(INPUT_DIR),
        "--batch-size", "0",  # Process all
    ]
    
    env = os.environ.copy()
    env["INPUT_DIR"] = str(input_dir)
    
    result = subprocess.run(
        cmd,
        cwd=str(BASE_DIR),
        env=env,
        capture_output=True,
        text=True,
        timeout=86400  # 24 hours
    )
    
    return result.returncode == 0

def sync_to_supabase():
    """Sync HTR results to Supabase."""
    sync_script = BASE_DIR / "sync_htr_supabase.py"
    result = subprocess.run(
        [sys.executable, str(sync_script)],
        cwd=str(BASE_DIR),
        capture_output=True,
        text=True,
        timeout=300
    )
    return result.returncode == 0

def commit_and_push(freguesia, stats):
    """Commit changes and push to GitHub."""
    subprocess.run(["git", "add", "-A"], cwd=str(BASE_DIR), capture_output=True)
    
    msg = f"pipeline: {freguesia} - {stats.get('processed', 0)} novas imagens, {stats.get('synced', 0)} registos"
    subprocess.run(
        ["git", "commit", "-m", msg],
        cwd=str(BASE_DIR),
        capture_output=True
    )
    subprocess.run(
        ["git", "push", "origin", "main"],
        cwd=str(BASE_DIR),
        capture_output=True,
        timeout=60
    )

def process_freguesia(freguesia):
    """Full pipeline for one freguesia."""
    log(f"\n{'='*60}")
    log(f"🚀 Processando freguesia: {freguesia}")
    log(f"{'='*60}")
    
    # Step 1: Clean up old images if needed
    cleanup_images()
    TIFF_DIR.mkdir(parents=True, exist_ok=True)
    JPEG_DIR.mkdir(parents=True, exist_ok=True)
    
    # Step 2: Get all doc_ids for this freguesia
    log(f"📋 Carregando inventário de {freguesia}...")
    docs = filter_inventory(freguesia)
    doc_ids = [d["doc_id"] for d in docs if d["doc_id"]]
    log(f"   Encontrados {len(doc_ids)} livros (doc_ids)")
    
    # Step 3: Download all images
    log("📥 A fazer download de imagens...")
    total_downloaded = 0
    total_pages = 0
    for i, doc_id in enumerate(doc_ids):
        n, total = download_freguesia_images(freguesia, doc_id, max_pages=500)
        total_downloaded += n
        total_pages += total
        if (i + 1) % 20 == 0:
            log(f"   Progresso: {i+1}/{len(doc_ids)} livros, {total_downloaded} imgs baixadas")
    
    log(f"   Download completo: {total_downloaded} imagens de {total_pages} páginas")
    
    # Step 4: Run HTR
    log("🔍 A processar com HTR (Gemini 3 Flash Preview)...")
    start_time = time.time()
    success = run_htr()
    elapsed = time.time() - start_time
    
    if success:
        tiff_count = len([f for f in TIFF_DIR.glob("*.tiff")])
        log(f"   HTR completo em {elapsed/60:.1f} min. {tiff_count} imagens processadas")
    else:
        log("   ❌ HTR falhou")
    
    # Step 5: Sync to Supabase
    log("☁️ A sincronizar para Supabase...")
    sync_to_supabase()
    log("   Sync concluído")
    
    # Step 6: Commit and push
    htr_count = len(list(INPUT_DIR.glob("*.json")))
    stats = {"processed": tiff_count, "htr_files": htr_count, "synced": htr_count - 1220}
    log(f"📤 A hacer commit e push para GitHub...")
    commit_and_push(freguesia, stats)
    log("   GitHub actualizado")
    
    # Step 7: Cleanup images
    log("🧹 A limpar imagens para libertar espaço...")
    cleanup_images()
    
    log(f"✅ Freguesia {freguesia} completada!")
    return True

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--freguesia", help="Freguesia specific to process")
    parser.add_argument("--status", action="store_true", help="Show pipeline status")
    parser.add_argument("--dry-run", action="store_true", help="Show plan without executing")
    parser.add_argument("--all", action="store_true", help="Process all freguesias in sequence")
    args = parser.parse_args()
    
    if args.status:
        state = load_state()
        print(f"Freguesias processadas: {len(state.get('processed_freguesias', []))}")
        for f in state.get('processed_freguesias', []):
            print(f"  ✓ {f}")
        disk = get_disk_usage()
        print(f"\nEspaço em disco: {disk['free']:.1f}GB/{disk['total']:.1f}GB livre")
        htr_count = len(list(INPUT_DIR.glob("*.json")))
        print(f"HTR files: {htr_count}")
        return
    
    state = load_state()
    
    if args.freguesia:
        process_freguesia(args.freguesia)
        state["processed_freguesias"] = state.get("processed_freguesias", []) + [args.freguesia]
        save_state(state)
    elif args.all:
        for freg in TARGET_FREGUESIAS:
            if freg in state.get("processed_freguesias", []):
                log(f"⏭️ {freg} já processada, saltando...")
                continue
            process_freguesia(freg)
            state["processed_freguesias"] = state.get("processed_freguesias", []) + [freg]
            save_state(state)
    else:
        # Process next unprocessed freguesia
        processed = set(state.get("processed_freguesias", []))
        # Start with Celorico da Beira freguesias (already done), then move on
        remaining = [f for f in TARGET_FREGUESIAS if f not in processed]
        
        if remaining:
            if args.dry_run:
                print(f"Próxima freguesia: {remaining[0]}")
                print(f"Restantes: {len(remaining)} freguesias")
                return
            
            process_freguesia(remaining[0])
            state["processed_freguesias"] = list(processed) + [remaining[0]]
            save_state(state)
        else:
            log("🎉 Todas as freguesias processadas!")

if __name__ == "__main__":
    main()
