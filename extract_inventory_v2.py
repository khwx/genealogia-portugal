"""
Script para extrair o inventário de registos de óbitos de qualquer concelho.
Uso:
    python extract_inventory_v2.py --concelho clb    # Celorico da Beira
    python extract_inventory_v2.py --concelho cbr    # Coimbra
    python extract_inventory_v2.py --concelho ctb    # Castelo Branco
"""
import requests
from bs4 import BeautifulSoup
import pandas as pd
import json
import time
import os
import argparse

BASE_URL = "https://tombo.pt"
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}

os.makedirs(OUTPUT_DIR, exist_ok=True)


def get_session():
    session = requests.Session()
    session.headers.update(HEADERS)
    return session


def fetch_page(session, url, retries=3):
    for attempt in range(retries):
        try:
            resp = session.get(url, timeout=30)
            resp.raise_for_status()
            return resp.text
        except Exception as e:
            print(f"  Erro (tentativa {attempt+1}/3): {e}")
            if attempt < retries - 1:
                time.sleep(2 * (attempt + 1))
    return None


def extract_freguesias(session, municipio_code):
    """Extrai lista de freguesias da página do município."""
    url = f"{BASE_URL}/m/{municipio_code}"
    print(f"A extrair lista de freguesias de {url}...")
    html = fetch_page(session, url)
    if not html:
        return []

    soup = BeautifulSoup(html, "lxml")
    freguesias = []
    seen = set()

    for link in soup.find_all("a", href=True):
        href = link["href"]
        if href.startswith(f"/f/{municipio_code}"):
            code = href.split("/")[-1]
            if code in seen:
                continue
            seen.add(code)
            name = link.get_text(strip=True)
            freguesias.append({"codigo": code, "nome": name, "url": href})

    print(f"  Encontradas {len(freguesias)} freguesias")
    return freguesias


def extract_obitos_from_freguesia(session, freguesia, municipio_code):
    """Extrai registos de óbitos de uma freguesia."""
    code = freguesia["codigo"]
    name = freguesia["nome"]
    url = f"{BASE_URL}{freguesia['url']}"

    print(f"  A processar: {name}...")
    html = fetch_page(session, url)
    if not html:
        return []

    soup = BeautifulSoup(html, "lxml")
    registros = []

    for table in soup.find_all("table"):
        caption = table.find("caption")
        if not caption:
            continue
        caption_text = caption.get_text(strip=True).lower()
        if "óbitos" not in caption_text and "obitos" not in caption_text:
            continue

        h3 = caption.find("h3")
        tipo = h3.get_text(strip=True) if h3 else caption_text

        for row in table.find_all("tr"):
            cells = row.find_all(["td", "th"])
            if len(cells) < 2:
                continue

            link_el = cells[0].find("a", href=True)
            if not link_el:
                continue

            href = link_el["href"]
            titulo = link_el.get("title", link_el.get_text(strip=True))
            data = cells[1].get_text(strip=True) if len(cells) > 1 else ""

            info = ""
            if len(cells) > 2:
                info_link = cells[2].find("a", href=True)
                if info_link:
                    info = info_link.get("href", "")

            registros.append({
                "freguesia": name,
                "freguesia_codigo": code,
                "tipo": tipo,
                "titulo": titulo,
                "datas": data,
                "url_viewer": href if href.startswith("http") else f"{BASE_URL}{href}",
                "url_info": info if info.startswith("http") else f"https://digitarq.arquivos.pt{info}" if info else "",
                "concelho_codigo": municipio_code,
            })

        break

    # Procurar duplicados
    for table in soup.find_all("table"):
        caption = table.find("caption")
        if not caption:
            continue
        caption_text = caption.get_text(strip=True).lower()
        if "duplicados" in caption_text and ("óbitos" in caption_text or "obitos" in caption_text):
            h3 = caption.find("h3")
            tipo = h3.get_text(strip=True) if h3 else caption_text

            for row in table.find_all("tr"):
                cells = row.find_all(["td", "th"])
                if len(cells) < 2:
                    continue
                link_el = cells[0].find("a", href=True)
                if not link_el:
                    continue
                href = link_el["href"]
                titulo = link_el.get("title", link_el.get_text(strip=True))
                data = cells[1].get_text(strip=True) if len(cells) > 1 else ""
                info = ""
                if len(cells) > 2:
                    info_link = cells[2].find("a", href=True)
                    if info_link:
                        info = info_link.get("href", "")

                registros.append({
                    "freguesia": name,
                    "freguesia_codigo": code,
                    "tipo": tipo,
                    "titulo": titulo,
                    "datas": data,
                    "url_viewer": href if href.startswith("http") else f"{BASE_URL}{href}",
                    "url_info": info if info.startswith("http") else f"https://digitarq.arquivos.pt{info}" if info else "",
                    "concelho_codigo": municipio_code,
                })

    print(f"    Encontrados {len(registros)} registos")
    return registros


def scrape_all_obitos(municipio_code):
    """Função principal de scraping."""
    print("=" * 60)
    print(f"Extração de Registos de Óbitos - Concelho: {municipio_code}")
    print("=" * 60)

    session = get_session()

    freguesias = extract_freguesias(session, municipio_code)
    if not freguesias:
        print("Erro ao extrair freguesias")
        return []

    all_obitos = []
    for freguesia in freguesias:
        obitos = extract_obitos_from_freguesia(session, freguesia, municipio_code)
        all_obitos.extend(obitos)
        time.sleep(1)

    print(f"\n{'=' * 60}")
    print(f"Total de registos encontrados: {len(all_obitos)}")
    print(f"{'=' * 60}")

    # Guardar com sufixo do concelho
    json_file = os.path.join(OUTPUT_DIR, f"obitos_inventario_{municipio_code}.json")
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(all_obitos, f, ensure_ascii=False, indent=2)
    print(f"  JSON guardado: {json_file}")

    if all_obitos:
        df = pd.DataFrame(all_obitos)
        excel_file = os.path.join(OUTPUT_DIR, f"obitos_inventario_{municipio_code}.xlsx")
        df.to_excel(excel_file, index=False, engine="openpyxl")
        print(f"  Excel guardado: {excel_file}")

        csv_file = os.path.join(OUTPUT_DIR, f"obitos_inventario_{municipio_code}.csv")
        df.to_csv(csv_file, index=False, encoding="utf-8")
        print(f"  CSV guardado: {csv_file}")

        print(f"\nResumo por freguesia:")
        summary = df.groupby("freguesia").size().sort_values(ascending=False)
        for freg, count in summary.items():
            print(f"  {freg}: {count}")
    else:
        print("\nNenhum registo encontrado.")

    return all_obitos


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Extrair inventário de óbitos de qualquer concelho')
    parser.add_argument('--concelho', required=True, help='Código do concelho (ex: clb, cbr, ctb)')
    args = parser.parse_args()

    scrape_all_obitos(args.concelho)
