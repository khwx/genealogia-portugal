"""
Página simples para listar livros de óbitos e receber páginas de índice.
"""
from flask import Flask, render_template_string, request, jsonify
import json
from collections import defaultdict
import os

app = Flask(__name__)

# Carregar inventário
with open(os.path.join(os.path.dirname(__file__), 'output', 'obitos_inventario.json')) as f:
    inventory = json.load(f)

# Agrupar por freguesia
by_freguesia = defaultdict(list)
for r in inventory:
    freg = r.get('freguesia', 'Unknown')
    by_freguesia[freg].append(r)

# Ordenar por número de livros
sorted_freguesias = sorted(by_freguesia.items(), key=lambda x: -len(x[1]))

HTML = """
<!DOCTYPE html>
<html lang="pt">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Óbitos - Celorico da Beira</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: -apple-system, sans-serif; background: #f5f5f5; padding: 10px; }
        h1 { text-align: center; padding: 15px; background: #1a5276; color: white; margin: -10px -10px 15px; border-radius: 0 0 10px 10px; }
        h1 small { font-size: 0.5em; display: block; opacity: 0.8; }
        .freguesia { background: white; margin-bottom: 10px; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
        .freg-header { padding: 12px 15px; background: #2c3e50; color: white; cursor: pointer; display: flex; justify-content: space-between; align-items: center; }
        .freg-header h2 { font-size: 1em; }
        .freg-header span { background: #e74c3c; padding: 2px 8px; border-radius: 10px; font-size: 0.8em; }
        .freg-body { display: none; padding: 8px; }
        .freg-body.open { display: block; }
        .book { padding: 10px; border-bottom: 1px solid #eee; display: flex; flex-direction: column; gap: 5px; }
        .book:last-child { border-bottom: none; }
        .book-title { font-weight: 600; font-size: 0.85em; color: #2c3e50; }
        .book-dates { font-size: 0.75em; color: #7f8c8d; }
        .book-link { display: inline-block; padding: 6px 12px; background: #3498db; color: white; text-decoration: none; border-radius: 5px; font-size: 0.8em; text-align: center; }
        .book-link:visited { background: #2980b9; }
        .page-input { display: flex; gap: 5px; align-items: center; margin-top: 5px; }
        .page-input label { font-size: 0.8em; color: #555; white-space: nowrap; }
        .page-input input { flex: 1; padding: 6px 8px; border: 1px solid #ddd; border-radius: 4px; font-size: 0.85em; }
        .page-input button { padding: 6px 12px; background: #27ae60; color: white; border: none; border-radius: 4px; font-size: 0.8em; cursor: pointer; }
        .saved-msg { font-size: 0.7em; color: #27ae60; display: none; }
        .stats { text-align: center; padding: 10px; background: #ecf0f1; border-radius: 8px; margin-bottom: 15px; }
        .stats strong { color: #e74c3c; }
        #saved-pages { margin-top: 15px; background: white; padding: 15px; border-radius: 8px; }
        #saved-pages h3 { margin-bottom: 10px; }
        .saved-item { padding: 5px 0; border-bottom: 1px solid #eee; font-size: 0.85em; }
        .export-btn { display: block; width: 100%; padding: 12px; background: #8e44ad; color: white; border: none; border-radius: 8px; font-size: 1em; margin-top: 15px; cursor: pointer; }
    </style>
</head>
<body>
    <h1>📚 Óbitos Celorico da Beira
        <small>Indica as páginas do índice de cada livro</small>
    </h1>

    <div class="stats">
        <strong>{{ total_books }}</strong> livros em <strong>{{ total_freguesias }}</strong> freguesias
    </div>

    {% for freg, books in freguesias %}
    <div class="freguesia">
        <div class="freg-header" onclick="this.nextElementSibling.classList.toggle('open')">
            <h2>{{ freg }}</h2>
            <span>{{ books|length }} livros</span>
        </div>
        <div class="freg-body">
            {% for book in books %}
            <div class="book">
                <div class="book-title">{{ book.titulo }}</div>
                <div class="book-dates">📅 {{ book.datas }}</div>
                <a class="book-link" href="{{ book.url_viewer }}" target="_blank">👁️ Ver no Digitarq</a>
                <div class="page-input">
                    <label>📄 Pág. índice:</label>
                    <input type="text" id="pages-{{ loop.index0 }}-{{ loop.index }}" placeholder="ex: 249-255" data-freg="{{ freg }}" data-book="{{ book.titulo }}">
                    <button onclick="savePage(this)">💾</button>
                </div>
                <span class="saved-msg">✅ Guardado!</span>
            </div>
            {% endfor %}
        </div>
    </div>
    {% endfor %}

    <button class="export-btn" onclick="exportPages()">📋 Exportar Lista de Páginas</button>

    <div id="saved-pages">
        <h3>📌 Páginas Guardadas:</h3>
        <div id="saved-list"><em style="color:#999">Nenhuma página guardada ainda.</em></div>
    </div>

    <script>
        let savedPages = JSON.parse(localStorage.getItem('obitos_pages') || '{}');

        function savePage(btn) {
            const input = btn.previousElementSibling;
            const freg = input.dataset.freg;
            const book = input.dataset.book;
            const pages = input.value.trim();

            if (!pages) return;

            savedPages[freg] = savedPages[freg] || {};
            savedPages[freg][book] = pages;
            localStorage.setItem('obitos_pages', JSON.stringify(savedPages));

            btn.nextElementSibling.style.display = 'inline';
            setTimeout(() => btn.nextElementSibling.style.display = 'none', 2000);

            updateSavedList();
        }

        function updateSavedList() {
            const list = document.getElementById('saved-list');
            let html = '';
            for (const freg in savedPages) {
                for (const book in savedPages[freg]) {
                    html += `<div class="saved-item"><strong>${freg}</strong> - ${book}: <strong>${savedPages[freg][book]}</strong></div>`;
                }
            }
            list.innerHTML = html || '<em style="color:#999">Nenhuma página guardada ainda.</em>';
        }

        function exportPages() {
            const text = JSON.stringify(savedPages, null, 2);
            const blob = new Blob([text], {type: 'application/json'});
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'paginas_indice.json';
            a.click();
        }

        // Restore saved values
        document.querySelectorAll('.page-input input').forEach(input => {
            const freg = input.dataset.freg;
            const book = input.dataset.book;
            if (savedPages[freg] && savedPages[freg][book]) {
                input.value = savedPages[freg][book];
            }
        });

        updateSavedList();
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML, freguesias=sorted_freguesias, total_books=len(inventory), total_freguesias=len(sorted_freguesias))

if __name__ == '__main__':
    print("📚 Página disponível em: http://localhost:5555")
    app.run(host='0.0.0.0', port=5555, debug=False)
