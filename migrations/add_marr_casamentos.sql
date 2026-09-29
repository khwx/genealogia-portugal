-- Migration: MARR rich fields (casamentos)
-- Adiciona colunas para os detalhes de casamento extraídos pelo HTR
-- (dispensa canónica, testemunhas, legitimação de filhos). As restantes
-- (data_casamento, estado_civil, idade, profissao, naturalidade,
-- numero_assento, assinatura, pai/mae/conjuge, texto_original) já existem.
-- Idempotente: pode correr várias vezes.

alter table public.pessoas
    add column if not exists dispensa text,
    add column if not exists testemunhas text,
    add column if not exists legitimacao text;

create index if not exists idx_pessoas_dispensa on public.pessoas (dispensa);
create index if not exists idx_pessoas_testemunhas on public.pessoas (testemunhas);
create index if not exists idx_pessoas_legitimacao on public.pessoas (legitimacao);