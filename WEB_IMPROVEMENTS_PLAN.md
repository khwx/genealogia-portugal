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
- [ ] **Filtros de Tipo de Registo:** Adicionar seletor rápido (Todos, Óbitos ✝️, Casamentos 💍, Nascimentos 👶).
- [ ] **Filtros Temporais:** Seletor de intervalo de anos (ex: 1700–1800, 1800–1900).
- [x] **Referência do Livro Paroquial:** Cruzar o `file_id` com o inventário (`celorico_completo.json`) para exibir o código do livro do Arquivo Distrital (ex: `PT/TT/PRQ/...`) e link para o fundo documental.
- [x] **Paginação / Scroll Infinito:** Substituir o limite estático de 50/100 resultados por paginação fluida ou scroll infinito para explorar os 8.700+ registos.

### Fase 2: Vista de Detalhe do Registo (Modal / Página Dedicada)
- [ ] **Modal de Detalhe:** Ao clicar num cartão, abrir um modal com:
  - Nome completo e datas normalizadas.
  - Árvore de familiares (Pai, Mãe, Cônjuge).
  - Transcrição original integral (`raw_text` do HTR).
  - Visualizador incorporado ou link direto para a imagem de alta resolução no Digitarq.

### Fase 3: Transição para Casamentos e Nascimentos
- [ ] **Expansão do Schema Supabase:** Garantir colunas para `tipo_registo` (`DEAT`, `MARR`, `BIRT`), `data_casamento`, `data_nascimento`.
- [ ] **Páginas Específicas por Tipo:** Adaptar os cartões para destacar a informação relevante de cada tipo de evento (ex: cônjuges em casamentos, pais em batismos).

### Fase 4: Evolução do Mapa e Estatísticas
- [ ] **Mapa Dinâmico (`/mapa`):** Mostrar popups interativos em cada freguesia com contagem detalhada por tipo de ato e períodos cronológicos.
- [x] **Gráficos de Natalidade/Mortalidade:** Adicionar gráficos simples de distribuição por século.

---

## 3. Registo de Alterações no GitHub
- Commit inicial da interface moderna em `index.html` com suporte a relações e link Digitarq.
- Registo deste plano de melhorias em `WEB_IMPROVEMENTS_PLAN.md` para acompanhamento contínuo.
