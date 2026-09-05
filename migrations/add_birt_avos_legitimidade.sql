-- Migration: add BIRT rich fields (4 avós, legitimidade, naturalidade dos pais)
-- Para árvore genealógica 3 gerações a partir de batismos
-- Idempotente, só adiciona colunas

alter table public.pessoas
    add column if not exists avo_paterno text,
    add column if not exists avo_paterna text,
    add column if not exists avo_materno text,
    add column if not exists avo_materna text,
    add column if not exists legitimidade text,
    add column if not exists naturalidade_pai text,
    add column if not exists naturalidade_mae text;

-- Índices para pesquisa genealógica
create index if not exists idx_pessoas_avo_paterno on public.pessoas (avo_paterno);
create index if not exists idx_pessoas_avo_materno on public.pessoas (avo_materno);
create index if not exists idx_pessoas_legitimidade on public.pessoas (legitimidade);
