# CLAUDE.md — lab

**Esto es EL PRODUCTO, no el andamiaje de un paper.** Una capa de decisión
determinística para agentes LLM: factibilidad aritmética → creencias con procedencia
(`COMPUTED > OBSERVED > ELICITED > ASSUMED`) → dial de garantía por request (A0–A3) →
ruteo selectivo con abstención → circuit breakers contables → artefacto EXPLAIN.
Diseño completo del entregable: `README.md` §"The deliverable" / `README.es.md`.
El paper que lo valida vive en `..\whitepaper\` (este mismo repo) y va SEGUNDO en
prioridad; la capa de ejecución anterior (LangGraph) quedó CONGELADA en `..\legacy\agentic\`:
no es el producto y no se evoluciona (decisión del autor, 2026-08-27). El
whitepaper de la marca anterior quedó FUERA del repo, ya cosechado en `notes/`.
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

- **El control nulo por prompting NO se corre nunca más**: quedó su dato histórico
  (idéntico a `direct` en toda celda medida). Ninguna corrida nueva lo incluye, y
  `RETIRED` en `app/paradigms/` lo impide por código.
- **`direct` es el caso degenerado gateado por factibilidad**: solo existe cuando la
  evidencia entra en ventana — en el régimen de producción eso no pasa. No es un
  candidato del catálogo del motor; es lo que la aritmética elige sola cuando puede.
- La fila activa de medición: react (fallback), dag_strategy, map_reduce, rewoo,
  gist_reader (falsificado, no promovido) + la superficie managed. Candidatos cerrados
  2026-08-27: graph_traverse FALSIFICADO (P10a), extract_compute / streaming_scan
  INFACTIBLES bajo presupuesto de producción (decisión del autor: la infactibilidad ES
  el resultado; P11/P12 no-evaluables), pointer_chase FALSIFICADO (P14a; sus frenos
  P14b confirmados). Veredictos y P13a-c en README §Findings + notes/. Región abierta:
  C3 profundo en nano (grilla completa u=0.000; también oráculo-cero en gold_transfer).
  **P15 (2026-08-27): REFUTADA** — θ pierde −0.087 neto contra el mejor fijo en el
  corpus held-out seed 47. Mecanismo verificado: φ no tiene eje de horizonte, C5 cae en
  las mismas regiones que C2/C4, y θ rutea rewoo contra su propio veredicto P6b. P15d
  (reproducibilidad) CONFIRMADA 26/26. Detalle en README §Findings.

## Modelo de medición (decisión del autor, 2026-08-26)

**De ahora en adelante: `gpt-5.4-nano`** en `foundryopencode` (eastus2, misma
suscripción VS Enterprise), `temperature=0` + seed — **determinismo casi al token
verificado** (réplicas de direct idénticas), cuota propia 2,5M+ TPM, costo tier-nano.
Embeddings siguen en `innerbifoundry` (config separada `AZURE_OPENAI_EMBEDDING_*`).
Resultados nano en `results/nano/` — NUNCA mezclar modelos en un mismo archivo de
resume. La grilla `gpt-5-chat` queda congelada como primer modelo (con sus celdas †
pendientes documentadas); es el brazo de comparación multi-modelo, no se extiende.

## Dónde vive cada cosa (ordenado 2026-08-28)

```
lab/
  app/        el PRODUCTO — capa de decisión y paradigmas
  bench/      el BANCO — analysis/ runs/ audits/ oneoff/ + _sanity.py
  corpus/     generación y verificación del mundo
  tests/      test_science.py · test_consolidation.py
  results/    MEDICIÓN — evidencia de lo corrido          (fuera de git)
  state/      ESTADO — ledger de creencias, θ, calibración (fuera de git)
  cache/      completions content-addressed                (fuera de git)
```

Eran **72 scripts sueltos en la raíz**, al lado de `app/`. La regla —el banco importa al
producto, el producto no sabe que el banco existe— estaba escrita y no se veía en el árbol.
Se corren **desde `lab/`**: `py bench/analysis/_analyze_money.py`. Detalle en
`bench/README.md`. Los nombres de script que el `README.md` menciona no cambiaron; sólo su
carpeta.

**`results/` y `state/` son dos árboles y no se mezclan.** Un `rglob("*.jsonl")` sobre
resultados levantaba el ledger de creencias como filas medidas. Están fuera de git por
tamaño, no por importancia: al ledger lo protege su cadena de hashes (`store.verify_chain`),
no el control de versiones.

## Antes de gastar un token

```powershell
py tests\test_science.py            # debe pasar completo
py tests\test_consolidation.py      # debe pasar completo
py corpus\verify.py --corpus corpus\<nombre>
# predicciones falsables registradas con fecha en README.md, ANTES de correr
# repeat >= 3, piso de ruido POR CELDA, decisiones sobre brecha NETA
# ESTIMAR CONTRA EL CORPUS, NUNCA CONTRA EL REGISTRO: un .jsonl no declara si esta
#   completo. Estimar desde uno parcial costo un error de 34x. La cuenta correcta es
#   len(tasks.json) x brazos x repeat, cuesta lo mismo, y no se puede equivocar asi
```

Corridas resumibles por `(task, paradigm, trial)`; el cache content-addressed hace la
segunda pasada gratis. Corpus: gold_v2 (en ventana, ~18k), gold_wide (~135k),
gold_deep (~483k), gold_xl (~1.272k tokens).

## Estado git

Repo git desde 2026-08-27 (primer commit `76c8b8e`, confirmado por el autor;
.gitignore cubre .env/cache/results). Remote: `origin` = github.com/arielelevy/mapo
(PRIVADO), rama `main`. Nunca push sin confirmación del autor.
