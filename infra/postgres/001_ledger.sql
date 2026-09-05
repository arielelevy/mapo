-- MAPO · ledger epistémico · migración 001
-- Fuente: lab/ARQUITECTURA.es.md §5. Este archivo NO cierra deudas: persiste guardas que
-- runner.py, consolidation.py y certify.py ya imponen en proceso, para que sobrevivan a
-- un reinicio, a dos workers y a una auditoría externa.
-- Aplicar una sola vez; idempotente por `schema_migration`.

begin;

create table if not exists schema_migration (
  id         text primary key,
  applied_at timestamptz not null default now()
);

do $$
begin
  if exists (select 1 from schema_migration where id = '001_ledger') then
    raise notice '001_ledger ya aplicada';
    return;
  end if;

  ---------------------------------------------------------------------------
  -- Función común: append-only real. Aborta UPDATE y DELETE.
  ---------------------------------------------------------------------------
  create function forbid_mutation() returns trigger language plpgsql as $f$
  begin
    raise exception '% es append-only: % no permitido', tg_table_name, tg_op
      using errcode = 'restrict_violation';
  end
  $f$;

  ---------------------------------------------------------------------------
  -- θ versionada. Inmutable: una versión, un digest, para siempre.
  ---------------------------------------------------------------------------
  create table policy_bundle (
    version    int  primary key,
    digest     text not null unique,
    bundle     jsonb not null,
    created_at timestamptz not null default now()
  );
  create trigger policy_bundle_append_only
    before update or delete on policy_bundle
    for each row execute function forbid_mutation();

  ---------------------------------------------------------------------------
  -- Certificado de promoción: liga incumbente, candidata, manifiesto de datos,
  -- split y medición. Se emite aunque la candidata NO se acepte.
  ---------------------------------------------------------------------------
  create table promotion_certificate (
    id                    uuid primary key default gen_random_uuid(),
    incumbent_version     int  not null references policy_bundle(version),
    candidate_version     int  not null references policy_bundle(version),
    dataset_manifest_hash text not null,
    split                 text not null check (split in ('val','final')),
    measurement           jsonb not null,
    accepted              boolean not null,
    created_at            timestamptz not null default now()
  );
  create trigger promotion_certificate_append_only
    before update or delete on promotion_certificate
    for each row execute function forbid_mutation();

  ---------------------------------------------------------------------------
  -- Persiste la regla de runner.py: un episodio es una celda, no un trial.
  -- La PK hace imposible que dos workers reintroduzcan la pseudorreplicación.
  ---------------------------------------------------------------------------
  create table episode (
    task_id        text not null,
    paradigm       text not null,
    policy_version int  not null references policy_bundle(version),
    split          text not null check (split in ('train','val','final')),
    utility        double precision not null,
    cost_tokens    int  not null,
    was_best       boolean not null,
    n_trials       int  not null check (n_trials >= 3),
    recorded_at    timestamptz not null default now(),
    primary key (task_id, paradigm, policy_version)
  );

  ---------------------------------------------------------------------------
  -- Contraparte durable de FinalLedger (app/certify.py): "tocar final una sola
  -- vez" deja de depender de un archivo local y pasa a ser una restricción.
  ---------------------------------------------------------------------------
  create table final_use_ledger (
    claim_id              text primary key,
    dataset_manifest_hash text not null,
    certificate_id        uuid not null references promotion_certificate(id),
    used_at               timestamptz not null default now()
  );
  create trigger final_use_ledger_append_only
    before update or delete on final_use_ledger
    for each row execute function forbid_mutation();

  ---------------------------------------------------------------------------
  -- Historia canónica de creencias. verify_chain() sigue siendo una función
  -- pura sobre estas filas; la base sólo garantiza que nadie las toque.
  ---------------------------------------------------------------------------
  create table belief_log (
    seq        bigserial primary key,
    request_id text  not null,
    prev_hash  bytea not null,
    hash       bytea not null,
    payload    jsonb not null,
    logged_at  timestamptz not null default now()
  );
  create index belief_log_request_idx on belief_log(request_id, seq);
  create trigger belief_log_append_only
    before update or delete on belief_log
    for each row execute function forbid_mutation();

  ---------------------------------------------------------------------------
  -- Una versión de índice = embedder + dim + parser + chunker + manifiesto.
  -- Si cambia cualquiera, es otro índice, y el EXPLAIN lo dice.
  ---------------------------------------------------------------------------
  create table index_version (
    id                   serial primary key,
    collection           text not null unique,        -- Chunk_v8
    embedder             text not null,
    dim                  int  not null,
    parser_version       text not null,
    chunker_version      text not null,
    corpus_manifest_hash text not null,
    built_at             timestamptz not null default now(),
    verified_at          timestamptz,
    promoted_at          timestamptz
  );

  ---------------------------------------------------------------------------
  -- Fila única: el flip atómico de promoción. Weaviate no se muta en el flip.
  ---------------------------------------------------------------------------
  create table live_pointer (
    singleton        boolean primary key default true check (singleton),
    index_version_id int not null references index_version(id),
    policy_version   int not null references policy_bundle(version),
    flipped_at       timestamptz not null default now()
  );

  ---------------------------------------------------------------------------
  -- EXPLAIN por request, con qué índice y qué θ estaban vivos en ese momento.
  ---------------------------------------------------------------------------
  create table request_log (
    request_id       text primary key,
    received_at      timestamptz not null default now(),
    index_version_id int references index_version(id),
    policy_version   int references policy_bundle(version),
    explain          jsonb not null
  );
  create trigger request_log_append_only
    before update or delete on request_log
    for each row execute function forbid_mutation();

  insert into schema_migration(id) values ('001_ledger');
end
$$;

commit;
