#!/usr/bin/env python3
"""Apaga os ids duplicados listados em /tmp/dup_ids.json."""
import json
import os
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
env = {}
for line in open(os.path.join(ROOT, ".env")):
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, v = line.split("=", 1)
        env[k] = v
K = env.get("SUPABASE_SECRET_KEY") or env.get("SUPABASE_KEY")
URL = env["SUPABASE_URL"]

ids = json.load(open("/tmp/dup_ids.json"))
print(f"A apagar: {len(ids)}", flush=True)


def delete_one(i):
    req = urllib.request.Request(
        f"{URL}/rest/v1/pessoas?id=eq.{i}",
        headers={"apikey": K, "Authorization": "Bearer " + K},
        method="DELETE",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status in (200, 204)
    except Exception:
        return False


ok = 0
with ThreadPoolExecutor(max_workers=8) as ex:
    for j, res in enumerate(ex.map(delete_one, ids)):
        ok += res
        if (j + 1) % 50 == 0 or (j + 1) == len(ids):
            print(f"Progresso: {j+1}/{len(ids)} (ok: {ok})", flush=True)
print(f"FEITO: {ok}/{len(ids)} apagados", flush=True)
