# Santa Clara

Pagina inicial adaptada da referencia https://lustosa.com.br/, capturada em
20/10/2026. O layout utiliza os componentes e a fonte local da referencia,
com marca, conteudo e interacoes do Santa Clara.

## Executar

```powershell
python preview.py --port 5174
```

Abra http://localhost:5174/.

O painel de métricas fica em http://localhost:5174/admin/. O gráfico de horários
usa a hora de Brasília. Navegadores estimados são identificadores locais de 30 dias.
Sessões são agrupadas por aba durante a navegação, com janela de 30 minutos.
O painel funciona com a tabela existente. Em bases maiores, aplique
`supabase_dashboard_metrics.sql` para agregar visualizações no banco.

Para habilitar cidade ou bairro, configure `SANTA_CLARA_GEO_PROXY_TOKEN` no servidor
e no proxy confiável. O proxy deve remover os cabeçalhos de geografia enviados pelo
visitante e preencher `X-Santa-Clara-Geo-Token` e, conforme o provedor, os campos
`X-Santa-Clara-City` e `X-Santa-Clara-Neighborhood` com valores URL-encoded.
Sem informação do provedor, o painel mostra a localização como não identificada.

## Pop-up do e-book

O componente `EbookPopup` abre ao carregar a página inicial, respeitando a
frequência de exibição. O preview local mostra o layout mesmo sem o link.
Para ativar o pop-up com o botão funcional no site público, preencha
`ebookUrl` em `content/business.json` e no arquivo servido `site-config.js`
com o caminho público do PDF ou com a URL HTTPS oficial. Se o PDF ficar neste
projeto, coloque-o em `assets/` e use um caminho iniciado por `/assets/`.
A capa já está em `assets/images/ebook-santa-clara.png`.

## Arquivos ativos

- `index.html`: pagina gerada.
- `assets/reference.css`: folha de estilos capturada, com fontes locais.
- `santa-clara.css`: cabecalho, rodape e ajustes responsivos.
- `santa-clara.js`: carrossel manual, busca, abas, orcamento e dialogs.
- `site-config.js`: integracoes e dados comerciais confirmados.
- `logo.png` e `hero.png`: imagens previamente existentes no projeto.
- `assets/atendimento.png`: imagem ilustrativa do banner.

A pagina anterior esta preservada em `backups/santa-clara-before-lustosa.html`.
Arquivos antigos de outras referencias nao fazem parte da pagina ativa nem
sao publicados pelo servidor `preview.py`.

## Integracoes pendentes

Preencher `whatsapp` (somente numeros, com pais e DDD), `resultsUrl`,
`address` e `mapsUrl` em `site-config.js` somente com dados confirmados.
Sem configuracao, os botoes exibem orientacoes honestas, sem enviar pacientes
a contatos ou portais de outro laboratorio.

O orcamento e apenas uma selecao temporaria de exames, nao um checkout.
Nao existe coleta de credenciais, pagamento, armazenamento de exames ou backend
de agendamento. O unico preco informado e o ECG particular de R$ 50 fornecido
no briefing. Horario 06:30-16:00; dias e endereco precisam de confirmacao.

## Referencia visual

Foram preservados fonte, cores de interface, largura de conteudo de 1094px,
cabecalho de 64px, banner de 400px no desktop/450px no celular, faixa de aviso,
tres acessos rapidos, busca/abas/cartoes de exames e grade de seis servicos.
Marca, banner principal, textos, catalogo e contatos foram adaptados.
Promocoes, certificacoes, responsaveis tecnicos e precos do Lustosa nao foram
atribuidos ao Santa Clara. Imagens de servicos e fontes estao em `assets/`.

`tools/build_santa_clara.py` registra a transformacao da captura. Sua execucao
depende da captura local e das dependencias em `tools/vendor`; nao e necessaria
para executar o site.
