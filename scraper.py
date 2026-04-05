"""
Scraping de registos de óbitos do tombo.pt / digitarq.arquivos.pt
"""
import time
import json
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

import config


HEADERS = {
    "User-Agent": config.USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pt-PT,pt;q=0.9,en;q=0.8",
}


def get_session():
    """Cria uma sessão HTTP com headers comuns."""
    session = requests.Session()
    session.headers.update(HEADERS)
    return session


def fetch_page(session, url, retries=config.MAX_RETRIES):
    """Faz fetch de uma página com retries."""
    for attempt in range(retries):
        try:
            resp = session.get(url, timeout=config.REQUEST_TIMEOUT)
            resp.raise_for_status()
            return resp.text
        except requests.RequestException as e:
            print(f"  Erro ao carregar {url} (tentativa {attempt+1}/{retries}): {e}")
            if attempt < retries - 1:
                time.sleep(config.REQUEST_DELAY * (attempt + 1))
    return None


def extract_obitos_links_from_municipio(session):
    """
    Extrai links de registos de óbitos a partir da página do município.
    Nota: os registos de óbitos do registo civil (pós-1911) estão a nível concelhio.
    """
    print("A extrair links de óbitos da página do município...")
    html = fetch_page(session, config.TOMBO_URL)
    if not html:
        return []

    soup = BeautifulSoup(html, "lxml")
    obitos_records = []

    # Procurar secção de óbitos
    # Os links para digitarq estão nas páginas de cada freguesia
    # Primeiro vamos extrair os links das freguesias
    freguesias = []
    for link in soup.find_all("a", href=True):
        href = link["href"]
        if href.startswith("/f/clb"):
            name = link.get_text(strip=True)
            # Extrair código da freguesia
            code = href.split("/")[-1]
            freguesias.append((code, name, href))

    print(f"  Encontradas {len(freguesias)} freguesias")

    for code, name, href in freguesias:
        print(f"  A processar freguesia: {name}...")
        url = urljoin(config.TOMBO_URL, href)
        freguesia_html = fetch_page(session, url)
        if not freguesia_html:
            continue

        freguesia_soup = BeautifulSoup(freguesia_html, "lxml")

        # Procurar secção de óbitos
        obitos_section = None
        for heading in freguesia_soup.find_all(["h2", "h3", "h4"]):
            if "óbitos" in heading.get_text(strip=True).lower():
                obitos_section = heading
                break

        if not obitos_section:
            print(f"    Sem secção de óbitos encontrada")
            continue

        # Extrair links de registos após a secção de óbitos
        parent = obitos_section.parent
        links = parent.find_all("a", href=True)

        for link in links:
            href_link = link["href"]
            if "digitarq.arquivos.pt" in href_link or "fileViewer" in href_link:
                title = link.get("title", "")
                text = link.get_text(strip=True)
                # Procurar datas próximas
                date_text = ""
                for sibling in link.find_next_siblings():
                    sib_text = sibling.get_text(strip=True)
                    if sib_text and len(sib_text) < 30 and "-" in sib_text:
                        date_text = sib_text
                        break

                obitos_records.append({
                    "freguesia": name,
                    "titulo": text or title,
                    "data": date_text,
                    "url": href_link,
                })

        time.sleep(config.REQUEST_DELAY)

    return obitos_records


def extract_obitos_from_digitarq(session, document_id):
    """
    Extrai informações de um documento específico do digitarq.
    """
    url = f"{config.DIGITARQ_BASE}/documentDetails/{document_id}"
    html = fetch_page(session, url)
    if not html:
        return None

    soup = BeautifulSoup(html, "lxml")
    info = {}

    # Extrair título
    title_el = soup.find("h1") or soup.find("h2")
    if title_el:
        info["titulo"] = title_el.get_text(strip=True)

    # Extrair datas
    for dt in soup.find_all("dt"):
        label = dt.get_text(strip=True).lower()
        dd = dt.find_next_sibling("dd")
        if dd:
            value = dd.get_text(strip=True)
            if "data" in label or "date" in label:
                info["data"] = value
            elif "título" in label or "title" in label:
                info["titulo"] = value

    return info


def get_file_viewer_url(session, document_details_url):
    """
    A partir de um URL de documentDetails, extrai o URL do fileViewer.
    """
    html = fetch_page(session, document_details_url)
    if not html:
        return None

    soup = BeautifulSoup(html, "lxml")
    for link in soup.find_all("a", href=True):
        if "fileViewer" in link["href"]:
            return link["href"]
    return None


def scrape_all_obitos():
    """
    Função principal de scraping.
    Retorna lista de registos de óbitos encontrados.
    """
    session = get_session()

    # Método 1: Extrair da página principal do município
    records = extract_obitos_links_from_municipio(session)

    # Guardar resultados
    output_file = f"{config.TEXT_DIR}/obitos_links.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

    print(f"\nTotal de registos de óbitos encontrados: {len(records)}")
    print(f"Resultados guardados em: {output_file}")

    return records


if __name__ == "__main__":
    scrape_all_obitos()
