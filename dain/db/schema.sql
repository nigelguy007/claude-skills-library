-- Dain · Postgres schema (e.g. Supabase). The deployment shape of src/brain/store.ts,
-- src/gate.ts, src/state.ts and src/events.ts. Not yet wired to the code: the tests and
-- demo run on the in-memory store. An adapter implementing the same methods is the next
-- engineering step.

-- Chronicle: append-only. Anything an agent writes lands here first.
create table chronicle (
  id          uuid primary key default gen_random_uuid(),
  kind        text not null,
  speaker_id  text,
  payload     jsonb not null,
  at          timestamptz not null default now()
);
create index chronicle_kind_speaker on chronicle (kind, speaker_id, at);
-- Enforce append-only for the application role.
revoke update, delete on chronicle from public;

-- Canon: versioned, human-approved facts. Only a named human moves a record here.
create table canon (
  kind             text not null,
  key              text not null,
  version          int  not null,
  value            jsonb not null,
  approved_by      text not null check (length(approved_by) > 0),
  approved_role    text not null check (approved_role in ('speaker', 'specialist', 'product_lead')),
  approved_at      timestamptz not null default now(),
  source_chronicle uuid references chronicle (id),
  primary key (kind, key, version)
);
revoke update, delete on canon from public;

-- C0 state machines.
create table item_state (
  entity       text not null check (entity in ('Speaker', 'ContentItem', 'Enquiry', 'AssetPack')),
  id           text not null,
  speaker_id   text not null,
  state        text not null,
  revise_count int  not null default 0 check (revise_count <= 3),
  entered_at   timestamptz not null default now(),
  primary key (entity, id)
);
create index item_state_waiting on item_state (state, entered_at);

-- Action Gate.
create table approval_token (
  id           uuid primary key default gen_random_uuid(),
  item_id      text not null,
  content_hash text not null,
  approver     text not null,
  role         text not null,
  expires_at   timestamptz not null,
  used         boolean not null default false,
  voided       boolean not null default false
);
create table execution (
  idempotency_key text primary key,          -- at most one external action per key
  token_id        uuid not null references approval_token (id),
  status          text not null check (status in ('pending', 'done')),
  result          text,
  updated_at      timestamptz not null default now()
);

-- B3 review items.
create table review_item (
  id         text primary key,
  entity     text not null,
  speaker_id text not null,
  content    text not null,
  original   text not null,
  context    jsonb not null default '{}',
  blocked    jsonb not null default '[]',
  label      text
);

-- R5 event log.
create table event (
  id   bigserial primary key,
  type text not null,
  data jsonb not null,
  at   timestamptz not null default now()
);
create index event_type_at on event (type, at);

-- Durable runner (only if the chosen engine doesn't keep its own step state).
create table run_step (
  run_id text not null,
  name   text not null,
  value  jsonb,
  primary key (run_id, name)
);
