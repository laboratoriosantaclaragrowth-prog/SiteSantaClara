// Rastreador próprio e leve do site (sem bibliotecas), igual ao do painel do Instituto do Sono:
// visitas, tempo ativo, seções vistas, cliques, rolagem, origem (UTM/referência) e aparelho.
// Só funciona depois que a pessoa clica em "Aceitar análise" (LGPD).
// Os dados vão em lotes para /api/track e são gravados no Supabase.
//
// Regras de precisão:
// - 1 visita = 1 aba aberta no site; nova visita após 30 min sem atividade.
// - Tempo ativo = segundos com a aba visível E alguém interagiu nos últimos 2 min.
// - A visita é registrada em ~1,5s (quem sai rápido também conta).
// - Tempo e rolagem são atualizados a cada 15s e na saída da página.
(() => {
  if (window.SantaClaraTracking) return;
  const preferenceKey = 'santa-clara:analytics-preference:v1';
  const visitorKey = 'santa-clara:analytics-visitor';
  const sessionKey = 'santa-clara:track-session';
  const duration = 30 * 86400000;
  const SESSION_TIMEOUT = 30 * 60 * 1000;
  const FLUSH_MS = 15000;
  const IDLE_MS = 120000;
  const canEnable = navigator.globalPrivacyControl !== true && navigator.doNotTrack !== '1' && !navigator.webdriver;
  const formSession = crypto.randomUUID();
  let preference = readPreference();
  let tracker;
  let syncPreferences;

  // Nome amigável de cada parte do site (para o painel)
  const SECTION_NAMES = {
    'site-header': 'Menu do topo',
    'mobile-nav': 'Menu do celular',
    inicio: 'Topo (banner)',
    'sc-service-cards': 'Destaques',
    'sc-promo-banner': 'Banner check-ups',
    servicos: 'Exames que fazemos',
    laboratorio: 'Somos o Santa Clara',
    sobre: 'Nossa história',
    'duvidas-exames': 'Faixa pedido de exames',
    'contact-band': 'Faixa de contato',
    depoimentos: 'Depoimentos',
    'perguntas-frequentes': 'Dúvidas frequentes',
    'patient-faq': 'Dúvidas frequentes',
    'onde-estamos': 'Como chegar',
    'location-section': 'Como chegar',
    'related-exams': 'Outros exames',
    'exam-heading': 'Topo do artigo',
    'exam-detail-layout': 'Texto do exame',
    'blog-article': 'Texto do artigo',
    'exam-guide': 'Lista de exames/artigos',
    'contact-page-intro': 'Topo da página',
    'contact-page-layout': 'Canais de contato',
    privacidade: 'Privacidade',
    banner: 'Coleta domiciliar: topo',
    highlights: 'Coleta domiciliar: destaques',
    services: 'Coleta domiciliar: serviços',
    region: 'Coleta domiciliar: região',
    facilidades: 'Coleta domiciliar: facilidades',
    vantagens: 'Coleta domiciliar: vantagens',
    'site-footer': 'Rodapé',
    'ebook-popup': 'Pop-up do e-book',
    'sc-analytics-preferences': 'Aviso de privacidade',
  };
  const AREA_SELECTOR = [
    '[data-track-section]', 'dialog.ebook-popup', '.sc-analytics-preferences', '#mobile-nav', 'header.site-header',
    'main section', 'main > article', 'main > div', 'footer',
  ].join(', ');
  const OBSERVED_SELECTOR = 'main section, main > article, main > div, footer, [data-track-section]';

  function readPreference() {
    try {
      const saved = JSON.parse(localStorage.getItem(preferenceKey));
      if (saved?.expires > Date.now() && ['accepted', 'rejected'].includes(saved.choice)) return saved;
    } catch {}
    return null;
  }

  function sectionNameOf(el) {
    const area = el?.closest?.(AREA_SELECTOR);
    if (!area) return undefined;
    if (area.dataset.trackSection) return area.dataset.trackSection;
    const key = (SECTION_NAMES[area.id] && area.id) || [...area.classList].find(c => SECTION_NAMES[c]);
    if (key) return SECTION_NAMES[key];
    const label = area.getAttribute('aria-label') || area.querySelector('h1, h2, h3')?.textContent || area.id;
    return label ? label.replace(/\s+/g, ' ').trim().slice(0, 50) : undefined;
  }

  function classifyLink(a) {
    if (!a) return { target: 'button' };
    const href = a.getAttribute('href') || '';
    if (/wa\.me|whatsapp/i.test(href)) return { target: 'whatsapp', href: href.split('?')[0] };
    if (href.startsWith('tel:')) return { target: 'phone', href };
    if (href.startsWith('mailto:')) return { target: 'email', href: 'mailto' };
    if (/\.pdf($|\?)/i.test(href)) return { target: 'download', href: href.split('?')[0] };
    if (/google\.[^/]+\/maps|maps\.app|goo\.gl\/maps/i.test(href)) return { target: 'maps', href: 'google maps' };
    if (href.startsWith('#') || href.startsWith('/') || href.includes(location.hostname)) return { target: 'internal', href: href.slice(0, 200) };
    return { target: 'external', href: href.split('?')[0].slice(0, 200) };
  }

  function deviceInfo() {
    const ua = navigator.userAgent;
    const w = Math.min(screen.width, screen.height);
    const device = /iPad|Tablet/i.test(ua) || (/Android/i.test(ua) && !/Mobile/i.test(ua)) ? 'tablet'
      : /Mobi|iPhone|Android/i.test(ua) || w < 600 ? 'mobile' : 'desktop';
    const os = /Windows/i.test(ua) ? 'Windows' : /iPhone|iPad|iOS/i.test(ua) ? 'iOS' : /Android/i.test(ua) ? 'Android'
      : /Mac OS/i.test(ua) ? 'macOS' : /Linux/i.test(ua) ? 'Linux' : 'Outro';
    const browser = /Instagram/i.test(ua) ? 'Instagram (app)' : /FBAN|FBAV/i.test(ua) ? 'Facebook (app)' : /Edg\//.test(ua) ? 'Edge'
      : /SamsungBrowser/.test(ua) ? 'Samsung' : /OPR\//.test(ua) ? 'Opera' : /Firefox\//.test(ua) ? 'Firefox'
      : /CriOS|Chrome\//.test(ua) ? 'Chrome' : /Safari\//.test(ua) ? 'Safari' : 'Outro';
    return {
      device, os, browser, screen: `${screen.width}x${screen.height}`,
      language: navigator.language, timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
    };
  }

  function getSession() {
    const now = Date.now();
    let visitor;
    let returning = false;
    try {
      const stored = JSON.parse(localStorage.getItem(visitorKey));
      if (stored?.id && stored.expires > now) { visitor = stored; returning = true; }
    } catch {}
    visitor = visitor || { id: crypto.randomUUID(), expires: now + duration };
    try { localStorage.setItem(visitorKey, JSON.stringify(visitor)); } catch {}

    try {
      const saved = JSON.parse(sessionStorage.getItem(sessionKey));
      if (saved?.id && saved.visitor_id === visitor.id && now - saved.last < SESSION_TIMEOUT) {
        saved.last = now;
        saved.first = false;
        return saved;
      }
    } catch {}
    const params = new URLSearchParams(location.search);
    const utm = {};
    ['utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content', 'gclid', 'fbclid'].forEach(k => {
      const v = params.get(k);
      if (v) utm[k] = v.slice(0, 200);
    });
    // gclid/fbclid sem UTM = anúncio Google/Meta
    if (!utm.utm_source && utm.gclid) { utm.utm_source = 'google'; utm.utm_medium = 'cpc'; }
    if (!utm.utm_source && utm.fbclid) { utm.utm_source = 'facebook'; utm.utm_medium = 'paid_social'; }
    delete utm.fbclid;
    let refHost = '';
    try { refHost = document.referrer ? new URL(document.referrer).hostname.replace(/^www\./, '') : ''; } catch {}
    if (refHost === location.hostname.replace(/^www\./, '')) refHost = '';
    return {
      id: crypto.randomUUID(), visitor_id: visitor.id, started: now, last: now, first: true, active: 0,
      is_returning: returning, utm, landing_page: location.pathname,
      referrer: refHost ? document.referrer.slice(0, 300) : '', referrer_host: refHost,
    };
  }

  function startTracker() {
    if (tracker) return;
    const sess = getSession();
    const info = deviceInfo();
    const queue = [];
    const cleanup = new AbortController();
    const { signal } = cleanup;
    let activeSeconds = Number(sess.active) || 0;
    let sentActive = -1;
    let maxScroll = 0;
    let sentScroll = -1;
    let lastInteraction = Date.now();
    let first = sess.first;
    const pageStart = activeSeconds;
    let pageTimeSent = false;

    const save = () => {
      sess.last = Date.now();
      sess.active = activeSeconds;
      sess.first = first;
      try { sessionStorage.setItem(sessionKey, JSON.stringify(sess)); } catch {}
    };
    save();

    const push = (e) => {
      queue.push({ page: location.pathname, ts: new Date().toISOString(), ...e });
      if (queue.length >= 40) flush();
    };

    const flush = (useBeacon = false) => {
      if (!tracker || preference?.choice !== 'accepted' || preference.expires <= Date.now()) return;
      const changed = activeSeconds !== sentActive || maxScroll !== sentScroll;
      if (!queue.length && !first && !changed) return;
      const payload = JSON.stringify({
        first,
        analyticsConsent: 'v1',
        analyticsConsentAt: preference.at,
        session: {
          id: sess.id, visitor_id: sess.visitor_id, is_returning: sess.is_returning,
          landing_page: sess.landing_page, page: location.pathname,
          referrer: sess.referrer, referrer_host: sess.referrer_host,
          active_seconds: activeSeconds, max_scroll: maxScroll,
          ...sess.utm, ...info,
        },
        events: queue.splice(0, queue.length),
      });
      sentActive = activeSeconds;
      sentScroll = maxScroll;
      first = false;
      save();
      try {
        if (useBeacon && navigator.sendBeacon) {
          navigator.sendBeacon('/api/track', new Blob([payload], { type: 'application/json' }));
        } else {
          fetch('/api/track', { method: 'POST', body: payload, keepalive: true, headers: { 'Content-Type': 'application/json' } }).catch(() => {});
        }
      } catch {}
    };

    // Tempo ativo
    const tick = setInterval(() => {
      if (document.visibilityState === 'visible' && Date.now() - lastInteraction < IDLE_MS) activeSeconds += 1;
    }, 1000);
    const onAct = () => { lastInteraction = Date.now(); };
    ['pointerdown', 'keydown', 'scroll', 'touchstart', 'mousemove', 'wheel']
      .forEach(ev => addEventListener(ev, onAct, { passive: true, signal }));

    // Rolagem máxima da página
    const onScroll = () => {
      const h = document.documentElement;
      const pct = Math.round(((h.scrollTop + innerHeight) / Math.max(h.scrollHeight, 1)) * 100);
      if (pct > maxScroll) maxScroll = Math.min(pct, 100);
    };
    addEventListener('scroll', onScroll, { passive: true, signal });
    onScroll();

    // Cliques em links e botões (1 registro por clique)
    document.addEventListener('click', (ev) => {
      const el = ev.target?.closest?.('a, button, summary, [data-track]');
      if (!el) return;
      const a = el.tagName === 'A' ? el : null;
      const text = (el.dataset.track || el.textContent || el.getAttribute('aria-label') || '').replace(/\s+/g, ' ').trim();
      const label = text.slice(0, 80) || el.getAttribute('aria-label') || '(ícone)';
      const { target, href } = classifyLink(a);
      push({ type: 'click', label, target, href, section: sectionNameOf(el) });
      if (target !== 'internal' && target !== 'button') flush(true);
    }, { capture: true, signal });

    // Tempo em cada seção na tela
    const seen = new Set();
    const intersecting = new Set();
    const visibleSince = new Map();
    const startSection = (name) => {
      if (!visibleSince.has(name) && document.visibilityState === 'visible') visibleSince.set(name, Date.now());
    };
    const stopSection = (name) => {
      const t0 = visibleSince.get(name);
      if (t0 == null) return;
      visibleSince.delete(name);
      const secs = Math.round((Date.now() - t0) / 100) / 10;
      if (secs >= 1) push({ type: 'section_time', section: name, value: Math.min(secs, 1800) });
    };
    const stopAll = () => [...visibleSince.keys()].forEach(stopSection);
    const io = new IntersectionObserver((entries) => {
      entries.forEach((en) => {
        const name = sectionNameOf(en.target);
        if (!name) return;
        // "Viu" quando a seção ocupa boa parte da tela
        const visible = en.isIntersecting && (en.intersectionRatio >= 0.4 || en.intersectionRect.height >= innerHeight * 0.5);
        if (visible) {
          intersecting.add(name);
          if (!seen.has(name)) { seen.add(name); push({ type: 'section_view', section: name }); }
          startSection(name);
        } else {
          intersecting.delete(name);
          stopSection(name);
        }
      });
    }, { threshold: [0, 0.2, 0.4, 0.6, 0.8, 1] });
    const observe = (root) => {
      const candidates = [...root.querySelectorAll(OBSERVED_SELECTOR)];
      if (root.matches?.(OBSERVED_SELECTOR) || root.matches?.('dialog.ebook-popup')) candidates.push(root);
      candidates.filter(el => !candidates.some(other => other !== el && el.contains(other)) && sectionNameOf(el))
        .forEach(el => io.observe(el));
    };
    observe(document);
    // O pop-up do e-book entra na página depois; observa quando aparecer.
    const mo = new MutationObserver(records => records.forEach(r => r.addedNodes.forEach(node => {
      if (node.nodeType === 1 && node.matches('dialog.ebook-popup')) io.observe(node);
    })));
    mo.observe(document.body, { childList: true });

    // Envio: primeiro registro rápido, depois a cada 15s e na saída
    const pushPageTime = () => {
      if (pageTimeSent) return;
      const secs = activeSeconds - pageStart;
      if (secs > 0) push({ type: 'page_time', value: secs });
      pageTimeSent = true;
    };
    const onHide = () => {
      if (document.visibilityState === 'hidden') { stopAll(); flush(true); }
      else intersecting.forEach(startSection);
    };
    document.addEventListener('visibilitychange', onHide, { signal });
    addEventListener('pagehide', () => { stopAll(); pushPageTime(); flush(true); }, { signal });
    const firstTimer = setTimeout(() => flush(), 1500);
    const timer = setInterval(() => flush(), FLUSH_MS);

    push({ type: 'pageview' });
    tracker = {
      session: sess,
      push,
      flush,
      stop() {
        clearTimeout(firstTimer);
        clearInterval(tick);
        clearInterval(timer);
        cleanup.abort();
        io.disconnect();
        mo.disconnect();
      },
    };
  }

  function stopAnalytics() {
    tracker?.stop();
    tracker = undefined;
    try { localStorage.removeItem(visitorKey); } catch {}
    try { sessionStorage.removeItem(sessionKey); } catch {}
    try { sessionStorage.removeItem('santa-clara:tracking'); } catch {}
  }

  function analyticsAllowed() {
    return canEnable && preference?.choice === 'accepted' && preference.expires > Date.now();
  }

  // Envio de formulários (cadastro do e-book). Com a análise autorizada, liga o cadastro à visita.
  async function send(path, data) {
    if (tracker && !analyticsAllowed()) stopAnalytics();
    const context = tracker ? {
      analyticsConsent: 'v1', analyticsConsentAt: preference.at,
      visitorId: tracker.session.visitor_id, trackSession: tracker.session.id,
      current: { page: location.pathname, referrer: document.referrer },
      entry: { page: tracker.session.landing_page, referrer: tracker.session.referrer, ...tracker.session.utm },
    } : {};
    return fetch(path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      keepalive: true,
      body: JSON.stringify({ session: formSession, ...context, ...data }),
    });
  }

  // Eventos do pop-up do e-book
  const EBOOK_EVENTS = { ebook_popup_view: 'ebook_open', ebook_popup_close: 'ebook_close', ebook_lead_saved: 'ebook_submit' };
  function event(name, details = {}) {
    if (!tracker || !analyticsAllowed() || !EBOOK_EVENTS[name]) return;
    const type = EBOOK_EVENTS[name];
    tracker.push({ type, label: type === 'ebook_close' ? `fechou (${details.reason || 'x'})` : 'pop-up e-book', section: 'Pop-up do e-book' });
    if (type === 'ebook_submit') tracker.flush(true);
  }

  function updatePreference(choice) {
    if (!['accepted', 'rejected'].includes(choice)) return;
    const now = Date.now();
    preference = { choice, at: new Date(now).toISOString(), expires: now + duration };
    try { localStorage.setItem(preferenceKey, JSON.stringify(preference)); } catch {}
    if (analyticsAllowed()) startTracker();
    else stopAnalytics();
  }

  window.SantaClaraTracking = { send, event };
  if (analyticsAllowed()) startTracker();
  else stopAnalytics();

  addEventListener('storage', change => {
    if (change.key !== preferenceKey && change.key !== null) return;
    preference = readPreference();
    if (analyticsAllowed()) startTracker();
    else stopAnalytics();
    syncPreferences?.(preference?.choice ?? null);
  });

  const preferences = document.createElement('script');
  preferences.src = '/assets/analytics-preferences.js';
  preferences.addEventListener('load', () => {
    syncPreferences = window.SantaClaraAnalyticsPreferences?.({
      choice: preference?.choice ?? null, canEnable, onChange: updatePreference,
    });
  }, { once: true });
  document.head.append(preferences);
})();
