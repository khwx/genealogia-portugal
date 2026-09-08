-- Migration: add padrinhos + transcrição HTR aos batismos
-- Os campos godfather/godmother/texto_original são extraídos pelo HTR
-- mas não tinham coluna no Supabase (eram descartados no sync).
-- Idempotente, só adiciona colunas. Correr no Supabase SQL Editor.

alter table public.pessoas
    add column if not exists godfather text,
    add column if not exists godmother text,
    add column if not exists texto_original text;

-- Índices para pesquisa genealógica por padrinhos
create index if not exists idx_pessoas_godfather on public.pessoas (godfather);
create index if not exists idx_pessoas_godmother on public.pessoas (godmother);
