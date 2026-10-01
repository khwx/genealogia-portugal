#!/usr/bin/env python3
"""Retry em lote das 88 páginas BIRT 'retry_exhausted' (manchadas/difíceis)
com prompt leve — mesma técnica dos resgates manuais (MARR fragmentos, BIRT 25841965).

Lê docs/manual_retry_list.md, para cada fid: fetch imagem Digitarq, prompt
simples (transcription + baptized), guarda output/htr_text/<fid>.json com
record_type BIRT. Idempotente: salta fids que já tenham baptized.

Run:  python3 scripts/retry_manual88.py
"""

import base64
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PROMPT = (
    "Transcreve TODO o texto manuscrito desta página de registo de batismo "
    "português e extrai os batizados, mesmo que a página esteja manchada ou "
    "parcialmente ilegível — transcreve o que conseguires ler. "
    "Devolve SÓ JSON: {\"transcription\": \"...texto...\", \"baptized\": "
    "[{\"name\": \"...\", \"father\": \"...\", \"mother\": \"...\", "
    "\"birth_date\": \"...\", \"baptism_date\": \"...\"}]}"
)


def load_env():
    env = {}
    for line in open(os.path.join(ROOT, ".env")):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env[k] = v
    return env


ENV = load_env()
KEYS = [k.strip() for k in ENV.get("GEMINI_KEYS", "").split(",") if k.strip()]
MODEL = "gemini-3.5-flash-lite"


def read_retry_list():
    fids = []
    for line in open(os.path.join(ROOT, "docs", "manual_retry_list.md")):
        m = re.search(r"\|\s*BIRT\s*\|\s*(\d+)", line)
        if m:
            fids.append(m.group(1))
    return fids


def fetch_b64(fid):
    url = f"https://digitarq.arquivos.pt/rdigital/dissemination?fileId={fid}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    img = Image.open(BytesIO(urllib.request.urlopen(req, timeout=25).read()))
    img.load()
    if img.mode != "RGB":
        img = img.convert("RGB")
    if img.width > 1500:
        ratio = 1500 / img.width
        img = img.resize((int(img.width * ratio), int(img.height * ratio)), Image.Resampling.LANCZOS)
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=80)
    return base64.b64encode(buf.getvalue()).decode()


def already_structured(fid):
    p = os.path.join(ROOT, "output", "htr_text", fid + ".json")
    if not os.path.exists(p):
        return False
    try:
        d = json.load(open(p))
    except Exception:
        return False
    ps = d.get("baptized")
    return isinstance(ps, list) and any(
        isinstance(x, dict) and (x.get("name") or x.get("nome")) for x in ps
    )


def try_keys(b64):
    last = None
    for ki, key in enumerate(KEYS[:8]):
        payload = {
            "contents": [{
                "parts": [
                    {"text": PROMPT},
                    {"inline_data": {"mime_type": "image/jpeg", "data": b64}},
                ]
            }],
            "generationConfig": {"temperature": 0.1, "maxOutputTokens": 8192},
        }
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{MODEL}:generateContent?key={key}"
        )
        try:
            req = urllib.request.Request(
                url, data=json.dumps(payload).encode(),
                headers={"Content-Type": "application/json"},
            )
            res = json.loads(urllib.request.urlopen(req, timeout=60).read().decode())
            return res["candidates"][0]["content"]["parts"][0]["text"], None
        except urllib.error.HTTPError as e:
            last = f"HTTP {e.code}"
            time.sleep(3 if e.code == 429 else 0.5)
        except Exception as e:
            last = f"{type(e).__name__}"
            time.sleep(1.0)
    return None, last


def parse_out(txt):
    if not txt:
        return None
    s = txt.strip()
    if s.startswith("```"):
        s = re.sub(r"^```[a-zA-Z]*\n?", "", s)
        s = re.sub(r"```\s*$", "", s).strip()
    a, b = s.find("{"), s.rfind("}")
    if a == -1 or b == -1:
        return None
    try:
        return json.loads(s[a:b + 1])
    except Exception:
        return None


def process(fid):
    if already_structured(fid):
        return fid, "ja-estruturado", 0
    try:
        b64 = fetch_b64(fid)
    except Exception as e:
        return fid, f"fetch-fail {type(e).__name__}", 0
    txt, err = try_keys(b64)
    pj = parse_out(txt)
    if not pj:
        return fid, f"gemini-fail {err}", 0
    nb = len(pj.get("baptized") or [])
    out = {
        "file_id": fid,
        "record_type": "BIRT",
        "model": MODEL + "-retry88",
        "raw_text": txt,
        "transcription": pj.get("transcription"),
        "baptized": pj.get("baptized") or [],
        "parsed_ok": True,
    }
    with open(os.path.join(ROOT, "output", "htr_text", fid + ".json"), "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    return fid, "ok", nb


def main():
    fids = read_retry_list()
    print(f"Lista: {len(fids)} fids")
    todo = [f for f in fids if not already_structured(f)]
    print(f"Por fazer: {len(todo)}")
    ok = nb = 0
    fails = []
    with ThreadPoolExecutor(max_workers=3) as ex:
        for i, (fid, status, n) in enumerate(ex.map(process, todo)):
            if status == "ok":
                ok += 1
                nb += n
            else:
                fails.append((fid, status))
            if (i + 1) % 10 == 0 or (i + 1) == len(todo):
                print(f"Progresso: {i+1}/{len(todo)} (ok: {ok}, batizados: {nb}, falhas: {len(fails)})", flush=True)
    print(f"\n=== Retry88 completo: {ok}/{len(todo)} ok, {nb} batizados ===")
    for fid, s in fails[:20]:
        print("  falha:", fid, s)


if __name__ == "__main__":
    main()
