# Scouting de patrones — 2026-08-26 (noche)

Registro de lo cosechado buscando el próximo candidato de la fila, después del
screening de los tres verificados. Fuente de los candidatos anteriores: el análisis
de ChatGPT en `..\..\chat\whitepaper\a.md` (ya cosechado — de ahí salieron
graph_traverse / extract_compute / streaming_scan y los "patrones reales para QA":
stateful chaining, circuit breakers, routing de topología, lectura adaptativa).

## Estado de la fila tras el screening de hoy (gpt-5-chat, gold_deep)

| Candidato | Veredicto | Dato |
|---|---|---|
| `graph_traverse` | **FALSIFICADO (P10a)** | u=0.0 en las 6 celdas, incluidas las de su tesis (c3-000-h1, c3-001-h2). Pagó ~280k de índice y respondió "Not found" leyendo 4/48 unidades. Las cadenas de este corpus NO son adyacencia de entidades. |
| `extract_compute` | **INFACTIBLE bajo presupuesto de producción** (decisión del autor: la infactibilidad ES el resultado) | El gate lo rechazó antes del primer token: proyecta ~580k vs presupuesto declarado 60k (eje budget). P11a/P11b quedan no-evaluables bajo este presupuesto. |
| `streaming_scan` | **INFACTIBLE ídem** | P12a exigía costo ≈ contenido×1 (~483k), incompatible por construcción con 60k. P12a/P12b no-evaluables. |

Decisión del autor (2026-08-26): NO se re-corre con presupuesto inflado. El nicho
abierto que queda: **celdas acopladas (C3) fuera de ventana a costo acotado** — hoy
solo las resuelve react (control en el MODELO: lotería de costo, colapsa en nano).

## Papers leídos (2026-08-26)

### DocTrace — "Trace Only What You Need: Structure-Aware On-Demand Hypergraph Memory for Long-Document QA" (arxiv 2606.10921)
- Construye memoria de estructura **on-demand durante el razonamiento, no upfront**:
  la sub-pregunta dispara la selección de semillas (relevancia semántica+léxica+entidad)
  y solo las regiones seleccionadas pagan construcción de memoria.
- Contraste directo con nuestro graph_traverse: el índice global de entidades pagó
  280k y no sirvió; DocTrace argumenta trazar desde la semilla solo lo necesario.
- Su orquestación usa DAGs de dependencias con re-planeo LLM (eso NO lo importamos:
  dag_strategy ya mostró la entropía de descomposición + replaneo).
- Lección tomada: **la estructura útil es local al anclaje y se descubre siguiendo el
  texto, no indexando el corpus**.

### PRISM — "Agentic Retrieval with LLMs for Multi-Hop QA" (arxiv 2510.14278)
- Sub-preguntas secuenciales; el retrieval de cada hop se condiciona con el resultado
  del hop anterior; criterio de parada explícito.
- Limitaciones que ellos mismos reportan: propagación de errores entre hops y
  dependencia fuerte del modelo para descomponer.
- Lección tomada: **condicionar la búsqueda con el resultado anterior** es el
  mecanismo correcto para acoplamiento; la DESCOMPOSICIÓN de la pregunta es la parte
  que nuestros datos ya falsificaron (plan_execute/dag). Multi-hop por descomposición:
  medio descartado (decisión del autor — "es similar a dag").

### BAGEN — "Are LLM Agents Budget-Aware?" (arxiv 2606.00198)
- Miden si los agentes estiman su presupuesto restante: **optimismo universal** (todos
  los modelos subestiman lo que les falta; los débiles son MÁS optimistas).
- Reconocimiento tardío del fracaso: mantienen >70% de confianza de éxito habiendo
  quemado 60% del presupuesto; recién alarman en el último 20%.
- Lo que funciona: **early-stopping por política determinística** (ahorra 28-64% de
  tokens en trayectorias fallidas a costo de 1.6-4.2 pp de éxito). Lo que no: pedirle
  al LLM que estime intervalos de costo (47% de cobertura incluso post-training).
- Validación externa de nuestras invariantes: el presupuesto lo gobierna el código
  (gate aritmético + breakers contables), jamás el juicio del modelo.

### Otros hits relevantes (no leídos a fondo)
- ContextBudget (arxiv 2604.01664): compresión de contexto como problema de decisión
  secuencial bajo presupuesto explícito.
- Self-GC (arxiv 2607.00692), MemOCR (2601.21468), SPD-RAG (2603.08329).
- Literatura de orquestación 2026: coordinación multi-agente ≈ 15× tokens de un chat;
  ~37% de fallas son de coordinación — coherente con nuestra "entropía de agentes".

## El patrón propuesto: `pointer_chase` (invención propia, 2026-08-26)

**Tesis**: en este corpus una cadena acoplada es una secuencia de punteros visibles
en el TEXTO del ancla ("ver B", un campo que refiere a otra unidad), que solo se
revela una unidad a la vez. No hace falta índice global (graph_traverse falsificado),
ni descomposición (plan/dag falsificados), ni tool-loop con historia (react: lotería
O(historia), colapso nano). Hace falta: anclar por retrieval, y un bucle EN CÓDIGO
donde el LLM actúa de sensor sobre UNA unidad por vez.

**Mecanismo** (control 100% en código; el LLM jamás elige herramientas):
1. Semilla: `search(question)` — determinística; candidatos de anclaje.
2. Sensor de anclaje: 1 llamada corta → proposición `{"start": "<unit-id>"}`,
   validada contra los ids listados (id inválido → top-1 determinístico).
3. Bucle de persecución (hop 1..H_MAX, H_MAX por ARITMÉTICA:
   `min(cap, allowance // unidad_media)` — en gold_deep ≈ 3, suficiente para h1/h2):
   - código lee la unidad actual (`read`, contabilidad del surface);
   - sensor: pregunta + ledger tipado (hechos acumulados, chico) + texto de la unidad
     → JSON `{"fact": "...", "next": "<unit-id> | SEARCH:<query> | DONE | DEAD_END"}`;
   - código valida: id inexistente = alucinación contada (breaker a la 2ª);
     unidad ya visitada = stall (breaker a la 2ª); SEARCH → keyword_search
     determinístico, primer hit no visitado; DONE/DEAD_END → salir.
4. Solve: 1 llamada con pregunta + ledger (sin historia de conversación).

**Qué raíz ataca cada propiedad**:
- Sin historia reenviada → raíz O(historia) (la de rewoo, pero CON observación).
- Una unidad por llamada → contexto acotado por construcción (raíz evidencia>ventana).
- H_MAX aritmético + breakers de stall/alucinación → sin lotería ni runaway (BAGEN:
  el código para, no el optimismo del modelo).
- Estructura on-demand desde el ancla (DocTrace) → sin índice global.
- Control en estructura, no en modelo → apuesta a transferir a nano (P13a) justo en
  el nicho donde react colapsa. Si transfiere, MAPO rutea acoplamiento a precio nano.

**Costo estimado por celda c3 (gold_deep)**: ancla ~1k + ≤3 hops × ~11k + solve ~1k
≈ 35k tokens. Screening propuesto (niche c3-000-h1/c3-001-h2 repeat=2 + anti-nicho
c2-000-w48/c5-000-w48 repeat=1) ≈ **~210k tokens gpt-5-chat**.

**Predicciones borrador (a registrar en README.md antes de correr)**:
- P14a: resuelve c3-000-h1 y c3-001-h2 (gold_deep) con u ≥ 0.9 a costo por celda
  ≤ 1/3 de la mediana de react en esas celdas, con dispersión entre réplicas ≤ 1.5×
  (el bucle es código: no hay lotería). Si falla: las cadenas del corpus no son
  punteros visibles en el texto — el acoplamiento exige búsqueda gobernada por el
  modelo después de todo.
- P14b: en el anti-nicho (c2 cobertura, c5 contradicción) para dentro de su tope de
  hops (costo ≤ H_MAX × unidad media, sin runaway) y falla honesto (DEAD_END o
  respuesta equivocada, `hallucinated_units = 0`), no por invención. Si falla: la
  contabilidad de stall está mal especificada — el chase deambula en vez de parar.
- P14c (después, nano): siendo estructura-gobernado, su veredicto c3 transfiere a
  nano (Δu ≤ 0.25) donde react colapsó. Si falla: leer punteros exige juicio del
  modelo — el argumento de estructura de P13a no se extiende al acoplamiento.

## Diseño guardado: arquitectura de memoria de agente (2026-08-26)

Imagen: `notes/2026-08-26-ai-memory-diseno.jpg` (original en el Desktop del autor,
`1787754820210.jpg`). El autor lo marca como **diseño valioso**. Contenido:

- Hub central **AI Memory** conectado a: base (PostgreSQL/MongoDB/SQLite/OKF) con
  vector data + metadata; **Dreams**; **RFC Process (Reflect, Consolidate and
  Forget)**; y **MCP** hacia Agent extensions (plans, goals, LSP, sub-agents,
  web fetch/search).
- Dos niveles de memoria operativa: **OM (short-term)** y **Consolidated OMs
  (long-term)** — la consolidación corre por el proceso RFC, offline.
- **Session** segmentada (C1 | 01 02 03) que habla con DOS modelos: **Fast LLM**
  (barato, para lo mecánico) y **LLM** (para lo que exige juicio).
- Agent en el medio: usuario ↔ prompt ↔ agent ↔ session; el agent lee OM/OMs pero
  la memoria la gobierna el hub, no el agent.

Resonancia con lab: es la misma familia de ideas que `consolidation.py` +
`store.py` (beliefs/calibration/dreams/policies/propositions en el LearningStore, el
ciclo copy-on-write con guarda de promoción = el RFC). La partición Fast LLM/LLM es
exactamente la decisión que P13a/P13b están midiendo (¿qué regiones puede llevar un
modelo nano?). Candidato a figura/argumento del paper y a roadmap del producto
(superficie managed + memoria consolidada por tarea).

## Veredicto del screening de pointer_chase (2026-08-27, gpt-5-chat, gold_deep)

**P14a FALSIFICADA — pointer_chase no promovido.** u=0.0 en las 4 filas del nicho
(c3-000-h1 ×2, c3-001-h2 ×2). El diagnóstico fino difiere de la cláusula registrada:

- **El fallo fue el ANCLAJE, no la lectura de punteros.** En c3-000-h1 (relevantes
  memo-000→001) el chase ancló en memo-023 y deambuló 023→015→007 hasta stall; en
  c3-001-h2 (relevantes 008→010→011) ancló en memo-045 y siguió 045→015→009→006.
  Nunca pisó una unidad relevante, así que la tesis "el puntero es visible en el
  texto" quedó SIN testear: con una sola semilla de retrieval, un error de anclaje
  pierde la trayectoria completa. react gana exactamente porque puede re-buscar con
  términos nuevos cuando la primera búsqueda no sirve — búsqueda gobernada por el
  modelo ES el mecanismo en este corpus.
- **Y el nicho no era el que creíamos**: react resuelve esas celdas con u=1.0 a
  ~10-14.5k tokens — MÁS BARATO que el chase (19-25k). En gpt-5-chat el acoplamiento
  profundo ya tiene solución barata. El problema abierto real es **c3 en nano**
  (ningún paradigma lo resuelve allí, grilla completa u=0.000).

**P14b CONFIRMADA — los frenos funcionan.** Anti-nicho: c2 paró en 1 hop (6.4k,
"done", u=0.167 parcial honesto); c5 paró exactamente en el cap (6 hops, 37k ≤
proyección 47k). Cero alucinaciones de puntero, respuestas "Unknown/Not contained"
en vez de invención. Y las réplicas del nicho son idénticas en path y ±0.1% en costo:
**el bucle en código elimina la lotería, como predicho** — eso transfiere como
resultado de mecanismo aunque el patrón muera.

Lección para el próximo intento (si lo hay): el eslabón débil es la SEMILLA única.
Un multi-anclaje (probar top-k anclas secuencialmente dentro del presupuesto) se
acerca peligrosamente a re-inventar react; la alternativa es mejorar el retriever
para tareas de cadena, no el paradigma. P14c (nano) no se corre: solo sobrevivientes.

## Veredicto P13a-c: estructura vs juicio en nano (2026-08-27, `_analyze_p13.py`)

98 celdas compartidas entre la grilla congelada gpt-5-chat y la grilla nano
(gold_v2 + gold_deep; infra_error excluido, cot excluido, infactibles aparte).

- **P13a CUMPLE (12/15), con UN matiz que es hallazgo**: rewoo y map_reduce
  sostienen TODAS sus celdas (Δu ≤ 0.25). Las 3 roturas son todas `direct`
  (Δu=1.00 en v2/c3-002-h3, v2/c5-000-w48, deep/c5-000-w4): leerlo todo en ventana
  NO alcanza cuando la síntesis exige juicio (contradicción C5, cadena h3). Matiz
  fino: direct-nano sostiene h1/h2 (u=1.0) y rompe en h3 — la profundidad de cadena
  degrada al modelo chico incluso con toda la evidencia enfrente. La frontera real
  no es solo "quién gobierna el flujo": hay celdas donde el juicio DE LECTURA es el
  cuello, y eso direct no lo estructural-iza.
- **P13b CUMPLE en los tres**: react 10/14 celdas con Δu ≥ 0.25, reflection 8/13,
  dag_strategy 7/13. Sorpresa direccional: en C2 nano MEJORA a chat (dag -0.25,
  react -0.21, y plan_execute -0.52/-0.56 — el modelo chico se autodestruye menos
  con la descomposición). Anotar para el paper: la degradación es por-región, no
  uniforme, y en cobertura independiente el barato empata o gana.
- **P13c CUMPLE justo**: 73/81 celdas con réplicas idénticas en utilidad (90.1%).
  8 celdas no-idénticas ⇒ el piso de ruido por celda sigue siendo OBLIGATORIO; el
  determinismo nano es casi-total, no total.

**Titular de producto**: la evidencia habilita a MAPO a rutear cobertura (C2/C4) a
nano con paradigmas estructurados (rewoo / map_reduce / dag×managed dio u≈1.0 en
nano-managed) a precio nano, y PROHÍBE el downgrade de modelo en C3/C5 profundas
(react/reflection solo rinden en chat; c3-deep en nano no lo resuelve NADIE — es la
región abierta). Esta es exactamente la clase de regla que el aprendizaje offline
debe proponer/puntuar/promover.

Dos artefactos del análisis, explicados:
- El "desacuerdo de factibilidad" en map_reduce (deep c2-000-w48 / c3-000-h1:
  factible en chat, infactible en nano) NO es bug del gate: las filas chat son
  históricas, anteriores al check de presupuesto de map_reduce (el episodio de 5.7×
  que motivó ese check). El gate actual las declararía infactibles igual que en nano.
- **Contaminación menor a registrar**: el índice de graph_traverse se memoiza en
  disco por digest de CORPUS, sin modelo en la clave (`cache/graph/`) — las filas
  nano (tok≈250) reusaron el grafo construido por gpt-5-chat. Irrelevante al
  veredicto (falsificado en ambos), pero si algún día un candidato con índice
  sobrevive, la clave del memo debe incluir el fingerprint del modelo.

## Estado de corridas al momento de esta nota
- Cola nano (`_run_nano_queue.py`, gpt-5.4-nano): corriendo, ~[79/96] de la fase A
  (grilla gold_v2). En c3-001-h2 (gold_v2) nano da u=0.000 en TODOS los paradigmas de
  ambas réplicas — consistente con P13b (react/reflection/dag degradan) pero OJO:
  también rewoo/gist_reader/map_reduce dan 0 ahí; mirar si es la celda (acoplada) o
  el modelo, contra la grilla chat, cuando termine.
- Candidatos gpt-5-chat: terminada (veredictos arriba).
