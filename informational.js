(() => {
  const tracking = document.createElement('script');
  tracking.src = '/assets/lead-tracking.js';
  window.santaClaraTrackingReady = new Promise(resolve => {
    tracking.addEventListener('load', resolve, { once: true });
    tracking.addEventListener('error', resolve, { once: true });
    document.head.append(tracking);
  });
  const config = window.SANTA_CLARA;
  const $ = selector => document.querySelector(selector);
  const $$ = selector => [...document.querySelectorAll(selector)];
  const dialog = $('#site-dialog');
  let previousFocus;
  const escape = value => String(value).replace(/[&<>"']/g, char => ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[char]));
  const safeUrl = value => {
    try { return new URL(value).protocol === 'https:'; } catch { return false; }
  };

  function show(title, content) {
    $('#dialog-title').textContent = title;
    $('#dialog-content').innerHTML = content;
    if (!dialog.open) {
      previousFocus = document.activeElement;
      dialog.showModal();
      document.body.style.overflow = 'hidden';
    }
  }
  dialog.addEventListener('close', () => {
    document.body.style.overflow = '';
    previousFocus?.focus();
  });
  dialog.addEventListener('click', event => {
    if (event.target !== dialog) return;
    const rect = dialog.getBoundingClientRect();
    if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) dialog.close();
  });

  function contact(origin) {
    if (!/^\d{12,13}$/.test(config.whatsapp)) {
      show('Atendimento Santa Clara', `<p>Atendimento em ${escape(config.city)}, das ${escape(config.hours)}.</p><p>O contato online ainda não está disponível. Consulte a recepção para orientações sobre o seu exame.</p>`);
      return;
    }
    const message = `Olá! Vim pelo site do Santa Clara. Gostaria de informações sobre ${origin || 'o atendimento e o preparo dos exames'}.`;
    window.SantaClaraTracking?.event('link_click', { target: `https://wa.me/${config.whatsapp}` });
    window.open(`https://wa.me/${config.whatsapp}?text=${encodeURIComponent(message)}`, '_blank', 'noopener,noreferrer');
  }

  const information = {
    'social-pendente': ['Redes sociais', '<p>Os links oficiais do Santa Clara ainda não foram cadastrados neste site.</p>'],
    'agencia-pendente': ['Top Marketing', '<p>O endereço do site da Top Marketing ainda não foi cadastrado.</p>'],
    'localizacao-pendente': ['Como chegar ao Santa Clara', `<p>${escape(config.city)}</p><p>O endereço completo e o mapa ainda aguardam confirmação. Consulte a recepção antes de se deslocar.</p>`],
    resultados: ['Resultados de exames', '<p>Tenha em mãos o protocolo entregue na coleta e siga as instruções de acesso nele.</p><p>Se precisar de ajuda para localizar seu laudo, fale com a recepção.</p><button class="site-button primary" type="button" data-action="agendar" data-contact-origin="como acessar meu resultado">Pedir ajuda pelo WhatsApp</button>'],
    sobre: ['Laboratório Santa Clara', '<p>O Laboratório Santa Clara realiza exames laboratoriais em Araçuaí / MG.</p><p>Conheça nosso guia de exames e consulte a equipe sobre preparo e atendimento.</p><a class="site-button primary" href="/exames/">Conhecer os exames</a>'],
    convenios: ['Convênios', '<p>A cobertura depende do convênio, do plano e do exame solicitado.</p><p>Confirme com a recepção os convênios atendidos e a documentação necessária.</p><button class="site-button primary" data-action="agendar">Consultar atendimento</button>'],
    duvidas: ['Perguntas frequentes', '<details><summary>Qual é o horário de atendimento?</summary><p>Das 06:30 às 16:00. Confirme os dias de funcionamento com a recepção.</p></details><details><summary>Preciso de jejum?</summary><p>O preparo depende dos exames solicitados. Confirme as orientações com a equipe antes da coleta.</p></details><details><summary>Onde encontro informações sobre meu exame?</summary><p>Acesse o <a class="guide-link" href="/exames/">guia de exames</a> e consulte a página do exame solicitado.</p></details><details><summary>Como acessar meus resultados?</summary><p>Siga as orientações fornecidas no atendimento ou procure a recepção.</p></details>'],
    privacidade: ['Privacidade', '<p>Consulte como usamos os dados do cadastro do e-book e como você pode escolher se autoriza a análise de audiência.</p><a href="/contato/#privacidade">Ler o aviso de privacidade</a>']
  };

  function closeMenu() {
    $('#mobile-nav').hidden = true;
    $('.mobile-toggle').setAttribute('aria-expanded', 'false');
  }
  function slideTo(index) {
    const slides = $$('.site-slide');
    if (!slides.length) return;
    $('#slide-track').style.transform = `translate3d(-${index * 100}%,0,0)`;
    slides.forEach((slide, i) => {
      slide.inert = i !== index;
      slide.setAttribute('aria-hidden', String(i !== index));
    });
    $$('[data-slide]').forEach((dot, i) => {
      dot.setAttribute('aria-current', String(i === index));
      dot.style.width = i === index ? '30px' : '8px';
      dot.style.opacity = i === index ? '1' : '.6';
    });
  }
  document.addEventListener('click', event => {
    const target = event.target.closest('a,button');
    if (!target) return;
    if (target.dataset.slide !== undefined) slideTo(Number(target.dataset.slide));
    const action = target.dataset.action;
    if (action) {
      event.preventDefault();
      if (action === 'carregar-mapa') {
        const frame = document.createElement('iframe');
        frame.className = 'location-map';
        frame.title = 'Localização do Laboratório Santa Clara no Google Maps';
        frame.referrerPolicy = 'no-referrer';
        frame.allowFullscreen = true;
        frame.src = target.dataset.mapSrc;
        target.closest('.location-map-preview').replaceWith(frame);
        frame.focus();
      } else if (action === 'planet-toggle') {
        const planet = target.closest('.clinic-planet');
        const paused = planet.classList.toggle('is-paused');
        target.setAttribute('aria-pressed', String(paused));
        target.textContent = paused ? 'Retomar rotação' : 'Pausar rotação';
      } else if (action === 'agendar') contact(target.dataset.contactOrigin);
      else if (action === 'fechar-dialog') dialog.close();
      else if (action === 'menu') {
        $('#mobile-nav').hidden = !$('#mobile-nav').hidden;
        target.setAttribute('aria-expanded', String(!$('#mobile-nav').hidden));
      } else if (action === 'resultados' && safeUrl(config.resultsUrl)) {
        window.open(config.resultsUrl, '_blank', 'noopener,noreferrer');
      } else if (information[action]) show(...information[action]);
    }
    if (target.closest('#mobile-nav')) closeMenu();
    if (target.tagName === 'A') $$('header details[open]').forEach(item => { item.open = false; });
  });
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape') {
      $$('header details[open]').forEach(item => { item.open = false; });
      closeMenu();
    }
  });
  $$('header details').forEach(item => item.addEventListener('toggle', () => {
    if (item.open) $$('header details').filter(other => other !== item).forEach(other => { other.open = false; });
  }));
  slideTo(0);

  const heroTrack = $('#heroTrack');
  if (heroTrack) {
    const slides = [...heroTrack.children];
    const dots = $$('#heroDots .hero-dot');
    let current = 0;

    function selectHeroSlide(index) {
      current = (index + slides.length) % slides.length;
      heroTrack.style.transform = `translate3d(-${current * 100}%,0,0)`;
      slides.forEach((slide, position) => {
        const selected = position === current;
        slide.inert = !selected;
        slide.setAttribute('aria-hidden', String(!selected));
      });
      dots.forEach((dot, position) => {
        dot.classList.toggle('active', position === current);
        dot.setAttribute('aria-current', String(position === current));
      });
    }

    $('#heroPrevBtn')?.addEventListener('click', () => selectHeroSlide(current - 1));
    $('#heroNextBtn')?.addEventListener('click', () => selectHeroSlide(current + 1));
    dots.forEach((dot, index) => dot.addEventListener('click', () => selectHeroSlide(index)));
    selectHeroSlide(0);
  }

  const filter = $('#exam-filter');
  if (filter) {
    const normalize = value => value.normalize('NFD').replace(/\p{Diacritic}/gu, '').toLowerCase();
    const aliases = {
      glicemia: 'glicose açucar',
      colesterol: 'hdl ldl perfil lipídico',
      'exame-de-urina': 'eas urina tipo 1',
      'exame-de-fezes': 'parasitológico coproparasitológico',
      eletrocardiograma: 'ecg eletro'
    };
    const cards = $$('#exam-results .guide-card').map(card => {
      const link = card.querySelector('h3 a');
      const slug = link.pathname.split('/')[2];
      const keywords = [link.textContent, aliases[slug], card.dataset.searchTerms].filter(Boolean);
      return { card, keywords: normalize(keywords.join(' ')) };
    });

    function filterExams() {
      const terms = normalize(filter.value.trim()).split(/\s+/).filter(Boolean);
      let count = 0;
      for (const { card, keywords } of cards) {
        card.hidden = !terms.every(term => keywords.includes(term));
        if (!card.hidden) count += 1;
      }
      $('#exam-count').textContent = count === 0 ? 'Nenhum exame encontrado no guia.'
        : `${count} ${count === 1 ? 'exame no guia' : 'exames no guia'}`;
    }

    filter.addEventListener('input', filterExams);
    filterExams();
    const search = $('#buscar-exames');
    search.hidden = false;
    if (window.location.hash === '#buscar-exames') search.scrollIntoView();
  }

  for (const [selector, url] of [['#social-instagram', config.instagramUrl], ['#social-facebook', config.facebookUrl], ['#agency-link', config.agencyUrl]]) {
    const link = $(selector);
    if (link && safeUrl(url)) {
      link.href = url;
      link.target = '_blank';
      link.rel = 'noopener noreferrer';
      delete link.dataset.action;
    }
  }
})();
