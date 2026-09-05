# Spike: Temporal para la ingesta y el fan-out de agentes

Decisión del autor (2026-09-05): probar Temporal para el plano de ingesta y para tareas
asincrónicas, incluido fan-out/fan-in de agentes. `lab/ARQUITECTURA.es.md` §2 lo
postergaba con tres disparadores escritos. Este spike es la prueba ejecutable que la
regla del repo exige antes de que la decisión entre a un documento: primero corre,
después se escribe.

Lo que NO es: producto. No llama a ningún modelo, no toca Weaviate, no importa `lab/`.
El banco sigue sin framework. Vive en `spikes/` justamente para que nadie lo confunda con
`lab/app/`.

## Correr

```
winget install Temporal.TemporalCLI
pip install --user temporalio
temporal server start-dev --db-filename .temporal-dev.db     # server + UI en :8233, SQLite
python demo.py                                                # levanta y mata workers solo
```

`demo.py` deja `RESULTADO.md` con la corrida completa. La UI en `http://localhost:8233`
muestra la event history de cada workflow: ahí se ve el timer durable y el reintento.

## Las cuatro pruebas y lo que mostraron

| Prueba | Qué se fuerza | Resultado medido (2026-09-05) |
|---|---|---|
| A. Caída entre `verify` y el flip | El worker hace `os._exit(3)` dentro de `promote`, antes de tocar `live_pointer` | `parse`, `chunk`, `embed`, `index`, `verify` corrieron UNA vez, en el worker 1. `promote` corrió en el worker 2 (attempt 2). `live_pointer` fue `None` hasta el flip, después `7`. Total 7,4 s. |
| B. 429 con hora de reset | `embed` devuelve `RateLimited` no reintentable con `try again at`; el worker se mata durante la espera | El workflow durmió 5,99 s con `workflow.sleep` (timer del server). El worker 2 retomó tras el timer y completó. Total 9,5 s. |
| C. Idempotencia por contenido | Se vuelve a pedir la ingesta del mismo hash con `REJECT_DUPLICATE` | `WorkflowAlreadyStartedError`. Tabla `chunk` sin cambios (36/36). |
| D. Fan-out de 5 agentes | Rama 1 falla una vez (transitorio), rama 3 devuelve `RateLimited` | `asyncio.gather` dentro del workflow. Rama 1: attempts=2 por RetryPolicy. Rama 3: reejecutada tras timer durable, sin afectar a las otras. Fan-in con `reduce`. Total 6,7 s, de los cuales 5,99 s son el timer. |

## Lo que se aprendió y hay que llevar al diseño

**El "Continue a las 3:20" es un timer durable.** Lo que anoche se hizo a mano contra
Codex (`codex-inject`, un proceso que esperó cuatro horas y reintentó) es la prueba B.
El plano de ejecución del producto va a chocar con cuotas de la API del modelo igual, y
la respuesta correcta es la misma: el error lleva la hora, el workflow duerme hasta esa
hora, el timer vive en el server y no en el proceso. En la fase 0 de la arquitectura eso
era una columna `not_before` en la work table; con Temporal viene incluido.

**Sin heartbeat un worker muerto se detecta tarde.** La primera corrida de A tardó
22,2 s: el server esperó el `start_to_close_timeout` de 20 s antes de reprogramar
`promote`. Con `heartbeat_timeout=3s` y un `activity.heartbeat()` al entrar a cada
actividad bajó a 7,4 s. En producción esto es obligatorio para toda actividad larga
(Docling, embeddings por lote).

**La cola sticky retiene el workflow task del worker muerto.** La primera corrida de B
tardó 17,4 s por el `sticky_queue_schedule_to_start_timeout` por defecto de 10 s. Con
2 s bajó a 9,5 s. Es un parámetro del `Worker`, no del workflow.

**Los dos determinismos no se pisan si el workflow sólo orquesta.** El workflow no
decide nada: llama actividades en orden y duerme. La decisión de MAPO (creencias, reglas,
θ, EXPLAIN) no aparece en la event history de Temporal. Eso es lo que hay que preservar
cuando esto pase a producto: `mapo.core` nunca se ejecuta dentro de un workflow; a lo
sumo una actividad lo invoca como función pura.

**El fan-out por rama es una actividad por rama, no un child workflow.** Alcanza para las
olas de `dag_strategy`. Un child workflow por agente sólo se justifica si cada rama tiene
sub-pasos propios que deban sobrevivir por separado.

## Lo que el spike NO demuestra todavía

- Costo operativo real on-prem. Acá corrió `temporal server start-dev` (un binario,
  SQLite). Producción es `temporalio/auto-setup` o el server con su esquema en Postgres,
  más la UI: dos contenedores más que la topología de §7, y su esquema puede vivir en el
  mismo Postgres 18 en una base aparte. Falta levantarlo así y medirlo.
- Las actividades son stubs. El paso siguiente es envolver las funciones reales de
  ingesta detrás de `data/ports.py` como actividades, sin cambiarlas, y correr un PDF de
  verdad de punta a punta. Eso no gasta créditos de modelo si el embedder es el TEI local.
- Fan-out de paradigmas con llamadas reales al modelo. **No se corre hasta el 2026-09-13**
  por la restricción de créditos vigente en `CLAUDE.md`.
- Streaming de tokens al cliente. Temporal no lo resuelve y el diseño de §6 (SSE con bus)
  sigue vigente para el plano de query.

## Archivos

| Archivo | Qué es |
|---|---|
| `shared.py` | Tipos de entrada/salida y el ledger SQLite que hace de Postgres para lo que se mide (`step_log`, `live_pointer`, `chunk`) |
| `activities.py` | Actividades stub: registran cada ejecución, fallan de forma controlada, hacen el flip |
| `workflows.py` | `IngestDocumentWorkflow` y `FanOutAgentsWorkflow`, con el helper del timer durable por `RateLimited` |
| `worker.py` | Worker con `sticky_queue_schedule_to_start_timeout=2s` |
| `demo.py` | Las cuatro pruebas; escribe `RESULTADO.md` |
