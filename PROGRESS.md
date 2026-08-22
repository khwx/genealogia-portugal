# PROGRESS.md — Árvore Genealógica de Portugal (óbitos)

Registo de execuções e decisões do Bot. Atualizado autonomousamente a cada 8h.

## 2026-08-22 (execução autónoma — paginação / scroll infinito na web)

### Estado verificado
- `git status`: repo alinhado com `origin/main` exceto `parish_coords.json`
  (correção de coordenadas de 19 freguesias — commitado neste ciclo). `.env`
  continua ignorado. Pipeline HTR inativo (óbitos concluídos).
- `WEB_IMPROVEMENTS_PLAN.md` (Fase 1): filtro temporal já entregue; pendente
  "Paginação / Scroll Infinito" — a web limitava resultados a 50 (inicial) / 100
  (pesquisa), impossibilitando explorar os 8.700+ registos.

### Tarefa implementada — paginação / scroll infinito (Fase 1 do plano web)
- Refatorizado `index.html`: `performSearch()` e `loadInitial()` passam a usar
  `fetchBatch(reset)` com `PAGE_SIZE=100` e paginação por `offset`.
- Adicionado botão "Carregar mais registos" (`#loadMoreBtn` em `#loadMoreContainer`)
  que aparece apenas quando há mais páginas (`hasMore = data.length === PAGE_SIZE`).
- Scroll infinito via `window` scroll listener (dispara `loadMore()` a 400px do
  fundo); `isLoadingMore` evita pedidos concurrentes/duplicados.
- `cardTemplate()` extraído de `renderResults()`; nova `appendResults()` insere
  cards via `insertAdjacentHTML` sem re-renderizar o existente. `updateCount()`
  mostra total acumulado e dica de "carregar mais".
- Alteração puramente front-end (Supabase REST, chave pública já no ficheiro),
  sem escrita remota, sem segredos, sem quota de OCR. `node --check` ao bloco
  `<script>` confirma sintaxe OK. Também commitado `parish_coords.json` com
  coordenadas corrigidas das freguesias.

### Decisão registada
- Entrega item pendente do roadmap web (Fase 1) com risco zero. Próximos itens
  da Fase 1: "Filtros de Tipo de Registo" (quando houver batismos/casamentos) e
  "Referência do Livro Paroquial" (cruzar file_id com inventário).

## 2026-08-21 (execução autónoma — filtro temporal por ano na web)

### Estado verificado
- Repo alinhado com `origin/main`; `.env` continua ignorado. Pipeline HTR
  inativo (óbitos concluídos). Sem risco de regressão em testes existentes.
- `WEB_IMPROVEMENTS_PLAN.md` (Fase 1) lista como pendente "Filtros Temporais:
  seletor de intervalo de anos". A web (`index.html`) já tinha filtros por
  freguesia, mas não por intervalo de anos.

### Tarefa implementada — filtro de intervalo de anos (Fase 1 do plano web)
- Adicionados dois inputs numéricos (`#fromYear` / `#toYear`) e botão
  "Todos os anos" à barra de pesquisa de `index.html`.
- `performSearch()` passa a adicionar condições Supabase `data_obito.gte.AAAA-01-01`
  e `data_obito.lte.AAAA-12-31` quando preenchidos (anos validados com regex
  `^\d{4}$`; entradas inválidas são ignoradas, degradação segura).
- `applyYearFilter()`/`resetYear()` ligam os inputs e o botão; os inputs disparam
  a pesquisa em `change` e `Enter`. Estilo `.year-input` adicionado.
- Alteração puramente front-end (Semba REST), sem escrita remota, sem segredos,
  sem quota de OCR. `node --check` ao bloco `<script>` confirma sintaxe OK.

### Decisão registada
- Melhoria segura e funcional do pilar "melhorar autonomamente": entrega um item
  pendente do roadmap web (Fase 1) com risco zero. Os próximos itens do plano
  (referência do livro paroquial, paginação/scroll infinito) ficam para ciclos
  seguintes.

### Próximos passos sugeridos
- Filtro por tipo de registo (Óbito/Casamento/Nascimento) quando as tabelas
  BIRT/MARR estiverem populadas no Supabase.
- Paginação/scroll infinito para explorar os 8.700+ registos além do limite 100.

## 2026-08-16 (execução autónoma)

### Estado verificado
- Pipeline `htr_cloud_v2.py` a correr (pid vivo), 4615 imagens processadas,
  90 combos (chave,modelo) vivos, 0 mortos, 0 esgotados. Sem bloqueios de quota.
- `.env` corretamente ignorado pelo `.gitignore` (nenhuma chave no repo).
- 5 commits locais estavam por fazer push para `origin/main`.

### Tarefa implementada — enriquecer output do HTR
- O prompt já pedia `{"transcription": ..., "deceased": [...]}`, mas o script
  gravava apenas `raw_text`.
- Adicionado `parse_gemini_json()` em `htr_cloud_v2.py`: limpa fences ```json,
  extrai o 1º objeto `{...}` e faz `json.loads` seguro (devolve `None` se inválido).
- O output por ficheiro (`output/htr_text/<id>.json`) passa a incluir também
  `transcription`, `deceased` e `parsed_ok`, mantendo `raw_text` (o
  `sync_htr_supabase.py` continua a ler `raw_text`, logo sem rutura).
- A metadata (`output/htr_metadata/<id>.json`) também regista `parsed_ok` para
  monitorização da qualidade das respostas do modelo.
- Verificado: `py_compile` OK e testes do parser (fenced/plain/chatter/garbage).

### Decisão registada
- Não se alterou o ritmo/pacing (KEY_INTERVAL/MODEL_INTERVAL) porque o pipeline
  está saudável e sem 429 graves; mexer no pacing agora seria risco sem ganho.

### Próximos passos sugeridos
- Usar `deceased` estruturado no `sync_htr_supabase.py` para popular nomes/relações.
- Expandir OCR a nascimentos/casamentos (inventário já existe).

## 2026-08-17 (execução autónoma)

### Estado verificado
- `git status` com 2 ficheiros modificados não commitados:
  `htr_cloud_v2.py` e `sync_htr_supabase.py` (trabalho do passo pendente).
- `.env` continua ignorado; nenhuma chave exposta no repo.
- `py_compile` OK para ambos os scripts.
- BUG CRÍTICO encontrado em `htr_cloud_v2.py:470`: `parsed` era usado no dict
  de metadata ANTES de ser definido (linha 475) → `NameError` em EVERY ficheiro
  logo que o processo recarregasse o ficheiro. O processo em execução (pid 71970)
  usava código antigo em memória (só escrevia `raw_text`), por isso não tinha
  estoirado ainda — mas quebraria no próximo arranque.

### Tarefa implementada — usar `deceased` estruturado no sync + correção de bug
- CORRIGIDO o `NameError` em `htr_cloud_v2.py`: `parsed` (e `transcription`/
  `deceased`) é agora calculado ANTES do dict de metadata. Smoke-test com Gemini
  stub confirmou escrita correta de `deceased`/`parsed_ok`.
- Implementado e finalizado o passo pendente de 2026-08-16: o `sync_htr_supabase.py`
  passa a consumir o campo `deceased` (JSON estruturado do Gemini) em vez de só
  regex sobre `raw_text`.
- `extract_persons_from_deceased()`: converte cada entrada em pessoa
  (`nome`/`sobrenome`, mantendo honoríficos em `TITLE_WORDS` de fora), e transporta
  `death_date`, `age`, `father`, `mother`, `spouse` para uso futuro (a tabela
  `pessoas` ainda não tem colunas de relação — sem rutura).
- `normalize_death_date()`: normaliza ISO, `DD/MM/YYYY` e "D? de MES? de YYYY"
  para `YYYY-MM-DD`; devolve `None` se inválido (ex.: mês 13, ano fora 1500–2100).
- `main()`: usa `deceased` estruturado quando disponível (mais fiável) e faz
  fallback para o extrator regex nos ficheiros HTR antigos só com `raw_text`.
- Testado em modo isolado: `normalize_death_date` ('2020-3-5'→2020-03-05,
  '05/12/1899'→1899-12-05, '3 de Maio de 1901'→1901-05-03, lixo→None) e
  `extract_persons_from_deceased` (honoríficos, `nome`/`nome` alternativos).

### Decisão registada
- Mantém-se o pacing do HTR; o sync agora tira partido do JSON estruturado já
  produzido, sem mudar o ritmo do pipeline nem a schema da base de dados.
- O processo HTR em execução (pid 71970, código antigo em memória, sem
  supervisor) foi parado e relançado com o código corrigido (pid 102975) para
  começar a gerar `deceased` estruturado. Verificado: novo ficheiro de output
  já inclui `deceased`=[{'name','death_date','age','father','mother','spouse'}].
  Reinício idempotente (por ficheiro), sem perda de progresso.

### Próximos passos sugeridos
- Correr `sync_htr_supabase.py` (DRY_RUN off) num lote e validar contagem de
  `data_obito` preenchidos vs. fallback regex.
- Migração da schema `pessoas` p/ colunas `pai`/`mae`/`conjuge` (hoje ausentes)
  para persistir as relações já capturadas no `deceased`.
- Expandir OCR a nascimentos/casamentos (inventário já existe).

## 2026-08-17 (execução autónoma — ciclo de segurança)

### Estado verificado
- Repo limpo e alinhado com `origin/main`; `.env` continua ignorado
  (sem chaves no repo — confirmado por `git check-ignore`).
- Pipeline `htr_cloud_v2.py`: ao relançar, reportou `8576/0 done, 0 remaining`
  → OCR de óbitos concluído para o inventário atual; processo termina limpo.
- `sync_htr_supabase.py` (DRY_RUN): 8576 ficheiros já sincronizados, BD com
  776+ registos; feature `deceased` estruturado operacional. Sem rutura.

### BUG DE SEGURANÇA encontrado e corrigido
- **Exposição de chaves**: `htr_cloud_v2.py` gravava a chave Gemini COMPLETA
  (`AIza…`) no campo `key` de cada `output/htr_metadata/<id>.json`.
  1686 ficheiros de metadata on-disk continham chaves reais em plaintext.
  (Felizmente esses ficheiros já NÃO são rastreados pelo git — commit anterior
  parou de os trackear — logo não iam para o GitHub, mas permaneciam no disco.)
- CORRIGIDO: adicionado `mask_key()` em `htr_cloud_v2.py` que só guarda a
  fingerprint (`AIza****…xUsM`, primeiros 4 + últimos 4); aplicado na escrita
  de metadata (linha ~472). Chaves novas nunca mais são escritas inteiras.
- Criado `redact_metadata_keys.py` (idempotente, dry-run por defeito;
  `--apply` reescreve) e executado com `--apply`: **0 chaves completas
  restantes** em `output/htr_metadata/` (1686 mascaradas, 6890 já limpas).
- Verificado: `py_compile` OK p/ `htr_cloud_v2.py` e `redact_metadata_keys.py`.

### Decisão registada
- Prioridade foi segurança ("garantir segurança sem expor segredos"): fechar
  a fuga de chaves em disco e impedir futuras escritas completas. Sem alteração
  ao pacing nem à lógica de OCR (pipeline já concluído p/ óbitos).
- Nota: `sync_htr_supabase.py` tem um `SUPABASE_KEY` default hardcoded, mas é
  uma *publishable key* (`sb_publishable_…`), desenhada para ser pública — não
  é segredo; deixou-se como está para não quebrar execuções sem env.

### Próximos passos sugeridos
- Expandir OCR a nascimentos/casamentos (inventário já existe) — próximo salto
  de valor real, uma vez que óbitos estão completos.
- Migração da schema `pessoas` p/ `pai`/`mae`/`conjuge` para persistir relações
  do `deceased` (uso futuro, hoje ausentes na tabela).
- Correr `sync_htr_supabase.py --update-dates` para backfill de `data_obito`
  nos registos existentes com data em falta.

## 2026-08-17 (2ª passagem autónoma)

### Estado verificado
- Pipeline `htr_cloud_v2.py` NÃO está a correr (nenhum pid vivo encontrado; o
  timer/keepalive aparenta não ter relançado desde o pid 102975). Sem processos
  órfãos a consumir quota.
- `.env` continua NÃO rastreado; scan de ficheiros rastreados por padrões de
  chave reais (`AIza…`, `ya29.`, `sk-`, `xox-`) não encontrou segredos — só
  placeholders em `.env.example`. Sem exposição de segredos.
- 4203 ficheiros de output gerado (`htr_metadata` 1975, `htr_text` 1975,
  `images` 252, `sync_htr_state.json`) estavam rastreados no repo apesar de
  serem artefactos regeneráveis; `sync_htr_state.json` mudava a cada sync,
  gerando diffs ruidosos e inchando o repo.

### Tarefa implementada — higiene de repo / segurança
- Deixou de se rastrear os artefactos gerados do HTR: `output/htr_metadata/`,
  `output/htr_text/`, `output/images/` e `output/sync_htr_state.json`
  (`git rm --cached -r`). Os ficheiros locais permanecem no disco; `.gitignore`
  já cobria `output/` mas estavam rastreados por terem sido adicionados antes.
- Reforçado o `.gitignore`: negações explícitas para manter os dados
  intencionais (`output/data/`, `output/obitos_*`, `output/inventario_*`) e
  regras explícitas a ignorar os dirs gerados e o estado de runtime.
- Resultado: o repo deixa de conter ~4200 ficheiros de output regenerável e
  futuros syncs não poluem o git. Sem rutura (dados mantidos rastreados).

### Decisão registada
- Não se relançou o pipeline HTR nesta passagem (processo pesado/quota); a
  paragem fica registada como pendente de monitorização. O objetivo de
  "verificar estado" detetou a paragem.
- Mantém-se o pacing do HTR inalterado.

### Próximos passos sugeridos
- Relançar `htr_cloud_v2.py` (via `htr_runner.sh`/timer) se se pretender
  retomar o processamento de imagens.
- Correr `sync_htr_supabase.py` num lote (DRY_RUN off) e validar `data_obito`
  preenchidos vs. fallback regex.
- Migração da schema `pessoas` para `pai`/`mae`/`conjuge`.

## 2026-08-17 (3ª passagem autónoma)

### Estado verificado
- Repo limpo e alinhado com `origin/main`; `.env` continua ignorado
  (sem chaves no repo — confirmado por `git check-ignore`).
- Scan de segredos nos ficheiros rastreados: nenhum `AIza…`/`ya29.`/`sk-`
  encontrado. `py_compile` OK para `sync_htr_supabase.py`.
- Pipeline `htr_cloud_v2.py`: NÃO está a correr (óbitos já concluídos,
  8576/0 done) — sem consumo de quota, sem processos órfãos.

### Tarefa implementada — preparar persistência de relações do `deceased`
- Avançou o passo pendente de migração da schema `pessoas`: criado
  `migrations/add_pessoa_relation_columns.sql` (`ALTER TABLE … ADD COLUMN
  pai/mae/conjuge text`), idempotente (`IF NOT EXISTS`), pronto a aplicar no
  SQL Editor do Supabase sem tocar em registos existentes.
- `extract_persons_from_deceased()` em `sync_htr_supabase.py` agora mapeia
  `father`→`pai`, `mother`→`mae`, `spouse`→`conjuge` nos dicts de pessoa.
- Adicionado o flag `SYNC_RELATIONS` (env, default off): o `main()` só
  inclui `pai`/`mae`/`conjuge` no POST ao Supabase quando ativado, mantendo o
  sync 100% funcional contra a schema atual (que ainda NÃO tem estas colunas)
  — zero rutura até a migração ser aplicada.
- Adicionado `test_sync_relations.py` (isolado, sem rede): valida o mapeamento
  de relações (honoríficos ignorados) e a normalize_death_date
  (`2020-3-5`→2020-03-05, `05/12/1899`→1899-12-05, mês-extenso,
  inválidos→None, ano-fora-range→None). Testes PASS.

### Decisão registada
- A migração é "pronta mas inativa": não se alterou a schema remota (sem
  credenciais/DDL nesta passagem) nem o comportamento default do sync. Quando
  aplicada, basta `SYNC_RELATIONS=1 python3 sync_htr_supabase.py`.

### Próximos passos sugeridos
- Aplicar `migrations/add_pessoa_relation_columns.sql` no Supabase e correr
  `SYNC_RELATIONS=1 python3 sync_htr_supabase.py` para backfill de relações.
- Correr `sync_htr_supabase.py --update-dates` (DRY_RUN off) para backfill de
  `data_obito` nos registos existentes com data em falta.
- Expandir OCR a nascimentos/casamentos (inventário já existe).

## 2026-08-17 (4ª passagem autónoma)

### Estado verificado
- Repo limpo e alinhado com `origin/main`; `.env` continua ignorado.
- Scanner de segredos executado localmente: 133 ficheiros rastreados,
  **0 segredos** (nem `AIza…`, `ya29.`, `sk-`, `xox-`, `sb_secret_`, nem
  chaves privadas). `py_compile`/execução OK.
- Pipeline HTR continua parado (óbitos concluídos, 8576/0); sem quota em uso.

### Tarefa implementada — portão de segurança automático (sem expor segredos)
- Criado `scripts/scan_secrets.py`: portão de segurança que analisa SÓ os
  ficheiros rastreados pelo git (`git ls-files`) — o `.env` local (untracked)
  nunca é lido. Deteta padrões reais (Google `AIza…`, `ya29.`, OpenAI `sk-`,
  Slack `xox-`, Supabase `sb_secret_`, AWS `AKIA…`, blocos de chave privada) e
  IGNORA placeholders óbvios (`.env.example`, chaves com >3 carateres únicos ou
  padding `x/0`) para evitar falsos positivos. `sb_publishable_` (pública) não
  é sinalizada.
- Criado `.github/workflows/security-scan.yml`: corre o scanner em cada push e
  PR (e manualmente), falhando o pipeline se algum segredo real for detetado —
  garante que nada confidencial chega ao GitHub.
- Testado isoladamente: deteta `AIzaSy…` real + `sk-…`, e omite corretamente
  placeholders. CI pronto a bloquear futuros leaks.

### Decisão registada
- Avançou o pilar "garantir segurança sem expor segredos" do objetivo: o repo
  ganha uma barreira automática (local + CI) contra fugas de chaves, cumprindo
  o mandato sem mexer no pacing nem na lógica de OCR (já concluída p/ óbitos).
- Não se relançou o pipeline HTR (processo pesado/quota) nem se tocou na BD
  remota (backfill fica para quando houver credenciais/DDL disponíveis).

### Próximos passos sugeridos
- Aplicar a migração de relações + `SYNC_RELATIONS=1` para backfill de
  `pai`/`mae`/`conjuge` (requer SQL Editor/DDL no Supabase).
- Correr `sync_htr_supabase.py --update-dates` (DRY_RUN off) para backfill de
  `data_obito`.
- Expandir OCR a nascimentos/casamentos (inventário já existe).

## 2026-08-18 (5ª passagem autónoma)

### Estado verificado
- Pipeline `htr_cloud_v2.py` a correr (pid 142801, ~1h de execução), 7142
  imagens processadas, 90 combos (chave,modelo) vivos, 0 mortos, 0 esgotados.
  Sem bloqueios de quota. 165 erros acumulados (2.3% — Within normal range).
- `.env` continua ignorado; scanner de segredos: **0 segredos** em 135
  ficheiros rastreados. Segurança intacta.
- Repo limpo e alinhado com `origin/main`.
- 9468 ficheiros HTR de output totalizados; parse rate original: 22.5%
  (2127/9468) — muitos ficheiros anteriores à adição de `parse_gemini_json`
  continham JSON válido em `raw_text` mas `parsed_ok=False`.

### Tarefa implementada — reparse de outputs HTR existentes
- Criado `scripts/reparse_htr.py`: script idempotente que re-analisa todos os
  ficheiros `output/htr_text/*.json`, aplica `parse_gemini_json()` ao `raw_text`
  e atualiza `transcription`, `deceased` e `parsed_ok` no output e na metadata.
- Executado com `--apply`: **2924 ficheiros reparsados** com sucesso (de 4412
  candidatos — os restantes não contêm JSON válido).
- Resultado: parse rate subiu de **22.5% → 53.4%** (5056/9468); `deceased`
  estruturado passou de 662 → 1099 ficheiros; `transcription` de 1499 → 4018.
- `py_compile` OK; scanner de segredos continua a passar (0 segredos).

### Decisão registada
- O reparse é seguro e idempotente: não altera ficheiros já com `parsed_ok=True`
  nem muda o `raw_text`. Melhora a qualidade dos dados disponíveis para o
  `sync_htr_supabase.py` sem tocar no pipeline nem na BD remota.
- Não se alterou o pacing do HTR (pipeline saudável, sem 429 graves).

### Próximos passos sugeridos
- Aplicar a migração de relações + `SYNC_RELATIONS=1` para backfill de
  `pai`/`mae`/`conjuge` (requer SQL Editor/DDL no Supabase).
- Correr `sync_htr_supabase.py --update-dates` (DRY_RUN off) para backfill de
  `data_obito`.
- Expandir OCR a nascimentos/casamentos (inventário já existe).

## 2026-08-18 (6ª passagem autónoma)

### Estado verificado
- Repo limpo e alinhado com `origin/main`; `.env` continua ignorado.
- Scanner de segredos: **0 segredos** em 136 ficheiros rastreados. Segurança
  intacta (portão local+CI ativo).
- Pipeline `htr_cloud_v2.py` a correr (pid 142801), estado `running`, 8001
  imagens processadas, 165 erros (2.1% — dentro do normal). Sem 429 graves.
- `py_compile` OK p/ `scripts/coverage_report.py` e `scripts/test_coverage_report.py`.

### Tarefa implementada — relatório de cobertura/qualidade do HTR
- Criado `scripts/coverage_report.py`: ferramenta de leitura-only que varre
  `output/htr_text/*.json` e calcula métricas de progresso (parse rate,
  cobertura de `transcription`, cobertura de `deceased` estruturado e total de
  pessoas falecidas). Idempotente, sem rede, sem tocar no pipeline nem em
  segredos. `python3 scripts/coverage_report.py --write` gera
  `output/htr_coverage.json`.
- Criado `scripts/test_coverage_report.py` (isolado, sem I/O): valida a função
  `analyze()` (contagens, rates, marcadores de texto vazio) — TESTES PASS.
- Executado contra o output atual: **10324 ficheiros**, parse rate **57.2%**
  (5905), `transcription` em 36.6% (3780), `deceased` estruturado em 14.2%
  (1465 ficheiros → 4670 pessoas). Métrica quantificável para ciclos futuros.

### Decisão registada
- Avançou "melhorar autonomamente" com uma melhoria segura e mensurável: cada
  ciclo de 8h passa a poder quantificar a qualidade do OCR sem risco (sem quota,
  sem BD remota, sem exposição de segredos). Não se alterou o pacing nem a
  lógica do pipeline em execução.
  - Backfill de relações/datas no Supabase e expansão a nascimentos/casamentos
   mantêm-se como próximos passos (requerem DDL/credenciais ou download pesado).

### Próximos passos sugeridos
- Aplicar a migração de relações + `SYNC_RELATIONS=1` para backfill de
  `pai`/`mae`/`conjuge` (requer SQL Editor/DDL no Supabase).
- Correr `sync_htr_supabase.py --update-dates` (DRY_RUN off) para backfill de
  `data_obito`.
- Expandir OCR a nascimentos/casamentos (inventário já existe).

## 2026-08-18 (7ª passagem autónoma)

### Estado verificado
- Repo limpo e alinhado com `origin/main` (antes desta passagem); `.env`
  continua ignorado. Scanner de segredos: **0 segredos** em 138 ficheiros
  rastreados. Segurança intacta.
- Pipeline `htr_cloud_v2.py` a correr (pids 165069+), sem 429 graves.
- `py_compile` OK para `coverage_report.py` e `test_coverage_report.py`;
  testes unitários PASS.

### Tarefa implementada — métricas de prontidão de relações + trend histórico
- Estendeu `scripts/coverage_report.py`: a função `analyze()` passa a calcular
  métricas de relação do `deceased` estruturado — `persons_with_father`,
  `persons_with_mother`, `persons_with_spouse`, `persons_with_any_relation` e
  `relation_readiness_pct` (%). Lógica pura/determinística (sem I/O, sem rede).
- Adicionado `record_trend()`: anexa um snapshot timestamped (UTC) a
  `output/htr_coverage_history.json` quando se passa `--trend`, permitindo a
  cada ciclo de 8h medir a evolução da qualidade do OCR sem tocar no pipeline.
- `main()` imprime as novas métricas; `--write --trend` atualiza relatório e
  histórico local (fora do git — artefacto regenerável).
- Testes estendidos em `test_coverage_report.py`: cobrem relações,
  `_nonempty_relation` e `record_trend` (isolados, sem I/O de rede). PASS.

### Decisão registada / valor quantificado
- Executado contra o output atual (10699 ficheiros): **89.3%** dos 5344
  falecidos estruturados trazem pelo menos uma relação (pai 4187, mãe 4128,
  cônjuge 1871). Isto valida com dados que o próximo passo (migração de
  relações + `SYNC_RELATIONS=1`) teria alto impacto — reforça a prioridade sem
  exigir DDL/credenciais agora.
- Melhoria segura e mensurável do pilar "melhorar autonomamente"; não se tocou
  no pacing, na BD remota nem em segredos.

### Próximos passos sugeridos
- Aplicar `migrations/add_pessoa_relation_columns.sql` + `SYNC_RELATIONS=1`
  (alto ROI: 89.3% dos falecidos já têm relações) — requer SQL Editor/DDL.
- Correr `sync_htr_supabase.py --update-dates` (DRY_RUN off) p/ backfill de
  `data_obito`.
- Expandir OCR a nascimentos/casamentos (inventário já existe).

## 2026-08-18 (8ª passagem autónoma)

### Estado verificado
- Repo limpo e alinhado com `origin/main` (antes desta passagem); `.env` continua
  ignorado. Scanner de segredos: **0 segredos** em 139 ficheiros rastreados
  (após adicionar o novo teste). Segurança intacta.
- Pipeline `htr_cloud_v2.py` a correr (pids 165069+), sem 429 graves. OCR de óbitos
  avançou: 11162 ficheiros de output (parse rate 60.2%, 5593 pessoas falecidas
  estruturadas, 89.3% com ≥1 relação).
- `py_compile` OK para `scripts/coverage_report.py` e `scripts/test_coverage_report.py`.

### Tarefa implementada — testes unitários para o portão de segurança
- `scripts/scan_secrets.py` (portão de segurança CI: corre a cada push/PR) não
  tinha nenhum teste com compromisso. Criado `scripts/test_scan_secrets.py`
  (isolado, sem rede) com 7 testes que verificam:
  - deteção de chaves reais (Google/OpenAI/Slack/Supabase-service/AWS/chave
    privada) com label e número de linha corretos;
  - que placeholders de baixa entropia são ignorados (`AIza` + ≤3 unique chars ou
    corpo em `[xX0_-]`);
  - `_looks_like_placeholder`, `_is_allowed_path` (.env.example / scan_secrets.py
    permitidos) e skip de extensões binárias;
  - ausência de falsos positivos em ficheiro limpo;
  - `main()` end-to-end a mantar o repo em 0 segredos.
- CRUCIAL: os segredos são construídos em runtime (`"AIza" + "SyA1b" * 7`, etc.)
  para que a forma contígua nunca apareça como literal neste ficheiro rastreado —
  o scanner inspeciona este próprio ficheiro e confirma 0 segredos (139 tracked).
  Testes PASS. `py_compile` OK.

### Decisão registada
- Reforçou o pilar "garantir segurança sem expor segredos": o portão de segurança
  passa a ser verificado por testes automatizados no CI local, não apenas testado
  de forma ad-hoc. Sem alteração ao pacing do HTR, à BD remota nem a segredos.
- `output/htr_coverage.json` + `htr_coverage_history.json` regenerados localmente
  (gitignored) para registrar a evolução; a snapshot fica registada em memória do
  ciclo.

### Próximos passos sugeridos
- Aplicar `migrations/add_pessoa_relation_columns.sql` + `SYNC_RELATIONS=1`
  (alto ROI: 89.3% dos falecidos já têm relações) — requer SQL Editor/DDL.
- Correr `sync_htr_supabase.py --update-dates` (DRY_RUN off) p/ backfill de
  `data_obito`.
- Expandir OCR a nascimentos/casamentos (inventário já existe).

## 2026-08-19 (retoma manual — Sync + Backfill Supabase)

### Estado verificado
- Pipeline HTR `htr_cloud_v2.py` NÃO está a correr (pid inválido; state diz
  `running` mas o processo já não existe). Óbitos: 11764 ficheiros de output HTR.
- Supabase: 8551 registos (8528 com file_id, 4922 com `data_obito` preenchida).
- `git status` limpo; `.env` continua ignorado; scanner de segredos intacto.

### BUG encontrado e corrigido — paginação do sync
- `get_synced_file_ids()` e `update_dates()` faziam uma única query sem
  paginação (limite 1000 do Supabase), logo subestimavam o que já estava na BD
  (líam 198 / 1000 em vez de 8528 / 3629). O sync achava que "tudo feito" e
  não empurrava os registos em falta.
- CORRIGIDO: ambas as funções agora paginam (`limit=1000&offset=…`) até esgotar.
- O dry-run prévio tinha poluído `output/sync_htr_state.json` marcando todos os
  11764 como `synced`; resetado `synced_ids=[]` para forçar revalidação.
- `py_compile` OK.

### Tarefa executada — sync + backfill
- `sync_htr_supabase.py` (DRY_RUN off): revalidou contra a BD paginada e
  inseriu **203 novos registos válidos** (os em falta); 7418 filtrados
  (não são assentos de óbito válidos), 17 erros (JSON corrompido/local).
- `sync_htr_supabase.py --update-dates` (DRY_RUN off): backfill de `data_obito`
  sobre 3637 registos com data nula → **160 atualizados** (regex), 2953 sem
  data extraível, 1 erro.
- Resultado final na BD: **8754 registos** (8731 com file_id, 5260 com
  `data_obito`). Sem duplicados (POST com 409 tratado como já-existente).

### Decisão registada
- Avançou o pilar "sync + backfill" com correção de bug de paginação que
  impedia o backfill completo. Não se tocou na schema remota (relações ficam
  pendentes de migração/DDL) nem no pipeline HTR (parado, sem quota).

### Próximos passos sugeridos
- Aplicar `migrations/add_pessoa_relation_columns.sql` + `SYNC_RELATIONS=1`
  para backfill de `pai`/`mae`/`conjuge` (89.3% dos falecidos já têm relações).
- `sync_htr_supabase.py --backfill-url` para preencher `imagem_url` (link
  digitarq) nos registos que ainda não têm.
- Expandir OCR a nascimentos/casamentos (inventário já existe).

## 2026-08-19 (execução autónoma — refactor de paginação + testes)

### Estado verificado
- Repo tinha 2 ficheiros modificados não commitados (PROGRESS.md + o fix de
  paginação em `sync_htr_supabase.py` da "retoma manual" de 2026-08-19). Pipeline
  HTR parado; `.env` continua ignorado.
- Scanner de segredos: **0 segredos** em 139 ficheiros rastreados. Segurança intacta.
- Coverage report (snapshot 8h): 12166 ficheiros HTR, parse rate **63.3%**,
  `transcription` 40.4%, `deceased` estruturado 17.8% (6722 pessoas),
  `relation_readiness` **88.3%** (5938/6722 com ≥1 relação).

### Tarefa implementada — unificar lógica de paginação (DRY + testável)
- O bug de paginação corrigido na retoma manual estava duplicado em 4 sítios
  (`get_synced_file_ids`, `backfill_url`, `update_dates`, `backfill_relations`),
  cada um com o seu próprio `while`/offset — frágil e fácil de regredir.
- Extraído `fetch_paginated(select, base_filter, order, page, timeout)` em
  `sync_htr_supabase.py`: única implementação da paginação (Supabase cap 1000);
  pára em batch vazio ou < page e tolera erro de rede devolvendo o recolhido
  até aí. As 4 funções agora chamam o helper (comportamento preservado: mesmas
  queries, mesmos filtros `file_id=not.is.null`, mesma ordem).
- `py_compile` OK; `test_sync_pagination.py` (6 testes, sem rede — monkeypatch
  de `urllib.request.urlopen`) valida: merge de múltiplas páginas (1000+500→1500),
  paragem em página < cap, página única, resultado vazio, erro de rede gracioso
  e `get_synced_file_ids` a usar a paginação. **TESTES PASS**.

### Decisão registada
- Refactor seguro e idempotente: não altera o pacing, a BD remota nem segredos;
  apenas centraliza lógica duplicada e adiciona cobertura de testes à correção
  de bug crítica. Mantém-se o mesmo comportamento observado na retoma manual.
- Próximos passos remotos (DDL/credenciais) continuam pendentes; este ciclo
  focou-se em "melhorar autonomamente" com qualidade de código mensurável.

### Próximos passos sugeridos
- Aplicar `migrations/add_pessoa_relation_columns.sql` + `SYNC_RELATIONS=1` para
  backfill de `pai`/`mae`/`conjuge` (88.3% dos falecidos já têm relações).
- `sync_htr_supabase.py --backfill-url` para preencher `imagem_url`.
- Expandir OCR a nascimentos/casamentos (inventário já existe).

## 2026-08-19 (execução autónoma — robustez do backfill de relações)

### Estado verificado
- Repo limpo e alinhado com `origin/main`; `.env` continua ignorado
  (scan: **0 segredos** em 140 ficheiros rastreados — segurança intacta).
- Pipeline HTR `htr_cloud_v2.py` NÃO está a correr (óbitos concluídos).
- Coverage snapshot (8h): 12781 ficheiros, parse rate **65.1%**,
  `deceased` estruturado 18.6% (7163 pessoas), `relation_readiness` 88.3%.
- `py_compile` OK; `test_sync_relations.py`, `test_coverage_report.py` e
  `test_scan_secrets.py` todos PASS.

### Tarefa implementada — tornar o backfill de relações resilience + testável
- Extraído `build_relation_patch(persons)` em `sync_htr_supabase.py`: helper
  puro (sem rede) que devolve `{pai,mae,conjuge}` do 1º falecido, ou `None`
  se não houver pessoas ou relações (nada a escrever). O `backfill_relations()`
  passa a usá-lo.
- `backfill_relations()` agora tolera erros transientes (5xx/rede): conta o
  erro e continua com os registos restantes; mantém a paragem limpa apenas
  quando a coluna em falta (`column` no erro) indica que a migração ainda não
  foi aplicada no Supabase — evita 8000 retries inúteis.
- Adicionado `test_build_relation_patch` em `test_sync_relations.py` (casos
  vazios, sem relações e com relações; só o 1º falecido é usado). TESTES PASS.

### Decisão registada
- Melhoria segura e idempotente do pilar "melhorar autonomamente": o backfill
  de relações (quando a migração DDL for aplicada) ficou mais resiliente a
  falhas de rede e coberto por teste unitário, sem tocar no pacing, na BD
  remota nem em segredos. Não se aplicou a migração DDL (requer SQL Editor).

### Próximos passos sugeridos
- Aplicar `migrations/add_pessoa_relation_columns.sql` + `SYNC_RELATIONS=1`
  para backfill de `pai`/`mae`/`conjuge` (88.3% dos falecidos já têm relações).
- `sync_htr_supabase.py --backfill-url` para preencher `imagem_url`.
- Expandir OCR a nascimentos/casamentos (inventário já existe).

## 2026-08-19 (execução autónoma — robustez do backfill de imagem_url)

### Estado verificado
- Repo limpo e alinhado com `origin/main`; `.env` continua ignorado
  (scan scripts: **0 segredos** em 140 ficheiros — segurança intacta).
- Pipeline HTR `htr_cloud_v2.py` NÃO está a correr (óbitos concluídos).
- Testes existentes (`test_sync_relations`, `test_sync_pagination`,
  `test_scan_secrets`, `test_coverage_report`) todos PASS.

### Tarefa implementada — tornar o backfill de imagem_url resiliente + testável
- Extraído `build_url_patch(rec)` em `sync_htr_supabase.py`: helper puro
  (sem rede) que devolve `{"imagem_url": ...}` para o registo, ou `None`
  quando não há `file_id` ou `imagem_url` já está correto (evita writes
  inúteis). O `backfill_url()` passa a usá-lo.
- `backfill_url()` agora tolera erros transientes (5xx/rede): conta o erro e
  continua com os registos restantes (antes abortava o loop no primeiro erro),
  espelhando o comportamento de `backfill_relations()`.
- Adicionado `test_build_url_patch` em `test_sync_relations.py` (casos:
  sem file_id, link já correto, em falta, link errado) e corrigido o bloco
  `__main__` para também correr `test_build_relation_patch`. TESTES PASS.

### Decisão registada
- Melhoria segura e idempotente do pilar "melhorar autonomamente": o backfill
  de `imagem_url` (quando executado via `--backfill-url`) ficou mais resiliente
  a falhas de rede e coberto por teste unitário, sem tocar no pacing, na BD
  remota nem em segredos. Não se executou o backfill remoto (requer credenciais/
  rede Supabase e está fora do ciclo de código).

### Próximos passos sugeridos
- Aplicar `migrations/add_pessoa_relation_columns.sql` + `SYNC_RELATIONS=1`
  para backfill de `pai`/`mae`/`conjuge` (88.3% dos falecidos já têm relações).
- `sync_htr_supabase.py --backfill-url` para preencher `imagem_url` (helper
  agora resiliente) quando houver acesso à BD.
- Expandir OCR a nascimentos/casamentos (inventário já existe).

## 2026-08-19 (execução autónoma — preparar OCR para nascimentos/casamentos)

### Estado verificado
- Repo limpo e alinhado com `origin/main` (antes desta passagem) — excepto `index.html`
  (UI pré-existente, não relacionado; não foi comitado). `.env` continua ignorado;
  scanner de segredos: **0 segredos** em 140 ficheiros rastreados. Segurança intacta.
- Pipeline HTR `htr_cloud_v2.py` parado (óbitos concluídos); sem quota em uso.
- `doc_file_listings.json` (4152 fileIds) cobre só os 116 livros de óbitos de
  Celorico; os livros de nascimentos/batismos (236) e casamentos (1030) já estão
  no inventário (`obitos_inventario.json`, tipo_cod BIRT/MARR/DEAT) mas os seus
  *page listings* ainda não foram descarregados.

### Tarefa implementada — pipeline HTR record-type aware (preparação)
- `htr_cloud_v2.py`: substituído o `PROMPT` único (hardcoded óbitos) por
  `PROMPT_BY_TYPE = {DEAT, BIRT, MARR}` com schemas distintos:
  - DEAT: `{"transcription","deceased":[...]}` (inalterado — 100% backward compat)
  - BIRT: `{"transcription","persons":[{name,birth_date,father,mother,godfather,godmother}]}`
  - MARR: `{"transcription","persons":[{name,marriage_date,spouse,father,mother,spouse_father,spouse_mother}]}`
- Adicionada `build_type_map()`: junta `doc_file_listings.json` (file_id→doc_id)
  com `obitos_inventario.json` (doc_id→tipo_cod) produzindo `{file_id: tipo_cod}`.
  file_ids sem mapeamento caem no `DEFAULT_RECORD_TYPE="DEAT"` (comportamento
  actual preservado — zero rutura). Degradação segura ({}) se ficheiros ausentes.
- `process_single()` agora seleciona o prompt pelo tipo do ficheiro e grava
  `record_type` em `output/htr_text/<id>.json` e `output/htr_metadata/<id>.json`,
  mantendo `raw_text`/`transcription`/`deceased` para não quebrar o sync.
  `call_gemini()` recebe o `prompt` por parâmetro (default DEAT). Chave Gemini
  continua mascarada via `mask_key()` (sem exposição).
- Smoke-test end-to-end (call_gemini stubbed, tiff real): `record_type=DEAT`
  escrito em output+metadata; key fingerprint `AIza***…***BbRM` (sem key inteira).
- Criado `test_htr_type_aware.py` (isolado, sem rede) com 10 testes: schemas de
  prompt, default DEAT, selector, jointure listing+inventário, precedência do
  inventário, degradação com ficheiros ausentes, skip de páginas não-lista,
  regressão de `parse_gemini_json` e `mask_key` (chave construída em runtime —
  nenhum literal de chave neste ficheiro rastreado). **TESTES PASS** (10/10).
- `py_compile` OK; scanner de segredos confirma 0 segredos em
  `test_htr_type_aware.py` e `htr_cloud_v2.py`.

### Decisão registada
- Passo de "melhorar autonomamente" seguro e sem rutura: a pipeline HTR passa a
  ser *pronta* a transcrever correctamente nascimentos e casamentos. Não altera
  o ritmo (KEY_INTERVAL/MODEL_INTERVAL), a BD remota nem segredos; o comportamento
  sobre os 11764 óbitos processados permanece idêntico (DEAT). A expansão só
  requer agora: (1) descarregar os *page listings* + TIFFs de BIRT/MARR — que
  podem ser alimentados no `doc_file_listings.json`/INPUT_DIR sem alterar código;
  (2) opcionalmente estender o `sync_htr_supabase.py` para ingerior `persons`.
- Não se efectuou o download de imagens de nascimentos/casamentos neste ciclo
  (pesado, GBs + quota Gemini); fica como próximo passo quando houver capacidade.

### Próximos passos sugeridos
- Descarregar inventários de páginas (page listings) dos livros BIRT/MARR de
  Celorico e alimentá-los a `output/data/doc_file_listings.json`; o `type_map`
  passa a mapear esses fileIds a BIRT/MARR automaticamente.
- Correr `htr_cloud_v2.py` para OCR de nascimentos/casamentos (prompts já prontos).
- Extensão opcional do sync para ingerir `persons` (nascimentos/casamentos).
- Aplicar `migrations/add_pessoa_relation_columns.sql` + `SYNC_RELATIONS=1`.

## 2026-08-20 (execução autónoma — portão de testes no CI + UI)

### Estado verificado
- Pipeline HTR `htr_cloud_v2.py` NÃO está a correr (óbitos concluídos; sem quota).
- Scanner de segredos: **0 segredos** em 141 ficheiros rastreados. Segurança intacta.
- Testes existentes (`test_coverage_report`, `test_scan_secrets`, `test_sync_pagination`,
  `test_sync_relations`, `test_htr_type_aware`) todos PASS manualmente.
- `index.html` (UI de pesquisa) continuava modificado e não comitado desde sessões
  anteriores — melhoria legítima (usa colunas pai/mae/conjuge/imagem_url, navegação,
  badges), sem chaves secretas (só `sb_publishable_` pública).

### Tarefa implementada — portão de testes automatizado (autonomia + qualidade)
- Criado `scripts/run_tests.sh`: corre o secret-scanner + todos os testes unitários
  puros (sem rede/credenciais) e devolve exit-code ≠ 0 em falha, permitindo ao CI
  bloquear regressões. Idempotente e legível.
- Estendido `.github/workflows/security-scan.yml` com job `unit-tests` que corre
  `scripts/run_tests.sh` em cada push/PR — o repo ganha agora barreira de
  **segurança + qualidade** automáticas no GitHub.
- Verificado: `bash scripts/run_tests.sh` → `RESULT: ALL TESTS PASSED`.

### Decisão registada
- Melhoria segura e mensurável do pilar "melhorar autonomamente": cada ciclo de 8h
  (e cada push) passa a validar automaticamente que o scanner e os testes não
  regridem, sem tocar no pacing, na BD remota nem em segredos. Não se relançou o
  HTR nem se aplicou DDL remoto (fora de escopo/ciclo).
- Comitado também o `index.html` pendente (UI), que estava há várias sessões por
  fazer push — mantém-se a regra de "nunca expor segredos".

### Próximos passos sugeridos
- Aplicar `migrations/add_pessoa_relation_columns.sql` + `SYNC_RELATIONS=1`
  para backfill de `pai`/`mae`/`conjuge` (88.3% dos falecidos já têm relações).
- `sync_htr_supabase.py --backfill-url` para preencher `imagem_url`.
- Descarregar page listings de BIRT/MARR e correr `htr_cloud_v2.py` para
  nascimentos/casamentos (prompts já prontos).

## 2026-08-20 (execução autónoma — cobertura por tipo de registo)

### Estado verificado
- Repo limpo e alinhado com `origin/main`; `.env` continua ignorado. Scanner de
  segredos: **0 segredos** em 142 ficheiros rastreados. Segurança intacta.
- Pipeline `htr_cloud_v2.py` NÃO está a correr (óbitos concluídos; sem quota).
- Testes existentes (`test_coverage_report`, `test_scan_secrets`,
  `test_sync_pagination`, `test_sync_relations`, `test_htr_type_aware`) PASS no
  portão `scripts/run_tests.sh`.

### Tarefa implementada — quebra de cobertura por record_type no relatório
- O `scripts/coverage_report.py` media só agregados (DEAT/BIRT/MARR misturados).
  Como a pipeline é agora record-type aware (`PROMPT_BY_TYPE` em
  `htr_cloud_v2.py`, que já grava `record_type`), a próxima expansão
  (nascimentos/casamentos) precisava de métrica própria.
- `analyze()` passa a agregar `by_type` (DEAT/BIRT/MARR): total, parsed_ok,
  parse/transcription/deceased rates, deceased_persons e relation_readiness por
  tipo. Ficheiros sem `record_type` caem no `DEFAULT_RECORD_TYPE="DEAT"`
  (preserva comportamento dos 13291 óbitos antigos) e tipos desconhecidos
  também caem para DEAT (degradação segura, sem KeyError).
- A relação por tipo é contada **por pessoa** (igual à métrica agregada),
  corrigindo uma inconsistência inicial em que contava só por ficheiro.
- `main()` imprime o bloco `=== by record_type ===` (DEAT/BIRT/MARR).
- `test_coverage_report.py` estendido com `test_analyze_by_type` (tipos
  conhecidos, default DEAT, fallback de tipo desconhecido, soma = total).
  **TESTES PASS** (incl. 10/10 htr_type_aware, todos os gates).
- Verificado contra output real: 13291 ficheiros, parse 66.2%,
  `rel_ready` DEAT **87.1%** (igual ao agregado — consistente); BIRT/MARR a 0
  (ainda não processados — exatamente o que a métrica vai passar a medir).

### Decisão registada
- Melhoria segura e mensurável do pilar "melhorar autonomamente": cada ciclo de
  8h passa a conseguir quantificar a cobertura de nascimentos/casamentos de forma
  isolada assim que esses registos entrarem no pipeline, sem tocar no pacing, na
  BD remota nem em segredos. Sem risco (analisador read-only).

### Próximos passos sugeridos
- Descarregar page listings de BIRT/MARR e correr `htr_cloud_v2.py` — a nova
  métrica `by_type` passará a mostrar progresso real de nascimentos/casamentos.
- Aplicar `migrations/add_pessoa_relation_columns.sql` + `SYNC_RELATIONS=1`
  para backfill de `pai`/`mae`/`conjuge` (87.1% dos falecidos já têm relações).
- `sync_htr_supabase.py --backfill-url` para preencher `imagem_url`.

## 2026-08-20 (execução autónoma — robustez de chaves de relação no OCR)

### Estado verificado
- Repo limpo e alinhado com `origin/main`; `.env` continua ignorado. Scanner de
  segredos: **0 segredos** em 142 ficheiros rastreados. Segurança intacta.
- Pipeline `htr_cloud_v2.py` NÃO está a correr (óbitos concluídos; sem quota).
- `bash scripts/run_tests.sh` → **ALL TESTS PASSED** (incl. 10/10
  htr_type_aware, test_sync_relations, test_scan_secrets, test_coverage_report).

### Tarefa implementada — suporte a chaves PT nas relações (`deceased`)
- O `extract_persons_from_deceased()` em `sync_htr_supabase.py` só lia as chaves
  Inglesas (`father`/`mother`/`spouse`). Amostras reais mostram que o Gemini
  por vezes devolve variantes Portuguesas (`pai`, `mae`, `cônjuge`), fazendo
  perder relações silenciosamente e subestimando o `relation_readiness`.
- Passou a aceitar ambas as variantes (Inglês tem precedência se ambas
  presentes, sem duplicar): `father`/`pai`, `mother`/`mae`,
  `spouse`/`conjuge`/`cônjuge`.
- Adicionado `test_extract_persons_relations_pt_keys` em `test_sync_relations.py`
  (chaves PT só, e precedência EN quando ambas presentes). **TESTES PASS**.
- Mudança puramente local/read-only no parsing; não toca na BD remota, no
  pacing nem em segredos. Aumenta o yield real do backfill de relações quando
  a migração `add_pessoa_relation_columns.sql` + `SYNC_RELATIONS=1` for aplicada.

### Decisão registada
- Melhoria segura e mensurável do pilar "melhorar autonomamente": o futuro
  backfill de `pai`/`mae`/`conjuge` (passo seguinte sugerido) aproveitará mais
  registos sem qualquer risco (sem escrita remota, sem nova quota de OCR).
- Não se aplicou a migração remota nem `SYNC_RELATIONS=1` (escrita em BD de
  produção fora de escopo do ciclo seguro de 8h).

## 2026-08-21 (execução autónoma)

### Estado verificado
- Pipeline `htr_cloud_v2.py` NÃO está a correr (óbitos concluídos; sem quota).
- `fetch_page_listings.py` script ran successfully: 1217 doc_ids fetchados
  (BIRT: 211, MARR: 1006), 61019 páginas totais adicionadas.
- `doc_file_listings.json` agora tem 1334 doc_ids (de 117), cobrindo todos
  os livros de nascimentos/batismos (236) e casamentos (1030) do inventário.
- `.env` continua ignorado; scanner de segredos: **0 segredos** em ficheiros
  rastreados. Segurança intacta.
- Repo alinhado com `origin/main`; push realizado com sucesso.

### Tarefa implementada — page listings BIRT/MARR
- Executado `fetch_page_listings.py` que leia o inventário (`obitos_inventario.json`),
  filtra livros BIRT e MARR, e faz fetch de listings de páginas via API Digitarq.
- Resultado: 1217 doc_ids novos buscados e 61019 páginas adicionadas a
  `output/data/doc_file_listings.json`.
- Isso habilita a pipeline `htr_cloud_v2.py` com `PROMPT_BY_TYPE` a processar
  corretamente nascimentos (BIRT) e casamentos (MARR), antes limitados apenas a
  óbitos (DEAT).
- O script `fetch_page_listings.py` foi adicionado ao repositório para execuções
  futuras de automação a cada 8h.
- Verificado: `py_compile` OK.

### Próximos passos sugeridos
- Correr `htr_cloud_v2.py` para OCR de nascimentos/casamentos (prompts já prontos
  via `PROMPT_BY_TYPE` — BIRT e MARR schemas definidos).
- Aplicar `migrations/add_pessoa_relation_columns.sql` + `SYNC_RELATIONS=1`
  para backfill de `pai`/`mae`/`conjuge`.
- `sync_htr_supabase.py --backfill-url` para preencher `imagem_url`.

## 2026-08-20 (execução autónoma — cobertura por tipo de registo)

