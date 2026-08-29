-- Migration: add assinatura (priest signature) for complete record
alter table public.pessoas add column if not exists assinatura text;
