"""
Base de dados SQLite para armazenamento de registos (nascimentos, casamentos, óbitos).
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
    
    # Tabela genérica de registos (nascimentos, casamentos, óbitos)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS registos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tipo TEXT NOT NULL,  -- 'BIRT' (nascimento), 'MARR' (casamento), 'DEAT' (óbito)
            nome TEXT,
            data_evento TEXT,  -- data do nascimento/casamento/óbito
            numero_registo TEXT,
            freguesia TEXT,
            ano INTEGER,
            fonte TEXT,
            texto_original TEXT,
            imagem_url TEXT,
            livro_titulo TEXT,
            livro_url TEXT,
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
            tipo TEXT NOT NULL,  -- 'BIRT', 'MARR', 'DEAT'
            freguesia_id INTEGER,
            titulo TEXT,
            data_inicio TEXT,
            data_fim TEXT,
            url TEXT,
            FOREIGN KEY (freguesia_id) REFERENCES freguesias(id)
        )
    """)
    
    # Índices para pesquisa rápida
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_registos_nome ON registos(nome)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_registos_data ON registos(data_evento)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_registos_freguesia ON registos(freguesia)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_registos_ano ON registos(ano)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_registos_tipo ON registos(tipo)")
    
    # Manter tabela antiga para compatibilidade (se existir)
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
    
    conn.commit()
    conn.close()
    print("Base de dados inicializada com sucesso.")


def insert_registo(record, db_path=None):
    """Insere um registo (nascimento/casamento/óbito) na base de dados."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    
    # Extrair ano da data
    ano = None
    data = record.get("data_evento") or record.get("data")
    if data:
        import re
        year_match = re.search(r"(\d{4})", str(data))
        if year_match:
            ano = int(year_match.group(1))
    
    cursor.execute("""
        INSERT INTO registos (tipo, nome, data_evento, numero_registo, freguesia, ano, fonte, texto_original, imagem_url, livro_titulo, livro_url)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        record.get("tipo", "DEAT"),
        record.get("nome"),
        data,
        record.get("numero_registo"),
        record.get("freguesia"),
        ano,
        record.get("fonte"),
        record.get("texto_original"),
        record.get("imagem_url") or record.get("imagem_url"),
        record.get("livro_titulo"),
        record.get("livro_url"),
    ))
    
    conn.commit()
    conn.close()
    return cursor.lastrowid


def insert_registos_batch(records, db_path=None):
    """Insere múltiplos registos de uma vez."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    
    inserted = 0
    for record in records:
        data = record.get("data_evento") or record.get("data")
        ano = None
        if data:
            import re
            year_match = re.search(r"(\d{4})", str(data))
            if year_match:
                ano = int(year_match.group(1))
        
        cursor.execute("""
            INSERT INTO registos (tipo, nome, data_evento, numero_registo, freguesia, ano, fonte, texto_original, imagem_url, livro_titulo, livro_url)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            record.get("tipo", "DEAT"),
            record.get("nome"),
            data,
            record.get("numero_registo"),
            record.get("freguesia"),
            ano,
            record.get("fonte"),
            record.get("texto_original"),
            record.get("imagem_url") or record.get("imagem_url"),
            record.get("livro_titulo"),
            record.get("livro_url"),
        ))
        inserted += 1
    
    conn.commit()
    conn.close()
    print(f"  {inserted} registos inseridos na base de dados.")
    return inserted


# Funções legadas para compatibilidade
def insert_obito(record, db_path=None):
    """Insere um registo de óbito na base de dados (função legada)."""
    record["tipo"] = "DEAT"
    return insert_registo(record, db_path)


def insert_obitos_batch(records, db_path=None):
    """Insere múltiplos registos de óbito de uma vez (função legada)."""
    for r in records:
        r["tipo"] = "DEAT"
    return insert_registos_batch(records, db_path)


def search_by_name(name, db_path=None, tipo=None):
    """Pesquisa registos por nome (opcionalmente filtrar por tipo)."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    
    if tipo:
        cursor.execute("""
            SELECT * FROM registos
            WHERE nome LIKE ? AND tipo = ?
            ORDER BY data_evento
        """, (f"%{name}%", tipo))
    else:
        cursor.execute("""
            SELECT * FROM registos
            WHERE nome LIKE ?
            ORDER BY data_evento
        """, (f"%{name}%",))
    
    results = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return results


def get_all_registos(db_path=None, tipo=None):
    """Obtém todos os registos (opcionalmente filtrar por tipo)."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    
    if tipo:
        cursor.execute("SELECT * FROM registos WHERE tipo = ? ORDER BY data_evento", (tipo,))
    else:
        cursor.execute("SELECT * FROM registos ORDER BY data_evento")
    
    results = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return results


def get_all_obitos(db_path=None):
    """Obtém todos os registos de óbitos (função legada)."""
    return get_all_registos(db_path, tipo="DEAT")


def get_statistics(db_path=None):
    """Obtém estatísticas dos registos."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    
    stats = {}
    
    # Total de registos
    cursor.execute("SELECT COUNT(*) as total FROM registos")
    stats["total"] = cursor.fetchone()["total"]
    
    # Registos por tipo
    cursor.execute("SELECT tipo, COUNT(*) as count FROM registos GROUP BY tipo")
    stats["por_tipo"] = [dict(row) for row in cursor.fetchall()]
    
    # Registos por ano
    cursor.execute("SELECT ano, COUNT(*) as count FROM registos WHERE ano IS NOT NULL GROUP BY ano ORDER BY ano")
    stats["por_ano"] = [dict(row) for row in cursor.fetchall()]
    
    # Registos por freguesia
    cursor.execute("SELECT freguesia, COUNT(*) as count FROM registos WHERE freguesia IS NOT NULL GROUP BY freguesia ORDER BY count DESC")
    stats["por_freguesia"] = [dict(row) for row in cursor.fetchall()]
    
    # Registos por tipo e freguesia
    cursor.execute("""
        SELECT tipo, freguesia, COUNT(*) as count 
        FROM registos 
        WHERE freguesia IS NOT NULL 
        GROUP BY tipo, freguesia 
        ORDER BY tipo, count DESC
    """)
    stats["por_tipo_freguesia"] = [dict(row) for row in cursor.fetchall()]
    
    conn.close()
    return stats


if __name__ == "__main__":
    init_database()
    stats = get_statistics()
    print(f"\nEstatísticas:")
    print(f"  Total de registos: {stats.get('total', 0)}")
