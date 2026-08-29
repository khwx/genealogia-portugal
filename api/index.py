from flask import Flask, jsonify, request, render_template_string, render_template
import requests
import os
import json
import sys
import time

# Load .env (same pattern as other scripts, so it works on a fresh clone)
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

try:
    import name_phonetics
except ImportError:
    name_phonetics = None
env_file = os.path.join(_root, '.env')
if not os.path.exists(env_file):
    env_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
if os.path.exists(env_file):
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                k, v = line.split('=', 1)
                os.environ[k.strip()] = v.strip()

app = Flask(__name__, template_folder=os.path.join(_root, 'templates'))

SUPABASE_URL = os.environ.get('SUPABASE_URL', 'https://qljopxbxgflozrcdblrl.supabase.co')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY', '') or os.environ.get('SUPABASE_ANON_KEY', '')

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

# Cache simples em memória para /api/mapa, /api/seculos, /api/decadas (TTL 10 min)
_CACHE = {}
_CACHE_TTL = 600
def cache_get(key):
    v = _CACHE.get(key)
    if v and time.time() - v[0] < _CACHE_TTL:
        return v[1]
    return None
def cache_set(key, data):
    _CACHE[key] = (time.time(), data)

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

@app.route('/casamentos')
def casamentos():
    return render_template('casamentos.html')

@app.route('/batismos')
def batismos():
    return render_template('batismos.html')

@app.route('/mapa')
def mapa():
    return render_template('map.html')

@app.route('/api/mapa')
def api_mapa():
    cached = cache_get('mapa')
    if cached is not None:
        return jsonify(cached)
    try:
        # Carregar coordenadas
        with open(os.path.join(_root, 'parish_coords.json'), 'r') as f:
            coords = json.load(f)
        
        # Obter contagem por freguesia do Supabase (com paginação para abranger todos os 8700+ registos)
        counts = {}
        # Distribuição por século por freguesia (para os popups do mapa)
        parish_centuries = {}
        offset = 0
        page = 1000
        while True:
            resp = requests.get(
                f"{SUPABASE_URL}/rest/v1/pessoas",
                headers=HEADERS,
                params={"select": "freguesia,data_obito", "limit": page, "offset": offset},
                timeout=30
            )
            if resp.status_code != 200:
                break
            batch = resp.json()
            if not batch:
                break
            for item in batch:
                f = item.get('freguesia') or 'Outras'
                counts[f] = counts.get(f, 0) + 1
                d = item.get('data_obito')
                if d:
                    try:
                        if 'T' in d:
                            year = int(d[:4])
                        else:
                            year = int(str(d).split('-')[0])
                        if year >= 1000:
                            seculo = (year - 1) // 100 + 1
                            pc = parish_centuries.setdefault(f, {})
                            pc[seculo] = pc.get(seculo, 0) + 1
                    except (ValueError, TypeError):
                        pass
            if len(batch) < page:
                break
            offset += page
        
        # Combinar coordenadas com contagens e períodos cronológicos
        map_data = []
        for f, coord in coords.items():
            periodos = parish_centuries.get(f, {})
            # Ordenar séculos por ordem cronológica e manter só com registos
            periodos_ordenados = {s: periodos[s] for s in sorted(periodos.keys()) if periodos[s] > 0}
            map_data.append({
                'freguesia': f,
                'coords': coord,
                'count': counts.get(f, 0),
                'periodos': periodos_ordenados
            })
        cache_set('mapa', map_data)
        return jsonify(map_data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/seculos')
def api_seculos():
    cached = cache_get('seculos')
    if cached is not None:
        return jsonify(cached)
    # Distribuição de registos por século (apenas leitura, sem segredos).
    # Usa o mesmo padrão de paginação de /api/mapa para abranger todos os registos.
    try:
        centuries = {}
        offset = 0
        page = 1000
        while True:
            resp = requests.get(
                f"{SUPABASE_URL}/rest/v1/pessoas",
                headers=HEADERS,
                params={"select": "data_obito", "limit": page, "offset": offset},
                timeout=30
            )
            if resp.status_code != 200:
                break
            batch = resp.json()
            if not batch:
                break
            for item in batch:
                d = item.get('data_obito')
                if not d:
                    continue
                year = None
                try:
                    if 'T' in d:
                        year = int(d[:4])
                    else:
                        year = int(str(d).split('-')[0])
                except (ValueError, TypeError):
                    continue
                if year < 1000:
                    continue
                seculo = (year - 1) // 100 + 1
                centuries[seculo] = centuries.get(seculo, 0) + 1
            if len(batch) < page:
                break
            offset += page

        result = [
            {"seculo": f"{s}", "count": centuries[s]}
            for s in sorted(centuries.keys())
        ]
        payload = {"seculos": result}
        cache_set('seculos', payload)
        return jsonify(payload)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/decadas')
def api_decadas():
    cached = cache_get('decadas')
    if cached is not None:
        return jsonify(cached)
    try:
        decadas = {}
        offset = 0
        page = 1000
        while True:
            resp = requests.get(
                f"{SUPABASE_URL}/rest/v1/pessoas",
                headers=HEADERS,
                params={"select": "data_obito", "limit": page, "offset": offset},
                timeout=30
            )
            if resp.status_code != 200:
                break
            batch = resp.json()
            if not batch:
                break
            for item in batch:
                d = item.get('data_obito')
                if not d:
                    continue
                try:
                    year = int(str(d)[:4]) if str(d)[:4].isdigit() else None
                    if year and 1000 <= year <= 2100:
                        dec = (year // 10) * 10
                        decadas[dec] = decadas.get(dec, 0) + 1
                except:
                    continue
            if len(batch) < page:
                break
            offset += page
        result = [{"decada": k, "count": decadas[k]} for k in sorted(decadas.keys())]
        payload = {"decadas": result}
        cache_set('decadas', payload)
        return jsonify(payload)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/stats-extras')
def api_stats_extras():
    cached = cache_get('stats_extras')
    if cached is not None:
        return jsonify(cached)
    try:
        from collections import Counter
        sobrenomes = Counter()
        idades = Counter()
        offset = 0
        page = 1000
        while True:
            resp = requests.get(
                f"{SUPABASE_URL}/rest/v1/pessoas",
                headers=HEADERS,
                params={"select": "sobrenome,idade", "limit": page, "offset": offset},
                timeout=30
            )
            if resp.status_code != 200:
                break
            batch = resp.json()
            if not batch:
                break
            for r in batch:
                s = (r.get('sobrenome') or '').strip()
                if s and s.lower() not in ('[ilegível]','[ileg]'):
                    sobrenomes[s] += 1
                idade = r.get('idade')
                if isinstance(idade, int) and 0 < idade < 110:
                    bucket = f"{(idade//10)*10}-{(idade//10)*10+9}"
                    idades[bucket] += 1
            if len(batch) < page:
                break
            offset += page
        top = [{"nome": k, "count": v} for k, v in sobrenomes.most_common(10)]
        idade_dist = [{"faixa": k, "count": v} for k, v in sorted(idades.items())]
        payload = {"top_sobrenomes": top, "idade_dist": idade_dist}
        cache_set('stats_extras', payload)
        return jsonify(payload)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/validar')
def validar():
    # Buscar um registo ainda não validado, saltando [ilegível]/[não consta] por defeito
    # Se só houver ilegíveis, mostra o primeiro na mesma para permitir rejeitar
    for filt in [
        {"validado": "eq.false", "nome": "not.is.null", "nome_not_ilike": "[ilegível]", "limit": 5},
        {"validado": "eq.false", "nome": "not.is.null", "limit": 5},
    ]:
        params = {"validado": filt["validado"], "nome": filt["nome"], "limit": filt["limit"], "order": "criado_em.desc"}
        resp = requests.get(f"{SUPABASE_URL}/rest/v1/pessoas", headers=HEADERS, params=params, timeout=30)
        if resp.status_code == 200 and resp.json():
            batch = resp.json()
            # filtrar localmente ilegíveis na primeira volta
            if "nome_not_ilike" in filt:
                filtered = [r for r in batch if "[ileg" not in (r.get("nome") or "").lower() and "[não" not in (r.get("nome") or "").lower()]
                if filtered:
                    return render_template('validate.html', registo=filtered[0])
                continue
            return render_template('validate.html', registo=batch[0])
    return render_template('validate.html', registo=None)

@app.route('/api/validar', methods=['POST'])
def salvar_validacao():
    dados = request.json
    id = dados.pop('id')
    acao = dados.pop('acao', 'aprovar')  # aprovar | rejeitar | ilegivel
    if acao in ('rejeitar', 'ilegivel', 'saltar'):
        # Marca como validado mas com qualidade 0 para não voltar à fila de revisão
        # e não poluir a pesquisa pública (excluída pelo filtro qualidade.gt.0)
        resp = requests.patch(
            f"{SUPABASE_URL}/rest/v1/pessoas?id=eq.{id}",
            headers=HEADERS,
            json={"validado": True, "qualidade": 0.0},
            timeout=30
        )
        return jsonify({"success": resp.status_code in [200, 204]})
    # aprovar: atualiza nome corrigido
    resp = requests.patch(
        f"{SUPABASE_URL}/rest/v1/pessoas?id=eq.{id}",
        headers=HEADERS,
        json={**dados, "qualidade": 1.0, "validado": True},
        timeout=30
    )
    return jsonify({"success": resp.status_code in [200, 204]})

@app.route('/api/pessoas')
def get_pessoas():
    # Server-side search used by the web app. Supports the same filters as
    # the browser (text, freguesia, year range) plus a record-type filter
    # (tipo_registo) so the schema prepared in Fase 3 (DEAT/MARR/BIRT) is
    # already usable once the migration is applied. Degrades safely if the
    # tipo_registo column is not present yet.
    try:
        query = request.args.get('q', '').strip()
        freguesia = request.args.get('freguesia', '').strip()
        from_year = request.args.get('from_year', '').strip()
        to_year = request.args.get('to_year', '').strip()
        tipo = request.args.get('tipo', '').strip().upper()
        try:
            limit = max(1, min(int(request.args.get('limit', 50)), 1000))
        except ValueError:
            limit = 50
        try:
            offset = max(0, int(request.args.get('offset', 0)))
        except ValueError:
            offset = 0

        # Validate year inputs (avoid injecting arbitrary values into the URL).
        def _valid_year(v):
            return v.isdigit() and 1000 <= int(v) <= 2999

        url = SUPABASE_URL + '/rest/v1/pessoas?select=*'
        conditions = []
        # Excluir da pesquisa pública os registos rejeitados/ilegíveis na revisão
        # (qualidade = 0). Mantém os registos ainda por validar (qualidade NULL) e
        # os aprovados (>= 1). Não afeta a fila de revisão, que usa outra query.
        conditions.append('or(qualidade.gt.0,qualidade.is.null)')
        if query:
            if name_phonetics:
                phonetic_cond = name_phonetics.build_postgrest_query_condition(query)
                if phonetic_cond:
                    conditions.append(phonetic_cond)
                else:
                    conditions.append(
                        f"or(nome.ilike.*{query}*,sobrenome.ilike.*{query}*,freguesia.ilike.*{query}*)"
                    )
            else:
                conditions.append(
                    f"or(nome.ilike.*{query}*,sobrenome.ilike.*{query}*,freguesia.ilike.*{query}*)"
                )
        if freguesia:
            conditions.append(f"freguesia.ilike.*{freguesia}*")
        if _valid_year(from_year):
            conditions.append(f"data_obito.gte.{from_year}-01-01")
        if _valid_year(to_year):
            conditions.append(f"data_obito.lte.{to_year}-12-31")
        if tipo in ('DEAT', 'MARR', 'BIRT'):
            conditions.append(f"tipo_registo=eq.{tipo}")

        if conditions:
            url += '&' + '&'.join(conditions)
            url += f'&order=criado_em.desc&limit={limit}&offset={offset}'
        else:
            url += f'&order=criado_em.desc&limit={limit}&offset={offset}'

        resp = requests.get(url, headers=HEADERS, timeout=30)
        if resp.status_code != 200:
            return jsonify({"error": resp.text[:300]}), resp.status_code
        data = resp.json()
        # Pesquisa fonética simples: se 0 resultados e query tem 3+ letras, tenta variantes pt
        if not data and query and len(query) >= 3:
            import unicodedata
            def norm(s):
                s = unicodedata.normalize('NFD', s).encode('ascii','ignore').decode()
                s = s.lower().replace('ph','f').replace('y','i').replace('w','v').replace('ck','k').replace('th','t')
                s = s.replace('joam','joao').replace('theresa','teresa').replace('thereza','teresa')
                return s
            phon = norm(query)
            if phon != query.lower():
                url2 = SUPABASE_URL + '/rest/v1/pessoas?select=*'
                cond2 = f"or(nome.ilike.*{phon}*,sobrenome.ilike.*{phon}*,freguesia.ilike.*{phon}*)"
                url2 += '&' + cond2 + f'&order=criado_em.desc&limit={limit}&offset={offset}'
                r2 = requests.get(url2, headers=HEADERS, timeout=30)
                if r2.status_code == 200 and r2.json():
                    return jsonify(r2.json())
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/variantes')
def api_variantes():
    # Consulta de variantes históricas e código fonético para suporte à pesquisa
    try:
        q = request.args.get('q', '').strip()
        if not q or not name_phonetics:
            return jsonify({"query": q, "variants": [q] if q else [], "soundex": ""})
        variants = name_phonetics.expand_name_variants(q)
        return jsonify({
            "query": q,
            "variants": variants,
            "soundex": name_phonetics.soundex_pt(q)
        })
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
