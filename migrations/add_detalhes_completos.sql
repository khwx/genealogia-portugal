-- Migration: complete rich details for NotebookLM-level presentation
-- Adds hora, profissao, estado civil, sacramentos, testamento and burial place.
-- Additive, idempotent, no drops.

alter table public.pessoas
    add column if not exists hora_obito text,
    add column if not exists profissao text,
    add column if not exists estado_civil text,
    add column if not exists sacramentos text,
    add column if not exists testamento text,
    add column if not exists local_sepultamento text;
