(() => {
  function campaignUrl(value) {
    if (typeof value !== 'string' || !value.trim()) return null;
    const raw = value.trim();
    try {
      const url = new URL(raw, window.location.origin);
      const isLocalPath = /^\/(?![\\/])/.test(raw) && url.origin === window.location.origin;
      const isExternalHttps = /^https:\/\//i.test(raw) && url.protocol === 'https:';
      if ((!isLocalPath && !isExternalHttps) || url.username || url.password) return null;
      if (!url.searchParams.has('utm_source')) url.searchParams.set('utm_source', 'santa_clara_site');
      url.searchParams.set('utm_medium', 'popup');
      if (!url.searchParams.has('utm_campaign')) url.searchParams.set('utm_campaign', 'ebook_santa_clara');
      return url.href;
    } catch {
      return null;
    }
  }

  function track(event, params = {}) {
    window.SantaClaraTracking?.event(event, params);
  }

  class EbookPopup {
    constructor(destination, localPreview) {
      this.destination = destination;
      this.localPreview = localPreview;
      this.listeners = new AbortController();
    }

    start() {
      if ((!this.destination && !this.localPreview) || !window.HTMLDialogElement?.prototype.showModal) return;
      window.setTimeout(() => {
        const check = () => this.maybeOpen();
        const { signal } = this.listeners;
        document.addEventListener('visibilitychange', check, { signal });
        document.addEventListener('close', check, { capture: true, signal });
        check();
      }, 15000);
    }

    maybeOpen() {
      if (this.listeners.signal.aborted || document.hidden) return;
      if (document.querySelector('dialog[open]')) return;
      this.listeners.abort();
      this.open();
    }

    open() {
      const dialog = document.createElement('dialog');
      dialog.className = 'ebook-popup';
      dialog.setAttribute('aria-labelledby', 'ebook-popup-title');
      dialog.setAttribute('aria-describedby', 'ebook-popup-description');
      dialog.innerHTML = `
        <button class="ebook-popup-close" type="button" aria-label="Fechar e-book">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="m6 6 12 12M18 6 6 18"/></svg>
        </button>
        <div class="ebook-popup-content">
          <div class="ebook-popup-copy">
            <span class="ebook-popup-badge">E-BOOK GRATUITO</span>
            <h2 id="ebook-popup-title" tabindex="-1" autofocus>Sua saúde sempre fica por último? Comece a cuidar dela em 3 passos.</h2>
            <div id="ebook-popup-description">
              <p class="ebook-popup-promise"><strong>Em 5 minutos, descubra por onde começar, mesmo com a agenda cheia.</strong></p>
              <p>Receba o guia gratuito do Santa Clara e escolha uma ação para colocar em prática hoje.</p>
            </div>
          </div>
          <img class="ebook-popup-cover" src="/assets/images/ebook-santa-clara.png" alt="Capa do e-book Você cuida de tudo. Mas quem cuida de você?" width="1536" height="1024" decoding="async" fetchpriority="low">
          <div class="ebook-popup-actions">
            <button type="button" class="site-button primary ebook-popup-cta" data-open-ebook-form>RECEBER MEU E-BOOK GRÁTIS</button>
          </div>
        </div>
        <div class="ebook-popup-content ebook-popup-registration" hidden>
            <div>
              <h2 id="ebook-registration-title" tabindex="-1">Receba seu e-book grátis</h2>
              <p id="ebook-registration-description">Preencha seus dados para abrir o guia.</p>
            </div>
            <form class="ebook-lead-form">
              <label>Primeiro nome <input name="name" autocomplete="given-name" maxlength="80" required></label>
              <label>E-mail <input name="email" type="email" autocomplete="email" maxlength="254" required></label>
              <label>WhatsApp (opcional) <input name="phone" type="tel" autocomplete="tel" maxlength="30"></label>
              <label class="ebook-lead-opt-in"><input type="checkbox" name="marketing"> Quero receber conteúdos e novidades do Laboratório Santa Clara pelos canais que informei.</label>
              <p class="ebook-lead-privacy">Usamos seus dados para liberar o e-book. <a href="/contato/#privacidade" target="_blank" rel="noopener">Política de privacidade</a></p>
              <button type="submit" class="site-button primary ebook-popup-cta">RECEBER MEU E-BOOK GRÁTIS</button>
              <p role="status" class="ebook-lead-status" hidden></p>
            </form>
        </div>`;

      const previousFocus = document.activeElement;
      const form = dialog.querySelector('.ebook-lead-form');
      const cta = form.querySelector('button[type="submit"]');
      const registration = dialog.querySelector('.ebook-popup-registration');
      const offer = dialog.querySelector('.ebook-popup-content');
      const status = dialog.querySelector('.ebook-lead-status');
      const submissionId = crypto.randomUUID();
      let reason = 'dismiss';
      const outside = event => {
        const rect = dialog.getBoundingClientRect();
        return event.target === dialog && (event.clientX < rect.left || event.clientX > rect.right ||
          event.clientY < rect.top || event.clientY > rect.bottom);
      };
      let outsidePress = false;
      dialog.addEventListener('pointerdown', event => { outsidePress = outside(event); });
      dialog.addEventListener('click', event => {
        if (outsidePress && outside(event)) dialog.close();
        outsidePress = false;
      });
      dialog.querySelector('.ebook-popup-close').addEventListener('click', () => dialog.close());
      dialog.querySelector('[data-open-ebook-form]').addEventListener('click', () => {
        offer.hidden = true;
        registration.hidden = false;
        dialog.classList.add('ebook-popup-compact');
        dialog.setAttribute('aria-labelledby', 'ebook-registration-title');
        dialog.setAttribute('aria-describedby', 'ebook-registration-description');
        registration.querySelector('h2').focus();
      });
      form.addEventListener('submit', async event => {
        event.preventDefault();
        if (cta.disabled) return;
        cta.disabled = true;
        status.hidden = false;
        status.textContent = 'Liberando seu e-book…';
        const fields = Object.fromEntries(new FormData(form));
        track('ebook_popup_click');
        try {
          const response = await window.SantaClaraTracking.send('/api/ebook-leads', {
            ...fields, id: submissionId, marketing: fields.marketing === 'on',
          });
          const result = await response.json().catch(() => null);
          if (!result || (response.ok && typeof result.download !== 'string')) {
            throw new Error('O cadastro está indisponível nesta página. Tente novamente em instantes.');
          }
          if (!response.ok) throw new Error(result.error);
          reason = 'cta';
          dialog.close();
          location.assign(result.download);
        } catch (error) {
          status.textContent = error instanceof TypeError
            ? 'Não foi possível conectar. Tente novamente.'
            : (error.message || 'Não foi possível liberar o e-book. Tente novamente.');
          cta.disabled = false;
        }
      });
      dialog.addEventListener('close', () => {
        dialog.remove();
        if (previousFocus?.isConnected) previousFocus.focus({ preventScroll: true });
        track('ebook_popup_close', { reason });
      });

      document.body.append(dialog);
      dialog.showModal();
      track('ebook_popup_view');
    }
  }

  const localPreview = ['localhost', '127.0.0.1'].includes(window.location.hostname);
  Promise.resolve(window.santaClaraTrackingReady).then(() => {
    new EbookPopup(campaignUrl(window.SANTA_CLARA?.ebookUrl), localPreview).start();
  });
})();
