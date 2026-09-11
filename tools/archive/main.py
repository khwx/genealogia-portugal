"""
Script principal para extração de registos de óbitos.
Orquestra o scraping, OCR, parsing e exportação.
"""
import argparse
import json
import os
import sys
import time

import config
from scraper import scrape_all_obitos, get_session, fetch_page
from ocr_processor import process_all_images, extract_text_from_image
from parser import parse_text_file, parse_all_text_files
from database import init_database, insert_obitos_batch, get_all_obitos, get_statistics, search_by_name


def ensure_directories():
    """Cria diretórios necessários."""
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    os.makedirs(config.IMAGES_DIR, exist_ok=True)
    os.makedirs(config.TEXT_DIR, exist_ok=True)


def cmd_scrape(args):
    """Comando de scraping."""
    print("=" * 60)
    print("SCRAPING - Extração de links de registos de óbitos")
    print("=" * 60)
    records = scrape_all_obitos()
    print(f"\nEncontrados {len(records)} registos de óbitos.")
    return records


def cmd_download(args):
    """Comando de download de imagens."""
    print("=" * 60)
    print("DOWNLOAD - Descarregar imagens dos registos")
    print("=" * 60)

    # Carregar links extraídos
    links_file = os.path.join(config.TEXT_DIR, "obitos_links.json")
    if not os.path.exists(links_file):
        print("Ficheiro de links não encontrado. Execute o scraping primeiro.")
        return []

    with open(links_file, "r", encoding="utf-8") as f:
        links = json.load(f)

    print(f"A descarregar {len(links)} imagens...")
    session = get_session()
    downloaded = 0

    for i, link in enumerate(links):
        url = link.get("url", "")
        if not url:
            continue

        print(f"  [{i+1}/{len(links)}] {link.get('titulo', 'Sem título')}")

        # O URL pode ser do tipo documentDetails ou fileViewer
        # Precisamos extrair o URL real da imagem
        try:
            html = fetch_page(session, url)
            if html:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(html, "lxml")

                # Procurar links para imagens ou fileViewer
                for a in soup.find_all("a", href=True):
                    href = str(a.get("href", ""))
                    if "fileViewer" in href or ".jpg" in href or ".png" in href:
                        img_url = href
                        if not img_url.startswith("http"):
                            img_url = f"https://digitarq.arquivos.pt{img_url}"

                        # Download da imagem
                        img_resp = session.get(img_url, timeout=config.REQUEST_TIMEOUT)
                        if img_resp.status_code == 200:
                            filename = f"registo_{i+1:04d}.jpg"
                            filepath = os.path.join(config.IMAGES_DIR, filename)
                            with open(filepath, "wb") as img_file:
                                img_file.write(img_resp.content)
                            downloaded += 1
                            print(f"    Guardado: {filename}")
                        break

                time.sleep(config.REQUEST_DELAY)
        except Exception as e:
            print(f"    Erro: {e}")

    print(f"\nTotal de imagens descarregadas: {downloaded}")
    return downloaded


def cmd_ocr(args):
    """Comando de OCR."""
    print("=" * 60)
    print("OCR - Processamento de imagens")
    print("=" * 60)
    results = process_all_images()
    print(f"\nTotal de imagens processadas: {len(results)}")
    return results


def cmd_parse(args):
    """Comando de parsing."""
    print("=" * 60)
    print("PARSING - Extração de nomes, datas e números de registo")
    print("=" * 60)
    records = parse_all_text_files()
    print(f"\nTotal de registos extraídos: {len(records)}")
    return records


def cmd_export(args):
    """Comando de exportação."""
    print("=" * 60)
    print("EXPORTAÇÃO - Guardar resultados")
    print("=" * 60)

    # Inicializar base de dados
    init_database()

    # Carregar registos parseados
    all_records = get_all_obitos()

    if not all_records:
        print("Sem registos na base de dados. Execute o parsing primeiro.")
        return

    # Exportar para Excel
    try:
        import pandas as pd
        df = pd.DataFrame(all_records)

        # Guardar Excel
        df.to_excel(config.EXCEL_FILE, index=False, engine="openpyxl")
        print(f"  Excel guardado: {config.EXCEL_FILE}")

        # Guardar CSV
        df.to_csv(config.CSV_FILE, index=False, encoding="utf-8")
        print(f"  CSV guardado: {config.CSV_FILE}")
    except ImportError:
        print("  pandas/openpyxl não instalado. A exportar apenas para CSV manualmente.")
        # Fallback para CSV simples
        with open(config.CSV_FILE, "w", encoding="utf-8") as f:
            if all_records:
                headers = list(all_records[0].keys())
                f.write(",".join(headers) + "\n")
                for record in all_records:
                    values = [str(record.get(h, "")).replace(",", ";") for h in headers]
                    f.write(",".join(values) + "\n")
        print(f"  CSV guardado: {config.CSV_FILE}")

    # Mostrar estatísticas
    stats = get_statistics()
    print(f"\nEstatísticas:")
    print(f"  Total de registos: {stats.get('total', 0)}")

    if stats.get("por_ano"):
        print(f"  Por ano:")
        for item in stats["por_ano"][:10]:
            print(f"    {item['ano']}: {item['count']}")

    if stats.get("por_freguesia"):
        print(f"  Por freguesia:")
        for item in stats["por_freguesia"][:10]:
            print(f"    {item['freguesia']}: {item['count']}")


def cmd_search(args):
    """Comando de pesquisa."""
    print("=" * 60)
    print(f"PESQUISA - Procurar por '{args.query}'")
    print("=" * 60)

    results = search_by_name(args.query)
    print(f"\nEncontrados {len(results)} resultados:")
    for r in results[:20]:
        print(f"  Nome: {r.get('nome')}, Data: {r.get('data_obito')}, Freguesia: {r.get('freguesia')}")

    if len(results) > 20:
        print(f"  ... e mais {len(results) - 20} resultados")


def cmd_all(args):
    """Executa todo o pipeline."""
    print("=" * 60)
    print("PIPELINE COMPLETO - Extração de Registos de Óbitos")
    print("=" * 60)

    # 1. Scraping
    cmd_scrape(args)

    # 2. Download
    cmd_download(args)

    # 3. OCR
    cmd_ocr(args)

    # 4. Parsing
    records = cmd_parse(args)

    # 5. Guardar na base de dados
    if records:
        init_database()
        insert_obitos_batch(records)

    # 6. Exportar
    cmd_export(args)


def main():
    parser = argparse.ArgumentParser(
        description="Extração de registos de óbitos de Celorico da Beira"
    )
    parser.add_argument("--scrape", action="store_true", help="Extrair links de óbitos")
    parser.add_argument("--download", action="store_true", help="Descarregar imagens")
    parser.add_argument("--ocr", action="store_true", help="Processar OCR nas imagens")
    parser.add_argument("--parse", action="store_true", help="Parse de textos extraídos")
    parser.add_argument("--export", action="store_true", help="Exportar para Excel/CSV")
    parser.add_argument("--all", action="store_true", help="Executar todo o pipeline")
    parser.add_argument("--search", type=str, help="Pesquisar por nome")
    parser.add_argument("--query", type=str, help="Query de pesquisa (alias para --search)")

    args = parser.parse_args()

    # Garantir que os diretórios existem
    ensure_directories()

    if args.all:
        cmd_all(args)
    elif args.scrape:
        cmd_scrape(args)
    elif args.download:
        cmd_download(args)
    elif args.ocr:
        cmd_ocr(args)
    elif args.parse:
        cmd_parse(args)
    elif args.export:
        cmd_export(args)
    elif args.search or args.query:
        cmd_search(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
