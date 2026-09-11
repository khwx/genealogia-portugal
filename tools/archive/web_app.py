"""
Web search interface for the Celorico da Beira genealogy project.
Provides a web interface to search death records.
"""
from flask import Flask, render_template, request, jsonify, redirect, url_for
import json
import os

import config
from database import get_all_obitos, search_by_name, get_statistics

app = Flask(__name__)

@app.route('/')
def index():
    """Home page with search form and statistics."""
    stats = get_statistics()
    return render_template('index.html', stats=stats)

@app.route('/search')
def search():
    """Search for records by name."""
    query = request.args.get('q', '').strip()
    
    if not query:
        return redirect(url_for('index'))
    
    results = search_by_name(query)
    stats = get_statistics()
    
    return render_template('search_results.html', 
                         query=query, 
                         results=results, 
                         stats=stats,
                         total_results=len(results))

@app.route('/api/search')
def api_search():
    """API endpoint for searching records."""
    query = request.args.get('q', '').strip()
    limit = request.args.get('limit', 50, type=int)
    
    if not query:
        return jsonify({"error": "Query parameter 'q' is required"}), 400
    
    results = search_by_name(query)
    
    # Limit results
    results = results[:limit]
    
    return jsonify({
        "query": query,
        "total_results": len(results),
        "results": results
    })

@app.route('/obito/<int:obito_id>')
def obito_detail(obito_id):
    """Show details for a specific death record."""
    from database import get_connection
    
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM obitos WHERE id = ?", (obito_id,))
    obito = cursor.fetchone()
    
    if not obito:
        return "Record not found", 404
    
    # Get external sources
    cursor.execute("""
        SELECT fonte, id_externo, dados_json 
        FROM external_sources 
        WHERE obito_id = ?
    """, (obito_id,))
    external_sources = cursor.fetchall()
    
    conn.close()
    
    obito_dict = dict(obito)
    obito_dict['external_sources'] = [
        {
            "fonte": row[0],
            "id_externo": row[1],
            "dados": json.loads(row[2]) if row[2] else None
        }
        for row in external_sources
    ]
    
    return render_template('obito_detail.html', obito=obito_dict)

@app.route('/freguesia/<freguesia_name>')
def freguesia_page(freguesia_name):
    """Show all records for a specific freguesia."""
    from database import get_connection
    
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM obitos WHERE freguesia = ? ORDER BY data_obito", 
                   (freguesia_name,))
    results = cursor.fetchall()
    
    stats = get_statistics()
    
    conn.close()
    
    return render_template('freguesia.html',
                         freguesia=freguesia_name,
                         results=[dict(row) for row in results],
                         stats=stats,
                         total_results=len(results))

@app.route('/stats')
def stats_page():
    """Show detailed statistics."""
    stats = get_statistics()
    return render_template('stats.html', stats=stats)

@app.route('/about')
def about():
    """About page."""
    return render_template('about.html')

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
