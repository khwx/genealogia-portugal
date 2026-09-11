"""
Pipeline completo: Digitarq → Gemini Vision OCR → SQLite

Uso:
    python pipeline.py                          # Processa todos os livros com páginas marcadas
    python pipeline.py --livro PCLB01-003-00014 # Processa um livro específico
    python pipeline.py --url <url_digitarq>     # Processa uma imagem específica
    python pipeline.py --test                   # Testa com a imagem de teste
"""
import os
import re
import sys
import json
import time
import base64
import sqlite3
import argparse
import requests
from pathlib import Path
from datetime import datetime

# ─── Config ────────────────────────────────────────────────────────────────────

def load_env():
    env = {}
    env_path = Path(__file__).parent / '.env'
    if env_path.exists():
        with open(env_path, encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if '=' in line and not line.startswith('#'):
                    k, v = line.split('=', 1)
                    env[k.strip()] = v.strip().strip('"').strip("'")
    return env

ENV = load_env()
GEMINI_API_KEY = ENV.get('GEMINI_API_KEY', '')
DB_PATH = Path(ENV.get('DB_PATH', 'output/genealogia.db'))
IMAGES_DIR = Path('output/images')
BOOKS_CONFIG = Path('output/books_config.json')

GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"

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

# ─── Base de dados ──────────────────────────────────────────────────────────────

def init_db():
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
    print("✅ Base de dados inicializada")

def insert_obitos(records, livro_id=None, pagina=None, imagem_url=None, texto_original=None):
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
            rec.get('freguesia', ''),
            livro_id, pagina, imagem_url,
            texto_original, 'pendente'
        ))
        inserted += 1
    conn.commit()
    conn.close()
    return inserted

# ─── Digitarq ──────────────────────────────────────────────────────────────────

def get_digitarq_image_url(viewer_url: str, page: int) -> str:
    """
    Constrói a URL da imagem a partir do URL do fileViewer do Digitarq.
    Exemplo:
      viewer: https://digitarq.arquivos.pt/fileViewer/9ebcb2e4473a4fb9a14db130aa19fff9
      image:  https://digitarq.arquivos.pt/fileViewer/9ebcb2e4473a4fb9a14db130aa19fff9?isRepresentation=true&pageNumber=2
    """
    base = viewer_url.split('?')[0]
    return f"{base}?isRepresentation=true&pageNumber={page}"

def download_image(url: str, dest: Path) -> bool:
    """Descarrega uma imagem do Digitarq."""
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
        print(f"  ❌ Erro ao descarregar {url}: {e}")
        return False

def image_to_base64(path: Path) -> tuple[str, str]:
    """Converte imagem para base64 e devolve (mime_type, data)."""
    ext = path.suffix.lower()
    mime_map = {'.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
                '.png': 'image/png', '.tiff': 'image/tiff'}
    mime = mime_map.get(ext, 'image/jpeg')
    data = base64.b64encode(path.read_bytes()).decode('utf-8')
    return mime, data

# ─── Gemini Vision ──────────────────────────────────────────────────────────────

PROMPT_OCR = """Estás a analisar uma fotografia de um ÍNDICE de registos de óbitos manuscrito português, datado de entre 1654 e 1911.

TAREFA: Extrai TODOS os registos que encontrares e devolve um JSON array.

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
2. Inclui TODOS os nomes que encontrares, mesmo que parciais
3. Preserva os nomes em português histórico (ex: D. Maria, Joana da Conceição)
4. Se a data estiver ilegível, usa null
5. Corrige erros óbvios de OCR mas mantém o grafismo original dos nomes
6. O índice tem tipicamente: número | nome | data | folha/página

Se a imagem não contiver texto legível de índice, devolve: []"""

def gemini_ocr(image_path: Path) -> list[dict]:
    """Envia uma imagem para o Gemini e extrai registos de óbitos."""
    if not GEMINI_API_KEY:
        print("  ❌ GEMINI_API_KEY não configurada no .env")
        return []

    print(f"  🤖 Gemini Vision: {image_path.name}...", end=' ', flush=True)
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
            print(f"❌ HTTP {r.status_code}: {r.text[:200]}")
            return []

        result = r.json()
        text = result['candidates'][0]['content']['parts'][0]['text'].strip()

        # Limpar markdown
        if text.startswith('```'):
            text = re.sub(r'^```\w*\n?', '', text)
            text = re.sub(r'\n?```$', '', text.strip())

        records = json.loads(text)
        if isinstance(records, list):
            print(f"✅ {len(records)} registos")
            return records
        else:
            print(f"⚠️ Resposta inesperada: {type(records)}")
            return []

    except json.JSONDecodeError as e:
        print(f"❌ JSON inválido: {e}")
        # Tentar extrair o que for possível
        return []
    except Exception as e:
        print(f"❌ Erro: {e}")
        return []

# ─── Datas ─────────────────────────────────────────────────────────────────────

def normalize_date(date_str: str) -> str | None:
    """Converte '15 de Janeiro de 1864' para '1864-01-15'."""
    if not date_str:
        return None
    s = date_str.lower().strip()

    # Formato: DD de Mês de AAAA
    m = re.search(r'(\d{1,2})\s+de\s+(\w+)\s+de\s+(\d{4})', s)
    if m:
        day, month_name, year = m.group(1).zfill(2), m.group(2), m.group(3)
        month = MONTHS_PT.get(month_name, '01')
        return f"{year}-{month}-{day}"

    # Formato: DD/MM/AAAA
    m = re.search(r'(\d{1,2})/(\d{1,2})/(\d{4})', s)
    if m:
        return f"{m.group(3)}-{m.group(2).zfill(2)}-{m.group(1).zfill(2)}"

    # Só o ano
    m = re.search(r'(\d{4})', s)
    if m:
        return m.group(1)

    return None

# ─── Pipeline principal ─────────────────────────────────────────────────────────

def process_image_url(url: str, livro_id: str = None, pagina: int = None, freguesia: str = None):
    """Processa uma imagem diretamente por URL."""
    safe_name = re.sub(r'[^\w]', '_', url.split('/')[-1][:40])
    dest = IMAGES_DIR / f"{livro_id or 'temp'}_{pagina or 0}_{safe_name}.jpg"

    print(f"\n📷 Descarregando página {pagina} de {livro_id or url[:60]}...")
    if not download_image(url, dest):
        return 0

    records = gemini_ocr(dest)
    if freguesia:
        for r in records:
            if not r.get('freguesia'):
                r['freguesia'] = freguesia

    saved = insert_obitos(records, livro_id=livro_id, pagina=pagina,
                          imagem_url=url, texto_original=None)
    print(f"  💾 {saved} registos guardados (pendentes)")
    return saved

def process_book(livro: dict):
    """Processa todas as páginas de índice de um livro."""
    codigo = livro.get('codigo') or livro.get('id', '')
    paginas_str = livro.get('paginas_indice', '')
    url_viewer = livro.get('url_viewer', '')
    freguesia = livro.get('freguesia', '')

    if not paginas_str or not url_viewer:
        print(f"  ⚠️  {codigo}: sem páginas de índice ou URL definidos")
        return 0

    # Parse ranges: "249-255, 260"
    paginas = []
    for part in paginas_str.split(','):
        part = part.strip()
        if '-' in part:
            a, b = part.split('-', 1)
            try:
                paginas.extend(range(int(a.strip()), int(b.strip()) + 1))
            except ValueError:
                pass
        elif part.isdigit():
            paginas.append(int(part))

    if not paginas:
        print(f"  ⚠️  {codigo}: formato de páginas inválido: '{paginas_str}'")
        return 0

    print(f"\n📚 Livro: {codigo} ({freguesia})")
    print(f"   Páginas de índice: {paginas}")

    total = 0
    for pag in paginas:
        img_url = get_digitarq_image_url(url_viewer, pag)
        total += process_image_url(img_url, livro_id=codigo, pagina=pag, freguesia=freguesia)
        time.sleep(2)  # Rate limiting

    # Atualizar status do livro
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT OR REPLACE INTO livros (codigo, titulo, freguesia, paginas_indice, url_viewer, status, data_processo) "
        "VALUES (?,?,?,?,?,?,?)",
        (codigo, livro.get('titulo', ''), freguesia, paginas_str, url_viewer,
         'processado', datetime.now().isoformat())
    )
    conn.commit()
    conn.close()

    return total

def load_books_config() -> list[dict]:
    """Carrega a configuração dos livros."""
    if BOOKS_CONFIG.exists():
        with open(BOOKS_CONFIG, encoding='utf-8') as f:
            return json.load(f)
    # Fallback: ler da BD
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM livros WHERE paginas_indice IS NOT NULL AND paginas_indice != ''"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def run_test():
    """Testa o pipeline com a imagem de teste incluída no repo."""
    test_img = Path('test_image.png')
    if not test_img.exists():
        print("❌ test_image.png não encontrada")
        return
    init_db()
    print("🧪 MODO TESTE")
    print(f"   Imagem: {test_img}")
    records = gemini_ocr(test_img)
    print(f"\n📋 Registos extraídos:")
    for r in records:
        print(f"   • {r.get('nome')} — {r.get('data_obito')}")
    if records:
        saved = insert_obitos(records, livro_id='TEST', texto_original='TESTE')
        print(f"\n✅ {saved} registos guardados na BD (status: pendente)")
    print(f"\n💡 Agora corre 'python review_server.py' e abre review.html")

# ─── CLI ────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='Pipeline Genealogia Portugal')
    parser.add_argument('--livro', help='Código do livro a processar')
    parser.add_argument('--url', help='URL direto de uma imagem Digitarq')
    parser.add_argument('--pagina', type=int, help='Número da página (com --url)')
    parser.add_argument('--test', action='store_true', help='Modo teste')
    args = parser.parse_args()

    if args.test:
        run_test()
        return

    init_db()

    if args.url:
        process_image_url(args.url, livro_id=args.livro, pagina=args.pagina)
        return

    books = load_books_config()
    if args.livro:
        books = [b for b in books if b.get('codigo', '') == args.livro]
        if not books:
            print(f"❌ Livro '{args.livro}' não encontrado na configuração")
            return

    if not books:
        print("⚠️  Nenhum livro com páginas de índice configuradas.")
        print("   Abre index_pages.html, define as páginas de índice e guarda.")
        return

    print(f"🚀 Iniciando pipeline — {len(books)} livro(s) a processar")
    total = 0
    for book in books:
        total += process_book(book)

    print(f"\n🎉 Concluído! {total} registos guardados com status 'pendente'")
    print("   Corre 'python review_server.py' e abre review.html para rever")

if __name__ == '__main__':
    main()
