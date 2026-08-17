# PROGRESS.md — Árvore Genealógica de Portugal (óbitos)

Registo de execuções e decisões do Bot. Atualizado autonomousamente a cada 8h.

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
