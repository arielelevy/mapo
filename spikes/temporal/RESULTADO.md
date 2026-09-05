# Spike Temporal — resultado de `demo.py` (2026-09-05T09:57:03)
server: localhost:7233 (temporal server start-dev, SQLite)  ·  SDK temporalio 1.32.0  ·  UI: http://localhost:8233

## A. El worker muere entre verify y el flip; otro worker retoma sin repetir pasos
- worker 1 (pid 34216) terminó con código 3 (3 = caída simulada en `promote`)
- live_pointer tras la caída: None  (esperado: None, nada se promovió a medias)
- worker 2 (pid 17468) completó el workflow en 7.4s
- resultado: promoted=True index_version=7 chunks=36
- live_pointer ahora: 7
- step_log (cada paso previo a la caída corrió UNA vez, en el worker 1; `promote` corrió en el worker 2):
     1. parse            attempt=1  pid=34216
     2. chunk            attempt=1  pid=34216
     3. embed            attempt=1  pid=34216
     4. index            attempt=1  pid=34216
     5. verify           attempt=1  pid=34216
     6. promote:CRASH    attempt=1  pid=34216
     7. promote          attempt=2  pid=17468

## B. Un 429 con hora de reset se vuelve un timer durable; el worker muere durante la espera y no importa
- worker 1 (pid 1572) matado a los 2.0s, en medio del timer
- worker 2 (pid 22484) completó en 9.5s; el workflow esperó 5.99s por el límite
- promoted=True live_pointer=8
- step_log (`embed` aparece dos veces: la que devolvió RateLimited y la que corrió tras el timer):
     1. parse            attempt=1  pid=1572
     2. chunk            attempt=1  pid=1572
     3. embed            attempt=1  pid=1572
     4. embed            attempt=1  pid=22484
     5. index            attempt=1  pid=22484
     6. verify           attempt=1  pid=22484
     7. promote          attempt=1  pid=22484

## C. Reingestar el mismo contenido es la misma ejecución, no una nueva
- start_workflow(id='ingest-c0ffee01') rechazado: WorkflowAlreadyStartedError (REJECT_DUPLICATE)
- filas en `chunk` para v7 antes/después: 36 / 36 (sin cambios)

## D. Fan-out de 5 agentes, reintento por rama, una rama con límite; fan-in con reduce
- completado en 6.7s; espera por límite: 5.99s (sólo la rama 3)
    rama 0: score=0.408  attempts=1 pid=45356
    rama 1: score=0.276  attempts=2 pid=45356  <- fallo transitorio en el intento 1, reintentado por RetryPolicy
    rama 2: score=0.382  attempts=1 pid=45356
    rama 3: score=0.719  attempts=1 pid=45356  <- RateLimited, timer durable, reejecutada
    rama 4: score=0.408  attempts=1 pid=45356
- reduce eligió la rama 3
- step_log:
     1. agent[0]         attempt=1  pid=45356
     2. agent[1]         attempt=1  pid=45356
     3. agent[4]         attempt=1  pid=45356
     4. agent[2]         attempt=1  pid=45356
     5. agent[3]         attempt=1  pid=45356
     6. agent[1]         attempt=2  pid=45356
     7. agent[3]         attempt=1  pid=45356
     8. reduce           attempt=1  pid=45356

