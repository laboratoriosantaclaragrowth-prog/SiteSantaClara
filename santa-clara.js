(() => {
  const config = window.SANTA_CLARA;
  const $ = (selector) => document.querySelector(selector);
  const $$ = (selector) => [...document.querySelectorAll(selector)];
  const dialog = $("#site-dialog");
  const exams = $$("[data-exam]").map(card => ({
    id: card.dataset.exam, name: card.dataset.name,
    category: card.dataset.category, description: card.querySelector("p").textContent
  }));
  const selected = new Set();
  let activeCategory = "laboratorio";
  let toastTimer;
  let priorFocus;
  const normalize = value => value.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
  const escape = value => String(value).replace(/[&<>"']/g, char => ({ "&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;" }[char]));

  function show(title, content) {
    $("#dialog-title").textContent = title;
    $("#dialog-content").innerHTML = content;
    if (!dialog.open) {
      priorFocus = document.activeElement;
      dialog.showModal();
      document.body.style.overflow = "hidden";
    }
  }
  dialog.addEventListener("close", () => {
    document.body.style.overflow = "";
    priorFocus?.focus();
  });
  dialog.addEventListener("click", event => {
    if (event.target === dialog) {
      const rect = dialog.getBoundingClientRect();
      if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) dialog.close();
    }
  });
  function contact(origin) {
    if (!/^\d{12,13}$/.test(config.whatsapp)) {
      show("Atendimento Santa Clara", `<p>Atendimento em ${escape(config.city)}, das ${escape(config.hours)}.</p><p>O agendamento online ainda não está disponível. Entre em contato diretamente com a recepção do laboratório.</p>`);
      return;
    }
    const names = exams.filter(exam => selected.has(exam.id)).map(exam => exam.name);
    const message = `Olá! Vim pelo site Santa Clara (${origin}). Gostaria de informações${names.length ? " sobre: " + names.join(", ") : " para agendar meus exames"}.`;
    window.open(`https://wa.me/${config.whatsapp}?text=${encodeURIComponent(message)}`, "_blank", "noopener,noreferrer");
  }
  function quote() {
    const items = exams.filter(exam => selected.has(exam.id));
    show("Meu orçamento", items.length ? items.map(exam => `<div class="quote-row"><span>${escape(exam.name)}${exam.id === "ecg" ? " · R$ 50,00" : ""}</span><button data-remove="${exam.id}">Remover</button></div>`).join("") + '<p>Confirme os valores e a disponibilidade com nossa equipe.</p><button class="site-button primary" data-action="solicitar">Solicitar orçamento</button>' : '<p>Seu orçamento está vazio.</p><p>Selecione os exames que deseja consultar.</p><button class="site-button primary" data-action="ver-exames">Ver exames</button>');
  }
  function updateCount() {
    $("#cart-count").textContent = selected.size;
    $("#cart-count").hidden = !selected.size;
    $$("[data-add-exam]").forEach(button => {
      button.setAttribute("aria-pressed", String(selected.has(button.dataset.addExam)));
      button.style.backgroundColor = selected.has(button.dataset.addExam) ? "#e4eaff" : "";
    });
  }
  function filter() {
    const term = normalize($("#exam-search").value.trim());
    let count = 0;
    $$("[data-exam]").forEach(card => {
      const match = card.dataset.category === activeCategory && normalize(card.textContent).includes(term);
      card.hidden = !match;
      if (match) count++;
    });
    $("#search-empty").hidden = count > 0;
    $$("[data-tab]").forEach(tab => {
      const active = tab.dataset.tab === activeCategory;
      tab.setAttribute("aria-selected", String(active));
      tab.classList.toggle("border-b-2", active);
      tab.classList.toggle("border-primary", active);
    });
  }
  const information = {
    "social-pendente": ["Redes sociais", "<p>Os links oficiais do Santa Clara ainda não foram cadastrados neste site.</p>"],
    "agencia-pendente": ["Top Marketing", "<p>O endereço do site da Top Marketing ainda não foi cadastrado.</p>"],
    resultados: ["Resultados de exames", "<p>O portal de resultados ainda não está integrado a este site.</p><p>Utilize as orientações recebidas no seu atendimento ou consulte a recepção do Santa Clara.</p>"],
    unidade: ["Nossa unidade", `<img class="dialog-photo" src="/hero.png" alt="Fachada do Laboratório Santa Clara"><p><strong>Laboratório Santa Clara</strong><br>${escape(config.city)}</p><p>Horário de atendimento: ${escape(config.hours)}.</p><p>${config.address ? escape(config.address) : "Confirme o endereço e os dias de funcionamento com a recepção antes de se deslocar."}</p>`],
    sobre: ["Laboratório Santa Clara", "<p>O Laboratório Santa Clara realiza exames laboratoriais em Araçuaí / MG.</p><p>Consulte nossa equipe para informações sobre exames, preparo, valores e atendimento.</p>"],
    ecg: ["Eletrocardiograma", '<p>ECG particular: <strong>R$ 50,00</strong>.</p><p>Consulte os horários e a disponibilidade com a equipe.</p><button class="site-button primary" data-action="agendar">Consultar atendimento</button>'],
    convenios: ["Convênios", '<p>A cobertura depende do convênio, do plano e do exame solicitado.</p><p>Confirme com a recepção os convênios atendidos e a documentação necessária.</p><button class="site-button primary" data-action="agendar">Consultar convênio</button>'],
    preparo: ["Preparo para exames", "<p>O preparo varia conforme o exame solicitado. Confirme as orientações com o laboratório antes da coleta.</p><p>Tenha em mãos seu pedido de exames e um documento de identificação.</p>"],
    duvidas: ["Perguntas frequentes", '<details><summary>Qual é o horário de atendimento?</summary><p>Das 06:30 às 16:00. Confirme os dias de funcionamento com a recepção.</p></details><details><summary>Preciso de jejum?</summary><p>O preparo depende dos exames solicitados. Confirme as orientações com a equipe.</p></details><details><summary>Quanto custa o eletrocardiograma?</summary><p>O ECG particular custa R$ 50,00. Consulte a disponibilidade.</p></details><details><summary>Como acessar meus resultados?</summary><p>Siga as orientações fornecidas no atendimento ou procure a recepção.</p></details>'],
    privacidade: ["Privacidade", "<p>Esta página não recebe pedidos médicos, senhas ou resultados de exames. A seleção de exames fica apenas nesta página e é apagada ao recarregar.</p><p>Não há ferramentas de publicidade ou rastreamento nesta versão. Nenhuma informação é enviada automaticamente.</p>"]
  };
  document.addEventListener("click", event => {
    const target = event.target.closest("a,button");
    if (!target) return;
    if (target.dataset.slide !== undefined) {
      const index = Number(target.dataset.slide);
      $("#slide-track").style.transform = `translate3d(-${index * 100}%,0,0)`;
      $$(".site-slide").forEach((slide, i) => { slide.inert = i !== index; slide.setAttribute("aria-hidden", String(i !== index)); });
      $$("[data-slide]").forEach((dot, i) => {
        dot.setAttribute("aria-current", String(i === index));
        dot.style.width = i === index ? "30px" : "8px";
        dot.style.opacity = i === index ? "1" : ".6";
      });
    }
    if (target.dataset.tab) { activeCategory = target.dataset.tab; filter(); }
    if (target.dataset.scroll) $("#exam-list").scrollBy({left: Number(target.dataset.scroll) * 318, behavior:"smooth"});
    if (target.dataset.examDetail) {
      event.preventDefault();
      const exam = exams.find(item => item.id === target.dataset.examDetail);
      show(exam.name, `<p>${escape(exam.description)}</p><p>${exam.id === "ecg" ? "Atendimento particular: R$ 50,00." : "Consulte valores, disponibilidade e preparo com o laboratório."}</p><button class="site-button primary" data-add-exam="${exam.id}">Adicionar ao orçamento</button>`);
    }
    if (target.dataset.addExam) {
      selected.add(target.dataset.addExam);
      updateCount();
      $("#toast").textContent = "Exame adicionado ao orçamento.";
      $("#toast").hidden = false;
      clearTimeout(toastTimer);
      toastTimer = setTimeout(() => { $("#toast").hidden = true; }, 2500);
    }
    if (target.dataset.remove) { selected.delete(target.dataset.remove); updateCount(); quote(); }
    const action = target.dataset.action;
    if (action) {
      event.preventDefault();
      if (information[action]) {
        if (action === "resultados" && /^https:\/\//.test(config.resultsUrl)) window.open(config.resultsUrl, "_blank", "noopener,noreferrer");
        else show(...information[action]);
      } else if (action === "agendar" || action === "solicitar") contact(action);
      else if (action === "orcamento") quote();
      else if (action === "fechar-dialog") dialog.close();
      else if (action === "ver-exames") { dialog.close(); $("#exames").scrollIntoView(); }
      else if (action === "menu") {
        $("#mobile-nav").hidden = !$("#mobile-nav").hidden;
        target.setAttribute("aria-expanded", String(!$("#mobile-nav").hidden));
      }
    }
    if (target.closest("#mobile-nav")) {
      $("#mobile-nav").hidden = true;
      $(".mobile-toggle").setAttribute("aria-expanded", "false");
    }
    if (target.tagName === "A") $$("header details[open]").forEach(item => item.open = false);
  });
  document.addEventListener("keydown", event => {
    if (event.key === "Escape") {
      $$("header details[open]").forEach(item => item.open = false);
      $("#mobile-nav").hidden = true;
      $(".mobile-toggle").setAttribute("aria-expanded", "false");
    }
  });
  $$("header details").forEach(item => item.addEventListener("toggle", () => {
    if (item.open) $$("header details").filter(other => other !== item).forEach(other => other.open = false);
  }));
  $("#exam-search").addEventListener("input", filter);
  $$("[data-tab]").forEach((tab, index, tabs) => tab.addEventListener("keydown", event => {
    if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
    event.preventDefault();
    const next = event.key === "Home" ? 0 : event.key === "End" ? tabs.length - 1 :
      (index + (event.key === "ArrowRight" ? 1 : -1) + tabs.length) % tabs.length;
    activeCategory = tabs[next].dataset.tab;
    filter();
    tabs[next].focus();
  }));
  $$(".site-slide").forEach((slide, i) => { slide.inert = i !== 0; slide.setAttribute("aria-hidden", String(i !== 0)); });
  filter();
  for (const [selector, url] of [["#social-instagram", config.instagramUrl], ["#social-facebook", config.facebookUrl], ["#agency-link", config.agencyUrl]]) {
    const link = $(selector);
    if (link && /^https:\/\//.test(url || "")) {
      link.href = url;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      delete link.dataset.action;
    }
  }
})();

// Smooth reveal animation on scroll for all cards (efeito de subir)
(() => {
  function initCardReveal() {
    const cardSelectors = '.sc-service-card, .sc-convenio-card, .sc-google-card, .guide-card, .sc-testimonial-card';
    const cards = document.querySelectorAll(cardSelectors);
    
    if (!('IntersectionObserver' in window)) {
      cards.forEach(card => card.classList.add('sc-revealed'));
      return;
    }

    const observer = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          entry.target.classList.add('sc-revealed');
          observer.unobserve(entry.target);
        }
      });
    }, {
      threshold: 0.1,
      rootMargin: '0px 0px -30px 0px'
    });

    cards.forEach(card => {
      card.classList.add('sc-reveal-card');
      observer.observe(card);
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initCardReveal);
  } else {
    initCardReveal();
  }
})();
