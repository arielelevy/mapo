# CLAUDE.md — lab

**Esto es EL PRODUCTO, no el andamiaje de un paper.** Una capa de decisión
determinística para agentes LLM: factibilidad aritmética → creencias con procedencia
(`COMPUTED > OBSERVED > ELICITED > ASSUMED`) → dial de garantía por request (A0–A3) →
ruteo selectivo con abstención → circuit breakers contables → artefacto EXPLAIN.
Diseño completo del entregable: `README.md` (§«Cómo se decide un request»).
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

## El plantel de paradigmas (actualizado 2026-08-29)

**Trece corren la homogénea.** `REGISTRY` tiene 15; salen `cot` (control nulo por
prompting: decisión del 2026-08-26, no se corre nunca más, impedido por código) y
`plan_execute` (retirado por dominado; decisión del autor 2026-08-29: no se ejecuta más).

**`supervisor` es candidato nuevo (2026-08-29)** — el tercero de la familia de sub-agentes
y el que faltaba. `dag_strategy` fija su plan antes de ejecutar, `handoff` fija sus alcances
en el código, y `supervisor` **no decide sus llamadas de antemano**: mira lo que volvió y
recién ahí despacha la siguiente. Su sub-agente recibe **una ventana de 8 unidades**
recortada por el código (una búsqueda sobre la sub-pregunta), no el alcance entero — el
aislamiento de contexto no es una optimización del patrón, es su definición. `P28a-d`
registradas antes de correr.

**Correr los retirados exige declararlo**: `baseline_roster()` obliga a nombrar cada brazo y
`run_cross_product(baseline_reason=...)` deja la razón en el log. El `CATALOG` no se toca —
sus estados y razones son evidencia.

Veredictos previos: `graph_traverse` falsificado (P10a) y en standby con sus dos condiciones
de revival; `extract_compute` / `streaming_scan` INFACTIBLES bajo presupuesto de producción
(la infactibilidad ES el resultado); `pointer_chase` falsificado (P14a). **P15 REFUTADA**: θ
pierde −0,087 neto contra el mejor fijo.

## Corpus con entidades reales (K-6, 2026-08-29)

El generador produce **variantes de superficie** por persona y por firma, **anáfora** con
concordancia, y la referencia cruzada en **forma no canónica**. Medido: **36,5% de las
menciones son invisibles a un `keyword_search` del nombre completo** y el **100% de los
saltos de cadena C3 exige resolver una variante**.

- **Guarda de ambigüedad**: una forma que matchea a dos personas se descarta — destruye la
  verdad derivable.
- **`entities.json`** es el gold: formas, menciones contadas **contra el texto**, y las
  descartadas con quiénes las producen.
- **`corpus/verify.py` sigue siendo independiente**: resuelve por *matching* contra los
  canónicos, no regenerando las variantes del generador, y **no lee `entities.json`** — eso
  sería el generador verificándose a sí mismo.
- **Guarda de correferencia**: un corpus puede verificar 100% y haber perdido la dificultad
  en silencio. Se cuenta y se levanta.

## El analizador léxico es parte del contrato (2026-08-29)

`ANALYZER_VERSION = "v2-stopwords"`. Se sacó el filtro por largo (`len(t) > 2`), que
descartaba las iniciales: `M. Cavallero` e `I. Cavallero` tokenizaban **idéntico**. Ahora se
filtra por palabras vacías, como un motor real, y el IDF pondera.

**Consecuencia medida**: 19 de 26 tareas de `gold_p17` cambian el orden que devuelve el
léxico. **El registro anterior no es replayable** y está en
`results/archivo-2026-08-29-pre-K6/` con su explicación. `load_rows` levanta si un archivo
mezcla analizadores — es la única de las **cinco** guardas de mezcla que ningún otro campo
podía detectar.

**La fusión es un factor**: `HybridRetriever(fusion="rrf" | "relative_score")`. Medido, no
hay evidencia de que una sea mejor —gana en un corpus, pierde en el otro, todo dentro del
ruido— así que queda **RRF**, y en Weaviate va clavado (`rankedFusion`), no heredado del
default, que cambió en su v1.24.

## El vocabulario de región cambió, y por medición (2026-08-30)

`REGION_VOCABULARY = "regions/3-literal"` — el anterior (`card/oracle/coup/chain`) **por**
un eje nuevo, `literal`: en cuántas unidades aparece el literal que la pregunta cita.
`measure_question_literal()` es hermana de `measure_continuation` —forma de token cerrada,
verificada por contención, sin modelo en el medio— y **no es un disparador léxico**: la
misma pregunta cambia de valor si cambia el material.

**No se eligió, se midió.** Con la política de desempate por costo evaluada leave-one-out
sobre 41 tareas × 7 brazos, contra el mejor fijo (`reflection`, u=0,930, 125.169 tokens):

| vocabulario | utilidad | ahorro |
|---|---:|---:|
| **`regions/3-literal`** | **0,951** | **46%** |
| `regions/2-continuation` | 0,928 | 37% |

**El anterior sigue siendo recomputable** (`Features.region_previa()`): 5.932 filas lo
llevan estampado y `load_rows` levanta si un archivo mezcla dos.

> **Corrección 2026-09-01.** La tabla de arriba (0,951 / 46% contra 0,928 / 37%) **no la
> reproduce ningún script del repo**: la revisión externa del paper lo buscó y no lo encontró,
> y el paper la retiró. Lo que sí produce un script es `_plasticidad.py` sobre el rectángulo
> 64 × 8 con objetivo de costo: θ región completa −0,063 [−0,139, +0,002] con 68% de ahorro;
> θ región COMPUTADA −0,104 [−0,181, −0,030] con 31%. Y `_predictores.py` da para la señal
> suelta `cardinalidad × término` −0,017 con 42% (LOTO). Hasta que exista el script, el 0,951
> no se cita. Mismo día: el piso de ruido de `_predictores.py` era el bootstrap del propio
> estadístico y se corrigió; `fiabilidad.perfil` definía inestable como `0 < media < 1` y se
> corrigió a réplicas distintas. Recómputo completo: `bench/analysis/_recomputo_revision.py`.

**Y el sensor tenía un defecto que sólo se vio midiendo** (`EP-5`): una pregunta booleana
cita **sus opciones de respuesta**, no un término de búsqueda —`C7` pregunta «Answer
'escalate' or 'no escalation'»— y esos literales no están en el material por construcción.
La guarda usa `answer_cardinality`, que el caller **declara**. Recomputado con el sensor
corregido, el vocabulario sobrevive: 0,951 y 46%. **Fragilidad anotada**: 14 regiones sobre
41 tareas son 2,9 por región, y ése es su límite real hasta que `M-8` amplíe el panel.

**Lo que NO se tomó, y es decisión abierta del autor (`CP-8`)**: `cardinalidad × literal`
ahorra **69%** y es puramente `COMPUTABLE`, así que **deja a la SONDA sin nada que
resolver**. Lo destapó `test_science.py` §21. Se tomó el que domina al anterior sin apagar
nada.

## La superficie es parte del contrato (2026-08-29)

`SURFACE_VERSION = "v2-agotamiento-compartido"`, y es la **quinta** guarda de mezcla.

De dónde salió: `scoped()` no reataba `surfaced` —lo que alguna búsqueda ya trajo— ni los
contadores de racha, así que **cada sub-agente arrancaba creyendo que nadie había
buscado**. Medido: `supervisor` 370 búsquedas y `handoff` 158, las dos con **0 estériles**,
contra 62,5% de `dag_strategy`. Ese cero no era chico, era estructural.

**Y hasta dónde llega el cambio hay que decirlo con precisión.** En el régimen medido
—`basic`, `stop_on_barren=0`, `stall_warnings=0` en todo el registro— es **sólo
contabilidad**: las utilidades y los costos viejos no están comprometidos, y la corrección
se hace **rellenando desde el caché, no re-corriendo**. Pasa a cambiar comportamiento en
cuanto la variante sea `accounting`/`cognitive` —ahí el aviso entra al prompt— o
`stop_on_barren > 0`.

**La guarda es POR BRAZO, no por archivo.** `scoped()` lo llaman `handoff` y `supervisor` y
nadie más; `dag_strategy` arma el alcance de otra forma. Levantar sobre el archivo entero
volvería inservible un registro válido de 989 filas por un cambio que a diez de los doce
brazos no los toca — y una guarda así se termina desactivando, que es peor que no tenerla.

## Precios y ventanas son INFORMACIÓN EXTERNA, no medición nuestra

Viven en `config/tariffs.json` — **datos, no código** — y por tres razones que no son de
estilo:

1. **Son una cláusula del contrato con el proveedor.** Cambian sin avisar, y actualizarlos
   no debería tocar un `.py` ni pasar por revisión de código.
2. **No se infieren ni se derivan.** Un precio es un hecho de afuera; medirlo sería medir
   la factura, no el sistema. Por eso el archivo lleva **fuente y fecha adentro**, y
   `cost_unit()` estampa `usd@nano/2026-08-28` en cada reporte: un precio sin procedencia
   no se puede auditar, y una fecha vieja se ve.
3. **Un modelo nuevo es una entrada más**, no un cambio de código. `roles` mapea el papel
   lógico (`fast`, `deep`, `max`) al arancel, y el `deployment` al lugar físico donde está.
   La indirección existe para que redesplegar no obligue a tocar la capa de decisión.

**Qué hay declarado por nivel**, y todo es externo:

| eje | qué es |
|---|---|
| `prompt` / `completion` | precio por millón, distintos entre sí (4-8×) y los patrones se diferencian justo en esa proporción |
| `cached_prompt` / `cache_write` | nano no cobra escritura de caché; los `5.6` sí |
| `context_input_tokens` | la ventana de **entrada** (la total incluye 128.000 de salida) |
| `long_context_threshold_input_tokens` | **272.000 para los tres `5.6`** — por encima, tarifa larga |
| `long_context_prompt` / `_completion` | 2× la entrada y 1,5× la salida por encima del umbral |
| `reasons_by_default`, `explicit_effort_with_tools` | **estos dos SÍ están medidos**, con una llamada real por modelo — y se dice cuál está medido y cuál declarado por familia |

**El escalón es un ACANTILADO, no una pendiente** (`X-5n`): por encima del umbral se cobra
la tarifa larga por el **request entero**, no marginalmente. Modelarlo como pendiente
sub-proyectaría justo en el borde, que es donde una cota de admisión decide.

**Y de ahí sale el régimen del banco.** El corpus pone `w48` en ~483k tokens de material,
por encima de los 272k. Con `nano` eso significa que **no entra**; con `luna`/`terra`, que
**cuesta el doble**. El régimen —«leer todo no es la opción obvia»— se conserva con
cualquiera de los tres, y con los `5.6` es más realista: en producción lo que disuade de
leer todo es el precio, no el límite.

## Un factor que no llega al modelo NO existe

Apareció **tres veces en un día**: `offer_board`/`terse_tools` no llegaban a `specs_for`,
`compact_material` no lo pasaba el runner, y `_sub_surface` no lo propagaba a los
sub-agentes. Un factor inalcanzable **no falla: corre y mide su ausencia**, y el resultado se
lee igual que un efecto nulo medido. `test_science.py` §59 lo impide estructuralmente.

## Modelos: los tres corren con herramientas (medido 2026-08-29)

> **QUIÉN MIDE, contra el registro y no contra la intención (2026-08-30).** La campaña es
> **`luna`** — 2.511 filas de `gold_h1`—, `terra` corre **sólo C3** (90 filas) porque cuesta
> 10× la entrada, y **`nano` no tiene ninguna fila**: `results/nano/gold_h1_rows.jsonl` no
> existe. `luna` reemplazó a `nano` como modelo de medición y `nano` quedó como base
> histórica. La tabla de abajo sigue siendo válida —es el smoke de capacidades de los tres—
> pero no hay que leerla como que los tres midieron.

`nano` (`gpt-5.4-nano`), `luna` (`gpt-5.6-luna`) y `terra` (`gpt-5.6-terra`), todos en
`foundryopencode`. **Smoke con una llamada real por modelo, con un prompt que obliga a usar
la tool** — no leído de documentación, que ya costó dos conclusiones equivocadas (`X-5p`):

| | con tools | `reasoning_effort` + tools |
|---|---|---|
| `nano` | OK | **OK** (7 tokens de razonamiento) |
| `luna` | **OK** (razona por defecto, 5 tokens) | HTTP 400 |
| `terra` | **OK** | HTTP 400 |

Así que `X-5s` (`reasoning_effort` como factor) **sólo se puede en nano**, y ahora está
medido individualmente en vez de declarado por familia. `luna` cuesta **clase nano**
(0,20/1,20 contra 0,20/1,25): no es el caro. `terra` es el caro (2/12) y por decisión del
autor va **sólo donde nano no alcanza** — C3, donde nano da u=0,000 en toda la grilla.

`temperature=0` + seed. Embeddings en `innerbifoundry`, config separada
(`AZURE_OPENAI_EMBEDDING_*`), 1.689 vectores cacheados por contenido. Resultados por modelo
en `results/<modelo>/` — **nunca** mezclar modelos en un archivo de resume; `load_rows`
levanta.

**La grilla `gpt-5-chat` dejó de ser referencia** (`R-2` cerrado 2026-08-29): la corrida
homogénea la reemplaza entera — otro corpus, otro tokenizador, otro plantel. Su dato
histórico se replaya, sus huecos ya no significan nada.

## Qué documento es cada cosa (ordenado 2026-08-29)

Son 18 en la raíz y ninguno sobra — cada uno responde una pregunta distinta. Lo que faltaba
era saber **cuál abrir**:

> **Cambió el 2026-08-29.** `README.es.md` se eliminó: era el espejo en español de una
> sección de `README.md`, y dos archivos que dicen lo mismo empiezan a decir cosas
> distintas. `README.md` quedó en castellano, sólo con el estado actual, y su cronología
> de predicciones —1.400 de sus 1.687 líneas— se mudó a `historico/`.

| documento | responde |
|---|---|
| `CLAUDE.md` | **este**: cómo trabajar acá, y qué decidió el autor |
| `PENDIENTES.es.md` · `PAPER.es.md` · `PRODUCTO.es.md` | qué falta, en tres tiempos |
| `README.md` | qué es MAPO, cómo se decide un request, y cómo se corre — **sólo estado actual** |
| `historico/BITACORA-PREDICCIONES.es.md` | la cronología: predicciones registradas antes de correr, y sus veredictos |
| `BENCHMARK.es.md` | cómo mide el banco, y por qué mide lo que producción ejecuta |
| `MEDICION.es.md` | en qué terminó siendo el método, después de romperse varias veces |
| `DISENO.es.md` | el ejecutable actual y sus deudas comprobadas |
| `ARQUITECTURA.es.md` | la pila física del producto (decidida, **no ejecutada**) |
| `PATRON_O_FACTOR.es.md` | la prueba de qué es un patrón y qué es un factor |
| `PATRON_REC.es.md` | reparación epistémica contrafactual: el diseño |
| `EL_DIAL.es.md` | quién elige el dial de garantía, y por qué no el modelo |
| `SOUNDNESS.es.md` | el teorema, y qué NO afirma |
| `COTA_RATCHET.es.md` | la cota que reemplazó el préstamo de v1 |
| `MODELO_Y_CONSTANTES.es.md` | qué se rompe si cambia el modelo (mecanismos vs magnitudes) |
| `ONTOLOGIA_PREGUNTAS.es.md` | los ejes de la pregunta. **Ya no es del todo pizarra** (2026-08-30): dos de sus ejes se midieron contra el registro y separan los brazos **mejor por segmento** que el vocabulario de región — `contradicción` da `S/R = 1,82` con **una sola partición binaria**, contra 1,84 de los ocho segmentos estructurales. Lo que sigue sin medir es si un clasificador puede recuperar el eje de un request real |
| `CONTRATOS.es.md` | contratos de completitud, numéricos y de cita — **dos de las tres clases están en `app/contracts.py`**, no es pizarra |
| `LECCIONES.es.md` | los errores propios, con el número que los delató |

**Y los READMEs de subcarpeta, que son índice del CÓDIGO y no de la teoría:**

| documento | responde |
|---|---|
| `app/README.es.md` | qué hace cada módulo del producto, y en qué estado está |
| `app/paradigms/README.es.md` | el catálogo: 15 registrados, 12 que corren la campaña, 8 activos — y por qué cada uno está donde está |
| `bench/README.md` | cómo se corre el banco, y los tres barridos que buscan la misma falla |
| `corpus/README.es.md` | las 11 celdas, la receta de `gold_h1`, y por qué el corpus tiene entidades |
| `tests/README.es.md` | qué demuestra y qué **no** demuestra cada suite |

> **Este es el único índice.** `DISENO.es.md` §9 tenía un segundo mapa documental y se
> desincronizó —declaraba `CONTRATOS.es.md` como no implementado, y no conocía tres
> archivos—. Se reemplazó por un puntero a acá el 2026-08-29. Dos índices del mismo repo
> empiezan a decir cosas distintas, y el que nadie mantiene es el que miente.

> **Cierre del 2026-08-30**: `historico/CIERRE-2026-08-30.es.md` — once defectos, el
> grader que ponía cero a doce topologías, los predictores con el método completo, y la
> auditoría del ciclo epistémico contra el objetivo real del producto. **Es lo que hay que
> leer para retomar.**

> **Cierre del 2026-08-29**: `historico/IMPLEMENTACION-2026-08-29.es.md` — el board,
> el guard, los cinco defectos que destaparon, y el estado verificado al cerrar.
> Es lo que hay que leer para retomar sin depender de acordarse de nada.

**`historico/`** guarda los snapshots fechados —cierres de sesión, revisiones de código,
auditorías— que valían el día que se escribieron y no describen el estado de hoy. Estaban
mezclados en la raíz, y un documento con fecha al lado de uno vivo se lee como vivo.

## Los tres archivos de pendientes (separados 2026-08-29)

**El orden es del autor y los archivos lo hacen cumplir:**

| archivo | qué tiene | cuándo |
|---|---|---|
| `PENDIENTES.es.md` | **sólo lab**, 23 vivos — y los 23 son la **misma corrida homogénea** mirada por 23 lados | **primero**, hasta que esté terminado, probado, afinado, verificado y testeado |
| `PAPER.es.md` | lo que falta para publicar | **segundo**, con iteraciones de ida y vuelta contra el lab |
| `PRODUCTO.es.md` | lo que hay que construir (`A-*`, `E-3`, `G-2`) | **último**, cuando todo lo demás esté perfecto |

Estaban los tres mezclados, y mezclados se cuelan: un pendiente de producto al lado de uno
de medición compite por la misma atención aunque el orden diga otra cosa.

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
# predicciones falsables registradas con fecha en historico/BITACORA-PREDICCIONES.es.md,
#   ANTES de correr
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

## Las apuestas del paper (2026-09-03)

`P31` a `P36` registradas en `historico/BITACORA-PREDICCIONES.es.md`, una por contribución del
paper, con criterio numérico y lo que se retira si fallan. Las dos gratis corrieron el mismo día:
**`P34` PARCIAL** (`bench/analysis/_p34_costo.py`: 41% de ahorro a Δu +0,058 con la clave
cardinalidad de la RESPUESTA × término; destapó que el eje `card` de la región es cardinalidad
de UNIDADES y que el vocabulario no tiene la cardinalidad de la respuesta, que el caller declara)
y **`P36` FRACASO** (`bench/analysis/_p36_abstraccion.py`: la etapa de abstracción no aísla el
horizonte desde estadísticas crudas; una lo aísla en 8 de 200 particiones y la selección no la
retiene). **No bajar `MIN_EPISODES_FOR_CONFIDENCE` ni agregar `answer_cardinality` al
vocabulario mirando estos números**: las dos son decisiones del autor y cada una pide su propia
predicción registrada antes de correr. Quedan `P32`, `P31`, `P35` y `P33`, en ese orden de costo. La revision externa del 2026-09-03
agrego dos mas, registradas el mismo dia y sin correr: `P37` (24 tareas a mano sobre documentos
reales: el mecanismo sobrevive fuera del generador) y `P38` (el factorial 2x2 que separa la
ramificacion delegada del stack de servicio y mide `V_T` con secuencias de nodos). `P38` va
antes que `P37` porque decide que puede afirmar el paper en 6.1 y las tareas ya existen.
`P39` (rutear por capacidades cobra el premio entre los ocho) corrio el mismo dia, a cero tokens,
y dio FRACASO: ninguna de cuatro politicas LOTO cruza el piso p95; la causa es `EXIGE`, una
conjuncion con dos filas de un solo brazo capaz (`material_mayor_que_ventana`, `entidad_nombrada`),
que deja 63 de 64 tareas sin candidato. **No arreglar `EXIGE` mirando ese numero**: la fila de
material pasa de exigencia a costo solo con su propia prediccion registrada.
**`P40` (2026-09-04) cerro la pregunta del ruteo con una cota, y es el resultado que importa**:
el Teorema 1 instanciado sobre el registro da `Sum(pi*G) = 0,242` contra `Sum(nu*L) = 1,536`,
o sea `beta_max = 0,157`, replicado en `0,186` sobre el held-out. Un ruteador perfecto donde el
brazo gana puede errar en el 16% de donde pierde y nada mas; la asimetria por tarea es 5,5x.
Corolarios que no son opinion: `pointer_chase` tiene `pi = 0` y rutearle nunca se justifica, y
el premio se agranda subiendo `pi` (`P31`) o bajando `L` con abstencion, no con otra clave.
Y una trampa encontrada midiendo: el eje `ausencia` de `ejes_de` sale de `relevant_units == []`,
que **es el gold**, y ahi vive el 80% de la brecha ruteable. La sonda de indice (recuperador
lexico sobre el alcance, cero tokens) es la unica familia de features que correlaciona en los
dos paneles. Script: `bench/analysis/_eda_ruteo_profunda.py`.

**P41 (2026-09-05), preparada y sin resultado empírico:** `app/completion_repair.py` conecta
el déficit de completitud con una reparación acotada. `bench/runs/_run_p41_repair.py` compara
base, retención, reparación genérica y dirigida sobre doce mundos C9 nuevos, dos ejecutores
y tres réplicas. Los corpus y las pruebas locales pasaron. **El autor no tiene créditos hasta
el 2026-09-13; no relanzar llamadas pagadas mientras siga esa restricción.** No hay reanudación
automática. Retomar con `historico/CIERRE-2026-09-05-P41.es.md`. La prueba es local a C9; una
afirmación de mejora del sistema completo requiere después evaluar intervención selectiva y
regresiones sobre todo el corpus.

> **Cierre editorial del 2026-09-03**: `historico/CIERRE-2026-09-03.es.md`. Es lo que hay que leer para
> retomar: qué se hizo en los papers y las figuras, qué destaparon `P34` y `P36`, y qué decide
> el autor antes de la próxima corrida.
