# Árvore Genealógica de Portugal

## Descrição

**Plataforma colaborativa** para criação de árvores genealógicas a partir de registos paroquiais e civis de Portugal. Cobertura de **todos os concelhos** do território continental e ilhas.

### Fontes de dados
- **Tombo.pt / Digitarq** — Imagens digitalizadas de registos paroquiais
- **FamilySearch** — Índices já transcritos
- **Transkribus** — Transcrição HTR de manuscritos antigos
- **Contribuições da comunidade**

### Tipos de registos
- **Nascimentos / Batismos**
- **Casamentos**
- **Óbitos**

### Período
- Registos paroquiais: **1654 — 1911**
- Registo civil: **1911 — presente**

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

### 1. Extrair inventário de um concelho
```bash
python extract_inventory.py
```

### 2. Iniciar interface web
```bash
python web_app.py
```
Aceda a: http://localhost:5000

### 3. Pesquisar registos
```bash
python -c "
from database import search_by_name
results = search_by_name('Maria Silva')
for r in results:
    print(f'{r[\"nome\"]} - {r[\"data_obito\"]} - {r[\"freguesia\"]}')
"
```

### 4. Sincronizar com FamilySearch
```bash
python -c "
from database import sync_with_familysearch
sync_with_familysearch()
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
