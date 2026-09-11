#!/usr/bin/env python3
"""
Fetch page listings from Digitarq API for BIRT and MARR books.

Reads the inventory (obitos_inventario.json), filters BIRT/MARR books,
extracts doc_ids, and fetches page listings from the Digitarq API.
Merges results into existing doc_file_listings.json.
"""
import json
import re
import time
import urllib.request
import urllib.error
from pathlib import Path

BASE_DIR = Path(__file__).parent
OUTPUT_DIR = BASE_DIR / "output"
DATA_DIR = OUTPUT_DIR / "data"
INVENTARIO_FILE = OUTPUT_DIR / "obitos_inventario.json"
DOC_FILE_LISTINGS = DATA_DIR / "doc_file_listings.json"

DIGITARQ_API = "https://digitarq.arquivos.pt/api/rdigital"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://digitarq.arquivos.pt/",
}

def extract_doc_id(url):
    """Extract doc_id hash from Digitarq URL."""
    if not url:
        return None
    m = re.search(r"documentDetails/([0-9a-fA-F]+)", url)
    return m.group(1).lower() if m else None

def load_inventory():
    with open(INVENTARIO_FILE, encoding="utf-8") as f:
        return json.load(f)

def load_existing_listings():
    if DOC_FILE_LISTINGS.exists():
        with open(DOC_FILE_LISTINGS, encoding="utf-8") as f:
            return json.load(f)
    return {}

def fetch_page_listings(doc_id, max_pages=1000):
    """Fetch page listings for a doc_id from Digitarq API."""
    url = f"{DIGITARQ_API}/{doc_id}?max={max_pages}"
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read())
        return data.get("results", [])
    except urllib.error.HTTPError as e:
        print(f"  HTTP {e.code} for {doc_id}: {e.reason}")
        return []
    except Exception as e:
        print(f"  Error for {doc_id}: {e}")
        return []

def main():
    print("=" * 60)
    print("Fetch Page Listings for BIRT/MARR")
    print("=" * 60)

    # Load inventory
    print("Loading inventory...")
    inventory = load_inventory()

    # Filter BIRT and MARR books
    birt_books = [d for d in inventory if d.get("tipo_cod") == "BIRT"]
    marr_books = [d for d in inventory if d.get("tipo_cod") == "MARR"]

    # Extract unique doc_ids
    birt_doc_ids = set()
    marr_doc_ids = set()

    for book in birt_books:
        doc_id = extract_doc_id(book.get("url_info", ""))
        if doc_id:
            birt_doc_ids.add(doc_id)

    for book in marr_books:
        doc_id = extract_doc_id(book.get("url_info", ""))
        if doc_id:
            marr_doc_ids.add(doc_id)

    print(f"BIRT books: {len(birt_books)} -> unique doc_ids: {len(birt_doc_ids)}")
    print(f"MARR books: {len(marr_books)} -> unique doc_ids: {len(marr_doc_ids)}")

    # Load existing listings
    existing = load_existing_listings()
    existing_ids = set(k.lower() for k in existing.keys())
    print(f"Existing doc_ids in listings: {len(existing_ids)}")

    # Determine which to fetch
    to_fetch = {}
    for doc_id in birt_doc_ids:
        if doc_id not in existing_ids:
            to_fetch[doc_id] = "BIRT"
    for doc_id in marr_doc_ids:
        if doc_id not in existing_ids:
            to_fetch[doc_id] = "MARR"

    print(f"New doc_ids to fetch: {len(to_fetch)} (BIRT: {sum(1 for v in to_fetch.values() if v == 'BIRT')}, MARR: {sum(1 for v in to_fetch.values() if v == 'MARR')})")

    if not to_fetch:
        print("Nothing new to fetch.")
        return

    # Fetch listings
    total_fetched = 0
    total_pages = 0
    for i, (doc_id, tipo) in enumerate(sorted(to_fetch.items()), 1):
        print(f"[{i}/{len(to_fetch)}] Fetching {doc_id} ({tipo})...")
        pages = fetch_page_listings(doc_id)
        if pages:
            existing[doc_id] = pages
            total_fetched += 1
            total_pages += len(pages)
            print(f"  -> {len(pages)} pages")
        else:
            print(f"  -> No pages found or error")
        time.sleep(0.5)  # Rate limiting

    # Save updated listings
    with open(DOC_FILE_LISTINGS, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)

    print(f"\n=== Complete ===")
    print(f"Fetched: {total_fetched} doc_ids")
    print(f"Total pages added: {total_pages}")
    print(f"Total doc_ids in listings: {len(existing)}")
    print(f"Saved to: {DOC_FILE_LISTINGS}")

if __name__ == "__main__":
    main()