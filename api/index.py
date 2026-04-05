from flask import Flask, jsonify, request, render_template_string
import requests
import os

app = Flask(__name__)

SUPABASE_URL = os.environ.get('SUPABASE_URL', '')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY', '') or os.environ.get('SUPABASE_ANON_KEY', '')

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="pt-PT">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Árvore Genealógica de Portugal</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-100 min-h-screen">
    <nav class="bg-green-800 text-white p-4">
        <div class="container mx-auto">
            <div class="flex justify-between items-center">
                <h1 class="text-2xl font-bold">🌳 Árvore Genealógica de Portugal</h1>
                <a href="/index_pages.html" class="bg-blue-600 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded text-sm">
                    📚 Editor de Índices
                </a>
            </div>
        </div>
    </nav>
    
    <div class="container mx-auto p-4">
        <div class="bg-white rounded-lg shadow-lg p-6 mb-6">
            <h2 class="text-xl font-semibold mb-4">Pesquisar Registos</h2>
            <form action="/pesquisar" method="GET" class="flex gap-2">
                <input type="text" name="q" placeholder="Introduza um nome..." 
                       class="flex-1 p-3 border rounded-lg focus:outline-none focus:ring-2 focus:ring-green-500"
                       value="{{ query or '' }}">
                <button type="submit" class="bg-green-600 text-white px-6 py-3 rounded-lg hover:bg-green-700">
                    Pesquisar
                </button>
            </form>
        </div>

        {% if stats %}
        <div class="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
            <div class="bg-white rounded-lg shadow p-4 text-center">
                <div class="text-3xl font-bold text-green-600">{{ stats.total }}</div>
                <div class="text-gray-500">Total de registos</div>
            </div>
            <div class="bg-white rounded-lg shadow p-4 text-center">
                <div class="text-3xl font-bold text-blue-600">{{ stats.freguesias }}</div>
                <div class="text-gray-500">Freguesias</div>
            </div>
            <div class="bg-white rounded-lg shadow p-4 text-center">
                <div class="text-3xl font-bold text-purple-600">{{ stats.concelhos }}</div>
                <div class="text-gray-500">Concelhos</div>
            </div>
            <div class="bg-white rounded-lg shadow p-4 text-center">
                <div class="text-3xl font-bold text-orange-600">{{ stats.distritos }}</div>
                <div class="text-gray-500">Distritos</div>
            </div>
        </div>
        {% endif %}

        {% if results %}
        <div class="bg-white rounded-lg shadow-lg p-6">
            <h3 class="text-lg font-semibold mb-4">Resultados ({{ results|length }})</h3>
            <div class="overflow-x-auto">
                <table class="w-full table-auto">
                    <thead>
                        <tr class="bg-gray-100">
                            <th class="p-3 text-left">Nome</th>
                            <th class="p-3 text-left">Data Óbito</th>
                            <th class="p-3 text-left">Freguesia</th>
                            <th class="p-3 text-left">Nº Registo</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for p in results %}
                        <tr class="border-b hover:bg-gray-50">
                            <td class="p-3">{{ p.nome }} {{ p.sobrenome or '' }}</td>
                            <td class="p-3">{{ p.data_obito or '—' }}</td>
                            <td class="p-3">{{ p.freguesia or '—' }}</td>
                            <td class="p-3">{{ p.numero_registo or '—' }}</td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
        {% endif %}
    </div>
</body>
</html>
"""

@app.route('/')
def index():
    stats = get_stats()
    return render_template_string(HTML_TEMPLATE, stats=stats, query=None, results=None)

@app.route('/pesquisar')
def pesquisar():
    query = request.args.get('q', '').strip()
    results = []
    
    if query:
        resp = requests.get(
            f"{SUPABASE_URL}/rest/v1/pessoas",
            headers=HEADERS,
            params={"nome": f"ilike.*{query}*", "order": "data_obito"},
            timeout=30
        )
        if resp.status_code == 200:
            results = resp.json()
    
    stats = get_stats()
    return render_template_string(HTML_TEMPLATE, stats=stats, query=query, results=results)

@app.route('/api/pessoas')
def api_pessoas():
    query = request.args.get('q', '').strip()
    limit = request.args.get('limit', 50)
    
    params = {"limit": limit, "order": "data_obito"}
    if query:
        params["nome"] = f"ilike.*{query}*"
    
    resp = requests.get(f"{SUPABASE_URL}/rest/v1/pessoas", headers=HEADERS, params=params, timeout=30)
    return jsonify(resp.json() if resp.status_code == 200 else [])

@app.route('/api/freguesias')
def api_freguesias():
    resp = requests.get(f"{SUPABASE_URL}/rest/v1/freguesias", headers=HEADERS, timeout=30)
    return jsonify(resp.json() if resp.status_code == 200 else [])

@app.route('/api/stats')
def api_stats():
    return jsonify(get_stats())

def get_stats():
    try:
        resp = requests.get(f"{SUPABASE_URL}/rest/v1/pessoas", headers=HEADERS, params={"select": "count"}, timeout=30)
        total = resp.json()[0]['count'] if resp.status_code == 200 else 0
        
        resp2 = requests.get(f"{SUPABASE_URL}/rest/v1/freguesias", headers=HEADERS, params={"select": "count"}, timeout=30)
        freguesias = resp2.json()[0]['count'] if resp2.status_code == 200 else 0
        
        return {
            "total": total,
            "freguesias": freguesias,
            "concelhos": 1,
            "distritos": 1
        }
    except:
        return {"total": 0, "freguesias": 0, "concelhos": 0, "distritos": 0}

if __name__ == '__main__':
    app.run()


@app.route('/index_pages.html')
def serve_index_pages():
    return '''<!DOCTYPE html>
<html lang="pt">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Editor de Índices - Celorico da Beira</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        .book-item { transition: all 0.2s; }
        .book-item:hover { background-color: #f9fafb; }
    </style>
</head>
<body class="bg-gray-50 min-h-screen">
    <div class="max-w-4xl mx-auto p-4">
        <header class="mb-6 flex justify-between items-center">
            <div>
                <h1 class="text-2xl font-bold text-gray-800">📚 Editor de Índices</h1>
                <p class="text-gray-600">Indica as páginas do índice de cada livro</p>
            </div>
            <a href="/" class="text-blue-600 hover:underline">← Voltar à Pesquisa</a>
        </header>

        <div class="mb-4">
            <input type="text" id="search" placeholder="Pesquisar freguesia ou livro..." 
                   class="w-full p-3 border border-gray-300 rounded-lg shadow-sm focus:ring-2 focus:ring-blue-500 focus:outline-none">
        </div>

        <div id="books-list" class="space-y-3">
            <div class="text-center py-10 text-gray-500">A carregar livros...</div>
        </div>
    </div>

    <script>
        async function fetchBooks() {
            try {
                const res = await fetch('/api/livros');
                const books = await res.json();
                renderBooks(books);
            } catch (err) {
                document.getElementById('books-list').innerHTML = '<div class="text-red-500 text-center p-4 bg-red-50 rounded">⚠️ Erro ao carregar dados.</div>';
            }
        }

        function renderBooks(books) {
            const container = document.getElementById('books-list');
            if (!books || books.length === 0) {
                container.innerHTML = '<div class="text-center text-gray-500 py-8">Nenhum livro encontrado.</div>';
                return;
            }

            container.innerHTML = books.map(book => `
                <div class="book-item bg-white p-4 rounded-lg shadow-sm border border-gray-200">
                    <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                        <div class="flex-1">
                            <h3 class="font-semibold text-gray-800">${book.freguesia}</h3>
                            <p class="text-sm text-gray-600">${book.titulo}</p>
                            <p class="text-xs text-gray-400">${book.datas || ''}</p>
                        </div>
                        <div class="flex flex-col sm:flex-row items-start sm:items-center gap-2">
                            <a href="${book.url_viewer}" target="_blank" class="text-blue-600 hover:underline text-sm flex items-center gap-1">
                                🔗 Ver no Digitarq
                            </a>
                            <div class="flex items-center gap-2">
                                <span class="text-xs font-medium text-gray-500">Pág. Índice:</span>
                                <input type="text" id="pages-${book.id}" value="${book.paginas_indice || ''}" 
                                       class="w-24 p-1 text-sm border border-gray-300 rounded focus:ring-1 focus:ring-blue-500 focus:outline-none"
                                       placeholder="ex: 249-255">
                                <button onclick="savePages(${book.id})" 
                                        class="bg-green-600 hover:bg-green-700 text-white text-xs px-3 py-1 rounded transition">
                                    💾
                                </button>
                            </div>
                            <span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${getStatusColor(book.status)}">
                                ${book.status || 'pendente'}
                            </span>
                        </div>
                    </div>
                </div>
            `).join('');
        }

        function getStatusColor(status) {
            switch(status) {
                case 'concluido': return 'bg-green-100 text-green-800';
                case 'processando': return 'bg-yellow-100 text-yellow-800';
                default: return 'bg-gray-100 text-gray-800';
            }
        }

        async function savePages(id) {
            const input = document.getElementById(`pages-${id}`);
            const pages = input.value.trim();
            if (!pages) return;

            const btn = input.nextElementSibling;
            btn.disabled = true;
            btn.textContent = '⏳';

            try {
                const res = await fetch(`/api/livros/${id}`, {
                    method: 'PATCH',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ paginas_indice: pages })
                });
                if (res.ok) {
                    btn.textContent = '✅';
                    setTimeout(() => { btn.textContent = '💾'; btn.disabled = false; }, 1500);
                } else {
                    throw new Error('Erro ao guardar');
                }
            } catch (err) {
                btn.textContent = '❌';
                setTimeout(() => { btn.textContent = '💾'; btn.disabled = false; }, 1500);
            }
        }

        document.getElementById('search').addEventListener('input', (e) => {
            const term = e.target.value.toLowerCase();
            // O filtro é feito no browser para simplificar
            const allDivs = document.querySelectorAll('.book-item');
            allDivs.forEach(div => {
                const text = div.textContent.toLowerCase();
                div.style.display = text.includes(term) ? '' : 'none';
            });
        });

        fetchBooks();
    </script>
</body>
</html>'''
