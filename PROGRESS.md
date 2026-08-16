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
