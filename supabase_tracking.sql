create table if not exists public.santa_clara_tracking (
  id uuid primary key,
  kind text not null,
  session uuid not null,
  created timestamptz not null default now(),
  data jsonb not null
);

create index if not exists santa_clara_tracking_kind_created
  on public.santa_clara_tracking (kind, created desc, id desc);

alter table public.santa_clara_tracking enable row level security;
revoke all on public.santa_clara_tracking from public, anon, authenticated;
grant select, insert on public.santa_clara_tracking to service_role;
