#!/usr/bin/env python3
"""Avalia e remove duplicados das 88 (criados por 2 syncs concorrentes)."""
import json
import os
import sys
import urllib.request
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

env = {}
for line in open(os.path.join(ROOT, ".env")):
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, v = line.split("=", 1)
        env[k] = v
K = env.get("SUPABASE_SECRET_KEY") or env.get("SUPABASE_KEY")
URL = env["SUPABASE_URL"]

man = [l.strip() for l in open("/tmp/retry88.txt") if l.strip()]

rows = []
off = 0
while True:
    q = ("/rest/v1/pessoas?select=id,file_id,nome,sobrenome,data_nascimento,pai,mae"
         "&file_id=in.(" + ",".join(man) + f")&limit=500&offset={off}&order=id.asc")
    req = urllib.request.Request(URL + q, headers={"apikey": K, "Authorization": "Bearer " + K})
    try:
        b = json.load(urllib.request.urlopen(req, timeout=120))
    except Exception as e:
        print(f"ERRO fetch offset {off}: {e}", flush=True)
        sys.exit(1)
    rows += b
    print(f"buscados: {len(rows)}", flush=True)
    if len(b) < 500:
        break
    off += 500

g = defaultdict(list)
for x in rows:
    g[(x["file_id"], x.get("nome"), x.get("sobrenome"),
       x.get("data_nascimento"), x.get("pai"), x.get("mae"))].append(x["id"])
dup = [i for v in g.values() for i in sorted(v)[1:]]
print(f"linhas: {len(rows)} grupos: {len(g)} DUPLICADAS: {len(dup)}", flush=True)
json.dump(dup, open("/tmp/dup_ids.json", "w"))
print("OK ids em /tmp/dup_ids.json", flush=True)
