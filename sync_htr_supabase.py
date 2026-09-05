#!/usr/bin/env python3
"""
Sync HTR results to Supabase pessoas table.
Resume-safe: skips already-synced records.
Only syncs records with valid death record content.

Modes:
  normal:  Sync new HTR files to Supabase (default)
  --update-dates:  Backfill data_obito on existing records with NULL date

Usage:
  python3 sync_htr_supabase.py
  python3 sync_htr_supabase.py --update-dates
  DRY_RUN=1 python3 sync_htr_supabase.py
"""
import os
import sys
import json
import re
import time
from pathlib import Path
from datetime import datetime

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://qljopxbxgflozrcdblrl.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "sb_publishable_-oWYfk9uhb5DIByIe7xUhw_jb_touP1")

INPUT_DIR = Path(os.environ.get("INPUT_DIR", "/home/pxtkhw/projetos/obitos/output/htr_text"))
METADATA_DIR = Path(os.environ.get("METADATA_DIR", "/home/pxtkhw/projetos/obitos/output/htr_metadata"))
CELORICO_JSON = Path(os.environ.get("CELORICO_JSON", "/home/pxtkhw/projetos/obitos/output/data/celorico_completo.json"))
FREGUESIA_MAPPING_JSON = Path(os.environ.get("FREGUESIA_MAPPING_JSON", "/home/pxtkhw/projetos/obitos/output/data/freguesia_file_mapping.json"))
STATE_FILE = Path(os.environ.get("STATE_FILE", "/home/pxtkhw/projetos/obitos/output/sync_htr_state.json"))

# Original digitization source — kept as a link so we don't store images locally.
DIGITARQ_BASE = os.environ.get("DIGITARQ_BASE", "https://digitarq.arquivos.pt")
def imagem_url_for(file_id):
    return f"{DIGITARQ_BASE}/rdigital/dissemination?fileId={file_id}"

DRY_RUN = os.environ.get("DRY_RUN", "").lower() in ("1", "true", "yes")

# When the Supabase `pessoas` schema has been migrated (see
# migrations/add_pessoa_relation_columns.sql), set SYNC_RELATIONS=1 to also
# persist the structured father/mother/spouse relations. Off by default so the
# sync keeps working against the current schema (which lacks those columns).
SYNC_RELATIONS = os.environ.get("SYNC_RELATIONS", "").lower() in ("1", "true", "yes")

UPDATE_DATES = "--update-dates" in sys.argv

# Portuguese number-word parsing tables
DAY_NUMBERS = {
    'hum': 1, 'um': 1, 'uma': 1,
    'dois': 2, 'duas': 2, 'tres': 3, 'três': 3,
    'quatro': 4, 'cinco': 5, 'seis': 6, 'sete': 7, 'oito': 8, 'nove': 9,
    'dez': 10, 'onze': 11, 'doze': 12, 'treze': 13,
    'catorze': 14, 'quatorze': 14, 'quinze': 15,
    'dezasseis': 16, 'dezaseis': 16, 'dezesseis': 16,
    'dezassete': 17, 'dezasete': 17, 'dezessete': 17,
    'dezoito': 18, 'dezanove': 19, 'dezenove': 19,
    'vinte': 20, 'trinta': 30,
}
TENS = {'vinte': 20, 'trinta': 30}
MONTH_MAP = {
    'janeiro': '01', 'fevereiro': '02', 'março': '03', 'abril': '04',
    'maio': '05', 'junho': '06', 'julho': '07', 'agosto': '08',
    'setembro': '09', 'outubro': '10', 'novembro': '11', 'dezembro': '12',
    'jan': '01', 'fev': '02', 'mar': '03', 'abr': '04',
    'mai': '05', 'jun': '06', 'jul': '07', 'ago': '08',
    'set': '09', 'out': '10', 'nov': '11', 'dez': '12',
    'mayo': '05', 'may': '05', 'septembro': '09',
}
YEAR_NUMBERS = {
    'mil': 1000, 'cento': 100, 'centos': 100, 'centtos': 100,
    'duzentos': 200, 'duzentas': 200, 'trezentos': 300, 'trezentas': 300,
    'quatrocentos': 400, 'quatrocentas': 400, 'quinhentos': 500, 'quinhentas': 500,
    'seiscentos': 600, 'seiscentas': 600,
    'setecentos': 700, 'settecentos': 700,
    'oitocentos': 800, 'outocentos': 800,
    'novecentos': 900, 'cem': 100,
    'noventa': 90, 'oitenta': 80, 'setenta': 70, 'sessenta': 60,
    'cinquenta': 50, 'cincoenta': 50, 'sincoenta': 50,
    'quarenta': 40, 'trinta': 30, 'vinte': 20,
    'dezanove': 19, 'dezenove': 19, 'dezoito': 18,
    'dezassete': 17, 'dezessete': 17, 'dezasseis': 16, 'dezesseis': 16,
    'quinze': 15, 'catorze': 14, 'treze': 13, 'doze': 12, 'onze': 11,
    'dez': 10, 'nove': 9, 'oito': 8, 'sete': 7, 'seis': 6,
    'cinco': 5, 'quatro': 4, 'tres': 3, 'três': 3,
    'dois': 2, 'duas': 2, 'hum': 1, 'um': 1, 'uma': 1,
}
HUNDREDS_PREFIX = {
    'sete': 'setecentos', 'sette': 'settecentos',
    'oito': 'oitocentos', 'outo': 'outocentos',
    'nove': 'novecentos', 'seis': 'seiscentos',
    'dous': 'duzentos', 'cinco': 'quinhentos',
    'quatro': 'quatrocentos', 'tres': 'trezentos', 'três': 'trezentos',
}

# Death record keywords (Portuguese)
DEATH_KEYWORDS = [
    'obito', 'faleceu', 'morreu', 'morreu', 'falec', 'morte',
    'sepult', 'enterro', 'assento', 'registo', 'livro',
    'dez', 'jan', 'fev', 'mar', 'abr', 'mai', 'jun',
    'jul', 'ago', 'set', 'out', 'nov', 'dez',
    'janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho',
    'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro'
]

def load_state():
    if STATE_FILE.exists():
        with open(STATE_FILE) as f:
            return json.load(f)
    return {"synced_ids": [], "errors": 0, "last_run": None, "filtered_out": 0}

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)

def is_good_quality(raw_text):
    if not raw_text:
        return False
    text_lower = raw_text.lower()
    special_char_ratio = len(re.findall(r'[^a-zA-ZÀ-Úà-ú\s\.,;:\-]', raw_text)) / max(len(raw_text), 1)
    if special_char_ratio > 0.15:
        return False
    death_keywords = re.compile(r'obito|faleceu|morreu|sepult|enterro')
    if not death_keywords.search(text_lower):
        return False
    if len(raw_text.strip()) < 50:
        return False
    has_capitalized_name = re.search(r'\b[A-ZÀ-Ú][a-zà-ú]+(?:\s+de\s+[A-ZÀ-Ú][a-zà-ú]+)+', raw_text)
    if not has_capitalized_name:
        return False
    return True

def build_file_to_freguesia():
    """Build mapping from file_id to freguesia. Uses combined mapping if available,
    falls back to celorico_completo.json, and enriches with BIRT/MARR via doc listings."""
    mapping = {}
    # 1. Try combined mapping file (includes all freguesias DEAT)
    if FREGUESIA_MAPPING_JSON.exists():
        with open(FREGUESIA_MAPPING_JSON) as f:
            data = json.load(f)
        mapping.update(data.get("mapping", {}))
    # 2. Fallback: load from celorico_completo.json
    if not mapping and CELORICO_JSON.exists():
        with open(CELORICO_JSON) as f:
            data = json.load(f)
        for doc in data.get("documentos", []):
            freg = doc.get("freguesia", "")
            for img in doc.get("imagens", []):
                fid = str(img.get("file_id", ""))
                if fid:
                    mapping[fid] = freg
    # 3. Enrich with BIRT/MARR via doc_file_listings + inventory (Celorico)
    try:
        listings_path = Path("output/data/doc_file_listings.json")
        invent_path = Path("output/celorico_casamentos_batismos.json")
        if listings_path.exists() and invent_path.exists():
            with open(listings_path) as f:
                listings = json.load(f)
            with open(invent_path) as f:
                invent = json.load(f)
            doc_to_freg = {}
            for doc in invent:
                url = doc.get("url_info", "")
                if "documentDetails/" in url:
                    doc_id = url.split("documentDetails/")[1]
                    doc_to_freg[doc_id] = doc.get("freguesia", "")
                elif "fileViewer/" in url:
                    doc_id = url.split("fileViewer/")[1].split("?")[0]
                    doc_to_freg[doc_id] = doc.get("freguesia", "")
            for doc_id, freg in doc_to_freg.items():
                if doc_id in listings:
                    for entry in listings[doc_id]:
                        fid = str(entry.get("id", ""))
                        if fid and fid not in mapping:
                            mapping[fid] = freg
    except Exception:
        pass
    return mapping

def is_valid_death_record(raw_text):
    """Check if HTR text looks like a valid death record."""
    if not raw_text or len(raw_text) < 50:
        return False, "too_short"
    
    text_lower = raw_text.lower()
    
    # Must have death-related keywords
    keyword_count = sum(1 for kw in DEATH_KEYWORDS if kw in text_lower)
    if keyword_count < 2:
        return False, "no_death_keywords"
    
    # Must have at least one capitalized name (Portuguese naming)
    has_name = re.search(r'\b[A-ZÀ-Ú][a-zà-ú]+(?:\s+de\s+[A-ZÀ-Ú][a-zà-ú]+)+', raw_text)
    if not has_name:
        return False, "no_valid_name"
    
    # Check for garbled text (too many special chars or repeated patterns)
    special_char_ratio = len(re.findall(r'[^a-zA-ZÀ-Úà-ú\s\.,;:\-]', raw_text)) / len(raw_text)
    if special_char_ratio > 0.15:
        return False, "garbled_text"
    
    return True, "valid"

def extract_persons(raw_text):
    """Extract person names from HTR text of death records."""
    persons = []
    text = ' '.join(raw_text.split())
    
NOISE_WORDS = {
    'villa', 'vila', 'igreja', 'igrejas', 'capella', 'capelas', 'collegiada',
    'bispado', 'arquivo', 'distrito', 'freguesia', 'freguesias',
    'cemiterio', 'cemitério', 'sepultura', 'sepultamento', 'sepultado',
    'assento', 'assentos', 'livro', 'livros', 'folhas', 'folha',
    'defuntos', 'morte', 'morto',
    'sacramento', 'sacramentos', 'batismo', 'casamento', 'obito', 'óbito',
    'testamento', 'testamentos',
    'eram', 'desta', 'deste', 'desse', 'dessa', 'nesta', 'neste',
    'era', 'anno', 'annos', 'anos', 'idade', 'meses', 'dias',
    'janeiro', 'fevereiro', 'março', 'marco', 'abril', 'maio', 'junho',
    'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro',
    'santa', 'santo', 'santos', 'sancta', 'senhora', 'senhor',
    'padre', 'reverendo', 'vigario', 'vigário', 'cura', 'prior',
    'arcipreste', 'beneficiado', 'mordomo', 'juiz', 'escrivão',
    'encomendado', 'provisor', 'vigairo',
    'matriz', 'collegio', 'colégio', 'convento', 'mosteiro',
    'ermida', 'cathedral', 'catedral', 'parochia', 'paróquia',
    'oratorio', 'oratório', 'capellao', 'capelão', 'sacristia',
    'celorico', 'celoricense', 'beirense', 'guarda',
    'portugal', 'reinado', 'el-rei', 'el rei',
    'magestade', 'majestade',
    'mes', 'mez', 'mezes',
    'irmaos', 'irmaãs', 'irmao', 'irmaã',
    'neto', 'neta', 'netos', 'netas',
    'sobrinho', 'sobrinha', 'sobrinhos', 'sobrinhas',
    'tio', 'tia', 'tios', 'tias',
    'avo', 'avos', 'avó', 'avô',
    'cunhado', 'cunhada', 'cunhados', 'cunhadas',
    'genro', 'nora',
    'padrasto', 'madrasta',
    'afilhado', 'afilhada', 'afilhados', 'afilhadas',
    'compadre', 'comadre',
    'vizinho', 'vizinha', 'vizinhos', 'vizinhas',
    'proximo', 'proxima', 'proximos', 'proximas',
    'familia', 'família', 'familias', 'famílias',
    'alma', 'almas',
    'domicilio', 'domicílio',
    'função', 'funcao',
    'serviço', 'servicos',
}

def clean_name(parts):
    cleaned = []
    for part in parts:
        part_lower = part.lower().strip('.,;:')
        if part_lower not in NOISE_WORDS and len(part) > 2:
            cleaned.append(part)
    return cleaned

TITLE_WORDS = {'d', 'don', 'dom', 'doña', 'dona', 'sr', 'sra', 's', 'snr', 'snra'}

def _is_valid_calendar_date(y, m, d):
    """Check if (y, m, d) is a valid calendar date (catches Feb 29 on non-leap years, etc.)."""
    days_in_month = [0, 31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    if m == 2 and y % 4 == 0 and (y % 100 != 0 or y % 400 == 0):
        return d <= 29
    return 1 <= d <= days_in_month[m]

def normalize_death_date(value):
    """Normalize a death_date from the structured `deceased` field.

    Accepts 'YYYY-MM-DD', 'YYYY-M-D', 'DD/MM/YYYY', 'D-M-YYYY' (or with
    month names). Returns 'YYYY-MM-DD' or None if unparseable/invalid.
    """
    if not value or not isinstance(value, str):
        return None
    v = value.strip()
    if not v:
        return None

    # ISO-like: YYYY-MM-DD or YYYY-M-D
    m = re.match(r'^(\d{4})-(\d{1,2})-(\d{1,2})$', v)
    if m:
        y, mo, d = (int(x) for x in m.groups())
        if 1500 <= y <= 2100 and 1 <= mo <= 12 and _is_valid_calendar_date(y, mo, d):
            return f"{y:04d}-{mo:02d}-{d:02d}"
        return None

    # DD/MM/YYYY or D/M/YYYY
    m = re.match(r'^(\d{1,2})/(\d{1,2})/(\d{4})$', v)
    if m:
        d, mo, y = (int(x) for x in m.groups())
        if 1500 <= y <= 2100 and 1 <= mo <= 12 and _is_valid_calendar_date(y, mo, d):
            return f"{y:04d}-{mo:02d}-{d:02d}"
        return None

    # D? MES? YYYY or D? de MES? de YYYY (extended pattern of extract_date)
    return extract_date(v)

def extract_persons_from_deceased(deceased_list):
    """Convert structured `deceased` entries (from Gemini) into person dicts.

    Each entry may have: name, death_date, age, father, mother, spouse.
    The relations (father/mother/spouse) are mapped to the DB column names
    `pai`/`mae`/`conjuge` so they can be persisted once the schema migration
    `migrations/add_pessoa_relation_columns.sql` is applied. They are only
    pushed to Supabase when SYNC_RELATIONS=1 (see main()).
    """
    persons = []
    if not isinstance(deceased_list, list):
        return persons
    for entry in deceased_list:
        if not isinstance(entry, dict):
            continue
        name = (entry.get("name") or entry.get("nome") or "").strip()
        if not name:
            continue
        # Drop leading honorifics/titles before splitting into given/surname.
        parts = [p for p in name.split() if p.lower().strip('.,;:') not in TITLE_WORDS]  # noqa
        if not parts:
            continue
        # Gemini usually returns English relation keys, but some responses use
        # Portuguese variants (e.g. `cônjuge` for spouses, `pai`/`mãe`). Accept
        # both so relation yield does not silently drop on key drift.
        pai = (entry.get("father") or entry.get("pai") or "").strip()[:100]
        mae = (entry.get("mother") or entry.get("mae") or "").strip()[:100]
        conjuge = (entry.get("spouse") or entry.get("conjuge") or entry.get("cônjuge") or "").strip()[:100]
        if len(parts) == 1:
            persons.append({
                "nome": parts[0][:100],
                "sobrenome": "",
                "death_date": entry.get("death_date"),
                "age": entry.get("age"),
                "pai": pai,
                "mae": mae,
                "conjuge": conjuge,
            })
            continue
        sobrenome = parts[-1][:50]
        nome = " ".join(parts[:-1])[:100]
        persons.append({
            "nome": nome,
            "sobrenome": sobrenome,
            "death_date": entry.get("death_date"),
            "age": entry.get("age"),
            "pai": pai,
            "mae": mae,
            "conjuge": conjuge,
        })
    return persons

def extract_detalhes(transcription):
    """Extract rich details (idade, causa, naturalidade, numero_assento, etc.) from transcription.
    Works on already-saved transcriptions, no Gemini needed. Covers NotebookLM example."""
    if not transcription:
        return {}
    t = ' '.join(transcription.split())
    out = {}
    # idade: dígitos OU por extenso (sessenta, setenta, etc.)
    m = re.search(r'com\s+(\d{1,3})\s+ann?os', t, re.I)
    if m:
        try: out['idade'] = int(m.group(1))
        except: pass
    else:
        # tenta por extenso: "com sessenta anos", "de oitenta annos", "com setenta e dois annos"
        mapa = {'um':1,'dois':2,'tres':3,'três':3,'quatro':4,'cinco':5,'seis':6,'sete':7,'oito':8,'nove':9,'dez':10,'onze':11,'doze':12,'treze':13,'catorze':14,'catorze':14,'quinze':15,'dezasseis':16,'dezaseis':16,'dezassete':17,'dezassete':17,'dezoito':18,'dezanove':19,'dezanove':19,'vinte':20,'trinta':30,'quarenta':40,'cinquenta':50,'sessenta':60,'setenta':70,'oitenta':80,'noventa':90,'cem':100,'cento':100}
        m2 = re.search(r'com\s+([a-zà-ú\s]+?)\s+ann?os', t, re.I)
        if m2:
            palavras = re.findall(r'[a-zà-ú]+', m2.group(1).lower())
            total = 0
            for p in palavras:
                if p in mapa:
                    total += mapa[p]
                elif p in ('e',):
                    continue
            if 1 <= total <= 120:
                out['idade'] = total
    # Fallback idade escrita por extenso already in deceased.age
    m = re.search(r'(morte\s+repentina|faleceu\s+de\s+[^,\.]{3,50})', t, re.I)
    if m:
        out['causa_morte'] = m.group(1).strip()[:120]
    m = re.search(r'natural(?:\s+e\s+morador)?\s+(?:da|de|na)\s+([^,\.\n]{3,60})', t, re.I)
    if m:
        out['naturalidade'] = m.group(1).strip()[:120]
    m = re.search(r'assento\s+n\.?º?\s*(\d+)', t, re.I)
    if m:
        out['numero_assento'] = m.group(1).strip()[:20]
    # hora: "pelas 7 horas da noite (19h)", "às 3 horas da tarde"
    m = re.search(r'pelas?\s+(\d{1,2})\s+horas?\s+da\s+(manhã|tarde|noite)', t, re.I)
    if m:
        out['hora_obito'] = f"{m.group(1)}h da {m.group(2)}"[:30]
    else:
        m = re.search(r'às?\s+(\d{1,2})\s+horas?', t, re.I)
        if m:
            out['hora_obito'] = f"{m.group(1)}h"[:20]
    # profissao: "moleira", "pedreiro", etc. (palavra após profissão comum)
    m = re.search(r'\b(moleir[ao]|pedreiro|proprietári[ao]|lavrador|jornaleir[ao]|sapateiro|alfaiate)\b', t, re.I)
    if m:
        out['profissao'] = m.group(1).lower()[:50]
    # estado_civil
    m = re.search(r'\b(viúv[ao]|casad[ao]|solteir[ao]|menor|inocente)\b', t, re.I)
    if m:
        out['estado_civil'] = m.group(1).lower()[:30]
    # sacramentos
    if re.search(r'recebeu\s+os\s+sacramentos', t, re.I):
        out['sacramentos'] = 'recebeu os sacramentos'
    elif re.search(r'sem\s+receber\s+sacramentos|sem\s+sacramentos', t, re.I):
        out['sacramentos'] = 'sem sacramentos'
    # testamento
    if re.search(r'não\s+fez\s+testamento', t, re.I):
        out['testamento'] = 'não fez testamento'
    elif re.search(r'fez\s+testamento', t, re.I):
        out['testamento'] = 'fez testamento'
    # sepultamento
    m = re.search(r'sepultad[ao]\s+no\s+([^,\.\n]{5,60}cemit[ée]rio[^,\.\n]{0,40})', t, re.I)
    if m:
        out['local_sepultamento'] = m.group(1).strip()[:120]
    else:
        m2 = re.search(r'sepultad[ao]\s+([^,\.\n]{5,80})', t, re.I)
        if m2: out['local_sepultamento'] = m2.group(1).strip()[:120]
    # assinatura: "O Pároco, João de Andrade Sena"
    m = re.search(r'(?:O\s+)?(?:P[aá]roco|Vig[aá]rio|Prior|Cura)\s+([^,\n]{3,50})', t, re.I)
    if m: out['assinatura'] = m.group(1).strip()[:80]
    return out

def extract_persons(raw_text):
    """Extract person names from HTR text - STRICT mode."""
    if not raw_text or len(raw_text.strip()) < 50:
        return []
    
    persons = []
    text = ' '.join(raw_text.split())
    
    def try_add_name(parts):
        cleaned = clean_name(parts)
        if len(cleaned) >= 2:
            nome = ' '.join(cleaned[:-1])[:100]
            apelido = cleaned[-1][:50]
            if nome and apelido and nome[0].isupper() and apelido[0].isupper():
                persons.append({"nome": nome, "sobrenome": apelido})
                return True
        return False
    
    # 1. Very strict pattern: D. Nome (must have full name after D.)
    names_d = re.findall(r'D\.\s+([A-ZÀ-Ú][a-zà-ú]+(?:\s+(?:de\s+|da\s+|do\s+)?[A-ZÀ-Ú][a-zà-ú]+){1,4})', text)
    for name in names_d:
        if try_add_name(name.split()):
            return persons[:1]
    
    # 2. Obito/Oficio/Assento de + Name
    names_obito = re.findall(r'(?:Obito|Oficio|Assento|Livro)\s+(?:de|da|do)\s+([A-ZÀ-Ú][a-zà-ú]+(?:\s+(?:de\s+|da\s+|do\s+)?[A-ZÀ-Ú][a-zà-ú]+){1,3})', text)
    for name in names_obito:
        if try_add_name(name.split()):
            return persons[:1]
    
    # 3. Priest titles + Name
    titles = r'(?:Padre|Reverendo(?:\s+Padre)?)\s+([A-ZÀ-Ú][a-zà-ú]+(?:\s+(?:de\s+|da\s+|do\s+)?[A-ZÀ-Ú][a-zà-ú]+){1,3})'
    names_priest = re.findall(titles, text)
    for name in names_priest:
        if try_add_name(name.split()):
            return persons[:1]
    
    # 4. Title + Name (Encomendado, Vigario, Prior, etc.)
    titles2 = r'(?:Encomendado|Vigario|Vigário|Cura|Prior|Arcipreste|Beneficiado|Mordomo|Juiz|Escrivão|Provisor)\s+([A-ZÀ-Ú][a-zà-ú]+(?:\s+(?:de\s+|da\s+|do\s+)?[A-ZÀ-Ú][a-zà-ú]+){1,3})'
    names_title = re.findall(titles2, text)
    for name in names_title:
        if try_add_name(name.split()):
            return persons[:1]
    
    # 5. mulher/filho/filha de + Name
    names_family = re.findall(r'(?:mulher|filho|filha|viuva?|sobrinha?|afilhada?|sobrinho|afilhado)\s+de\s+([A-ZÀ-Ú][a-zà-ú]+(?:\s+(?:de\s+|da\s+|do\s+)?[A-ZÀ-Ú][a-zà-ú]+){1,2})', text)
    for name in names_family[:1]:
        if try_add_name(name.split()):
            return persons[:1]
    
    # 6. meu/minha + relationship + Name
    names_family2 = re.findall(r'(?:meu|minha)\s+(?:sobrinho|sobrinha|afilhado|afilhada|filho|filha|irmao|irmaã|pai|mae)\s+([A-ZÀ-Ú][a-zà-ú]+(?:\s+(?:de\s+|da\s+|do\s+)?[A-ZÀ-Ú][a-zà-ú]+){1,2})', text)
    for name in names_family2[:1]:
        if try_add_name(name.split()):
            return persons[:1]
    
    # 7. Name de Name (surname pattern) - require at least 2 "de" connections
    names_surname = re.findall(r'(?:^|[\s,;])([A-ZÀ-Ú][a-zà-ú]+(?:\s+de\s+[A-ZÀ-Ú][a-zà-ú]+){1,2})', text)
    for name in names_surname[:1]:
        if try_add_name(name.split()):
            return persons[:1]
    
    # 8. death event patterns with old spelling
    names_death = re.findall(r'(?:faleceo|falleceu|falece|faleçeo|morreo|morreu)\s+(?:o|a)?\s*([A-ZÀ-Ú][a-zà-ú]+(?:\s+(?:de\s+|da\s+|do\s+)?[A-ZÀ-Ú][a-zà-ú]+){1,2})', text)
    for name in names_death[:1]:
        if try_add_name(name.split()):
            return persons[:1]
    
    return persons[:1]

def parse_day_word(text):
    text = text.strip().lower()
    if text in DAY_NUMBERS:
        return DAY_NUMBERS[text]
    m = re.match(r'(vinte|trinta)\s+e\s+(hum|um|dois|tres|três|quatro|cinco|seis|sete|oito|nove)', text)
    if m:
        return TENS[m.group(1)] + DAY_NUMBERS.get(m.group(2), 0)
    return None

def parse_year_words(text):
    text = text.strip().lower()
    text = re.sub(r'\s+ann?os?\s*$', '', text)
    def combine_hundreds(m):
        return HUNDREDS_PREFIX.get(m.group(1).lower(), m.group(1) + 'centos')
    text = re.sub(
        r'\b(duzentos|duzentas|trezentos|trezentas|quatrocentos|quatrocentas|'
        r'quinhentos|quinhentas|seiscentos|seiscentas|setecentos|settecentos|'
        r'oitocentos|outocentos|novecentos|sete|sette|oito|outo|nove|seis|'
        r'dous|cinco|quatro|tres|três)\s+cent[eo]s?\b',
        combine_hundreds, text
    )
    words = re.findall(r'[a-zà-ú]+', text)
    year = 0
    for w in words:
        if w == 'e':
            continue
        if w in YEAR_NUMBERS:
            year += YEAR_NUMBERS[w]
    if 1500 <= year <= 2100:
        return year
    return None

def extract_date(raw_text):
    """Extract death date from HTR text using multiple patterns."""
    text = raw_text.strip()
    # Focus on transcription portion (skip Gemini's document summary)
    m_trans = re.search(r'---TRANSCRIPTION---(.+)', text, re.DOTALL | re.IGNORECASE)
    if m_trans:
        text = m_trans.group(1)

    # Pattern A1: "Aos/Em/Em os XX dias do mes/mez de MONTH [de] YEAR"
    pat_a1 = re.compile(
        r'(?:aos|em\s+os|em)\s+'
        r'([\w\s]+?)\s+dias?\s+do\s+mes\s+de\s+'
        r'(\w+)[\s,]*(?:de\s+)?'
        r'([\w\s]+?)(?:\s+ann?os?|\s+falece[ou]|\s+foi|\s+sepult|$)',
        re.IGNORECASE
    )
    m = pat_a1.search(text)
    if m:
        day = parse_day_word(m.group(1))
        month = MONTH_MAP.get(m.group(2).lower().strip())
        year = parse_year_words(m.group(3))
        if day and month and year and _is_valid_calendar_date(year, int(month), day):
            return f"{year}-{month}-{day:02d}"

    # Pattern A2: "Aos/Em XX de MONTH de YEAR"
    pat_a2 = re.compile(
        r'(?:aos|em\s+os|em)\s+'
        r'([\w\s]+?)\s+de\s+'
        r'(\w+)\s+de\s+'
        r'([\w\s]+?)(?:\s+ann?os?|\s+falece[ou]|\s+foi|\s+sepult|$)',
        re.IGNORECASE
    )
    m = pat_a2.search(text)
    if m:
        day = parse_day_word(m.group(1))
        month = MONTH_MAP.get(m.group(2).lower().strip())
        year = parse_year_words(m.group(3))
        if day and month and year and _is_valid_calendar_date(year, int(month), day):
            return f"{year}-{month}-{day:02d}"

    # Pattern B: "no dia XX de MONTH de YEAR"
    pat_b = re.compile(
        r'(?:no\s+)?dia\s+'
        r'([\w\s]+?)\s+de\s+'
        r'(\w+)\s+de\s+'
        r'([\w\s]+?)(?:\s+ann?os?|\s+falece[ou]|\s+foi|\s+sepult|$)',
        re.IGNORECASE
    )
    m = pat_b.search(text)
    if m:
        day = parse_day_word(m.group(1))
        month = MONTH_MAP.get(m.group(2).lower().strip())
        year = parse_year_words(m.group(3))
        if day and month and year and _is_valid_calendar_date(year, int(month), day):
            return f"{year}-{month}-{day:02d}"

    # Pattern D: "XX de Month de YYYY" (numeric)
    pat_d = re.compile(
        r'(\d{1,2})\s+de\s+'
        r'(janeiro|fevereiro|março|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro'
        r'|jan|fev|mar|abr|mai|jun|jul|ago|set|out|nov|dez|mayo|may|septembro)'
        r'\s+de\s+(\d{4})',
        re.IGNORECASE
    )
    m = pat_d.search(text)
    if m:
        day = int(m.group(1))
        month = MONTH_MAP.get(m.group(2).lower().strip())
        year = int(m.group(3))
        if month and _is_valid_calendar_date(year, int(month), day):
            return f"{year:04d}-{month}-{day:02d}"

    return None

def supabase_request(method, path, data=None):
    """Make a request to Supabase REST API."""
    import urllib.request
    import urllib.error
    
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    headers = {
        "Content-Type": "application/json",
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Prefer": "return=minimal",
    }
    
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            if resp.status in (200, 201, 204):
                return {"status": "success"}
            return {"status": "error", "code": resp.status}
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:300]
        return {"status": "error", "code": e.code, "body": body}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def fetch_paginated(select, base_filter="file_id=not.is.null", order="id.asc",
                    page=1000, timeout=30):
    """Fetch all rows from `pessoas` paginating past Supabase's 1000-row cap.

    Returns a flat list of dicts. Used by every backfill/sync routine so the
    pagination logic lives in exactly one place (DRY + easy to test). A network
    error mid-stream stops pagination and returns whatever was collected so far
    instead of crashing the whole run.
    """
    import urllib.request
    import urllib.error

    rows = []
    offset = 0
    while True:
        url = (f"{SUPABASE_URL}/rest/v1/pessoas"
               f"?select={select}&{base_filter}"
               f"&limit={page}&offset={offset}&order={order}")
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
        }
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                batch = json.loads(resp.read())
        except Exception:
            break
        if not batch:
            break
        rows.extend(batch)
        if len(batch) < page:
            break
        offset += page
    return rows

def get_synced_file_ids():
    """Get file_ids already in Supabase (paginated — Supabase caps at 1000/query)."""
    data = fetch_paginated("file_id", base_filter="file_id=not.is.null",
                           order="file_id.asc")
    return set(str(r["file_id"]) for r in data if r.get("file_id"))

def build_url_patch(rec):
    """Build the {"imagem_url": ...} patch for a record, or None if nothing to do.

    Pure, network-free helper used by `backfill_url`. Returns None when the
    record has no file_id or when imagem_url is already set to the expected
    digitarq dissemination link (so we skip needless writes).
    """
    file_id = rec.get("file_id")
    if not file_id:
        return None
    new_url = imagem_url_for(file_id)
    existing = rec.get("imagem_url")
    if existing and existing == new_url:
        return None
    return {"imagem_url": new_url}


def backfill_url():
    """Backfill imagem_url (link to digitarq) on existing records that lack it."""
    import urllib.request
    import urllib.error

    print("=== Backfill imagem_url on existing records ===\n")

    updated = 0
    skipped = 0
    errors = 0
    total = 0

    records = fetch_paginated("id,file_id,imagem_url")
    total = len(records)
    for i, rec in enumerate(records):
        patch_data = build_url_patch(rec)
        if patch_data is None:
            skipped += 1
            continue
        if DRY_RUN:
            print(f"  Would set record {rec['id']}: imagem_url = {patch_data['imagem_url']}")
            updated += 1
        else:
            result = supabase_request("PATCH", f"pessoas?id=eq.{rec['id']}", patch_data)
            if result["status"] == "success":
                updated += 1
            else:
                # Transient errors (5xx, network) are counted and the backfill
                # continues with the remaining records instead of aborting.
                print(f"  Error updating record {rec['id']}: {result}")
                errors += 1

    print(f"\n=== Backfill URL Complete ===")
    print(f"Total scanned: {total}")
    print(f"Updated: {updated}")
    print(f"Skipped (already set): {skipped}")
    print(f"Errors: {errors}")

def update_dates():
    """Backfill data_obito on existing records where it's NULL."""
    import urllib.request
    import urllib.error

    print("=== Backfill data_obito on existing records ===\n")

    # Get all records with file_id and NULL data_obito (paginated)
    records = fetch_paginated(
        "id,file_id,nome,sobrenome",
        base_filter="file_id=not.is.null&data_obito=is.null",
    )

    print(f"Records with NULL data_obito: {len(records)}")
    if not records:
        print("Nothing to update.")
        return

    updated = 0
    errors = 0
    skipped_no_file = 0
    skipped_no_date = 0

    for i, rec in enumerate(records):
        file_id = rec.get("file_id")
        if not file_id:
            skipped_no_file += 1
            continue

        json_path = INPUT_DIR / f"{file_id}.json"
        if not json_path.exists():
            skipped_no_file += 1
            continue

        with open(json_path) as f:
            data = json.load(f)
        raw_text = data.get("raw_text", "")

        # Check if it's a valid death record (same filter as normal sync)
        is_valid, reason = is_valid_death_record(raw_text)
        if not is_valid:
            continue

        death_date = extract_date(raw_text)
        if not death_date:
            skipped_no_date += 1
            if (i + 1) % 50 == 0:
                print(f"  Progress: {i+1}/{len(records)} (updated: {updated}, no_date: {skipped_no_date}, errors: {errors})")
            continue

        if DRY_RUN:
            print(f"  Would update record {rec['id']} ({rec['nome']}): data_obito = {death_date}")
            updated += 1
        else:
            patch_url = f"{SUPABASE_URL}/rest/v1/pessoas?id=eq.{rec['id']}"
            patch_data = {"data_obito": death_date}
            result = supabase_request("PATCH", f"pessoas?id=eq.{rec['id']}", patch_data)
            if result["status"] == "success":
                updated += 1
                print(f"  ✓ Updated record {rec['id']} ({rec['nome']}): {death_date}")
            else:
                print(f"  ✗ Error updating record {rec['id']}: {result}")
                errors += 1

        if (i + 1) % 10 == 0:
            print(f"  Progress: {i+1}/{len(records)} (updated: {updated}, no_date: {skipped_no_date}, errors: {errors})")

    print(f"\n=== Update Complete ===")
    print(f"Updated: {updated}")
    print(f"No date found: {skipped_no_date}")
    print(f"Errors: {errors}")

BACKFILL_URL = "--backfill-url" in sys.argv
BACKFILL_RELATIONS = "--backfill-relations" in sys.argv

def build_relation_patch(persons):
    """Build the {pai,mae,conjuge} patch dict for the first deceased person.

    Pure, network-free helper used by `backfill_relations`. Returns None when
    there are no persons or when all three relation fields are empty (nothing to
    write). Relations are already truncated to 100 chars by
    `extract_persons_from_deceased`.
    """
    if not persons:
        return None
    person = persons[0]
    patch_data = {
        "pai": person.get("pai", ""),
        "mae": person.get("mae", ""),
        "conjuge": person.get("conjuge", ""),
    }
    if not any(patch_data.values()):
        return None
    return patch_data


def backfill_relations():
    """Backfill pai/mae/conjuge on existing records by re-reading HTR files."""
    import urllib.request
    import urllib.error

    print("=== Backfill Relations (pai, mae, conjuge) on existing records ===\n")
    if not SYNC_RELATIONS:
        print("Error: SYNC_RELATIONS must be enabled to backfill relations.")
        return

    updated = 0
    errors = 0
    total = 0

    records = fetch_paginated("id,file_id")
    total = len(records)
    for i, rec in enumerate(records):
            file_id = rec.get("file_id")
            if not file_id: continue
            
            json_path = INPUT_DIR / f"{file_id}.json"
            if not json_path.exists(): continue
            
            with open(json_path) as f:
                data = json.load(f)
            
            deceased = data.get("deceased")
            if not isinstance(deceased, list) or not deceased:
                continue
            
            # Use same logic as sync to get persons
            persons = extract_persons_from_deceased(deceased)
            if not persons: continue
            
            # For backfill, we assume 1 person per file_id for now
            # (matches current sync logic for death records)
            patch_data = build_relation_patch(persons)
            if patch_data is None:
                continue

            if DRY_RUN:
                print(f"  Would update {rec['id']}: {patch_data}")
                updated += 1
            else:
                result = supabase_request("PATCH", f"pessoas?id=eq.{rec['id']}", patch_data)
                if result["status"] == "success":
                    updated += 1
                else:
                    msg = str(result).lower()
                    # A 400 mentioning "column" means the migration was not
                    # applied yet — there is no point retrying every record.
                    if "column" in msg:
                        print("\n!!! ERROR: Columns 'pai', 'mae' or 'conjuge' not found.")
                        print("Did you run the SQL migration in Supabase SQL Editor?")
                        return
                    # Any other error (transient 5xx, network) is counted and
                    # the backfill continues with the remaining records.
                    print(f"  Error updating {rec['id']}: {result}")
                    errors += 1

    print(f"\n=== Backfill Relations Complete ===")
    print(f"Updated: {updated}")
    print(f"Errors: {errors}")

def main():
    if UPDATE_DATES:
        update_dates()
        return

    if BACKFILL_URL:
        backfill_url()
        return

    if BACKFILL_RELATIONS:
        backfill_relations()
        return

    state = load_state()
    synced = set(state.get("synced_ids", []))
    errors = state.get("errors", 0)
    filtered_out = state.get("filtered_out", 0)
    
    print("Checking Supabase for already-synced records...")
    db_synced = get_synced_file_ids()
    synced.update(db_synced)
    print(f"Already synced in DB: {len(db_synced)}")
    
    file_to_freguesia = build_file_to_freguesia()
    print(f"Loaded freguesia mapping for {len(file_to_freguesia)} files")
    
    json_files = sorted(INPUT_DIR.glob("*.json"))
    to_sync = [f for f in json_files if f.stem not in synced]
    
    print(f"\n=== HTR → Supabase Sync ===")
    print(f"Total HTR files: {len(json_files)}")
    print(f"Already synced: {len(synced)}")
    print(f"To sync: {len(to_sync)}")
    print(f"Dry run: {DRY_RUN}")
    
    if not to_sync:
        print("Nothing to sync.")
        return
    
    synced_count = 0
    filtered_count = 0
    
    for i, json_file in enumerate(to_sync):
        file_id = json_file.stem
        
        try:
            with open(json_file) as f:
                data = json.load(f)
            
            raw_text = data.get("raw_text", "")

            # Prefer structured `deceased`/`baptized` (Gemini JSON) when available
            deceased = data.get("deceased")
            baptized = data.get("baptized")
            record_type = data.get("record_type") or "DEAT"
            structured = False
            persons = []
            # BIRT: baptized (prompt rico 15 campos)
            if isinstance(baptized, list) and baptized and any(isinstance(d, dict) and (d.get("name") or d.get("nome")) for d in baptized):
                for entry in baptized:
                    if not isinstance(entry, dict): continue
                    name = (entry.get("name") or entry.get("nome") or "").strip()
                    if not name: continue
                    parts = [p for p in name.split() if p.lower().strip('.,;:') not in TITLE_WORDS]
                    if not parts: continue
                    pai = (entry.get("father") or entry.get("pai") or "").strip()[:100]
                    mae = (entry.get("mother") or entry.get("mae") or "").strip()[:100]
                    # Campos ricos BIRT para árvore 3 gerações
                    extra = {
                        "avo_paterno": (entry.get("avo_paterno") or "").strip()[:100],
                        "avo_paterna": (entry.get("avo_paterna") or "").strip()[:100],
                        "avo_materno": (entry.get("avo_materno") or "").strip()[:100],
                        "avo_materna": (entry.get("avo_materna") or "").strip()[:100],
                        "legitimidade": (entry.get("legitimidade") or "").strip()[:50],
                        "father_naturalidade": (entry.get("father_naturalidade") or "").strip()[:100],
                        "mother_naturalidade": (entry.get("mother_naturalidade") or "").strip()[:100],
                        "assinatura": (entry.get("assinatura") or "").strip()[:80],
                        "godfather": (entry.get("godfather") or "").strip()[:100],
                        "godmother": (entry.get("godmother") or "").strip()[:100],
                    }
                    base = {"pai": pai, "mae": mae, "conjuge": "", "birth_date": entry.get("birth_date") or entry.get("baptism_date"), "baptism_date": entry.get("baptism_date"), **extra}
                    if len(parts)==1:
                        persons.append({"nome": parts[0][:100], "sobrenome": "", **base})
                    else:
                        persons.append({"nome": " ".join(parts[:-1])[:100], "sobrenome": parts[-1][:50], **base})
                structured = True
                used_structured = True
            elif isinstance(deceased, list) and bool([d for d in deceased if isinstance(d, dict) and (d.get("name") or d.get("nome"))]):
                persons = extract_persons_from_deceased(deceased)
                structured = True
                used_structured = True
            else:
                # Filter: check if valid death record (only for DEAT fallback)
                if record_type == "BIRT":
                    # BIRT without structured data: skip (needs HTR)
                    filtered_count += 1
                    synced.add(file_id)
                    continue
                is_valid, reason = is_valid_death_record(raw_text)
                if not is_valid:
                    filtered_count += 1
                    synced.add(file_id)
                    if (i + 1) % 50 == 0:
                        print(f"Progress: {i+1}/{len(to_sync)} (synced: {synced_count}, filtered: {filtered_count}, errors: {errors})")
                    continue
                persons = extract_persons(raw_text)
                used_structured = False

            if not persons:
                filtered_count += 1
                synced.add(file_id)
                continue

            freguesia = file_to_freguesia.get(file_id, "Celorico da Beira")

            # Rich details from transcription (idade, causa, naturalidade, assento)
            detalhes = extract_detalhes(data.get("transcription") or raw_text)
            for person in persons:
                # Prefer the structured death_date/birth_date; otherwise regex the text.
                if record_type == "BIRT":
                    birth_date = normalize_death_date(person.get("birth_date") or person.get("baptism_date") or "")
                    # fallback to regex if no structured date
                    if not birth_date:
                        birth_date = extract_date(raw_text)
                    record = {
                        "nome": person["nome"],
                        "sobrenome": person.get("sobrenome", ""),
                        "data_nascimento": birth_date,
                        "data_obito": None,
                        "tipo_registo": "BIRT",
                        "freguesia": freguesia,
                        "concelho": "Celorico da Beira",
                        "distrito": "Guarda",
                        "fonte": "HTR Gemini 3 Flash Preview",
                        "imagem_url": imagem_url_for(file_id),
                        "file_id": file_id,
                        "criado_em": datetime.now().isoformat(),
                    }
                else:
                    if used_structured and person.get("death_date"):
                        death_date = normalize_death_date(person["death_date"])
                    else:
                        death_date = extract_date(raw_text)
                    record = {
                        "nome": person["nome"],
                        "sobrenome": person.get("sobrenome", ""),
                        "data_obito": death_date,
                        "tipo_registo": "DEAT",
                        "freguesia": freguesia,
                        "concelho": "Celorico da Beira",
                        "distrito": "Guarda",
                        "fonte": "HTR Gemini 3 Flash Preview",
                        "imagem_url": imagem_url_for(file_id),
                        "file_id": file_id,
                        "criado_em": datetime.now().isoformat(),
                    }
                # Add rich details when available (new columns, safe if not migrated yet)
                for k in ("idade","causa_morte","naturalidade","numero_assento","hora_obito","profissao","estado_civil","sacramentos","testamento","local_sepultamento","assinatura"):
                    if detalhes.get(k) is not None:
                        record[k] = detalhes[k]
                # Age from structured deceased has priority
                if person.get("age") is not None and str(person.get("age")).isdigit():
                    record["idade"] = int(person["age"])
                if SYNC_RELATIONS:
                    for rel_col in ("pai", "mae", "conjuge"):
                        val = (person.get(rel_col) or "").strip()
                        if val:
                            record[rel_col] = val[:100]
                # BIRT extra: 4 avós + legitimidade + naturalidade pais (para árvore 3 gerações)
                if record_type == "BIRT":
                    for col in ("avo_paterno","avo_paterna","avo_materno","avo_materna","legitimidade","naturalidade_pai","naturalidade_mae","assinatura"):
                        # mapping from prompt keys
                        key_map = {"avo_paterno":"avo_paterno","avo_paterna":"avo_paterna","avo_materno":"avo_materno","avo_materna":"avo_materna","legitimidade":"legitimidade","naturalidade_pai":"father_naturalidade","naturalidade_mae":"mother_naturalidade","assinatura":"assinatura"}
                        src = key_map[col]
                        val = (person.get(src) or person.get(col) or "").strip()
                        if val:
                            record[col] = val[:100]
                
                if not DRY_RUN:
                    result = supabase_request("POST", "pessoas", record)
                    if result["status"] == "error":
                        if result.get("code") == 409:
                            synced.add(file_id)
                        else:
                            print(f"  Error inserting {person['nome']}: {result}")
                            errors += 1
                    else:
                        synced.add(file_id)
                        synced_count += 1
                else:
                    synced.add(file_id)
                    synced_count += 1
            
            if (i + 1) % 10 == 0:
                print(f"Progress: {i+1}/{len(to_sync)} (synced: {synced_count}, filtered: {filtered_count}, errors: {errors})")
                state["synced_ids"] = list(synced)
                state["errors"] = errors
                state["filtered_out"] = filtered_count
                save_state(state)
        
        except Exception as e:
            print(f"Error processing {file_id}: {e}")
            errors += 1
    
    state["synced_ids"] = list(synced)
    state["errors"] = errors
    state["filtered_out"] = filtered_count
    state["last_run"] = datetime.now().isoformat()
    save_state(state)
    
    print(f"\n=== Sync Complete ===")
    print(f"Synced: {synced_count} persons")
    print(f"Filtered out (invalid): {filtered_count}")
    print(f"Errors: {errors}")
    print(f"Total in DB: {len(synced)}")

if __name__ == "__main__":
    main()
