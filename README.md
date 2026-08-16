# Árvore Genealógica de Portugal

## Descrição

**Plataforma colaborativa** para criação de árvores genealógicas a partir de registos paroquiais e civis de Portugal. Cobertura de **todos os concelhos** do território continental e ilhas.

### Fontes de dados
- **Tombo.pt / Digitarq** — Imagens digitalizadas de registos paroquiais
- **FamilySearch** — Índices já transcritos
- **Transkribus / HTR** — Transcrição de manuscritos antigos (CHURRO-3B, TrOCR, Gemini)
- **Contribuições da comunidade**

### Tipos de registos
- **Nascimentos / Batismos** (236 livros em Celorico da Beira)
- **Casamentos** (1030 livros em Celorico da Beira)
- **Óbitos** (1077 livros em Celorico da Beira)

### Período
- Registos paroquiais: **1654 — 1911**
- Registo civil: **1911 — presente**

### Cobertura atual
- **Celorico da Beira**: 2343 livros inventariados (nascimentos, casamentos, óbitos)
- Imagens descarregadas: 4185 ficheiros (3.8GB) para óbitos
- OCR processado: óbitos (Gemini API / Tesseract)

---

## Funcionalidades

1. **Scraping automático** — Extrai inventários do tombo.pt
2. **FamilySearch API** — Acede a índices já transcritos
3. **Transkribus HTR** — Transcreve manuscritos antigos usando IA
4. **Base de dados SQLite** — Armazena registos com índices para pesquisa
5. **Interface web Flask** — Pesquisa por nome, concelho, freguesia, data
6. **Exportação** — JSON, CSV, Excel
7. **Contribuições** — Qualquer pessoa pode ajudar a aumentar o projeto

---

## Pré-requisitos

- Python 3.8+
- Git
- Conta gratuita no [FamilySearch](https://www.familysearch.org/) (opcional)
- Conta gratuita no [Transkribus](https://transkribus.eu/) (opcional)

---

## Instalação

```bash
# Clone o repositório
git clone https://github.com/khwx/genealogia-portugal.git
cd genealogia-portugal

# Instale as dependências
pip install -r requirements.txt

# Configure as variáveis de ambiente (opcional, para APIs externas)
cp .env.example .env
# Edite o ficheiro .env com as suas credenciais
```

---

## Uso

### 1. Extrair inventário completo (nascimentos, casamentos, óbitos)
```bash
python extract_all_records.py --concelho clb    # Celorico da Beira
python extract_all_records.py --concelho cbr    # Coimbra
python extract_all_records.py --concelho ctb    # Castelo Branco
# Filtrar por tipo: --tipo BIRT (nascimentos) | MARR (casamentos) | DEAT (óbitos)
```

### 2. Inicializar base de dados
```bash
python database.py
# Cria output/genealogia.db com tabelas para todos os tipos de registos
```

### 3. Descarregar imagens dos livros
```bash
python pipeline_obitos.py --url <url_digitarq>     # Processa uma imagem específica
python get_images.py                                # Descarrega imagens de índices
python pipeline_obitos.py                           # Pipeline completo para óbitos
```

### 4. Processar OCR e extrair entidades
```bash
python htr_cloud.py          # Usa Gemini API para OCR
python extract_obitos_local.py  # Extrai nomes e relações familiares
```

### 5. Iniciar interface web
```bash
python web_app.py
```
Aceda a: http://localhost:5000

### 6. Pesquisar registos
```bash
python -c "
from database import search_by_name, get_all_registos
# Pesquisar por nome
results = search_by_name('Maria Silva')
# Filtrar por tipo: 'BIRT', 'MARR', 'DEAT'
obitos = get_all_registos(tipo='DEAT')
nascimentos = get_all_registos(tipo='BIRT')
casamentos = get_all_registos(tipo='MARR')
"
```

### 7. Exportar árvore genealógica
```bash
python gedcom_export.py   # Exporta para formato GEDCOM
python -c "
from database import get_all_registos
# Criar ligações familiares (pai, mãe, cônjuge)
"
```

---

## Estrutura da Base de Dados

### Tabelas principais

**`pessoas`**
- `id` — Chave primária
- `nome` — Nome completo
- `data_nascimento` — Data de nascimento
- `data_obito` — Data de óbito
- `data_casamento` — Data de casamento
- `concelho` — Concelho
- `freguesia` — Freguesia
- `pai_id` — ID do pai
- `mae_id` — ID da mãe
- `fonte` — Origem do registo
- `texto_original` — Texto original extraído
- `confidence_score` — Confiança da transcrição (0-1)

**`freguesias`** — Lista de freguesias por concelho
**`concelhos`** — Lista de concelhos por distrito
**`livros`** — Livros de registos
**`external_sources`** — Dados das fontes externas (JSON)

---

## Cobertura

### Concelhos já processados
- Celorico da Beira (1.077 livros de óbitos)

### Próximos concelhos
- Guarda
- Trancoso
- Fornos de Algodres
- ...

---

## APIs Externas

### FamilySearch
- Índices já transcritos de registos paroquiais portugueses
- Gratuito com conta
- Limite: ~1000 consultas/dia
- Documentação: https://developers.familysearch.org/

### Transkribus
- HTR (Handwritten Text Recognition) para manuscritos históricos
- 500 páginas gratuitas/mês
- Modelos para português histórico
- Documentação: https://transkribus.eu/TrpServer/rest/guides/api/

---

## Aviso Legal

Todos os dados são de **domínio público**:
- Registos paroquiais (até 1911) — mais de 100 anos
- Registo civil (até 1950) — mais de 70 anos

Este projeto não viola nenhuma restrição de proteção de dados (RGPD).

---

## Configuração e Segurança

**Nenhum segredo está no repositório.** Todas as chaves de API (Gemini, Supabase, Transkribus, FamilySearch, etc.) vêm de um ficheiro `.env` **local**, que está no `.gitignore` e nunca é comitado. O repo traz apenas `.env.example` com placeholders.

### Configurar o ambiente
```bash
cp .env.example .env
# Edita .env e preenche (ex.):
#   SUPABASE_URL=https://teu-projeto.supabase.co
#   SUPABASE_ANON_KEY=sb_publishable_...
#   GEMINI_KEYS=AIzaSy...,AIzaSy...
```

### Supabase
A app usa as tabelas `pessoas` e `livros`. Para o endpoint `POST /api/validar` gravar, a tabela `pessoas` precisa das colunas `qualidade` (numeric) e `validado` (boolean) e de uma política de UPDATE anon (correr o SQL em `.env.example`/Supabase SQL Editor). As leituras (`/api/pessoas`, `/api/livros`, `/api/mapa`) funcionam com a chave anon.

### Clonar noutra máquina e pôr a funcionar
```bash
git clone https://github.com/khwx/genealogia-portugal.git
cd genealogia-portugal
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # preenche os teus valores (nunca comites o .env)
# Coloca as tuas imagens em INPUT_DIR e corre o pipeline
```

### Pipeline de óbitos (resumo)
1. `python htr_cloud_v2.py` — transcreve as imagens `.tiff` de `output/full_images/` para `output/htr_text/*.json` (via Gemini).
2. `python sync_htr_supabase.py` — envia as transcrições para a tabela `pessoas` no Supabase.
3. `python api/index.py` — API Flask (rotas `/api/pessoas`, `/api/livros`, `/api/mapa`, `POST /api/validar`).

---

## Contribuindo

Contribuições são bem-vindas! Qualquer pessoa pode ajudar.

### Como contribuir
1. Faça o fork do projeto
2. Crie uma branch (`git checkout -b feature/nova-feature`)
3. Commit suas mudanças (`git commit -m 'Adiciona nova feature'`)
4. Push para a branch (`git push origin feature/nova-feature`)
5. Abra um Pull Request

### Tipos de contribuição
- **Scraping** — Adicionar novos concelhos
- **Transcrição** — Melhorar a precisão do OCR/HTR
- **Dados** — Contribuir com registos já transcritos
- **Interface** — Melhorar a interface web
- **Documentação** — Melhorar a documentação

---

## Licença

Licença MIT — ver ficheiro LICENSE para detalhes.
