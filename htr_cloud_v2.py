#!/usr/bin/env python3
"""
HTR Cloud V2 - OCR/HTR via Gemini com pacing por chave + concorrência.

Comportamento:
- Cada chave Gemini tem o seu próprio rate-limit (KEY_INTERVAL) para respeitar
  o free tier (~150 pedidos/dia por chave).
- Várias chaves/modelos processam em paralelo (CONCURRENT_REQUESTS).
- Health checks + backoff em 429/5xx (bloqueio temporário da chave).
- Idempotente: não reprocessa ficheiros já transcritos.
"""

import os
import sys
import re
import json
import base64
import time
import signal
import logging
import threading
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
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


def mask_key(key):
    """Return a redacted fingerprint of an API key (never the full secret).

    Only the first 4 and last 4 characters are kept; the middle is masked.
    Empty/invalid input returns an empty string. This prevents leaking real
    Gemini keys into on-disk metadata while keeping the value identifiable.
    """
    if not key or not isinstance(key, str):
        return ""
    key = key.strip()
    if len(key) <= 8:
        return "*" * len(key)
    return f"{key[:4]}{'*' * (len(key) - 8)}{key[-4:]}"

INPUT_DIR = Path(os.environ.get("INPUT_DIR", "/home/pxtkhw/projetos/obitos/output/full_images/tiff"))
OUTPUT_DIR = Path(os.environ.get("OUTPUT_DIR", "/home/pxtkhw/projetos/obitos/output/htr_text"))
METADATA_DIR = Path(os.environ.get("METADATA_DIR", "/home/pxtkhw/projetos/obitos/output/htr_metadata"))
LOG_FILE = Path(os.environ.get("LOG_FILE", "/home/pxtkhw/projetos/obitos/output/htr_cloud_v2.log"))
STATE_FILE = Path(os.environ.get("STATE_FILE", "/home/pxtkhw/projetos/obitos/output/htr_cloud_v2_state.json"))
OUTPUT_PARENT = OUTPUT_DIR.parent
DATA_DIR = Path(os.environ.get("DATA_DIR", str(OUTPUT_PARENT / "data")))
# Page listings + inventory feed the record-type (BIRT/MARR/DEAT) of each TIFF.
DOC_FILE_LISTINGS = Path(os.environ.get("DOC_FILE_LISTINGS", str(DATA_DIR / "doc_file_listings.json")))
INVENTARIO_JSON = Path(os.environ.get("INVENTARIO_JSON", str(OUTPUT_PARENT / "obitos_inventario.json")))

GEMINI_KEYS = os.environ.get("GEMINI_KEYS", "")
GEMINI_KEYS = [k.strip() for k in GEMINI_KEYS.split(",") if k.strip()]

GEMINI_MODELS = os.environ.get("GEMINI_MODELS", "gemini-3-flash-preview,gemini-2.5-flash").split(",")
GEMINI_MODELS = [m.strip() for m in GEMINI_MODELS if m.strip()]

MAX_IMAGE_WIDTH = int(os.environ.get("MAX_IMAGE_WIDTH", "1500"))
JPEG_QUALITY = int(os.environ.get("JPEG_QUALITY", "80"))
CONCURRENT_REQUESTS = max(1, int(os.environ.get("CONCURRENT_REQUESTS", "1")))

# Limites free tier da API Gemini (confirmados pelo utilizador, Google AI Studio):
#   Por CHAVE e por MODELO.  RPD = pedidos/dia; RPM = pedidos/min; TPM = tokens entrada/min.
#   Gemini 2.5 Flash      : RPD 20  RPM 5   TPM 250K
#   Gemini 3 Flash        : RPD 20  RPM 5   TPM 250K
#   Gemini 3.5 Flash      : RPD 20  RPM 5   TPM 250K
#   Gemini 3.6 Flash      : RPD 20  RPM 5   TPM 250K
#   Gemini 3.7 Flash      : RPD 20  RPM 5   TPM 250K
#   Gemini 3.5 Flash Lite : RPD 500 RPM 15 TPM 250K
#   Gemini 3.1 Flash Lite : RPD 500 RPM 15 TPM 250K
# TPM não é pacial ativamente (imagens pequenas + ritmo calmo mantêm bem abaixo de 250K/min).
KEY_INTERVAL = float(os.environ.get("KEY_INTERVAL", "4320"))
RPM_INTERVAL = float(os.environ.get("RPM_INTERVAL", "12"))

# RPD por MODELO (pedidos/dia/chave). 86400/RPD = intervalo seguro por (chave,modelo).
# O lite usa 300s (~288/dia, ~58% do limite 500) por decisão de ritmo calmo.
MODEL_INTERVAL = {
    "gemini-3-flash-preview": 4320,   # RPD 20
    "gemini-2.5-flash": 4320,         # RPD 20
    "gemini-3.5-flash-lite": 300,     # RPD 500 (calmo: 288/dia)
    "gemini-3.1-flash-lite": 300,     # RPD 500 (calmo: 288/dia)
    "gemini-3.6-flash": 4320,         # RPD 20
    "gemini-3.7-flash": 4320,         # RPD 20
}
# RPD free tier por MODELO (usado para preferir o modelo com mais quota livre).
MODEL_RPD = {
    "gemini-3-flash-preview": 20,
    "gemini-2.5-flash": 20,
    "gemini-3.5-flash-lite": 500,
    "gemini-3.1-flash-lite": 500,
    "gemini-3.6-flash": 20,
    "gemini-3.7-flash": 20,
}
# Intervalo RPM (s) por MODELO = 60 / RPM. Fallback RPM_INTERVAL (12s = 5/min).
MODEL_RPM_INTERVAL = {
    "gemini-3-flash-preview": 12,     # RPM 5
    "gemini-2.5-flash": 12,           # RPM 5
    "gemini-3.6-flash": 12,           # RPM 5
    "gemini-3.7-flash": 12,           # RPM 5
    "gemini-3.5-flash-lite": 5,       # RPM 15 (5s = 12/min, folga)
    "gemini-3.1-flash-lite": 5,       # RPM 15
}
# TPM (tokens entrada/min) por MODELO — documentação; não pacial ativamente.
MODEL_TPM = {
    "gemini-3-flash-preview": 250000,
    "gemini-2.5-flash": 250000,
    "gemini-3.5-flash-lite": 250000,
    "gemini-3.1-flash-lite": 250000,
    "gemini-3.6-flash": 250000,
    "gemini-3.7-flash": 250000,
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("htr_cloud_v2")

def parse_gemini_json(text):
    """Best-effort parse of the model JSON response.

    The prompt asks for `{"transcription": ..., "deceased": [...]}`, but the
    model sometimes wraps it in ```json fences or adds chatter. Returns the
    parsed dict, or None if no valid JSON object is found.
    """
    if not text:
        return None
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```[a-zA-Z]*\n?", "", t)
        t = re.sub(r"```\s*$", "", t).strip()
    start = t.find("{")
    end = t.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    frag = t[start:end + 1]
    try:
        obj = json.loads(frag)
    except json.JSONDecodeError:
        return None
    if not isinstance(obj, dict):
        return None
    return obj


PROMPT_BY_TYPE = {
    "DEAT": """You are a transcription assistant for Portuguese historical documents.
This image shows a page from a death register (livro de óbitos) from Celorico da Beira, Portugal.
Output ONLY a JSON object (no other text) with this structure:
{
  "transcription": "full transcribed text here",
  "deceased": [ { "name": "...", "death_date": "YYYY-MM-DD", "age": "...", "father": "...", "mother": "...", "spouse": "..." } ]
}
If you cannot read something, use [ilegível]. Do NOT invent content. Output ONLY the JSON.""",
    "BIRT": """You are a transcription assistant for Portuguese historical documents.
This image shows a page from a birth/baptism register (livro de nascimentos/batismos) from Celorico da Beira, Portugal.
Output ONLY a JSON object (no other text) with this structure:
{
  "transcription": "full transcribed text here",
  "persons": [ { "name": "nome do recém-nascido", "birth_date": "YYYY-MM-DD", "father": "...", "mother": "...", "godfather": "...", "godmother": "..." } ]
}
If you cannot read something, use [ilegível]. Do NOT invent content. Output ONLY the JSON.""",
    "MARR": """You are a transcription assistant for Portuguese historical documents.
This image shows a page from a marriage register (livro de casamentos) from Celorico da Beira, Portugal.
Output ONLY a JSON object (no other text) with this structure:
{
  "transcription": "full transcribed text here",
  "persons": [ { "name": "cônjuge 1", "marriage_date": "YYYY-MM-DD", "spouse": "cônjuge 2", "father": "...", "mother": "...", "spouse_father": "...", "spouse_mother": "..." } ]
}
If you cannot read something, use [ilegível]. Do NOT invent content. Output ONLY the JSON.""",
}
# Default record type when a file_id cannot be resolved to a book type. All
# currently downloaded TIFFs are óbitos (DEAT); defaulting to DEAT preserves the
# existing, tested behaviour exactly (no regression) while keeping BIRT/MARR
# ready: adding their page listings to doc_file_listings activates them with no
# further code change.
DEFAULT_RECORD_TYPE = "DEAT"


def build_type_map():
    """Build {file_id: tipo_cod} from page listings joined with the inventory.

    - doc_file_listings.json maps doc_id (hash) -> list of pages; each page has a
      numeric `id` (the digitarq fileId that names the downloaded TIFF) and a
      `name` (book title + series suffix).
    - obitos_inventario.json maps each book (by doc_id hash found in url_info)
      to its tipo_cod (BIRT/MARR/DEAT). This is the canonical record type.
    Unmapped file_ids (e.g. listings not yet fetched for nascimentos/casamentos)
    resolve to DEFAULT_RECORD_TYPE (DEAT) so the death pipeline keeps its exact
    behaviour. Returns {} if source files are missing (safe degradation, no
    exception, no rutura).
    """
    type_map = {}
    try:
        with open(INVENTARIO_JSON, encoding="utf-8") as f:
            inv = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        inv = []
    inv_tipo = {}
    if isinstance(inv, list):
        for r in inv:
            m = re.search(r"documentDetails/([0-9a-fA-F]+)", r.get("url_info", ""))
            if m:
                inv_tipo[m.group(1).lower()] = r.get("tipo_cod", DEFAULT_RECORD_TYPE)
    try:
        with open(DOC_FILE_LISTINGS, encoding="utf-8") as f:
            listings = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        listings = {}
    if isinstance(listings, dict):
        for doc_id, pages in listings.items():
            if not isinstance(pages, list):
                continue
            tipo = inv_tipo.get(str(doc_id).lower(), DEFAULT_RECORD_TYPE)
            for p in pages:
                fid = str(p.get("id", ""))
                if fid:
                    type_map[fid] = tipo
    return type_map


class KeyHealth:
    """Tracks health of each API key/model combo"""
    def __init__(self, key, model):
        self.key = key
        self.model = model
        self.success_count = 0
        self.error_count = 0
        self.last_success = 0
        self.last_error = 0
        self.blocked_until = 0
        self.consecutive_errors = 0
        self.lock = threading.Lock()

    @property
    def health_score(self):
        if self.success_count + self.error_count == 0:
            return 1.0
        return self.success_count / (self.success_count + self.error_count + 1)

    def mark_success(self):
        with self.lock:
            self.success_count += 1
            self.last_success = time.time()
            self.consecutive_errors = 0

    def mark_error(self, is_rate_limit=False):
        with self.lock:
            self.error_count += 1
            self.last_error = time.time()
            self.consecutive_errors += 1

    def block(self, seconds):
        with self.lock:
            self.blocked_until = time.time() + seconds

    @property
    def is_available(self):
        return time.time() > self.blocked_until


class HTRProcessor:
    def __init__(self):
        self.shutdown_requested = False
        self.key_health = {}
        self.global_success = 0
        self.global_errors = 0
        self.state = self.load_state()
        # Record-type (BIRT/MARR/DEAT) per file_id, joined from page listings +
        # inventory. Drives which prompt is used and is written to the output
        # for downstream consumers (sync). Defaults to DEAT when unresolvable.
        self.type_map = build_type_map()
        log.info(f"Loaded type map: {len(self.type_map)} file_ids mapped "
                 f"({sum(1 for v in self.type_map.values() if v == 'DEAT')} DEAT, "
                 f"{sum(1 for v in self.type_map.values() if v == 'BIRT')} BIRT, "
                 f"{sum(1 for v in self.type_map.values() if v == 'MARR')} MARR).")
        # Per-(key,model) pacing (RPD) and per-model pacing (RPM).
        self.combo_last = {(k, m): 0.0 for k in GEMINI_KEYS for m in GEMINI_MODELS}
        self.combo_locks = {(k, m): threading.Lock() for k in GEMINI_KEYS for m in GEMINI_MODELS}
        self.model_last = {m: 0.0 for m in GEMINI_MODELS}
        self.model_locks = {m: threading.Lock() for m in GEMINI_MODELS}
        self.state_lock = threading.Lock()
        # Health/quota tracking
        self.dead_combos = set()          # (key,model) com 400/404 -> inútil para sempre
        self.daily_exhausted = {}         # (key,model) -> timestamp de revival (quota diária)
        self.daily_count = {}             # (key,model) -> nº de sucessos hoje
        self.consecutive_429 = {}         # (key,model) -> 429 seguidos
        self.model_used = {}              # model -> nº total de selecções (balancear lites)
        self.today = datetime.now().strftime("%Y-%m-%d")

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

    def acquire_combo(self, key, model):
        """Pace a request: respect per-model RPM and per-(key,model) RPD."""
        rpd_interval = MODEL_INTERVAL.get(model, KEY_INTERVAL)
        rpm_interval = MODEL_RPM_INTERVAL.get(model, RPM_INTERVAL)
        # Per-model global RPM pacing (short spacing).
        mlock = self.model_locks.get(model)
        if mlock is not None:
            with mlock:
                wait = rpm_interval - (time.time() - self.model_last[model])
                if wait > 0:
                    time.sleep(wait)
                self.model_last[model] = time.time()
        # Per-(key,model) RPD pacing (long spacing).
        clock = self.combo_locks.get((key, model))
        if clock is not None:
            with clock:
                wait = rpd_interval - (time.time() - self.combo_last[(key, model)])
                if wait > 0:
                    time.sleep(wait)
                self.combo_last[(key, model)] = time.time()

    def _maybe_reset_daily(self):
        today = datetime.now().strftime("%Y-%m-%d")
        if today != self.today:
            self.today = today
            self.daily_count = {}
            self.daily_exhausted = {}
            self.consecutive_429 = {}
            log.info("Reset diário de contadores de quota.")

    def _next_midnight(self):
        now = datetime.now()
        nm = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        return nm.timestamp()

    def _is_exhausted(self, combo):
        rev = self.daily_exhausted.get(combo)
        if rev is None:
            return False
        if time.time() >= rev:
            self.daily_exhausted.pop(combo, None)
            self.daily_count.pop(combo, None)
            self.consecutive_429.pop(combo, None)
            return False
        return True

    def get_healthy_key(self, key_hint=None):
        """Get the healthiest available key/model combo.

        - Exclui combos mortos (400/404) e esgotados (quota diária).
        - Prefere a chave hint (espalha ficheiros por chaves).
        - Dentro da chave, prefere o modelo MENOS usado hoje (usa os 2 modelos).
        """
        self._maybe_reset_daily()
        candidates = []
        for key in GEMINI_KEYS:
            for model in GEMINI_MODELS:
                combo = (key, model)
                if combo in self.dead_combos:
                    continue
                if self._is_exhausted(combo):
                    continue
                if combo not in self.key_health:
                    self.key_health[combo] = KeyHealth(key, model)
                kh = self.key_health[combo]
                if kh.is_available:
                    candidates.append(kh)

        if not candidates:
            earliest = float('inf')
            for rev in self.daily_exhausted.values():
                if rev > time.time() and rev < earliest:
                    earliest = rev
            for kh in self.key_health.values():
                if kh.blocked_until > time.time() and kh.blocked_until < earliest:
                    earliest = kh.blocked_until
            if earliest == float('inf'):
                earliest = time.time() + 60
            wait = max(earliest - time.time(), 0) + 2
            log.warning(f"All combos unavailable. Waiting {wait:.0f}s...")
            time.sleep(wait)
            return self.get_healthy_key()

        def sortkey(kh):
            combo = (kh.key, kh.model)
            hint_first = 0 if (key_hint is not None and kh.key == key_hint) else 1
            used = self.daily_count.get(combo, 0)
            # Prefere o modelo com MAIS quota diária livre (evita martelar
            # modelos esgotados que só devolvem 429, roubando workers ao lite).
            remaining = MODEL_RPD.get(kh.model, 20) - used
            # Entre modelos com quota igual (ex.: os dois flash-lite RPD 500),
            # prefere o modelo MENOS usado no total (balanceia a carga).
            model_used = self.model_used.get(kh.model, 0)
            return (hint_first, -remaining, model_used, -kh.health_score, -kh.last_success)

        candidates.sort(key=sortkey)
        chosen = candidates[0]
        self.model_used[chosen.model] = self.model_used.get(chosen.model, 0) + 1
        return chosen

    def call_gemini(self, img_b64, preferred_key=None, prompt=None):
        """Call Gemini API with circuit breaker pattern"""
        # Select the record-type prompt (death by default).
        prompt = prompt or PROMPT_BY_TYPE["DEAT"]
        attempt = 0
        max_attempts = 5

        while attempt < max_attempts:
            kh = self.get_healthy_key(preferred_key)
            key, model = kh.key, kh.model
            combo = (key, model)

            # Respect the per-(key,model) free-tier spacing before sending.
            self.acquire_combo(key, model)

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
                    self.daily_count[combo] = self.daily_count.get(combo, 0) + 1
                    self.consecutive_429[combo] = 0
                    return {"status": "success", "text": text, "model": model, "key": key}

            except urllib.error.HTTPError as e:
                body = e.read().decode()[:200] if e.fp else ""

                if e.code == 429:
                    log.warning(f"Rate limit 429 for ...{key[-6:]} model {model}")
                    kh.mark_error(is_rate_limit=True)
                    self.consecutive_429[combo] = self.consecutive_429.get(combo, 0) + 1
                    self.daily_count[combo] = self.daily_count.get(combo, 0) + 1
                    # Só marca esgotado (quota diária) se: 2+ 429 seguidos E já
                    # usou ~80% do RPD. 429 isolado (ex.: RPM) não desativa o
                    # combo — isso evita desligar o lite (RPD 500) por erro de RPM.
                    rpd = MODEL_RPD.get(model, 20)
                    if self.consecutive_429[combo] >= 2 and self.daily_count[combo] >= 0.8 * rpd:
                        self.daily_exhausted[combo] = self._next_midnight()
                        log.warning(f"Quota diária esgotada ...{key[-6:]} {model}; salta até à meia-noite.")
                    kh.block(120)
                elif e.code in (400, 404):
                    # Chave inválida (400) ou modelo indisponível (404): morto para sempre.
                    log.error(f"HTTP {e.code} (combo morto) ...{key[-6:]} {model}: {body[:80]}")
                    self.dead_combos.add(combo)
                    kh.mark_error()
                    attempt += 1
                    time.sleep(5)
                    continue
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

        # Atribui uma chave estável por ficheiro para espalhar a carga por
        # várias chaves em paralelo (fallback para a mais saudável se bloqueada).
        preferred_key = None
        if GEMINI_KEYS:
            preferred_key = GEMINI_KEYS[abs(hash(file_id)) % len(GEMINI_KEYS)]

        # Pick the prompt for this record type (BIRT/MARR/DEAT). Falls back to
        # DEAT for unmapped file_ids, preserving the existing death behaviour.
        record_type = self.type_map.get(file_id, DEFAULT_RECORD_TYPE)
        prompt = PROMPT_BY_TYPE.get(record_type, PROMPT_BY_TYPE["DEAT"])

        try:
            img_b64 = self.prepare_image(tiff_path)
            result = self.call_gemini(img_b64, preferred_key, prompt=prompt)
            elapsed = time.time() - start

            parsed = parse_gemini_json(result.get("text", ""))
            transcription = parsed.get("transcription") if parsed else None
            deceased = parsed.get("deceased") if parsed else None

            metadata = {
                "file_id": file_id,
                "status": result["status"],
                "model": result.get("model", ""),
                "key": mask_key(result.get("key", "")),
                "text_length": len(result.get("text", "")),
                "record_type": record_type,
                "parsed_ok": parsed is not None,
                "wall_time_s": elapsed,
                "processed_at": datetime.now().isoformat(),
            }

            output_data = {
                "file_id": file_id,
                "record_type": record_type,
                "raw_text": result.get("text", ""),
                "transcription": transcription,
                "deceased": deceased,
                "parsed_ok": parsed is not None,
            }

            with open(OUTPUT_DIR / f"{file_id}.json", "w", encoding="utf-8") as f:
                json.dump(output_data, f, indent=2, ensure_ascii=False, default=str)

            with open(METADATA_DIR / f"{file_id}.json", "w", encoding="utf-8") as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False, default=str)

            with self.state_lock:
                self.state["processed"] += 1
                self.state["total_time"] += elapsed
                self.state["last_file"] = file_id
                if result["status"] == "error":
                    self.state["errors"] += 1
                self.save_state()

            log.info(f"[{self.state['processed']}] {file_id}: {result['status']} ({elapsed:.1f}s, {metadata['text_length']} chars)")

            if self.state["processed"] % 25 == 0:
                total_combos = len(GEMINI_KEYS) * len(GEMINI_MODELS)
                vivos = total_combos - len(self.dead_combos) - len(self.daily_exhausted)
                log.info(f"[STATUS] processados={self.state['processed']} combos_vivos={vivos} mortos={len(self.dead_combos)} esgotados_hoje={len(self.daily_exhausted)}")

        except Exception as e:
            log.error(f"[ERROR] {file_id}: {e}")
            with self.state_lock:
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

        log.info(f"=== HTR V2 Started: {len(processed)}/{len(tiff_files)} done, {len(to_process)} remaining ===")
        log.info(f"Concurrent mode: workers={CONCURRENT_REQUESTS}, key_interval={KEY_INTERVAL}s, keys={len(GEMINI_KEYS)}, models={len(GEMINI_MODELS)}")

        if not to_process:
            log.info("All done!")
            return

        try:
            with ThreadPoolExecutor(max_workers=CONCURRENT_REQUESTS) as ex:
                list(ex.map(self.process_single, to_process))
        except Exception as e:
            log.error(f"Executor error: {e}")

        log.info(f"=== Done: {self.state['processed']} processed, {self.state['errors']} errors ===")


if __name__ == "__main__":
    processor = HTRProcessor()
    processor.run()
