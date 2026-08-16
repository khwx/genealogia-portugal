"""
Script completo para limpar, baixar e processar todos os livros de óbitos.
Fluxo:
1. Limpar pastas de imagens e OCR
2. Identificar livros pendentes
3. Baixar todas as imagens
4. Processar com OCR (Gemini Vision)
5. Guardar resultados na BD

Uso:
    python full_pipeline.py                    # Processar todos os livros pendentes
    python full_pipeline.py --concelho clb     # Especificar concelho
    python full_pipeline.py --freguesia "Celorico (Santa Maria)"  # Uma freguesia
"""
import os
import sys
import json
import time
import re
import shutil
import argparse
import sqlite3
import requests
import base64
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).parent
OUTPUT_DIR = BASE_DIR / "output"
IMAGES_DIR = OUTPUT_DIR / "images"
FULL_IMAGES_DIR = OUTPUT_DIR / "full_images"
DB_PATH = OUTPUT_DIR / "obitos.db"
INVENTARIO_FILE = OUTPUT_DIR / "inventario_completo_clb.json"

GEMINI_API_KEY = ""
GEMINI_URL = ""

MONTHS_PT = {
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

def load_env():
    global GEMINI_API_KEY, GEMINI_URL
    env_path = BASE_DIR / '.env'
    if env_path.exists():
        with open(env_path, encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if '=' in line and not line.startswith('#'):
                    k, v = line.split('=', 1)
                    if k.strip() == 'GEMINI_API_KEY':
                        GEMINI_API_KEY = v.strip().strip('"').strip("'")
                        GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"

def clean_all():
    """Limpar todas as imagens e processamento existente."""
    print("=" * 60)
    print("LIMPANDO PASTAS...")
    print("=" * 60)
    
    dirs_to_clean = [IMAGES_DIR, FULL_IMAGES_DIR]
    for dir_path in dirs_to_clean:
        if dir_path.exists():
            shutil.rmtree(dir_path)
            print(f"  Apagada: {dir_path}")
        dir_path.mkdir(parents=True, exist_ok=True)
        print(f"  Criada: {dir_path}")
    
    # Remover BD
    if DB_PATH.exists():
        DB_PATH.unlink()
        print(f"  Apagada: {DB_PATH}")
    
    print("  Limpeza concluída!\n")

def init_db():
    """Inicializar base de dados."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute("""
        CREATE TABLE IF NOT EXISTS obitos (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            nome            TEXT NOT NULL,
            data_obito      TEXT,
            ano             INTEGER,
            numero_registo  TEXT,
            freguesia       TEXT,
            concelho        TEXT DEFAULT 'Celorico da Beira',
            distrito        TEXT DEFAULT 'Guarda',
            livro_id        TEXT,
            pagina          INTEGER,
            imagem_url      TEXT,
            texto_original  TEXT,
            fonte           TEXT DEFAULT 'Gemini Vision',
            confidence      REAL DEFAULT 1.0,
            status          TEXT DEFAULT 'pendente',
            data_extracao   TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    c.execute("""
        CREATE TABLE IF NOT EXISTS livros (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo          TEXT UNIQUE,
            titulo          TEXT,
            freguesia       TEXT,
            data_inicio     TEXT,
            data_fim        TEXT,
            total_paginas   INTEGER,
            paginas_indice  TEXT,
            url_viewer      TEXT,
            status          TEXT DEFAULT 'pendente',
            data_processo   TEXT
        )
    """)
    
    c.execute("CREATE INDEX IF NOT EXISTS idx_obitos_nome ON obitos(nome)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_obitos_data ON obitos(data_obito)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_obitos_status ON obitos(status)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_obitos_livro ON obitos(livro_id)")
    
    conn.commit()
    conn.close()
    print("Base de dados inicializada")

def load_inventario(freguesia_filter=None):
    """Carregar inventário e filtrar por freguesia se necessário."""
    with open(INVENTARIO_FILE, encoding='utf-8') as f:
        inventario = json.load(f)
    
    if freguesia_filter:
        inventario = [i for i in inventario if i.get('freguesia') == freguesia_filter]
    
    return inventario

def get_processed_books():
    """Obter lista de livros já processados na BD."""
    if not DB_PATH.exists():
        return set()
    
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("SELECT codigo FROM livros WHERE status = 'processado'").fetchall()
    conn.close()
    return set(r[0] for r in rows)

def get_digitarq_image_url(viewer_url, page):
    """Construir URL da imagem do Digitarq."""
    base = viewer_url.split('?')[0]
    return f"{base}?isRepresentation=true&pageNumber={page}"

def download_image(url, dest):
    """Baixar uma imagem do Digitarq."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "image/webp,image/apng,image/*,*/*;q=0.8",
        "Referer": "https://digitarq.arquivos.pt/",
    }
    try:
        r = requests.get(url, headers=headers, timeout=60)
        r.raise_for_status()
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(r.content)
        return True
    except Exception as e:
        print(f"  Erro ao baixar {url}: {e}")
        return False

def get_total_pages(viewer_url):
    """Obter número total de páginas de um livro."""
    # Fazer uma requisição à API do Digitarq para obter metadados
    doc_id = viewer_url.split('/')[-1].split('?')[0]
    api_url = f"https://digitarq.arquivos.pt/api/rdigital/{doc_id}?max=200"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://digitarq.arquivos.pt/",
    }
    
    try:
        r = requests.get(api_url, headers=headers, timeout=30)
        r.raise_for_status()
        data = r.json()
        return data.get('totalPages', 0)
    except:
        return 0

def download_book_images(livro, full_images_dir=True):
    """Baixar todas as imagens de um livro."""
    codigo = livro.get('titulo', '')
    url_viewer = livro.get('url_viewer', '')
    
    if not url_viewer:
        return 0
    
    # Extrair ID do documento
    doc_id = url_viewer.split('/')[-1].split('?')[0]
    
    # Obter número total de páginas
    total_pages = get_total_pages(url_viewer)
    if total_pages == 0:
        # Tentar obter páginas de outra forma
        total_pages = 100  # Valor por defeito
    
    print(f"  Baixando {codigo} ({total_pages} páginas)...")
    
    count = 0
    for page in range(1, total_pages + 1):
        img_url = get_digitarq_image_url(url_viewer, page)
        
        if full_images_dir:
            dest = FULL_IMAGES_DIR / f"{doc_id}_p{page:04d}.tiff"
        else:
            dest = IMAGES_DIR / f"{doc_id}_p{page:04d}.jpg"
        
        if not dest.exists():
            if download_image(img_url, dest):
                count += 1
                if count % 50 == 0:
                    print(f"    {count}/{total_pages} páginas baixadas...")
        
        time.sleep(0.5)  # Rate limiting
    
    return count

def image_to_base64(path):
    """Converter imagem para base64."""
    ext = path.suffix.lower()
    mime_map = {'.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
                '.png': 'image/png', '.tiff': 'image/tiff'}
    mime = mime_map.get(ext, 'image/jpeg')
    data = base64.b64encode(path.read_bytes()).decode('utf-8')
    return mime, data

PROMPT_OCR = """Estás a analisar uma fotografia de um ÍNDICE de registos de óbitos manuscrito português, datado de entre 1654 e 1911.

TAREFA: Extrai TODOS os registos que encontras e devolve um JSON array.

FORMATO de cada registo:
{
  "numero": "número do registo (se existir)",
  "nome": "nome completo da pessoa falecida",
  "data_obito": "data de óbito no formato original (ex: 15 de Janeiro de 1864)",
  "freguesia": "nome da freguesia (se mencionada)",
  "observacoes": "qualquer outra informação relevante"
}

REGRAS:
1. Devolve APENAS o JSON array, sem texto adicional
2. Inclui TODOS os nomes que encontras, mesmo que parciais
3. Preserva os nomes em português histórico (ex: D. Maria, Joana da Conceição)
4. Se a data estiver ilegível, usa null
5. Corrige erros óbvios de OCR mas mantém o grafismo original dos nomes
6. O índice tem tipicamente: número | nome | data | folha/página

Se a imagem não conter texto legível de índice, devolve: []"""

def gemini_ocr(image_path):
    """Enviar imagem para Gemini e extrair registos."""
    if not GEMINI_API_KEY:
        print("  GEMINI_API_KEY não configurada no .env")
        return []
    
    print(f"  Gemini Vision: {image_path.name}...", end=' ', flush=True)
    mime, data = image_to_base64(image_path)
    
    payload = {
        "contents": [{
            "parts": [
                {"text": PROMPT_OCR},
                {"inline_data": {"mime_type": mime, "data": data}}
            ]
        }],
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": 4096,
        }
    }
    
    try:
        r = requests.post(GEMINI_URL, json=payload, timeout=120)
        if r.status_code != 200:
            print(f"HTTP {r.status_code}: {r.text[:200]}")
            return []
        
        result = r.json()
        text = result['candidates'][0]['content']['parts'][0]['text'].strip()
        
        # Limpar markdown
        if text.startswith('```'):
            text = re.sub(r'^```\w*\n?', '', text)
            text = re.sub(r'\n?```$', '', text.strip())
        
        records = json.loads(text)
        if isinstance(records, list):
            print(f"{len(records)} registos")
            return records
        else:
            print(f"Resposta inesperada: {type(records)}")
            return []
    
    except json.JSONDecodeError as e:
        print(f"JSON inválido: {e}")
        return []
    except Exception as e:
        print(f"Erro: {e}")
        return []

def normalize_date(date_str):
    """Converter data para formato ISO."""
    if not date_str:
        return None
    s = date_str.lower().strip()
    
    m = re.search(r'(\d{1,2})\s+de\s+(\w+)\s+de\s+(\d{4})', s)
    if m:
        day, month_name, year = m.group(1).zfill(2), m.group(2), m.group(3)
        month = MONTHS_PT.get(month_name, '01')
        return f"{year}-{month}-{day}"
    
    m = re.search(r'(\d{1,2})/(\d{1,2})/(\d{4})', s)
    if m:
        return f"{m.group(3)}-{m.group(2).zfill(2)}-{m.group(1).zfill(2)}"
    
    m = re.search(r'(\d{4})', s)
    if m:
        return m.group(1)
    
    return None

def insert_obitos(records, livro_id=None, pagina=None, imagem_url=None, texto_original=None, freguesia=None):
    """Inserir registos na BD."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    inserted = 0
    for rec in records:
        nome = rec.get('nome', '').strip()
        if not nome or len(nome) < 3:
            continue
        data_str = rec.get('data_obito') or rec.get('data') or ''
        data_norm = normalize_date(data_str)
        ano = None
        if data_norm:
            m = re.match(r'(\d{4})', data_norm)
            if m:
                ano = int(m.group(1))
        c.execute("""
            INSERT INTO obitos
                (nome, data_obito, ano, numero_registo, freguesia, livro_id,
                 pagina, imagem_url, texto_original, status)
            VALUES (?,?,?,?,?,?,?,?,?,?)
        """, (
            nome, data_norm, ano,
            rec.get('numero_registo') or rec.get('numero'),
            freguesia or rec.get('freguesia', ''),
            livro_id, pagina, imagem_url,
            texto_original, 'pendente'
        ))
        inserted += 1
    conn.commit()
    conn.close()
    return inserted

def process_book_images(livro):
    """Processar todas as imagens de um livro com OCR."""
    codigo = livro.get('titulo', '')
    freguesia = livro.get('freguesia', '')
    url_viewer = livro.get('url_viewer', '')
    
    if not url_viewer:
        return 0
    
    doc_id = url_viewer.split('/')[-1].split('?')[0]
    
    # Listar imagens baixadas deste livro
    imagens = sorted(IMAGES_DIR.glob(f"{doc_id}_p*.jpg"))
    if not imagens:
        imagens = sorted(FULL_IMAGES_DIR.glob(f"{doc_id}_p*.tiff"))
    
    if not imagens:
        print(f"  Nenhuma imagem encontrada para {codigo}")
        return 0
    
    print(f"  Processando {len(imagens)} imagens de {codigo}...")
    
    total = 0
    for img_path in imagens:
        # Extrair número da página
        match = re.search(r'_p(\d+)', img_path.name)
        pagina = int(match.group(1)) if match else None
        
        records = gemini_ocr(img_path)
        if freguesia:
            for r in records:
                if not r.get('freguesia'):
                    r['freguesia'] = freguesia
        
        saved = insert_obitos(records, livro_id=codigo, pagina=pagina,
                            imagem_url=url_viewer, texto_original=None,
                            freguesia=freguesia)
        total += saved
        time.sleep(1)
    
    # Atualizar status do livro
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT OR REPLACE INTO livros (codigo, titulo, freguesia, url_viewer, status, data_processo) "
        "VALUES (?,?,?,?,?,?)",
        (codigo, codigo, freguesia, url_viewer, 'processado', datetime.now().isoformat())
    )
    conn.commit()
    conn.close()
    
    return total

def main():
    parser = argparse.ArgumentParser(description='Pipeline completo de processamento')
    parser.add_argument('--concelho', default='clb', help='Código do concelho')
    parser.add_argument('--freguesia', help='Filtrar por freguesia')
    parser.add_argument('--skip-clean', action='store_true', help='Não limpar pastas')
    parser.add_argument('--skip-download', action='store_true', help='Não baixar imagens')
    parser.add_argument('--skip-ocr', action='store_true', help='Não processar OCR')
    args = parser.parse_args()
    
    load_env()
    
    # 1. Limpar
    if not args.skip_clean:
        clean_all()
    
    # 2. Inicializar BD
    init_db()
    
    # 3. Carregar inventário
    inventario = load_inventario(args.freguesia)
    print(f"Total de livros no inventário: {len(inventario)}")
    
    # 4. Filtrar livros não processados
    processed = get_processed_books()
    livros_pendentes = [l for l in inventario if l.get('titulo') not in processed]
    print(f"Livros pendentes: {len(livros_pendentes)}")
    
    if not livros_pendentes:
        print("Todos os livros já foram processados!")
        return
    
    # 5. Baixar imagens
    if not args.skip_download:
        print("\n" + "=" * 60)
        print("DOWNLOAD DE IMAGENS")
        print("=" * 60)
        for i, livro in enumerate(livros_pendentes):
            print(f"\n[{i+1}/{len(livros_pendentes)}] {livro.get('titulo', '')}")
            try:
                download_book_images(livro, full_images_dir=True)
            except Exception as e:
                print(f"  Erro: {e}")
            time.sleep(2)
    
    # 6. Processar OCR
    if not args.skip_ocr:
        print("\n" + "=" * 60)
        print("PROCESSAMENTO OCR")
        print("=" * 60)
        total_registos = 0
        for i, livro in enumerate(livros_pendentes):
            print(f"\n[{i+1}/{len(livros_pendentes)}] {livro.get('titulo', '')}")
            try:
                saved = process_book_images(livro)
                total_registos += saved
                print(f"  Total de registos: {total_registos}")
            except Exception as e:
                print(f"  Erro: {e}")
        
        print(f"\n{'=' * 60}")
        print(f"CONCLUÍDO! {total_registos} registos guardados na BD")
        print(f"{'=' * 60}")

if __name__ == '__main__':
    main()
