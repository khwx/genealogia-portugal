#!/usr/bin/env python3
"""
Navegar para última página do Digitarq usando Chrome DevTools Protocol.
"""
import subprocess
import json
import time
import requests

def get_chrome_debugger_url():
    """Inicia Chrome com debugging e obtém URL."""
    cmd = [
        "docker", "run", "--rm", "-d",
        "--network", "bridge",
        "-p", "9222:9222",
        "chrome-ocr",
        "google-chrome",
        "--headless=new",
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--remote-debugging-port=9222",
        "--disable-gpu",
        "--virtual-time-budget=60000",
        "about:blank"
    ]
    subprocess.run(cmd, capture_output=True)
    time.sleep(3)
    
    # Obter URL do WebSocket
    resp = requests.get("http://localhost:9222/json", timeout=10)
    data = resp.json()
    return data[0]["webSocketDebuggerUrl"]

def navigate_to_last_page(ws_url, doc_id, total_pages=61):
    """Naviga para última página usando CDP."""
    # Enviar comando JavaScript para navegar para última página
    cmd = {
        "id": 1,
        "method": "Runtime.evaluate",
        "params": {
            "expression": f"""
                // Tentar navegar para última página
                fetch('https://digitarq.arquivos.pt/fileViewer/{doc_id}?page={total_pages}')
                    .then(r => r.text())
                    .then(console.log)
            """,
            "returnByValue": True
        }
    }
    # Preciso de uma biblioteca CDP
    return False

def try_js_navigation():
    """Tentar navegação via JavaScript no dump-dom."""
    # O dump-dom não executa JS dinamicamente
    # Precisamos usar abordagem diferente
    
    # Testar: usar a opção --打印 DOM após executar JS
    cmd = [
        "docker", "run", "--rm", "--network", "bridge",
        "chrome-ocr",
        "google-chrome",
        "--headless=new",
        "--no-sandbox", 
        "--disable-dev-shm-usage",
        "--virtual-time-budget=30000",
        "--dump-dom",
        "https://digitarq.arquivos.pt/fileViewer/fd0cf2bc50b14e739e362b44c64dc194#100"  # Hash
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=45)
    
    # Procurar dados dos registos
    if "óbitos" in result.stdout.lower() or "falecimento" in result.stdout.lower():
        print("✅ Encontrou registos!")
        return True
    
    print("Não encontrou dados - tentando API...")
    return False

# Testar API do Digitarq
def test_api():
    """Testar endpoint da API."""
    url = "https://digitarq.arquivos.pt/api/v1/records/fd0cf2bc50b14e739e362b44c64dc194"
    resp = requests.get(url, timeout=10)
    print(f"Status: {resp.status_code}")
    if resp.status_code == 200:
        try:
            data = resp.json()
            print(f"JSON: {json.dumps(data)[:500]}")
        except:
            print(f"Text: {resp.text[:500]}")

if __name__ == "__main__":
    print("1. Testar navegação JS...")
    try_js_navigation()
    
    print("\n2. Testar API...")
    test_api()