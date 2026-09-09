-- Migration: fechar escrita anónima na tabela pessoas
-- PROBLEMA: a publishable key (visível no JS do site) permitia INSERT/UPDATE/DELETE.
-- Qualquer pessoa (ex.: quem fez fork) podia escrever/apagar dados ou gastar quota.
-- CORREÇÃO: RLS ligado + leitura pública, escrita só com a SECRET key.
--
-- PASSOS (Supabase Dashboard → SQL Editor → Run):
--   1. Correr este ficheiro.
--   2. Em Project Settings → API, copiar a "Secret key" (sb_secret_...).
--   3. No servidor/local: export SUPABASE_SECRET_KEY="sb_secret_..." (e no Vercel,
--      adicionar como env var se o backend precisar de escrever).
-- O sync local (sync_htr_supabase.py) já prefere SUPABASE_SECRET_KEY.
--
-- Idempotente: pode correr várias vezes.

alter table public.pessoas enable row level security;

drop policy if exists "Leitura publica" on public.pessoas;
create policy "Leitura publica"
    on public.pessoas for select
    using (true);

-- Sem policies de insert/update/delete para anon/authenticated:
-- só a service_role (SECRET key, bypassa RLS) consegue escrever.
-- Opcional: permitir validação comunitária (UPDATE de `validado`/`qualidade`)
-- só em linhas ainda por validar, descommentar se o /validar precisar:
/*
drop policy if exists "Validacao comunitaria" on public.pessoas;
create policy "Validacao comunitaria"
    on public.pessoas for update
    using (validado is distinct from true)
    with check (validado is distinct from true);
*/
