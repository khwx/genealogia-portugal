# Expansão: Trancoso (depois Pinhel)

> Ordem: acabar Trancoso 100% antes de começar Pinhel.

## Lista do necessário — Trancoso

- [x] **Backup Celorico no GitHub** — repo `genealogia-transcricoes` (tarballs por tipo + inventários)
- [ ] **1. Inventário de livros** — `output/trancoso_inventario.json` (43 paróquias `tcs01–tcs43`,
      tabelas BIRT/MARR/DEAT do Tombo.pt; só leitura, sem chaves) → script `scripts/build_inventario_tcs.py`
- [ ] **2. Page listings** — `output/data/doc_file_listings_tcs.json` (fids por livro, via API Digitarq;
      reutilizar `scripts/fetch_page_listings.py` com o inventário novo)
- [ ] **3. Transcrição HTR** — workers `birt/marr/deat` com `FREGUESIAS` de Trancoso (~6s/pág;
      guardian `watch_htr` adaptado ou novo por concelho)
- [ ] **4. Migração/schema** — nenhuma (tabela `pessoas` já tem `concelho`; usar `concelho='Trancoso'`)
- [ ] **5. Sync Supabase** — `sync_htr_supabase.py` com mapeamento fid→freguesia de Trancoso
      (estender `build_file_to_freguesia` + `INPUT_DIR` ou pasta por concelho)
- [ ] **6. Frontend** — filtro por concelho (`/`, `/batismos`, `/casamentos`, `/mapa`); stats por concelho
- [ ] **7. Backup Trancoso no GitHub** — tarballs `trancoso-*.tar.gz` no repo `genealogia-transcricoes`
- [ ] **8. Verificação** — cobertura por freguesia × tipo; `?concelho=Trancoso` no ar

## Depois: Pinhel (`pnh`, `output/pinhel_inventario.json`) — mesmos 8 passos.

## Notas
- Nunca correr 2 syncs em simultâneo (duplica linhas; `db_synced` só protege no arranque).
- Transcrições ficam sempre em `output/htr_text/` (Celorico) e pasta própria por concelho novo,
  com backup em tarballs no GitHub antes de qualquer migração destrutiva.
