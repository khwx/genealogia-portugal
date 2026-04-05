"""
Base de dados SQLite para armazenamento de registos de óbitos.
"""
import sqlite3
import os

import config


def get_connection(db_path=None):
    """Obtém uma ligação à base de dados."""
    if db_path is None:
        db_path = config.DB_PATH

    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_database(db_path=None):
    """Inicializa a base de dados com as tabelas necessárias."""
    conn = get_connection(db_path)
    cursor = conn.cursor()

    # Tabela principal de óbitos
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS obitos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT,
            data_obito TEXT,
            numero_registo TEXT,
            freguesia TEXT,
            ano INTEGER,
            fonte TEXT,
            texto_original TEXT,
            imagem_url TEXT,
            data_extracao TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Tabela de freguesias
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS freguesias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo TEXT UNIQUE,
            nome TEXT
        )
    """)

    # Tabela de livros de registos
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS livros (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            freguesia_id INTEGER,
            titulo TEXT,
            data_inicio TEXT,
            data_fim TEXT,
            url TEXT,
            FOREIGN KEY (freguesia_id) REFERENCES freguesias(id)
        )
    """)

    # Índices para pesquisa rápida
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_obitos_nome ON obitos(nome)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_obitos_data ON obitos(data_obito)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_obitos_freguesia ON obitos(freguesia)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_obitos_ano ON obitos(ano)")

    conn.commit()
    conn.close()
    print("Base de dados inicializada com sucesso.")


def insert_obito(record, db_path=None):
    """Insere um registo de óbito na base de dados."""
    conn = get_connection(db_path)
    cursor = conn.cursor()

    # Extrair ano da data
    ano = None
    data = record.get("data")
    if data:
        # Tentar extrair ano de vários formatos
        import re
        year_match = re.search(r"(\d{4})", str(data))
        if year_match:
            ano = int(year_match.group(1))

    cursor.execute("""
        INSERT INTO obitos (nome, data_obito, numero_registo, freguesia, ano, fonte, texto_original, imagem_url)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        record.get("nome"),
        record.get("data"),
        record.get("numero_registo"),
        record.get("freguesia"),
        ano,
        record.get("fonte"),
        record.get("texto_original"),
        record.get("imagem_url"),
    ))

    conn.commit()
    conn.close()
    return cursor.lastrowid


def insert_obitos_batch(records, db_path=None):
    """Insere múltiplos registos de óbito de uma vez."""
    conn = get_connection(db_path)
    cursor = conn.cursor()

    inserted = 0
    for record in records:
        data = record.get("data")
        ano = None
        if data:
            import re
            year_match = re.search(r"(\d{4})", str(data))
            if year_match:
                ano = int(year_match.group(1))

        cursor.execute("""
            INSERT INTO obitos (nome, data_obito, numero_registo, freguesia, ano, fonte, texto_original, imagem_url)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            record.get("nome"),
            record.get("data"),
            record.get("numero_registo"),
            record.get("freguesia"),
            ano,
            record.get("fonte"),
            record.get("texto_original"),
            record.get("imagem_url"),
        ))
        inserted += 1

    conn.commit()
    conn.close()
    print(f"  {inserted} registos inseridos na base de dados.")
    return inserted


def search_by_name(name, db_path=None):
    """Pesquisa registos por nome."""
    conn = get_connection(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM obitos
        WHERE nome LIKE ?
        ORDER BY data_obito
    """, (f"%{name}%",))

    results = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return results


def get_all_obitos(db_path=None):
    """Obtém todos os registos de óbitos."""
    conn = get_connection(db_path)
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM obitos ORDER BY data_obito")
    results = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return results


def get_statistics(db_path=None):
    """Obtém estatísticas dos registos."""
    conn = get_connection(db_path)
    cursor = conn.cursor()

    stats = {}

    # Total de registos
    cursor.execute("SELECT COUNT(*) as total FROM obitos")
    stats["total"] = cursor.fetchone()["total"]

    # Registos por ano
    cursor.execute("SELECT ano, COUNT(*) as count FROM obitos WHERE ano IS NOT NULL GROUP BY ano ORDER BY ano")
    stats["por_ano"] = [dict(row) for row in cursor.fetchall()]

    # Registos por freguesia
    cursor.execute("SELECT freguesia, COUNT(*) as count FROM obitos WHERE freguesia IS NOT NULL GROUP BY freguesia ORDER BY count DESC")
    stats["por_freguesia"] = [dict(row) for row in cursor.fetchall()]

    conn.close()
    return stats


if __name__ == "__main__":
    init_database()
    stats = get_statistics()
    print(f"\nEstatísticas:")
    print(f"  Total de registos: {stats.get('total', 0)}")
