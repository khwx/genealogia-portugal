-- Migration: add record-type column to the `pessoas` table (Fase 3)
-- Prepares the schema to hold marriages (MARR) and births (BIRT) alongside
-- the existing death records (DEAT), so the web app can later filter and
-- render each event type. The date columns data_nascimento and
-- data_casamento already exist; only tipo_registo is added here.
--
-- Apply once in the Supabase SQL Editor (or via the service-role client).
-- Existing rows are all death records, so they default to 'DEAT'.
-- Columns are nullable-safe and additive; nothing is dropped.

alter table public.pessoas
    add column if not exists tipo_registo text not null default 'DEAT';

-- Speed up type-based filtering used by the web search/map.
create index if not exists idx_pessoas_tipo_registo
    on public.pessoas (tipo_registo);

-- Backfill: rows inserted before this migration had no tipo_registo, but
-- the project only ingested death (obito) records so far.
update public.pessoas
    set tipo_registo = 'DEAT'
    where tipo_registo is null;
