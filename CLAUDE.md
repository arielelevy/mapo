# CLAUDE.md — MAPO (whitepaper + lab)

**MAPO empieza de cero: SIN NINGUNA referencia a marcas o productos anteriores en
documentos activos ni en código.**

## EL OBJETIVO DEL PRODUCTO (medible)

> **Tirarle a MAPO un corpus gold NUEVO — que nunca vio — y que ejecute mejor que
> cualquier paradigma fijo en el harness.** Es decir: el motor decide por request
> (factibilidad → creencias → garantía → rutear o abstenerse) y captura brecha de
> oráculo NETA positiva contra el mejor fijo, incluido siempre-`react`, sobre datos
> held-out. Ese es el criterio de éxito; todo lo demás lo sirve.

## EJECUTADO PRIMERO, TEORIZADO DESPUÉS

**Todo lo que se haga tiene que existir en el programa ejecutable ANTES de entrar al
paper.** Ninguna idea se escribe como diseño sin implementación que la corra. Si algo
está hoy en el paper como "declarado, no medido", es deuda: implementarlo o sacarlo.
El piso de garantía que aprende de estadísticas de rechazo (paper §6.2) se
implementó el 2026-08-27 — rechazo tipado en `beliefs.py`, aprendizaje en `assurance.py`,
transporte en el bundle firmado de `policy.py`, guarda de replicación en
`consolidation.py`, probado en `tests/test_consolidation.py` §6.
Deuda actual conocida: **la SONDA ya se ejecuta**, pero el ciclo epistémico está
incompleto. Lee siempre la primera unidad, la verificación de referencias necesita
fortalecerse, el replanning reutiliza la región previa, no conserva una única historia
pre/post, y el costo no integra la utilidad total. Además P15 fue refutada: θ perdió
`-0,087` contra el mejor fijo porque el vocabulario de región no representa continuidad
u horizonte. La dirección aprobada es Reparación Epistémica Contrafactual, y desde el
2026-08-29 **está implementada y corrida**: `rec.py` (diagnóstico contrafactual mínimo,
esquema de intervenciones cerrado y firmado) y `certify.py` (tres mundos disjuntos, mundo
final de un solo uso, instalación fail-closed). Se corre con `bench/runs/_run_rec.py`.
**El veredicto medido es que la cláusula NO se promueve**: la métrica neta —el eje que
faltaba, porque lo que una cláusula compra es *no sondear*, no utilidad— da `+0,0311`
contra un piso de ruido de `0,0655` al λ=0,05 con que decide el banco, y sólo cruza a
λ=0,2. `aceptada: False`; el mundo final no se consumió. Diseño en `lab/PATRON_REC.es.md`;
arquitectura y deuda en `lab/DISENO.es.md`. Nada entra al paper hasta ejecutarse y medirse.
Handoff exhaustivo para retomar sin el chat: `lab/historico/CIERRE-2026-08-27.es.md`.
**El más reciente es `lab/historico/CIERRE-2026-09-03.es.md`**: pasada editorial de los dos
papers, figuras de arquitectura nuevas, recorte del largo, las seis apuestas `P31`–`P36` y el
veredicto de las dos gratis (`P34` parcial, `P36` fracaso), con dos decisiones pendientes del
autor: el eje `answer_cardinality` en el vocabulario y el piso de ocho episodios.

**Arquitectura de plataforma (PROPUESTA, 2026-08-27): `lab/ARQUITECTURA.es.md`.** Fija
las decisiones físicas del producto: on-prem/Docker; NO Temporal todavía (work table en
Postgres ahora, DBOS después, Temporal sólo con disparadores escritos) y NO LangGraph
nunca; Docling como extractor primario con procedencia página+bbox y un sensor barato
—`pypdfium2`, no PyMuPDF, que es AGPL— decidiendo OCR antes de la primera pasada;
Weaviate con hybrid y una colección por versión de índice, con `live_pointer` en Postgres
como único flip atómico de promoción; Postgres como ledger epistémico, que NO cierra
deudas nuevas sino que hace durables las guardas que `runner.py`, `consolidation.py` y
el `FinalLedger` de `certify.py` ya imponen en proceso; FastAPI con SSE resumible y
eventos tipados, donde A3 buffea la respuesta hasta verificar citas. Ninguna de esas
piezas está ejecutada.

**Consola de prueba: `ui/`** (Vite + React 19 + TypeScript; `npm install && npm run dev`).
Consume los mismos eventos tipados de `/v1/answer` y trae un modo demo para trabajarla sin
motor y sin gastar tokens. Tres cosas que la hacen fiel al producto y no hay que romper:
la **escalera de decisión** —el plantel entero tachándose por factibilidad, garantía y
θ ANTES de que exista un token—; `done`/`gated`/`deferred` **estructuralmente distintos**,
no tres colores del mismo cartel; y `irreversible`/`shared_writes`/`regulated` **declarados
por el caller, jamás inferidos del texto** (`serve.py` los asienta como COMPUTED 1.0).
La bandeja de contexto recalcula la poda aritmética en cada toggle: se ve qué paradigmas
mata cada unidad antes de gastar nada. Detalle en `ui/README.md`.

## Orden de prioridad: EL PRODUCTO PRIMERO, EL PAPER DESPUÉS

1. **El producto es el motor MAPO, y todavía no existe como tal.** Se construye a
   partir de lo que el banco pruebe, no antes (decisión del autor, 2026-08-27).
   - **`lab/app/`** — hoy contiene DOS cosas que no son lo mismo y que se separan
     cuando se arranque el producto: la **capa de decisión** (factibilidad aritmética
     → creencias con procedencia → dial A0–A3 → ruteo selectivo con abstención →
     EXPLAIN) más los paradigmas del catálogo, que SON producto; y el **banco de
     medición**
     (runner, grading, metrics, corpus, tests, `bench/`), que NO lo es.
   - **`legacy/agentic/`** — capa de ejecución anterior (LangGraph), **CONGELADA**.
     No es el producto y no se evoluciona. Se conserva como referencia de lo único
     que resolvió y el banco nunca tuvo que modelar: búsqueda sobre índice real,
     scoping por permisos, citas verificadas contra el índice, streaming. El sistema
     del que proviene NO se menciona en ningún lado.
   - **La regla que evita que se vuelvan a mezclar**: el banco importa al producto;
     el producto no sabe que el banco existe.
   El banco es **sin framework, por diseño** — no meter LangGraph ni Temporal ahí:
   mide paradigmas en proceso, y si el ejecutor necesitara un runtime para correr,
   dejaría de medir lo que producción ejecuta.
2. **El paper documenta y valida el producto**, no al revés. Vive en `whitepaper/`
   **`paper-es.md` es la ÚNICA versión mantenida** (decisión del autor, 2026-08-30). La
   redacción inglesa quedó congelada en `whitepaper/historico/paper-en-congelado.md`, anterior
   al recorte que sacó la grilla superada, y **no se edita**: dejarla viva obligaba a espejar
   cada cambio en dos archivos, y el que nadie mantiene es el que miente.
   `GATE.md` manda sobre qué se puede afirmar; `PLAN.md` es arqueología, no tesis.
   `MAP.md` es la única herencia de v1 (plasticidad Hebbiana para decisiones); el v1
   completo quedó fuera de MAPO, en su repo de origen.

## El ruteo es UN caso, no EL producto

La misma máquina (sensor → creencia tipada → regla con piso de procedencia → registro)
aplica a cuatro superficies: **contenido** (números slot-filled desde `COMPUTED`,
citado-o-callado, contratos de completitud), **datos** (gate de SQL/DAX propuesto,
análisis dimensional/grano, resolución temporal), **acciones** (precondiciones por
herramienta, ledger de idempotencia, handoffs con contrato), y **gobierno** (revisión
humana selectiva por dial, publicación con guarda de regresión). La selección de
paradigma es el caso medido primero, no el alcance del producto.

## Reglas de trabajo (establecidas por el autor)

- **La ingeniería de prompts NO es un patrón** (2026-08-26): el catálogo de ruteo del
  motor excluye a `cot` — dominado por `direct` en toda celda medida (misma utilidad,
  nunca más barato) y redundante con modelos razonadores. Se conserva en el banco SOLO
  como control nulo (es la evidencia de que el andamiaje por prompt no compra nada).
  Los patrones se distinguen por ESTRUCTURA de control de flujo, jamás por fraseo. Las
  mejoras vienen de señales de entorno (contables, deterministas), no de persuadir al
  modelo.

- **Evaluaciones livianas**: sets emparejados por celda, no producto cruzado completo.
  Lo que sea aritmética se saca gratis (factibilidad). Estimar tokens ANTES de correr.
- **Un 429 no es parte de la evaluación**: fallos de infraestructura quedan como
  `infra_error` y fuera de toda estadística. Verificarlo antes de cada corrida.
- **Protocolo antes de gastar**: tests (test_science + test_consolidation), verify del
  corpus, predicciones falsables registradas con fecha, `repeat ≥ 3`, piso de ruido
  POR CELDA, decisiones sobre la brecha NETA.
- **Nada se afirma sin medida, cita o rótulo de hipótesis** (G3). Novedades se enuncian
  como CONJUNCIÓN, nunca como partes (GATE §8quater).

## Decisiones vigentes (actualizado 2026-08-27)

- **`engine/` → `legacy/` (2026-08-27)**: no es el producto. Primero se sigue en `lab/`
  midiendo patrones y validando; el producto se arranca cuando ese registro esté
  maduro. Antes de congelarlo se le hizo revisión a mano completa (26 módulos) y se
  aplicaron ~50 arreglos — está documentado en `legacy/README.md`, que es lo que hay
  que leer antes de portar cualquier pieza.
- **Arquitectura física (2026-08-27, posterior y manda): `lab/ARQUITECTURA.es.md`.**
  Restricciones del autor: on-prem/Docker, Weaviate, single-tenant. Orquestación fase 0:
  Redis Streams + workers, **Temporal todavía NO** — entra sólo si dispara uno de los
  gatillos escritos en su §2.3 (gate A3 parkeado días con timers, fan-out multi-máquina,
  o un segundo lenguaje/servicio en el pipeline). LangGraph descartado, no pospuesto.
  Lo que NO cambia: **la capa de decisión nunca depende de un orquestador** y los
  paradigmas siguen siendo funciones async planas — el banco mide exactamente lo que
  producción ejecuta. (Supersede la entrada anterior "Temporal: sí para la ingesta",
  que era una decisión en principio.)

- **MAPO es este repo en `D:\Apps\MAPO`** (whitepaper + lab + legacy juntos),
  remote `origin` = github.com/arielelevy/mapo (PRIVADO), rama `main`, con las dos
  historias fusionadas (la del lab y la del paper). El repo viejo de la marca
  anterior queda archivado FUERA, con su v1. NO hacer push sin confirmación.
- Aval arXiv vía Errecalde/Jaime: **CANCELADO**. Se busca otro endorser o se publica en
  **Zenodo con DOI**. §14 del PLAN es histórico.
- **Modelo de medición: `luna` (`gpt-5.6-luna`) — REEMPLAZÓ a `nano` (corregido
  2026-08-30).** Esta entrada decía «`gpt-5.4-nano` en adelante» y era falsa contra el
  registro: `results/nano/gold_h1_rows.jsonl` **no existe**, la campaña entera son las
  2.478 filas de `luna`, y `terra` corre sólo C3 (90 filas) por costar 10× la entrada.
  `nano` queda como base histórica, no como modelo de medición.
  Y hay que corregir una segunda cosa de la misma línea: decía «determinismo casi al token
  verificado», que salió de **un smoke de una llamada por modelo**. Es cierto **por llamada**
  y falso **por trayectoria**: `pass^3` mide 17-34% de celdas inestables con `t=0` y semilla
  fija (paper §7.10.2). La grilla `gpt-5-chat` sigue CONGELADA como primer modelo.
  Detalle en `lab/CLAUDE.md`.
- `lab` YA vive en `D:\Apps\MAPO\lab` (mudado 2026-08-27, corridas
  terminadas, conteos verificados). Los veredictos P10–P14 y P13a-c están en
  `lab/historico/BITACORA-PREDICCIONES.es.md` y `lab/notes/` — la cronología salió de
  `lab/README.md` el 2026-08-29, donde ocupaba 1.400 de sus 1.687 líneas. Auditoría de código completa
  en `lab/historico/code-review-2026-08-27.md` (bloque crítico ya aplicado).
