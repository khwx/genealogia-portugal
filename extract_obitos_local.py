"""
Script completo para extração de nomes de registos de óbitos.
Funciona no teu PC local com Selenium + Google Vision + NVIDIA API + Supabase.

Requisitos:
- pip install selenium requests beautifulsoup4 python-dotenv
- Google Chrome instalado
- Google Vision API key (sem restrição de IP)
- NVIDIA API key
- Supabase credentials

Uso:
python extract_obitos_local.py
"""
import requests
import json
import base64
import os
import time
import re
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

# Ler configuração do .env
def get_config():
    config = {}
    env_path = Path(__file__).parent / '.env'
    with open(env_path, 'r') as f:
        for line in f:
            if '=' in line and not line.startswith('#'):
                key, value = line.strip().split('=', 1)
                config[key] = value
    return config

config = get_config()

GOOGLE_VISION_API_KEY = config.get('GOOGLE_VISION_API_KEY', '')
NVIDIA_API_KEY = config.get('NVIDIA_API_KEY', '')
SUPABASE_URL = config.get('SUPABASE_URL', '')
SUPABASE_KEY = config.get('SUPABASE_KEY', '')

IMAGES_DIR = Path(__file__).parent / 'output' / 'images'
IMAGES_DIR.mkdir(parents=True, exist_ok=True)


def setup_browser():
    """Configura o browser Selenium."""
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-software-rasterizer")
    
    try:
        driver = webdriver.Chrome(options=chrome_options)  # type: ignore
        print("✅ Browser iniciado com Chrome padrão")
        return driver
    except Exception as e:
        print(f"⚠️  Erro com Chrome padrão: {e}")
        print("Tenta instalar o chromedriver: sudo apt install chromium-chromedriver")
        return None


def get_image_urls_from_digitarq(doc_id, page_numbers=None, max_pages=10):
    """
    Usa Selenium para obter URLs de imagens do digitarq.
    """
    print(f"\n🌐 A obter imagens do documento {doc_id}...")
    
    driver = setup_browser()
    if not driver:
        return []
    
    try:
        base_url = "https://digitarq.arquivos.pt"
        url = f"{base_url}/fileViewer/{doc_id}?isRepresentation=false"
        
        print(f"   A carregar: {url}")
        driver.get(url)
        
        # Aguardar carregamento completo (JavaScript + imagens)
        print("   A aguardar carregamento (10s)...")
        time.sleep(10)
        
        # Tentar esperar pelo visor de imagens
        try:
            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "img, canvas, .viewer, [data-testid]"))
            )
        except:
            pass
        
        image_urls = []
        
        # 1. Capturar logs de rede para encontrar URLs de imagens
        try:
            logs = driver.get_log('performance')
            for log in logs:
                try:
                    message = json.loads(log['message'])
                    method = message['message'].get('method', '')
                    if method == 'Network.responseReceived':
                        response = message['message']['params']['response']
                        resp_url = response.get('url', '')
                        content_type = response.get('mimeType', '')
                        
                        if 'image' in content_type:
                            if resp_url not in image_urls:
                                image_urls.append(resp_url)
                                print(f"   🖼️  Log: {resp_url[:80]}...")
                except:
                    pass
        except:
            pass
        
        # 2. Procurar elementos de imagem no DOM (Next.js selectors)
        if not image_urls:
            print("   A procurar imagens no DOM...")
            selectors = [
                "img[src*='image']",
                "img[src*='jpg']", 
                "img[src*='jpeg']",
                "canvas",
                "[data-testid*='image']",
                ".viewer img",
                ".digitool img",
                "div[role='img'] img",
                "img"
            ]
            
            for selector in selectors:
                try:
                    imgs = driver.find_elements(By.CSS_SELECTOR, selector)
                    for img in imgs:
                        src = img.get_attribute('src') or img.get_attribute('data-src')
                        if src and src.startswith('http') and src not in image_urls:
                            # Verificar se é uma URL de imagem válida
                            if any(ext in src.lower() for ext in ['.jpg', '.jpeg', '.png', '.tiff', '.gif', 'image']):
                                image_urls.append(src)
                                print(f"   🖼️  DOM: {src[:80]}...")
                except:
                    pass
        
        # 3. Se ainda não encontrou, fazer screenshot das páginas
        if not image_urls:
            print("   A capturar screenshots das páginas...")
            capture_screenshots(driver, doc_id, max_pages)
        
        print(f"\n✅ Encontradas {len(image_urls)} imagens")
        return image_urls
        
    except Exception as e:
        print(f"❌ Erro: {e}")
        return []
    finally:
        driver.quit()


def capture_screenshots(driver, doc_id, max_pages=10):
    """
    Captura screenshots de múltiplas páginas navigando no viewer.
    """
    print("   A navegar e capturar páginas...")
    
    try:
        # Tentar encontrar e clicar no botão de última página (para ver índice)
        # O Digitarq novo pode ter diferentes botões
        page_navigation_attempts = 0
        
        while page_navigation_attempts < max_pages:
            try:
                # Procurar botão de próximo/última página
                buttons = driver.find_elements(By.CSS_SELECTOR, "button")
                
                clicked = False
                for btn in buttons:
                    btn_text = btn.text.lower()
                    if any(term in btn_text for term in ['próxima', 'next', 'ultima', 'last', '>', '>>']):
                        try:
                            btn.click()
                            time.sleep(3)
                            clicked = True
                            break
                        except:
                            continue
                
                if not clicked:
                    break
                    
                page_navigation_attempts += 1
                
                # Capturar screenshot
                screenshot_path = IMAGES_DIR / f"{doc_id}_page_{page_navigation_attempts}.png"
                driver.save_screenshot(str(screenshot_path))
                print(f"   📸 Página {page_navigation_attempts}: {screenshot_path.name}")
                
            except Exception as e:
                print(f"   ⚠️  Erro navegação: {e}")
                break
        
        # Se não navegou, tirar pelo menos 1 screenshot da página atual
        if page_navigation_attempts == 0:
            screenshot_path = IMAGES_DIR / f"{doc_id}_page_1.png"
            driver.save_screenshot(str(screenshot_path))
            print(f"   📸 Screenshot: {screenshot_path.name}")
            
    except Exception as e:
        print(f"   ⚠️  Erro ao capturar: {e}")


def create_session():
    """Cria sessão requests com retry logic."""
    session = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[500, 502, 503, 504]
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('https://', adapter)
    session.mount('http://', adapter)
    return session


def download_single_image(args):
    """Descarrega uma única imagem (para uso com thread pool)."""
    url, filename, session = args
    try:
        resp = session.get(url, timeout=60, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        if resp.status_code == 200 and len(resp.content) > 10000:
            with open(filename, 'wb') as f:
                f.write(resp.content)
            return filename, len(resp.content)
        return None, 0
    except Exception as e:
        return None, str(e)


def download_images(image_urls):
    """
    Descarrega as imagens para a pasta local com concurrent downloads.
    """
    print(f"\n💾 A descarregar {len(image_urls)} imagens (5 em paralelo)...")
    
    session = create_session()
    downloaded = []
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        args_list = [
            (url, IMAGES_DIR / f"page_{i+1}.jpg", session)
            for i, url in enumerate(image_urls)
        ]
        
        results = list(executor.map(download_single_image, args_list))
        
        for filename, size in results:
            if filename:
                downloaded.append(filename)
                print(f"   ✅ {filename.name} ({size} bytes)")
            else:
                print(f"   ❌ Erro: {size}")
    
    return downloaded


def google_vision_ocr(image_path):
    """
    Usa Google Vision API para extrair texto de uma imagem.
    """
    print(f"\n📷 Google Vision OCR: {os.path.basename(image_path)}")
    
    with open(image_path, 'rb') as f:
        image_data = base64.b64encode(f.read()).decode()
    
    url = f"https://vision.googleapis.com/v1/images:annotate?key={GOOGLE_VISION_API_KEY}"
    
    payload = {
        "requests": [
            {
                "image": {
                    "content": image_data
                },
                "features": [
                    {
                        "type": "TEXT_DETECTION",
                        "maxResults": 50
                    }
                ],
                "imageContext": {
                    "languageHints": ["pt"]
                }
            }
        ]
    }
    
    try:
        resp = requests.post(url, json=payload, timeout=60)
        
        if resp.status_code == 200:
            result = resp.json()
            if "responses" in result and result["responses"]:
                detections = result["responses"][0].get("textAnnotations", [])
                if detections:
                    full_text = detections[0].get("description", "")
                    confidence = detections[0].get("confidence", 0)
                    print(f"  ✅ Texto extraído (confiança: {confidence:.2f})")
                    return full_text
                else:
                    print("  ❌ Nenhum texto encontrado")
                    return ""
            else:
                print(f"  ❌ Resposta inválida: {result}")
                return ""
        else:
            print(f"  ❌ Erro HTTP {resp.status_code}: {resp.text[:200]}")
            return ""
    except Exception as e:
        print(f"  ❌ Erro: {e}")
        return ""


def nvidia_extract_names(ocr_text):
    """
    Usa NVIDIA API para extrair nomes e datas do texto OCR.
    """
    if not ocr_text or not ocr_text.strip():
        return []
    
    print(f"  🧠 NVIDIA API: Extraindo nomes...")
    
    url = "https://integrate.api.nvidia.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {NVIDIA_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "meta/llama-3.1-8b-instruct",
        "messages": [
            {
                "role": "system",
                "content": """You are a Portuguese genealogy expert. Extract names and death dates from OCR text of historical death record indexes.

Rules:
1. Return ONLY a JSON array
2. Each object must have 'nome' (full name) and 'data_obito' (death date in format 'DD de Mês de AAAA')
3. If a date is not found, use null for data_obito
4. If a name is unclear, use the best guess
5. Do NOT include any text outside the JSON array
6. Handle Portuguese names correctly (da Silva, dos Santos, etc.)
7. The text is from a death record index, so each line typically has: number, name, date"""
            },
            {
                "role": "user",
                "content": f"Extract all names and death dates from this OCR text of a Portuguese death record index:\n\n{ocr_text}"
            }
        ],
        "temperature": 0.1,
        "max_tokens": 2000
    }
    
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=60)
        
        if resp.status_code == 200:
            result = resp.json()
            content = result['choices'][0]['message']['content']
            
            # Parse JSON
            try:
                # Limpar possível markdown
                content = content.strip()
                if content.startswith('```'):
                    content = content.split('```')[1]
                    if content.startswith('json'):
                        content = content[4:]
                    content = content.strip()
                
                data = json.loads(content)
                if isinstance(data, list):
                    print(f"  ✅ {len(data)} nomes extraídos")
                    return data
                else:
                    print(f"  ⚠️  Resposta não é uma lista: {type(data)}")
                    return []
            except json.JSONDecodeError as e:
                print(f"  ❌ Erro ao parsear JSON: {e}")
                print(f"  Conteúdo: {content[:500]}")
                return []
        else:
            print(f"  ❌ Erro API {resp.status_code}: {resp.text[:200]}")
            return []
    except Exception as e:
        print(f"  ❌ Erro de conexão: {e}")
        return []


def normalize_date(date_str):
    """
    Converte '15 de Janeiro de 1864' para '1864-01-15'
    """
    if not date_str:
        return None
    
    date_str = date_str.lower().strip()
    
    meses = {
        "janeiro": "01", "jan": "01",
        "fevereiro": "02", "fev": "02",
        "março": "03", "marco": "03", "mar": "03",
        "abril": "04", "abr": "04",
        "maio": "05", "mai": "05",
        "junho": "06", "jun": "06",
        "julho": "07", "jul": "07",
        "agosto": "08", "ago": "08",
        "setembro": "09", "set": "09",
        "outubro": "10", "out": "10",
        "novembro": "11", "nov": "11",
        "dezembro": "12", "dez": "12",
    }
    
    # Tentar formato: DD de Mês de AAAA
    match = re.search(r'(\d{1,2})\s+de\s+(\w+)\s+de\s+(\d{4})', date_str)
    if match:
        day = match.group(1).zfill(2)
        month_name = match.group(2)
        year = match.group(3)
        month = meses.get(month_name, "01")
        return f"{year}-{month}-{day}"
    
    # Tentar formato: DD/MM/AAAA
    match = re.search(r'(\d{1,2})/(\d{1,2})/(\d{4})', date_str)
    if match:
        day = match.group(1).zfill(2)
        month = match.group(2).zfill(2)
        year = match.group(3)
        return f"{year}-{month}-{day}"
    
    # Tentar formato: AAAA-MM-DD
    match = re.search(r'(\d{4})-(\d{2})-(\d{2})', date_str)
    if match:
        return date_str[:10]
    
    return None


def save_to_supabase(records, freguesia="Celorico (Santa Maria)"):
    """
    Guarda os registos extraídos no Supabase.
    """
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("❌ Credenciais do Supabase não encontradas")
        return 0
    
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }
    
    saved = 0
    for record in records:
        nome = record.get('nome', '')
        data_obito = normalize_date(record.get('data_obito', ''))
        
        if not nome:
            continue
        
        data = {
            "nome": nome,
            "data_obito": data_obito,
            "fonte": "Google Vision + NVIDIA OCR",
            "freguesia": freguesia,
            "concelho": "Celorico da Beira",
            "distrito": "Guarda"
        }
        
        resp = requests.post(
            f"{SUPABASE_URL}/rest/v1/pessoas",
            headers=headers,
            json=data,
            timeout=30
        )
        
        if resp.status_code in [200, 201]:
            saved += 1
            print(f"  ✅ Guardado: {nome} ({data_obito})")
        else:
            print(f"  ⚠️  Erro ao guardar '{nome}': {resp.status_code}")
        
        # Rate limiting
        time.sleep(0.1)
    
    return saved


def process_local_images():
    """
    Processa imagens já existentes na pasta output/images/
    """
    image_files = list(IMAGES_DIR.glob("*.jpg")) + \
                  list(IMAGES_DIR.glob("*.jpeg")) + \
                  list(IMAGES_DIR.glob("*.png")) + \
                  list(IMAGES_DIR.glob("*.tiff")) + \
                  list(IMAGES_DIR.glob("*.bmp"))
    
    if not image_files:
        print(f"❌ Nenhuma imagem encontrada em {IMAGES_DIR}")
        return []
    
    print(f"=== PROCESSANDO {len(image_files)} IMAGENS ===\n")
    
    all_records = []
    
    for i, image_path in enumerate(sorted(image_files)):
        print(f"\n--- Imagem {i+1}/{len(image_files)}: {image_path.name} ---")
        
        # 1. OCR com Google Vision
        ocr_text = google_vision_ocr(image_path)
        
        if not ocr_text:
            print("  ⚠️  Nenhum texto extraído, a continuar...")
            continue
        
        # 2. Extrair nomes com NVIDIA API
        records = nvidia_extract_names(ocr_text)
        
        if records:
            all_records.extend(records)
        
        # Rate limiting
        time.sleep(1)
    
    return all_records


def process_book_from_inventory(inventory_file, freguesia_filter=None):
    """
    Processa um livro do inventário obtendo imagens via Selenium.
    """
    import json
    
    # Ler inventário
    with open(inventory_file, 'r', encoding='utf-8') as f:
        books = json.load(f)
    
    # Filtrar por freguesia se especificado
    if freguesia_filter:
        books = [b for b in books if freguesia_filter.lower() in b.get('freguesia', '').lower()]
    
    print(f"\n=== A PROCESSAR {len(books)} LIVROS ===")
    
    for i, book in enumerate(books):
        freguesia = book.get('freguesia', 'Desconhecido')
        titulo = book.get('titulo', '')
        dates = book.get('datas', '')
        url = book.get('url_viewer', '')
        
        # Extrair doc_id da URL
        if 'fileViewer/' in url:
            doc_id = url.split('fileViewer/')[1].split('?')[0]
        else:
            continue
        
        print(f"\n[{i+1}/{len(books)}] {freguesia} ({dates})")
        print(f"   {titulo}")
        
        # Obter imagens
        image_urls = get_image_urls_from_digitarq(doc_id, max_pages=5)
        
        if image_urls:
            # Descarregar imagens
            downloaded = download_images(image_urls)
            print(f"   ✅ {len(downloaded)} imagens guardadas")
        else:
            print("   ⚠️  Sem imagens - a verificar screenshots...")
        
        # Rate limiting entre livros
        time.sleep(2)
    
    print("\n✅ Processamento concluído!")


def main():
    """
    Função principal.
    """
    import sys
    
    print("=" * 60)
    print("EXTRAÇÃO DE NOMES DE REGISTOS DE ÓBITOS")
    print("=" * 60)
    
    # Verificar argumentos da linha de comandos
    if len(sys.argv) > 1:
        if sys.argv[1] == '--book':
            # Processar livro do inventário
            inventory_file = Path(__file__).parent / 'output' / 'obitos_inventario.json'
            freguesia_filter = sys.argv[2] if len(sys.argv) > 2 else None
            process_book_from_inventory(inventory_file, freguesia_filter)
            return
        elif sys.argv[1] == '--help':
            print("\nUso:")
            print("  python extract_obitos_local.py                    # Processar imagens locais")
            print("  python extract_obitos_local.py --book           # Processar todos os livros")
            print("  python extract_obitos_local.py --book 'Santa Maria'  # Processar livros filtrados")
            return
    
    # Verificar se já existem imagens na pasta
    existing_images = list(IMAGES_DIR.glob("*.jpg")) + \
                      list(IMAGES_DIR.glob("*.jpeg")) + \
                      list(IMAGES_DIR.glob("*.png"))
    
    if existing_images:
        print(f"\n📂 Encontradas {len(existing_images)} imagens existentes")
        print("A processar imagens existentes...")
        all_records = process_local_images()
    else:
        print("\n⚠️  Nenhuma imagem encontrada na pasta output/images/")
        print("\nPara extrair imagens do digitarq, executa:")
        print("  python extract_obitos_local.py --book")
        print("\nOu podes descarregar manualmente as imagens do índice")
        print("e colocá-las na pasta output/images/")
        return
    
    # 3. Guardar no Supabase
    if all_records:
        print(f"\n=== GUARDANDO {len(all_records)} REGISTOS NO SUPABASE ===")
        saved = save_to_supabase(all_records)
        print(f"\n✅ {saved} registos guardados no Supabase")
    else:
        print("\n❌ Nenhum registo extraído")
    
    # 4. Guardar resultados em JSON
    output_file = Path(__file__).parent / 'output' / 'extracted_names.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(all_records, f, ensure_ascii=False, indent=2)
    print(f"📄 Resultados guardados em: {output_file}")


if __name__ == "__main__":
    main()
