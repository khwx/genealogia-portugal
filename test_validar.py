"""
Testa as rotas /validar e /api/validar após adicionar as colunas
qualidade (numeric) e validado (boolean) à tabela pessoas no Supabase.
"""
import os
import sys
import json
from dotenv import load_dotenv

load_dotenv()

# 1) Verifica se as colunas existem no Supabase
import requests

SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY')
H = {'apikey': SUPABASE_KEY, 'Authorization': f"Bearer {SUPABASE_KEY}"}

print("=== 1) Verificar colunas no Supabase ===")
r = requests.get(f"{SUPABASE_URL}/rest/v1/pessoas?select=qualidade,validado&limit=1",
                 headers=H, timeout=30)
if r.status_code == 200:
    print("OK: colunas qualidade/validado existem ->", r.json())
else:
    print("FALHA:", r.status_code, r.json())
    sys.exit(1)

# 2) Testa as rotas via Flask test_client
print("\n=== 2) Testar rotas Flask ===")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'api'))
import importlib.util
spec = importlib.util.spec_from_file_location('api_index', 'api/index.py')
api = importlib.util.module_from_spec(spec)
spec.loader.exec_module(api)
client = api.app.test_client()

r = client.get('/validar')
print("GET /validar ->", r.status_code)

# obter um id para validar
r = client.get('/api/pessoas?limit=1')
p = r.get_json()
pid = p[0]['id'] if p else None
print("GET /api/pessoas ->", r.status_code, "id amostra:", pid)

if pid is not None:
    r = client.post('/api/validar', json={'id': pid, 'nome': 'TESTE'})
    print("POST /api/validar ->", r.status_code, r.get_json())
    # confirmar no Supabase
    r = requests.get(f"{SUPABASE_URL}/rest/v1/pessoas?id=eq.{pid}&select=id,qualidade,validado",
                     headers=H, timeout=30)
    print("Verificação DB ->", r.json())
