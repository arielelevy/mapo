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
mezcla analizadores — es la única de las cuatro guardas de mezcla que ningún otro campo
podía detectar.

**La fusión es un factor**: `HybridRetriever(fusion="rrf" | "relative_score")`. Medido, no
hay evidencia de que una sea mejor —gana en un corpus, pierde en el otro, todo dentro del
ruido— así que queda **RRF**, y en Weaviate va clavado (`rankedFusion`), no heredado del
default, que cambió en su v1.24.

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
| `ONTOLOGIA_PREGUNTAS.es.md` | **PIZARRA**: nada implementado ni medido |
| `CONTRATOS.es.md` | contratos de completitud, numéricos y de cita — **dos de las tres clases están en `app/contracts.py`**, no es pizarra |
| `LECCIONES.es.md` | los errores propios, con el número que los delató |

**Y los READMEs de subcarpeta, que son índice del CÓDIGO y no de la teoría:**

| documento | responde |
|---|---|
| `app/README.es.md` | qué hace cada módulo del producto, y en qué estado está |
| `app/paradigms/README.es.md` | el catálogo: 15 registrados, 13 que se corren, y por qué los otros no |
| `bench/README.md` | cómo se corre el banco, y los tres barridos que buscan la misma falla |
| `corpus/README.es.md` | las 11 celdas, la receta de `gold_h1`, y por qué el corpus tiene entidades |
| `tests/README.es.md` | qué demuestra y qué **no** demuestra cada suite |

> **Este es el único índice.** `DISENO.es.md` §9 tenía un segundo mapa documental y se
> desincronizó —declaraba `CONTRATOS.es.md` como no implementado, y no conocía tres
> archivos—. Se reemplazó por un puntero a acá el 2026-08-29. Dos índices del mismo repo
> empiezan a decir cosas distintas, y el que nadie mantiene es el que miente.

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
