-- Run once in the SQL Editor of a dedicated Supabase project. Safe to rerun.
begin;
create schema if not exists project514;
revoke all on schema project514 from public, anon, authenticated;
create table if not exists project514.entry (
    kind text not null,
    day text not null,
    payload text not null,
    primary key (kind, day)
);
revoke all on project514.entry from public, anon, authenticated;
alter table project514.entry enable row level security;

-- The phone can submit a daily summary only while its private token is enabled.
create or replace function public.project514_import(
    token text, sample_day date, workout_minutes integer default null, vo2_max numeric default null
) returns text language plpgsql security definer set search_path = pg_catalog as $$
declare
    expected text;
    zone text;
    local_today date;
begin
    perform pg_advisory_xact_lock(5140514);
    select payload::jsonb ->> 'digest' into expected from project514.entry where kind='phone' and day='';
    if expected is null or token is null or length(token) > 128 or
        encode(sha256(convert_to(token, 'UTF8')), 'hex') <> expected then
        raise exception 'Import disabled or token invalid' using errcode='42501';
    end if;
    select payload::jsonb ->> 'zone' into strict zone from project514.entry where kind='profile' and day='';
    local_today := (now() at time zone zone)::date;
    if sample_day is null or sample_day not between local_today - 31 and local_today
       or (workout_minutes is null and vo2_max is null)
       or workout_minutes not between 0 and 1440 or vo2_max not between 1 and 150 then
        raise exception 'Check sample date, units and values' using errcode='22023';
    end if;
    insert into project514.entry as existing(kind,day,payload)
    values ('health',to_char(sample_day,'YYYY-MM-DD'),
        jsonb_strip_nulls(jsonb_build_object('workout_minutes',workout_minutes,'vo2_max',vo2_max))::text)
    on conflict(kind,day) do update set payload=(existing.payload::jsonb || excluded.payload::jsonb)::text;
    return 'Saved';
end;
$$;
revoke all on function public.project514_import(text,date,integer,numeric) from public, anon, authenticated;
grant execute on function public.project514_import(text,date,integer,numeric) to anon;
notify pgrst, 'reload schema';
commit;
