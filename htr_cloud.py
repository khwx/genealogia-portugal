#!/usr/bin/env python3
"""
Cloud-based HTR for Portuguese death records.
Supports: OpenRouter (free vision models), Google AI Studio (Gemini Flash).
Resume-safe: skips already processed files.
"""

import os
import sys
import json
import base64
import time
import re
import signal
import logging
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime
from PIL import Image
from io import BytesIO

INPUT_DIR = Path(os.environ.get("INPUT_DIR", "/home/pxtkhw/projetos/obitos/output/full_images"))
OUTPUT_DIR = Path(os.environ.get("OUTPUT_DIR", "/home/pxtkhw/projetos/obitos/output/htr_text"))
METADATA_DIR = Path(os.environ.get("METADATA_DIR", "/home/pxtkhw/projetos/obitos/output/htr_metadata"))
LOG_FILE = Path(os.environ.get("LOG_FILE", "/home/pxtkhw/projetos/obitos/output/htr_cloud.log"))
STATE_FILE = Path(os.environ.get("STATE_FILE", "/home/pxtkhw/projetos/obitos/output/htr_cloud_state.json"))

BACKEND = os.environ.get("HTR_BACKEND", "openrouter")
OPENROUTER_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.environ.get("OPENROUTER_MODEL", "google/gemini-2.0-flash-001")
GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")

MAX_IMAGE_WIDTH = int(os.environ.get("MAX_IMAGE_WIDTH", "1500"))
JPEG_QUALITY = int(os.environ.get("JPEG_QUALITY", "80"))
DELAY_BETWEEN_REQUESTS = float(os.environ.get("DELAY_BETWEEN_REQUESTS", "1"))
MAX_RETRIES = int(os.environ.get("MAX_RETRIES", "5"))
RETRY_DELAY = float(os.environ.get("RETRY_DELAY", "10"))
REQUEST_TIMEOUT = int(os.environ.get("REQUEST_TIMEOUT", "120"))

BATCH_SIZE = int(os.environ.get("BATCH_SIZE", "50"))
DRY_RUN = os.environ.get("DRY_RUN", "").lower() in ("1", "true", "yes")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("htr_cloud")

shutdown_requested = False
def signal_handler(signum, frame):
    global shutdown_requested
    log.info("Shutdown signal received. Finishing current image...")
    shutdown_requested = True

signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)


PROMPT = """You are a transcription assistant for Portuguese historical documents.

This image shows a page from a death register (livro de óbitos) from Celorico da Beira, Portugal, from the 1700s-1800s.

Transcribe ALL the handwritten text you can read. Output the text as-is, preserving line breaks.

Then extract structured data:
- Names of deceased persons
- Death dates
- Ages
- Parents' names
- Spouses' names
- Parish (freguesia)

Format your response as:
---TRANSCRIPTION---
[transcribed text here]
---ENTITIES---
NOME: [name]
DATA ÓBITO: [date]
IDADE: [age]
PAI: [father]
MÃE: [mother]
CÔNJUGE: [spouse]
FREGUESIA: [parish]
---END---

If you cannot read something, write [ilegível]. Do NOT invent content."""


def load_state():
    if STATE_FILE.exists():
        with open(STATE_FILE) as f:
            return json.load(f)
    return {
        "started_at": datetime.now().isoformat(),
        "backend": BACKEND,
        "processed": 0,
        "errors": 0,
        "skipped": 0,
        "total_time": 0,
        "last_file": None,
        "status": "running",
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
                if d.get("status") == "success" and d.get("text_length", 0) > 20:
                    processed.add(stem)
    return processed


def prepare_image(tiff_path):
    img = Image.open(tiff_path).convert("RGB")
    w, h = img.size
    scale = min(MAX_IMAGE_WIDTH / w, 1.0)
    if scale < 1.0:
        new_w = int(w * scale)
        new_h = int(h * scale)
        img = img.resize((new_w, new_h), Image.LANCZOS)
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=JPEG_QUALITY)
    return base64.b64encode(buf.getvalue()).decode()


def call_openrouter(img_b64, prompt):
    url = "https://openrouter.ai/api/v1/chat/completions"
    payload = {
        "model": OPENROUTER_MODEL,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"},
                    },
                    {"type": "text", "text": prompt},
                ],
            }
        ],
        "max_tokens": 2000,
        "temperature": 0.1,
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {OPENROUTER_KEY}",
        "HTTP-Referer": "https://github.com/khwx/genealogia-portugal",
    }

    for attempt in range(MAX_RETRIES):
        try:
            req = urllib.request.Request(
                url, data=json.dumps(payload).encode(), headers=headers
            )
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
                data = json.loads(resp.read())
                text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                usage = data.get("usage", {})
                return {
                    "status": "success",
                    "text": text,
                    "tokens": usage.get("completion_tokens", 0),
                    "duration_ms": 0,
                    "model": data.get("model", OPENROUTER_MODEL),
                }
        except urllib.error.HTTPError as e:
            body = e.read().decode()[:200]
            if e.code == 429:
                wait = RETRY_DELAY * (attempt + 1) * 2
                log.warning(f"Rate limited (429). Waiting {wait}s...")
                time.sleep(wait)
            elif e.code >= 500:
                log.warning(f"Server error {e.code} (attempt {attempt+1}/{MAX_RETRIES})")
                time.sleep(RETRY_DELAY * (attempt + 1))
            else:
                log.error(f"HTTP {e.code}: {body}")
                return {"status": "error", "text": "", "error": f"HTTP {e.code}: {body}"}
        except Exception as e:
            log.warning(f"Error (attempt {attempt+1}/{MAX_RETRIES}): {e}")
            time.sleep(RETRY_DELAY)

    return {"status": "error", "text": "", "error": "max_retries_exceeded"}


def call_gemini(img_b64, prompt):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_KEY}"
    payload = {
        "contents": [
            {
                "parts": [
                    {"inline_data": {"mime_type": "image/jpeg", "data": img_b64}},
                    {"text": prompt},
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": 2000,
        },
    }
    headers = {"Content-Type": "application/json"}

    for attempt in range(MAX_RETRIES):
        try:
            req = urllib.request.Request(
                url, data=json.dumps(payload).encode(), headers=headers
            )
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
                data = json.loads(resp.read())
                candidates = data.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    text = "".join(p.get("text", "") for p in parts)
                else:
                    text = ""
                usage = data.get("usageMetadata", {})
                return {
                    "status": "success",
                    "text": text,
                    "tokens": usage.get("candidatesTokenCount", 0),
                    "duration_ms": 0,
                    "model": GEMINI_MODEL,
                }
        except urllib.error.HTTPError as e:
            body = e.read().decode()[:200]
            if e.code == 429:
                wait = RETRY_DELAY * (attempt + 1) * 2
                log.warning(f"Rate limited (429). Waiting {wait}s...")
                time.sleep(wait)
            elif e.code >= 500:
                log.warning(f"Server error {e.code} (attempt {attempt+1}/{MAX_RETRIES})")
                time.sleep(RETRY_DELAY * (attempt + 1))
            else:
                log.error(f"HTTP {e.code}: {body}")
                return {"status": "error", "text": "", "error": f"HTTP {e.code}: {body}"}
        except Exception as e:
            log.warning(f"Error (attempt {attempt+1}/{MAX_RETRIES}): {e}")
            time.sleep(RETRY_DELAY)

    return {"status": "error", "text": "", "error": "max_retries_exceeded"}


def call_htr(img_b64, prompt):
    if BACKEND == "gemini":
        if not GEMINI_KEY:
            return {"status": "error", "text": "", "error": "GEMINI_API_KEY not set"}
        return call_gemini(img_b64, prompt)
    elif BACKEND == "openrouter":
        if not OPENROUTER_KEY:
            return {"status": "error", "text": "", "error": "OPENROUTER_API_KEY not set"}
        return call_openrouter(img_b64, prompt)
    else:
        return {"status": "error", "text": "", "error": f"Unknown backend: {BACKEND}"}


def extract_structured_data(text):
    names = []
    dates = []
    places = []

    name_patterns = [
        r"[Dd]\.\s*\w+\s+de\s+\w+",
        r"[A-Z]\w+\s+de\s+\w+(?:\s+e\s+\w+)?",
        r"filh[oa]\s+de\s+\w+",
        r"mulher\s+de\s+\w+",
        r"marido\s+de\s+\w+",
        r"vi[úu]v[oa]\s+de\s+\w+",
    ]
    date_patterns = [
        r"\d{1,2}\s+de\s+(?:janeiro|fevereiro|mar[çc]o|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro)\s+de\s+\d{4}",
        r"ano\s+(?:do\s+Senhor\s+)?de\s+\d{4}",
        r"\d{1,2}/\d{1,2}/\d{4}",
        r"\d{4}",
    ]
    place_patterns = [
        r"Celorico(?:\s+da\s+Beira)?",
        r"freguesi[oa]\s+de\s+\w+",
        r"natural\s+de\s+\w+",
        r"Igreja\s+Matriz",
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
        "places": list(set(places)),
    }


def process_image(tiff_path, state):
    file_id = tiff_path.stem
    output_json = OUTPUT_DIR / f"{file_id}.json"
    meta_json = METADATA_DIR / f"{file_id}.json"

    start_time = time.time()

    try:
        img_b64 = prepare_image(tiff_path)
        result = call_htr(img_b64, PROMPT)

        elapsed = time.time() - start_time
        text = result.get("text", "")
        structured = extract_structured_data(text)

        metadata = {
            "file_id": file_id,
            "source_file": tiff_path.name,
            "backend": BACKEND,
            "model": result.get("model", ""),
            "status": result["status"],
            "text_length": len(text),
            "tokens": result.get("tokens", 0),
            "duration_ms": result.get("duration_ms", 0),
            "wall_time_s": elapsed,
            "processed_at": datetime.now().isoformat(),
            "names_found": structured["names"],
            "dates_found": structured["dates"],
            "places_found": structured["places"],
        }

        output_data = {
            "file_id": file_id,
            "raw_text": text,
            "structured": structured,
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
            f"({elapsed:.1f}s, {len(text)} chars, names: {names_str})"
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
            "backend": BACKEND,
            "model": "",
            "status": "error",
            "error": str(e),
            "wall_time_s": elapsed,
            "processed_at": datetime.now().isoformat(),
        }
        meta_json = METADATA_DIR / f"{file_id}.json"
        with open(meta_json, "w") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

    save_state(state)


def main():
    if len(sys.argv) > 1:
        global BACKEND, OPENROUTER_KEY, GEMINI_KEY
        for arg in sys.argv[1:]:
            if arg.startswith("--backend="):
                BACKEND = arg.split("=", 1)[1]
            elif arg.startswith("--openrouter-key="):
                OPENROUTER_KEY = arg.split("=", 1)[1]
            elif arg.startswith("--gemini-key="):
                GEMINI_KEY = arg.split("=", 1)[1]
            elif arg == "--dry-run":
                global DRY_RUN
                DRY_RUN = True
            elif arg == "--test":
                global BATCH_SIZE
                BATCH_SIZE = 3

    if BACKEND == "openrouter" and not OPENROUTER_KEY:
        if not os.environ.get("OPENROUTER_API_KEY"):
            log.error("OPENROUTER_API_KEY not set. Get one at https://openrouter.ai/keys")
            sys.exit(1)
    elif BACKEND == "gemini" and not GEMINI_KEY:
        if not os.environ.get("GEMINI_API_KEY"):
            log.error("GEMINI_API_KEY not set. Get one at https://aistudio.google.com/apikey")
            sys.exit(1)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    METADATA_DIR.mkdir(parents=True, exist_ok=True)

    state = load_state()

    tiff_files = sorted(INPUT_DIR.glob("*.tiff"))
    already = get_already_processed()
    to_process = [f for f in tiff_files if f.stem not in already]

    if BATCH_SIZE > 0:
        to_process = to_process[:BATCH_SIZE]

    log.info(f"=== Cloud HTR Batch Started ===")
    log.info(f"Backend: {BACKEND}")
    log.info(f"Model: {OPENROUTER_MODEL if BACKEND == 'openrouter' else GEMINI_MODEL}")
    log.info(f"Total images: {len(tiff_files)}")
    log.info(f"Already processed: {len(already)}")
    log.info(f"To process: {len(to_process)} (batch size: {BATCH_SIZE})")
    log.info(f"Dry run: {DRY_RUN}")

    if DRY_RUN:
        log.info("Dry run mode. Listing files to process:")
        for f in to_process[:20]:
            log.info(f"  {f.name}")
        if len(to_process) > 20:
            log.info(f"  ... and {len(to_process) - 20} more")
        return

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

        process_image(tiff_path, state)

        if (i + 1) % 10 == 0:
            avg_time = state["total_time"] / max(state["processed"], 1)
            remaining = len(to_process) - (i + 1)
            eta_mins = remaining * avg_time / 60
            log.info(
                f"--- Progress: {i+1}/{len(to_process)} "
                f"({state['processed']} ok, {state['errors']} err) "
                f"Avg: {avg_time:.1f}s/img, ETA: {eta_mins:.0f}min ---"
            )

    state["status"] = "completed"
    state["completed_at"] = datetime.now().isoformat()
    save_state(state)
    log.info(
        f"=== Batch Complete: {state['processed']} processed, {state['errors']} errors ==="
    )


if __name__ == "__main__":
    main()
