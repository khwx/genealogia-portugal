"""
Script para extrair nomes do índice de registos de óbitos.
Usa Google Vision API + NVIDIA API para OCR e extração de nomes.
Guarda no Supabase.

Uso:
1. Descarrega as imagens do índice do digitarq (últimas 5 páginas de cada livro)
2. Coloca as imagens na pasta `output/images/`
3. Executa: python extract_index_names.py
"""
import requests
import json
import base64
import os
import time
import re
from pathlib import Path

# Ler configuração do .env
def get_config():
    config = {}
    env_path = Path(__file__).parent / '.env'
    with open(env_path, 'r') as f:
        for line in f:
            if '=' in line and not line.startswith('#'):
                key, value = line.strip().split('=', 1)
                config[key] = value
    return config

config = get_config()

GOOGLE_VISION_API_KEY = config.get('GOOGLE_VISION_API_KEY', '')
NVIDIA_API_KEY = config.get('NVIDIA_API_KEY', '')
SUPABASE_URL = config.get('SUPABASE_URL', '')
SUPABASE_KEY = config.get('SUPABASE_KEY', '')

IMAGES_DIR = Path(__file__).parent / 'output' / 'images'


def google_vision_ocr(image_path):
    """
    Usa Google Vision API para extrair texto de uma imagem.
    """
    print(f"  📷 Google Vision OCR: {os.path.basename(image_path)}")
    
    with open(image_path, 'rb') as f:
        image_data = base64.b64encode(f.read()).decode()
    
    url = f"https://vision.googleapis.com/v1/images:annotate?key={GOOGLE_VISION_API_KEY}"
    
    payload = {
        "requests": [
            {
                "image": {
                    "content": image_data
                },
                "features": [
                    {
                        "type": "TEXT_DETECTION",
                        "maxResults": 50
                    }
                ],
                "imageContext": {
                    "languageHints": ["pt"]
                }
            }
        ]
    }
    
    try:
        resp = requests.post(url, json=payload, timeout=60)
        
        if resp.status_code == 200:
            result = resp.json()
            if "responses" in result and result["responses"]:
                detections = result["responses"][0].get("textAnnotations", [])
                if detections:
                    full_text = detections[0].get("description", "")
                    confidence = detections[0].get("confidence", 0)
                    print(f"  ✅ Texto extraído (confiança: {confidence:.2f})")
                    return full_text
                else:
                    print("  ❌ Nenhum texto encontrado")
                    return ""
            else:
                print(f"  ❌ Resposta inválida: {result}")
                return ""
        else:
            print(f"  ❌ Erro HTTP {resp.status_code}: {resp.text[:200]}")
            return ""
    except Exception as e:
        print(f"  ❌ Erro: {e}")
        return ""


def nvidia_extract_names(ocr_text):
    """
    Usa NVIDIA API para extrair nomes e datas do texto OCR.
    """
    if not ocr_text or not ocr_text.strip():
        return []
    
    print(f"  🧠 NVIDIA API: Extraindo nomes...")
    
    url = "https://integrate.api.nvidia.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {NVIDIA_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "meta/llama-3.1-8b-instruct",
        "messages": [
            {
                "role": "system",
                "content": """You are a Portuguese genealogy expert. Extract names and death dates from OCR text of historical death record indexes.

Rules:
1. Return ONLY a JSON array
2. Each object must have 'nome' (full name) and 'data_obito' (death date in format 'DD de Mês de AAAA')
3. If a date is not found, use null for data_obito
4. If a name is unclear, use the best guess
5. Do NOT include any text outside the JSON array
6. Handle Portuguese names correctly (da Silva, dos Santos, etc.)
7. The text is from a death record index, so each line typically has: number, name, date"""
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
        resp = requests.post(url, headers=headers, json=payload, timeout=60)
        
        if resp.status_code == 200:
            result = resp.json()
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
                    print(f"  ✅ {len(data)} nomes extraídos")
                    return data
                else:
                    print(f"  ⚠️  Resposta não é uma lista: {type(data)}")
                    return []
            except json.JSONDecodeError as e:
                print(f"  ❌ Erro ao parsear JSON: {e}")
                print(f"  Conteúdo: {content[:500]}")
                return []
        else:
            print(f"  ❌ Erro API {resp.status_code}: {resp.text[:200]}")
            return []
    except Exception as e:
        print(f"  ❌ Erro de conexão: {e}")
        return []


def normalize_date(date_str):
    """
    Converte '15 de Janeiro de 1864' para '1864-01-15'
    """
    if not date_str:
        return None
    
    date_str = date_str.lower().strip()
    
    meses = {
        "janeiro": "01", "jan": "01",
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
    
    # Tentar formato: DD de Mês de AAAA
    match = re.search(r'(\d{1,2})\s+de\s+(\w+)\s+de\s+(\d{4})', date_str)
    if match:
        day = match.group(1).zfill(2)
        month_name = match.group(2)
        year = match.group(3)
        month = meses.get(month_name, "01")
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


def save_to_supabase(records, freguesia="Celorico (Santa Maria)"):
    """
    Guarda os registos extraídos no Supabase.
    """
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("❌ Credenciais do Supabase não encontradas")
        return 0
    
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }
    
    saved = 0
    for record in records:
        nome = record.get('nome', '')
        data_obito = normalize_date(record.get('data_obito', ''))
        
        if not nome:
            continue
        
        data = {
            "nome": nome,
            "data_obito": data_obito,
            "fonte": "Google Vision + NVIDIA OCR",
            "freguesia": freguesia,
            "concelho": "Celorico da Beira",
            "distrito": "Guarda"
        }
        
        resp = requests.post(
            f"{SUPABASE_URL}/rest/v1/pessoas",
            headers=headers,
            json=data,
            timeout=30
        )
        
        if resp.status_code in [200, 201]:
            saved += 1
            print(f"  ✅ Guardado: {nome} ({data_obito})")
        else:
            print(f"  ⚠️  Erro ao guardar '{nome}': {resp.status_code}")
        
        # Rate limiting
        time.sleep(0.1)
    
    return saved


def process_all_images():
    """
    Processa todas as imagens na pasta output/images/
    """
    if not IMAGES_DIR.exists():
        print(f"❌ Pasta de imagens não encontrada: {IMAGES_DIR}")
        print(f"Cria a pasta e coloca lá as imagens do índice.")
        return
    
    image_files = list(IMAGES_DIR.glob("*.jpg")) + \
                  list(IMAGES_DIR.glob("*.jpeg")) + \
                  list(IMAGES_DIR.glob("*.png")) + \
                  list(IMAGES_DIR.glob("*.tiff")) + \
                  list(IMAGES_DIR.glob("*.bmp"))
    
    if not image_files:
        print(f"❌ Nenhuma imagem encontrada em {IMAGES_DIR}")
        print(f"Coloca as imagens do índice nesta pasta.")
        return
    
    print(f"=== PROCESSANDO {len(image_files)} IMAGENS ===\n")
    
    all_records = []
    
    for i, image_path in enumerate(sorted(image_files)):
        print(f"\n--- Imagem {i+1}/{len(image_files)}: {image_path.name} ---")
        
        # 1. OCR com Google Vision
        ocr_text = google_vision_ocr(image_path)
        
        if not ocr_text:
            print("  ⚠️  Nenhum texto extraído, a continuar...")
            continue
        
        # 2. Extrair nomes com NVIDIA API
        records = nvidia_extract_names(ocr_text)
        
        if records:
            all_records.extend(records)
        
        # Rate limiting
        time.sleep(1)
    
    # 3. Guardar no Supabase
    if all_records:
        print(f"\n=== GUARDANDO {len(all_records)} REGISTOS NO SUPABASE ===")
        saved = save_to_supabase(all_records)
        print(f"\n✅ {saved} registos guardados no Supabase")
    else:
        print("\n❌ Nenhum registo extraído")
    
    # 4. Guardar resultados em JSON
    output_file = Path(__file__).parent / 'output' / 'extracted_names.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(all_records, f, ensure_ascii=False, indent=2)
    print(f"📄 Resultados guardados em: {output_file}")


if __name__ == "__main__":
    process_all_images()
