#!/usr/bin/env python3
"""Backfill os campos ricos de casamento (dispensa, testemunhas, legitimacao)
nas linhas MARR já sincronizadas antes da migração add_marr_casamentos.sql.

Reusa a extração estruturada do sync (extract_persons_from_marriages) e faz
PATCH por (file_id, nome, conjuge). Idempotente: pode correr várias vezes.

Run:  python3 scripts/backfill_marr_rich.py
"""

import json
import os
import sys
import time
import glob
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from sync_htr_supabase import extract_persons_from_marriages

RICH_COLS = ("dispensa", "testemunhas", "legitimacao")
sleep_counter = 0


def load_env():
    env = {}
    for line in open(os.path.join(ROOT, ".env")):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env[k] = v
    return env


ENV = load_env()
URL = ENV["SUPABASE_URL"]
KEY = ENV.get("SUPABASE_SECRET_KEY") or ENV.get("SUPABASE_KEY")


def patch_row(filter_qs, body):
    for attempt in range(3):
        try:
            req = urllib.request.Request(
                URL + "/rest/v1/pessoas?" + filter_qs,
                data=json.dumps(body).encode(),
                headers={
                    "apikey": KEY,
                    "Authorization": "Bearer " + KEY,
                    "Content-Type": "application/json",
                    "Prefer": "return=representation,count=exact",
                },
                method="PATCH",
            )
            with urllib.request.urlopen(req) as r:
                payload = r.read().decode()
                try:
                    matched = json.loads(payload)
                    return (r.status, len(matched))
                except Exception:
                    return (r.status, 0)
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(2.0 * (attempt + 1))
                continue
            return (e.code, 0)
        except Exception:
            time.sleep(1.0 * (attempt + 1))
    return (500, 0)


def match_patch(args):
    file_id, nome, sobrenome, conjuge, rich = args
    params = [
        ("file_id", "eq", file_id),
        ("nome", "eq", nome),
        ("conjuge", "eq", conjuge) if conjuge else None,
    ]
    params = [p for p in params if p is not None and p[2]]
    qs = "&".join(
        f"{k}={op}.{urllib.parse.quote(v)}" if op else f"{k}={urllib.parse.quote(v)}"
        for k, op, v in params
    )
    code, matched = patch_row(qs, rich)
    return (code in (200, 204), code, matched)


def main():
    tasks = []
    structured_files = 0
    for fp in glob.glob(os.path.join(ROOT, "output", "htr_text", "*.json")):
        try:
            with open(fp) as f:
                data = json.load(f)
        except Exception:
            continue
        persons = data.get("persons")
        is_marr = data.get("record_type") == "MARR" or (
            isinstance(persons, list)
            and any(isinstance(p, dict) and (p.get("name") or p.get("nome")) for p in persons)
        )
        if not is_marr:
            continue
        try:
            extracted = extract_persons_from_marriages(persons)
        except Exception:
            continue
        if not extracted:
            continue
        structured_files += 1
        file_id = data.get("file_id") or os.path.basename(fp)[:-5]
        for p in extracted:
            rich = {}
            for col in RICH_COLS:
                v = p.get(col)
                if v not in (None, ""):
                    rich[col] = v
            if not rich:
                continue
            tasks.append((file_id, p.get("nome", ""), p.get("sobrenome", ""), p.get("conjuge", ""), rich))

    print(f"Ficheiros MARR com persons estruturados: {structured_files}")
    print(f"PATCHes a tentar (apenas com campos ricos): {len(tasks)}")
    if not tasks:
        print("Nada para backfill.")
        return

    done = 0
    ok = 0
    matched_total = 0
    start = time.time()
    with ThreadPoolExecutor(max_workers=8) as ex:
        for success, code, matched in ex.map(match_patch, tasks):
            done += 1
            if success:
                ok += 1
                matched_total += matched
            if done % 500 == 0 or done == len(tasks):
                el = time.time() - start
                print(f"Progresso: {done}/{len(tasks)} (ok: {ok}, linhas: {matched_total}, PATCHes/min: {ok/el*60:.0f})")

    print(f"\n=== Backfill completo ===")
    print(f"PATCHes: {ok}/{len(tasks)} ok (linhas atualizadas: {matched_total}) em {time.time()-start:.0f}s")


if __name__ == "__main__":
    main()