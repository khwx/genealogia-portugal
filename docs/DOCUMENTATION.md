# Documentação do Projeto - Árvore Genealógica de Portugal

## Como as imagens foram capturadas

### Fonte dos dados
Todas as imagens provêm do **Digitarq** (Arquivo Digital da Direção Geral do Livro, dos Arquivos e das Bibliotecas):
- URL base: https://digitarq.arquivos.pt
- Portal de acesso: https://tombo.pt

### Processo de extração

#### 1. Inventário de livros (Tombo.pt)
O script `extract_all_records.py` extrai a lista completa de livros disponíveis:
```bash
python extract_all_records.py --concelho clb
```
- Acede ao Tombo.pt/m/clb (Celorico da Beira)
- Extrai todas as freguesias (27 em Celorico)
- Para cada freguesia, extrai os três tipos de registos:
  - **BIRT** - Registos de nascimentos
  - **MARR** - Registos de casamentos
  - **DEAT** - Registos de óbitos

Resultado: `output/obitos_inventario.json` (2343 registos)

#### 2. Download de imagens (Digitarq API)
O script `pipeline_obitos.py` faz o download das imagens TIFF:
```python
# API Digitarq para listar ficheiros
API_FILES = "https://digitarq.arquivos.pt/api/rdigital/{doc_id}?max=200"
# Download da imagem
IMAGE_URL = "https://digitarq.arquivos.pt/rdigital/dissemination?fileId={file_id}"
```

Processo:
1. Lê o inventário (`obitos_inventario.json`)
2. Para cada livro, consulta a API do Digitarq
3. Descarrega as imagens TIFF para `output/full_images/`
4. Nome dos ficheiros: `{doc_id}.tiff` ou `{file_id}.tiff`

#### 3. Processamento OCR
As imagens são processadas com:
- **Tesseract** (via Docker) - para texto impresso
- **Gemini API** (`htr_cloud.py`) - para manuscritos
- **CHURRO-3B** (Colab notebooks) - modelo open-source para HTR

#### 4. Extração de entidades
O script `extract_obitos_local.py` extrai:
- Nomes de pessoas
- Datas (nascimento, casamento, óbito)
- Relações familiares (pai, mãe, cônjuge)
- Freguesia e concelho

## Estrutura da Base de Dados

### Tabelas principais

#### `registos` (nova - suporta todos os tipos)
- `id` - Chave primária
- `tipo` - 'BIRT', 'MARR', 'DEAT'
- `nome` - Nome da pessoa
- `data_evento` - Data do nascimento/casamento/óbito
- `freguesia` - Freguesia
- `ano` - Ano (para índice)
- `texto_original` - Texto OCR completo
- `imagem_url` - URL da imagem no Digitarq
- `livro_titulo` - Título do livro
- `livro_url` - URL do livro no Digitarq

#### `livros`
- `tipo` - 'BIRT', 'MARR', 'DEAT'
- `freguesia_id` - Referência à tabela freguesias
- `titulo` - PT/ADGRD/PRQ/...
- `data_inicio`, `data_fim` - Período do livro
- `url` - URL no Digitarq

#### `freguesias`
- `codigo` - Ex: clb01, clb02
- `nome` - Nome da freguesia

## Scripts principais

| Script | Função |
|--------|---------|
| `extract_all_records.py` | Extrai inventário completo do Tombo.pt |
| `pipeline_obitos.py` | Download de imagens e pipeline OCR |
| `htr_cloud.py` | Processamento OCR com Gemini API |
| `extract_obitos_local.py` | Extração de entidades dos registos |
| `database.py` | Gestão da base de dados SQLite |
| `web_app.py` | Interface web Flask |
| `gedcom_export.py` | Exportação para formato GEDCOM |

## Notebooks Colab

- `HTR_Colab.ipynb` - Processamento com Gemini API
- `HTR_Colab_CHURRO.ipynb` - Processamento com CHURRO-3B
- `HTR_Colab_LM.ipynb` - Processamento com modelos open-source

## Cobertura atual (Celorico da Beira)

| Tipo | Livros | Imagens descarregadas | OCR processado |
|------|--------|---------------------|------------------|
| Nascimentos | 236 | ❌ Pendente | ❌ Pendente |
| Casamentos | 1030 | ❌ Pendente | ❌ Pendente |
| Óbitos | 1077 | ✅ 4185 ficheiros (3.8GB) | ✅ Processado |

## Próximos passos para completar a árvore

1. ✅ Inventário completo (2343 livros)
2. ✅ Base de dados criada (`output/genealogia.db`)
3. ❌ Descarregar imagens de nascimentos e casamentos
4. ❌ Processar OCR para todos os tipos
5. ❌ Extrair relações familiares (pai, mãe, cônjuge)
6. ❌ Criar ligações na BD (foreign keys)
7. ❌ Exportar árvore GEDCOM funcional

## Reproduzir o processo para outro concelho

```bash
# 1. Extrair inventário
python extract_all_records.py --concelho cbr  # Coimbra
python extract_all_records.py --concelho ctb  # Castelo Branco

# 2. Atualizar base de dados
python database.py

# 3. Download de imagens (editar pipeline_obitos.py para ler novo inventário)
python pipeline_obitos.py

# 4. Processar OCR
python htr_cloud.py
```

## Notas técnicas

- **Formato das imagens**: TIFF (original do arquivo)
- **OCR**: Tesseract (Português) + Gemini API (manuscritos)
- **Base de dados**: SQLite (`output/genealogia.db`)
- **Backup de imagens**: Google Drive (3.8GB excedem limite GitHub LFS gratuito)
- **Licença**: MIT (dados de domínio público > 100 anos)
