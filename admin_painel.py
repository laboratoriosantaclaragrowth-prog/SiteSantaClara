"""Painel do site (/admin): login, período e HTML do painel.

O visual e as métricas seguem o painel do Instituto do Sono. Os números vêm das
funções sc_admin_* do Supabase (supabase_painel.sql).
"""

import hashlib
import hmac
import os
import time
from datetime import datetime, timedelta, timezone
from html import escape
from urllib.parse import quote, urlencode

from admin_painel_css import CSS

BRASILIA = timezone(timedelta(hours=-3))  # sem horário de verão desde 2019
ADMIN_COOKIE = "sc_admin"
SESSION_DAYS = 7
PRODUCTION_HOSTS = {"laboratoriosantaclaramg.com.br", "www.laboratoriosantaclaramg.com.br"}

WEEKDAYS = ["Dom", "Seg", "Ter", "Qua", "Qui", "Sex", "Sáb"]
MONTHS = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto",
          "setembro", "outubro", "novembro", "dezembro"]
TARGETS = {"whatsapp": "WhatsApp", "phone": "Telefone", "maps": "Google Maps", "email": "E-mail",
           "internal": "Link interno", "external": "Link externo", "button": "Botão", "download": "Download"}
DEVICES = {"mobile": "Celular", "desktop": "Computador", "tablet": "Tablet"}
PRESETS = {"hoje": "Hoje", "ontem": "Ontem", "7d": "7 dias", "30d": "30 dias", "mes": "Este mês", "90d": "90 dias"}
PAGE_NAMES = {
    "/": "Início (página principal)", "/exames": "Guia de exames", "/exames/aracuai": "Onde fazer exames em Araçuaí",
    "/santa-clara-ate-voce": "Coleta domiciliar", "/contato": "Contato", "/blog": "Blog (lista de artigos)",
}

ICONS = {
    "users": '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>',
    "message": '<path d="M7.9 20A9 9 0 1 0 4 16.1L2 22Z"/>',
    "book": '<path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/>',
    "clock": '<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>',
    "pointer": '<path d="m9 9 5 12 1.8-5.2L21 14Z"/><path d="M7.2 2.2 8 5.1"/><path d="m5.1 8-2.9-.8"/><path d="M14 4.1 12 6"/><path d="m6 12-1.9 2"/>',
    "eye": '<path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/>',
    "compass": '<circle cx="12" cy="12" r="10"/><polygon points="16.24 7.76 14.12 14.12 7.76 16.24 9.88 9.88 16.24 7.76"/>',
    "pin": '<path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z"/><circle cx="12" cy="10" r="3"/>',
    "download": '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" x2="12" y1="15" y2="3"/>',
}


def icon(name, size=18):
    return (f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
            f'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{ICONS[name]}</svg>')


# ---------------------------------------------------------------- login

def _secret():
    password = os.environ.get("SANTA_CLARA_ADMIN_PASSWORD", "")
    if len(password) < 8:
        return None
    # Trocar a senha encerra todos os logins abertos.
    seed = f"sc-admin|{password}|{os.environ.get('SUPABASE_SECRET_KEY', '')}"
    return hashlib.sha256(seed.encode()).digest()


def admin_configured():
    return _secret() is not None


def check_password(supplied):
    password = os.environ.get("SANTA_CLARA_ADMIN_PASSWORD", "")
    if not admin_configured():
        return False
    return hmac.compare_digest(hashlib.sha256(supplied.encode()).digest(), hashlib.sha256(password.encode()).digest())


def create_token():
    expires = str(int(time.time()) + SESSION_DAYS * 86400)
    return f"{expires}.{hmac.new(_secret(), expires.encode(), hashlib.sha256).hexdigest()}"


def verify_token(token):
    secret = _secret()
    if not secret or not token or "." not in token:
        return False
    expires, signature = token.split(".", 1)
    if not expires.isdigit() or int(expires) < time.time():
        return False
    expected = hmac.new(secret, expires.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def cookie_token(cookie_header):
    for part in (cookie_header or "").split(";"):
        name, _, value = part.strip().partition("=")
        if name == ADMIN_COOKIE:
            return value
    return ""


def session_cookie(host, value=None):
    secure = "" if is_local_host(host) else "; Secure"
    if value is None:
        return f"{ADMIN_COOKIE}=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax{secure}"
    return f"{ADMIN_COOKIE}={value}; Path=/; Max-Age={SESSION_DAYS * 86400}; HttpOnly; SameSite=Lax{secure}"


def host_name(host):
    host = (host or "").strip().lower()
    if host.startswith("["):
        return host.split("]")[0] + "]"
    return host.rsplit(":", 1)[0] if host.count(":") == 1 else host


def is_local_host(host):
    name = host_name(host)
    return name in {"localhost", "127.0.0.1", "[::1]"} or name.endswith(".localhost")


def is_test_visit(host, cookie_header):
    """Visitas fora do domínio oficial (computador, Vercel) e do admin logado são teste."""
    return host_name(host) not in PRODUCTION_HOSTS or verify_token(cookie_token(cookie_header))


# ---------------------------------------------------------------- período

def _today():
    now = datetime.now(BRASILIA)
    return datetime(now.year, now.month, now.day, tzinfo=BRASILIA)


def resolve_period(preset, month):
    today = _today()
    tomorrow = today + timedelta(days=1)
    if month and len(month) == 7 and month[4] == "-" and month[:4].isdigit() and month[5:].isdigit():
        year, mon = int(month[:4]), int(month[5:])
        if 1 <= mon <= 12:
            start = datetime(year, mon, 1, tzinfo=BRASILIA)
            end = datetime(year + (mon == 12), mon % 12 + 1, 1, tzinfo=BRASILIA)
            return {"key": f"m:{month}", "label": f"{MONTHS[mon - 1]} de {year}", "from": start, "to": min(end, tomorrow)}
    options = {
        "hoje": ("Hoje", today, tomorrow),
        "ontem": ("Ontem", today - timedelta(days=1), today),
        "30d": ("Últimos 30 dias", today - timedelta(days=29), tomorrow),
        "90d": ("Últimos 90 dias", today - timedelta(days=89), tomorrow),
        "mes": (f"{MONTHS[today.month - 1]} (até hoje)", today.replace(day=1), tomorrow),
    }
    key = preset if preset in options else "7d"
    label, start, end = options.get(key, ("Últimos 7 dias", today - timedelta(days=6), tomorrow))
    return {"key": key, "label": label, "from": start, "to": end}


def last_months(count=12):
    today = _today()
    year, month, out = today.year, today.month, []
    for _ in range(count):
        out.append((f"{year}-{month:02d}", f"{MONTHS[month - 1]} {year}"))
        month -= 1
        if month == 0:
            month, year = 12, year - 1
    return out


def iso(value):
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


# ---------------------------------------------------------------- formatação

def n(value):
    try:
        return f"{int(round(float(value or 0))):,}".replace(",", ".")
    except (TypeError, ValueError):
        return "0"


def num(value):
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def dec(value):
    value = num(value)
    return n(value) if value == int(value) else f"{value:.1f}".replace(".", ",")


def fmt_time(seconds):
    s = int(round(num(seconds)))
    if s < 60:
        return f"{s}s"
    m, r = divmod(s, 60)
    return f"{m}min {r:02d}s" if m < 60 else f"{m // 60}h {m % 60}min"


def pct(a, b):
    a, b = num(a), num(b)
    return round(a / b * 1000) / 10 if b else 0


def fmt_date(value):
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed.astimezone(BRASILIA).strftime("%d/%m/%y %H:%M")
    except ValueError:
        return "—"


def fmt_phone(phone):
    digits = "".join(c for c in str(phone or "") if c.isdigit())
    if digits.startswith("55") and len(digits) in (12, 13):
        digits = digits[2:]
    if len(digits) in (10, 11):
        return f"({digits[:2]}) {digits[2:-4]}-{digits[-4:]}"
    return str(phone or "")


def page_name(path):
    p = (path or "/").rstrip("/") or "/"
    if p in PAGE_NAMES:
        return PAGE_NAMES[p]
    for prefix, label in (("/blog/", "Blog"), ("/exames/", "Exame")):
        if p.startswith(prefix):
            return f"{label}: {p[len(prefix):].replace('-', ' ')}"
    return p


def e(value):
    return escape(str(value if value is not None else ""), quote=True)


def delta(now, prev, invert=False, suffix="%"):
    if prev is None:
        return ""
    now, prev = num(now), num(prev)
    if not prev and not now:
        return '<em class="adm-delta">—</em>'
    if not prev:
        return '<em class="adm-delta up">novo</em>'
    diff = now - prev if suffix == "pp" else (now - prev) / prev * 100
    good = diff < 0 if invert else diff > 0
    cls = "" if abs(diff) < 0.5 else ("up" if good else "down")
    arrow = "▲" if diff > 0 else "▼" if diff < 0 else ""
    amount = f"{abs(diff):.1f}".replace(".", ",") + " p.p." if suffix == "pp" else f"{abs(diff):.0f}%"
    return f'<em class="adm-delta {cls}">{arrow} {amount}</em>'


def bars(rows, label, value, fmt=n, green=False):
    if not rows:
        return '<p class="adm-empty">Sem dados no período.</p>'
    top = max([1] + [value(r) for r in rows])
    items = "".join(
        f'<li><div class="adm-bar-label" title="{e(label(r))}">{e(label(r))}</div>'
        f'<div class="adm-bar-track"><div class="adm-bar-fill" style="width:{value(r) / top * 100:.1f}%"></div></div>'
        f'<div class="adm-bar-value">{fmt(value(r))}</div></li>' for r in rows)
    return f'<ul class="adm-bars{" green" if green else ""}">{items}</ul>'


def table(headers, rows, empty="Sem dados no período."):
    head = "".join(f"<th>{h}</th>" for h in headers)
    body = "".join(rows) or f'<tr><td colspan="{len(headers)}" class="adm-empty">{empty}</td></tr>'
    return f'<div class="adm-scroll"><table class="adm-table"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def document(title, body):
    return (f'<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width, initial-scale=1">'
            f'<meta name="robots" content="noindex, nofollow"><title>{e(title)}</title>'
            f'<link rel="icon" href="/logo.png"><style>{CSS}</style></head>'
            f'<body><div class="adm">{body}</div></body></html>')


# ---------------------------------------------------------------- páginas

def render_login(error=False):
    missing = []
    if not admin_configured():
        missing.append("SANTA_CLARA_ADMIN_PASSWORD (mín. 8 caracteres)")
    if not os.environ.get("SUPABASE_URL") or not os.environ.get("SUPABASE_SECRET_KEY"):
        missing.append("SUPABASE_URL e SUPABASE_SECRET_KEY")
    notice = ""
    if missing:
        notice = f'<div class="adm-error">Falta configurar no servidor: {e(", ".join(missing))}.</div>'
    elif error:
        notice = '<p class="adm-error">Senha incorreta.</p>'
    return document("Painel | Laboratório Santa Clara", f'''
<main class="adm-login"><form method="post" action="/admin/login" class="adm-login-card">
<p class="adm-kicker">Laboratório Santa Clara</p><h1>Painel do site</h1>
<label><span>Senha</span><input type="password" name="password" required autofocus autocomplete="current-password"></label>
{notice}<button type="submit">Entrar</button></form></main>''')


def render_message(title, text):
    return document("Painel | Laboratório Santa Clara",
                    f'<main class="adm-wrap"><div class="adm-card"><h1>{e(title)}</h1><p>{text}</p></div></main>')


def render_dashboard(*, dash, prev, leads, visitors, keywords, period, include_test, preset, month):
    t = dash.get("totals") or {}
    pt = (prev or {}).get("totals")

    def prev_of(key):
        return None if pt is None else pt.get(key)

    def link(extra):
        params = {k: v for k, v in {"t": "1" if include_test else None, **extra}.items() if v}
        return "/admin" + (f"?{urlencode(params)}" if params else "")

    test_params = {k: v for k, v in {"p": preset, "m": month, "t": None if include_test else "1"}.items() if v}
    test_href = "/admin" + (f"?{urlencode(test_params)}" if test_params else "")
    by_day = dash.get("by_day") or []
    by_hour = dash.get("by_hour") or []
    by_weekday = dash.get("by_weekday") or []
    sections = dash.get("sections") or []
    clicks = dash.get("clicks") or []
    has_data = num(t.get("sessions")) > 0
    max_day = max([1] + [num(d["sessions"]) for d in by_day])
    max_hour = max([1] + [num(h["sessions"]) for h in by_hour])

    insights = []
    if has_data:
        best_hour = max(by_hour, key=lambda h: num(h["sessions"]), default={"hour": 0, "sessions": 0})
        best_wa_hour = max(by_hour, key=lambda h: num(h["whatsapp"]), default={"hour": 0, "whatsapp": 0})
        best_dow = max(by_weekday, key=lambda d: num(d["sessions"]), default={"dow": 0})
        insights.append(("clock", "Horário mais movimentado", f'{best_hour["hour"]}h às {int(best_hour["hour"]) + 1}h',
                         f'mais visitas em {WEEKDAYS[int(best_dow["dow"])]}'))
        wa_sections = dash.get("whatsapp_by_section") or []
        if wa_sections:
            peak = f' · pico às {best_wa_hour["hour"]}h' if num(best_wa_hour.get("whatsapp")) > 0 else ""
            insights.append(("message", "De onde mais saem cliques no WhatsApp", wa_sections[0]["section"],
                             f'{n(wa_sections[0]["clicks"])} cliques{peak}'))
        if clicks:
            where = f' · {clicks[0]["section"]}' if clicks[0].get("section") else ""
            insights.append(("pointer", "Botão mais clicado", clicks[0]["label"], f'{n(clicks[0]["clicks"])} cliques{where}'))
        sticky = sorted([s for s in sections if num(s["sessions"]) >= 3], key=lambda s: -num(s["avg_seconds"]))
        if sticky:
            insights.append(("eye", "Seção onde mais param", sticky[0]["section"], f'{fmt_time(sticky[0]["avg_seconds"])} em média'))
        sources = dash.get("sources") or []
        if sources:
            s0 = sources[0]
            insights.append(("compass", "Principal origem", s0["source"],
                             f'{n(s0["sessions"])} visitas · {dec(pct(s0["whatsapp"], s0["sessions"]))}% clicaram no WhatsApp'))
        cities = dash.get("cities") or []
        if cities and cities[0]["city"] != "Não identificada":
            insights.append(("pin", "Cidade que mais acessa", cities[0]["city"], f'{n(cities[0]["sessions"])} visitas'))

    presets = "".join(f'<a href="{e(link({"p": k}))}" class="{"on" if period["key"] == k else ""}">{v}</a>'
                      for k, v in PRESETS.items())
    selected = period["key"][2:] if period["key"].startswith("m:") else ""
    months = "".join(f'<option value="{v}"{" selected" if v == selected else ""}>{lbl}</option>' for v, lbl in last_months())
    out = [f'''<main class="adm-wrap">
<header class="adm-top">
  <div class="adm-title"><p class="adm-kicker">Laboratório Santa Clara</p><h1>Painel do site</h1>
  <p class="adm-period"><span class="adm-live"><i></i>{n(dash.get("online_now"))} no site agora</span> · {e(period["label"])}</p></div>
  <div class="adm-filters">
    <nav class="adm-range" aria-label="Período">{presets}</nav>
    <form class="adm-month" method="get" action="/admin">{'<input type="hidden" name="t" value="1">' if include_test else ""}
      <select name="m" aria-label="Escolher mês"><option value=""{"" if selected else " selected"} disabled>Escolher mês…</option>{months}</select>
      <button type="submit">Ver</button></form>
    <a class="adm-test {"on" if include_test else ""}" href="{e(test_href)}">{"✓ Incluindo testes" if include_test else "Incluir testes"}</a>
    <form method="post" action="/admin/logout"><button class="adm-ghost">Sair</button></form>
  </div>
</header>
<nav class="adm-nav" aria-label="Seções do painel">
  <a href="#resultado">Resultado</a><a href="#comportamento">O que fazem no site</a>
  <a href="#quando">Quando e como acessam</a><a href="#origem">De onde vêm</a><a href="#pessoas">Visitantes e leads</a>
</nav>''']

    if not has_data:
        out.append('''<div class="adm-card adm-note-card">Nenhuma visita real no período. Visitas feitas no seu computador,
no endereço da Vercel e enquanto você está logado no painel são marcadas como <b>teste</b> e ficam fora dos números.
Clique em <b>Incluir testes</b> para vê-las.</div>''')

    # ---------- RESULTADO
    out.append(f'''<h2 class="adm-group" id="resultado">Resultado <small>comparado com o período anterior</small></h2>
<section class="adm-kpis">
  <div class="adm-kpi"><div class="adm-kpi-head"><span class="adm-ico">{icon("users")}</span>Visitas</div>
    <strong>{n(t.get("sessions"))}</strong><small>{n(t.get("visitors"))} pessoas · {n(t.get("returning"))} voltaram</small>{delta(t.get("sessions"), prev_of("sessions"))}</div>
  <div class="adm-kpi hl"><div class="adm-kpi-head"><span class="adm-ico g">{icon("message")}</span>Clicaram no WhatsApp</div>
    <strong>{n(t.get("whatsapp_sessions"))}</strong><small>{dec(t.get("whatsapp_rate"))}% das visitas · {n(t.get("whatsapp_clicks"))} cliques</small>{delta(t.get("whatsapp_sessions"), prev_of("whatsapp_sessions"))}</div>
  <div class="adm-kpi hl"><div class="adm-kpi-head"><span class="adm-ico g">{icon("book")}</span>Leads do e-book</div>
    <strong>{n(t.get("leads"))}</strong><small>{dec(t.get("lead_rate"))}% das visitas</small>{delta(t.get("leads"), prev_of("leads"))}</div>
  <div class="adm-kpi"><div class="adm-kpi-head"><span class="adm-ico">{icon("clock")}</span>Tempo médio no site</div>
    <strong>{fmt_time(t.get("avg_seconds"))}</strong><small>metade fica mais de {fmt_time(t.get("median_seconds"))}</small>{delta(t.get("avg_seconds"), prev_of("avg_seconds"))}</div>
</section>
<section class="adm-strip">
  <div><span>Saíram em menos de 10s</span><b>{dec(t.get("bounce_rate"))}%</b>{delta(t.get("bounce_rate"), prev_of("bounce_rate"), invert=True, suffix="pp")}</div>
  <div><span>Cliques em “Ligar”</span><b>{n(t.get("phone_clicks"))}</b>{delta(t.get("phone_clicks"), prev_of("phone_clicks"))}</div>
  <div><span>Cliques em “Como chegar” (Maps)</span><b>{n(t.get("maps_clicks"))}</b>{delta(t.get("maps_clicks"), prev_of("maps_clicks"))}</div>
  <div><span>Páginas vistas · rolagem média</span><b>{n(t.get("pageviews"))} · {n(t.get("avg_scroll"))}%</b></div>
</section>''')
    if insights:
        out.append('<section class="adm-insights">' + "".join(
            f'<div class="adm-insight"><span class="adm-ico">{icon(ic)}</span><div><small>{e(lbl)}</small>'
            f'<b>{e(val)}</b><em>{e(sub)}</em></div></div>' for ic, lbl, val, sub in insights) + "</section>")

    cols = "".join(
        f'<div class="adm-col" title="{d["day"][8:10]}/{d["day"][5:7]}: {n(d["sessions"])} visitas · {n(d["whatsapp"])} WhatsApp · {n(d["leads"])} leads">'
        f'<b class="adm-col-n">{n(d["sessions"]) if num(d["sessions"]) else ""}</b>'
        f'<div class="adm-col-bar" style="height:{num(d["sessions"]) / max_day * 100:.1f}%">'
        + (f'<div class="adm-col-wa" style="height:{num(d["whatsapp"]) / max(num(d["sessions"]), 1) * 100:.1f}%"></div>' if num(d["whatsapp"]) else "")
        + f'</div><span>{d["day"][8:10]}/{d["day"][5:7]}</span></div>' for d in by_day)
    out.append(f'''<section class="adm-card"><div class="adm-card-head"><h3>Visitas por dia</h3>
<p class="adm-legend"><i class="lg-a"></i> visitas <i class="lg-b"></i> clicaram no WhatsApp</p></div>
<div class="adm-cols" style="grid-template-columns:repeat({max(len(by_day), 1)},minmax(0,1fr))">{cols}</div></section>''')

    # ---------- COMPORTAMENTO
    out.append('<h2 class="adm-group" id="comportamento">O que fazem no site</h2>')
    page_rows = [
        f'<tr><td><b>{e(page_name(pg["page"]))}</b><small class="adm-sub">{e(pg["page"])}</small></td><td>{n(pg["views"])}</td>'
        f'<td><div class="adm-mini"><div style="width:{min(num(pg["reach"]), 100)}%"></div></div>{n(pg["sessions"])} <small class="adm-muted">({dec(pg["reach"])}%)</small></td>'
        f'<td>{n(pg["entrances"])}</td><td>{fmt_time(pg["avg_seconds"])}</td>'
        f'<td>{n(pg["whatsapp_sessions"])} <small class="adm-muted">({dec(pct(pg["whatsapp_sessions"], pg["sessions"]))}%)</small></td></tr>'
        for pg in dash.get("pages") or []]
    out.append(f'''<section class="adm-card"><div class="adm-card-head"><h3>Páginas mais acessadas</h3></div>
{table(["Página", "Aberturas", "Visitas", "Entraram por ela", "Tempo médio", "WhatsApp"], page_rows)}
<p class="adm-note">Aberturas = vezes que a página abriu. Visitas = visitas diferentes que abriram a página. “Entraram por ela” = foi a primeira página da visita.</p></section>''')

    section_rows = [
        f'<tr><td><b>{e(s["section"])}</b></td><td><div class="adm-mini wide"><div style="width:{min(num(s["reach"]), 100)}%"></div></div>'
        f'{dec(s["reach"])}% <small class="adm-muted">({n(s["sessions"])})</small></td><td>{fmt_time(s["avg_seconds"])}</td><td>{fmt_time(s["total_seconds"])}</td></tr>'
        for s in sections if num(s["sessions"]) > 0]
    out.append(f'''<section class="adm-card"><div class="adm-card-head"><h3>Seções da página: até onde chegam e onde param</h3></div>
{table(["Seção", "Chegaram até ela", "Tempo médio na tela", "Tempo total"], section_rows)}</section>''')

    click_rows = [
        f'<tr><td><b>{e(c["label"])}</b></td><td><span class="adm-tag t-{e(c["target"])}">{e(TARGETS.get(c["target"], c["target"]))}</span></td>'
        f'<td>{e(c.get("section") or "—")}</td><td><b>{n(c["clicks"])}</b></td></tr>' for c in clicks[:25]]
    out.append(f'''<div class="adm-grid2 wide-left">
<section class="adm-card"><div class="adm-card-head"><h3>Botões mais clicados</h3></div>
{table(["Botão", "Tipo", "Onde", "Cliques"], click_rows, "Sem cliques no período.")}</section>
<div class="adm-stack">
<section class="adm-card"><div class="adm-card-head"><h3>Cliques no WhatsApp por seção</h3></div>
{bars(dash.get("whatsapp_by_section") or [], lambda r: r["section"], lambda r: num(r["clicks"]), green=True)}</section>
<section class="adm-card"><div class="adm-card-head"><h3>Cliques por tipo</h3></div>
{bars(dash.get("click_targets") or [], lambda r: TARGETS.get(r["target"], r["target"]), lambda r: num(r["clicks"]))}</section>
</div></div>''')

    ebook = dash.get("ebook") or {}
    steps = [("Pop-up apareceu", ebook.get("opens")), ("Clicou em “Receber”", ebook.get("offer_clicks")),
             ("Cadastrou (lead)", ebook.get("submits"))]
    funnel = ""
    for i, (label, value) in enumerate(steps):
        ratio = ""
        if i and num(steps[i - 1][1]) > 0 and num(value) <= num(steps[i - 1][1]):
            ratio = f"<small>{dec(pct(value, steps[i - 1][1]))}% da etapa anterior</small>"
        funnel += f'<div class="adm-funnel-step"><strong>{n(value)}</strong><span>{label}</span>{ratio}</div>'
    funnel += f'<div class="adm-funnel-step muted"><strong>{n(ebook.get("closes"))}</strong><span>Fecharam sem cadastrar</span></div>'
    out.append(f'<section class="adm-card"><div class="adm-card-head"><h3>Funil do e-book</h3></div><div class="adm-funnel">{funnel}</div></section>')

    # ---------- QUANDO E COMO
    hours = "".join(
        f'<div class="{"hot" if num(h["sessions"]) / max_hour >= 0.5 else ""}" title="{h["hour"]}h: {n(h["sessions"])} visitas · {n(h["whatsapp"])} WhatsApp" '
        f'style="--lvl:{num(h["sessions"]) / max_hour:.3f}"><b>{h["hour"]}h</b><span>{n(h["sessions"])}</span></div>' for h in by_hour)
    device_rows = [
        f'<tr><td><b>{e(DEVICES.get(d["device"], "Não identificado" if d["device"] == "?" else d["device"]))}</b></td>'
        f'<td>{n(d["sessions"])} <small class="adm-muted">({dec(pct(d["sessions"], t.get("sessions")))}%)</small></td>'
        f'<td>{fmt_time(d["avg_seconds"])}</td><td>{n(d["whatsapp"])}</td></tr>' for d in dash.get("devices") or []]
    unknown = lambda r: "Não identificado" if r["name"] == "?" else r["name"]  # noqa: E731
    out.append(f'''<h2 class="adm-group" id="quando">Quando e como acessam</h2>
<div class="adm-grid2">
<section class="adm-card"><div class="adm-card-head"><h3>Horário das visitas</h3></div><div class="adm-hours">{hours}</div>
<h4>Dia da semana</h4>{bars(by_weekday, lambda r: WEEKDAYS[int(r["dow"])], lambda r: num(r["sessions"]))}</section>
<section class="adm-card"><div class="adm-card-head"><h3>Quanto tempo ficam</h3></div>
{bars(dash.get("durations") or [], lambda r: r["bucket"], lambda r: num(r["sessions"]))}
<h4>Até onde rolam a página</h4>
{bars(dash.get("scroll") or [], lambda r: "até o fim" if num(r["bucket"]) >= 100 else f'{int(num(r["bucket"]))}–{int(num(r["bucket"])) + 24}%', lambda r: num(r["sessions"]))}</section>
</div>
<div class="adm-grid2">
<section class="adm-card"><div class="adm-card-head"><h3>Aparelho</h3></div>{table(["Aparelho", "Visitas", "Tempo médio", "WhatsApp"], device_rows)}</section>
<section class="adm-card"><div class="adm-card-head"><h3>Navegador e sistema</h3></div>
{bars(dash.get("browsers") or [], unknown, lambda r: num(r["sessions"]))}<h4>Sistema</h4>
{bars(dash.get("os") or [], unknown, lambda r: num(r["sessions"]))}</section>
</div>''')

    # ---------- ORIGEM
    source_rows = [
        f'<tr><td><b>{e(s["source"])}</b></td><td>{n(s["sessions"])}</td><td>{fmt_time(s["avg_seconds"])}</td>'
        f'<td>{n(s["whatsapp"])} <small class="adm-muted">({dec(pct(s["whatsapp"], s["sessions"]))}%)</small></td><td>{n(s["leads"])}</td></tr>'
        for s in dash.get("sources") or []]
    campaigns = dash.get("campaigns") or []
    campaign_block = ""
    if campaigns:
        campaign_block = "<h4>Campanhas (UTM)</h4>" + table(["Campanha", "Fonte / meio", "Visitas", "WhatsApp", "Leads"], [
            f'<tr><td><b>{e(c["campaign"])}</b></td><td>{e(c["source"])} / {e(c["medium"])}</td><td>{n(c["sessions"])}</td>'
            f'<td>{n(c["whatsapp"])}</td><td>{n(c["leads"])}</td></tr>' for c in campaigns])
    city_rows = [
        f'<tr><td><b>{e(c["city"])}</b></td><td>{e(c.get("region") or "—")}</td><td>{n(c["sessions"])}</td><td>{n(c["whatsapp"])}</td><td>{n(c["leads"])}</td></tr>'
        for c in (dash.get("cities") or [])[:12]]
    out.append(f'''<h2 class="adm-group" id="origem">De onde vêm</h2>
<div class="adm-grid2">
<section class="adm-card"><div class="adm-card-head"><h3>Origem das visitas</h3></div>
{table(["Origem", "Visitas", "Tempo", "WhatsApp", "Leads"], source_rows)}{campaign_block}</section>
<div class="adm-stack">
<section class="adm-card"><div class="adm-card-head"><h3>Cidades</h3></div>{table(["Cidade", "Estado", "Visitas", "WhatsApp", "Leads"], city_rows)}</section>
<section class="adm-card"><div class="adm-card-head"><h3>Página de entrada</h3></div>
{bars(dash.get("landing_pages") or [], lambda r: page_name(r["page"]), lambda r: num(r["sessions"]))}</section>
</div></div>''')

    if keywords is None:
        kw = '<p class="adm-empty">Lista indisponível. Rode o arquivo <code>supabase_painel.sql</code> no SQL Editor do Supabase.</p>'
    elif not keywords:
        kw = ('<p class="adm-empty">Nenhuma visita de anúncio com palavra-chave no período. Elas aparecem depois que o '
              '“Sufixo do URL final” é configurado no Google Ads (utm_term={keyword}).</p>')
    else:
        kw = table(["Palavra-chave", "Campanha", "Visitas", "Tempo médio", "WhatsApp", "Leads"], [
            f'<tr><td><b>{e(k["keyword"])}</b></td><td>{e(k.get("campaign") or "—")}</td><td>{n(k["sessions"])}</td>'
            f'<td>{fmt_time(k["avg_seconds"])}</td><td>{n(k["whatsapp"])} <small class="adm-muted">({dec(pct(k["whatsapp"], k["sessions"]))}%)</small></td>'
            f'<td>{n(k["leads"])}</td></tr>' for k in keywords])
    out.append(f'<section class="adm-card"><div class="adm-card-head"><h3>Palavras-chave dos anúncios</h3></div>{kw}</section>')

    # ---------- PESSOAS
    lead_rows = []
    for lead in leads:
        phone = "".join(c for c in str(lead.get("phone") or "") if c.isdigit())
        wa = f'<a class="adm-wa" href="https://wa.me/{phone if phone.startswith("55") else "55" + phone}" target="_blank" rel="noopener noreferrer">Chamar</a>' if phone else ""
        origin = " / ".join(x for x in (lead.get("utm_source"), lead.get("utm_campaign")) if x) or "—"
        lead_rows.append(
            f'<tr><td>{fmt_date(lead.get("created_at"))}</td><td><b>{e(lead.get("name"))}</b></td>'
            f'<td><a href="mailto:{e(lead.get("email"))}">{e(lead.get("email"))}</a></td><td>{e(fmt_phone(lead.get("phone")))}</td>'
            f'<td>{e(lead.get("city") or "—")}</td><td>{e(origin)}</td><td>{wa}</td></tr>')
    leads_csv = "/admin/leads.csv" + ("?t=1" if include_test else "")
    out.append(f'''<h2 class="adm-group" id="pessoas">Visitantes e leads</h2>
<section class="adm-card"><div class="adm-card-head"><h3>Leads do e-book <span class="adm-count">{n(len(leads))}</span></h3>
<a class="adm-btn" href="{leads_csv}">{icon("download", 15)} Baixar todos (Excel)</a></div>
{table(["Data", "Nome", "E-mail", "WhatsApp", "Cidade", "Origem", ""], lead_rows, "Nenhum lead no período.") if lead_rows else '<p class="adm-empty">Nenhum lead no período.</p>'}</section>''')

    if visitors is None:
        vis = '<p class="adm-empty">Lista indisponível. Rode o arquivo <code>supabase_painel.sql</code> no SQL Editor do Supabase.</p>'
        count = ""
    elif not visitors:
        vis, count = '<p class="adm-empty">Nenhum visitante no período.</p>', ""
    else:
        count = f'<span class="adm-count">{n(len(visitors))}</span>'
        rows = []
        for v in visitors:
            who = (f'<b>{e(v["name"])}</b><small class="adm-sub">{e(fmt_phone(v.get("phone")))} · {e(v.get("email"))}</small>'
                   if v.get("name") else '<span class="adm-muted">Anônimo</span>')
            back = '<span class="adm-tag t-whatsapp" style="margin-left:6px">voltou</span>' if num(v["visits"]) > 1 else ""
            period_visits = f'<small class="adm-sub">{n(v["visits_period"])} no período</small>' if v["visits"] != v["visits_period"] else ""
            rows.append(
                f'<tr><td><code>{e(v["code"])}</code></td><td>{who}</td><td><b>{n(v["visits"])}</b>{back}{period_visits}</td>'
                f'<td>{fmt_date(v["first_seen"])}</td><td>{fmt_date(v["last_seen"])}</td><td>{fmt_time(v["total_seconds"])}</td>'
                f'<td>{n(v["whatsapp_visits"]) + "×" if num(v["whatsapp_visits"]) else "—"}</td>'
                f'<td>{n(v["phone_clicks"]) + "×" if num(v["phone_clicks"]) else "—"}</td>'
                f'<td>{e(v.get("city") or "—")}</td><td>{e(v.get("first_source") or "—")}</td></tr>')
        vis = table(["Código", "Quem é", "Visitas", "Primeira vez", "Última vez", "Tempo total", "WhatsApp", "Ligar", "Cidade", "Veio de"], rows)
        vis = vis.replace('class="adm-scroll"', 'class="adm-scroll tall"', 1)
    out.append(f'''<section class="adm-card"><div class="adm-card-head"><h3>Visitantes {count}</h3></div>{vis}
<p class="adm-note">Só entram no painel as pessoas que clicaram em “Aceitar análise” no aviso de privacidade. Cada navegador recebe um código
que vale por 30 dias. Nome e telefone aparecem quando a pessoa se cadastra no e-book. Se ela trocar de aparelho ou limpar o navegador, conta como visitante novo.</p></section>
<p class="adm-foot">Horário de Brasília. Visitas de teste (computador local, endereço da Vercel e admin logado) ficam fora dos números. Robôs são filtrados.</p>
</main>''')
    return document("Painel | Laboratório Santa Clara", "".join(out))


def leads_csv(rows):
    cols = ["created_at", "name", "email", "phone", "page", "utm_source", "utm_medium", "utm_campaign", "device", "city", "region"]

    def cell(col, value):
        if col == "created_at" and value:
            value = fmt_date(value)
        text = str(value if value is not None else "")
        if text and text[0] in "=+-@":  # evita fórmula ao abrir no Excel
            text = "'" + text
        return '"' + text.replace('"', '""') + '"'

    titles = ["Data", "Nome", "E-mail", "WhatsApp", "Página", "Origem", "Meio", "Campanha", "Aparelho", "Cidade", "Estado"]
    lines = [";".join(titles)] + [";".join(cell(c, r.get(c)) for c in cols) for r in rows]
    return "﻿" + "\n".join(lines)


def leads_filename():
    return quote(f"leads-santa-clara-{datetime.now(BRASILIA):%Y-%m-%d}.csv")
