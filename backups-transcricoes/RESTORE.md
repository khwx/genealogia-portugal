# Backup das transcrições HTR

Seguro off-site: se a BD e o PC falharem, restaura-se tudo daqui.

## Conteúdo
- `celorico-{marr,birt,deat,legacy}.tar.gz` — 80 650 ficheiros JSON (`output/htr_text/`),
  um por página (`<file_id>.json` com `transcription` + estrutura `persons`/`baptized`/`deceased`)
- `inventarios/` — `celorico_casamentos_batismos.json` (livros BIRT/MARR),
  `trancoso_inventario.json` (+ Pinhel quando existir)

## Restaurar
```bash
tar -xzf backups-transcricoes/celorico-marr.tar.gz
tar -xzf backups-transcricoes/celorico-birt.tar.gz
tar -xzf backups-transcricoes/celorico-deat.tar.gz
tar -xzf backups-transcricoes/celorico-legacy.tar.gz
# (extrai para output/htr_text/) e depois:
python3 sync_htr_supabase.py
```

## Atualizar o backup
Após rondas grandes de transcrição, regenerar os tarballs e commitar
(ves o tamanho com `du -sh`). Não commitar `output/htr_text/` em bruto
(522MB / 80k ficheiros) — os tarballs (~38MB) chegam.
