(() => {
  window.SantaClaraAnalyticsPreferences = ({ choice, canEnable, onChange }) => {
    const styles = document.createElement('link');
    styles.rel = 'stylesheet';
    styles.href = '/assets/analytics-preferences.css';

    const controls = document.createElement('div');
    controls.className = 'sc-analytics-controls';
    controls.innerHTML = '<button type="button" aria-expanded="false" aria-controls="sc-analytics-preferences">Preferências de privacidade</button>';
    const settings = controls.firstElementChild;
    const footer = document.querySelector('footer');
    (footer?.querySelector('.footer-inner') || footer || document.body).append(controls);

    const panel = document.createElement('section');
    panel.id = 'sc-analytics-preferences';
    panel.className = 'sc-analytics-preferences';
    panel.setAttribute('aria-labelledby', 'sc-analytics-title');
    panel.hidden = true;
    panel.innerHTML = `
      <h2 id="sc-analytics-title" tabindex="-1">Preferências de análise</h2>
      <p>Com sua autorização, medimos visitas e cliques. Um identificador com validade de 30 dias permite reconhecer este navegador quando ele volta ao site.</p>
      <p class="sc-analytics-status" hidden></p>
      <a href="/contato/#privacidade">Política de privacidade</a>
      <div class="sc-analytics-options">
        <button type="button" data-analytics-choice="accepted">Aceitar análise</button>
        <button type="button" data-analytics-choice="rejected">Recusar análise</button>
      </div>
    `;
    document.body.append(panel);

    const heading = panel.querySelector('h2');
    const status = panel.querySelector('.sc-analytics-status');
    const accept = panel.querySelector('[data-analytics-choice="accepted"]');
    let openedBySettings = false;

    function show(visible) {
      panel.hidden = !visible;
      settings.setAttribute('aria-expanded', String(visible));
    }

    function close() {
      show(false);
      if (openedBySettings) settings.focus({ preventScroll: true });
      openedBySettings = false;
    }

    function updateStatus() {
      status.hidden = canEnable && choice === null;
      status.textContent = canEnable
        ? (choice === 'accepted' ? 'Sua escolha atual: análise permitida.' : 'Sua escolha atual: análise desativada.')
        : 'A análise está desativada pela preferência de privacidade do seu navegador.';
    }

    function toggleSettings() {
      if (!panel.hidden && openedBySettings) {
        close();
        return;
      }
      openedBySettings = true;
      updateStatus();
      show(true);
      heading.focus({ preventScroll: true });
    }

    accept.disabled = !canEnable;
    if (!canEnable) accept.setAttribute('aria-describedby', 'sc-analytics-status');
    status.id = 'sc-analytics-status';
    settings.addEventListener('click', toggleSettings);
    panel.addEventListener('click', (event) => {
      const option = event.target.closest('[data-analytics-choice]');
      if (!option || option.disabled) return;
      choice = option.dataset.analyticsChoice;
      onChange(choice);
      close();
    });
    panel.addEventListener('keydown', (event) => {
      if (event.key === 'Escape') close();
    });
    styles.addEventListener('load', () => {
      if (canEnable && choice === null) show(true);
    }, { once: true });
    styles.addEventListener('error', () => {
      if (canEnable && choice === null) show(true);
    }, { once: true });
    document.head.append(styles);

    return (nextChoice) => {
      choice = nextChoice;
      if (openedBySettings) updateStatus();
      else show(canEnable && choice === null);
    };
  };
})();
