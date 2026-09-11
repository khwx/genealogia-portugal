# Pipeline de Extração de Registos de Óbitos - Celorico da Beira

## Visão Geral

Pipeline completo para extrair registos de óbitos paroquiais do arquivo Distrital da Guarda
(Digarq) para uma base de dados SQLite.

```
Digitarq API → TIFF Download → JPEG Convert → Gemini OCR → SQLite
```

## Arquitetura

### Componentes

| Componente | Tecnologia | Função |
|-----------|-----------|--------|
| API Digitarq | REST API | Listar páginas e metadados |
| Disseminação | `/rdigital/dissemination` | Download de imagens TIFF originais |
| OCR | Gemini 2.5 Flash | Extração de texto das imagens |
| Base de dados | SQLite | Armazenamento dos registos |

### Fluxo de Dados

```
1. Inventário → Lista de livros com doc_ids
2. API Digitarq → Lista de páginas por livro
3. Disseminação → Download TIFF (qualidade original)
4. PIL/Pillow → Conversão TIFF → JPEG
5. Gemini Vision → OCR → JSON array de registos
6. SQLite → inserção com normalização de datas
```

## Descoberta Técnica

### O Problema

O website Digitarq usa **WebGL canvas** para renderizar imagens de documentos.
O Chrome headless no Docker **não consegue renderizar WebGL** porque:
- Falta bibliotecas GPU (`libnspr4.so`, etc.)
- SwiftShader não suporta todos os padrões WebGL
- Não temos permissões root para instalar pacotes

### A Solução

O endpoint de **disseminação** serve imagens TIFF diretamente:

```
GET https://digitarq.arquivos.pt/rdigital/dissemination?fileId={pageId}&download=true
```

- Retorna TIFF com qualidade original (2637×2013px)
- Não requer autenticação
- Não precisa de WebGL/rendering
- Funciona com qualquer doc_id

### Como Descobrimos

1. Analisamos o JavaScript bundle do fileViewer (`_app-46b1159528701f12.js`)
2. Encontrámos a função `handleDownload` que usa `rdigitalDissemination`
3. O URL padrão é: `/rdigital/dissemination?fileId={id}&download=true`
4. O `fileId` é o `id` da página retornado pela API `/api/rdigital/{docId}`

## Scripts

### 1. `capture_dissemination.py`

Captura imagens TIFF do Digitarq via disseminação.

```bash
# Capturar últimas 3 páginas de todos os livros
python capture_dissemination.py

# Capturar um livro específico
python capture_dissemination.py --doc-id 1d7ea53080f5401aa4c0a6d035244e71

# Capturar últimas 5 páginas
python capture_dissemination.py --last-pages 5

# Capturar páginas específicas
python capture_dissemination.py --pages 88-93

# Capturar todas as páginas
python capture_dissemination.py --all-pages
```

### 2. `ocr_gemini.py`

Processa imagens JPEG com Gemini Vision e extrai registos.

```bash
# Processar todas as imagens não processadas
python ocr_gemini.py

# Processar uma imagem específica
python ocr_gemini.py --file output/images/jpeg/image.jpeg

# Reprocessar todas as imagens
python ocr_gemini.py --reprocess
```

### 3. Scripts Anteriores (referência)

| Script | Função | Estado |
|--------|--------|--------|
| `capture_screenshots.py` | Captura screenshots via Docker Chrome | ⚠️ WebGL não renderiza |
| `capture_docker.py` | Versão anterior com chrome-ocr | ❌ Imagem Docker não existe |
| `pipeline.py` | Pipeline completo (deprecated) | ⚠️ Usa gemini-1.5-flash |
| `extract_obitos_local.py` | OCR com Google Vision | ❌ Requer credenciais GCP |

## Configuração

### API Keys Gemini

As chaves estão em `.env` como `GEMINI_KEYS` (separadas por vírgula).
Rate limit: 20 requests/min por chave (tier gratuito).
O script rota automaticamente entre 6 chaves.

### Inventário

Ficheiro: `output/inventario_completo_clb.json`
Contém 2343 livros de 25 freguesias de Celorico da Beira.

### Base de Dados

Ficheiro: `output/obitos.db`
Tabela: `obitos` com campos:
- `nome`, `data_obito`, `ano`, `numero_registo`
- `freguesia`, `concelho` (default: Celorico da Beira), `distrito` (default: Guarda)
- `livro_id`, `pagina`, `imagem_url`
- `status` (pendente/revisado/confirmado)
- `fonte` (default: Gemini Vision)
- `data_extracao`

## Livros Processados (Celorico Santa Maria)

| Livro | Doc ID | Período | Páginas |
|-------|--------|---------|---------|
| PCLB19/001/B1 | 1f55db5fa2c54f1a854aa454faaac8e1 | 1706-1718 | 85 |
| PCLB19/001/B2 | 1d7ea53080f5401aa4c0a6d035244e71 | 1718-1728 | 93 |
| PCLB19/001/B3 | b90c7862e3f149ae9c37a03724884eba | 1728-1744 | 149 |
| PCLB19/001/B4 | 4c38df691d7e4d50b62ec7fe196af3da | 1744-1775 | 301 |
| PCLB19/001/B5 | e093f8008c4b4306ae248ff95204abea | 1775-1815 | 307 |

## Resultados Atuais

- **7 registos** extraídos e inseridos na BD (status: pendente)
- **15 imagens TIFF** baixadas (3 últimas páginas × 5 livros)
- Ficheiro de resultados: `output/ocr_results.json`

## Limitações

1. **Rate limiting Gemini**: 20 requests/min por chave (tier gratuito)
2. **Qualidade OCR**: Depende da qualidade da escrita manuscrita
3. **Datas antigas**: Formato variável (séc. XVII-XVIII), normalização parcial
4. **Escrita ilegível**: Alguns registos podem ter campos incompletos

## Próximos Passos

1. Processar todas as últimas páginas dos 5 livros (índices de óbitos)
2. Expandir para as 25 freguesias de Celorico da Beira
3. Processar TODAS as páginas (não só as últimas)
4. Implementar revisão manual via `review_server.py`
5. Exportar para FamilySearch/GEDCOM
