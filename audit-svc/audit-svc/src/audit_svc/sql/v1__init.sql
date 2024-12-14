CREATE TABLE IF NOT EXISTS audit_event (
  event_id int8 GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  event_ts timestamptz not null,
  application_name text not null,
  event_kind varchar(126) not null,
  payload jsonb not null
);
