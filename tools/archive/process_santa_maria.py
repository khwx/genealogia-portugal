"""
Script para processar registos de Santa Maria com Transkribus.
Extrai nomes do índice (últimas 5 páginas de cada livro).
"""
import requests
import json
import os
import time
import xml.etree.ElementTree as ET

# Ler configuração do .env
def get_config():
    config = {}
    with open('.env', 'r') as f:
        for line in f:
            if '=' in line and not line.startswith('#'):
                key, value = line.strip().split('=', 1)
                config[key] = value
    return config

config = get_config()

TRANSKRIBUS_USERNAME = config.get('TRANSKRIBUS_USERNAME', '')
TRANSKRIBUS_PASSWORD = config.get('TRANSKRIBUS_PASSWORD', '')
TRANSKRIBUS_BASE_URL = "https://transkribus.eu/TrpServer/rest"


def login_transkribus():
    """Faz login no Transkribus e retorna o sessionId."""
    print("Fazendo login no Transkribus...")
    
    url = f"{TRANSKRIBUS_BASE_URL}/auth/login"
    data = {
        "user": TRANSKRIBUS_USERNAME,
        "pw": TRANSKRIBUS_PASSWORD
    }
    
    resp = requests.post(url, data=data, timeout=30)
    
    if resp.status_code == 200:
        # Parse XML response
        root = ET.fromstring(resp.text)
        session_id = root.find('sessionId').text
        user_id = root.find('userId').text
        name = root.find('firstname').text + " " + root.find('lastname').text
        
        print(f"✅ Login: {name} (ID: {user_id})")
        return session_id
    else:
        print(f"❌ Login falhou: {resp.status_code}")
        return None


def get_collections(session_id):
    """Obtém as coleções do utilizador."""
    print("\nObtendo coleções...")
    
    url = f"{TRANSKRIBUS_BASE_URL}/collections/list"
    headers = {"Cookie": f"JSESSIONID={session_id}"}
    
    resp = requests.get(url, headers=headers, timeout=30)
    
    if resp.status_code == 200:
        root = ET.fromstring(resp.text)
        collections = []
        for coll in root.findall('.//colList'):
            coll_id = coll.find('colId').text
            coll_name = coll.find('colName').text
            collections.append({"id": coll_id, "name": coll_name})
            print(f"  {coll_id}: {coll_name}")
        return collections
    else:
        print(f"❌ Erro: {resp.status_code}")
        return []


def process_santa_maria_books(session_id, num_books=5):
    """Processa os primeiros N livros de Santa Maria."""
    print(f"\n=== PROCESSANDO SANTA MARIA ({num_books} livros) ===")
    
    # Carregar inventário
    with open('output/obitos_inventario.json') as f:
        inventory = json.load(f)
    
    # Filtrar Santa Maria
    santa_maria = [r for r in inventory if 'Santa Maria' in r.get('freguesia', '')]
    print(f"Total de livros de Santa Maria: {len(santa_maria)}")
    
    # Processar apenas os primeiros N livros
    for i, book in enumerate(santa_maria[:num_books]):
        print(f"\n--- Livro {i+1}/{num_books} ---")
        print(f"Título: {book['titulo']}")
        print(f"Datas: {book['datas']}")
        print(f"URL: {book['url_viewer'][:60]}...")
        
        # Extrair documentId do URL
        doc_id = extract_document_id(book['url_viewer'])
        if doc_id:
            print(f"Document ID: {doc_id}")
            
            # Aqui iríamos descarregar as últimas páginas
            # e enviar para o Transkribus para OCR
            # Por agora, apenas marcamos como processado
            print(f"✅ Marcado para processamento")
        else:
            print(f"❌ Não foi possível extrair document ID")
    
    return len(santa_maria[:num_books])


def extract_document_id(url):
    """Extrai o documentId do URL do digitarq."""
    if "fileViewer/" in url:
        return url.split("fileViewer/")[1].split("?")[0]
    elif "documentDetails/" in url:
        return url.split("documentDetails/")[1].split("?")[0]
    return None


if __name__ == "__main__":
    # 1. Login
    session_id = login_transkribus()
    
    if session_id:
        # 2. Obter coleções
        collections = get_collections(session_id)
        
        # 3. Processar Santa Maria
        num_processed = process_santa_maria_books(session_id, num_books=5)
        
        print(f"\n=== RESUMO ===")
        print(f"Livros processados: {num_processed}")
        print(f"Próximo passo: Descarregar imagens e enviar para Transkribus")
