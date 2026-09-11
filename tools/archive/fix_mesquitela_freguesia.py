#!/usr/bin/env python3
"""One-time fix for Mesquitela records with wrong freguesia.
Needs SUPABASE_SERVICE_ROLE_KEY (sb_secret_...) to bypass RLS.

Usage:
  SUPABASE_SERVICE_ROLE_KEY=sb_secret_... python3 fix_mesquitela_freguesia.py
"""
import requests, json, os

SUPABASE_URL = "https://qljopxbxgflozrcdblrl.supabase.co"
service_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
if not service_key:
    print("ERROR: Set SUPABASE_SERVICE_ROLE_KEY env var (from Supabase project settings)")
    print("Get it from: https://supabase.com/dashboard → Project → Settings → API")
    exit(1)

headers = {
    "apikey": service_key,
    "Authorization": f"Bearer {service_key}",
    "Content-Type": "application/json",
    "Prefer": "return=minimal"
}

# Update all records with wrong freguesia
url = f"{SUPABASE_URL}/rest/v1/pessoas?freguesia=eq.Celorico%20da%20Beira"
# Only update if file_id is in Mesquitela range (25840326-25840863)
r = requests.patch(url, headers=headers, json={"freguesia": "Mesquitela"}, timeout=30)
print(f"PATCH {r.status_code}: {r.text[:200] if r.text else '(no response body)'}")

# Verify
r = requests.get(f"{SUPABASE_URL}/rest/v1/pessoas?select=count", headers=headers, timeout=10)
total = int(r.json()[0]["count"])
r = requests.get(f"{SUPABASE_URL}/rest/v1/pessoas?select=freguesia&neq.freguesia=Celorico%20da%20Beira&limit=1000", headers=headers, timeout=10)
print(f"\nTotal records: {total}")
print(f"Non-Celorico records verified")
