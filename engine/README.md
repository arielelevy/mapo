# MAPO Engine

El motor RAG de MAPO: capa de ejecución + capa de decisión.

## Composición

```
engine/
└── agentic/            capa de EJECUCIÓN (LangGraph) — código propio del autor,
    ├── strategies/       reusado: dag_strategy (verify-replan sobre blackboard),
    │                     react_agent (+exhaustive), map_reduce, plan_execute
    ├── subgraphs/        semantic_search (RRF: FTS + entidad + KNN)
    ├── tools/            agent_tools, retrieval, repositorio de búsqueda
    ├── blackboard.py     pizarra compartida del DAG
    ├── understand.py     resolución de follow-ups, NER, rewrite — y el clasificador
    │                     LLM de estrategia, QUE SE REEMPLAZA (ver abajo)
    └── state.py, context_guard.py, cache.py, ...
```

## La integración que define al producto

El clasificador de estrategia de `understand.py` es un **router LLM en prosa** — la
pieza que el estudio (`../whitepaper/`) muestra frágil. En MAPO se reemplaza por la
**capa de decisión de `../lab/app/`**:

```
request → features (φ) → factibilidad (aritmética, gratis)
        → creencias con procedencia → dial de garantía A0–A3
        → Π(φ, θ) selectivo con abstención  →  estrategia de engine/agentic
                                                (o fallback react si abstiene)
        → EXPLAIN registrado
```

`understand.py` conserva lo que no es ruteo (follow-ups, NER, rewrite, idioma).

## Estado y orden (decisión del autor, 2026-08-26)

**Primero se mide y selecciona; después se implementa.** El motor no se construye hasta
que el harness termine de medir el catálogo y la selección quede decidida por datos.

1. [x] Código de ejecución copiado (2026-08-26) — 26 archivos, sin referencias de origen
2. [ ] **EN CURSO — medición y selección de patrones** (harness): held-out P8, superficie
       managed P9, y los 3 candidatos verificados del informe de patrones —
       `graph_traverse` (HippoRAG 2405.14831 / GraphReader 2406.14550 / StepChain
       2510.02827: cadenas como traversal de grafo, costo fijo), `extract_compute`
       (LOTUS 2407.11418 / CodeAct 2402.01030: agregación exacta por código),
       `streaming_scan` (Chain-of-Agents 2406.02818: una pasada con estado de arrastre).
       Cada uno entra con predicción registrada antes de correr. Upgrade barato de
       `rewoo` disponible: LLMCompiler 2312.04511 (placeholders + 1 replan acotado)
3. [ ] Adaptadores por los 5 imports internos de la app original:
       `get_model_info`, `ChatRequest`, `redis_cache`, `search_helpers`, `search_service`
4. [ ] Reemplazo del clasificador de `understand.py` por la capa de decisión de lab
5. [ ] **Temporal.io como runtime** (decisión diferida a esta fase), en DOS planos:
       - **Plano de ingesta** (el mejor caso de Temporal): workflow `IngestCollection`
         → fan-out de activities por unidad (parsear → embeber → resumir → extraer
         entidades para el grafo) → `BuildIndexes` → `VerifyIndex` → `Promote`.
         Idempotencia por hash de contenido; 429/backoff como política de retry de
         activity; el event-history es el EXPLAIN de la ingesta. **Un índice candidato
         se promueve solo si no regresiona: la verificación es correr las tareas-sonda
         del harness contra el índice nuevo** (mismo patrón que la promoción de θ).
         La ingesta no se evalúa directo en el harness, pero es lo más evaluado
         indirectamente: la superficie de herramientas gobierna la varianza (50× vs
         1,2× medido), y la superficie es el producto de la ingesta.
       - **Plano de query**: durable execution para la ejecución de paradigmas;
         no toca la capa de decisión ni entra jamás al harness (sin frameworks)
6. [ ] El objetivo medible: corpus gold NUEVO → el motor le gana a todo paradigma fijo
       del harness (brecha de oráculo neta positiva, held-out)

## Reglas

- El sistema de origen no se menciona en ningún documento ni código de MAPO.
- Ejecutado primero, teorizado después: nada entra al paper sin correr acá.
