# Árvore Genealógica de Portugal

Pesquisa e exploração dos **livros paroquiais de Celorico da Beira** (batismos, casamentos e óbitos, 1654–1911) com transcrição automática de manuscritos e árvore genealógica interativa.

🌐 **Site:** https://genealogia-portugal.vercel.app

## Estado atual
- **Óbitos:** 25/25 freguesias completas (~35 000 registos)
- **Batismos:** em curso (13/25 freguesias sincronizadas)
- **Casamentos:** após os batismos

## Como funciona
1. **HTR** (`htr_cloud_v2.py`) — descarrega páginas do [Digitarq](https://digitarq.arquivos.pt), transcreve com a API Gemini, grava JSON em `output/htr_text/`
2. **Sync** (`sync_htr_supabase.py`) — envia os registos para o Supabase (tabela `pessoas`)
3. **Web** (`api/index.py` + `templates/`) — Flask no Vercel: pesquisa, batismos, casamentos, árvore D3, mapa, cobertura

## Estrutura
```
api/            Flask (rotas + API REST sobre o Supabase)
templates/      Páginas HTML (pesquisa, batismos, árvore, mapa, …)
index.html      Página inicial
scripts/        Testes, scanners de segredos, utilitários (get_images, gen_arquivo_refs, …)
tests/          Testes unitários (corridos por scripts/run_tests.sh)
migrations/     SQL do Supabase (tabela pessoas + RLS)
tools/archive/  Scripts exploratórios antigos (histórico, fora de uso)
docs/           PROGRESS.md (diário do bot), planos e documentação
```

## Desenvolvimento local
```bash
git clone https://github.com/khwx/genealogia-portugal.git
cd genealogia-portugal
pip install -r requirements.txt
cp .env.example .env   # preencher com valores próprios (Supabase + Gemini)
bash scripts/run_tests.sh   # tem de dar ALL TESTS PASSED
```

Queres ajudar? Lê **[CONTRIBUTING.md](CONTRIBUTING.md)** — cada colaborador usa a sua própria base de dados gratuita; ninguém precisa de acesso à nossa.

## Segurança
- `.env` nunca é comitado (o CI bloqueia PRs com segredos)
- Supabase com Row Level Security: leitura pública, escrita só com chave de serviço
- Dados 100% históricos (arquivos públicos) — sem dados de pessoas vivas
