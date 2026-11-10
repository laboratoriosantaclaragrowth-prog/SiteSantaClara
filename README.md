# Laboratório Santa Clara

Site institucional do Laboratório Santa Clara em Araçuaí (MG), com guia de exames, página de coleta domiciliar, blog, captação do e-book e painel de métricas.

## Rodar localmente

Com Python 3.10 ou mais recente, rode o comando abaixo e abra [o preview local](http://localhost:5174/).

```powershell
python preview.py --port 5174
```

O painel fica em `/admin/`. Para ativá-lo, defina `SANTA_CLARA_ADMIN_PASSWORD` no `.env` da raiz. O usuário do painel é `admin`.

Para usar o Supabase, defina `SUPABASE_URL` e `SUPABASE_SECRET_KEY` no `.env` do servidor e aplique `supabase_tracking.sql`. Sem essas variáveis, o preview armazena os registros em um banco SQLite local. `supabase_dashboard_metrics.sql` adiciona a agregação no banco. A variável `SANTA_CLARA_GEO_PROXY_TOKEN` é opcional e exige um proxy confiável configurado.

Para testar a entrega do e-book, copie o PDF para `assets/ebook-santa-clara.pdf` no ambiente em que o servidor roda. O arquivo fica fora do Git para preservar a entrega pelo formulário.

## Publicar na Vercel

Importe a raiz do repositório. O `vercel.json` publica as páginas e os assets e liga as rotas de cadastro, métricas e painel à função Python.

Em **Settings → Environment Variables**, defina `SUPABASE_URL` e `SUPABASE_SECRET_KEY` para o ambiente **Production**. Para acessar `/admin/`, defina também `SANTA_CLARA_ADMIN_PASSWORD`. Faça um novo deploy após configurar as variáveis. A função usa o Supabase para salvar os cadastros em produção.

No Supabase, aplique `supabase_tracking.sql` e mantenha `ebook-santa-clara.pdf` no bucket privado `santa-clara-privado`. Para usar outro caminho, defina `SANTA_CLARA_EBOOK_STORAGE_OBJECT` como `bucket/caminho/do-arquivo.pdf` na Vercel. Após salvar o cadastro, o formulário abre o PDF pelo endereço `/ebook` do próprio site. O PDF precisa ter até 4,5 MB para ser entregue pela função da Vercel.

## Verificar o projeto

```powershell
python -m pip install beautifulsoup4
python -m unittest discover -s tests
```

Para atualizar o sitemap, as URLs canônicas e o `llms.txt` depois de alterar as páginas públicas, rode `python tools/prepare_seo.py`. As orientações de hospedagem e acompanhamento estão em `SEO-PUBLICACAO.md`.
