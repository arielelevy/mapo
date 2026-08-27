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
u horizonte. La dirección aprobada, todavía NO implementada, es Reparación Epistémica
Contrafactual: diseño en `lab/PATRON_REC.es.md`; arquitectura y deuda en
`lab/DISENO.es.md`. Nada de eso entra al paper hasta ejecutarse y medirse.
Handoff exhaustivo para retomar sin el chat: `lab/CIERRE-2026-08-27.es.md`.

**Arquitectura de plataforma (PROPUESTA, 2026-08-27): `lab/ARQUITECTURA.es.md`.** Fija
las decisiones físicas del producto: on-prem/Docker; NO Temporal todavía (work table en
Postgres ahora, DBOS después, Temporal sólo con disparadores escritos) y NO LangGraph
nunca; Docling como extractor primario con procedencia página+bbox y un sensor barato
—`pypdfium2`, no PyMuPDF, que es AGPL— decidiendo OCR antes de la primera pasada;
Weaviate con hybrid y una colección por versión de índice, con `live_pointer` en Postgres
como único flip atómico de promoción; Postgres como ledger epistémico con un esquema que
hace estructuralmente imposibles las deudas §5.2 y §5.8 de `DISENO.es.md`; FastAPI con
SSE resumible y eventos tipados, donde A3 buffea la respuesta hasta verificar citas.
Ninguna de esas piezas está ejecutada.

## Orden de prioridad: EL PRODUCTO PRIMERO, EL PAPER DESPUÉS

1. **El producto es el motor MAPO, y todavía no existe como tal.** Se construye a
   partir de lo que el banco pruebe, no antes (decisión del autor, 2026-08-27).
   - **`lab/app/`** — hoy contiene DOS cosas que no son lo mismo y que se separan
     cuando se arranque el producto: la **capa de decisión** (factibilidad aritmética
     → creencias con procedencia → dial A0–A3 → ruteo selectivo con abstención →
     EXPLAIN) más los 13 paradigmas, que SON producto; y el **banco de medición**
     (runner, grading, metrics, corpus, tests, scripts `_*.py`), que NO lo es.
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
   (`paper-en.md` canónico, `paper-es.md` espejo — toda edición va a los DOS).
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
- **Temporal (2026-08-27, decidido en principio)**: sí para la **ingesta** — workflow
  por colección, fan-out de activities por unidad en task queues, idempotencia por
  hash de contenido, reintentos declarados, y `VerifyIndex` antes de `Promote` con la
  misma disciplina que la promoción de θ. En el **plano de query** queda como
  envoltorio opcional, no como requisito. **La capa de decisión NUNCA depende de
  Temporal**, y los paradigmas siguen siendo funciones async planas: es lo que
  mantiene al banco midiendo exactamente lo que producción ejecuta.

- **MAPO es este repo en `D:\Apps\MAPO`** (whitepaper + lab + legacy juntos),
  remote `origin` = github.com/arielelevy/mapo (PRIVADO), rama `main`, con las dos
  historias fusionadas (la del lab y la del paper). El repo viejo de la marca
  anterior queda archivado FUERA, con su v1. NO hacer push sin confirmación.
- Aval arXiv vía Errecalde/Jaime: **CANCELADO**. Se busca otro endorser o se publica en
  **Zenodo con DOI**. §14 del PLAN es histórico.
- Modelo de medición (2026-08-26): **`gpt-5.4-nano`** en adelante (t=0 + seed,
  determinismo casi al token verificado, cuota propia); la grilla `gpt-5-chat` queda
  CONGELADA como primer modelo. Detalle completo en `lab/CLAUDE.md`.
- `lab` YA vive en `D:\Apps\MAPO\lab` (mudado 2026-08-27, corridas
  terminadas, conteos verificados). Los veredictos P10–P14 y P13a-c están en
  `lab/README.md` §Findings y `lab/notes/`. Auditoría de código completa
  en `lab/code-review-2026-08-27.md` (bloque crítico ya aplicado).
