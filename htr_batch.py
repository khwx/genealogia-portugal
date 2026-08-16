#!/usr/bin/env python3
"""
Batch HTR (Handwritten Text Recognition) using gemma3:4b via Ollama.
Processes Portuguese death records from Celorico da Beira.
Designed to be resume-safe: skips already processed files.
"""

import os
import sys
import json
import base64
import time
import re
import signal
import logging
from pathlib import Path
from datetime import datetime
from PIL import Image
from io import BytesIO
import requests

# Configuration
INPUT_DIR = Path(os.environ.get("INPUT_DIR", "/home/pxtkhw/projetos/obitos/output/full_images"))
OUTPUT_DIR = Path(os.environ.get("OUTPUT_DIR", "/home/pxtkhw/projetos/obitos/output/htr_text"))
METADATA_DIR = Path(os.environ.get("METADATA_DIR", "/home/pxtkhw/projetos/obitos/output/htr_metadata"))
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
MODEL = os.environ.get("HTR_MODEL", "gemma3:4b")
LOG_FILE = Path(os.environ.get("LOG_FILE", "/home/pxtkhw/projetos/obitos/output/htr_batch.log"))
STATE_FILE = Path(os.environ.get("STATE_FILE", "/home/pxtkhw/projetos/obitos/output/htr_state.json"))

# Image processing settings
MAX_IMAGE_WIDTH = int(os.environ.get("MAX_IMAGE_WIDTH", "1200"))
MAX_IMAGE_HEIGHT = int(os.environ.get("MAX_IMAGE_HEIGHT", "900"))
JPEG_QUALITY = int(os.environ.get("JPEG_QUALITY", "85"))

# Rate limiting
DELAY_BETWEEN_REQUESTS = float(os.environ.get("DELAY_BETWEEN_REQUESTS", "2"))
MAX_RETRIES = int(os.environ.get("MAX_RETRIES", "3"))
RETRY_DELAY = float(os.environ.get("RETRY_DELAY", "30"))
REQUEST_TIMEOUT = int(os.environ.get("REQUEST_TIMEOUT", "600"))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout)
    ]
)
log = logging.getLogger("htr_batch")

# Graceful shutdown
shutdown_requested = False
def signal_handler(signum, frame):
    global shutdown_requested
    log.info("Shutdown signal received. Finishing current image...")
    shutdown_requested = True

signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)


def load_state():
    if STATE_FILE.exists():
        with open(STATE_FILE) as f:
            return json.load(f)
    return {
        "started_at": datetime.now().isoformat(),
        "processed": 0,
        "errors": 0,
        "skipped": 0,
        "total_time": 0,
        "last_file": None,
        "status": "running"
    }


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def get_already_processed():
    processed = set()
    if OUTPUT_DIR.exists():
        for f in OUTPUT_DIR.glob("*.json"):
            stem = f.stem
            meta = METADATA_DIR / f"{stem}.json"
            if meta.exists():
                with open(meta) as mf:
                    d = json.load(mf)
                    if d.get("status") == "success" and d.get("text_length", 0) > 10:
                        processed.add(stem)
    return processed


def prepare_image(tiff_path):
    img = Image.open(tiff_path).convert("RGB")
    w, h = img.size
    scale = min(MAX_IMAGE_WIDTH / w, MAX_IMAGE_HEIGHT / h, 1.0)
    if scale < 1.0:
        new_w = int(w * scale)
        new_h = int(h * scale)
        img = img.resize((new_w, new_h), Image.LANCZOS)
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=JPEG_QUALITY)
    return base64.b64encode(buf.getvalue()).decode()


def call_ollama(img_b64, prompt, retries=MAX_RETRIES):
    payload = {
        "model": MODEL,
        "prompt": prompt,
        "images": [img_b64],
        "stream": False,
        "options": {
            "temperature": 0.05,
            "num_predict": 1500
        }
    }
    
    for attempt in range(retries):
        try:
            r = requests.post(
                f"{OLLAMA_URL}/api/generate",
                json=payload,
                timeout=REQUEST_TIMEOUT
            )
            if r.status_code == 200:
                d = r.json()
                return {
                    "status": "success",
                    "text": d.get("response", ""),
                    "tokens": d.get("eval_count", 0),
                    "duration_ms": d.get("total_duration", 0) / 1e6
                }
            elif r.status_code == 500:
                log.warning(f"Ollama 500 error (attempt {attempt+1}/{retries})")
                time.sleep(RETRY_DELAY)
            else:
                log.error(f"Ollama error: {r.status_code} {r.text[:200]}")
                return {"status": "error", "text": "", "error": f"HTTP {r.status_code}"}
        except requests.exceptions.Timeout:
            log.warning(f"Timeout (attempt {attempt+1}/{retries})")
            time.sleep(RETRY_DELAY)
        except requests.exceptions.ConnectionError:
            log.warning(f"Connection error (attempt {attempt+1}/{retries})")
            time.sleep(RETRY_DELAY * 2)
        except Exception as e:
            log.error(f"Unexpected error: {e}")
            time.sleep(RETRY_DELAY)
    
    return {"status": "error", "text": "", "error": "max_retries_exceeded"}


def extract_structured_data(text):
    names = []
    dates = []
    places = []
    
    name_patterns = [
        r'[Dd]\.\s*\w+\s+de\s+\w+',
        r'[A-Z]\w+\s+de\s+\w+(?:\s+e\s+\w+)?',
        r'filh[oa]\s+de\s+\w+',
        r'mulher\s+de\s+\w+',
        r'marido\s+de\s+\w+',
        r'vi[úu]v[oa]\s+de\s+\w+',
    ]
    
    date_patterns = [
        r'\d{1,2}\s+de\s+(?:janeiro|fevereiro|mar[çc]o|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro)\s+de\s+\d{4}',
        r'ano\s+(?:do\s+Senhor\s+)?de\s+\d{4}',
        r'\d{1,2}/\d{1,2}/\d{4}',
        r'\d{4}',
    ]
    
    place_patterns = [
        r'Celorico(?:\s+da\s+Beira)?',
        r'freguesi[oa]\s+de\s+\w+',
        r'natural\s+de\s+\w+',
        r'Igreja\s+Matriz',
    ]
    
    for pattern in name_patterns:
        names.extend(re.findall(pattern, text, re.IGNORECASE))
    
    for pattern in date_patterns:
        dates.extend(re.findall(pattern, text, re.IGNORECASE))
    
    for pattern in place_patterns:
        places.extend(re.findall(pattern, text, re.IGNORECASE))
    
    return {
        "names": list(set(names)),
        "dates": list(set(dates)),
        "places": list(set(places))
    }


PROMPT = """Transcreva o texto manuscrito deste registo de óbitos português. 
Extraia: nomes das pessoas falecidas, datas de óbito, idades, nomes dos pais/cônjuges, freguesia.
Se não conseguir ler, escreva [ilegível].
Formato de saída:
NOME: 
DATA ÓBITO:
IDADE:
PAI:
MÃE:
CÔNJUGE:
FREGUESIA:
OBSERVAÇÕES:"""


def process_image(tiff_path, state):
    file_id = tiff_path.stem
    output_json = OUTPUT_DIR / f"{file_id}.json"
    meta_json = METADATA_DIR / f"{file_id}.json"
    
    start_time = time.time()
    
    try:
        img_b64 = prepare_image(tiff_path)
        result = call_ollama(img_b64, PROMPT)
        
        elapsed = time.time() - start_time
        
        text = result.get("text", "")
        structured = extract_structured_data(text)
        
        metadata = {
            "file_id": file_id,
            "source_file": tiff_path.name,
            "model": MODEL,
            "status": result["status"],
            "text_length": len(text),
            "tokens": result.get("tokens", 0),
            "duration_ms": result.get("duration_ms", 0),
            "wall_time_s": elapsed,
            "processed_at": datetime.now().isoformat(),
            "names_found": structured["names"],
            "dates_found": structured["dates"],
            "places_found": structured["places"]
        }
        
        output_data = {
            "file_id": file_id,
            "raw_text": text,
            "structured": structured
        }
        
        with open(output_json, "w") as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        
        with open(meta_json, "w") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        
        state["processed"] += 1
        state["total_time"] += elapsed
        state["last_file"] = file_id
        
        names_str = ", ".join(structured["names"][:3]) if structured["names"] else "none"
        log.info(
            f"[{state['processed']}] {file_id}: {result['status']} "
            f"({elapsed:.0f}s, {len(text)} chars, names: {names_str})"
        )
        
        if result["status"] == "error":
            state["errors"] += 1
    
    except Exception as e:
        elapsed = time.time() - start_time
        state["errors"] += 1
        log.error(f"[ERROR] {file_id}: {e}")
        
        metadata = {
            "file_id": file_id,
            "source_file": tiff_path.name,
            "model": MODEL,
            "status": "error",
            "error": str(e),
            "wall_time_s": elapsed,
            "processed_at": datetime.now().isoformat()
        }
        with open(meta_json, "w") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
    
    save_state(state)


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    METADATA_DIR.mkdir(parents=True, exist_ok=True)
    
    state = load_state()
    
    tiff_files = sorted(INPUT_DIR.glob("*.tiff"))
    already = get_already_processed()
    to_process = [f for f in tiff_files if f.stem not in already]
    
    log.info(f"=== HTR Batch Started ===")
    log.info(f"Model: {MODEL}")
    log.info(f"Total images: {len(tiff_files)}")
    log.info(f"Already processed: {len(already)}")
    log.info(f"To process: {len(to_process)}")
    log.info(f"Estimated time: {len(to_process) * 7 / 3600:.1f} hours")
    
    if not to_process:
        log.info("Nothing to process. Exiting.")
        state["status"] = "completed"
        save_state(state)
        return
    
    for i, tiff_path in enumerate(to_process):
        if shutdown_requested:
            log.info("Shutdown requested. Saving state and exiting.")
            state["status"] = "paused"
            save_state(state)
            return
        
        if i > 0 and DELAY_BETWEEN_REQUESTS > 0:
            time.sleep(DELAY_BETWEEN_REQUESTS)
        
        # Check if Ollama is still responding
        try:
            r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
            if r.status_code != 200:
                log.warning("Ollama not responding. Waiting 30s...")
                time.sleep(30)
        except:
            log.warning("Ollama connection lost. Waiting 60s...")
            time.sleep(60)
        
        process_image(tiff_path, state)
        
        if (i + 1) % 10 == 0:
            avg_time = state["total_time"] / max(state["processed"], 1)
            remaining = len(to_process) - (i + 1)
            eta_hours = remaining * avg_time / 3600
            log.info(
                f"--- Progress: {i+1}/{len(to_process)} "
                f"({state['processed']} ok, {state['errors']} err) "
                f"Avg: {avg_time:.0f}s/img, ETA: {eta_hours:.1f}h ---"
            )
    
    state["status"] = "completed"
    state["completed_at"] = datetime.now().isoformat()
    save_state(state)
    log.info(f"=== Batch Complete: {state['processed']} processed, {state['errors']} errors ===")


if __name__ == "__main__":
    main()
