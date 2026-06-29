# Célula 1: Instalar dependências
!pip install -q requests pillow

# Célula 2: Preparar o ambiente
import requests
import os
import json
from pathlib import Path

os.makedirs('full_images', exist_ok=True)
print('Ambiente preparado!')

# Célula 3: Função para descarregar imagens do Digitarq (sem API key)
def download_image_from_digitarq(file_id, output_dir='full_images'):
    """Descarrega uma imagem do Digitarq usando o file_id."""
    url = f"https://digitarq.arquivos.pt/rdigital/dissemination?fileId={file_id}"
    try:
        response = requests.get(url, timeout=60, stream=True)
        response.raise_for_status()
        
        output_path = Path(output_dir) / f"{file_id}.tiff"
        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        return True, output_path
    except Exception as e:
        return False, str(e)

print('Função de download criada!')

# Célula 4: Exemplo - descarregar uma imagem específica
# Podes obter o file_id a partir do inventário ou da URL do Digitarq
# Exemplo: URL https://digitarq.arquivos.pt/fileViewer/734a3244db0d49c2886cb74df6c6e5c7
# O file_id é: 734a3244db0d49c2886cb74df6c6e5c7

file_id_exemplo = "734a3244db0d49c2886cb74df6c6e5c7"  # Substitui por um file_id real
sucesso, resultado = download_image_from_digitarq(file_id_exemplo)

if sucesso:
    print(f'Imagem descarregada: {resultado}')
    print(f'Tamanho: {resultado.stat().st_size} bytes')
else:
    print(f'Erro: {resultado}')

# Célula 5: Descarregar todas as imagens de um livro (usando a API do Digitarq)
def get_file_list_from_digitarq(doc_id):
    """Obtém a lista de ficheiros de um documento no Digitarq."""
    url = f"https://digitarq.arquivos.pt/api/rdigital/{doc_id}?max=200"
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        data = response.json()
        return data.get('results', [])
    except Exception as e:
        print(f'Erro ao obter lista: {e}')
        return []

# Exemplo: doc_id do inventário (campo 'url_viewer' contém o doc_id)
# doc_id = "734a3244db0d49c2886cb74df6c6e5c7"  # Parte após /fileViewer/

print('Função para listar ficheiros criada!')

# Célula 6: Processo completo para um livro
def process_book_in_colab(doc_id, output_dir='full_images'):
    """Processa um livro completo no Colab."""
    print(f'A processar livro: {doc_id}')
    
    # Obter lista de ficheiros
    files = get_file_list_from_digitarq(doc_id)
    print(f'Encontrados {len(files)} ficheiros')
    
    downloaded = 0
    for file_info in files:
        file_id = file_info.get('id')
        if not file_id:
            continue
        
        sucesso, _ = download_image_from_digitarq(file_id, output_dir)
        if sucesso:
            downloaded += 1
        
        if downloaded % 10 == 0:
            print(f'  {downloaded}/{len(files)} descarregados...')
    
    print(f'✅ {downloaded} imagens descarregadas para {output_dir}')
    return downloaded

# Célula 7: Exemplo de uso (substitui pelo doc_id real do inventário)
# Para usar: carrega primeiro o inventário (célula 8)

# Célula 8: Carregar inventário e processar em lote
import json

# Opção A: Fazer upload do inventário do servidor local
from google.colab import files
print('Faz upload do obitos_inventario.json...')
# uploaded = files.upload()  # Descomenta para fazer upload

# Opção B: Descarregar inventário diretamente do GitHub
!wget -q https://raw.githubusercontent.com/khwx/genealogia-portugal/main/output/obitos_inventario.json -O obitos_inventario.json
print('Inventário descarregado do GitHub!')

# Célula 9: Processar todos os livros do inventário (CUIDADO: demora horas!)
def process_all_books_from_inventory(inventory_file, max_books=5):
    """Processa os primeiros N livros do inventário."""
    with open(inventory_file) as f:
        inventory = json.load(f)
    
    print(f'Total de livros no inventário: {len(inventory)}')
    
    # Filtrar por tipo (opcional)
    # inventory = [r for r in inventory if r.get('tipo_cod') == 'DEAT']  # Só óbitos
    
    for i, book in enumerate(inventory[:max_books]):
        doc_id = book.get('url_viewer', '').split('/')[-1].split('?')[0]
        if not doc_id:
            continue
        
        print(f'\n{i+1}/{max_books} - {book.get("titulo", "N/A")}')
        try:
            process_book_in_colab(doc_id)
        except Exception as e:
            print(f'  Erro: {e}')
        
        # Pausa para não sobrecarregar o servidor
        import time
        time.sleep(2)

# Descomenta para executar (cuidado com o tempo e espaço no Colab!)
# process_all_books_from_inventory('obitos_inventario.json', max_books=2)

print('Código preparado! Descomenta as últimas linhas para executar.')

# Célula 10: Alternativa - Montar Google Drive (mais rápido se já tiveres as imagens no Drive)
from google.colab import drive
print('Para montar o Google Drive:')
print('drive.mount("/content/drive")')
print('Depois copia as imagens:')
print('!cp -r /content/drive/MyDrive/obitos_images/* full_images/')
