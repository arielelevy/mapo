# legacy — capa de ejecución anterior (CONGELADA)

**Esto no es el producto y no se evoluciona.** Es la capa de ejecución de un sistema
anterior — código propio del autor — que se conserva por una sola razón: es la única
pieza del repo que resolvió lo que el banco nunca tuvo que modelar (búsqueda sobre un
índice real, scoping por permisos, citas verificadas contra el índice, streaming a un
cliente). Cuando el producto necesite esas piezas, se leen de acá; no se importan.

Se le hizo la revisión a mano completa del 2026-08-27 y se aplicaron los arreglos ANTES
de congelarlo, para que lo que se lea de acá valga la pena leerlo.

Este README documenta el motor **como está**, no como debería estar: el pipeline real, el
mapa de módulos, el subgrafo de recuperación, las cuatro estrategias, y la **revisión a
mano del 2026-08-27** con todo lo que se encontró para mejorar o simplificar. Vale la regla
del proyecto: *ejecutado primero, teorizado después*; acá se documenta lo que corre.

---

## 1. Composición

```
legacy/
└── agentic/                    8.549 LOC, 26 archivos, 0 tests
    ├── load_context.py           entrada: request → estado estructurado
    ├── understand.py             follow-up, idioma, NER, rewrite + CLASIFICADOR (se reemplaza)
    ├── hyde.py                   respuestas hipotéticas por idioma → consultas KNN extra
    ├── pre_fetch.py              recuperación previa a la estrategia + modo descubrimiento
    ├── strategies/               react_agent · dag_strategy · map_reduce · plan_execute
    ├── subgraphs/semantic_search.py   4 ramas paralelas + fusión RRF + rerank
    ├── tools/                    agent_tools (9 tools) · retrieval · cross_document · DAO
    ├── blackboard.py             pizarra compartida (qué se vio, qué falta, qué se encontró)
    ├── context_guard.py          desalojo por crecimiento + extracción de hallazgo
    ├── resolve_entity_links.py   salida: nombres → links de entidad verificados
    ├── state.py                  el estado de LangGraph
    ├── agent_config.py           TODOS los prompts (460 líneas)
    ├── config.py                 TODAS las constantes (sin defaults dispersos)
    ├── cache.py                  cache Redis por usuario
    └── utils.py                  sanitizado, compresión de scratchpad, eventos de UI, embeddings
```

---

## 2. El pipeline real (y lo que falta)

```
   ┌──────────────────────────────────────────────────────────────────────┐
   │  request                                                             │
   └──────────────┬───────────────────────────────────────────────────────┘
                  │
        ┌─────────▼─────────┐   parsea add_entities / add_search_set,
        │  load_context     │   expande search sets, extrae followup_doc_ids
        │  load_context.py  │   de los links citados en respuestas previas,
        └─────────┬─────────┘   arma entity_context y NER por documento
                  │
        ┌─────────▼─────────┐   3 llamadas LLM mini:
        │  understand       │   (a) idioma  (b) tipo de follow-up  (c) clasificación
        │  understand.py    │   → strategy, rewritten_query, key_terms, dominio,
        └─────────┬─────────┘     complexity, needs_decomposition
                  │
        ┌─────────▼─────────┐   sólo si complexity == "complex":
        │  hyde             │   1 llamada → N párrafos hipotéticos (uno por idioma)
        │  hyde.py          │
        └─────────┬─────────┘
                  │
        ┌─────────▼─────────┐   corre el subgrafo semántico ANTES de la estrategia;
        │  pre_fetch        │   si no hay scope, DESCUBRE documentos y los fija
        │  pre_fetch.py     │
        └─────────┬─────────┘
                  │
     ┌────────────┴───────────────────────────────┐
     │            ruteo por `strategy`            │
     ▼            ▼              ▼           ▼    ▼
  react_agent   dag        map_reduce  plan_execute  conversational
  (+exhaustive) (plan→olas→verify→replan→síntesis)      ▲
     │            │              │           │          │
     │            │              │           │          └── NO EXISTE acá
     └────────────┴──────┬───────┴───────────┘
                         │
        ┌────────────────▼──────┐  **bold** → [link](entity:id/tipo), y verifica
        │  resolve_entity_links │  CADA link contra el índice (los inventados se borran)
        └────────────────┬──────┘
                         │
        ┌────────────────▼──────┐
        │  verify_answer        │  NO EXISTE acá (pero react_agent lee su salida:
        │                       │  unsupported_claims, y state.py declara sus campos)
        └───────────────────────┘
```

**Lo que falta para que esto corra de punta a punta** (más que los imports del roadmap):

| Falta | Evidencia |
|---|---|
| **El ensamblado del grafo** (`StateGraph` del orquestador, nodos y aristas condicionales) | no hay ningún `add_node` fuera de `subgraphs/semantic_search.py` |
| **`verify_answer`** | `state.py:146-150` declara `confidence_score`, `unsupported_claims`, `verification_status`, `verify_retried`; `react_agent.py:312` consume el retry que produce |
| **El nodo `conversational`** | `agent_config.py:361` define `CONVERSATIONAL_PROMPT`; nadie lo importa |
| 6 imports de la app de origen | ver §7 |

---

## 3. Mapa de módulos

| Archivo | LOC | Rol | Estado tras la revisión |
|---|---:|---|---|
| `tools/opensearch_repository.py` | 1519 | DAO: queries, filtros, auth, paginado | el más acoplado al origen; 1 fail-open (§8) |
| `strategies/dag_strategy.py` | 973 | plan → olas → verify → replan → síntesis | verificación por longitud (§8) |
| `subgraphs/semantic_search.py` | 692 | 4 ramas + RRF + rerank + cobertura | **3 defectos de ranking (§8)** |
| `strategies/react_agent.py` | 649 | ReAct + pizarra + refine | loop triplicado (§9) |
| `tools/agent_tools.py` | 494 | 9 tools con scope en clausuras | 1 tool siempre vacía (§8) |
| `understand.py` | 491 | comprensión + clasificador en prosa | **lo que reemplaza `lab/app/`** |
| `strategies/plan_execute.py` | 462 | descomposición en sub-consultas | inalcanzable hoy (§5) |
| `agent_config.py` | 460 | todos los prompts | ~15 líneas de prompt muerto (§8) |
| `strategies/map_reduce.py` | 358 | 1 doc por rama, merge final | recorte silencioso a 20 docs (§8) |
| `load_context.py` | 348 | request → estado | 1 no-determinismo (§8) |
| `blackboard.py` | 278 | pizarra compartida | 1 método muerto, campo sobrecargado |
| `tools/retrieval.py` | 271 | formatea el subgrafo para el LLM | KNN duplicado (§9) |
| `state.py` | 236 | TypedDicts + reducer del DAG | — |
| `pre_fetch.py` | 186 | recuperación previa + descubrimiento | pisa `entity_context` (§8) |
| `tools/cross_document.py` | 172 | nombres recurrentes entre documentos | ver `find_recurring_names` (§8) |
| `context_guard.py` | 163 | desalojo por crecimiento | prefijo fijo mágico (§8) |
| `resolve_entity_links.py` | 153 | anti-alucinación de citas | la pieza más sana del módulo |
| `utils.py` | 152 | sanitizado, compresión, embeddings | embeddings por fuera del cliente (§8) |
| `parse_entity_context.py` | 140 | metadata de documentos en 1 msearch | parámetro fantasma (§8) |
| `config.py` | 185 | 45 constantes, sin defaults dispersos | bien: una sola fuente |
| `cache.py` | 81 | cache Redis por usuario | tabla de TTLs decorativa |
| `hyde.py` | 86 | respuestas hipotéticas | temperatura fuera de `config.py` |

---

## 4. El subgrafo de recuperación (lo que hace de verdad)

```
                       rewritten_query + key_terms + hyde_queries
                                        │
        ┌───────────────┬───────────────┼───────────────┬──────────────┐
        ▼               ▼               ▼               ▼              │
   semantic_fts    semantic_entity  semantic_knn   semantic_hyde       │
   BM25 anidado    entity_label     KNN sobre      1 KNN por           │
   en chunks       (keyword+frase)  embeddings     hipótesis           │
        │               │               │               │             │
        │          entity_matches       │               │             │
        │        (NO entra a RRF)       │               │             │
        └───────────────┬───────────────┴───────────────┘             │
                        ▼                                             │
              ┌──────────────────────┐                                │
              │  _rrf_fuse           │  peso 2x para FTS, k=60        │
              │  rango 0,000 - 0,049 │  dedup por contenido           │
              └──────────┬───────────┘                                │
                         ▼                                            │
              ┌──────────────────────┐                                │
              │  _density_rerank     │  suma matches/sqrt(largo)      │
              │  rango 0,0 - 0,3+    │  ← 5x MÁS GRANDE que el RRF    │
              └──────────┬───────────┘     (defecto R2, §8)           │
                         ▼                                            │
              ┌──────────────────────┐                                │
              │  _ensure_coverage    │  NO HACE NADA (defecto R3, §8) │
              └──────────┬───────────┘                                │
                         ▼                                            │
                 fused_entities  ──────────────────────────────────────┘
                         │
                  corte por brecha de score (retrieval.py) → resultados al LLM
```

El diagrama de arriba es el punto más importante de toda la revisión: **la fusión RRF que
le da nombre al retriever queda sepultada por un boost de densidad que es un orden de
magnitud más grande**, y la etapa que debía garantizar cobertura por documento es un no-op.
Los tres defectos están en §8 con la aritmética.

---

## 5. Las cuatro estrategias

```
react_agent (+exhaustive)          dag_strategy
──────────────────────────         ─────────────────────────────────────────
 pizarra ← prefetch (10 ó 20)       dag_plan  → 1-4 sub-preguntas, olas por deps
     │                                  │
 loop de tools (20 ó 40 iter)       ┌───▼────┐  Send() paralelo, tope 4 por ola
     │  ├ dedup por tool+args       │ olas   │  cada sub-agente: 10 iter, 120s,
     │  ├ context_guard (desaloja)  │        │  tope 30 tools, pizarra compartida
     │  └ scratchpad (comprime)     └───┬────┘
     │                                  │
 nudge si quedan pendientes          dag_verify  → completitud 0-1 por sub-pregunta
     │                                  │
 grounding search (busca con        ¿avg >= 0,8 o todos "accept"?
 la propia respuesta)                   │            │
     │                                 sí            no → dag_replan (máx 3)
 refine con citas (streaming)           │                    │
                                   dag_synthesize ◄──────────┘

map_reduce                          plan_execute
──────────────────────────          ─────────────────────────────────────────
 lista docs del scope                pe_plan → 2-6 sub-consultas independientes
     │                                   │
 Send() 1 por doc (tope 20)          Send() 1 por sub-consulta
     │                                   │
 lee documento ENTERO                cada una: mini ReAct, 3 iter, pizarra
 (2 queries, no 1 por página)            │
     │                               pe_aggregate (streaming)
 parte en trozos de 320K si no entra
     │
 merge final (streaming)
```

**Alcanzabilidad hoy**: `understand.py` descarta `result.strategy` salvo para
`conversational`, y decide con `needs_decomposition` / `complexity`. Resultado:

| Estrategia | ¿Se alcanza? |
|---|---|
| `react_agent` / `react_agent_exhaustive` | sí (el caso por defecto) |
| `dag` | sí (`needs_decomposition == True`) |
| `map_reduce` | **no**, sólo por `forced_strategy` |
| `plan_execute` | **no**, sólo por `forced_strategy` |
| `conversational` | se rutea, pero el nodo no existe acá |

---

## 6. Contexto: pizarra + guardia + scratchpad

Tres mecanismos distintos atacan el mismo problema (el contexto crece y se re-envía en cada
turno). Conviene verlos juntos porque **se solapan**:

```
  resultado de tool
        │
        ├─► scratchpad_compress   si > 50.000 chars → 1 LLM extrae → tope 3.000
        │   (utils.py)            el crudo se guarda aparte para la verificación
        │
        ├─► context_guard         si el contexto CRECIÓ > umbral desde la última vez →
        │   (context_guard.py)    desaloja UN ToolMessage viejo y lo reemplaza por
        │                         "[Finding: ...]" (1 LLM más)
        │
        └─► blackboard            lo desalojado queda como hallazgo permanente,
            (blackboard.py)       re-inyectado como HumanMessage antes de cada llamada
```

Costo real por resultado grande de tool: **hasta 2 llamadas LLM extra** (comprimir +
extraer hallazgo) antes de que el modelo lo vea. Es una decisión defendible, pero no está
medida: es exactamente el tipo de cosa que el banco de `../lab/` puede cuantificar (la
superficie de herramientas gobierna la varianza: 50x vs 1,2x medido).

---

## 7. Acoplamiento con la app de origen

| Módulo | Línea | Símbolo | Para qué |
|---|---:|---|---|
| `config.py` | 12 | `get_model_info` | resolver el modelo "mini" y sus overrides |
| `state.py` | 9 | `ChatRequest` | tipo del request en el estado |
| `load_context.py` | 18 | `ChatRequest` | parseo del request |
| `cache.py` | 17 | `get_redis_global_client` | cache de permisos por usuario |
| `tools/opensearch_repository.py` | 88 | `apply_standard_search_filters` | filtros obligatorios de índice |
| `tools/opensearch_repository.py` | 89 | `SearchService`, `init_search_service` | proxy de búsqueda + filtro de workspaces |

Terceros: `langchain_core`, `langgraph`, `pydantic`, `openai` (sólo embeddings, §8-I1),
`langsmith` (un `@traceable`), `pandas` (sólo la tool `analyze_table`).

El nombre del sistema de origen **ya no aparece** en ningún archivo (se purgó de los
docstrings el 2026-08-27). Quedan identificadores que cruzan la frontera del adaptador
(`timbr_token`, `ChatRequest`): se renombran cuando se escriban los adaptadores, no antes.

---

## 8. Revisión a mano (2026-08-27) — hallazgos

Revisión manual, archivo por archivo, de los 26 módulos. Criterio: **defecto** es algo que
produce una respuesta peor o menos reproducible; **degradación silenciosa** es perder
capacidad sin que nadie se entere; **contrato falso** es que el código diga una cosa y haga
otra. No se reportan como defectos las decisiones deliberadas y documentadas.

### Recuperación — los tres que más pesan

**R1 · `_rrf_fuse` no fusiona lo que su comentario dice fusionar** ·
`subgraphs/semantic_search.py:543`
El score se acumula por `entity_id` y recién después se deduplica por clave de contenido,
quedándose con la copia mejor rankeada. Pero el docstring de `_content_key` dice que la
clave "fusiona los scores RRF para que el contenido único rankee más alto". No los fusiona:
los descarta. La misma página que llega por dos PDFs distintos aporta la mitad de la
evidencia que debería.

**R2 · el rerank por densidad tapa al RRF** · `subgraphs/semantic_search.py:583`
`e.score = score_rrf + matches/sqrt(largo)`. Con k=60 y peso 2x, el score RRF de un
resultado en el tope es `2/61 = 0,033`; sumando dos ramas, ~0,049 como máximo. La densidad,
con 10 apariciones del término en 3.000 chars, da `10/54,8 = 0,18`. **El "boost" es 4-5x
todo el rango de la señal que pretende ajustar**: el orden final lo decide la frecuencia de
términos, no la fusión. El comentario dice "preservando el ranking RRF"; es falso.

**R3 · `_ensure_coverage` es un no-op** · `subgraphs/semantic_search.py:604`
Promete "al menos un chunk por documento único", pero agrupa por `e.entity_id`, que después
de `_rrf_fuse` es único por resultado. Entonces `doc_counts[...] == 1` siempre, la condición
`> 1` nunca se cumple, `worst_idx` queda en `None` y **no se reemplaza nada jamás**.
Equivale a `entities[:max_results]`. Debería agrupar por `source_entity_uid` (el documento
padre), que es lo que la función dice.

**R4 · `provenance` es una constante, no una procedencia** ·
`subgraphs/semantic_search.py:656`
Siempre dice `"semantic_search+rrf+density"`. Si la rama FTS falla (el `except` la deja en
`[]`), la respuesta igual afirma que hubo fusión FTS+KNN. Para un producto cuya tesis es
registro y procedencia, la procedencia tiene que decir **qué ramas contribuyeron de hecho**.

### Degradación silenciosa (el patrón repetido)

| # | Dónde | Qué se pierde sin avisar |
|---|---|---|
| **S1** | `utils.py:140` | sin `OPENAI_API_KEY`, `get_embedding` devuelve `[]` y la rama KNN se apaga: la búsqueda queda en BM25 puro, con un `INFO` en el log y nada en la respuesta |
| **S2** | `load_context.py:229` | si falla expandir un search set, se sigue con menos documentos y el usuario recibe una respuesta "completa" sobre un corpus recortado |
| **S3** | `strategies/map_reduce.py:110` | con más de 20 documentos se procesan los primeros 20 y **los demás no se mencionan** — en la estrategia cuyo objetivo es la exhaustividad |
| **S4** | `strategies/map_reduce.py` (gather) | una parte que falla se loguea y se descarta; el resumen final no dice que faltó |
| **S5** | `tools/agent_tools.py:268` | la descripción de `read_fragment` promete 10 ids por llamada; el código procesa `ids[:5]` y no avisa de los cortados |

Los cinco son el mismo error de diseño: **la falla se convierte en silencio en vez de en un
campo del resultado**. Una respuesta construida sobre menos material del que el usuario
cree no es una respuesta peor: es una respuesta que no se puede evaluar.

### Defectos de comportamiento

**B1 · `find_recurring_names` siempre devuelve lista vacía** ·
`tools/agent_tools.py:352` + `tools/cross_document.py:73`
`do_find_recurring_names(ids, _cfg)` se llama sin `ner_entities` ni `extra_names`, y esos
son los **únicos** orígenes del conjunto de candidatos. Con candidatos vacíos hay un
`return []` temprano. La tool responde `{"recurring_names": [], "total_recurring": 0}`, que
el modelo lee como "no hay nombres recurrentes" en vez de "la herramienta no corrió". Y su
descripción es la más enfática de todas: *"CALL THIS FIRST for any cross-document
name/entity question"*. **La tool más promocionada del catálogo es un no-op que además
miente el resultado.** Arreglo: pasarle `state["doc_ner_entities"]` (ya cargado en
`load_context`) y `entity_types_filter`.

**B2 · `read_fragment` dice "ya leído" de fragmentos que nunca leyó** ·
`tools/agent_tools.py:256-296`
Un id que no está en la pizarra se cuenta como `skipped`; si todos lo son, la respuesta es
`{"already_read": true, ...}`. El agente concluye que ya vio ese contenido y deja de
buscarlo. Los dos casos ("ya lo leíste" y "no te dejo leer esto porque no salió de una
búsqueda") tienen que ser respuestas distintas.

**B3 · `investigate` penaliza registrar hallazgos** · `tools/agent_tools.py:404`
Cada nota agrega **un hallazgo y además un ítem pendiente** a la pizarra. Como el nudge y el
porcentaje de cobertura se calculan sobre ítems pendientes, anotar lo que se encontró hace
que el agente parezca menos completo y dispara más nudging. El incentivo está al revés:
registrar conocimiento debería cerrar trabajo, no abrirlo.

**B4 · `record_findings` no puede sobrescribir el snippet del prefetch** ·
`blackboard.py:146-149`
El campo `findings` tiene dos significados (snippet crudo del prefetch y hallazgo extraído),
y la guarda `not item.findings` hace que el hallazgo real nunca reemplace al snippet. El
parche existente es `clear_snippet` desde el guardia de contexto. Además **`record_findings`
no lo llama nadie**: es API muerta. Arreglo de raíz: dos campos, `snippet` y `findings`.

**B5 · las pistas de búsqueda se pisan antes de usarse** ·
`understand.py:290` → `pre_fetch.py:181`
`understand` agrega `## Search hints` con los `key_terms` al `entity_context`; `pre_fetch`
**reconstruye `entity_context` entero** y las borra. Nunca llegan al prompt de la estrategia.
En el mismo camino, la asignación de `entity_context` de `_discover_docs` (`pre_fetch.py:98`)
también queda pisada siempre: es código muerto.

**B6 · orden no determinista de documentos** · `load_context.py:229`
`context_docs = list(set(context_docs + expanded_ids))` — el orden de un `set` de strings
depende del hash aleatorizado por proceso. El orden viaja al `entity_context`, o sea al
prompt: **dos corridas idénticas producen prompts distintos**. Para un motor que tiene que
ser reproducible, esto es de los peores. Arreglo: `list(dict.fromkeys(...))`.

**B7 · el presupuesto de refine se pide, no se aplica** ·
`strategies/react_agent.py:578` y siguientes
Se calcula un `max_context_chars` adaptativo (60% de la ventana del modelo) y acto seguido
se lo topea a 70.000: para cualquier modelo con ventana mayor a ~29K tokens el cálculo
adaptativo no cambia nada. Después, al resumir por partes, se le **pide** al LLM "keep under
N characters" y no se trunca la salida: el presupuesto puede excederse igual. Contrasta con
`scratchpad_compress`, que sí corta.

**B8 · fail-open en el filtro de búsqueda** · `tools/opensearch_repository.py:325`
Los filtros obligatorios y el de workspaces se inyectan sólo `if len(lines) >= 2 and
len(lines) % 2 == 0`. Un payload con formato inesperado se envía **sin filtros**. Una
precondición que no se cumple tiene que abortar, no dejar pasar.

**B9 · `cached_workspaces == []` se interpreta como "sin filtro"** ·
`tools/opensearch_repository.py:333`
Es correcto si y sólo si el servicio de origen garantiza que lista vacía significa "no hace
falta filtrar" y nunca "este usuario no tiene workspaces" ni un fallo transitorio. El valor
se cachea 5 minutos en Redis. **Verificar contra el servicio antes de dar por buena esa
semántica**; si es ambigua, distinguir los dos casos explícitamente.

**B10 · verificación por longitud** · `strategies/dag_strategy.py:650`
`all_long = all(len(r) > 1500 ...)` → completitud 1,0 y `accept` para todas las
sub-preguntas, sin llamar al verificador. Un resultado largo y equivocado pasa; uno corto y
correcto no. Es medir la cosa por su tamaño.

**B11 · `forced_strategy` apaga el manejo de follow-ups** · `understand.py:197-215`
El camino forzado retorna temprano con `history_relevant=False`, `history_text=""` y
`followup_type="standalone"`: forzar estrategia hace perder, sin decirlo, la resolución de
referencias y el scope a documentos citados.

**B12 · `build_document_metadata` no hace nada si la consulta está vacía** ·
`parse_entity_context.py:27`
`if not doc_ids or not user_query: return {}, {}, []`, y `user_query` **no se usa** en
ninguna parte de la función. Un parámetro fantasma que además apaga la metadata. Y a
diferencia del resto del módulo, si el msearch falla levanta `RuntimeError` sin envolver: la
política de fallas es inconsistente dentro del mismo nodo.

### Código muerto y contratos falsos

| # | Dónde | Qué |
|---|---|---|
| D1 | `understand.py:256-275` | 20 líneas de guardas comentadas, con el comentario "currently inactive since strategy is always react_agent" — falso: hoy rutea a `dag`, `conversational` y `exhaustive`. Y el docstring de la clase sigue prometiendo esas guardas |
| D2 | `agent_config.py:38-52` | las reglas 1-6 de selección de estrategia del `UNDERSTAND_PROMPT`: `understand.py` descarta `result.strategy` salvo `conversational`, así que ese bloque **se paga en tokens en cada request y no decide nada** |
| D3 | `strategies/react_agent.py:268` | `AGENT_CONFIGS.get("react_agent", AGENT_CONFIGS["react_agent"])` — un `.get` con su propio valor como default |
| D4 | `strategies/react_agent.py:518` | `refine_model = None` con el comentario "use GPT-5 for exhaustive": la variable nunca cambia |
| D5 | `agent_config.py:426` | `AgentConfig.tools`, `.temperature` y `.name` no se leen nunca; `AGENT_CONFIGS["map_reduce"]` tampoco. Sólo sobreviven `system_prompt` y `max_iterations` de una entrada |
| D6 | `blackboard.py:146` | `record_findings` sin llamadores |
| D7 | `parse_entity_context.py:121` | `extract_entities_from_messages` sin llamadores |
| D8 | `config.py:53` | `get_mini_model_name` sin llamadores (`get_chat_model(mini=True)` lo reimplementa) |
| D9 | `cache.py:20-29` | `CACHE_ENTRIES` se presenta como "single source of truth" pero cualquier nombre pasa con TTL 300 por default; `cache_ping` y `cache_stats` sin llamadores |
| D10 | `strategies/map_reduce.py` (docstring) | dice "si excede `MAX_CHUNKS_PER_LLM_CALL` chars" cuando el corte es `MAX_CHUNKS_PER_LLM_CALL * 4000` |
| D11 | `config.py:124` | `MAX_MAP_REDUCE_LLM_CALLS` se documenta como "total LLM calls" pero se aplica como "cantidad de documentos": un documento partido en 5 gasta 5 llamadas y el presupuesto no se entera |
| D12 | `strategies/plan_execute.py:207` | el docstring dice `MAX_AGENT_ITERATIONS` (20); el código usa `PE_SUB_AGENT_ITERATIONS` (3) |

### Menores

| # | Dónde | Qué |
|---|---|---|
| I1 | `utils.py:128-152` | `get_embedding` llama a la API de OpenAI directo, con su propio singleton y su propia env var, cuando todo el resto pasa por el cliente inyectado |
| I2 | `context_guard.py:74` | `for i in range(3, end)` — asume que los tres primeros mensajes son el prefijo fijo; si la forma del prompt cambia, desaloja el sistema o deja de desalojar |
| I3 | `context_guard.py` | sin `config` no hay extracción de hallazgo y el mensaje se reemplaza por `[Evicted]`: se destruye contenido sin dejar resumen. Mejor no desalojar |
| I4 | `hyde.py:56` | `temperature=0.7` hardcodeada, cuando las cinco temperaturas del sistema son constantes en `config.py` |
| I5 | `strategies/dag_strategy.py:445` | se le pasa un presupuesto de **tamaño** de contexto (`DAG_CONTEXT_CHAR_LIMIT // olas`) al parámetro de **crecimiento** del guardia: son magnitudes distintas |
| I6 | `strategies/dag_strategy.py` (replan) | por "diminishing returns" se vuelve a verificar con la misma entrada 1-2 veces más: llamadas LLM idénticas y desechadas |
| I7 | `strategies/dag_strategy.py:930` y `plan_execute.py:415` | se le inyecta `board.render()` (incluidas las líneas "queries ya ejecutadas, NO repetir") al contexto de síntesis: contabilidad operativa dentro del material de la respuesta |
| I8 | `tools/agent_tools.py:428` | la descripción de `analyze_table` afirma "safe subset — no arbitrary code" sobre `pandas.query()`. `pandas.query` **no es un sandbox**; la entrada la genera un modelo. Verificar o bajar la afirmación |
| I9 | `strategies/map_reduce.py` | es la única estrategia que no devuelve `tool_context`: la verificación de fidelidad se queda sin material justo ahí |
| I10 | `resolve_entity_links.py:78` | `batch_verify_entity_ids` devuelve `dict[str,str]` o `dict[str,dict]` según un flag (de ahí el `cast`): una función, dos formas de retorno |
| I11 | varios | `List`/`Dict`/`Tuple`/`Optional` legacy conviviendo con sintaxis moderna; f-strings sin placeholders (`pre_fetch.py:152`, `understand.py:281`) |

---

## 9. Qué simplificar

### S-1 · El loop de tools está escrito tres veces (y ya divergió)

```
react_agent._run_tool_loop        dag_execute._run_loop         pe_execute_subquery
──────────────────────────        ─────────────────────         ───────────────────
 inyecta pizarra           sí      inyecta pizarra        sí      inyecta pizarra      sí
 guardia de contexto       sí      guardia de contexto    sí      guardia de contexto  sí
 comprime resultado        sí      comprime resultado     sí      comprime resultado   sí
 dedup tool+args           sí      dedup tool+args        NO      dedup tool+args      NO
 marca visitados (read)    sí      marca visitados        NO      marca visitados      NO
 tope de llamadas totales  NO      tope de llamadas       sí      tope de llamadas     NO
 tope de misma tool        NO      tope de misma tool     sí      tope de misma tool   NO
 timeout                   NO      timeout (120s)         sí      timeout              NO
```

Las diferencias **no son de diseño, son accidentes**: cada copia recibió el arreglo que las
otras no. Un solo `run_tool_loop(llm, tools, messages, *, max_iter, limits, board, guard,
extract_fn, timeout)` elimina ~200 líneas triplicadas y, sobre todo, hace que "estructura de
control" vuelva a ser una cosa explícita y única — que es literalmente la tesis del paper.

### S-2 · Otras duplicaciones concretas

| Duplicado | Dónde | Unificación |
|---|---|---|
| KNN implementado dos veces | `tools/retrieval.py:knn_search` importa 5 privados de `semantic_search` adentro de la función | que `knn_search` invoque la rama del subgrafo |
| `pe_aggregate` ≈ `dag_synthesize` | ambos: juntar sub-resultados, recortar, pegar pizarra, sintetizar en streaming | un `synthesize(sub_results, prompt, state)` |
| `pe_plan` ≈ `dag_plan` (preámbulo) | regex de labels + hint de dominio + idiomas | `build_planner_context(state)` |
| Duck-typing de mensajes | `load_context.py` repite 8 veces `getattr(x, k, None) or (x.get(k) if isinstance(x, dict) else None)` | un `_field(obj, name, default="")` |
| Escaneos lineales de la pizarra | 6 métodos recorren `self._items` buscando por `entity_id` | índice `dict[str, BlackboardItem]` |
| Doble normalización de nombres | `cross_document._norm` ya colapsa variantes de 2 palabras; `_merge_name_variants` vuelve a hacerlo | una sola capa |

### S-3 · Lo que se puede sacar entero

`UNDERSTAND_PROMPT` reglas 1-6 (D2), guardas comentadas de `understand.py` (D1),
`AgentConfig.tools/temperature/name` (D5), `record_findings` (D6),
`extract_entities_from_messages` (D7), `get_mini_model_name` (D8), `cache_ping`/`cache_stats`
(D9), y la asignación muerta de `entity_context` en `_discover_docs` (B5).

### S-4 · Una llamada LLM menos por request

`_detect_language` y `_resolve_followup` son dos llamadas mini que ven **exactamente el mismo
material** (la consulta, y para la segunda el historial) y ninguna ve documentos. Un solo
esquema estructurado `{query_language, followup_type}` conserva la propiedad que justifica el
aislamiento (no contaminarse con el idioma de los documentos) y ahorra una llamada por
request.

---

## 10. Por qué esto justifica la capa de decisión

La revisión encontró, sin buscarlas, tres formas de la misma patología — y las tres son
exactamente lo que `../lab/app/` reemplaza:

**(a) Ruteo en prosa que no se puede auditar.** El `UNDERSTAND_PROMPT` tiene seis reglas de
selección de estrategia cuyo resultado se descarta (D2); la decisión real termina saliendo de
dos campos (`needs_decomposition`, `complexity`) que el mismo LLM inventa en la misma llamada.
No hay registro de por qué se eligió, ni forma de reproducirlo.

**(b) Umbrales mágicos repartidos por el código.** `> 1500` chars = completo (B10), `>= 0,8`
= listo, semilla 10 ó 20, nudge si quedan ≤ 15 ó ≤ 50, `domain == "legal"` ⇒ siempre complejo,
`> 200` chars = vale la pena guardar. Ninguno medido, todos decidiendo.

**(c) Instrucciones de ruteo escondidas en descripciones de tools.** La de
`find_recurring_names` son diez líneas de keywords en dos idiomas ("CALL THIS FIRST...") —
para una tool que devuelve vacío siempre (B1).

La capa de decisión de `../lab/app/` sustituye las tres por lo mismo que ya corre en el banco:

```
request → φ (features)
        → factibilidad ARITMÉTICA (gratis, antes de gastar un token)
        → creencias tipadas con procedencia (COMPUTED / OBSERVED / ELICITED / ASSUMED)
        → dial de garantía A0-A3 (piso de procedencia por request)
        → Π(φ, θ) selectivo CON ABSTENCIÓN → estrategia de la capa de ejecución
                                             (o fallback react si no hay margen)
        → EXPLAIN registrado (se puede reproducir la decisión)
```

`understand.py` conserva lo que no es ruteo: follow-ups, NER, rewrite, idioma.

Y hay una lectura al revés que también sirve: **la factibilidad aritmética hubiera evitado
S3** (map_reduce recortando a 20 documentos en silencio) — con 40 documentos en scope,
map_reduce es *infactible* por conteo de llamadas y el registro lo dice, en vez de correr
sobre la mitad y devolver una respuesta que parece completa.

---

## 11. Orden de trabajo

**Primero se mide y se selecciona; después se implementa.** El motor no se construye hasta
que el harness termine de medir el catálogo y la selección quede decidida por datos.

1. [x] Código de ejecución copiado (2026-08-26) — 26 archivos
2. [x] Purga del nombre del sistema de origen en docstrings (2026-08-27)
3. [x] Revisión a mano completa de los 26 módulos (2026-08-27) — §8 y §9
4. [ ] **EN CURSO — medición y selección de patrones** (harness): held-out P8, superficie
       managed P9, y los 3 candidatos verificados del informe de patrones —
       `graph_traverse` (HippoRAG 2405.14831 / GraphReader 2406.14550 / StepChain
       2510.02827: cadenas como traversal de grafo, costo fijo), `extract_compute`
       (LOTUS 2407.11418 / CodeAct 2402.01030: agregación exacta por código),
       `streaming_scan` (Chain-of-Agents 2406.02818: una pasada con estado de arrastre).
       Cada uno entra con predicción registrada antes de correr. Upgrade barato de
       `rewoo` disponible: LLMCompiler 2312.04511 (placeholders + 1 replan acotado)
5. [ ] Arreglos que no dependen de la medición y ya están identificados:
       R1-R4 (recuperación), B1/B2/B6 (impacto directo en la respuesta),
       S-1 (unificar el loop de tools)
6. [ ] Adaptadores por los 6 imports de la app original (§7) **y las tres piezas ausentes**:
       el ensamblado del grafo, `verify_answer` y el nodo `conversational`
7. [ ] Reemplazo del clasificador de `understand.py` por la capa de decisión de `../lab/app/`
8. [ ] **Temporal.io como runtime** (decisión diferida a esta fase), en DOS planos:
       - **Plano de ingesta** (el mejor caso de Temporal): workflow `IngestCollection`
         → fan-out de activities por unidad (parsear → embeber → resumir → extraer
         entidades para el grafo) → `BuildIndexes` → `VerifyIndex` → `Promote`.
         Idempotencia por hash de contenido; reintentos con backoff como política de
         retry de activity; el event-history es el EXPLAIN de la ingesta. **Un índice candidato
         se promueve solo si no regresiona: la verificación es correr las tareas-sonda
         del harness contra el índice nuevo** (mismo patrón que la promoción de θ).
         La ingesta no se evalúa directo en el harness, pero es lo más evaluado
         indirectamente: la superficie de herramientas gobierna la varianza (50x vs
         1,2x medido), y la superficie es el producto de la ingesta.
       - **Plano de query**: durable execution para la ejecución de paradigmas;
         no toca la capa de decisión ni entra jamás al harness (sin frameworks)
9. [ ] El objetivo medible: corpus gold NUEVO → el motor le gana a todo paradigma fijo
       del harness (brecha de oráculo neta positiva, held-out)

---

## 12. Reglas

- El sistema de origen no se menciona en ningún documento ni código de MAPO.
- Ejecutado primero, teorizado después: nada entra al paper sin correr acá.
- Los patrones se distinguen por **estructura de control de flujo**, jamás por fraseo.
- Una falla no se convierte en silencio: se convierte en un campo del resultado.
