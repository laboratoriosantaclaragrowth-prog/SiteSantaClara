"""Generate crawlable informational pages from the existing visual template."""
import copy
import json
from html import escape
from pathlib import Path
from urllib.parse import urlsplit, urlencode
from xml.etree.ElementTree import Element, SubElement, tostring

from bs4 import BeautifulSoup


def build_informational_site(root, page):
    business = json.loads((root / 'content/business.json').read_text(encoding='utf-8'))
    exams = json.loads((root / 'content/exams.json').read_text(encoding='utf-8'))
    parse = lambda value: BeautifulSoup(value, 'html.parser')
    base = business['siteUrl'].rstrip('/')
    if base and (urlsplit(base).scheme != 'https' or not urlsplit(base).netloc or urlsplit(base).path):
        raise ValueError('siteUrl must be the confirmed HTTPS origin without a path')
    e = escape

    def contact_cta(origin='atendimento', label='Falar com a equipe'):
        if business['whatsapp'].isdigit() and len(business['whatsapp']) in (12, 13):
            return f'<button class="site-button primary" data-action="agendar" data-contact-origin="{e(origin, quote=True)}">{e(label)}</button>'
        if business['phone']:
            return f'<a class="site-button primary" href="tel:{e(business["phone"], quote=True)}">Ligar para o laboratório</a>'
        return '<button class="site-button primary" data-action="agendar">Consultar atendimento</button>'

    def location():
        address = e(business['address']) if business['address'] else 'Endereço completo: confirme com a recepção antes de se deslocar.'
        map_url = business['mapsUrl']
        route = (f'<a class="site-button primary" href="{e(map_url, quote=True)}" target="_blank" rel="noopener noreferrer">Como chegar</a>'
                 if urlsplit(map_url).scheme == 'https' else '<button class="site-button primary" data-action="localizacao-pendente">Como chegar</button>')
        embed_url = business['mapEmbedUrl']
        valid_map = urlsplit(embed_url).scheme == 'https' and urlsplit(embed_url).hostname in {'www.google.com', 'maps.google.com'} and urlsplit(embed_url).path.startswith('/maps/embed')
        media = (f'<div class="location-map location-map-preview"><strong class="location-map-title">Localização no mapa</strong><p>Ao abrir o mapa, seu navegador se conecta ao Google Maps.</p><button type="button" class="site-button primary" data-action="carregar-mapa" data-map-src="{e(embed_url, quote=True)}">Ver no mapa</button></div>'
                 if valid_map else '<div class="clinic-planet"><div class="planet-orbit"><img class="planet-image" src="/assets/planetinha_santaclara.png" alt="Vista panorâmica do Laboratório Santa Clara em formato de planetinha" width="1280" height="1280" loading="lazy"></div><button class="planet-toggle" type="button" data-action="planet-toggle" aria-pressed="false">Pausar rotação</button></div><p class="location-caption">Mapa disponível após confirmação do endereço do laboratório.</p>')
        return f'''<section class="location-section" id="onde-estamos" aria-labelledby="location-title"><div class="info-container location-layout"><div><p class="section-kicker">Santa Clara em Araçuaí</p><h2 id="location-title">Onde estamos</h2><p>Encontre o laboratório e consulte as informações para sua visita.</p><dl class="location-facts"><div><dt>Localização</dt><dd>{e(business['city'])}<br>{address}</dd></div><div><dt>Horário de atendimento</dt><dd>{e(business['hours'])}<br><span>Confirme os dias de funcionamento com a equipe.</span></dd></div></dl><div class="info-actions">{route}<button class="site-button outline" data-action="agendar">Falar com a equipe</button></div></div><div class="location-media">{media}</div></div></section>'''

    def exam_cards():
        return ''.join(f'''<article class="guide-card"><p class="exam-category">{e(exam['category'])}</p><h3><a href="/exames/{exam['slug']}/">{e(exam['name'])}</a></h3><p>{e(exam['summary'])}</p><a class="guide-link" href="/exames/{exam['slug']}/" aria-label="Saiba mais sobre {e(exam['name'], quote=True)}">Saiba mais <span aria-hidden="true">→</span></a></article>''' for exam in exams)

    # Remove the commercial surface, including header and footer entry points.
    for control in page.select('[data-action="orcamento"]'):
        control.decompose()
    page.select_one('script[src="/santa-clara.js"]')['src'] = '/informational.js'
    for link in page.select('[data-action="ecg"]'):
        del link['data-action']
        link['href'] = '/exames/eletrocardiograma/'
    for link in page.select('[data-action="unidade"]'):
        del link['data-action']
        link['href'] = '/#onde-estamos'
    for link in page.select('[data-action="preparo"]'):
        del link['data-action']
        link['href'] = '/#orientacoes'
    for link in page.select('[href="#exames"]'):
        link['href'] = '/exames/'
        if link.get_text(strip=True) == 'Buscar exames':
            link.string = 'Guia de exames'
    for link in page.select('[href="#servicos"]'):
        link['href'] = '/#servicos'
    for link in page.select('[data-action="agendar"]'):
        if link.get_text(strip=True) in {'Agendar', 'Agendar exames'}:
            link.string = 'Fale conosco'
    for link in page.select('[href="#inicio"]'):
        link['href'] = '/#inicio'
    hero_titles = page.select('.site-slide h2')
    hero_titles[0].name = 'h1'
    hero_titles[0].string = 'Laboratório Santa Clara em Araçuaí'
    hero_titles[1].find_next_sibling('p').string = 'Conheça o ECG e consulte as orientações para seu atendimento.'
    quick = page.select('#acessos h2')
    quick[1].string = 'Fale com a equipe'
    quick[2].string = 'Onde estamos'
    services = page.select('#servicos .grid > div')
    services[1].p.string = 'Conheça o exame e as orientações de atendimento.'
    services[2].p.string = 'Tire suas dúvidas sobre o atendimento no laboratório.'
    products = page.select_one('#exames')
    products.replace_with(parse(f'''<section class="exam-guide info-container" id="exames" aria-labelledby="guide-title"><p class="section-kicker">Informação para cuidar de você</p><h2 id="guide-title">Exames realizados no Santa Clara</h2><p class="section-intro">Conheça os exames, entenda para que servem e confira o que perguntar à equipe antes do atendimento.</p><div class="guide-grid">{exam_cards()}</div><p class="guide-contact">Não encontrou o exame do seu pedido? <button data-action="agendar">Consulte nossa equipe.</button></p></section>'''))
    page.select_one('#servicos').insert_before(parse(location()))
    page.select_one('#servicos').insert_after(parse('''<section class="preparation-section info-container" id="orientacoes"><p class="section-kicker">Antes da sua visita</p><h2>Orientações para realizar seus exames</h2><div class="preparation-grid"><div><h3>Confirme o preparo</h3><p>Apresente o seu pedido à equipe. As orientações dependem dos exames solicitados e das condições do atendimento.</p></div><div><h3>Organize os documentos</h3><p>Consulte a recepção sobre pedido de exames, documento de identificação e documentação do convênio, quando aplicável.</p></div><div><h3>Consulte os resultados</h3><p>Siga as instruções recebidas no atendimento para acessar os seus resultados e apresentá-los ao profissional de saúde.</p></div></div></section>'''))
    if page.select_one('#toast'):
        page.select_one('#toast').decompose()

    # Keep the first screen focused on the visitor's next step, not a carousel.
    page.select_one('.site-hero').replace_with(parse(f'''<section class="conversion-hero" id="inicio" aria-labelledby="hero-title"><img class="conversion-hero-image" src="/assets/atendimento.png" alt="" width="1536" height="1024" fetchpriority="high"><div class="info-container"><p class="section-kicker">Exames laboratoriais em Araçuaí / MG</p><h1 id="hero-title">Laboratório<br>Santa Clara</h1><p class="hero-description">Seu próximo exame começa com uma conversa.</p><p>Consulte os exames realizados, tire dúvidas sobre o preparo e encontre nossa unidade em Nova Terra.</p><div class="info-actions">{contact_cta(label='Falar no WhatsApp')}<a class="site-button outline" href="#onde-estamos">Como chegar</a></div><a class="hero-exams" href="/exames/">Conhecer os exames realizados →</a></div></section>'''))
    page.select_one('#acessos').replace_with(parse('''<nav class="patient-shortcuts" aria-label="Acesso rápido"><div class="info-container"><a href="/exames/"><strong>Guia de exames</strong><span>Entenda seu exame e o preparo →</span></a><a href="#onde-estamos"><strong>Nossa localização</strong><span>Rua Amazonas, 15 · Nova Terra →</span></a><button data-action="resultados"><strong>Já fez seu exame?</strong><span>Consulte como acessar os resultados →</span></button></div></nav>'''))
    # The guide already covers these services; avoid repeating six more cards.
    page.select_one('#servicos').replace_with(parse(f'''<section id="servicos" class="contact-band"><div class="info-container"><div><h2>Está com um pedido de exames?</h2><p>Fale com a equipe para confirmar a disponibilidade, o preparo e o atendimento por convênio ou particular.</p></div>{contact_cta(label='Tirar dúvidas no WhatsApp')}</div></section>'''))
    page.select_one('#orientacoes').insert_after(parse('''<section class="info-container patient-faq" id="perguntas-frequentes"><p class="section-kicker">Antes de ir ao laboratório</p><h2>Dúvidas frequentes</h2><details><summary>Onde fica o Laboratório Santa Clara?</summary><p>Na Rua Amazonas, 15, bairro Nova Terra, em Araçuaí / MG. <a href="#onde-estamos">Veja o endereço e abra a rota até o laboratório.</a></p></details><details><summary>Como confirmar se o laboratório realiza meu exame?</summary><p>Consulte o <a href="/exames/">guia de exames</a> ou <button data-action="agendar">fale com a equipe pelo WhatsApp</button> para confirmar o exame do seu pedido.</p></details><details><summary>Quais documentos preciso levar?</summary><p>Consulte a recepção sobre documento de identificação, pedido de exames e documentação do convênio, quando aplicável.</p></details><details><summary>O laboratório atende por convênio?</summary><p>A cobertura depende do convênio, do plano e do exame solicitado. Confirme com a equipe antes da visita.</p></details><details><summary>Como recebo meus resultados?</summary><p>Siga as instruções fornecidas no atendimento. Se precisar de ajuda para acessar seus resultados, entre em contato com a recepção.</p></details></section>'''))
    page.body.append(parse(f'<nav class="mobile-contact-bar" aria-label="Contato rápido">{contact_cta(label="Falar no WhatsApp")}<a class="site-button outline" href="/#onde-estamos">Como chegar</a></nav>'))

    def metadata(document, title, description, path, exam=None):
        # Resolve contact details in every generated page, including footer links.
        for caption in document.select('.location-caption'):
            if business['address']:
                caption.string = 'Conheça o Santa Clara em Nova Terra, Araçuaí.'
        for link in document.select('.contact-column a'):
            if link.get_text(strip=True) == 'consultar telefone' and business['phone']:
                link['href'] = 'tel:' + business['phone']
                link.attrs.pop('data-action', None)
                link.string = '(33) 98752-1448'
            elif link.get_text(strip=True) == 'consultar atendimento' and business['whatsapp']:
                link.string = '(33) 98752-1448'
        for link in document.select('[data-action="duvidas"]'):
            link['href'] = '/#perguntas-frequentes'
            del link['data-action']
        for link in document.select('.header-actions .schedule'):
            link.string = 'Falar no WhatsApp'
        if exam:
            document.select_one('.exam-heading .info-container').append(parse(f'<div class="info-actions exam-heading-actions">{contact_cta(exam["name"], "Consultar este exame no WhatsApp")}</div>'))
        # Real links remain usable without JavaScript and never send a message automatically.
        if business['whatsapp'].isdigit() and len(business['whatsapp']) in (12, 13):
            for link in document.select('[data-action="agendar"]'):
                origin = link.get('data-contact-origin') or (exam['name'] if exam else 'o atendimento e o preparo dos exames')
                message = f'Olá! Vim pelo site do Santa Clara. Gostaria de informações sobre {origin}.'
                link.name = 'a'
                link.attrs.pop('type', None)
                link['href'] = 'https://wa.me/' + business['whatsapp'] + '?' + urlencode({'text': message})
                link['target'] = '_blank'
                link['rel'] = 'noopener noreferrer'
                del link['data-action']
        document.title.string = title
        document.select_one('meta[name="description"]')['content'] = description
        for old in document.select('link[rel="canonical"],meta[property^="og:"],script[type="application/ld+json"]'):
            old.decompose()
        for prop, value in [('og:title', title), ('og:description', description), ('og:type', 'article' if exam else 'website'), ('og:locale', 'pt_BR'), ('og:site_name', business['name'])]:
            tag = document.new_tag('meta', attrs={'property': prop, 'content': value})
            document.head.append(tag)
        if base:
            document.head.append(document.new_tag('link', rel='canonical', href=base + path))
            document.head.append(document.new_tag('meta', attrs={'property': 'og:url', 'content': base + path}))
        clinic = {'@type': 'MedicalClinic', 'name': business['name'], 'address': {'@type': 'PostalAddress', 'addressLocality': 'Araçuaí', 'addressRegion': 'MG', 'addressCountry': 'BR'}}
        if business['address']:
            clinic['address']['streetAddress'] = business['address']
        if business['phone']:
            clinic['telephone'] = business['phone']
        if base:
            clinic['url'] = base + '/'
            clinic['logo'] = base + '/logo.png'
            clinic['image'] = base + '/hero.png'
            document.head.append(document.new_tag('meta', attrs={'property': 'og:image', 'content': base + '/hero.png'}))
        socials = [business[key] for key in ('instagramUrl', 'facebookUrl') if business[key]]
        if socials:
            clinic['sameAs'] = socials
        schema = {'@context': 'https://schema.org', '@type': 'MedicalWebPage' if exam else 'WebPage', 'name': title, 'description': description, 'inLanguage': 'pt-BR', 'publisher': clinic}
        if exam:
            schema['about'] = {'@type': 'MedicalTest', 'name': exam['name'], 'description': exam['summary']}
        if base:
            schema['url'] = base + path
            if path != '/':
                crumbs = [{'@type': 'ListItem', 'position': 1, 'name': 'Início', 'item': base + '/'}, {'@type': 'ListItem', 'position': 2, 'name': 'Exames', 'item': base + '/exames/'}]
                if exam:
                    crumbs.append({'@type': 'ListItem', 'position': 3, 'name': exam['name'], 'item': base + path})
                schema['breadcrumb'] = {'@type': 'BreadcrumbList', 'itemListElement': crumbs}
        tag = document.new_tag('script', type='application/ld+json')
        tag.string = json.dumps(schema, ensure_ascii=False).replace('<', '\\u003c')
        document.head.append(tag)

    metadata(page, 'Laboratório Santa Clara em Araçuaí | Exames e localização', 'Conheça os exames do Laboratório Santa Clara em Araçuaí, consulte informações de preparo, atendimento e localização.', '/')
    template = copy.deepcopy(page)
    (root / 'index.html').write_text(str(page), encoding='utf-8')
    paths = ['/', '/exames/']
    listing = copy.deepcopy(template)
    listing.main.clear()
    listing.main['class'] = ['informational-main']
    listing.main.append(parse(f'''<section class="info-container exam-guide"><nav class="breadcrumbs" aria-label="Navegação estrutural"><a href="/">Início</a><span aria-hidden="true">/</span><span>Exames</span></nav><p class="section-kicker">Guia de exames</p><h1>Exames realizados no Santa Clara</h1><p class="section-intro">Informações sobre exames em Araçuaí, preparo e atendimento.</p><div class="guide-grid">{exam_cards()}</div></section>'''))
    listing.main.append(parse(location()))
    metadata(listing, 'Exames em Araçuaí | Guia do Laboratório Santa Clara', 'Conheça hemograma, glicemia, colesterol, exames de urina e fezes e eletrocardiograma no Santa Clara em Araçuaí.', '/exames/')
    (root / 'exames').mkdir(exist_ok=True)
    (root / 'exames/index.html').write_text(str(listing), encoding='utf-8')
    for exam in exams:
        document = copy.deepcopy(template)
        document.main.clear()
        document.main['class'] = ['informational-main']
        title = f"{exam['name']} em Araçuaí"
        related = ''.join(f'<a href="/exames/{other["slug"]}/">{e(other["name"])}</a>' for other in exams if other != exam)
        document.main.append(parse(f'''<div class="exam-heading"><div class="info-container"><nav class="breadcrumbs" aria-label="Navegação estrutural"><a href="/">Início</a><span aria-hidden="true">/</span><a href="/exames/">Exames</a><span aria-hidden="true">/</span><span>{e(exam['name'])}</span></nav><p class="section-kicker">{e(exam['category'])}</p><h1>{e(title)}</h1><p class="section-intro">{e(exam['summary'])}</p><a class="guide-link" href="#onde-estamos">Veja onde estamos <span aria-hidden="true">↓</span></a></div></div><div class="info-container exam-detail-layout"><article class="exam-article"><section><h2>Para que serve?</h2><p>{e(exam['purpose'])}</p></section><section><h2>Como é realizado?</h2><p>{e(exam['collection'])}</p></section><section><h2>Como se preparar?</h2><p>{e(exam['preparation'])}</p><p>As instruções específicas de preparo devem ser confirmadas com a equipe do Santa Clara antes do exame.</p></section><section><h2>Dúvida frequente</h2><h3>{e(exam['question'])}</h3><p>{e(exam['answer'])}</p></section><p class="clinical-note">Informação geral de saúde. Não substitui avaliação profissional nem as orientações recebidas no atendimento.</p><p class="source-note">Referência: <a href="{exam['source']}" target="_blank" rel="noopener noreferrer">MedlinePlus — {e(exam['name'])}</a>.</p></article><aside class="exam-help"><h2>Atendimento Santa Clara</h2><p>Confirme a disponibilidade, os documentos e as orientações para realizar {e(exam['name'].lower())}.</p><dl><dt>Cidade</dt><dd>{e(business['city'])}</dd><dt>Horário</dt><dd>{e(business['hours'])}</dd></dl><button class="site-button primary" data-action="agendar" data-contact-origin="{e(exam['name'], quote=True)}">Falar com a equipe</button><a class="guide-link" href="#onde-estamos">Localização do laboratório →</a></aside></div>'''))
        document.main.append(parse(location()))
        document.main.append(parse(f'<section class="info-container related-exams"><h2>Conheça outros exames</h2><nav aria-label="Outros exames">{related}</nav></section>'))
        path = f"/exames/{exam['slug']}/"
        metadata(document, title + ' | Laboratório Santa Clara', f"{exam['name']} no Santa Clara em Araçuaí: entenda para que serve, como é realizado e como consultar preparo e localização.", path, exam)
        output = root / 'exames' / exam['slug']
        output.mkdir(exist_ok=True)
        (output / 'index.html').write_text(str(document), encoding='utf-8')
        paths.append(path)
    (root / 'site-config.js').write_text('// Generated from content/business.json.\nwindow.SANTA_CLARA = Object.freeze(' + json.dumps(business, ensure_ascii=False, indent=2) + ');\n', encoding='utf-8')
    # The domain is intentionally not guessed; generate an absolute sitemap only when configured.
    robots = 'User-agent: *\nAllow: /\n'
    if base:
        sitemap = Element('urlset', xmlns='http://www.sitemaps.org/schemas/sitemap/0.9')
        for path in paths:
            SubElement(SubElement(sitemap, 'url'), 'loc').text = base + path
        (root / 'sitemap.xml').write_bytes(tostring(sitemap, encoding='utf-8', xml_declaration=True))
        robots += f'Sitemap: {base}/sitemap.xml\n'
    (root / 'robots.txt').write_text(robots, encoding='utf-8')
    print(f'Generated {len(paths)} informational pages. Domain configured: {bool(base)}')
