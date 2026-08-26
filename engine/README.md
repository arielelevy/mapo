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
**capa de decisión de `../paperlab/app/`**:

```
request → features (φ) → factibilidad (aritmética, gratis)
        → creencias con procedencia → dial de garantía A0–A3
        → Π(φ, θ) selectivo con abstención  →  estrategia de engine/agentic
                                                (o fallback react si abstiene)
        → EXPLAIN registrado
```

`understand.py` conserva lo que no es ruteo (follow-ups, NER, rewrite, idioma).

## Estado

- [x] Código de ejecución copiado (2026-08-26) — 26 archivos, sin referencias de origen
- [ ] Adaptadores por los 5 imports internos de la app original:
      `get_model_info`, `ChatRequest`, `redis_cache`, `search_helpers`, `search_service`
- [ ] Reemplazo del clasificador de `understand.py` por la capa de decisión de paperlab
- [ ] El objetivo medible: corpus gold NUEVO → el motor le gana a todo paradigma fijo
      del harness (brecha de oráculo neta positiva, held-out)

## Reglas

- El sistema de origen no se menciona en ningún documento ni código de MAPO.
- Ejecutado primero, teorizado después: nada entra al paper sin correr acá.
