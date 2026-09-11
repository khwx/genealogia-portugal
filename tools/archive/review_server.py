"""
Servidor Flask local para a interface de revisão de registos.
Corre na porta 5001. Conecta ao SQLite local.

Uso:
    python review_server.py
    Depois abre: review.html (no browser ou via Vercel)
"""
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import sqlite3
import json
import re
from pathlib import Path
from datetime import datetime

app = Flask(__name__, static_folder='.')
CORS(app)  # Permite chamadas do Vercel ou ficheiros locais

ENV = {}
env_path = Path('.env')
if env_path.exists():
    with open(env_path, encoding='utf-8') as f:
        for line in f:
            if '=' in line and not line.startswith('#'):
                k, v = line.split('=', 1)
                ENV[k.strip()] = v.strip().strip('"').strip("'")

DB_PATH = Path(ENV.get('DB_PATH', 'output/genealogia.db'))


def get_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ─── Livros ──────────────────────────────────────────────────────────────────

@app.route('/api/livros', methods=['GET'])
def list_livros():
    conn = get_db()
    rows = conn.execute("SELECT * FROM livros ORDER BY freguesia, codigo").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route('/api/livros/<int:livro_id>', methods=['PATCH'])
def update_livro(livro_id):
    data = request.json
    conn = get_db()
    fields = []
    values = []
    for field in ['paginas_indice', 'status', 'titulo', 'url_viewer', 'freguesia']:
        if field in data:
            fields.append(f"{field} = ?")
            values.append(data[field])
    if not fields:
        return jsonify({'error': 'Nenhum campo para atualizar'}), 400
    values.append(livro_id)
    conn.execute(f"UPDATE livros SET {', '.join(fields)} WHERE id = ?", values)
    conn.commit()
    conn.close()
    return jsonify({'ok': True})


# ─── Registos ────────────────────────────────────────────────────────────────

@app.route('/api/registos', methods=['GET'])
def list_registos():
    status = request.args.get('status', 'pendente')
    livro = request.args.get('livro', '')
    q = request.args.get('q', '')
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 20))
    offset = (page - 1) * per_page

    conn = get_db()
    where = ["1=1"]
    params = []

    if status != 'todos':
        where.append("status = ?")
        params.append(status)
    if livro:
        where.append("livro_id = ?")
        params.append(livro)
    if q:
        where.append("nome LIKE ?")
        params.append(f'%{q}%')

    where_sql = " AND ".join(where)

    total = conn.execute(
        f"SELECT COUNT(*) FROM obitos WHERE {where_sql}", params
    ).fetchone()[0]

    rows = conn.execute(
        f"SELECT * FROM obitos WHERE {where_sql} ORDER BY livro_id, pagina, id "
        f"LIMIT ? OFFSET ?",
        params + [per_page, offset]
    ).fetchall()
    conn.close()

    return jsonify({
        'total': total,
        'page': page,
        'per_page': per_page,
        'records': [dict(r) for r in rows]
    })


@app.route('/api/registos/<int:reg_id>/aprovar', methods=['POST'])
def aprovar(reg_id):
    conn = get_db()
    conn.execute("UPDATE obitos SET status='aprovado' WHERE id=?", (reg_id,))
    conn.commit()
    conn.close()
    return jsonify({'ok': True})


@app.route('/api/registos/<int:reg_id>/rejeitar', methods=['POST'])
def rejeitar(reg_id):
    conn = get_db()
    conn.execute("UPDATE obitos SET status='rejeitado' WHERE id=?", (reg_id,))
    conn.commit()
    conn.close()
    return jsonify({'ok': True})


@app.route('/api/registos/<int:reg_id>/editar', methods=['POST'])
def editar(reg_id):
    data = request.json
    conn = get_db()
    fields = []
    values = []
    for field in ['nome', 'data_obito', 'freguesia', 'ano', 'numero_registo', 'observacoes']:
        if field in data:
            fields.append(f"{field} = ?")
            values.append(data[field])
    # Aprovar automaticamente após edição
    fields.append("status = 'aprovado'")
    if not fields:
        return jsonify({'error': 'Nada para editar'}), 400
    values.append(reg_id)
    conn.execute(f"UPDATE obitos SET {', '.join(fields)} WHERE id=?", values)
    conn.commit()
    conn.close()
    return jsonify({'ok': True})


@app.route('/api/registos/aprovar-todos', methods=['POST'])
def aprovar_todos():
    livro = request.json.get('livro_id')
    conn = get_db()
    if livro:
        conn.execute(
            "UPDATE obitos SET status='aprovado' WHERE status='pendente' AND livro_id=?",
            (livro,)
        )
    else:
        conn.execute("UPDATE obitos SET status='aprovado' WHERE status='pendente'")
    count = conn.execute("SELECT changes()").fetchone()[0]
    conn.commit()
    conn.close()
    return jsonify({'aprovados': count})


# ─── Estatísticas ─────────────────────────────────────────────────────────────

@app.route('/api/stats', methods=['GET'])
def stats():
    conn = get_db()

    total = conn.execute("SELECT COUNT(*) FROM obitos").fetchone()[0]
    pendentes = conn.execute("SELECT COUNT(*) FROM obitos WHERE status='pendente'").fetchone()[0]
    aprovados = conn.execute("SELECT COUNT(*) FROM obitos WHERE status='aprovado'").fetchone()[0]
    rejeitados = conn.execute("SELECT COUNT(*) FROM obitos WHERE status='rejeitado'").fetchone()[0]

    por_ano = [dict(r) for r in conn.execute(
        "SELECT ano, COUNT(*) as total FROM obitos WHERE ano IS NOT NULL AND status='aprovado' "
        "GROUP BY ano ORDER BY ano"
    ).fetchall()]

    por_freguesia = [dict(r) for r in conn.execute(
        "SELECT freguesia, COUNT(*) as total FROM obitos WHERE status='aprovado' AND freguesia != '' "
        "GROUP BY freguesia ORDER BY total DESC LIMIT 20"
    ).fetchall()]

    conn.close()
    return jsonify({
        'total': total,
        'pendentes': pendentes,
        'aprovados': aprovados,
        'rejeitados': rejeitados,
        'por_ano': por_ano,
        'por_freguesia': por_freguesia,
    })


# ─── Exportação GEDCOM ───────────────────────────────────────────────────────

@app.route('/api/export/gedcom', methods=['GET'])
def export_gedcom():
    from gedcom_export import generate_gedcom
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM obitos WHERE status='aprovado' ORDER BY ano, nome"
    ).fetchall()
    conn.close()
    records = [dict(r) for r in rows]
    gedcom_text = generate_gedcom(records)
    from flask import Response
    return Response(
        gedcom_text,
        mimetype='text/plain',
        headers={'Content-Disposition': 'attachment; filename=genealogia-portugal.ged'}
    )


@app.route('/api/export/csv', methods=['GET'])
def export_csv():
    import csv, io
    conn = get_db()
    rows = conn.execute(
        "SELECT nome, data_obito, ano, freguesia, concelho, distrito, livro_id, pagina "
        "FROM obitos WHERE status='aprovado' ORDER BY ano, nome"
    ).fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['nome', 'data_obito', 'ano', 'freguesia', 'concelho', 'distrito', 'livro', 'pagina'])
    for row in rows:
        writer.writerow(list(row))

    from flask import Response
    return Response(
        '\ufeff' + output.getvalue(),  # BOM para Excel
        mimetype='text/csv; charset=utf-8',
        headers={'Content-Disposition': 'attachment; filename=genealogia-portugal.csv'}
    )


# ─── Servir ficheiros estáticos ───────────────────────────────────────────────

@app.route('/')
def index():
    return send_from_directory('.', 'index_pages.html')

@app.route('/<path:filename>')
def static_files(filename):
    return send_from_directory('.', filename)


if __name__ == '__main__':
    print("🌳 Genealogia Portugal — Servidor de revisão")
    print("   BD:", DB_PATH.absolute())
    print("   URL: http://localhost:5001")
    print("   Abre review.html no browser\n")
    app.run(port=5001, debug=True)
