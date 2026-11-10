(() => {
  if (window.SantaClaraTracking) return;
  const preferenceKey = 'santa-clara:analytics-preference:v1';
  const visitorKey = 'santa-clara:analytics-visitor';
  const sessionKey = 'santa-clara:tracking';
  const duration = 30 * 86400000;
  const canEnable = navigator.globalPrivacyControl !== true && navigator.doNotTrack !== '1';
  const formSession = crypto.randomUUID();
  let preference = readPreference();
  let analytics;
  let syncPreferences;

  function readPreference() {
    try {
      const saved = JSON.parse(localStorage.getItem(preferenceKey));
      if (saved?.expires > Date.now() && ['accepted', 'rejected'].includes(saved.choice)) return saved;
    } catch {}
    return null;
  }

  function stopAnalytics() {
    analytics = undefined;
    try { localStorage.removeItem(visitorKey); } catch {}
    try { sessionStorage.removeItem(sessionKey); } catch {}
  }

  function startAnalytics() {
    if (analytics) return;
    const params = new URLSearchParams(location.search);
    const current = { page: location.pathname, referrer: document.referrer };
    for (const key of ['utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term', 'utm_id']) {
      current[key] = params.get(key) || '';
    }
    const now = Date.now();
    let visitorId;
    try {
      const stored = JSON.parse(localStorage.getItem(visitorKey));
      const visitor = stored?.id && stored.expires > now
        ? stored : { id: crypto.randomUUID(), expires: now + duration };
      localStorage.setItem(visitorKey, JSON.stringify(visitor));
      visitorId = visitor.id;
    } catch {}
    let session = { id: crypto.randomUUID(), entry: current, last: now };
    try {
      const previous = JSON.parse(sessionStorage.getItem(sessionKey));
      if (previous?.id && now - previous.last < 30 * 60 * 1000) session = { ...previous, last: now };
      sessionStorage.setItem(sessionKey, JSON.stringify(session));
    } catch {}
    analytics = { visitorId, session, current };
    event('page_view');
  }

  async function send(path, data) {
    if (analytics && preference?.expires <= Date.now()) stopAnalytics();
    if (path === '/api/events' && !analytics) return;
    const context = analytics ? {
      current: analytics.current,
      entry: analytics.session.entry,
      analyticsConsent: 'v1',
      analyticsConsentAt: preference.at,
    } : {};
    return fetch(path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      keepalive: true,
      body: JSON.stringify({ session: path === '/api/events' ? analytics.session.id : formSession,
        ...context, ...data }),
    });
  }

  function event(name, details = {}) {
    if (!analytics || preference?.expires <= Date.now()) return;
    send('/api/events', {
      id: crypto.randomUUID(), event: name,
      visitorId: name === 'page_view' ? analytics.visitorId : undefined, ...details,
    }).catch(() => {});
  }

  function updatePreference(choice) {
    if (!['accepted', 'rejected'].includes(choice)) return;
    const now = Date.now();
    preference = { choice, at: new Date(now).toISOString(), expires: now + duration };
    try { localStorage.setItem(preferenceKey, JSON.stringify(preference)); } catch {}
    if (canEnable && choice === 'accepted') startAnalytics();
    else stopAnalytics();
  }

  window.SantaClaraTracking = { send, event };
  if (canEnable && preference?.choice === 'accepted') startAnalytics();
  else stopAnalytics();

  window.addEventListener('storage', change => {
    if (change.key !== preferenceKey && change.key !== null) return;
    preference = readPreference();
    if (canEnable && preference?.choice === 'accepted') startAnalytics();
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

  function trackLink(click) {
    const link = click.target.closest('a[href]');
    if (!link || click.defaultPrevented) return;
    const url = new URL(link.href, location.href);
    if (!['http:', 'https:'].includes(url.protocol)) return;
    const target = url.origin === location.origin
      ? url.pathname + (/^#[\w-]+$/.test(url.hash) ? url.hash : '')
      : url.origin + url.pathname;
    event('link_click', { target });
  }

  document.addEventListener('click', trackLink);
  document.addEventListener('auxclick', click => { if (click.button === 1) trackLink(click); });
})();
