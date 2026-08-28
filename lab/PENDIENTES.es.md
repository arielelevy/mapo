# Pendientes — MAPO

> **Fuente única de "qué falta".** Recopilado el 2026-08-27 juntando el artefacto del
> plan de tesis, `DISENO.es.md` §5 y §8, `code-review-2026-08-27.md`, `ARQUITECTURA.es.md`,
> `CLAUDE.md` y lo que salió midiendo hoy. Lo que está acá no está hecho.
>
> **Cómo se usa**: cuando algo se cierra, se saca de acá y se registra dónde
> corresponda (`README.md` §Findings si es un hallazgo, el commit si es código). Un
> pendiente que se completa y se queda en esta lista es peor que no tenerla.

---

## 0. Lo que bloquea a todo lo demás

| # | Qué | Por qué manda | Costo |
|---|---|---|---|
| **B1** | **El veredicto de P16** | Corriendo, seed 61, con `_analyze_p16.py` congelado ANTES de la corrida. El barrido de λ dice si la ventaja sobrevive a cobrar el costo de escalar. Todo lo que toque `features.py` / `rules.py` / `policy.py` espera a que cierre | en curso |
| **B2** | **Aplicar el prerrequisito de detectores honestos** | Dos sitios: `features.py:214` (el segmento de región) y `rules.py:248` (la creencia `oracle_available`, que es la que la cascada lee). Hoy los dos derivan de `bool(task["oracle"])`, o sea del gold | minutos, apenas cierre B1 |
| **B3** | **Correr P17** | La primera medición honesta de selección. P17b (≥7 de 14 vuelven `specialise`), P17c (la brecha neta — el re-test de lo que P15a falló), P17d (26/26) | ~14M tokens |

**Riesgo de B3 ya registrado**: θ se ajusta sobre corpus cuyas regiones se computaron con
la regla vieja. Si P17b falla con margen 0 *por falta de episodios* y no por falta de
señal, hay que **reconstruir los corpus** bajo la regla honesta antes de poder medir
selección. Es un costo enunciado ahora, no descubierto después.

---

## 1. Mediciones pendientes

| # | Qué | Detalle | Costo |
|---|---|---|---|
| M-1 | Brazo en PROSA (E1) | Los dos brazos implementados y sin correr: el clasificador de producción tal cual y el router en prosa más fuerte construible. Espera a que P16 libere la cuota | ~26 llamadas |
| M-2 | Instrumentar retención de verdad | El recall de evidencia ya está medido y manda (ver §Findings). Falta el **segundo eslabón**: cuánta de la evidencia recuperada sobrevive hasta la llamada que responde. Eso sí necesita código y corrida | código + corrida |
| M-3 | Transferencia de θ entre familias de modelos | El colapso de `react` en nano sugiere que parte de lo aprendido es del modelo y no de la tarea. Condiciona la lectura de todo el registro | corrida |
| M-4 | Corpus natural + segunda familia | Validez externa real. Un segundo generador propio **reformula** la objeción, no la responde. QA numérica sobre documentos largos calza con los contratos | la fase cara |
| M-5 | C3 profundo en nano | Región abierta: la grilla completa dio u=0,000, y también oráculo-cero en `gold_transfer`. No hay ganador conocido | corrida |

---

## 2. Producto — deuda de la capa de decisión

| # | Qué | Por qué importa |
|---|---|---|
| P-1 | **Que la sonda sense recuperabilidad** | La sonda existe para convertir una variable invisible en observada, y hoy sensa *acoplamiento*. Medido: el recall de evidencia predice fuera de muestra al 60% desde el paradigma, y la región apenas al 3,8%. La variable que conviene sensar es **si la evidencia se va a encontrar** |
| P-2 | **Sacar el peso Hebbiano del camino activo como selector** | Demostrado, no medido: en el punto fijo `w* = 1,6p − 0,6`, monótona en la tasa de victorias, y `theta_assertions` ya ordena por esa tasa. Una transformación monótona **no puede** cambiar un argmax, así que como selector es redundante por construcción y ningún tuneo lo arregla |
| P-2b | **Reintroducirlo como detector de no estacionariedad** | El drift está medido: **4 de 5 regiones cambian de ganador (80%)**. Donde el peso y la tasa discrepan sobre el mejor brazo, la región está en transitorio, y la acción correcta es **bajar la confianza y abstenerse** — maquinaria que el producto ya tiene. Requiere antes arreglar la parametrización: el piso 0,01 aplasta todos los brazos débiles, salir de él cuesta ~5 victorias, y con ~6 updates por clave contra un horizonte de ~20 el estimador nunca sale del prior. Predicción falsable registrada ANTES de correr |
| P-2c | **Hebbiano sobre el ORDEN de llamada a tools** (idea del autor) | La dirección más prometedora, y por dos razones. Restaura lo que hace distintivo al aprendizaje Hebbiano — **asociación entre pares** — de modo que la prueba de monotonía no aplica: un peso de transición (tool_i → tool_j) no es una estadística marginal de un brazo. Y apunta al blanco correcto: un paradigma **es** mecánicamente una política sobre secuencias de tools, y elegir paradigma predice el 60% del recall de evidencia fuera de muestra, así que el orden es el canal por donde actúa la palanca dominante. **Bloqueado por instrumentación**: `tools.py:375` guarda `calls[name] += 1`, un conteo sin secuencia — el orden no se registra. Loguearlo es el primer paso barato |
| P-2d | **Asociaciones aprendidas como creencias** (idea del autor) | Se puede, con una restricción que no se negocia. El retículo es `ASSUMED < ELICITED < OBSERVED < COMPUTED` y las acciones irreversibles exigen `COMPUTED`/`OBSERVED` **justamente** para dejar afuera a la estadística y a la opinión. Una asociación aprendida es aritmética sobre un ledger, así que *parece* COMPUTED — y si entrara con ese rango, una regularidad estadística podría gatear una acción irreversible, que es exactamente lo que el piso existe para impedir. No es una observación sobre ESTE request: es un prior sobre requests parecidos. Necesita un rango estrictamente por debajo de OBSERVED, y **el retículo hoy no tiene ese casillero** |
| P-2e | **Componer el patrón en vez de elegirlo** (idea del autor) | La conclusión lógica de P-2c, y la más grande. Si las asociaciones de orden se aprenden, el paradigma deja de ser una entrada de catálogo y pasa a **sintetizarse por request**: el catálogo se vuelve un *prior*, no el espacio de acción. Encaja con lo que E2 ya midió — «donde la cascada dispara, la elección no produce el valor: la estructura de la acción lo produce». **Y abre dos tensiones que hay que resolver antes, no después**: (1) el banco mide paradigmas que son funciones async planas, y un patrón sintetizado no está en el catálogo, así que la comparación contra brazos fijos deja de estar definida — hace falta una respuesta de diseño, no una mano; (2) A2 y A3 restringen los patrones admisibles al catálogo (A2 con profundidad ≤ 3, A3 a un subconjunto certificado), así que un patrón sintetizado **no puede correr bajo A2+** sin una historia de certificación. Los dos son problemas de diseño reales, y son la razón por la que esto va después de P-2c y no antes |
| P-3 | Calibración por proposición al router activo | Hoy se persiste pero los routers se crean sin leerla |
| P-4 | Horizonte con evidencia propia | `coupling` y `horizon_unknown` comparten credencia en algunos caminos — y el horizonte es el eje que P15 señaló |
| P-5 | Las particiones descubiertas no gobiernan el router | Se persisten en `store.py` y nadie las consulta |
| P-6 | Particiones que usan truth de evaluación | Algunas usan variables posteriores a la ejecución: fuga |
| P-7 | El producto no cierra el bucle | No persiste de manera completa resultados y creencias, así que el aprendizaje no se realimenta de producción |
| P-8 | Promoción sin incertidumbre | Usa puntos estimados, sin intervalo ni certificado autenticado |
| P-9 | Repetir consolidación reaplica historia | Ya absorbida por el incumbente: el replay no es idempotente |
| P-10 | Flags declarativos del dial A0–A3 | `theta_may_learn_online` y el sellado de A3 están declarados y no impuestos |
| P-11 | **Separar producto de banco en `lab/app/`** | Hoy conviven. La regla que evita que se vuelvan a mezclar: **el banco importa al producto; el producto jamás sabe que el banco existe**. Concreto: `serve.py` todavía importa `grading` |

---

## 2b. Las decisiones dinámicas que hoy no gobierna nadie

**La inconsistencia, verificada en el código y no supuesta.** El invariante del producto
dice: *«El LLM es sensor: emite proposiciones; JAMÁS maneja flujo de control ni decide
gates.»* Eso se cumple **entre** paradigmas — la capa de decisión elige cuál corre. No se
cumple **adentro** de ninguno: ahí el modelo maneja el flujo de control, que es
exactamente lo que el invariante prohíbe.

Y el repo ya lo sabía a medias: `paradigms/dag.py:16-21` llama al problema por su nombre
—*«una topología con una docena de umbrales es una topología cuyo comportamiento se fija a
mano en vez de derivarse»*— y lo registra en el catálogo como **Constant Soup**. Nunca se
actuó sobre eso.

| # | La decisión | Quién la toma hoy | Qué habilitaría gobernarla |
|---|---|---|---|
| **D-1** | **Cuándo parar de iterar** | Un tope constante en código (`max_iterations=20` para react, `4` para plan-execute, `paradigms/__init__.py:211,282`) **o el modelo**, que corta emitiendo una respuesta sin `tool_calls`. Las dos son flujo de control decidido fuera de la capa de decisión | **El mejor candidato de todos, y el más barato.** Es la decisión atada *directo* al costo, y las señales contables para gobernarla **ya existen y ya se registran**: `stall_warnings` (el recuperador se secó), `coverage`, `relevant_units_read`. El loop de `paradigms/__init__.py:81` **no consulta ninguna**. Son deterministas y contables ⇒ entran como creencias `COMPUTED` sin violar nada |
| **D-2** | **Qué herramienta sigue** | El modelo, en cada vuelta | Es P-2c: asociación (tool_i → tool_j). Bloqueado por la misma instrumentación — `tools.py:375` guarda un conteo sin secuencia |
| **D-3** | **La descomposición en DAG** | El modelo: produce `sub_questions` con sus dependencias declaradas, y `_assign_waves` sólo topologiza lo que el modelo dijo (`dag.py:186`). O sea, **el modelo dibuja el grafo de control** | Gobernar la forma —cuántos nodos, qué profundidad de replan— con creencias sobre el request en vez de con la propuesta del modelo. Es la versión estructural de D-1 |
| **D-4** | **La partición de `map_reduce`** | Fija por construcción | **Challenger multi-agente (idea del autor)**: agentes con alcance propio y handoffs con contrato, en vez de una partición fija y un fold. Los handoffs (agente_i → agente_j) son exactamente las asociaciones que P-2c aprende, y el contrato del handoff es exactamente dónde viven las creencias tipadas. **Encaja con el alcance declarado del producto** — `CLAUDE.md` ya lista «acciones … handoffs con contrato» como una de las cuatro superficies. Califica como patrón legítimo y no como prompting, porque la diferencia es **estructural**: alcances independientes y transferencia explícita. Entra al catálogo como candidato **con predicción falsable registrada antes de correr**, como todos |
| **D-5** | **La «Constant Soup» en general** | Una docena de umbrales a mano en `dag.py` | Derivarlos, que es lo que el propio módulo dice que habría que hacer. D-1 y D-3 son los dos primeros |

### Cómo implementan el handoff los frameworks, y por qué eso ES la oportunidad

Consultado en fuentes el 2026-08-27, porque el patrón no está en nuestro catálogo y
convenía ver cómo lo resuelve el resto antes de diseñarlo.

| Framework | Cómo transfiere el control |
|---|---|
| **Microsoft Agent Framework** | `HandoffAgentExecutor` **inyecta herramientas de handoff** en cada agente según las reglas configuradas, y el agente invoca una para transferir. Topología de malla, agentes conectados **sin orquestador**: cada agente decide cuándo transferir |
| **OpenAI Agents SDK** | El handoff *es* una herramienta: se genera `transfer_to_<agent_name>` y el modelo la llama. Aparece en la traza como cualquier otra acción |
| **Google ADK** | «LLM-driven delegation»: el LLM lee las `description` de los sub-agentes y **genera `transfer_to_agent()`** |

**Los tres hacen lo mismo: el modelo emite una llamada a herramienta y eso transfiere el
control.** O sea, el handoff estándar de la industria es exactamente el anti-patrón que
§2b acaba de catalogar — flujo de control decidido por el modelo.

**Y ahí está la oportunidad, que es la tesis del producto aplicada a una superficie
nueva.** La versión MAPO conserva la ESTRUCTURA —alcances independientes, transferencia de
propiedad, contexto que viaja completo— y cambia **quién decide la transferencia**: no una
herramienta que el modelo llama, sino una **regla determinista sobre la base de creencias**,
con piso de procedencia. El modelo puede *proponer* el handoff como proposición tipada; la
transferencia la autoriza la regla. Eso es exactamente lo que `CLAUDE.md` ya llama
«handoffs con contrato», y es una diferencia medible y no retórica:

- **Reproducible**: misma base de creencias ⟹ mismo handoff. Con `transfer_to_agent()` la
  transferencia hereda toda la varianza del modelo.
- **Gateable**: un handoff hacia un agente con capacidad irreversible puede exigir
  `COMPUTED`/`OBSERVED`, cosa que una llamada a herramienta no puede exigirse a sí misma.
- **Auditable**: el handoff entra al EXPLAIN como cualquier otra decisión.

**Vecino de literatura a leer antes de afirmar novedad** (aparecido en la misma búsqueda,
NO leído todavía): *«The Provenance Paradox in Multi-Agent LLM Routing: Delegation
Contracts and Attested Identity»*, arXiv 2603.18043. Por el título toca las tres cosas a
la vez — procedencia, contratos de delegación y ruteo — así que entra a T-6 con prioridad
alta: si ya dice esto, la novedad hay que reformularla.

**Por qué esta familia importa ahora y no antes.** Está medido que elegir paradigma
predice el **60%** de la varianza del recall de evidencia fuera de muestra, y que el recall
es la variable dominante del resultado. Pero un paradigma es, mecánicamente, una política
sobre estas decisiones. Así que la capa de decisión está gobernando la palanca **por su
nombre** —«corré `dag_strategy`»— y no por su contenido. El 40% de varianza que el nombre
del paradigma no explica vive acá adentro.

**Y no se fijan a mano ni se aprenden una vez: se aprenden EN PRODUCCIÓN, por dominio**
(decisión del autor, 2026-08-27). Cuándo parar, cuántos nodos, qué orden de herramientas
— todo eso depende del dominio, del corpus y de cómo está armado el sistema. Un umbral
ajustado sobre un corpus sintético y horneado en el código es la Constant Soup otra vez,
sólo que con un número mejor elegido.

Eso NO significa aprender adentro de un request, que el invariante prohíbe. Significa
**aprender offline del tráfico de esa instalación**, con copy-on-write y guarda de
promoción, y transportar el resultado en el bundle firmado. **Esa maquinaria ya existe y
ya está probada**: §6.2 hace exactamente esto para el piso de garantía — estadísticas de
rechazo tipado por región → piso aprendido → guarda de replicación → bundle firmado. La
generalización es una sola frase: **toda constante que dependa del dominio debería ser una
cantidad aprendida por región, transportada en el bundle y protegida por la guarda**, con
la misma forma que los pisos ya validados.

**Orden sugerido, por costo creciente**: D-1 (las señales ya existen, sólo hay que
consultarlas) → instrumentar la secuencia de tools (D-2/P-2c) → D-4 como candidato nuevo
→ D-3 → P-2e (componer el patrón), que es el techo y arrastra las dos tensiones de A2/A3
y del banco.

---

## 3. Code review — MEDIUM abiertos

Del bloque de `code-review-2026-08-27.md`. Los bloques CRÍTICO y HIGH están aplicados;
de los MEDIUM se aplicaron M2, M4, M5, M6, M7, M9, M12, M19 y —el 2026-08-27— **M3, M11,
M17 y M18**. **Verificar antes de arreglar**: esta tabla se armó por grep y alguno puede
haberse cerrado de rebote.

**Los que quedan esperan a que P16 cierre, y por una razón concreta**: `_analyze_p16.py`
llama a `router.plan`, que pasa por factibilidad y por reglas. **M10** (el `GIST_CHARS`
inflado) y **M8** (la constante de supresión de sonda) cambiarían qué paradigmas se podan
y qué regla dispara, así que moverlos ahora reescribiría el veredicto congelado por debajo.
Van en el mismo turno que B2. **M1, M13, M14 y M16** tocan la ejecución de los paradigmas
o la consolidación: con una corrida a mitad de camino, una fila que hoy crashea pasaría a
degradar y el dato dejaría de ser homogéneo. También esperan.

| # | Dónde | Qué |
|---|---|---|
| M1 | `tools.py:399-440`, `paradigms/__init__.py:101` vs `modern.py:82` | Args del modelo lanzan `KeyError`/`ValueError` crudos en vez de `ToolFailure`: recuperable en un paradigma y fatal en otros |
| M3 | `llm.py:107-110` | `throttled_seconds`: `+=` fuera del lock y doble conteo cuando `wait > 30` |
| M8 | `rules.py:265` | Sonda suprimida por una observación de credencia 0,3 que tampoco especializa (drift 0,0 vs 0,7): hace falta la constante compartida |
| M10 | `feasibility.py:38` vs `tools.py:41` | `GIST_CHARS=400` contra un gist real de ~215 (`SUMMARY_CHARS=180`): proyección 2× ⇒ sobre-rechazo por factibilidad |
| M11 | `beliefs.py:527+` | ECE con punto medio del bin: error sistemático ~0,1, que es exactamente el umbral de confianza |
| M13 | `paradigms/dag.py:350`, `modern.py:73,127` | Accesos fuera del `try`: un replan malformado crashea la tarea en vez de degradar como ya hacen sus propios caminos |
| M14 | `modern.py` ×9 + `dag.py:217` | Extractor JSON copiado nueve veces con tuplas de excepciones divergentes: falta `extract_json()` compartido |
| M15 | `store.py:245-261` vs `consolidation.py:333-348` | Loop de calibración duplicado y **ya divergido** (`contradictions` sólo está en uno) |
| M16 | `consolidation.py:191-192` | `float(r[attribute])` en los *splits* sin el filtro de `None` que sí tienen los *values*: crashea sobre filas legacy |
| M17 | `runner.py` / `main.py` | Verificar que ningún default reintroduzca `cot`, que por decisión no se corre nunca más |
| M18 | `main.py:78-92` | Dos `POST /run` concurrentes duplican celdas y pesan doble en `study()`: falta lockfile por `results_path` |
| — | entorno | `pip-audit` nunca se corrió (no está instalado) |

---

## 4. Teoría — pizarra, y bloquea a F6

| # | Qué | Por qué |
|---|---|---|
| T-1 | Semántica formal del contrato | Una página por clase de contrato: qué proposición exacta garantiza cada una. **Sin esto, F6 mide algo indefinido** |
| T-2 | Red-team de mis-binding | Buscar nuestro propio contraejemplo antes de que lo encuentre un revisor: referentes, alcance de agregación, negaciones en la prosa conectiva |
| T-3 | Teorema de soundness del ensamblador | La salida está *implicada* por la base de creencias; el LLM propone plantilla, el código instancia y verifica el binding |
| T-4 | Cota nativa del ratchet | Pérdida de cobertura por endurecimiento y tasa de falsos endurecimientos bajo la guarda split-half. **Reemplaza el préstamo del Teorema 10.1**, que acota algo que un ratchet no puede hacer |
| T-5 | Quién fija el dial | Definirlo, y cómo se evalúa marginalizando sobre sus posiciones |
| T-6 | Vecinos leídos completos | EnvProbe, Kintsugi, SHARP, Trace2Policy… antes de usar «primero» en el paper; reabrir el claim de consolidación del `GATE.md`. **Prioridad alta, agregado 2026-08-27**: arXiv 2603.18043, *The Provenance Paradox in Multi-Agent LLM Routing: Delegation Contracts and Attested Identity* — por el título toca procedencia + contratos de delegación + ruteo a la vez, que es nuestra conjunción. NO leído |

---

## 5. Paper

| # | Qué |
|---|---|
| W-1 | **Re-encuadrar §5.1 (teorema de selección) vs §5.2 (dominancia de cascada)**. E2 muestra que la dominancia hace el trabajo que se le acredita al teorema; ahora además con el AURC degenerado (0,000 contra un techo de +0,400) sobre la mesa |
| W-2 | Toda edición va a **los dos** archivos: `paper-en.md` (canónico) y `paper-es.md` (espejo) |
| W-3 | Integrar el hallazgo de nano (P13) — «la estructura rescata al modelo barato, los loops abiertos no» — que es el resultado más publicable y está huérfano de tesis |
| W-4 | Endorser de arXiv, o publicar en **Zenodo con DOI**. §14 del `PLAN.md` es histórico |

---

## 6. Plataforma — `ARQUITECTURA.es.md`, nada implementado

Es una **propuesta** entera. Piezas, en el orden en que se vuelven necesarias:

- Docling como extractor primario con procedencia página+bbox, y `pypdfium2` (no PyMuPDF, que es AGPL) como sensor barato que decide OCR antes de la primera pasada.
- Postgres como ledger epistémico, con un esquema que haga **estructuralmente imposibles** las deudas §5.2 y §5.8 de `DISENO.es.md`.
- Weaviate con hybrid y una colección por versión de índice; `live_pointer` en Postgres como único flip atómico de promoción.
- Work table en Postgres ahora; DBOS después. **Temporal sólo si dispara uno de los gatillos escritos** en su §2.1. LangGraph descartado, no pospuesto.
- FastAPI con SSE resumible y eventos tipados, donde **A3 buffea la respuesta hasta verificar citas**.
- On-prem / Docker, single-tenant.

**Invariante que no se negocia**: la capa de decisión **nunca** depende de un orquestador,
y los paradigmas siguen siendo funciones async planas — para que el banco mida exactamente
lo que producción ejecuta.

---

## 7. Fases del plan de tesis, con estado

| Fase | Qué | Estado |
|---|---|---|
| F0 | P15 cerrada y registrada | **hecho** — refutada, mecanismo verificado, veredicto reproducible |
| F1 | Sensar y re-decidir | **en curso** — las tres pre-empciones diagnosticadas, la selección disparó, P16 corriendo, P17 registrada |
| F2 | Los tres routers rivales | **parcial** — brazos prosa implementados, E2 (ridge) corrido; falta correr E1 |
| F3 | Retención de contexto y mediación | **parcial** — el recall medido y predictivo fuera de muestra; falta instrumentar retención propiamente dicha (M-2) |
| F4 | Estadística que resista al tribunal | **hecho** — bootstrap pareado, Benjamini-Hochberg, AURC. Falta escribir el alcance: la reproducibilidad de EXPLAIN es *aguas abajo del sensor* |
| F5 | Teoría nativa | **pizarra** — T-1 a T-5 |
| F6 | Contratos contra los baselines directos | **no empezado** — bloqueado por T-1 |
| F7 | Validez externa de verdad | **no empezado** — M-3 y M-4 |

---

## 8. Reglas que aplican a todo lo de arriba

- **Ejecutado primero, teorizado después.** Nada entra al paper sin implementación que lo
  corra. Si está en el paper como «declarado, no medido», es deuda: implementarlo o sacarlo.
- **Nada se afirma sin medida, cita o rótulo de hipótesis** (G3). Las novedades se enuncian
  como CONJUNCIÓN, nunca como partes (`GATE.md` §8quater).
- **Antes de gastar un token**: `test_science` + `test_consolidation` en verde, `corpus/verify.py`,
  predicciones falsables registradas con fecha, `repeat ≥ 3`, piso de ruido POR CELDA,
  decisiones sobre la brecha **neta**.
- **Ninguna referencia a marcas o productos anteriores**, en documentos ni en código.
- **Nunca hacer push sin confirmación del autor.**
