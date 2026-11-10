(() => {
  const privacy = document.querySelector('#privacidade');
  document.querySelector('[data-privacy]').addEventListener('click', event => {
    event.preventDefault();
    privacy.showModal();
  });
  document.querySelector('[data-close-privacy]').addEventListener('click', () => privacy.close());
  const menu = document.querySelector('#navbarNav');
  const toggles = [...document.querySelectorAll('.navbar-toggler')];
  function setMenu(open) {
    menu.classList.toggle('show', open);
    toggles.forEach(button => button.setAttribute('aria-expanded', String(open)));
  }
  toggles.forEach(button => {
    button.setAttribute('aria-label', button.closest('#navbarNav') ? 'Fechar menu' : 'Abrir menu');
    button.addEventListener('click', () => setMenu(!menu.classList.contains('show')));
  });
  menu.querySelectorAll('a').forEach(link => link.addEventListener('click', () => setMenu(false)));
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && menu.classList.contains('show')) {
      setMenu(false);
      toggles[0].focus();
    }
  });
  document.querySelectorAll('.accordion-button').forEach(button => button.addEventListener('click', () => {
    const panel = document.querySelector(button.dataset.bsTarget);
    const open = !panel.classList.contains('show');
    document.querySelectorAll('.accordion-collapse').forEach(item => item.classList.remove('show'));
    document.querySelectorAll('.accordion-button').forEach(item => {
      item.classList.add('collapsed');
      item.setAttribute('aria-expanded', 'false');
    });
    panel.classList.toggle('show', open);
    button.classList.toggle('collapsed', !open);
    button.setAttribute('aria-expanded', String(open));
  }));
  const benefits = [...document.querySelectorAll('[data-benefit]')];
  let current = 0;
  document.querySelectorAll('[data-direction]').forEach(button => button.addEventListener('click', () => {
    current = (current + Number(button.dataset.direction) + benefits.length) % benefits.length;
    benefits.forEach((item, index) => { item.hidden = current !== index; });
    document.querySelector('.benefit-status').textContent = `${current + 1} de ${benefits.length}`;
  }));
})();
