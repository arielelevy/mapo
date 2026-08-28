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

## 3. Code review — MEDIUM abiertos

Del bloque de `code-review-2026-08-27.md`. Los bloques CRÍTICO y HIGH están aplicados;
de los MEDIUM se aplicaron M2, M4, M5, M6, M7, M9, M12 y M19. **Verificar antes de
arreglar**: esta tabla se armó por grep y alguno puede haberse cerrado de rebote.

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
| T-6 | Vecinos de REC leídos completos | EnvProbe, Kintsugi, SHARP, Trace2Policy… antes de usar «primero» en el paper; reabrir el claim de consolidación del `GATE.md` |

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
