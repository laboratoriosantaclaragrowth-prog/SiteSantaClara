-- =====================================================================
-- Laboratório Santa Clara — painel do site (visitas, cliques, seções, leads)
-- Rode este arquivo inteiro UMA vez no Supabase:
--   SQL Editor → New query → cole tudo → Run
-- Pode rodar de novo sem problema (ele só recria as funções).
-- =====================================================================

-- ---------- Tabelas ----------
create table if not exists public.sc_sessions (
  id               text primary key,               -- id aleatório da visita (gerado no navegador)
  visitor_id       text,                           -- id do aparelho (identifica quem volta)
  started_at       timestamptz not null default now(),
  last_seen_at     timestamptz not null default now(),
  active_seconds   integer not null default 0,     -- tempo com a aba visível e alguém mexendo
  pageviews        integer not null default 0,
  max_scroll       integer not null default 0,     -- % mais funda da página que a pessoa chegou
  landing_page     text,
  last_page        text,
  referrer         text,
  referrer_host    text,
  utm_source       text,
  utm_medium       text,
  utm_campaign     text,
  utm_term         text,
  utm_content      text,
  gclid            text,
  device           text,                           -- mobile | tablet | desktop
  os               text,
  browser          text,
  screen           text,
  language         text,
  timezone         text,
  country          text,
  region           text,
  city             text,
  hostname         text,
  is_returning     boolean not null default false,
  is_test          boolean not null default false,
  clicked_whatsapp boolean not null default false,
  converted_lead   boolean not null default false
);

create table if not exists public.sc_events (
  id          bigserial primary key,
  session_id  text not null references public.sc_sessions(id) on delete cascade,
  visitor_id  text,
  created_at  timestamptz not null default now(),
  type        text not null,   -- pageview | page_time | section_view | section_time | click | ebook_open | ebook_close | ebook_submit
  page        text,
  section     text,
  label       text,
  target      text,            -- whatsapp | phone | maps | email | internal | external | button | download
  href        text,
  value       numeric
);

create index if not exists sc_sessions_real_idx    on public.sc_sessions (is_test, started_at desc);
create index if not exists sc_sessions_seen_idx    on public.sc_sessions (last_seen_at desc);
create index if not exists sc_sessions_visitor_idx on public.sc_sessions (visitor_id);
create index if not exists sc_events_session_idx   on public.sc_events (session_id);
create index if not exists sc_events_visitor_idx   on public.sc_events (visitor_id);
create index if not exists sc_events_type_idx      on public.sc_events (type, created_at desc);

-- Segurança: ninguém de fora lê ou escreve direto. Só o servidor do site (chave secreta).
alter table public.sc_sessions enable row level security;
alter table public.sc_events   enable row level security;
revoke all on public.sc_sessions, public.sc_events from public, anon, authenticated;

-- ---------- Leads do e-book ----------
-- Os cadastros continuam na tabela santa_clara_tracking (tipo ebook_lead).
-- Esta visão só organiza as colunas para o painel.
create or replace view public.sc_leads with (security_invoker = true) as
select id,
       created                                        as created_at,
       data->>'name'                                  as name,
       data->>'email'                                 as email,
       data->>'phone'                                 as phone,
       data->>'visitor_id'                            as visitor_id,
       data->>'track_session'                         as session_id,
       coalesce(nullif(data->'current'->>'page', ''), nullif(data->'entry'->>'page', '')) as page,
       nullif(data->'entry'->>'utm_source', '')       as utm_source,
       nullif(data->'entry'->>'utm_medium', '')       as utm_medium,
       nullif(data->'entry'->>'utm_campaign', '')     as utm_campaign,
       nullif(data->>'city', '')                      as city,
       nullif(data->>'region', '')                    as region,
       nullif(data->>'device', '')                    as device,
       coalesce((data->>'is_test')::boolean, false)   as is_test
from public.santa_clara_tracking
where kind = 'ebook_lead';
revoke all on public.sc_leads from public, anon, authenticated;
grant select on public.sc_leads to service_role;

-- Os cadastros feitos antes deste painel vieram dos testes (computador local e Vercel).
-- Eles continuam salvos e aparecem quando você clica em "Incluir testes".
update public.santa_clara_tracking
   set data = data || '{"is_test": true}'::jsonb
 where kind = 'ebook_lead' and not (data ? 'is_test');

-- ---------- Recebe um lote de eventos do site ----------
create or replace function public.sc_track_batch(p jsonb)
returns void
language plpgsql
security definer
set search_path = public
as $$
declare
  s jsonb := p->'session';
  v_sid text := s->>'id';
  v_events jsonb := coalesce(p->'events', '[]'::jsonb);
begin
  if v_sid is null or length(v_sid) > 64 then return; end if;
  if jsonb_typeof(v_events) <> 'array' then v_events := '[]'::jsonb; end if;

  insert into sc_sessions as ss (
    id, visitor_id, started_at, last_seen_at, active_seconds, max_scroll,
    landing_page, last_page, referrer, referrer_host,
    utm_source, utm_medium, utm_campaign, utm_term, utm_content, gclid,
    device, os, browser, screen, language, timezone,
    country, region, city, is_returning, is_test, hostname
  ) values (
    v_sid, left(s->>'visitor_id', 64), now(), now(),
    least(greatest(coalesce((s->>'active_seconds')::int, 0), 0), 14400),
    least(greatest(coalesce((s->>'max_scroll')::int, 0), 0), 100),
    left(s->>'landing_page', 300), left(s->>'page', 300), left(s->>'referrer', 500), left(s->>'referrer_host', 200),
    left(s->>'utm_source', 120), left(s->>'utm_medium', 120), left(s->>'utm_campaign', 200),
    left(s->>'utm_term', 200), left(s->>'utm_content', 200), left(s->>'gclid', 200),
    left(s->>'device', 20), left(s->>'os', 40), left(s->>'browser', 40), left(s->>'screen', 20),
    left(s->>'language', 20), left(s->>'timezone', 60),
    left(s->>'country', 60), left(s->>'region', 80), left(s->>'city', 80),
    coalesce((s->>'is_returning')::boolean, false),
    coalesce((s->>'is_test')::boolean, false),
    left(s->>'hostname', 120)
  )
  on conflict (id) do update set
    last_seen_at   = now(),
    active_seconds = greatest(ss.active_seconds, least(greatest(coalesce((s->>'active_seconds')::int, 0), 0), 14400)),
    max_scroll     = greatest(ss.max_scroll, least(greatest(coalesce((s->>'max_scroll')::int, 0), 0), 100)),
    last_page      = coalesce(left(s->>'page', 300), ss.last_page),
    country        = coalesce(ss.country, left(s->>'country', 60)),
    region         = coalesce(ss.region, left(s->>'region', 80)),
    city           = coalesce(ss.city, left(s->>'city', 80)),
    is_test        = ss.is_test or coalesce((s->>'is_test')::boolean, false);

  insert into sc_events (session_id, visitor_id, created_at, type, page, section, label, target, href, value)
  select v_sid,
         left(s->>'visitor_id', 64),
         case when (e->>'ts') ~ '^\d{4}-\d{2}-\d{2}T' and (e->>'ts')::timestamptz between now() - interval '1 day' and now() + interval '5 minutes'
              then (e->>'ts')::timestamptz else now() end,
         left(e->>'type', 30),
         left(e->>'page', 300),
         left(e->>'section', 60),
         left(e->>'label', 120),
         left(e->>'target', 30),
         left(e->>'href', 300),
         case when (e->>'value') ~ '^-?\d+(\.\d+)?$' then least((e->>'value')::numeric, case when e->>'type' = 'page_time' then 14400 else 1800 end) else null end
  from jsonb_array_elements(v_events) as e
  where e->>'type' in ('pageview','page_time','section_view','section_time','click','ebook_open','ebook_close','ebook_submit')
  limit 200;

  update sc_sessions set
    pageviews        = pageviews + (select count(*) from jsonb_array_elements(v_events) e where e->>'type' = 'pageview'),
    clicked_whatsapp = clicked_whatsapp or exists (select 1 from jsonb_array_elements(v_events) e where e->>'type' = 'click' and e->>'target' = 'whatsapp'),
    converted_lead   = converted_lead   or exists (select 1 from jsonb_array_elements(v_events) e where e->>'type' = 'ebook_submit')
  where id = v_sid;
end;
$$;

-- ---------- Painel ----------
-- Regras:
--  * Visitas = visitas que COMEÇARAM no período (horário de Brasília).
--  * Eventos (seções, cliques) = os dessas mesmas visitas, para os números baterem entre si.
--  * Leads = cadastros feitos no período.
--  * Testes (computador local, Vercel e admin logado) ficam fora, a não ser que p_include_test = true.
create or replace function public.sc_admin_dashboard(p_from timestamptz, p_to timestamptz, p_include_test boolean default false)
returns jsonb
language sql
stable
security definer
set search_path = public
as $$
with
s as (
  select * from sc_sessions
  where started_at >= p_from and started_at < p_to
    and (p_include_test or not is_test)
),
e as (
  select ev.* from sc_events ev join s on s.id = ev.session_id
),
l as (
  select * from sc_leads where created_at >= p_from and created_at < p_to and (p_include_test or not is_test)
),
tot as (select count(*)::numeric n from s)
select jsonb_build_object(
  'totals', (
    select jsonb_build_object(
      'sessions',          count(*),
      'visitors',          count(distinct visitor_id),
      'new_visitors',      count(*) filter (where not is_returning),
      'returning',         count(*) filter (where is_returning),
      'avg_seconds',       coalesce(round(avg(active_seconds)), 0),
      'median_seconds',    coalesce(round(percentile_cont(0.5) within group (order by active_seconds)::numeric), 0),
      'engaged',           count(*) filter (where active_seconds >= 10 or pageviews > 1),
      'bounce_rate',       coalesce(round(100.0 * count(*) filter (where active_seconds < 10 and pageviews <= 1) / nullif(count(*),0), 1), 0),
      'avg_scroll',        coalesce(round(avg(max_scroll)), 0),
      'pageviews',         coalesce(sum(pageviews), 0),
      'whatsapp_sessions', count(*) filter (where clicked_whatsapp),
      'whatsapp_rate',     coalesce(round(100.0 * count(*) filter (where clicked_whatsapp) / nullif(count(*),0), 1), 0),
      'whatsapp_clicks',   (select count(*) from e where type = 'click' and target = 'whatsapp'),
      'phone_clicks',      (select count(*) from e where type = 'click' and target = 'phone'),
      'maps_clicks',       (select count(*) from e where type = 'click' and target = 'maps'),
      'leads',             (select count(*) from l),
      'lead_rate',         coalesce(round(100.0 * (select count(*) from l) / nullif(count(*),0), 1), 0)
    ) from s
  ),
  'online_now', (select count(*) from sc_sessions where last_seen_at > now() - interval '5 minutes' and (p_include_test or not is_test)),
  'by_day', coalesce((
    select jsonb_agg(x order by x->>'day') from (
      select jsonb_build_object(
        'day', d::date,
        'sessions', (select count(*) from s where (started_at at time zone 'America/Sao_Paulo')::date = d::date),
        'leads',    (select count(*) from l where (created_at at time zone 'America/Sao_Paulo')::date = d::date),
        'whatsapp', (select count(*) from s where clicked_whatsapp and (started_at at time zone 'America/Sao_Paulo')::date = d::date)
      ) x
      from generate_series((p_from at time zone 'America/Sao_Paulo')::date, ((p_to - interval '1 second') at time zone 'America/Sao_Paulo')::date, interval '1 day') d
    ) t), '[]'::jsonb),
  'by_hour', coalesce((
    select jsonb_agg(jsonb_build_object('hour', g.h,
      'sessions', (select count(*) from s where extract(hour from started_at at time zone 'America/Sao_Paulo') = g.h),
      'whatsapp', (select count(*) from s where clicked_whatsapp and extract(hour from started_at at time zone 'America/Sao_Paulo') = g.h)) order by g.h)
    from generate_series(0,23) g(h)), '[]'::jsonb),
  'by_weekday', coalesce((
    select jsonb_agg(jsonb_build_object('dow', g.d, 'sessions', (select count(*) from s where extract(dow from started_at at time zone 'America/Sao_Paulo') = g.d)) order by g.d)
    from generate_series(0,6) g(d)), '[]'::jsonb),
  'sections', coalesce((
    select jsonb_agg(x order by (x->>'reach')::numeric desc) from (
      select jsonb_build_object(
        'section', section,
        'sessions', count(distinct session_id) filter (where type = 'section_view'),
        'reach', round(100.0 * count(distinct session_id) filter (where type = 'section_view') / nullif((select n from tot),0), 1),
        'total_seconds', coalesce(round(sum(value) filter (where type = 'section_time')), 0),
        'avg_seconds', coalesce(round(sum(value) filter (where type = 'section_time') / nullif(count(distinct session_id) filter (where type = 'section_view'),0), 1), 0)
      ) x
      from e where section is not null and type in ('section_view','section_time')
      group by section
    ) t), '[]'::jsonb),
  'clicks', coalesce((
    select jsonb_agg(x order by (x->>'clicks')::int desc) from (
      select jsonb_build_object('label', label, 'target', target, 'section', section, 'clicks', count(*), 'sessions', count(distinct session_id)) x
      from e where type = 'click'
      group by label, target, section
      order by count(*) desc limit 40
    ) t), '[]'::jsonb),
  'click_targets', coalesce((
    select jsonb_agg(jsonb_build_object('target', target, 'clicks', c, 'sessions', ss) order by c desc)
    from (select coalesce(target,'outro') target, count(*) c, count(distinct session_id) ss from e where type = 'click' group by 1) t), '[]'::jsonb),
  'whatsapp_by_section', coalesce((
    select jsonb_agg(jsonb_build_object('section', section, 'clicks', c) order by c desc)
    from (select coalesce(section,'Outro') section, count(*) c from e where type = 'click' and target = 'whatsapp' group by 1) t), '[]'::jsonb),
  'pages', coalesce((
    select jsonb_agg(x order by (x->>'views')::int desc) from (
      select jsonb_build_object(
        'page', pg,
        'views', count(*) filter (where type = 'pageview'),
        'sessions', count(distinct session_id) filter (where type = 'pageview'),
        'reach', round(100.0 * count(distinct session_id) filter (where type = 'pageview') / nullif((select n from tot),0), 1),
        'entrances', (select count(*) from s where coalesce(nullif(rtrim(s.landing_page,'/'),''),'/') = z.pg),
        'avg_seconds', coalesce(round(sum(value) filter (where type = 'page_time') / nullif(count(distinct session_id) filter (where type = 'pageview'),0)), 0),
        'whatsapp', count(*) filter (where type = 'click' and target = 'whatsapp'),
        'whatsapp_sessions', count(distinct session_id) filter (where type = 'click' and target = 'whatsapp')
      ) x
      from (select ev.*, coalesce(nullif(rtrim(split_part(ev.page,'?',1),'/'),''),'/') pg from e ev where ev.type in ('pageview','page_time','click')) z
      group by pg
      having count(*) filter (where type = 'pageview') > 0
      order by count(*) filter (where type = 'pageview') desc
      limit 40
    ) t), '[]'::jsonb),
  'landing_pages', coalesce((
    select jsonb_agg(jsonb_build_object('page', landing_page, 'sessions', c, 'whatsapp', wa) order by c desc)
    from (select coalesce(nullif(rtrim(landing_page,'/'),''),'/') landing_page, count(*) c, count(*) filter (where clicked_whatsapp) wa from s group by 1 order by c desc limit 15) t), '[]'::jsonb),
  'sources', coalesce((
    select jsonb_agg(jsonb_build_object('source', src, 'sessions', c, 'leads', ld, 'whatsapp', wa, 'avg_seconds', a) order by c desc)
    from (
      select case
               when utm_source is not null and utm_source <> '' then utm_source || coalesce(' / ' || nullif(utm_medium,''), '')
               when gclid is not null and gclid <> '' then 'google / anúncio'
               when referrer_host ~ '(^|\.)google\.' then 'google / orgânico'
               when referrer_host ~ '(^|\.)bing\.com$' then 'bing / orgânico'
               when referrer_host ~ '(chatgpt\.com|openai\.com|perplexity\.ai|gemini\.google|copilot\.microsoft)' then referrer_host || ' / IA'
               when referrer_host ~ '(instagram|facebook|fb)\.' then referrer_host || ' / social'
               when referrer_host is not null and referrer_host <> '' then referrer_host
               else 'Direto (digitou ou link salvo)'
             end src,
             count(*) c, count(*) filter (where converted_lead) ld, count(*) filter (where clicked_whatsapp) wa, round(avg(active_seconds)) a
      from s group by 1 order by c desc limit 20) t), '[]'::jsonb),
  'campaigns', coalesce((
    select jsonb_agg(jsonb_build_object('campaign', utm_campaign, 'source', utm_source, 'medium', utm_medium, 'sessions', c, 'leads', ld, 'whatsapp', wa) order by c desc)
    from (select utm_campaign, utm_source, utm_medium, count(*) c, count(*) filter (where converted_lead) ld, count(*) filter (where clicked_whatsapp) wa
          from s where utm_campaign is not null group by 1,2,3 order by c desc limit 20) t), '[]'::jsonb),
  'devices', coalesce((
    select jsonb_agg(jsonb_build_object('device', device, 'sessions', c, 'avg_seconds', a, 'whatsapp', wa) order by c desc)
    from (select coalesce(device,'?') device, count(*) c, round(avg(active_seconds)) a, count(*) filter (where clicked_whatsapp) wa from s group by 1) t), '[]'::jsonb),
  'browsers', coalesce((
    select jsonb_agg(jsonb_build_object('name', browser, 'sessions', c) order by c desc)
    from (select coalesce(browser,'?') browser, count(*) c from s group by 1 order by c desc limit 8) t), '[]'::jsonb),
  'os', coalesce((
    select jsonb_agg(jsonb_build_object('name', os, 'sessions', c) order by c desc)
    from (select coalesce(os,'?') os, count(*) c from s group by 1 order by c desc limit 8) t), '[]'::jsonb),
  'cities', coalesce((
    select jsonb_agg(jsonb_build_object('city', city, 'region', region, 'sessions', c, 'leads', ld, 'whatsapp', wa) order by c desc)
    from (select coalesce(city, 'Não identificada') city, region, count(*) c, count(*) filter (where converted_lead) ld, count(*) filter (where clicked_whatsapp) wa
          from s group by 1,2 order by c desc limit 25) t), '[]'::jsonb),
  'scroll', coalesce((
    select jsonb_agg(jsonb_build_object('bucket', b, 'sessions', c) order by b)
    from (select least(max_scroll / 25 * 25, 100) b, count(*) c from s group by 1) t), '[]'::jsonb),
  'durations', coalesce((
    select jsonb_agg(jsonb_build_object('bucket', b, 'sessions', c) order by o)
    from (
      select case when active_seconds < 10 then '0–10s' when active_seconds < 30 then '10–30s'
                  when active_seconds < 60 then '30s–1min' when active_seconds < 180 then '1–3min'
                  when active_seconds < 600 then '3–10min' else '10min+' end b,
             min(active_seconds) o, count(*) c
      from s group by 1) t), '[]'::jsonb),
  'ebook', jsonb_build_object(
    'opens',        (select count(distinct session_id) from e where type = 'ebook_open'),
    'offer_clicks', (select count(distinct session_id) from e where type = 'click' and section = 'Pop-up do e-book' and label ilike 'receber%'),
    'closes',       (select count(distinct session_id) from e where type = 'ebook_close'),
    'submits',      (select count(*) from l)
  )
);
$$;

-- ---------- Lista de visitantes ----------
-- Cada navegador recebe um código aleatório na primeira visita (válido por 30 dias).
-- Se a pessoa se cadastrar no e-book, o nome e o telefone ficam ligados ao código.
create or replace function public.sc_admin_visitors(p_from timestamptz, p_to timestamptz, p_include_test boolean default false)
returns jsonb
language sql
stable
security definer
set search_path = public
as $$
with active as (
  select distinct visitor_id from sc_sessions
  where started_at >= p_from and started_at < p_to and visitor_id is not null
    and (p_include_test or not is_test)
),
v as (
  select s.visitor_id,
         count(*) visits,
         count(*) filter (where s.started_at >= p_from and s.started_at < p_to) visits_period,
         min(s.started_at) first_seen,
         max(s.last_seen_at) last_seen,
         sum(s.active_seconds) total_seconds,
         sum(s.pageviews) pageviews,
         count(*) filter (where s.clicked_whatsapp) whatsapp_visits,
         (array_agg(s.city order by s.started_at desc) filter (where s.city is not null))[1] city,
         (array_agg(s.device order by s.started_at desc))[1] device,
         (array_agg(case
            when s.gclid is not null or s.utm_medium in ('cpc','ppc','paid','paid_social') then
              'Anúncio ' || initcap(coalesce(nullif(s.utm_source,''),'pago')) || coalesce(' · ' || nullif(s.utm_campaign,''), '')
            when nullif(s.utm_source,'') is not null then s.utm_source || coalesce(' / ' || nullif(s.utm_medium,''), '')
            when s.referrer_host ~ '(^|\.)google\.' then 'Google (busca orgânica)'
            when nullif(s.referrer_host,'') is not null then s.referrer_host
            else 'Direto' end order by s.started_at))[1] first_source
  from sc_sessions s join active a on a.visitor_id = s.visitor_id
  where (p_include_test or not s.is_test)
  group by s.visitor_id
)
select coalesce(jsonb_agg(x order by (x->>'last_seen') desc), '[]'::jsonb) from (
  select jsonb_build_object(
    'code', upper(left(replace(v.visitor_id,'-',''), 6)),
    'visits', v.visits, 'visits_period', v.visits_period,
    'first_seen', v.first_seen, 'last_seen', v.last_seen,
    'total_seconds', v.total_seconds, 'pageviews', v.pageviews,
    'whatsapp_visits', v.whatsapp_visits,
    'phone_clicks', (select count(*) from sc_events e where e.visitor_id = v.visitor_id and e.type = 'click' and e.target = 'phone'),
    'city', v.city, 'device', v.device, 'first_source', v.first_source,
    'name', l.name, 'phone', l.phone, 'email', l.email
  ) x
  from v
  left join lateral (select name, phone, email from sc_leads where sc_leads.visitor_id = v.visitor_id order by created_at desc limit 1) l on true
  order by v.last_seen desc
  limit 200
) t;
$$;

-- ---------- Palavras-chave dos anúncios (utm_term) ----------
create or replace function public.sc_admin_keywords(p_from timestamptz, p_to timestamptz, p_include_test boolean default false)
returns jsonb
language sql
stable
security definer
set search_path = public
as $$
select coalesce(jsonb_agg(x order by (x->>'sessions')::int desc), '[]'::jsonb) from (
  select jsonb_build_object(
    'keyword', lower(utm_term),
    'campaign', (array_agg(utm_campaign order by started_at desc))[1],
    'sessions', count(*),
    'avg_seconds', round(avg(active_seconds)),
    'whatsapp', count(*) filter (where clicked_whatsapp),
    'leads', count(*) filter (where converted_lead)
  ) x
  from sc_sessions
  where started_at >= p_from and started_at < p_to
    and (p_include_test or not is_test)
    and nullif(utm_term, '') is not null
  group by lower(utm_term)
  order by count(*) desc
  limit 50
) t;
$$;

revoke all on function public.sc_track_batch(jsonb) from public, anon, authenticated;
revoke all on function public.sc_admin_dashboard(timestamptz, timestamptz, boolean) from public, anon, authenticated;
revoke all on function public.sc_admin_visitors(timestamptz, timestamptz, boolean) from public, anon, authenticated;
revoke all on function public.sc_admin_keywords(timestamptz, timestamptz, boolean) from public, anon, authenticated;
grant execute on function public.sc_track_batch(jsonb) to service_role;
grant execute on function public.sc_admin_dashboard(timestamptz, timestamptz, boolean) to service_role;
grant execute on function public.sc_admin_visitors(timestamptz, timestamptz, boolean) to service_role;
grant execute on function public.sc_admin_keywords(timestamptz, timestamptz, boolean) to service_role;
