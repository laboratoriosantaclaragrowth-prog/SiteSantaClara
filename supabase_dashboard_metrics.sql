begin;

create or replace function public.santa_clara_dashboard_metrics()
returns jsonb
language sql stable security invoker
set search_path = ''
as $$
  with views as materialized (
    select
      session,
      extract(hour from created at time zone 'America/Sao_Paulo')::int as hour,
      nullif(data ->> 'visitor_id', '') as visitor,
      coalesce(nullif(data ->> 'device', ''), 'Não identificado') as device,
      coalesce(nullif(data ->> 'city', ''), 'Não identificado') as city,
      coalesce(nullif(data ->> 'neighborhood', ''), 'Não identificado') as neighborhood
    from public.santa_clara_tracking
    where kind = 'page_view'
  ),
  totals as (
    select count(*) as views, count(visitor) as identified_views,
      count(distinct visitor) as visitors, count(distinct session) as sessions
    from views
  ),
  hourly as (
    select hour, count(*) as total from views group by hour
  ),
  device_totals as (
    select device, count(*) as total from views group by device
  ),
  city_totals as (
    select city, count(*) as total from views group by city
  ),
  neighborhood_totals as (
    select neighborhood, count(*) as total from views group by neighborhood
  )
  select to_jsonb(totals) || jsonb_build_object(
    'hours', (
      select jsonb_agg(coalesce(hourly.total, 0) order by clock.hour)
      from generate_series(0, 23) as clock(hour)
      left join hourly using (hour)
    ),
    'devices', coalesce((select jsonb_object_agg(device, total) from device_totals), '{}'::jsonb),
    'cities', coalesce((select jsonb_object_agg(city, total) from city_totals), '{}'::jsonb),
    'neighborhoods', coalesce((select jsonb_object_agg(neighborhood, total) from neighborhood_totals), '{}'::jsonb)
  ) from totals;
$$;

revoke all on function public.santa_clara_dashboard_metrics() from public, anon, authenticated;
grant execute on function public.santa_clara_dashboard_metrics() to service_role;

commit;
