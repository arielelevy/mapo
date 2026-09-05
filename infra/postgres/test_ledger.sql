-- Tests de lab/ARQUITECTURA.es.md §10 que son SQL puro. Corren en una transacción que
-- se revierte: no dejan filas. Cada guarda que falla aborta el bloque con un error
-- `FALLO ...`; si todo pasa se imprimen sólo líneas `OK ...`.
\set ON_ERROR_STOP on
begin;

do $$
declare
  cid  uuid;
  ivid int;
begin
  insert into policy_bundle(version, digest, bundle) values (1, 'd-1', '{}'), (2, 'd-2', '{}');
  insert into promotion_certificate(incumbent_version, candidate_version, dataset_manifest_hash, split, measurement, accepted)
    values (1, 2, 'manifest-a', 'final', '{"net": 0.0311}', false)
    returning id into cid;

  -- T1 · anti-pseudorreplicación: dos trials de la misma celda violan la PK
  insert into episode values ('t1', 'react', 2, 'val', 0.5, 100, true, 3);
  begin
    insert into episode values ('t1', 'react', 2, 'val', 0.6, 120, false, 3);
    raise exception 'FALLO T1: la base aceptó un segundo trial de la misma celda';
  exception when unique_violation then
    raise notice 'OK T1 anti-pseudorreplicacion: unique_violation en (task, paradigm, policy_version)';
  end;

  -- T1b · n_trials >= 3 (repeat >= 3 del protocolo)
  begin
    insert into episode values ('t2', 'react', 2, 'val', 0.5, 100, true, 2);
    raise exception 'FALLO T1b: la base aceptó n_trials = 2';
  exception when check_violation then
    raise notice 'OK T1b piso de replicas: check n_trials >= 3';
  end;

  -- T2 · final una sola vez: segundo uso del mismo claim_id falla
  insert into final_use_ledger(claim_id, dataset_manifest_hash, certificate_id) values ('claim-1', 'manifest-a', cid);
  begin
    insert into final_use_ledger(claim_id, dataset_manifest_hash, certificate_id) values ('claim-1', 'manifest-a', cid);
    raise exception 'FALLO T2: la base aceptó un segundo uso del mundo final';
  exception when unique_violation then
    raise notice 'OK T2 final una sola vez: unique_violation en claim_id';
  end;

  -- T3 · belief_log append-only: UPDATE y DELETE abortan
  insert into belief_log(request_id, prev_hash, hash, payload) values ('r-1', decode('00', 'hex'), decode('01', 'hex'), '{}');
  begin
    update belief_log set payload = '{"tampered": true}' where request_id = 'r-1';
    raise exception 'FALLO T3: UPDATE sobre belief_log no fue bloqueado';
  exception when restrict_violation then
    raise notice 'OK T3 append-only: UPDATE bloqueado por trigger';
  end;
  begin
    delete from belief_log where request_id = 'r-1';
    raise exception 'FALLO T3: DELETE sobre belief_log no fue bloqueado';
  exception when restrict_violation then
    raise notice 'OK T3 append-only: DELETE bloqueado por trigger';
  end;

  -- T3b · certificados y θ también inmutables
  begin
    update promotion_certificate set accepted = true where id = cid;
    raise exception 'FALLO T3b: se pudo reescribir un certificado';
  exception when restrict_violation then
    raise notice 'OK T3b certificado inmutable';
  end;
  begin
    update policy_bundle set bundle = '{"x": 1}' where version = 2;
    raise exception 'FALLO T3b: se pudo reescribir θ';
  exception when restrict_violation then
    raise notice 'OK T3b policy_bundle inmutable';
  end;

  -- T4 · live_pointer fila única
  insert into index_version(collection, embedder, dim, parser_version, chunker_version, corpus_manifest_hash)
    values ('Chunk_v7', 'text-embedding-3-large', 3072, 'docling-2', 'chunker-1', 'corpus-h')
    returning id into ivid;
  insert into live_pointer(index_version_id, policy_version) values (ivid, 2);
  begin
    insert into live_pointer(singleton, index_version_id, policy_version) values (false, ivid, 2);
    raise exception 'FALLO T4: la base aceptó una segunda fila en live_pointer';
  exception when check_violation then
    raise notice 'OK T4 live_pointer: check singleton';
  end;
  begin
    insert into live_pointer(index_version_id, policy_version) values (ivid, 1);
    raise exception 'FALLO T4b: la base aceptó una segunda fila en live_pointer';
  exception when unique_violation then
    raise notice 'OK T4b live_pointer: una sola fila';
  end;

  -- T5 · el flip es un UPDATE de una fila (lo que sí se permite)
  update live_pointer set policy_version = 1, flipped_at = now();
  raise notice 'OK T5 flip: UPDATE de la fila unica permitido';

  -- T6 · referencias: un episodio no puede apuntar a una θ que no existe
  begin
    insert into episode values ('t3', 'react', 99, 'val', 0.5, 100, true, 3);
    raise exception 'FALLO T6: episodio con policy_version inexistente';
  exception when foreign_key_violation then
    raise notice 'OK T6 integridad: policy_version debe existir en policy_bundle';
  end;
end
$$;

rollback;
