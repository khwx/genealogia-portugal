"""
Script para processar texto OCR com NVIDIA API.
Extrai nomes e datas de registos de óbitos.
"""
import requests
import json
import os
import time
import re

# Ler a chave do .env
def get_nvidia_key():
    with open('.env', 'r') as f:
        for line in f:
            if line.startswith('NVIDIA_API_KEY='):
                return line.strip().split('=', 1)[1]
    return None

NVIDIA_API_KEY = get_nvidia_key()
NVIDIA_URL = "https://integrate.api.nvidia.com/v1/chat/completions"

HEADERS = {
    "Authorization": f"Bearer {NVIDIA_API_KEY}",
    "Content-Type": "application/json"
}

# Meses em português
MESES = {
    "janeiro": "01", "janeiro": "01", "jan": "01",
    "fevereiro": "02", "fev": "02",
    "março": "03", "marco": "03", "mar": "03",
    "abril": "04", "abr": "04",
    "maio": "05", "mai": "05",
    "junho": "06", "jun": "06",
    "julho": "07", "jul": "07",
    "agosto": "08", "ago": "08",
    "setembro": "09", "set": "09",
    "outubro": "10", "out": "10",
    "novembro": "11", "nov": "11",
    "dezembro": "12", "dez": "12",
}

def normalize_date(date_str):
    """
    Converte '15 de Janeiro de 1864' para '1864-01-15'
    """
    if not date_str:
        return None
    
    date_str = date_str.lower().strip()
    
    # Tentar formato: DD de Mês de AAAA
    match = re.search(r'(\d{1,2})\s+de\s+(\w+)\s+de\s+(\d{4})', date_str)
    if match:
        day = match.group(1).zfill(2)
        month_name = match.group(2)
        year = match.group(3)
        month = MESES.get(month_name, "01")
        return f"{year}-{month}-{day}"
    
    # Tentar formato: DD/MM/AAAA
    match = re.search(r'(\d{1,2})/(\d{1,2})/(\d{4})', date_str)
    if match:
        day = match.group(1).zfill(2)
        month = match.group(2).zfill(2)
        year = match.group(3)
        return f"{year}-{month}-{day}"
    
    # Tentar formato: AAAA-MM-DD
    match = re.search(r'(\d{4})-(\d{2})-(\d{2})', date_str)
    if match:
        return date_str[:10]
    
    return None

def extract_names_from_ocr(ocr_text):
    """
    Extrai nomes e datas de texto OCR usando NVIDIA API.
    Retorna lista de dicionários com 'nome' e 'data_obito'.
    """
    if not ocr_text or not ocr_text.strip():
        return []
    
    payload = {
        "model": "meta/llama-3.1-8b-instruct",
        "messages": [
            {
                "role": "system",
                "content": """You are a Portuguese genealogy expert. Extract names and death dates from OCR text of historical death records.

Rules:
1. Return ONLY a JSON array
2. Each object must have 'nome' (full name) and 'data_obito' (death date)
3. If a date is not found, use null for data_obito
4. If a name is unclear, use the best guess
5. Do NOT include any text outside the JSON array
6. Handle Portuguese names correctly (da Silva, dos Santos, etc.)"""
            },
            {
                "role": "user",
                "content": f"Extract all names and death dates from this OCR text of a Portuguese death record index:\n\n{ocr_text}"
            }
        ],
        "temperature": 0.1,
        "max_tokens": 2000
    }
    
    try:
        response = requests.post(NVIDIA_URL, headers=HEADERS, json=payload, timeout=60)
        
        if response.status_code == 200:
            result = response.json()
            content = result['choices'][0]['message']['content']
            
            # Parse JSON
            try:
                # Limpar possível markdown
                content = content.strip()
                if content.startswith('```'):
                    content = content.split('```')[1]
                    if content.startswith('json'):
                        content = content[4:]
                    content = content.strip()
                
                data = json.loads(content)
                if isinstance(data, list):
                    return data
                else:
                    print(f"⚠️  Resposta não é uma lista: {type(data)}")
                    return []
            except json.JSONDecodeError as e:
                print(f"❌ Erro ao parsear JSON: {e}")
                print(f"Conteúdo: {content[:500]}")
                return []
        else:
            print(f"❌ Erro API {response.status_code}: {response.text[:200]}")
            return []
    except Exception as e:
        print(f"❌ Erro de conexão: {e}")
        return []


def save_to_supabase(records):
    """
    Guarda os registos extraídos no Supabase.
    """
    # Ler configuração do .env
    supabase_url = None
    supabase_key = None
    
    with open('.env', 'r') as f:
        for line in f:
            if line.startswith('SUPABASE_URL='):
                supabase_url = line.strip().split('=', 1)[1]
            elif line.startswith('SUPABASE_KEY='):
                supabase_key = line.strip().split('=', 1)[1]
    
    if not supabase_url or not supabase_key:
        print("❌ Credenciais do Supabase não encontradas")
        return 0
    
    headers = {
        "apikey": supabase_key,
        "Authorization": f"Bearer {supabase_key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }
    
    saved = 0
    for record in records:
        nome = record.get('nome', '')
        data_obito = record.get('data_obito', '')
        
        if not nome:
            continue
        
        data_obito = normalize_date(data_obito)
        
        data = {
            "nome": nome,
            "data_obito": data_obito if data_obito else None,
            "fonte": "NVIDIA OCR + Transkribus",
            "freguesia": "Celorico (Santa Maria)",
            "concelho": "Celorico da Beira",
            "distrito": "Guarda"
        }
        
        resp = requests.post(
            f"{supabase_url}/rest/v1/pessoas",
            headers=headers,
            json=data,
            timeout=30
        )
        
        if resp.status_code in [200, 201]:
            saved += 1
        else:
            print(f"⚠️  Erro ao guardar '{nome}': {resp.status_code}")
        
        # Rate limiting
        time.sleep(0.1)
    
    return saved


if __name__ == "__main__":
    # Teste com texto de exemplo
    test_ocr = """
    Indice de obitos da freguesia de Celorico Santa Maria 1864
    1 Joao da Silva faleceu a 15 de Janeiro de 1864
    2 Maria Jose Ferreira faleceu a 22 de Marco de 1864
    3 Antonio Rodrigues faleceu a 5 de Junho de 1864
    4 Ana Costa faleceu a 10 de Agosto de 1864
    5 Manuel Pereira faleceu a 20 de Novembro de 1864
    """
    
    print("=== TESTE EXTRAÇÃO DE NOMES ===")
    print(f"Texto OCR: {len(test_ocr)} caracteres")
    
    records = extract_names_from_ocr(test_ocr)
    
    if records:
        print(f"\n✅ {len(records)} nomes extraídos:")
        for r in records:
            print(f"  • {r.get('nome', '?')} - {r.get('data_obito', '?')}")
        
        # Guardar no Supabase
        print(f"\n=== GUARDANDO NO SUPABASE ===")
        saved = save_to_supabase(records)
        print(f"✅ {saved} registos guardados no Supabase")
    else:
        print("❌ Nenhum nome extraído")
