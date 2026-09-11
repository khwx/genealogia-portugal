"""
Pipeline completo para extração de óbitos de Celorico da Beira do Digitarq.
1. API Digitarq -> lista de ficheiros por documento
2. Download de imagens via /rdigital/dissemination?fileId=X
3. OCR com Tesseract (Docker)
4. Extração de nomes com NVIDIA AI
5. Guardar dados em JSON
6. Enviar para Supabase
7. Criar árvore genealógica
"""
import requests
import json
import os
import time
import re
import subprocess
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE_DIR = Path(__file__).parent
OUTPUT_DIR = BASE_DIR / "output"
IMAGES_DIR = OUTPUT_DIR / "full_images"
OCR_DIR = OUTPUT_DIR / "ocr_text"
DATA_DIR = OUTPUT_DIR / "data"
INVENTARIO_FILE = OUTPUT_DIR / "obitos_inventario.json"
RESULTS_FILE = DATA_DIR / "obitos_extraidos.json"

DIGITARQ_BASE = "https://digitarq.arquivos.pt"
API_FILES = f"{DIGITARQ_BASE}/api/rdigital/{{doc_id}}?max=200"
IMAGE_URL = f"{DIGITARQ_BASE}/rdigital/dissemination?fileId={{file_id}}"
THUMB_URL = f"{DIGITARQ_BASE}/rdigital/thumb?fileId={{file_id}}"

for d in [IMAGES_DIR, OCR_DIR, DATA_DIR]:
    d.mkdir(parents=True, exist_ok=True)


def get_session():
    session = requests.Session()
    retry = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def get_celorico_docs():
    with open(INVENTARIO_FILE, 'r') as f:
        data = json.load(f)
    celorico = [d for d in data if 'celorico' in str(d).lower()]
    return celorico


def get_file_list(session, doc_id):
    url = API_FILES.format(doc_id=doc_id)
    try:
        resp = session.get(url, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        files = data.get("results", [])
        total = data.get("total", 0)
        if total > len(files):
            resp2 = session.get(f"{url}&max={total+10}", timeout=30)
            files = resp2.json().get("results", [])
        return files
    except Exception as e:
        print(f"  ERRO API {doc_id}: {e}")
        return []


def download_image(session, file_id, filepath):
    if filepath.exists() and filepath.stat().st_size > 1000:
        return True
    url = IMAGE_URL.format(file_id=file_id)
    try:
        resp = session.get(url, timeout=60, stream=True)
        resp.raise_for_status()
        with open(filepath, 'wb') as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
        return True
    except Exception as e:
        print(f"  ERRO download {file_id}: {e}")
        return False


def ocr_image_docker(tiff_path, output_txt_path):
    if output_txt_path.exists() and output_txt_path.stat().st_size > 10:
        with open(output_txt_path, 'r') as f:
            text = f.read().strip()
        if len(text) > 20:
            return text
    
    tiff_path_str = str(tiff_path.absolute())
    output_path_str = str(output_txt_path.absolute())
    
    cmd = [
        "docker", "run", "--rm",
        "-v", f"{tiff_path.parent.absolute()}:/images",
        "ocr-engine",
        "bash", "-c",
        f"""
python3 -c "
from PIL import Image, ImageEnhance, ImageOps, ImageFilter
img = Image.open('/images/{tiff_path.name}')
gray = img.convert('L')
auto = ImageOps.autocontrast(gray, cutoff=2)
w, h = auto.size
scaled = auto.resize((w*2, h*2), Image.LANCZOS)
scaled.save('/images/{tiff_path.stem}_ocr.png', dpi=(300,300))
print('Preprocessed')
"
tesseract /images/{tiff_path.stem}_ocr.png /tmp/ocr_out -l por --psm 6 --dpi 300 2>/dev/null
cat /tmp/ocr_out.txt
"""
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        text = result.stdout.strip()
        lines = [l for l in text.split('\n') if l.strip() and l.strip() != 'Preprocessed']
        text = '\n'.join(lines)
        with open(output_path_str, 'w') as f:
            f.write(text)
        return text
    except Exception as e:
        print(f"  ERRO OCR {tiff_path.name}: {e}")
        return ""


def ocr_image_simple(tiff_path, output_txt_path):
    if output_txt_path.exists() and output_txt_path.stat().st_size > 10:
        with open(output_txt_path, 'r') as f:
            text = f.read().strip()
        if len(text) > 20:
            return text
    
    tiff_path_str = str(tiff_path.absolute())
    output_path_str = str(output_txt_path.absolute())
    
    cmd = [
        "docker", "run", "--rm",
        "-v", f"{tiff_path.parent.absolute()}:/images",
        "ocr-engine",
        "bash", "-c",
        f"""
python3 << 'PYEOF'
from PIL import Image, ImageEnhance, ImageOps, ImageFilter
img = Image.open("/images/{tiff_path.name}")
gray = img.convert("L")
auto = ImageOps.autocontrast(gray, cutoff=2)
w, h = auto.size
scaled = auto.resize((w*2, h*2), Image.LANCZOS)
scaled.save("/images/{tiff_path.stem}_ocr.png", dpi=(300,300))
PYEOF
tesseract /images/{tiff_path.stem}_ocr.png /tmp/ocr_out -l por --psm 6 --dpi 300 2>/dev/null
cat /tmp/ocr_out.txt
"""
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        text = result.stdout.strip()
        lines = text.split('\n')
        filtered = [l for l in lines if l.strip()]
        text = '\n'.join(filtered)
        with open(output_path_str, 'w') as f:
            f.write(text)
        return text
    except Exception as e:
        print(f"  ERRO OCR {tiff_path.name}: {e}")
        return ""


def extract_names_nvidia(text, nvidia_api_key):
    if not text or len(text.strip()) < 20:
        return []
    
    url = "https://integrate.api.nvidia.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {nvidia_api_key}",
        "Content-Type": "application/json"
    }
    
    prompt = f"""Analisa este texto de um registo de óbitos histórico português e extrai TODOS os nomes de pessoas mencionadas.
Para cada pessoa, identifica:
- nome completo
- data de óbito (se mencionada)
- idade (se mencionada)
- filiação (pai/mãe, se mencionados)
- estado civil (se mencionado)
- local (se mencionado)
- ofício/profissão (se mencionado)

Texto OCR (pode conter erros):
{text[:3000]}

Responde em formato JSON array:
[{{"nome": "...", "data_obito": "...", "idade": "...", "pai": "...", "mae": "...", "estado_civil": "...", "local": "...", "profissao": "..."}}]

Se não conseguires extrair nomes claros, responde: []"""

    payload = {
        "model": "meta/llama-3.1-405b-instruct",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
        "max_tokens": 2000
    }
    
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        json_match = re.search(r'\[.*\]', content, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
        return []
    except Exception as e:
        print(f"  ERRO NVIDIA AI: {e}")
        return []


def extract_names_regex(text):
    patterns = [
        r'(?i)(?:faleceu|morreu|óbito|obito|falecido|falleceu)\s+(?:a\s+)?(\d{1,2}[\s./-]\d{1,2}[\s./-]\d{2,4})',
        r"(?i)(?:filh[oa]\s+(?:de|d'))\s+([A-Z][a-zàáâãéêíóôõúç]+(?:\s+[A-Z][a-zàáâãéêíóôõúç]+)*)",
        r"(?i)(?:mulher|marido|espos[oa]|viúv[oa])\s+(?:de|d')\s+([A-Z][a-zàáâãéêíóôõúç]+(?:\s+[A-Z][a-zàáâãéêíóôõúç]+)*)",
    ]
    
    names = []
    for pat in patterns:
        matches = re.findall(pat, text)
        names.extend(matches)
    
    return list(set(names))


def send_to_supabase(records, supabase_url, supabase_key):
    url = f"{supabase_url}/rest/v1/obitos"
    headers = {
        "apikey": supabase_key,
        "Authorization": f"Bearer {supabase_key}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal"
    }
    
    try:
        resp = requests.post(url, headers=headers, json=records, timeout=60)
        if resp.status_code in (200, 201):
            print(f"  Enviados {len(records)} registos para Supabase")
            return True
        else:
            print(f"  ERRO Supabase {resp.status_code}: {resp.text[:200]}")
            return False
    except Exception as e:
        print(f"  ERRO Supabase: {e}")
        return False


def create_supabase_table(supabase_url, supabase_key):
    print("  A criar tabela obitos no Supabase (se não existe)...")
    print("  NOTA: Usa o SQL Editor no Supabase dashboard para criar a tabela:")
    print("""
    CREATE TABLE IF NOT EXISTS obitos (
        id SERIAL PRIMARY KEY,
        doc_id TEXT,
        freguesia TEXT,
        livro TEXT,
        file_id TEXT,
        file_name TEXT,
        page_number INTEGER,
        nome TEXT,
        data_obito TEXT,
        idade TEXT,
        pai TEXT,
        mae TEXT,
        estado_civil TEXT,
        local TEXT,
        profissao TEXT,
        ocr_text TEXT,
        created_at TIMESTAMPTZ DEFAULT NOW()
    );
    """)


def process_document(session, doc, nvidia_api_key=None, max_pages=None):
    doc_id = doc['url_viewer'].split('/fileViewer/')[-1].split('?')[0]
    freguesia = doc.get('freguesia', '')
    livro = doc.get('titulo', '')
    datas = doc.get('datas', '')
    
    print(f"\n{'='*60}")
    print(f"Documento: {livro} | {freguesia} | {datas}")
    print(f"Doc ID: {doc_id}")
    
    files = get_file_list(session, doc_id)
    if not files:
        print("  Sem ficheiros!")
        return []
    
    print(f"  {len(files)} imagens encontradas")
    
    if max_pages:
        files = files[:max_pages]
    
    all_records = []
    
    for i, file_info in enumerate(files):
        file_id = file_info['id']
        file_name = file_info.get('name', '')
        page_num = i + 1
        
        tiff_path = IMAGES_DIR / f"{file_id}.tiff"
        ocr_path = OCR_DIR / f"{file_id}.txt"
        
        print(f"  [{page_num}/{len(files)}] {file_name} (fileId={file_id})")
        
        if not download_image(session, file_id, tiff_path):
            continue
        
        text = ocr_image_simple(tiff_path, ocr_path)
        
        if not text or len(text.strip()) < 20:
            print(f"    OCR vazio ou muito curto")
            continue
        
        print(f"    OCR: {len(text)} chars")
        
        names_regex = extract_names_regex(text)
        names_ai = []
        if nvidia_api_key:
            names_ai = extract_names_nvidia(text, nvidia_api_key)
        
        record = {
            "doc_id": doc_id,
            "freguesia": freguesia,
            "livro": livro,
            "datas": datas,
            "file_id": file_id,
            "file_name": file_name,
            "page_number": page_num,
            "ocr_text": text[:5000],
            "names_regex": names_regex,
            "names_ai": names_ai,
        }
        
        all_records.append(record)
        time.sleep(0.5)
    
    return all_records


def build_family_tree(records):
    people = {}
    relationships = []
    
    for record in records:
        for person in record.get("names_ai", []):
            if isinstance(person, dict) and person.get("nome"):
                name = person["nome"]
                if name not in people:
                    people[name] = {
                        "nome": name,
                        "data_obito": person.get("data_obito", ""),
                        "idade": person.get("idade", ""),
                        "profissao": person.get("profissao", ""),
                        "local": person.get("local", ""),
                    }
                
                if person.get("pai"):
                    pai = person["pai"]
                    if pai not in people:
                        people[pai] = {"nome": pai}
                    relationships.append({"parent": pai, "child": name, "type": "pai"})
                
                if person.get("mae"):
                    mae = person["mae"]
                    if mae not in people:
                        people[mae] = {"nome": mae}
                    relationships.append({"parent": mae, "child": name, "type": "mae"})
    
    return {"people": list(people.values()), "relationships": relationships}


def main():
    print("="*60)
    print("PIPELINE DE EXTRAÇÃO DE ÓBITOS - CELORICO DA BEIRA")
    print("="*60)
    
    session = get_session()
    
    config = {}
    env_path = BASE_DIR / '.env'
    if env_path.exists():
        with open(env_path, 'r') as f:
            for line in f:
                if '=' in line and not line.startswith('#'):
                    key, value = line.strip().split('=', 1)
                    config[key] = value
    
    nvidia_api_key = config.get('NVIDIA_API_KEY', '')
    supabase_url = config.get('SUPABASE_URL', '')
    supabase_key = config.get('SUPABASE_KEY', '')
    
    docs = get_celorico_docs()
    print(f"\n{len(docs)} documentos de Celorico da Beira encontrados")
    
    all_records = []
    
    if RESULTS_FILE.exists():
        with open(RESULTS_FILE, 'r') as f:
            all_records = json.load(f)
        print(f"Carregados {len(all_records)} registos anteriores")
    
    processed_docs = {r['doc_id'] for r in all_records}
    
    for i, doc in enumerate(docs):
        doc_id = doc['url_viewer'].split('/fileViewer/')[-1].split('?')[0]
        if doc_id in processed_docs:
            print(f"\n[{i+1}/{len(docs)}] Já processado: {doc.get('titulo','')}")
            continue
        
        print(f"\n[{i+1}/{len(docs)}] A processar: {doc.get('titulo','')}")
        
        records = process_document(session, doc, nvidia_api_key)
        all_records.extend(records)
        
        with open(RESULTS_FILE, 'w') as f:
            json.dump(all_records, f, indent=2, ensure_ascii=False)
        
        print(f"  Total registos: {len(all_records)}")
        time.sleep(2)
    
    print(f"\n{'='*60}")
    print(f"PROCESSAMENTO COMPLETO")
    print(f"Total de registos: {len(all_records)}")
    
    tree = build_family_tree(all_records)
    tree_file = DATA_DIR / "arvore_genealogica.json"
    with open(tree_file, 'w') as f:
        json.dump(tree, f, indent=2, ensure_ascii=False)
    print(f"Árvore genealógica: {len(tree['people'])} pessoas, {len(tree['relationships'])} relações")
    
    if supabase_url and supabase_key:
        create_supabase_table(supabase_url, supabase_key)
        supabase_records = []
        for r in all_records:
            for person in r.get('names_ai', []):
                if isinstance(person, dict) and person.get('nome'):
                    supabase_records.append({
                        "doc_id": r['doc_id'],
                        "freguesia": r['freguesia'],
                        "livro": r['livro'],
                        "file_id": r['file_id'],
                        "file_name": r['file_name'],
                        "page_number": r['page_number'],
                        "nome": person.get('nome', ''),
                        "data_obito": person.get('data_obito', ''),
                        "idade": person.get('idade', ''),
                        "pai": person.get('pai', ''),
                        "mae": person.get('mae', ''),
                        "estado_civil": person.get('estado_civil', ''),
                        "local": person.get('local', ''),
                        "profissao": person.get('profissao', ''),
                        "ocr_text": r.get('ocr_text', '')[:2000],
                    })
        
        if supabase_records:
            for batch_start in range(0, len(supabase_records), 50):
                batch = supabase_records[batch_start:batch_start+50]
                send_to_supabase(batch, supabase_url, supabase_key)
    
    print("\nFicheiros guardados:")
    print(f"  Dados: {RESULTS_FILE}")
    print(f"  Árvore: {tree_file}")


if __name__ == "__main__":
    main()
