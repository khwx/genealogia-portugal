# Contribuir para genealogia-portugal

## O projeto
Digitalização e pesquisa dos livros paroquiais de Celorico da Beira (óbitos, batismos, casamentos) com transcrição automática (HTR via API Gemini) e apresentação web.

## Arquitetura (3 partes)
1. **HTR local** (`htr_cloud_v2.py`) — descarrega imagens do Digitarq, transcreve com a API Gemini, grava JSON em `output/htr_text/`
2. **Sync** (`sync_htr_supabase.py`) — envia os JSON para o Supabase (tabela `pessoas`)
3. **Web** (`api/index.py` + `templates/` + `index.html`) — Flask no Vercel, lê do Supabase

## Como contribuir
1. Fork → branch (`feat/...` ou `fix/...`) → Pull Request contra `main`
2. Correr `bash scripts/run_tests.sh` antes do PR — tem de dar `ALL TESTS PASSED`
3. PRs pequenos e focados; sem segredos (ver abaixo)

## Ambiente próprio (cada um na sua BD)
Não precisas de acesso à nossa base de dados — e é melhor assim:
- Cria um projeto **gratuito** em [supabase.com](https://supabase.com) e aplica os SQL em `migrations/` (criam a tabela `pessoas` + RLS)
- Arranja uma chave **gratuita** em [Google AI Studio](https://aistudio.google.com) para o HTR (podes pôr mais do que uma, separadas por vírgula, para maior quota)
- Copia `.env.example` para `.env` e preenche com os **teus** valores
- Para leitura/exploração podes usar diretamente a nossa BD pública (só leitura); para testar escrita e sync usa a tua

## Regras de segurança
- **Nunca** comites `.env` nem chaves (o CI bloqueia o PR se detetar segredos)
- A BD principal tem Row Level Security: leitura pública, escrita só com chave de serviço (que nunca sai do servidor)
- Não partilhes chaves por issues, PRs ou chat — cada um usa as suas

## Ideias por onde começar
- Melhorias de UI nos templates (`batismos.html`, `family_tree.html`, …)
- Novos testes em `test_*.py`
- Documentação e traduções
