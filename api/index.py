import os
import requests
from flask import Flask, jsonify, request

app = Flask(__name__, template_folder='.')

SUPABASE_URL = os.environ.get('SUPABASE_URL', 'https://qljopxbxgflozrcdblrl.supabase.co')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY', '') or os.environ.get('SUPABASE_ANON_KEY', '')

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

@app.route('/')
def home():
    return '<h1>Genealogia Portugal - Server Online</h1><a href="/index_pages.html">Editor de Indices</a>'

@app.route('/api/livros')
def get_livros():
    try:
        resp = requests.get(SUPABASE_URL + '/rest/v1/livros?order=freguesia.asc', headers=HEADERS)
        return jsonify(resp.json())
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/livros/<int:livro_id>', methods=['PATCH'])
def update_livro(livro_id):
    data = request.json
    try:
        resp = requests.patch(
            SUPABASE_URL + '/rest/v1/livros?id=eq.' + str(livro_id),
            headers=HEADERS,
            json=data
        )
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/<path:filename>')
def serve_html(filename):
    if filename.endswith('.html'):
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            pass
    return "Error loading page or not found", 404

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3000)
