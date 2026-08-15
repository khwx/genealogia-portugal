#!/usr/bin/env python3
"""
OCR com Gemini Vision para registos de óbitos paroquiais.

Processa imagens JPEG do output/images/jpeg/ e extrai registos de óbito.
Guarda resultados em output/ocr_results.json e na BD SQLite.

Uso:
    python ocr_gemini.py                        # Processa todas as imagens não processadas
    python ocr_gemini.py --file image.jpeg      # Processa uma imagem específica
    python ocr_gemini.py --reprocess            # Reprocessa todas as imagens
"""
import os
import re
import json
import time
import base64
import sqlite3
import argparse
import requests
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).parent
OUTPUT_DIR = BASE_DIR / "output"
JPEG_DIR = OUTPUT_DIR / "images" / "jpeg"
DB_PATH = OUTPUT_DIR / "obitos.db"
RESULTS_FILE = OUTPUT_DIR / "ocr_results.json"
PROGRESS_FILE = OUTPUT_DIR / "ocr_progress.json"

MONTHS_PT = {
    "janeiro": "01", "fevereiro": "02", "março": "03", "marco": "03",
    "abril": "04", "maio": "05", "junho": "06", "julho": "07",
    "agosto": "08", "setembro": "09", "outubro": "10", "novembro": "11",
    "dezembro": "12",
}

GEMINI_KEYS = [k.strip() for k in os.environ.get("GEMINI_KEYS", "").split(",") if k.strip()]
if not GEMINI_KEYS:
    single = os.environ.get("GEMINI_API_KEY", "").strip()
    if single:
        GEMINI_KEYS = [single]

DOC_MAP = {
    "1d7ea53080f5401aa4c0a6d035244e71": {"titulo": "PCLB19/001/B2", "periodo": "1718-1728"},
    "1f55db5fa2c54f1a854aa454faaac8e1": {"titulo": "PCLB19/001/B1", "periodo": "1706-1718"},
    "4c38df691d7e4d50b62ec7fe196af3da": {"titulo": "PCLB19/001/B4", "periodo": "1744-1775"},
    "b90c7862e3f149ae9c37a03724884eba": {"titulo": "PCLB19/001/B3", "periodo": "1728-1744"},
    "e093f8008c4b4306ae248ff95204abea": {"titulo": "PCLB19/001/B5", "periodo": "1775-1815"},
}

PROMPT = """Esta é uma fotografia de uma PÁGINA DE ÍNDICE de registos de óbitos paroquiais portugueses (séc. XVII-XIX) do arquivo Distrital da Guarda.

TAREFA: Extrai TODOS os registos de óbito que encontrares na imagem.
Cada registo pode ter: número, nome do falecido, data de óbito, idade, estado civil, profissão, filiação, naturalidade, causa de morte, observações.

Devolve APENAS um JSON array. Cada objeto com os campos que conseguires extrair:
{
  "numero": "número do registo",
  "nome": "nome completo do falecido",
  "data_obito": "data no formato original (ex: 15 de Janeiro de 1864)",
  "idade": "idade",
  "estado_civil": "solteiro, casado, viúvo, etc.",
  "profissao": "profissão",
  "filiacao": "nome do pai/mãe",
  "naturalidade": "local de origem",
  "causa_morte": "causa de óbito",
  "observacoes": "outras informações"
}

REGRAS:
1. Preserva nomes em português histórico
2. Se a data estiver ilegível, usa null
3. Inclui TODOS os registos, mesmo que parciais
4. Se não houver registos legíveis, devolve: []"""


def load_progress() -> set:
    if PROGRESS_FILE.exists():
        with open(PROGRESS_FILE) as f:
            return set(json.load(f))
    return set()


def save_progress(processed: set):
    with open(PROGRESS_FILE, "w") as f:
        json.dump(list(processed), f)


def normalize_date(date_str: str) -> str | None:
    if not date_str:
        return None
    s = str(date_str).lower().strip()
    m = re.search(r"(\d{1,2})\s+de\s+(\w+)\s+de\s+(\d{4})", s)
    if m:
        day, month_name, year = m.group(1).zfill(2), m.group(2), m.group(1) if len(m.group(1)) == 4 else m.group(3)
        year = m.group(3)
        month = MONTHS_PT.get(month_name, "01")
        return f"{year}-{month}-{day}"
    m = re.search(r"(\d{4})", s)
    if m:
        return m.group(1)
    return None


def gemini_ocr(image_path: Path, key_idx: int) -> tuple[list[dict], int]:
    """Processar imagem com Gemini. Retorna (records, next_key_idx)."""
    with open(image_path, "rb") as f:
        img_data = base64.b64encode(f.read()).decode()

    payload = {
        "contents": [{"parts": [
            {"text": PROMPT},
            {"inline_data": {"mime_type": "image/jpeg", "data": img_data}}
        ]}],
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 8192}
    }

    for attempt in range(len(GEMINI_KEYS)):
        idx = (key_idx + attempt) % len(GEMINI_KEYS)
        key = GEMINI_KEYS[idx]
        api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={key}"

        try:
            r = requests.post(api_url, json=payload, timeout=120)
            if r.status_code == 200:
                result = r.json()
                text = result["candidates"][0]["content"]["parts"][0]["text"].strip()
                if text.startswith("```"):
                    text = re.sub(r"^```\w*\n?", "", text)
                    text = re.sub(r"\n?```$", "", text.strip())
                records = json.loads(text)
                if isinstance(records, list):
                    return records, idx
                return [], idx
            elif r.status_code == 429:
                print(f"    ⏳ Rate limit chave {idx+1} - 20s...")
                time.sleep(20)
            else:
                print(f"    ❌ HTTP {r.status_code}")
                time.sleep(5)
        except json.JSONDecodeError:
            print(f"    ⚠️ JSON inválido")
            return [], idx
        except Exception as e:
            print(f"    ❌ {e}")
            time.sleep(5)

    return [], key_idx


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS obitos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            data_obito TEXT,
            ano INTEGER,
            numero_registo TEXT,
            freguesia TEXT,
            concelho TEXT DEFAULT 'Celorico da Beira',
            distrito TEXT DEFAULT 'Guarda',
            livro_id TEXT,
            pagina INTEGER,
            imagem_url TEXT,
            texto_original TEXT,
            fonte TEXT DEFAULT 'Gemini Vision',
            confidence REAL DEFAULT 1.0,
            status TEXT DEFAULT 'pendente',
            data_extracao TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    c.execute("CREATE INDEX IF NOT EXISTS idx_obitos_nome ON obitos(nome)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_obitos_data ON obitos(data_obito)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_obitos_status ON obitos(status)")
    conn.commit()
    conn.close()


def insert_records(records: list[dict]):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    inserted = 0
    for rec in records:
        nome = rec.get("nome", "").strip()
        if not nome or len(nome) < 3:
            continue
        data_str = rec.get("data_obito") or ""
        data_norm = normalize_date(data_str)
        ano = None
        if data_norm:
            m = re.match(r"(\d{4})", data_norm)
            if m:
                ano = int(m.group(1))
        c.execute("""
            INSERT INTO obitos (nome, data_obito, ano, numero_registo, freguesia, livro_id, pagina, status)
            VALUES (?,?,?,?,?,?,?,?)
        """, (
            nome, data_norm, ano,
            rec.get("numero"),
            rec.get("freguesia", "Celorico (Santa Maria)"),
            rec.get("livro_id"),
            rec.get("pagina"),
            "pendente"
        ))
        inserted += 1
    conn.commit()
    conn.close()
    return inserted


def main():
    parser = argparse.ArgumentParser(description="OCR Gemini para registos de óbitos")
    parser.add_argument("--file", help="Processar uma imagem específica")
    parser.add_argument("--reprocess", action="store_true", help="Reprocessar todas")
    args = parser.parse_args()

    init_db()

    if args.file:
        jpeg_files = [Path(args.file)]
    else:
        jpeg_files = sorted(JPEG_DIR.glob("*.jpeg"))

    if not jpeg_files:
        print("Nenhuma imagem JPEG encontrada")
        return

    processed = set() if args.reprocess else load_progress()
    print(f"📸 {len(jpeg_files)} imagens ({len(processed)} já processadas)\n")

    all_results = []
    key_idx = 0
    total_inserted = 0

    for i, jpeg_path in enumerate(jpeg_files):
        if str(jpeg_path) in processed:
            continue

        doc_id = jpeg_path.name.split("_")[0]
        livro_info = DOC_MAP.get(doc_id, {"titulo": "?"})
        page_match = re.search(r"m(\d+)", jpeg_path.name)
        page_num = int(page_match.group(1)) if page_match else 0

        print(f"[{i+1}/{len(jpeg_files)}] {jpeg_path.name} (livro: {livro_info['titulo']})")

        records, key_idx = gemini_ocr(jpeg_path, key_idx)

        for rec in records:
            rec["livro_id"] = livro_info["titulo"]
            rec["freguesia"] = "Celorico (Santa Maria)"
            rec["pagina"] = page_num

        print(f"  ✅ {len(records)} registos")
        for rec in records[:2]:
            print(f"     • {rec.get('nome', '?')} — {rec.get('data_obito', '?')}")

        all_results.extend(records)
        inserted = insert_records(records)
        total_inserted += inserted

        processed.add(str(jpeg_path))
        save_progress(processed)

        time.sleep(5)

    # Guardar todos os resultados
    existing = []
    if RESULTS_FILE.exists():
        with open(RESULTS_FILE) as f:
            existing = json.load(f)
    existing.extend(all_results)
    with open(RESULTS_FILE, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*60}")
    print(f"CONCLUÍDO!")
    print(f"Registos extraídos: {len(all_results)}")
    print(f"Inseridos na BD: {total_inserted}")
    print(f"Resultados: {RESULTS_FILE}")
    print(f"BD: {DB_PATH}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
