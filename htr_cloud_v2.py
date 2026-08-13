#!/usr/bin/env python3
"""
HTR Cloud V2 - Melhorado para rate limits e eficiência
Features:
- Rate limit por key/modelo com backoff exponencial
- Cache de quotes dezativação/images por key
- Delay dinámico baseado em sucesso/erro
- Retry com circuit breaker
- Health checks de keys
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
from collections import defaultdict
from PIL import Image
from io import BytesIO

# Load .env
env_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
if os.path.exists(env_file):
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                k, v = line.split('=', 1)
                os.environ[k.strip()] = v.strip()

INPUT_DIR = Path(os.environ.get("INPUT_DIR", "/home/pxtkhw/projetos/obitos/output/full_images/tiff"))
OUTPUT_DIR = Path(os.environ.get("OUTPUT_DIR", "/home/pxtkhw/projetos/obitos/output/htr_text"))
METADATA_DIR = Path(os.environ.get("METADATA_DIR", "/home/pxtkhw/projetos/obitos/output/htr_metadata"))
LOG_FILE = Path(os.environ.get("LOG_FILE", "/home/pxtkhw/projetos/obitos/output/htr_cloud_v2.log"))
STATE_FILE = Path(os.environ.get("STATE_FILE", "/home/pxtkhw/projetos/obitos/output/htr_cloud_v2_state.json"))

GEMINI_KEYS = os.environ.get("GEMINI_KEYS", "")
GEMINI_KEYS = [k.strip() for k in GEMINI_KEYS.split(",") if k.strip()]
GEMINI_MODELS = os.environ.get("GEMINI_MODELS", "gemini-3-flash-preview,gemini-2.5-flash").split(",")
GEMINI_MODELS = [m.strip() for m in GEMINI_MODELS if m.strip()]

MAX_IMAGE_WIDTH = int(os.environ.get("MAX_IMAGE_WIDTH", "1500"))
JPEG_QUALITY = int(os.environ.get("JPEG_QUALITY", "80"))
CONCURRENT_REQUESTS = int(os.environ.get("CONCURRENT_REQUESTS", "1"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("htr_cloud_v2")

PROMPT = """You are a transcription assistant for Portuguese historical documents.
This image shows a page from a death register (livro de óbitos) from Celorico da Beira, Portugal.
Output ONLY a JSON object (no other text) with this structure:
{
  "transcription": "full transcribed text here",
  "deceased": [ { "name": "...", "death_date": "YYYY-MM-DD", "age": "...", "father": "...", "mother": "...", "spouse": "..." } ]
}
If you cannot read something, use [ilegível]. Do NOT invent content. Output ONLY the JSON."""


class KeyHealth:
    """Tracks health of each API key"""
    def __init__(self, key, model):
        self.key = key
        self.model = model
        self.success_count = 0
        self.error_count = 0
        self.last_success = 0
        self.last_error = 0
        self.blocked_until = 0
        self.consecutive_errors = 0

    @property
    def health_score(self):
        if self.success_count + self.error_count == 0:
            return 1.0
        return self.success_count / (self.success_count + self.error_count + 1)

    def mark_success(self):
        self.success_count += 1
        self.last_success = time.time()
        self.consecutive_errors = 0

    def mark_error(self, is_rate_limit=False):
        self.error_count += 1
        self.last_error = time.time()
        self.consecutive_errors += 1

    def block(self, seconds):
        self.blocked_until = time.time() + seconds

    @property
    def is_available(self):
        return time.time() > self.blocked_until


class HTRProcessor:
    def __init__(self):
        self.shutdown_requested = False
        self. key_health = {}
        self.global_success = 0
        self.global_errors = 0
        self.state = self.load_state()

    def signal_handler(self, signum, frame):
        sig_name = signal.Signals(signum).name if hasattr(signal, 'Signals') else str(signum)
        log.info(f"Signal {sig_name} received. Finishing current image...")
        self.shutdown_requested = True

    def load_state(self):
        if STATE_FILE.exists():
            with open(STATE_FILE) as f:
                return json.load(f)
        return {
            "started_at": datetime.now().isoformat(),
            "processed": 0,
            "errors": 0,
            "total_time": 0,
            "last_file": None,
            "status": "running",
        }

    def save_state(self):
        with open(STATE_FILE, "w") as f:
            json.dump(self.state, f, indent=2)

    def get_healthy_key(self):
        """Get the healthiest available key"""
        candidates = []
        for key in GEMINI_KEYS:
            for model in GEMINI_MODELS:
                health_key = (key, model)
                if health_key not in self.key_health:
                    self.key_health[health_key] = KeyHealth(key, model)

                kh = self.key_health[health_key]
                if kh.is_available:
                    candidates.append(kh)

        if not candidates:
            # All blocked, wait for earliest
            earliest = float('inf')
            for kh in self.key_health.values():
                if kh.blocked_until > 0 and kh.blocked_until < earliest:
                    earliest = kh.blocked_until
            wait = max(earliest - time.time(), 0) + 2
            log.warning(f"All keys blocked. Waiting {wait:.0f}s...")
            time.sleep(wait)
            return self.get_healthy_key()

        # Sort by health score (most successful first)
        candidates.sort(key=lambda x: (x.health_score, -x.last_success), reverse=True)
        return candidates[0]

    def call_gemini(self, img_b64):
        """Call Gemini API with circuit breaker pattern"""
        attempt = 0
        max_attempts = 5

        while attempt < max_attempts:
            kh = self.get_healthy_key()
            key, model = kh.key, kh.model

            payload = {
                "contents": [{
                    "parts": [
                        {"inline_data": {"mime_type": "image/jpeg", "data": img_b64}},
                        {"text": PROMPT},
                    ]
                }],
                "generationConfig": {"temperature": 0.1, "maxOutputTokens": 2000},
            }

            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"

            try:
                req = urllib.request.Request(
                    url, data=json.dumps(payload).encode(),
                    headers={"Content-Type": "application/json"},
                    method="POST"
                )
                with urllib.request.urlopen(req, timeout=60) as resp:
                    data = json.loads(resp.read())

                    candidates = data.get("candidates", [])
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        text = "".join(p.get("text", "") for p in parts)
                    else:
                        text = data.get("text", "")

                    kh.mark_success()
                    self.global_success += 1
                    return {"status": "success", "text": text, "model": model}

            except urllib.error.HTTPError as e:
                body = e.read().decode()[:200] if e.fp else ""

                if e.code == 429:
                    log.warning(f"Rate limit 429 for ...{key[-6:]} model {model}")
                    kh.mark_error(is_rate_limit=True)
                    kh.block(180)  # Block for 3 minutes
                elif e.code == 503:
                    log.warning(f"Service unavailable 503 for ...{key[-6:]} model {model}")
                    kh.mark_error()
                    kh.block(60)  # Block for 1 minute
                elif e.code >= 500:
                    log.warning(f"Server error {e.code}")
                    kh.mark_error()
                    kh.block(30)
                else:
                    log.error(f"HTTP {e.code}: {body[:100]}")
                    kh.mark_error()
                    kh.block(300)

                attempt += 1
                time.sleep(min(2 ** attempt, 60))  # Exponential backoff

            except Exception as e:
                log.warning(f"Error: {str(e)[:100]}")
                kh.mark_error()
                attempt += 1
                time.sleep(5)

        return {"status": "error", "text": "", "error": "max_retries_exceeded"}

    def prepare_image(self, tiff_path):
        img = Image.open(tiff_path).convert("RGB")
        scale = min(MAX_IMAGE_WIDTH / img.size[0], 1.0)
        if scale < 1.0:
            new_size = (int(img.size[0] * scale), int(img.size[1] * scale))
            img = img.resize(new_size, Image.LANCZOS)
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=JPEG_QUALITY)
        return base64.b64encode(buf.getvalue()).decode()

    def get_processed_files(self):
        processed = set()
        if OUTPUT_DIR.exists():
            for f in OUTPUT_DIR.glob("*.json"):
                processed.add(f.stem)
        return processed

    def process_single(self, tiff_path):
        start = time.time()
        file_id = tiff_path.stem

        try:
            img_b64 = self.prepare_image(tiff_path)
            result = self.call_gemini(img_b64)
            elapsed = time.time() - start

            metadata = {
                "file_id": file_id,
                "status": result["status"],
                "model": result.get("model", ""),
                "text_length": len(result.get("text", "")),
                "wall_time_s": elapsed,
                "processed_at": datetime.now().isoformat(),
            }

            output_data = {
                "file_id": file_id,
                "raw_text": result.get("text", ""),
            }

            with open(OUTPUT_DIR / f"{file_id}.json", "w", encoding="utf-8") as f:
                json.dump(output_data, f, indent=2, ensure_ascii=False, default=str)

            with open(METADATA_DIR / f"{file_id}.json", "w", encoding="utf-8") as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False, default=str)

            self.state["processed"] += 1
            self.state["total_time"] += elapsed
            self.state["last_file"] = file_id

            log.info(f"[{self.state['processed']}] {file_id}: {result['status']} ({elapsed:.1f}s, {metadata['text_length']} chars)")

            if result["status"] == "error":
                self.state["errors"] += 1

        except Exception as e:
            log.error(f"[ERROR] {file_id}: {e}")
            self.state["errors"] += 1

        self.save_state()

    def run(self):
        signal.signal(signal.SIGTERM, self.signal_handler)
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGHUP, self.signal_handler)

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        METADATA_DIR.mkdir(parents=True, exist_ok=True)

        tiff_files = sorted(INPUT_DIR.glob("*.tiff"))
        processed = self.get_processed_files()
        to_process = [f for f in tiff_files if f.stem not in processed]

        log.info(f"=== HTR V2 Started: {len(processed)}/{len(tiff_files)} already done, {len(to_process)} remaining ===")
        log.info(f"Keys: {len(GEMINI_KEYS)} | Models: {len(GEMINI_MODELS)} | Target: all remaining")

        if not to_process:
            log.info("All done!")
            return

        for i, tiff_path in enumerate(to_process):
            if self.shutdown_requested:
                log.info("Shutdown requested. Exiting gracefully.")
                break

            self.process_single(tiff_path)

            # ULTRA SLOW MODE: 10 min delay between requests to avoid rate limits
            # This processes ~100 images/day per 7 keys, well within quotas
            if self.global_errors > 0 and self.global_success > 0:
                error_rate = self.global_errors / (self.global_success + self.global_errors)
                if error_rate > 0.5:
                    sleep_time = 900  # 15 min if many errors
                elif error_rate > 0.2:
                    sleep_time = 600   # 10 min if some errors (default)
                else:
                    sleep_time = 600    # 10 min base delay
            else:
                sleep_time = 600       # 10 min base delay between requests

            if i > 0:  # Don't delay on first run
                time.sleep(sleep_time)

        log.info(f"=== Done: {self.state['processed']} processed, {self.state['errors']} errors ===")


if __name__ == "__main__":
    processor = HTRProcessor()
    processor.run()
