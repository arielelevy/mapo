# CLAUDE.md — paperlab

**Esto es EL PRODUCTO, no el andamiaje de un paper.** Una capa de decisión
determinística para agentes LLM: factibilidad aritmética → creencias con procedencia
(`COMPUTED > OBSERVED > ELICITED > ASSUMED`) → dial de garantía por request (A0–A3) →
ruteo selectivo con abstención → circuit breakers contables → artefacto EXPLAIN.
Diseño completo del entregable: `README.md` §"The deliverable" / `README.es.md`.
El paper que lo valida vive en `..\whitepaper\` y va SEGUNDO en prioridad.
**MAPO empieza de cero: sin ninguna referencia a marcas o productos anteriores.**
**Objetivo medible del producto**: que a MAPO le tiren un corpus gold NUEVO y ejecute
mejor que cualquier paradigma fijo del harness (brecha de oráculo neta positiva sobre
datos held-out). **Ejecutado primero, teorizado después**: nada entra al paper sin
implementación que lo corra.

## Invariantes del producto (no romper)

- La garantía tiene UNA forma: "misma base de creencias ⟹ misma decisión". Nunca
  prometer "mismo prompt ⟹ misma respuesta".
- El LLM es sensor: emite proposiciones; JAMÁS maneja flujo de control ni decide gates.
- Acciones irreversibles: procedencia mínima `COMPUTED`/`OBSERVED`. La opinión del
  modelo no es evidencia admisible.
- El aprendizaje es offline y copy-on-write; promoción con guarda anti-regresión;
  partición proponer/puntuar/promover por tarea. Nada aprende adentro de un request.
- `infra_error` (429 agotado) se registra y se EXCLUYE de toda estadística.
- Sin framework de agentes, sin juez LLM, sin defaults en configuración (env faltante
  = raise en import).

## La fila de paradigmas (decisión del autor, 2026-08-26)

- **`cot` NO se corre nunca más**: queda su dato histórico como control nulo (idéntico a
  direct en toda celda). Ninguna corrida nueva lo incluye.
- **`direct` es el caso degenerado gateado por factibilidad**: solo existe cuando la
  evidencia entra en ventana — en el régimen de producción eso no pasa. No es un
  candidato del catálogo del motor; es lo que la aritmética elige sola cuando puede.
- La fila activa de medición: react (fallback), dag_strategy, map_reduce, rewoo,
  gist_reader (falsificado, no promovido) + la superficie managed. Candidatos cerrados
  2026-08-27: graph_traverse FALSIFICADO (P10a), extract_compute / streaming_scan
  INFACTIBLES bajo presupuesto de producción (decisión del autor: la infactibilidad ES
  el resultado; P11/P12 no-evaluables), pointer_chase FALSIFICADO (P14a; sus frenos
  P14b confirmados). Veredictos y P13a-c en README §Findings + notes/. Región abierta:
  C3 profundo en nano (grilla completa u=0.000).

## Modelo de medición (decisión del autor, 2026-08-26)

**De ahora en adelante: `gpt-5.4-nano`** en `foundryopencode` (eastus2, misma
suscripción VS Enterprise), `temperature=0` + seed — **determinismo casi al token
verificado** (réplicas de direct idénticas), cuota propia 2,5M+ TPM, costo tier-nano.
Embeddings siguen en `innerbifoundry` (config separada `AZURE_OPENAI_EMBEDDING_*`).
Resultados nano en `results/nano/` — NUNCA mezclar modelos en un mismo archivo de
resume. La grilla `gpt-5-chat` queda congelada como primer modelo (con sus celdas †
pendientes documentadas); es el brazo de comparación multi-modelo, no se extiende.

## Antes de gastar un token

```powershell
py tests\test_science.py            # debe pasar completo
py tests\test_consolidation.py      # debe pasar completo
py corpus\verify.py --corpus corpus\<nombre>
# predicciones falsables registradas con fecha en README.md, ANTES de correr
# repeat >= 3, piso de ruido POR CELDA, decisiones sobre brecha NETA
# estimar tokens con corridas previas y reportar el estimado
```

Corridas resumibles por `(task, paradigm, trial)`; el cache content-addressed hace la
segunda pasada gratis. Corpus: gold_v2 (en ventana, ~18k), gold_wide (~135k),
gold_deep (~483k), gold_xl (~1.272k tokens).

## Estado git

Repo git desde 2026-08-27 (primer commit `76c8b8e`, confirmado por el autor;
.gitignore cubre .env/cache/results). Sin remote todavía. Nunca push sin confirmación.
