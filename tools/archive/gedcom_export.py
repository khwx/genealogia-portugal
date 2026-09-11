"""
Exportação de registos para formato GEDCOM 5.5.1
Compatível com: Gramps, Ancestry, MyHeritage, FamilySearch, MacFamilyTree

Uso standalone:
    python gedcom_export.py                         # Exporta para output/genealogia.ged
    python gedcom_export.py --output minha_arvore.ged
"""
import re
import sqlite3
import argparse
from pathlib import Path
from datetime import datetime


ENV = {}
env_path = Path('.env')
if env_path.exists():
    with open(env_path, encoding='utf-8') as f:
        for line in f:
            if '=' in line and not line.startswith('#'):
                k, v = line.split('=', 1)
                ENV[k.strip()] = v.strip().strip('"').strip("'")

DB_PATH = Path(ENV.get('DB_PATH', 'output/genealogia.db'))

MONTHS_GEDCOM = {
    '01': 'JAN', '02': 'FEB', '03': 'MAR', '04': 'APR',
    '05': 'MAY', '06': 'JUN', '07': 'JUL', '08': 'AUG',
    '09': 'SEP', '10': 'OCT', '11': 'NOV', '12': 'DEC',
}


def format_name_gedcom(nome: str) -> str:
    """
    Formata o nome para GEDCOM: 'João Silva' → 'João /Silva/'
    O apelido vai entre //.
    """
    parts = nome.strip().split()
    if not parts:
        return nome
    # Prefixos nobiliárquicos/religiosos
    prefixos = {'d.', 'dr.', 'dr', 'frei', 'irmã', 'irmao', 'padre', 'rev.', 'reverendo'}
    # Conectivos do apelido português
    conectivos = {'da', 'de', 'do', 'das', 'dos', 'e', 'van', 'von'}

    # Encontrar onde começa o apelido (último grupo de palavras)
    # Heurística: a partir da 2ª palavra não-prefixo, tudo é apelido
    first_name_parts = []
    last_name_parts = []

    i = 0
    # Ignorar prefixos iniciais
    while i < len(parts) and parts[i].lower().rstrip('.') in prefixos:
        first_name_parts.append(parts[i])
        i += 1

    # Primeiro nome
    if i < len(parts):
        first_name_parts.append(parts[i])
        i += 1

    # Resto vai para apelido
    last_name_parts = parts[i:]

    if last_name_parts:
        return f"{' '.join(first_name_parts)} /{' '.join(last_name_parts)}/"
    else:
        return f"/{' '.join(first_name_parts)}/"


def format_date_gedcom(date_str: str | None) -> str | None:
    """
    Converte '1864-01-15' para '15 JAN 1864' (formato GEDCOM).
    """
    if not date_str:
        return None

    # Formato ISO: AAAA-MM-DD
    m = re.match(r'(\d{4})-(\d{2})-(\d{2})', date_str)
    if m:
        year, month, day = m.group(1), m.group(2), m.group(3)
        month_ged = MONTHS_GEDCOM.get(month, month)
        return f"{int(day)} {month_ged} {year}"

    # Só o ano
    m = re.match(r'^(\d{4})$', date_str.strip())
    if m:
        return m.group(1)

    return None


def generate_gedcom(records: list[dict]) -> str:
    """
    Gera o conteúdo GEDCOM a partir de uma lista de registos.
    """
    now = datetime.now()
    lines = [
        "0 HEAD",
        "1 SOUR genealogia-portugal",
        "2 VERS 1.0",
        "2 NAME Genealogia Portugal",
        "2 CORP khwx",
        "1 DATE " + now.strftime("%d %b %Y").upper(),
        "1 FILE genealogia-portugal.ged",
        "1 GEDC",
        "2 VERS 5.5.1",
        "2 FORM LINEAGE-LINKED",
        "1 CHAR UTF-8",
        "1 LANG Portuguese",
        "",
    ]

    for i, rec in enumerate(records, start=1):
        indi_id = f"@I{i}@"
        nome_ged = format_name_gedcom(rec.get('nome', 'Desconhecido'))
        data_obito_ged = format_date_gedcom(rec.get('data_obito'))
        freguesia = rec.get('freguesia', '')
        concelho = rec.get('concelho', 'Celorico da Beira')
        distrito = rec.get('distrito', 'Guarda')
        livro_id = rec.get('livro_id', '')
        pagina = rec.get('pagina', '')

        # Construir localização
        lugar_parts = [p for p in [freguesia, concelho, distrito, 'Portugal'] if p]
        lugar = ', '.join(lugar_parts)

        lines.append(f"0 {indi_id} INDI")
        lines.append(f"1 NAME {nome_ged}")

        # Óbito
        lines.append("1 DEAT Y")
        if data_obito_ged:
            lines.append(f"2 DATE {data_obito_ged}")
        if lugar:
            lines.append(f"2 PLAC {lugar}")

        # Fonte
        fonte_parts = []
        if livro_id:
            fonte_parts.append(f"Livro: {livro_id}")
        if pagina:
            fonte_parts.append(f"Pág. {pagina}")
        fonte_parts.append("Digitarq/Tombo.pt")
        if fonte_parts:
            lines.append(f"1 SOUR {' | '.join(fonte_parts)}")

        # Nota com número de registo
        num_registo = rec.get('numero_registo', '')
        if num_registo:
            lines.append(f"1 NOTE Registo nº {num_registo}")

        lines.append("")

    lines.append("0 TRLR")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description='Exportar GEDCOM')
    parser.add_argument('--output', default='output/genealogia.ged',
                        help='Ficheiro de saída')
    parser.add_argument('--freguesia', help='Filtrar por freguesia')
    parser.add_argument('--ano-inicio', type=int, help='Ano início')
    parser.add_argument('--ano-fim', type=int, help='Ano fim')
    args = parser.parse_args()

    if not DB_PATH.exists():
        print(f"❌ BD não encontrada: {DB_PATH}")
        print("   Corre primeiro: python pipeline.py --test")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    where = ["status = 'aprovado'"]
    params = []
    if args.freguesia:
        where.append("freguesia LIKE ?")
        params.append(f'%{args.freguesia}%')
    if args.ano_inicio:
        where.append("ano >= ?")
        params.append(args.ano_inicio)
    if args.ano_fim:
        where.append("ano <= ?")
        params.append(args.ano_fim)

    rows = conn.execute(
        f"SELECT * FROM obitos WHERE {' AND '.join(where)} ORDER BY ano, nome",
        params
    ).fetchall()
    conn.close()

    records = [dict(r) for r in rows]
    if not records:
        print("❌ Nenhum registo aprovado encontrado")
        print("   Abre review.html e aprova alguns registos primeiro")
        return

    gedcom = generate_gedcom(records)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(gedcom, encoding='utf-8')

    print(f"✅ {len(records)} registos exportados para: {output_path}")
    print(f"   Importa este ficheiro no Gramps, Ancestry ou MyHeritage")


if __name__ == '__main__':
    main()
