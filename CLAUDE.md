# CLAUDE.md — MAPO (whitepaper + paperlab)

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
Deuda actual conocida: el piso de garantía que aprende de estadísticas de rechazo
(paper §6.2) — falta implementarlo en `assurance.py`/`policy.py`.

## Orden de prioridad: EL PRODUCTO PRIMERO, EL PAPER DESPUÉS

1. **El producto es el motor MAPO** y tiene dos mitades (ver `engine/README.md`):
   - **`engine/agentic/`** — capa de EJECUCIÓN (LangGraph): estrategias dag/react/
     map_reduce/plan_execute, blackboard, semantic_search RRF, tools. Código propio del
     autor, reusado; el sistema del que proviene NO se menciona en ningún lado.
   - **`paperlab/app/`** — capa de DECISIÓN determinística (factibilidad aritmética →
     creencias con procedencia → dial A0–A3 → ruteo selectivo con abstención → EXPLAIN),
     que REEMPLAZA al clasificador LLM en prosa de `engine/agentic/understand.py`.
   `paperlab/` además es el banco de medición (sin framework, por diseño — no meter
   LangGraph ahí). Ante cualquier decisión de diseño, pensar primero cómo mejora al
   producto; el paper viene después.
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

## Decisiones vigentes (2026-08-26)

- **MAPO es un repo git NUEVO en `D:\Apps\MAPO`** (whitepaper + paperlab juntos). El repo
  viejo (`lumen-whitepaper`) queda archivado con v1. NO hacer push sin confirmación;
  el remote de GitHub para MAPO todavía no existe.
- Aval arXiv vía Errecalde/Jaime: **CANCELADO**. Se busca otro endorser o se publica en
  **Zenodo con DOI**. §14 del PLAN es histórico.
- Modelo de medición: `gpt-5-chat` (rechaza temperature explícita; escape verificado:
  `gpt-5.4-1` acepta t=0 pero es razonador y cambia qué se mide).
- `paperlab` se muda a `D:\Apps\MAPO\paperlab` cuando termine la corrida activa — NUNCA
  mover mientras una corrida escribe en `results/`.
