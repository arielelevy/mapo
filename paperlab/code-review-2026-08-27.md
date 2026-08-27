# Code Review Report — paperlab

**Proyecto**: paperlab (MAPO — capa de decisión determinística para agentes LLM)
**Fecha**: 2026-08-27
**Alcance**: Full Review (estática + arquitectura + concurrencia + corpus/tests + scripts + deps + secretos)
**Revisado**: `app/` completo (19 módulos), `corpus/generate.py` + `verify.py`, `tests/` (2 suites), 21 scripts `_*.py`, `requirements.txt`, higiene git. 5 auditores paralelos + verificación manual de todos los CRITICAL/HIGH (los marcados ✓ fueron confirmados línea por línea por el revisor principal; el resto viene con evidencia citada del auditor).
**Calibración**: las invariantes del proyecto (sin defaults de config, LLM-como-sensor, plan malformado = fallo real, comentarios ensayo) NO se reportan como defectos.

## Resumen ejecutivo

| Severidad | Cantidad | Acción |
|---|---|---|
| CRITICAL | 6 | Corregir antes de la próxima corrida/análisis |
| HIGH | 12 | Corregir antes de cerrar E0 |
| MEDIUM | 20 | Planificar (varios son de una línea) |
| LOW / INFO | 22 | Oportunidad |

**Lectura transversal**: (1) hay UNA clase de bug repetida en cuatro capas — *escrituras no atómicas sin manejo de corrupción* (cache LLM, cache embeddings, grafo memoizado, store de políticas/beliefs) — un solo patrón (tmp + `os.replace` + try en lectura) cierra los cuatro; (2) la invariante "infra_error se excluye de toda estadística" está aplicada en `study()` pero NO en `episodes()`/`replicates()`/`consolidate()`; (3) dos hallazgos tocan directamente los números del paper (grading A1, cascade A3); (4) secretos/git: **limpio**; corpus: **sintético verificado**.

---

## CRITICAL

### C1 ✓ — `infra_error` contamina aprendizaje, piso de ruido y consolidación
`app\runner.py:531-534` (`replicates`), `:543-558` (`episodes`), `:687` (`consolidate`)
Solo `study()` filtra `infra_error` (runner.py:489). `episodes()` alimenta theta (report/consolidate/promote), `replicates()` alimenta el piso de ruido de `credible_oracle_gap`, y `consolidate()` pasa filas sin filtrar a `discover_partitions`. Una tanda con 429s agotados enseña a theta que el paradigma "falla" en esa región y infla el piso de ruido con ceros que no son mediciones. Viola la invariante nuclear del proyecto, en silencio.
**Fix**: filtrar en `load_rows()` con `include_infra=False` por defecto.

### C2 ✓ — `report()` instala una theta SIN guarda anti-regresión y pisa el historial versionado
`app\runner.py:576-580` + `app\main.py:49-56` + `app\store.py:362`
Cada `report()` hace cold(v0)→candidate(v1)→`save(policy_dir)`: siempre escribe `theta_v0001.json`, sobreescribiendo un bundle "immutable, versioned, signed", y `_current_bundle()` toma el glob más alto como política viva. Un `GET /report` (lectura) instala política de producción que jamás pasó por `promote()`.
**Fix**: guardar la theta de `report()` en `policies/fitted/` (fuera del glob de producción) o pasarla por `promote()` antes de `save()`.

### C3 ✓ — Cache no atómico + lectura sin manejo de corrupción: envenenamiento permanente y silencioso
`app\llm.py:305-314`, `app\embeddings.py:59-63,85-88`, `app\paradigms\modern.py:198-201,243` (`_entity_graph`), `app\store.py` (head/calibration/propositions/dreams/theta)
`write_text` directo al path final: un crash/Ctrl+C (o dos workers en carrera — el `LLMClient` es uno compartido, runner.py:301) deja JSON truncado. Desde ahí, toda corrida (resume y sealed incluidos) revienta en `json.loads`, cae en el `except Exception` del runner (:435) y se registra como fila de utilidad 0 **no-infra**: el cache que "hace la segunda pasada gratis" se vuelve una fuente permanente de datos corruptos. En store.py además: append+head no transaccional (crash entre ambos ⇒ `verify_chain` reporta truncamiento falso) y dos requests FastAPI concurrentes bifurcan la cadena de beliefs sin lock; `next_cycle` = `len(glob)+1` puede SOBREESCRIBIR un dream si hay huecos.
**Fix**: patrón único — escribir a `.tmp` + `os.replace()`; en lecturas de cache, atrapar `JSONDecodeError`, borrar la entrada y tratar como miss; lock alrededor de append+head; `next_cycle` = max índice + 1.

### C4 ✓ — Grading: crédito por substring bidireccional regala 1.0 a respuestas incompletas
`app\grading.py:83` — `return 1.0 if only in candidate or candidate in only else 0.0`
`candidate in only` es la dirección inversa a la que justifica el comentario: oracle `["42"]`, respuesta `"4"` → 1.0; oracle `["AR1234"]`, respuesta `"AR123"` → 1.0. Todo prefijo/fragmento puntúa perfecto en singletons — infla exactamente la métrica con la que se deciden brechas de pocos puntos.
**Fix**: eliminar `candidate in only`; opcionalmente exigir límites de palabra para `only in candidate`.
**Impacto**: re-puntuar los JSONL existentes tras el fix (re-grading es barato: no re-corre el LLM).

### C5 — El verificador NO re-deriva el vínculo persona↔cuenta en C7: tareas irresolubles pasan PASS
`corpus\verify.py:273-291` + `corpus\generate.py:552-564`
`_c7` solo comprueba que haya UN trigger de escalación entre las unidades; nunca parsea `Settlement account … was flagged` ni verifica que la cuenta sea la de la persona preguntada, ni que el memo nombre→cuenta esté en `unit_ids`. Con `--per-cell > 8` el memo del holder queda afuera y la tarea es incontestable, con oracle `escalate` y verify en PASS. Es exactamente la clase de bug (oráculo mal por construcción, silencioso) que motivó el verificador.
**Fix**: parsear la cuenta del alert y exigir `holder_of[cuenta] == persona` + memo del holder ∈ `unit_ids`.

### C6 ✓ — Filtros por substring en map_reduce y reflection: falla del harness medida como falla del paradigma
`app\paradigms\__init__.py:234` (`if "NOTHING" not in completion.text.upper()`) y `:325` (`if "NO DEFECTS" in critique.text.upper()`)
Una extracción que diga "says nothing about X, but names Y as director" se descarta antes del reduce; una crítica "there are no defects of scope, but two omissions" se toma como aprobación y saltea la revisión. Confound directo: el estudio mide estructura de control, no accidentes de fraseo.
**Fix**: igualdad estricta (`text.strip().upper() != "NOTHING"`; exigir exactamente `NO DEFECTS`).
**Impacto**: puede haber sesgado celdas históricas de map_reduce/reflection — anotar en el registro.

---

## HIGH

### H1 ✓ — Sealed-miss de embeddings no aborta la replay sellada
`app\embeddings.py:65-69`: lanza `RuntimeError` pelado; el runner re-lanza solo `SealedCacheMiss` (:431-434) y lo demás lo registra como fila de utilidad 0 → la replay sellada continúa "en vivo parcial". **Fix**: lanzar `SealedCacheMiss` (1 línea).

### H2 ✓ — La superficie `cognitive` anuncia `coverage` pero `dispatch` lo rechaza; y nunca recibe stall warnings
`app\tools.py:189-194` (specs acumulativos) vs `:372-375` (`if self.variant != "accounting": raise ValueError`) y `:295` (misma comparación en `_note_search`). El modelo ve la tool, la llama, y el `ValueError` (no `ToolFailure`) zerea la celda. **Fix**: `if self.variant not in ("accounting", "cognitive")` en ambos puntos.

### H3 ✓ — El flag `regulated` es un check muerto: el floor CERTIFIED jamás se aplica
`app\assurance.py:196` lee `base.value("regulated")` pero `sense()` (`app\rules.py:190-306`) nunca lo asserta. Un request con `regulated: True` corre EXPLORATORY. Falla silenciosa de gobernanza. **Fix**: assertarlo en `sense()` con provenance COMPUTED.

### H4 ✓ — `cascade_value` es irreproducible entre procesos y acredita el escalón equivocado
`app\metrics.py:359`: `hash((task, depth))` usa salt por proceso (PYTHONHASHSEED no está fijado) — el número del paper cambia entre ejecuciones con `sensitivity < 1`. Además `:350,361`: al fallar sin detección se acredita `max(achieved, …)` en vez de la utilidad del escalón donde paró — sobreestima a favor de la tesis. **Fix**: sha256 para el draw; llevar la utilidad del escalón actual al `break`.

### H5 — La guarda anti-regresión compara incumbente y candidato sobre poblaciones distintas
`app\router.py:319-320`: `value_on` saltea tareas sin episodio del paradigma elegido — `counted` difiere entre bundles y el guard queda sesgado pro-candidato. **Fix**: puntuar esas tareas con el fallback observado (o 0.0) para igualar el denominador.

### H6 — La valuación offline pierde el coupling: `promote()` valida un router que no es el de producción
`app\router.py:342`: `_region_coupling` no lo lee nadie; `value_on` llama `plan()` sin coupling → toda región tight cae en `probe_before_deciding_on_bulk` → cheapest siempre. **Fix**: mapear coupling de la región a `plan(...)`; borrar la clave muerta.

### H7 — Con <6 tareas la guarda de promoción evalúa sobre el training set (guarda vacua)
`app\consolidation.py:486-489`: `final_ids` vacío → fallback al universo completo → candidato casi siempre "no regresa". **Fix**: saltear la promoción explícitamente con nota, como ya hace la abstracción.

### H8 — A0 EXPLORATORY endurece el floor en vez de relajarlo
`app\router.py:192-195`: `trust_elicited = (derived_floor is ELICITED)` → con A0 (`ASSUMED`) da False → floor OBSERVED, más estricto que A1/A2. Un booleano no representa 4 provenances. **Fix**: `BeliefPolicy` debe llevar `derived_floor` directamente.

### H9 — `compact_history` borra texto de unidades NO noteadas que comparten mensaje con una noteada
`app\cognitive.py:268-277`: un read batcheado con 1 unidad noteada reemplaza el mensaje ENTERO — las otras N-1 desaparecen sin nota ni stub que las mencione, contra su propio docstring. **Fix**: compactar solo si todas están noteadas, o reconstruir conservando las no noteadas.

### H10 ✓ — `REPORTS` en verify.py no acepta el discriminador numérico de nombres
`corpus\verify.py:106` vs `:38`: `_NAME` fue parcheado a `(?: \d+)?` tras el incidente de 400 personas; `REPORTS` quedó con el patrón viejo — el verificador rechaza corpus válidos justo en el régimen >396 personas para el que se parcheó. **Fix**: `rf"Reports to (?P<supervisor>{_NAME}) for all authorisations\."`.

### H11 — Re-ejecutar `_wire_feasibility.py` escribe un `dag.py` con SyntaxError (reproducido en sandbox)
`_wire_feasibility.py:21-33`: sus anclas siguen matcheando el archivo ya parcheado; el `replace` produce un `dag.py` roto que SE ESCRIBE antes de que el script aborte por el ancla de runner.py. **Fix**: guardia "ya aplicado" al inicio (1 línea); ídem preventivo en los otros patch-scripts (`_throttle.py` y `_unify_retry.py` se salvan hoy por accidente de orden de anclas).

### H12 — Filas de excepción registran `cost_tokens=0` aunque los tokens se gastaron
`app\runner.py:442-463`: un dag que crasheó tras plan+waves+verify pierde decenas de miles de tokens de la contabilidad — theta aprende que "falla barato". **Fix**: acumular usage en la surface o adjuntarlo a la excepción, y registrarlo en la fila de error.

---

## MEDIUM

| # | Dónde | Qué | Fix |
|---|---|---|---|
| M1 | `app\tools.py:399-440` + `paradigms\__init__.py:101` vs `modern.py:82` | Args del modelo (`search` sin query, `limit` no numérico) lanzan `KeyError`/`ValueError` crudos, no `ToolFailure`; recuperable en un paradigma y fatal en otros | Validar args al inicio de `dispatch` → `ToolFailure`; quitar el catch ampliado de modern.py:82 |
| M2 | `app\config.py:60-84` | `Settings` expone `api_key`/`embedding_api_key` en el `__repr__` autogenerado | `field(repr=False)` en ambos |
| M3 | `app\llm.py:107-110` | `throttled_seconds`: `+=` fuera del lock + doble conteo cuando `wait>30` | acumular `slept` bajo lock |
| M4 | `app\config.py:111-115`, `embeddings.py:45-47` | Ni fingerprint ni clave de embeddings incluyen el endpoint: mismo deployment en otra cuenta ⇒ colisión de cache | incluir host en ambos (invalida cache una vez — hacerlo ya) |
| M5 | `app\metrics.py:541` | `if noise else None`: con piso de ruido 0.0 (nano determinístico) la brecha se reporta "no evaluable" | `if noise is not None` |
| M6 | `app\beliefs.py:135` | Empate provenance+credence: la creencia VIEJA gana sobre la re-medición | desempatar por recencia |
| M7 | `app\rules.py:282` | `coupling_credence or 0.5` fabrica credence de la nada (latente) | assertar solo si `> 0.0` |
| M8 | `app\rules.py:265` | Probe suprimido por observación de credence 0.3 que tampoco especializa (drift 0.0 vs 0.7) | constante compartida 0.7 |
| M9 | `app\grading.py:66` | Oracle vacío: `";;;"` normaliza a set vacío → 1.0 | exigir contenido normalizado |
| M10 | `app\feasibility.py:37` vs `tools.py:41` | `GIST_CHARS=400` vs gist real ~215: proyección 2× ⇒ sobre-rechazo | derivar de `SUMMARY_CHARS` |
| M11 | `app\beliefs.py:412` | ECE con punto medio del bin: error sistemático ~0.1 == el umbral de confianza | usar media de credence por bin |
| M12 | `app\feasibility.py:274-278` | Catch-all: paradigma desconocido/typo pasa como feasible | whitelist + raise |
| M13 | `app\paradigms\dag.py:350`, `modern.py:73,127` | Accesos fuera del try: replan/steps/decision malformados crashean la tarea en vez de degradar como sus propios caminos ya hacen | validar forma antes de usar |
| M14 | `modern.py` ×9 + `dag.py:217` | Extractor JSON `raw[raw.index("{"):raw.rindex("}")+1]` copiado 9 veces con tuplas de excepciones divergentes | helper `extract_json()` compartido |
| M15 | `store.py:245-261` vs `consolidation.py:333-348` | Loop de calibración duplicado, ya divergió (`contradictions`) | extraer a `beliefs.py` |
| M16 | `app\consolidation.py:190-204` | `float(r[attribute])` crashea sobre filas legacy sin el atributo (values filtra None; splits no) | filtrar también en los splits |
| M17 | `app\runner.py:229` + `main.py:80-86` | Default de `run_cross_product` incluye `cot` — contra la decisión "no se corre nunca más" | `RETIRED = {"cot"}` en app/ |
| M18 | `app\main.py:78-92` | Dos `POST /run` concurrentes duplican celdas (doble peso en `study()`) | lockfile por results_path |
| M19 | `requirements.txt` | Pins que nunca corrieron (`httpx 0.30.0` pineado > 0.28.1 instalado; scipy declarada, no importada NI instalada; py real: 3.14.3 global sin venv) | regenerar de `pip freeze`, borrar scipy, anotar intérprete |
| M20 | `corpus\generate.py:630-632` | `inflate_units` corre ANTES de `build_tasks`: los `amend-*`/`alert-*` quedan sin inflar — la unidad-respuesta es el outlier corto del corpus (atajo estructural) | generar tareas primero, o padear al crearlos |

## LOW / INFO (selección — detalle completo en los apéndices de auditoría)

- `llm.py:36` `MAX_ATTEMPTS` muerto + 3 imports huérfanos en embeddings.py; `runner.py:42-86` `_RetiredTaskCorpus` muerto con NameError latente; `dag.py:71` `tool_calls` campo muerto; `feasibility.py:94` `FEASIBLE` sin uso; rama infeasible inalcanzable de dag (165 < 200).
- `llm.py:208-227` presupuesto de retry con `spent` obsoleto (excluye el request en curso); `tools.py:442` `batched_reads` cuenta reads rechazados; `retrieval.py:374` reranker puede duplicar unit_ids y su fallback es invisible en `describe()`.
- `modern.py:448` `CARRY_MAX_CHARS` trunca a JSON inválido (carry congelado, silencioso); `modern.py:133-153` gist_reader reporta ids alucinados como "omitted for budget" y no los suma a `hallucinated_units`; `cognitive.py:263,321` ni compact ni manage reconocen el payload de `read_all` (clave `units`).
- `modern.py:502` hop cap duplicado sin importar `POINTER_HOP_CAP` + comentario de feasibility dice "allowance" donde el código usa budget; `router.py:101` comentario promete supersesión por `mean_cost` no implementada; `features.py:159` vs `rules.py:208` claves de payload distintas (`units` vs `unit_ids`) con fallback silencioso a `n_units=1`; `features.py:207` `bool("false") == True`; `metrics.py:303` coverage 1.0 inalcanzable.
- Corpus/tests: guarda near-miss con 5 strings hardcodeados (sin backstop sobre las `note-*` reales); `relevant_units`/`truth_n_units`/`truth_coupling` jamás re-derivados; camino de ACEPTACIÓN de `promote()` no assertado en ninguna suite (checks tautológicos `isinstance(bool)`); confabulation guard con una sola semilla; `planted_index` con período `width` duplica tareas C5 si `per_cell > width`; validación `people vs width` corre después del IndexError; oracle C2 puede ser `[]`; unicidad de cuentas AR no asegurada; test_science muta el `THROTTLE` global; numeración de secciones salta 9→14.
- Scripts: `_run_*` históricos re-ejecutables correrían `cot` (gasto contra decisión registrada); `_run_queue.py` backup `.bak` destructivo + sleep 90min hardcodeado; dos definiciones distintas de "fila envenenada" (flag vs regex); bloque nano duplicado en 2 scripts (candidato a `Settings.nano_from_env()`); `_warm.py` accede al privado `_memo`; docstring de `_run_nano_smoke.py` afirma algo hoy falso (el override nano NO alcanza a embeddings).
- INFO: `.env.example`/CLAUDE.md exponen nombres de recursos Azure reales (sin credenciales; genericizar si el repo se hace público); declarar "synthetic data" en los `manifest.json`.

## Salud por capa

| Capa | Estado | Nota |
|---|---|---|
| Infra (llm/tools/config/embeddings/retrieval) | ⚠ | Sólida en diseño; el cluster de atomicidad (C3) y H1/H2 son los riesgos reales |
| Decisión (feasibility/router/rules/policy/assurance/beliefs) | ⚠ | Aritmética entre capas mayormente consistente; H3/H5-H8 tocan la garantía y la promoción |
| Medición (grading/metrics) | ✗ | C4 y H4 afectan números publicables — corregir y re-puntuar |
| Ejecución (runner/paradigms/cognitive) | ⚠ | C1/C2/C6, H9, H12 |
| Corpus (generate/verify) | ⚠ | Verificador genuinamente independiente y determinista; C5 y H10 son los huecos |
| Tests | ⚠ | Tolerancias apretadas y valores re-computados OK; 13 módulos de app/ sin ningún check (incl. feasibility/assurance/rules, núcleo de las invariantes); camino de aceptación de promote() sin assert |
| Dependencias | ⚠ | M19; pip-audit no instalado (no se corrió) |
| Secretos / git | ✓ | Limpio: nada sensible trackeado, cache sin headers, corpus sintético verificado contra el generador |

## Estado de aplicación (2026-08-27, mismo día)

Bloque "Ya" **aplicado y verificado**: C1 (`load_rows` excluye infra_error por
defecto), C2 (theta de `report()` a `policies/fitted/`, fuera del glob de
producción), C3 (`app/fsio.py` con `write_atomic`; cache LLM/embeddings/grafo con
lectura tolerante a corrupción; store con head atómico, lock en append+head y
`next_cycle` por max+1), C4 (substring bidireccional eliminado), C5 (C7 re-deriva
alert→cuenta→persona→memo presente), C6 (igualdad estricta en NOTHING/NO DEFECTS),
H4 (sha256 + missed-failure devuelve el escalón actual; la semántica generosa del
detector perfecto se conserva porque está registrada como Finding 2), H10 (REPORTS
usa `_NAME`). Tests: ambos suites PASAN. Corpus: los 7 verifican con el chequeo C7
reforzado (el hueco era latente — ningún corpus real tiene C7 irresolubles).
**Re-punteo** (`_fix_grading_regrade.py`): 10 archivos, 761 filas, **0 cambios** —
el bug de grading nunca se disparó en los datos reales; los números publicados
quedan en pie.

## Plan de acción sugerido

**Ya (antes de la próxima corrida o análisis)**
1. C1 (filtro infra_error en load_rows) — 3 líneas, protege todo lo aprendido.
2. C4 + re-puntuar los JSONL (re-grading sin LLM) — los números del paper primero.
3. C3 patrón tmp+replace en los 4 puntos + try en lecturas de cache.
4. C6 (NOTHING / NO DEFECTS) y C2 (theta de report a directorio aparte).
5. H4 (sha256 en cascade_value) antes de citar cascade_utility en el paper.

**Antes de cerrar E0**
6. C5 + H10 en el verificador, y re-verificar los 6 corpus.
7. H1-H3, H5-H9, H12. M4 (endpoint en fingerprint/clave — invalida cache: hacerlo en un corte limpio).
8. H11 + guardias en los patch-scripts.

**Después**
9. MEDIUMs de una línea (M2, M5, M7, M9, M12) en una pasada; M14/M15 (dedup); tests para feasibility/assurance/rules y el caso de aceptación de promote(); M19 (pins reales).
