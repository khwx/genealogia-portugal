#!/usr/bin/env python3
"""Worker DEAT sequencial — uma freguesia de cada vez, ritmo seguro.

Serve qualquer concelho com inventário + page listings:
  python3 output/workers/deat_tcs.py                      # Trancoso (tcs, default)
  python3 output/workers/deat_tcs.py --codigo pnh         # Pinhel

Usa as mesmas chaves do .env, prompt específico de Óbitos, e guarda em
output/htr_text_<codigo>/.
"""
import os, sys, json, base64, time, re, urllib.request, urllib.error
from pathlib import Path
from PIL import Image
from io import BytesIO

ROOT = Path(__file__).resolve().parent.parent.parent
for line in open(ROOT / ".env"):
    line = line.strip()
    if line and not line.startswith('#') and '=' in line:
        k, v = line.split('=', 1)
        os.environ[k.strip()] = v.strip()

def _arg_codigo():
    for i, a in enumerate(sys.argv[1:]):
        if a == "--codigo" and i + 2 <= len(sys.argv) - 1:
            return sys.argv[i + 2]
        if a.startswith("--codigo="):
            return a.split("=", 1)[1]
    return None

CODIGO = _arg_codigo() or os.environ.get("CONCELHO_CODIGO", "tcs")
_DEFAULT_INV = {"tcs": "trancoso_inventario.json", "pnh": "pinhel_inventario.json"}
INVENTORY_JSON = Path(os.environ.get(
    "INVENTORY_JSON",
    ROOT / "output" / _DEFAULT_INV.get(CODIGO, f"{CODIGO}_inventario.json")))
LISTINGS_JSON = Path(os.environ.get(
    "LISTINGS_JSON", ROOT / "output" / "data" / f"doc_file_listings_{CODIGO}.json"))

GEMINI_KEYS = [k.strip() for k in os.environ.get("GEMINI_KEYS", "").split(",") if k.strip()]
MODEL = "gemini-3.5-flash-lite"
OUTPUT_DIR = Path(os.environ.get("OUTPUT_DIR", ROOT / "output" / f"htr_text_{CODIGO}"))
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

KEY_DAILY_CAP = 300
USAGE_FILE = ROOT / "output" / "key_usage.json"
try:
    _usage = json.load(open(USAGE_FILE))
except Exception:
    _usage = {}

def _usage_today():
    today = time.strftime("%Y-%m-%d")
    return today, _usage.setdefault(today, {})

def key_over_cap(idx):
    _, u = _usage_today()
    return u.get(str(idx), 0) >= KEY_DAILY_CAP

def key_used(idx):
    today, u = _usage_today()
    u[str(idx)] = u.get(str(idx), 0) + 1
    for d in sorted(_usage.keys())[:-3]:
        del _usage[d]
    try:
        json.dump(_usage, open(USAGE_FILE, "w"))
    except Exception:
        pass

PROMPT_DEAT = """You are a paleography assistant for Portuguese parish marriage records (17th-19th century, public domain).
Transcribe the marriage record and extract structured data. Output ONLY valid JSON:
{
  "transcription": "brief summary of the record",
  "deceased": [
    {
      "name": "groom full name",
      "spouse": "bride full name",
      "marriage_date": "YYYY-MM-DD or null",
      "father": "groom father or null",
      "mother": "groom mother or null",
      "spouse_father": "bride father or null",
      "spouse_mother": "bride mother or null"
    }
  ]
}"""

with open(LISTINGS_JSON) as f:
    all_listings = json.load(f)
with open(INVENTORY_JSON) as f:
    inventory = json.load(f)

# Obter lista de freguesias de Óbitos
freguesias_deat = sorted(set(d.get('freguesia') for d in inventory if d.get('tipo_cod') == 'DEAT' and d.get('freguesia')))
print(f"[DEAT-{CODIGO.upper()}] freguesias de Óbitos: {len(freguesias_deat)} | saida: {OUTPUT_DIR}", flush=True)

def doc_ids_of(freguesia):
    return sorted(set(
        d["url_info"].split("documentDetails/")[1] for d in inventory
        if d.get("tipo_cod") == "DEAT" and d.get("freguesia") == freguesia
        and "documentDetails/" in d.get("url_info", "")))

key_idx = 0

def fetch_b64(fid):
    url = f"https://digitarq.arquivos.pt/rdigital/dissemination?fileId={fid}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        img_data = r.read()
    img = Image.open(BytesIO(img_data))
    if img.mode != "RGB":
        img = img.convert("RGB")
    if img.width > 1500:
        ratio = 1500 / img.width
        img = img.resize((int(img.width * ratio), int(img.height * ratio)), Image.Resampling.LANCZOS)
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=80)
    return base64.b64encode(buf.getvalue()).decode()

def parse_json(txt):
    if not txt:
        return None
    t = txt.strip()
    if t.startswith("```"):
        t = re.sub(r"^```[a-zA-Z]*\n?", "", t)
        t = re.sub(r"```\s*$", "", t).strip()
    s = t.find("{")
    e = t.rfind("}")
    if s == -1 or e == -1:
        return None
    try:
        return json.loads(t[s:e + 1])
    except:
        return None

def call_gemini(b64):
    global key_idx
    tried = 0
    for _ in range(len(GEMINI_KEYS)):
        if tried >= 6:
            break
        idx = key_idx % len(GEMINI_KEYS)
        key_idx += 1
        if key_over_cap(idx):
            continue
        tried += 1
        key = GEMINI_KEYS[idx]
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={key}"
        payload = {"contents": [{"parts": [{"text": PROMPT_DEAT}, {"inline_data": {"mime_type": "image/jpeg", "data": b64}}]}],
                   "generationConfig": {"temperature": 0.1, "maxOutputTokens": 8192},
                   "safetySettings": [{"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                                      {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                                      {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                                      {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}]}
        try:
            req = urllib.request.Request(url, data=json.dumps(payload).encode(),
                                         headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=10) as r:
                res = json.loads(r.read().decode())
                cand = res.get("candidates", [{}])[0]
                content = cand.get("content", {})
                parts = content.get("parts", [])
                if parts and "text" in parts[0]:
                    key_used(idx)
                    return parts[0]["text"]
                # Handle RECITATION or other finish reasons
                finish = cand.get("finishReason", "")
                if finish == "RECITATION":
                    print(f"      RECITATION blocked for key {idx}, trying next...", flush=True)
                return None
        except urllib.error.HTTPError as e:
            time.sleep(60 if e.code == 429 else 0.5)
        except Exception as e:
            time.sleep(1.0)
    return None

for freguesia in freguesias_deat:
    all_fids = []
    for doc_id in doc_ids_of(freguesia):
        if doc_id in all_listings:
            all_fids.extend([x["id"] for x in all_listings[doc_id]])
    already_done = set(f.stem for f in OUTPUT_DIR.glob("*.json"))
    todo = [fid for fid in all_fids if fid not in already_done]
    if not todo:
        continue
    print(f"\n[DEAT-{CODIGO.upper()}] {freguesia}: {len(all_fids)} total, {len(already_done)} done, {len(todo)} remaining", flush=True)

    done = 0
    errors = 0
    for i, fid in enumerate(todo):
        out = OUTPUT_DIR / f"{fid}.json"
        if out.exists():
            done += 1
            continue
        try:
            b64 = fetch_b64(fid)
            txt = call_gemini(b64)
            if not txt:
                print(f"      GEMINI_RETURNED_NONE for {fid}", flush=True)
            if txt:
                parsed = parse_json(txt)
                output = {"file_id": fid, "record_type": "DEAT", "model": MODEL, "raw_text": txt,
                          "transcription": parsed.get("transcription") if parsed else None,
                          "deceased": parsed.get("deceased") if parsed else [],
                          "parsed_ok": parsed is not None}
                with open(out, "w", encoding="utf-8") as f:
                    json.dump(output, f, ensure_ascii=False, indent=2)
                done += 1
            else:
                errors += 1
        except Exception as e:
            errors += 1
            print(f"      ERROR {fid}: {type(e).__name__}: {str(e)[:150]}", flush=True)
        if (i + 1) % 50 == 0:
            print(f"  [{i + 1}/{len(todo)}] done={done} errors={errors}", flush=True)
        time.sleep(6.0)  # Ritmo seguro 6s

    print(f"\nDone DEAT: {freguesia} {done}/{len(todo)} new, {errors} errors", flush=True)

print(f"\nTotal files in disco: {len(list(OUTPUT_DIR.glob('*.json')))}", flush=True)
