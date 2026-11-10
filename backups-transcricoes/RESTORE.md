# Backup das transcrições HTR

Seguro off-site: se a BD e o PC falharem, restaura-se tudo daqui.

## Conteúdo
- `celorico-{marr,birt,deat,legacy}.tar.gz` — 80 650 ficheiros JSON (`output/htr_text/`),
  um por página (`<file_id>.json` com `transcription` + estrutura `persons`/`baptized`/`deceased`)
- `trancoso-{marr,birt}.tar.gz` — transcrições Trancoso (~26.5k MARR + ~16k BIRT parcial)
- `inventarios/` — `celorico_casamentos_batismos.json` (livros BIRT/MARR),
  `trancoso_inventario.json` (+ Pinhel quando existir)

## Restaurar
```bash
# Celorico
tar -xzf backups-transcricoes/celorico-marr.tar.gz
tar -xzf backups-transcricoes/celorico-birt.tar.gz
tar -xzf backups-transcricoes/celorico-deat.tar.gz
tar -xzf backups-transcricoes/celorico-legacy.tar.gz
# Trancoso
tar -xzf backups-transcricoes/trancoso-marr.tar.gz -C output/htr_text_tcs/
tar -xzf backups-transcricoes/trancoso-birt.tar.gz -C output/htr_text_tcs/
# (extrai para output/htr_text/ ou output/htr_text_tcs/) e depois:
python3 sync_htr_supabase.py
```

## Atualizar o backup
Após rondas grandes de transcrição, regenerar os tarballs e commitar
(ves o tamanho com `du -sh`). Não commitar `output/htr_text/` em bruto
(522MB / 80k ficheiros) — os tarballs chegam.
