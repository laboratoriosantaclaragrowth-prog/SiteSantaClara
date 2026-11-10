"""Render the authenticated traffic dashboard."""

import json
from datetime import datetime, timedelta, timezone
from html import escape
from urllib.parse import urlencode
from tracking_metrics import PERIODS


BRASILIA = timezone(timedelta(hours=-3))
UTM_KEYS = ("utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term", "utm_id")

ICONS = {
    "whatsapp": '<path d="M20 11.5a8 8 0 0 1-11.8 7L4 20l1.4-4.1A8 8 0 1 1 20 11.5Z"/><path d="M9 9c.3 2.5 2 4.2 4.5 5l1-1"/>',
    "users": '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2m20 0v-2a4 4 0 0 0-3-3.9M16 3.1a4 4 0 0 1 0 7.8"/><circle cx="9" cy="7" r="4"/>',
    "sessions": '<path d="M3 12h4l3-8 4 16 3-8h4"/>',
    "pages": '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 9h18m-14 5h5m-5 3h10"/>',
    "leads": '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3 7 9 6 9-6"/>',
}


def icon(name):
    return (f'<svg viewBox="0 0 24 24" width="21" height="21" fill="none" stroke="currentColor" '
            f'stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{ICONS[name]}</svg>')


def number(value):
    return f"{value:,}".replace(",", ".")


def local_time(value):
    try:
        parsed = value if isinstance(value, datetime) else datetime.fromisoformat(value)
        parsed = parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(BRASILIA).strftime("%d/%m/%Y · %H:%M:%S")
    except (ValueError, TypeError):
        return "—"


def render_hour_chart(hours):
    peak = max(hours, default=0)
    if not peak:
        return '<p class="empty-panel">As visualizações aparecerão aqui quando o site registrar acessos.</p>'
    bars = []
    for hour, value in enumerate(hours):
        time = f"{hour:02d}h"
        caption = f"{time} · {number(value)} visualizações"
        height = 100 * value / peak
        bars.append(
            f'<li title="{caption}"><div class="bar-track">'
            f'<span class="hour-bar" style="--height:{height:.2f}%"></span></div>'
            f'<span class="hour-tick" aria-hidden="true">{time if hour % 4 == 0 else ""}</span>'
            f'<span class="sr-only">{caption}</span></li>'
        )
    return f'<ol class="hour-chart" aria-label="Visualizações em cada hora">{"".join(bars)}</ol>'


def render_breakdown(values, empty):
    ordered = sorted(values.items(), key=lambda item: (-item[1], item[0]))[:6]
    if not ordered:
        return f'<p class="empty-panel">{escape(empty)}</p>'
    total = sum(values.values())
    items = []
    for label, count in ordered:
        percent = count / total * 100 if total else 0
        items.append(
            f'<li><div class="breakdown-row"><span>{escape(label)}</span>'
            f'<strong>{number(count)}</strong></div><div class="breakdown-track" aria-hidden="true">'
            f'<span style="--width:{percent:.2f}%"></span></div></li>'
        )
    return f'<ul class="breakdown">{"".join(items)}</ul>'


def render_activity_row(row, labels):
    created, event, session, raw = row
    data = json.loads(raw) if isinstance(raw, str) else raw
    current = data.get("current") or {}
    entry = data.get("entry") or {}
    lead = event == "ebook_lead"
    contact = " · ".join(str(data[key]) for key in ("name", "email", "phone") if data.get(key))
    consent = "Aceito" if data.get("marketing") else "Não aceito"
    entry_utms = " · ".join(f"{key}={entry[key]}" for key in UTM_KEYS if entry.get(key))
    current_utms = " · ".join(f"{key}={current[key]}" for key in UTM_KEYS if current.get(key))
    details = [
        ("Contato", contact if lead else None),
        ("Sessão", session),
        ("Entrada", entry.get("page")),
        ("Referência", entry.get("referrer")),
        ("UTMs de entrada", entry_utms),
        ("UTMs atuais", current_utms),
        ("Aparelho", data.get("device")),
        ("Cidade estimada", data.get("city")),
        ("Bairro", data.get("neighborhood")),
        ("Consentimento de marketing", consent if lead else None),
    ]
    detail_markup = "".join(
        f"<div><dt>{label}</dt><dd>{escape(str(value))}</dd></div>" for label, value in details if value
    )
    origin = entry.get("utm_source") or entry.get("referrer") or "Sem referência"
    action = "E-book solicitado" if lead else data.get("target") or data.get("reason")
    badge = " lead" if lead else ""
    return (
        f'<tr><td class="time">{local_time(created)}</td>'
        f'<td><span class="badge{badge}">{escape(labels.get(event, event))}</span></td>'
        f'<td><strong>{escape(str(current.get("page") or "—"))}</strong>'
        f'<small>{escape(str(origin))}</small></td>'
        f'<td>{escape(str(action or "—"))}</td>'
        f'<td><details><summary>Ver detalhes</summary><dl>{detail_markup}</dl></details></td></tr>'
    )


def event_url(kind, page=1, *, period, anchor="#atividade"):
    query = {"periodo": period}
    if kind:
        query["tipo"] = kind
    if page > 1:
        query["pagina"] = page
    return f"/admin/?{escape(urlencode(query))}{anchor}"


def render_dashboard_html(*, counts, rows, kind, page, labels, metrics, period="7d"):
    visitors = metrics.get("visitors")
    sessions = metrics.get("sessions")
    views = metrics.get("views", counts.get("page_view", 0))
    leads = counts.get("ebook_lead", 0)
    identified = metrics.get("identified_views", 0)
    cards = [
        ("users", "Navegadores estimados", visitors, f"{number(identified)} visualizações com identificador"),
        ("sessions", "Sessões", sessions, "Visitas com pelo menos uma página vista"),
        ("pages", "Páginas vistas", views, "Visualizações registradas"),
        ("leads", "Cadastros", leads, "Formulários de e-book recebidos"),
        ("whatsapp", "Cliques no WhatsApp", counts.get("whatsapp_click", 0), "Aberturas do link de atendimento"),
    ]
    card_markup = "".join(
        f'<article class="metric"><span class="metric-icon">{icon(symbol)}</span>'
        f'<h2>{label}</h2><strong>{number(value) if value is not None else "—"}</strong>'
        f'<p>{description}</p></article>'
        for symbol, label, value, description in cards
    )
    active = ' aria-current="page"'
    periods = "".join(
        f'<a class="period" href="{event_url(kind, period=key, anchor="")}"'
        f'{active if key == period else ""}>{label}</a>'
        for key, label in PERIODS.items()
    )
    filters = "".join(
        f'<a href="{event_url(key, period=period)}"{active if key == kind else ""}>{escape(label)}'
        f' <span>{number(counts.get(key, 0))}</span></a>'
        for key, label in labels.items()
    )
    total = counts.get(kind, 0) if kind else sum(counts.get(key, 0) for key in labels)
    previous = f'<a href="{event_url(kind, page - 1, period=period)}">← Anterior</a>' if page > 1 else ""
    following = f'<a href="{event_url(kind, page + 1, period=period)}">Próxima →</a>' if page * 100 < total else ""
    activity = "".join(render_activity_row(row, labels) for row in rows)
    if not activity:
        activity = '<tr><td colspan="5" class="empty-panel">Nenhum evento encontrado nesta página.</td></tr>'

    hours = render_hour_chart(metrics.get("hours") or [])
    devices = render_breakdown(metrics.get("devices") or {}, "Ainda não há dados sobre aparelhos.")
    cities = render_breakdown(metrics.get("cities") or {}, "Cidade indisponível para os acessos registrados.")
    neighborhoods = render_breakdown(metrics.get("neighborhoods") or {}, "Os dados de acesso não indicam o bairro com precisão.")
    return f"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Painel Santa Clara | Visão geral</title>
  <link rel="icon" href="/logo.png">
  <link rel="stylesheet" href="/assets/admin-dashboard.css">
</head>
<body>
  <header class="masthead">
    <div class="wrap masthead-inner">
      <div class="brand"><img src="/logo.png" alt="" width="42" height="42"><div><strong>Santa Clara</strong><span>Administração</span></div></div>
      <nav aria-label="Navegação do painel"><a href="#visao-geral">Visão geral</a><a href="#atividade">Atividade</a></nav>
    </div>
  </header>
  <main id="visao-geral" class="wrap">
    <div class="hero">
      <div>
        <p class="eyebrow">PAINEL DO LABORATÓRIO</p>
        <h1>Visão geral do site</h1>
        <p>Acompanhe o tráfego, a origem dos acessos e os cadastros do e-book.</p>
      </div>
      <nav class="periods" aria-label="Período dos dados">{periods}</nav>
    </div>
    <section aria-label="Indicadores principais" class="metrics">{card_markup}</section>
    <p class="measurement-note">Novas métricas de audiência incluem apenas visitas com análise autorizada. O histórico pode incluir registros da configuração anterior. Cadastros do e-book são contabilizados separadamente.</p>
    <section aria-label="Perfil dos acessos" class="analytics">
      <article class="panel hours">
        <h2>Horários de acesso</h2><p>Visualizações por hora no fuso de Brasília</p>{hours}
      </article>
      <article class="panel">
        <h2>Tipo de aparelho</h2><p>Visualizações por categoria de dispositivo</p>{devices}
      </article>
      <article class="panel">
        <h2>Cidades</h2><p>Localização aproximada, quando disponível</p>{cities}
      </article>
      <article class="panel">
        <h2>Bairros</h2><p>Distribuição quando existe localização suficiente</p>{neighborhoods}
      </article>
    </section>
    <section id="atividade" class="panel activity">
      <div class="activity-header"><h2>Atividade registrada</h2><p>Consulte os acessos, cliques e cadastros individuais.</p></div>
      <nav class="filters" aria-label="Filtrar por evento">
        <a href="{event_url("", period=period)}"{active if not kind else ""}>Todos</a>{filters}
      </nav>
      <div class="table-scroll" tabindex="0" role="region" aria-label="Tabela de atividades">
        <table>
          <thead><tr><th scope="col">Data e hora</th><th scope="col">Evento</th><th scope="col">Página e origem</th><th scope="col">Ação</th><th scope="col">Detalhes</th></tr></thead>
          <tbody>{activity}</tbody>
        </table>
      </div>
      <div class="pagination">
        <span>{number(total)} registros · Página {page}</span>
        <nav aria-label="Paginação">{previous}{following}</nav>
      </div>
    </section>
    <footer>Laboratório Santa Clara · Painel de acesso restrito</footer>
  </main>
</body>
</html>"""
