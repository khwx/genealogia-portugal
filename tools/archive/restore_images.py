#!/usr/bin/env python3
"""
Restore missing TIFF images from Digitarq using HTR file_ids.
Mapeia cada file_id -> doc_id via API e faz download via endpoint de disseminação.
"""
import json
import time
import urllib.request
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_DIR = Path(__file__).parent
OUTPUT_DIR = BASE_DIR / "output"
INPUT_DIR = OUTPUT_DIR / "htr_text"
TIFF_DIR = OUTPUT_DIR / "full_images" / "tiff"
JPEG_DIR = OUTPUT_DIR / "full_images" / "jpeg"
CELORICO_JSON = OUTPUT_DIR / "data" / "celorico_completo.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://digitarq.arquivos.pt/",
}

DIGITARQ_API = "https://digitarq.arquivos.pt/api/rdigital"
DISSEMINATION_URL = "https://digitarq.arquivos.pt/rdigital/dissemination"


def load_file_to_docid():
    """Build mapping from file_id to doc_id via celorico_completo.json."""
    mapping = {}
    with open(CELORICO_JSON) as f:
        data = json.load(f)
    for doc in data.get("documentos", []):
        doc_id = doc.get("doc_id", "")
        for img in doc.get("imagens", []):
            fid = str(img.get("file_id", ""))
            if fid and doc_id:
                mapping[fid] = doc_id
    return mapping


def get_page_list(doc_id):
    """Get pages from Digitarq API, returning list of (page_id, page_name)."""
    url = f"{DIGITARQ_API}/{doc_id}?max=200"
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())
    return [(p["id"], p["name"]) for p in data.get("results", [])]


def download_tiff(file_id, page_id, doc_id):
    """Download single TIFF via dissemination endpoint."""
    tiff_path = TIFF_DIR / f"{file_id}.tiff"
    if tiff_path.exists() and tiff_path.stat().st_size > 1000:
        return f"SKIP (exists): {file_id}"
    
    url = f"{DISSEMINATION_URL}?fileId={page_id}&download=true"
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            content = resp.read()
            if "image" in resp.headers.get("Content-Type", ""):
                TIFF_DIR.mkdir(parents=True, exist_ok=True)
                tiff_path.write_bytes(content)
                # Convert to JPEG
                try:
                    from PIL import Image
                    img = Image.open(tiff_path)
                    JPEG_DIR.mkdir(parents=True, exist_ok=True)
                    img.convert("RGB").save(JPEG_DIR / f"{file_id}.jpg", "JPEG", quality=85)
                except:
                    pass
                return f"OK: {file_id} ({len(content)} bytes)"
            return f"FAIL (not image): {file_id}"
    except Exception as e:
        return f"ERROR: {file_id} - {e}"


def main():
    import sys
    
    TIFF_DIR.mkdir(parents=True, exist_ok=True)
    JPEG_DIR.mkdir(parents=True, exist_ok=True)
    
    print("=== Image Restoration ===")

    # Get all file_ids from HTR text
    htr_files = sorted(INPUT_DIR.glob("*.json"))
    all_file_ids = {f.stem for f in htr_files}
    print(f"HTR files: {len(all_file_ids)}")
    
    # Check which already exist
    existing = {f.stem.replace('.tiff', '') for f in TIFF_DIR.glob("*.tiff")}
    missing = all_file_ids - existing
    print(f"Already downloaded: {len(existing)}")
    print(f"Missing: {len(missing)}")
    
    if not missing:
        print("All images already present!")
        return
    
    # Load file_id -> doc_id mapping
    file_to_doc = load_file_to_docid()
    print(f"File-to-doc mapping: {len(file_to_doc)}")
    
    # Pre-load all doc_id -> page lists
    doc_to_pages = {}
    unique_docs = set(file_to_doc.get(fid) for fid in missing if fid in file_to_doc)
    print(f"Fetching page lists from API for {len(unique_docs)} books...")
    
    for doc_id in unique_docs:
        if not doc_id:
            continue
        try:
            pages = get_page_list(doc_id)
            doc_to_pages[doc_id] = pages
            print(f"  {doc_id}: {len(pages)} pages", flush=True)
        except Exception as e:
            print(f"  API error for {doc_id}: {e}", flush=True)
    
    # Build download queue
    download_queue = []
    for fid in sorted(missing):
        doc_id = file_to_doc.get(fid, "")
        if doc_id in doc_to_pages:
            pages = doc_to_pages[doc_id]
            page_id = next((pid for pid, pname in pages if pid == fid), None)
            if page_id:
                download_queue.append((fid, page_id))
    
    print(f"\nDownload queue: {len(download_queue)} images")
    print(f"Starting downloads with 4 parallel workers...")
    
    completed = 0
    errors = 0
    
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(download_tiff, fid, pid, ""): fid for fid, pid in download_queue}
        for future in as_completed(futures):
            result = future.result()
            if result.startswith("ERROR"):
                errors += 1
                if errors <= 5:
                    print(f"  {result}", flush=True)
            else:
                completed += 1
            if (completed + errors) % 100 == 0:
                print(f"  Progress: {completed} OK, {errors} errors (total: {completed+errors}/{len(download_queue)})", flush=True)
    
    print(f"\n{'='*60}")
    print(f"CONCLUÍDO!")
    print(f"Downloaded: {completed}")
    print(f"Errors: {errors}")
    print(f"Total TIFFs: {len(list(TIFF_DIR.glob('*.tiff')))}")
    print(f"Total JPEGs: {len(list(JPEG_DIR.glob('*.jpg')))}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
