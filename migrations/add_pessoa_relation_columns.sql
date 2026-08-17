-- Migration: add relation columns to the `pessoas` table
-- Applied to Supabase (SQL Editor) once the structured `deceased` relations
-- (father/mother/spouse) from Gemini OCR should be persisted.
--
-- After applying, run:
--   SYNC_RELATIONS=1 python3 sync_htr_supabase.py
-- to backfill pai/mae/conjuge on new syncs.
--
-- Columns are nullable text; existing rows are untouched.

alter table public.pessoas
    add column if not exists pai text,
    add column if not exists mae text,
    add column if not exists conjuge text;

-- Optional: indexes to speed up relational lookups (not required).
-- create index if not exists idx_pessoas_pai on public.pessoas (pai);
-- create index if not exists idx_pessoas_mae on public.pessoas (mae);
-- create index if not exists idx_pessoas_conjuge on public.pessoas (conjuge);
