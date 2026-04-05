"""
Parsing de texto extraído por OCR para identificar nomes, números de registo e datas.
"""
import re
import os

import config


# Padrões regex para extrair informação
# Nomes portugueses típicos em registos de óbito
NAME_PATTERNS = [
    # "Óbito de [Nome]" ou "Faleceu [Nome]"
    r"(?:óbito|faleceu|falecimento)\s+(?:de\s+)?([A-ZÁÀÂÃÉÈÊÍÏÓÔÕÖÚÜÑÇ][a-záàâãéèêíïóôõöúüñçç]+(?:\s+(?:de|da|do|dos|das|e|em|no|na|por|com|sem))?s?\s+[A-ZÁÀÂÃÉÈÊÍÏÓÔÕÖÚÜÑÇ][a-záàâãéèêíïóôõöúüñç]+)+)",
    # "[Nome], [idade]"
    r"([A-ZÁÀÂÃÉÈÊÍÏÓÔÕÖÚÜÑÇ][a-záàâãéèêíïóôõöúüñç]+(?:\s+(?:de|da|do|dos|das|e))?s?\s+[A-ZÁÀÂÃÉÈÊÍÏÓÔÕÖÚÜÑÇ][a-záàâãéèêíïóôõöúüñç]+(?:\s+[A-ZÁÀÂÃÉÈÊÍÏÓÔÕÖÚÜÑÇ][a-záàâãéèêíïóôõöúüñç]+)*),?\s+\d+",
    # Padrão genérico de nome próprio + apelido
    r"([A-ZÁÀÂÃÉÈÊÍÏÓÔÕÖÚÜÑÇ][a-záàâãéèêíïóôõöúüñç]{2,}(?:\s+(?:de|da|do|dos|das|e|dos))?s?\s+[A-ZÁÀÂÃÉÈÊÍÏÓÔÕÖÚÜÑÇ][a-záàâãéèêíïóôõöúüñç]{2,})",
]

# Padrões para datas
DATE_PATTERNS = [
    r"(\d{1,2}[/-]\d{1,2}[/-]\d{4})",
    r"(\d{1,2}\s+de\s+\w+\s+de\s+\d{4})",
    r"(\d{4}[/-]\d{1,2}[/-]\d{1,2})",
    r"(\d{1,2}\s+de\s+(?:janeiro|fevereiro|março|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro)\s+de\s+\d{4})",
]

# Padrões para números de registo
REGISTRO_PATTERNS = [
    r"(?:registo|registro|n\.?º?|número)\s*(?:de\s+)?(?:óbito|morte)?\s*(?:n\.?º?)?\s*(\d+)",
    r"(?:assento|lançamento)\s*(?:n\.?º?)?\s*(\d+)",
    r"\bn\.?º?\s*(\d+)\b",
]

# Palavras-chave que indicam início de registo de óbito
DEATH_KEYWORDS = [
    "óbito", "faleceu", "falecimento", "morte", "morreu", "obito",
    "assento de óbito", "registo de óbito",
]

# Meses em português
MONTHS = {
    "janeiro": 1, "fevereiro": 2, "março": 3, "abril": 4,
    "maio": 5, "junho": 6, "julho": 7, "agosto": 8,
    "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12,
}


def normalize_text(text):
    """Normaliza texto para facilitar o parsing."""
    # Substituir caracteres especiais
    text = text.replace("\r\n", "\n")
    text = text.replace("\r", "\n")
    # Remover múltiplos espaços
    text = re.sub(r"\s+", " ", text)
    return text


def extract_date(text):
    """Extrai datas do texto."""
    for pattern in DATE_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1)
    return None


def extract_registro_number(text):
    """Extrai número de registo do texto."""
    for pattern in REGISTRO_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1)
    return None


def extract_names(text):
    """Extrai nomes do texto."""
    names = []
    for pattern in NAME_PATTERNS:
        matches = re.finditer(pattern, text)
        for match in matches:
            name = match.group(1).strip()
            # Filtrar nomes muito curtos ou muito longos
            if 3 < len(name) < 100:
                names.append(name)
    return list(set(names))  # Remover duplicados


def parse_text_file(text_file):
    """
    Parse de um ficheiro de texto extraído por OCR.
    Retorna lista de registos encontrados.
    """
    if not os.path.exists(text_file):
        return []

    with open(text_file, "r", encoding="utf-8") as f:
        text = f.read()

    return parse_text(text, text_file)


def parse_text(text, source_file=None):
    """
    Parse de texto para extrair registos de óbito.
    """
    text = normalize_text(text)
    records = []

    # Dividir texto em linhas
    lines = text.split("\n")

    # Tentar extrair informação de cada linha
    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Verificar se a linha contém palavras-chave de óbito
        has_death_keyword = any(kw in line.lower() for kw in DEATH_KEYWORDS)

        if has_death_keyword or len(line) > 20:
            name = extract_names(line)
            date = extract_date(line)
            registro = extract_registro_number(line)

            if name or date or registro:
                # Se encontrou nome, é provavelmente um registo válido
                if name:
                    for n in name:
                        records.append({
                            "nome": n,
                            "data": date,
                            "numero_registo": registro,
                            "fonte": source_file or "",
                            "texto_original": line,
                        })
                elif date and registro:
                    # Mesmo sem nome claro, guardar se tem data e número
                    records.append({
                        "nome": None,
                        "data": date,
                        "numero_registo": registro,
                        "fonte": source_file or "",
                        "texto_original": line,
                    })

    # Se não encontrou nada por linhas, tentar no texto completo
    if not records:
        all_names = extract_names(text)
        date = extract_date(text)
        registro = extract_registro_number(text)

        for name in all_names:
            records.append({
                "nome": name,
                "data": date,
                "numero_registo": registro,
                "fonte": source_file or "",
                "texto_original": "",
            })

    return records


def parse_all_text_files(text_dir=None):
    """
    Processa todos os ficheiros de texto num diretório.
    """
    if text_dir is None:
        text_dir = config.TEXT_DIR

    if not os.path.exists(text_dir):
        print(f"Diretório de texto não encontrado: {text_dir}")
        return []

    all_records = []
    text_files = sorted([
        os.path.join(text_dir, f)
        for f in os.listdir(text_dir)
        if f.endswith(".txt")
    ])

    print(f"Encontrados {len(text_files)} ficheiros de texto para processar")

    for i, text_file in enumerate(text_files):
        print(f"  Processando ficheiro {i+1}/{len(text_files)}: {os.path.basename(text_file)}")
        records = parse_text_file(text_file)
        all_records.extend(records)

    print(f"\nTotal de registos extraídos: {len(all_records)}")
    return all_records


if __name__ == "__main__":
    records = parse_all_text_files()
    for r in records[:10]:
        print(f"  Nome: {r.get('nome')}, Data: {r.get('data')}, Registo: {r.get('numero_registo')}")
