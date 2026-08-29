# Plano de Melhorias e Análise da Aplicação Web — Genealogia Portugal

Este documento regista a análise completa da aplicação web e a lista detalhada de melhorias planeadas para a apresentação de dados genealógicos (óbitos, casamentos e batismos), garantindo total integração com o Supabase e escalabilidade.

---

## 1. Análise do Estado Atual

### Pontos Fortes
- **Arquitetura Serverless / Cloud Ready:** Aplicação Flask em Python compatível com Vercel, ligada diretamente ao Supabase (PostgreSQL).
- **Volume de Dados:** Mais de **8.750 registos de óbitos** indexados e validados para o concelho de Celorico da Beira.
- **Interface Moderna:** Design responsivo em Dark Mode (tipografia Inter, cartões limpos, barras de estatísticas e mapas).
- **Relações Familiares e Fontes:** Captura estruturada de Pai, Mãe, Cônjuge e link direto para a imagem do documento original no Digitarq.

### Oportunidades de Melhoria
1. **Filtros e Granularidade na Pesquisa:** Atualmente a pesquisa é feita por texto livre (`ilike`). Falta filtragem por tipo de evento (Óbito, Casamento, Nascimento), intervalo de anos e freguesia específica.
2. **Links de Livros de Arquivo:** Além da imagem individual (`file_id`), associar a referência do livro paroquial original (ex: `PT/TT/PRQ/PCLB19/003/O1`) para contextualização arquivística.
3. **Visualização Detalhada (Modal / Página de Detalhe):** Permitir clicar num registo para ver a transcrição integral gerada pela IA (HTR/Gemini), metadados e árvore genealógica imediata.
4. **Preparação para Casamentos e Nascimentos:** A base de dados e o frontend precisam de extensões para suportar novos tipos de registos paroquiais (1654–1911).
5. **Mapa Interativo:** Enriquecer a página `/mapa` com indicadores visuais de volume de registos por freguesia e distribuição cronológica.

---

## 2. Lista Priorizada de Melhorias (Roadmap)

### Fase 1: Enriquecimento da Pesquisa e Cartões de Dados
- [x] **Filtros de Tipo de Registo:** Seletor rápido (Todos, Óbitos ✝️, Casamentos 💍, Nascimentos 👶) implementado no `index.html` com fallback seguro caso a coluna `tipo_registo` ainda não esteja migrada.
- [x] **Filtros Temporais:** Seletor de intervalo de anos (ex: 1700–1800, 1800–1900).
- [x] **Referência do Livro Paroquial:** Cruzar o `file_id` com o inventário (`celorico_completo.json`) para exibir o código do livro do Arquivo Distrital (ex: `PT/TT/PRQ/...`) e link para o fundo documental.
- [x] **Paginação / Scroll Infinito:** Substituir o limite estático de 50/100 resultados por paginação fluida ou scroll infinito para explorar os 8.700+ registos.

### Fase 2: Vista de Detalhe do Registo (Modal / Página Dedicada)
- [x] **Modal de Detalhe:** Ao clicar num cartão, abrir um modal com:
  - Nome completo e datas normalizadas.
  - Árvore de familiares (Pai, Mãe, Cônjuge).
  - Transcrição original integral (`raw_text` do HTR).
  - Visualizador incorporado ou link direto para a imagem de alta resolução no Digitarq.

### Fase 3: Transição para Casamentos e Nascimentos
- [x] **Expansão do Schema Supabase:** `migrations/add_tipo_registo.sql` adiciona a coluna `tipo_registo` (`DEAT`/`MARR`/`BIRT`) + índice; as colunas `data_nascimento` e `data_casamento` já existiam. A migração é idempotente e segura (nada é dropado).
- [x] **Páginas Específicas por Tipo:** Cartões com badge de tipo (Óbito/Casamento/Nascimento) e modal de detalhe que revela `data_nascimento`/`data_casamento` quando presentes. Cartões totalmente específicos por evento ficam pendentes até existirem dados MARR/BIRT.

### Fase 4: Evolução do Mapa e Estatísticas
- [x] **Mapa Dinâmico (`/mapa`):** Mostrar popups interativos em cada freguesia com contagem detalhada por tipo de ato e períodos cronológicos.
- [x] **Gráficos de Natalidade/Mortalidade:** Adicionar gráficos simples de distribuição por século.
- [x] **Cobertura por Freguesia na Web:** Tabela completa em `index.html` com 2.343 livros / 26.813 páginas / 26.878 nomes por freguesia (Galisteu e São Martinho assinalados).
- [x] **Pesquisa Robusta com Timeout:** `fetchBatch` agora tenta `/api/pessoas` (backend) com fallback para Supabase direto, ambos com `AbortController` de 8s para não ficar a pensar.

### Fase 5: Apresentação e Exportação (2026-08-28)
- [x] **Árvore Genealógica Visual:** Modal com bloco destacado Pais → Registo → Cônjuge.
- [x] **Exportação CSV/GEDCOM:** Botões no topo dos resultados para descarregar os registos carregados.
- [x] **Pesquisa Fonética e Variantes Históricas:** Módulo `name_phonetics.py` com Soundex PT e clusters de grafias arcaicas (Joam/João, Manoel/Manuel, Theresa/Teresa, etc.) integrado em `/api/pessoas`, `/api/variantes` e `index.html`.
- [x] **Heatmap por Freguesia no Mapa:** `templates/map.html` agora colore cada `circleMarker` num gradiente de densidade (azul → verde → amarelo → vermelho) proporcional ao número de registos, com legenda de densidade sobreposta ao mapa.
- [x] **Timeline Interativa por Década:** Gráfico clicável em `templates/map.html` (`/api/decadas`) que filtra a pesquisa por década (link para `/?from_year=&to_year=`).

---

## 3. Registo de Alterações no GitHub
- Commit inicial da interface moderna em `index.html` com suporte a relações e link Digitarq.
- Registo deste plano de melhorias em `WEB_IMPROVEMENTS_PLAN.md` para acompanhamento contínuo.
