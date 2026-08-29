-- Migration: add rich detail columns for death records (NotebookLM-level)
-- Adds age, cause of death, naturalidade/morada and assento number so the
-- web app can show the same detail that NotebookLM extracts from a page
-- (ex: "assento n.º 26, morte repentina, 60 anos, natural da Rapa").
-- All columns are additive, nullable and idempotent; nothing is dropped.

alter table public.pessoas
    add column if not exists idade integer,
    add column if not exists causa_morte text,
    add column if not exists naturalidade text,
    add column if not exists numero_assento text;

create index if not exists idx_pessoas_idade on public.pessoas (idade);
create index if not exists idx_pessoas_numero_assento on public.pessoas (numero_assento);
