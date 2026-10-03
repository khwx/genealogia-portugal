# Expansão: Trancoso (depois Pinhel)

> Ordem: acabar Trancoso 100% antes de começar Pinhel.

## Lista do necessário — Trancoso

- [x] **Backup Celorico no GitHub** — `backups-transcricoes/` no próprio repo
      (tarballs por tipo + inventários + RESTORE.md; ~38MB)
- [x] **1. Inventário de livros** — `output/trancoso_inventario.json` ✅ 2026-10-03
      (41 paróquias, 4 605 livros: BIRT 1 597, MARR 1 501, DEAT 1 507)
- [x] **2. Page listings** — `output/data/doc_file_listings_tcs.json` ✅ 2026-10-03
      (**98 685 páginas**: BIRT 40 548, MARR 26 475, DEAT 31 662)
- [ ] **3. Transcrição HTR** — A DECORRER (MARR primeiro: `output/workers/marr_tcs.py` →
      `output/htr_text_tcs/`, guardian `scripts/watch_htr_tcs.sh`; começou Aldeia Nova)
- [ ] **4. Migração/schema** — nenhuma (tabela `pessoas` já tem `concelho`; usar `concelho='Trancoso'`)
- [ ] **5. Sync Supabase** — `sync_htr_supabase.py` com mapeamento fid→freguesia de Trancoso
      (estender `build_file_to_freguesia` + `INPUT_DIR` ou pasta por concelho)
- [ ] **6. Frontend** — filtro por concelho (`/`, `/batismos`, `/casamentos`, `/mapa`); stats por concelho
- [ ] **7. Backup Trancoso no GitHub** — tarballs `trancoso-*.tar.gz` em `backups-transcricoes/`
- [ ] **8. Verificação** — cobertura por freguesia × tipo; `?concelho=Trancoso` no ar

## Depois: Pinhel (`pnh`, `output/pinhel_inventario.json`) — mesmos 8 passos.

## Notas
- Nunca correr 2 syncs em simultâneo (duplica linhas; `db_synced` só protege no arranque).
- Transcrições ficam sempre em `output/htr_text/` (Celorico) e pasta própria por concelho novo,
  com backup em tarballs no GitHub antes de qualquer migração destrutiva.
