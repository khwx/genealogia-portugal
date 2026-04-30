from flask import Flask, jsonify, request, render_template_string, render_template
import requests
import os
import json

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
    try:
        with open('index.html', 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        return "Error loading page: " + str(e), 500

@app.route('/api/livros')
def get_livros():
    try:
        resp = requests.get(SUPABASE_URL + '/rest/v1/livros?order=freguesia.asc', headers=HEADERS)
        return jsonify(resp.json())
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/family-tree')
def family_tree():
    return render_template('family_tree.html')

@app.route('/mapa')
def mapa():
    return render_template('map.html')

@app.route('/api/mapa')
def api_mapa():
    try:
        # Carregar coordenadas
        with open('parish_coords.json', 'r') as f:
            coords = json.load(f)
        
        # Obter contagem por freguesia do Supabase
        resp = requests.get(
            f"{SUPABASE_URL}/rest/v1/pessoas",
            headers=HEADERS,
            params={"select": "freguesia"},
            timeout=30
        )
        
        if resp.status_code == 200:
            data = resp.json()
            counts = {}
            for item in data:
                f = item.get('freguesia', 'Other')
                counts[f] = counts.get(f, 0) + 1
            
            # Combinar coordenadas com contagens
            map_data = []
            for f, coord in coords.items():
                map_data.append({
                    'freguesia': f,
                    'coords': coord,
                    'count': counts.get(f, 0)
                })
            return jsonify(map_data)
        
        return jsonify([]), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/validar')
def validar():
    # Buscar um registo com qualidade abaixo de 0.8 para revisão
    resp = requests.get(
        f"{SUPABASE_URL}/rest/v1/pessoas",
        headers=HEADERS,
        params={"qualidade": "lt.0.8", "limit": 1, "order": "qualidade"},
        timeout=30
    )
    registo = resp.json()[0] if resp.status_code == 200 and resp.json() else None
    return render_template('validate.html', registo=registo)

@app.route('/api/validar', methods=['POST'])
def salvar_validacao():
    dados = request.json
    id = dados.pop('id')
    
    # Atualizar registo como validado
    resp = requests.patch(
        f"{SUPABASE_URL}/rest/v1/pessoas?id=eq.{id}",
        headers=HEADERS,
        json={**dados, "qualidade": 1.0, "validado": True},
        timeout=30
    )
    return jsonify({"success": resp.status_code in [200, 204]})

@app.route('/api/pessoas')
def get_pessoas():
    try:
        query = request.args.get('q', '')
        url = SUPABASE_URL + '/rest/v1/pessoas?select=*'
        
        if query:
            # Pesquisa simplificada no nome
            url += f'&nome=ilike.*{query}*&limit=100'
        else:
            url += '&order=data_extracao.desc&limit=50'
            
        resp = requests.get(url, headers=HEADERS)
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
