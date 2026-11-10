# Publicacao e acompanhamento

## Implementado

- Páginas estáticas de exames, contato, coleta domiciliar e blog, com títulos e descrições próprios.
- Conteudo de exames com fontes, navegacao interna e contexto de Aracuai.
- Endereco, telefone, links sociais e rotas confirmados pelo responsavel.
- WhatsApp direto, inclusive sem JavaScript; mensagem sugerida, nunca enviada automaticamente.
- Atalhos para exames, localizacao e resultados; perguntas frequentes visiveis.
- Rotas de Itinga, Coronel Murta, Virgem da Lapa e Francisco Badaró até a unidade de Araçuaí.
- Dados estruturados MedicalClinic e MedicalWebPage, sem notas ou avaliacoes inventadas.
- Domínio oficial configurado em HTTPS, URLs canônicas, `og:url` e sitemap das páginas públicas.
- `robots.txt` com acesso às páginas públicas para buscadores, incluindo OAI-SearchBot. O painel e os endpoints ficam fora do sitemap e do rastreamento.
- `llms.txt` com links para páginas institucionais, exames, coleta domiciliar e blog. É um índice opcional para ferramentas que leem esse formato.

## Antes de publicar

1. Rodar `python tools/prepare_seo.py` ao adicionar ou remover páginas públicas. O comando usa o domínio HTTPS de `content/business.json` para atualizar canônicas, metadados, sitemap e `llms.txt`, preservando conteúdo e layout.
2. Confirmar dias de funcionamento e portal de resultados. O portal ainda nao esta integrado.
3. Solicitar revisao dos textos de saude ao profissional responsavel pelo laboratorio. Registrar responsavel e data somente depois da revisao real; o conteudo atual nao afirma revisao clinica.
4. Publicar as rotas públicas em hospedagem HTTPS, redirecionar HTTP para HTTPS e confirmar resposta 200 nas páginas, no sitemap e no robots.txt. O `preview.py` envia `X-Robots-Tag: noindex, nofollow` e serve apenas para testes locais. Exponha somente os arquivos públicos na hospedagem e mantenha o painel e as APIs protegidos pelo servidor.
5. Verificar o domínio no Google Search Console e enviar `/sitemap.xml`. Conferir indexação, versão mobile, dados estruturados, inclusão nos recursos de IA da Pesquisa e Core Web Vitals na URL pública. Enviar o sitemap também ao Bing Webmaster Tools.
6. Verificar e atualizar o Perfil da Empresa no Google com a categoria correta, endereço, telefone, horários confirmados, URL e fotos reais. O cadastro do CNES e o site mostram telefone, bairro e horário diferentes. Confirme esses dados com o laboratório antes de sincronizar os cadastros. Essas contas não foram acessadas nem alteradas.

## Medir resultados reais

Comparar impressões, cliques e consultas locais no Search Console. Usar o painel do site para acompanhar os cliques no WhatsApp e os cadastros do e-book. Registrar com a equipe quantos contatos vindos do site viraram atendimentos.

Nao ha garantia de primeira posicao, prazo de indexacao ou volume de conversoes. Nao criar paginas repetidas para cidades onde o laboratorio nao atende nem publicar depoimentos ficticios.

Referencias oficiais:
- https://developers.google.com/search/docs/fundamentals/creating-helpful-content
- https://developers.google.com/search/docs/appearance/structured-data/local-business
- https://developers.google.com/search/docs/crawling-indexing/sitemaps/build-sitemap
- https://developers.google.com/search/docs/appearance/ai-features
- https://developers.openai.com/api/docs/bots
- https://llmstxt.org/
- https://support.google.com/business/answer/7091?hl=pt-BR
- https://cnes2.datasus.gov.br/Mod_Conjunto.asp?VCo_Unidade=3103402134284
