# Implementación del 2026-08-29 — el board, el guard, y lo que destaparon

> **Qué es este documento.** El registro exacto de lo que se implementó, en qué orden, qué
> lo motivó, qué lo prueba, y qué quedó abierto. Está escrito para que **retomar no dependa
> de acordarse de nada**: cada afirmación acá se puede volver a derivar del repo.
>
> **Snapshot fechado.** Vale el día que se escribió. Lo vivo está en `PENDIENTES.es.md`,
> `DISENO.es.md` §6bis y `ARQUITECTURA.es.md` §6bis.

---

## 0. Estado verificado al cierre

Todo lo de abajo se corrió, no se recuerda:

| | |
|---|---|
| `test_science.py` | **52 chequeos, 524 asserts, ALL CHECKS PASSED** |
| `test_consolidation.py` | **52 asserts, ALL CHECKS PASSED** |
| `_audit_documentos.py` | ningún documento vivo contradice al catálogo, ningún enlace roto |
| `_audit_inerte.py` | todas las guardas disparan en algún corpus |
| `corpus/verify.py` | ground truth verificado independiente de los documentos |
| `results/luna/gold_h1_rows.jsonl` | **989 filas · 815 medidas · cero `infra_error`** |
| `results/luna/gold_h1_boardqueue_rows.jsonl` | 9 filas (celda `cola` del cruce, cortada a pedido) |
| las cinco guardas de mezcla | los dos archivos cargan sin levantar |

**El registro sobrevivió una interrupción del backfill.** El script borra el destino
*antes* de replayar y restaura ante `BaseException`; se cortó a mano a mitad y el archivo
quedó **byte por byte idéntico** a su copia (`sha 147104311f5f`, comparación directa
`True`). La guarda funcionó como está escrita.

---

## 1. El orden en que pasaron las cosas, y por qué importa

No fue una lista de tareas: **cada paso salió del anterior.** Reconstruir el orden es lo
que evita repetir el razonamiento.

```
reforzar el paper
   └─ §5 tenía 2 secciones y el lab 3 teoremas cerrados con test  →  §5.3, §5.4, §5.5
       └─ el banco es un procedimiento de ajuste, y no estaba dicho  →  §6.5
           └─ ¿esto vale? ¿se extrapola fuera de RAG?  →  revisión crítica
               └─ 12 tools, NINGUNA cambia nada fuera del proceso  →  §5.6 + límite en §9
                   └─ «¿y el blackboard?»  →  medido: 1 de 125 llamadas
                       └─ «es GENERAL, no de dag»  →  la cola era inerte fuera de dag
                           └─ «el guard es para acotar contexto»  →  faltaba entero
                               └─ analizar los logs  →  supervisor y handoff: 0% estéril
                                   └─ «algo que corregir»  →  quinta guarda de mezcla
```

---

## 2. Lo que entró al paper

**Siete** secciones nuevas, en los dos archivos y en la misma posición (`paper-en.md` es
canónico, `paper-es.md` su espejo; `_audit_documentos.py` compara la secuencia de
encabezados y da **50 = 50**).

| sección | qué afirma | por qué entró |
|---|---|---|
| **§5.3** soundness del ensamblador | si emite, todo número emitido está implicado por la base de creencias al piso pedido | estaba construido y probado (`test_science.py` §46) y el paper lo ignoraba: «soundness» aparecía **0 veces** |
| **§5.4** la cota nativa del ratchet | `≤ 2R` endurecimientos en toda la vida del sistema, por monotonía | reemplaza un préstamo de v1 que era un **error de categoría**: una secuencia monótona tiene varianza que tiende a cero, así que la cota se cumplía vacuamente |
| **§5.5** quién fija el dial | `max(pedido, piso de creencias, piso aprendido)`, y `max` es la única composición donde toda fuente sólo endurece | idem, y marginalizar destapó que **A0, A1 y A2 son indistinguibles** en restricción de catálogo |
| **§5.6** lo que la teoría no supone | ninguno de los cinco resultados menciona recuperación: eso **es** la afirmación, no una salvedad | decisión del autor: *no angostar el paper*. Con las cuatro superficies y el argumento de que la rama `v=0` vive en acciones |
| **§6.5** el banco como procedimiento de ajuste | el mismo producto cruzado que mide los paradigmas ajusta la capa que los elige, a costo marginal cero | tesis del autor, encaja con el ejecutable, y el paper no lo decía |
| **§7.7** estado compartido ofrecido y no tomado | **1 de 125** llamadas | evidencia nueva, medida esta sesión |
| **§7.8** el 99% del gasto de entrada es la conversación mandada otra vez | trazado por llamada: turno 0 = 607 tokens, turno 8 = 67.233 (**110,8×**) | el primer resultado que una FILA no podía producir |

**Y el balance honesto, en §9**: las 12 herramientas de todo el registro —5 leen el mundo,
6 escriben el estado del propio agente, 1 lee contabilidad— y **ninguna cambia nada fuera
del proceso**. Las 6 tareas con `irreversible=True` son una clasificación calificada por
exact-match con la etiqueta de una acción encima: no hay herramienta que congele una
cuenta, así que el piso que existe para gatear lo irreversible **nunca tuvo un acto que
gatear**.

**Conteos viejos corregidos**: el apéndice decía «7 paradigmas, 63 aserciones» y son **15
registrados y 573 aserciones** (hoy 524, tras cerrar §65); §9 decía «un modelo, `gpt-5-chat`, rechaza temperatura» y
ahora dice lo medido — tres modelos, `terra` el más reproducible, y la restricción viva
que es estructural (`tools` + `reasoning_effort≠none` = HTTP 400 en la familia `5.6`).

---

## 3. Los cinco defectos encontrados, todos de la misma familia

**La familia es una sola: algo existe, se lee, se ejecuta, tiene test que pasa — y no
llega a donde tendría que llegar.** Ninguna de las auditorías previas la ve:
`_audit_declarado` busca nombres que nadie lee, `_audit_inerte` busca guardas que ningún
corpus dispara. Ésta vive en el **camino**.

### 3.1 — Lo que no es una medición entraba al aprendizaje (`X-7`, cerrado)

**Tres constructores de episodios con tres filtros.** Los dos scripts de análisis
descartaban infactibles y de infraestructura; `Runner.episodes()` —el camino del
**producto**— no descartaba las infactibles. La guarda vivía en el banco y le faltaba al
producto: la inversión exacta de la regla del repo.

**Medido antes de tocar nada: 39 de 180 episodios (21,7%) venían de celdas que nunca
ejecutaron.** El sesgo no es aleatorio —cae sobre los brazos caros, que son los que la poda
alcanza—: dos pares reportaban `u = 0,667` midiendo **1,000 donde ejecutaron**, y quince
pares llevaban `u = 0,000` con `n = 2–3` **sin una sola ejecución detrás**.

> Lo grave es el **conteo**, no el promedio: los episodios son lo que cruza
> `MIN_EPISODES_FOR_CONFIDENCE`, así que un par podía **ganar confianza con celdas donde
> el brazo nunca corrió**. Ninguno había cruzado —la campaña era joven— pero quince estaban
> en camino, y **nada lo impedía**.

`policy.learnable_rows` es ahora el único portón y **devuelve el conteo tipado de lo
descartado**: un filtro silencioso deja la estadística limpia y a nadie en condiciones de
decir sobre cuántas filas se computó. Los cuatro aprendices pasan por ahí.

**Y el error simétrico está probado igual**: una respuesta equivocada, una vacía de un
brazo que **sí** corrió, y un `Unknown` literal del modelo son mediciones. Entrenar sólo
con éxitos es la forma más rápida de aprender que todo funciona. `test_science.py` §60.

### 3.2 — La cola del board era inerte fuera de `dag` (`B-1`)

Medido: de **125 llamadas a herramientas**, `post` se llamó **una vez** y `board` **cero**.
0,8%.

**Y el nulo es sobre la afordancia, no sobre el estado compartido.** El mismo objeto,
alcanzado de dos maneras, da resultados opuestos:

| cómo se accede | quién lo escribe | resultado |
|---|---|---|
| **inyectado** en el prompt del sub-agente | el **código** | `dag_strategy` es el mejor paradigma fijo en `gold_transfer` |
| **ofrecido** como tool | el **modelo**, si elige | **1 de 125** |

La corrección del autor —*«es GENERAL, no de dag»*— destapó que la cola que implementé
llegaba al modelo por **dos caminos y los dos particulares**: la plantilla del sub-agente de
`dag_strategy`, y el retorno de la tool. **Un agente solo no podía llevar cola.** Ahora se
inyecta en el **bucle de herramientas compartido**, el único del repo que manda la
declaración de tools. `test_science.py` §61, 25 asserts.

### 3.3 — El guard de contexto no existía (`B-2`)

El banco tiene **dos** compactaciones y **ninguna extrae nada**:

| | qué hace | medido |
|---|---|---|
| `compact_history` | stub **sólo** de lo que el modelo anotó | el modelo escribió **1 nota en 28 filas** |
| `manage_history` | degrada incondicionalmente a gist | **61 llamadas sobre `w4`, 0 mensajes degradados** |
| *el guard de la capa congelada* | **crea** un hallazgo enfocado en la pregunta | **no existía acá** |

Las dos **degradan**; la que faltaba **produce**. Y esa diferencia es lo que le da al board
algo que sostener.

`app/context_guard.py`: dispara por **crecimiento** (20k caracteres en una iteración),
expulsa de a uno, nunca toca el prompt ni el batch corriente, y **la extracción es una
llamada al modelo que se cobra**. `test_science.py` §62.

**Dos correcciones que salieron de probarlo:**

1. **El test cazó que el guard no disparaba nunca.** Yo protegía el batch corriente **y
   además** los últimos 4 mensajes; en un bucle corto esos 4 **son** toda la conversación.
   Corría, no fallaba, y medía cero. Quedó **una sola protección, la principiada**: lo que
   el modelo todavía no razonó.
2. **El probe sobre el corpus destapó que una extracción vacía se contaba como «el texto no
   aportaba nada»** — y son opuestas: la segunda habla del **retriever**, la primera es una
   falla del **extractor**. Peor: expulsaba igual, perdiendo evidencia por una falla del
   extractor, que es el daño que el mecanismo existe para evitar. Cuatro contadores en vez
   de tres, y una extracción fallida **deja el texto donde estaba**.

### 3.4 — El agotamiento del retriever era invisible en un sub-agente (`X-8`, cerrado)

Lo delató el registro con un cero que no era chico sino **estructural**:

| brazo | búsquedas | estériles | tasa |
|---|---:|---:|---:|
| `dag_strategy` | 661 | 413 | **62,5%** |
| `react` | 460 | 214 | 46,5% |
| `supervisor` | 370 | **0** | **0,0%** |
| `handoff` | 158 | **0** | **0,0%** |

`scoped()` reata por referencia todo lo que es de la tarea y **no reataba `surfaced`** —lo
que alguna búsqueda ya trajo— ni los contadores. Cada sub-agente arrancaba con el conjunto
vacío: **toda búsqueda suya parecía nueva**. Los `int` además no se pueden reatar (`replace`
copia por valor), así que ahora viven en un objeto `Barren` compartido.
`test_science.py` §63.

> **Sólo `handoff` y `supervisor` llaman a `scoped()`.** `dag_strategy` arma el alcance de
> otra forma, así que su 62,5% **ya era correcto** — corrección de algo que insinué mal
> antes.

### 3.5 — Arreglar `X-8` volvió incomparables filas viejas, y nada lo veía (`X-11`, cerrado)

Las cuatro guardas de mezcla miran decodificación, brazo de recuperación, analizador léxico
y vocabulario de región. **Un cambio de código en la superficie no entra en ninguna**, y la
huella tampoco lo lleva.

`SURFACE_VERSION = "v2-agotamiento-compartido"`, estampado en la fila, **quinta guarda** en
`load_rows`, siguiendo el precedente de `ANALYZER_VERSION`. Y es **por brazo, no por
archivo**: levantar sobre el archivo entero volvería inservible un registro válido de 989
filas por un cambio que a **diez de los doce brazos no los toca** — y una guarda así se
termina desactivando, que es peor que no tenerla. `test_science.py` §64.

**Y hasta dónde llega el cambio hay que decirlo con precisión, porque lo escribí exagerado
primero.** Verificado: las 814 filas con variante declarada corrieron en `basic` con
`stop_on_barren=0`; el aviso de estancamiento está gateado a `accounting`/`cognitive` y
`stall_warnings` da **0 en todo el registro**. Así que **en el régimen medido el cambio es
sólo de contabilidad**: las utilidades y los costos viejos **no están comprometidos**. Pasa
a cambiar comportamiento en cuanto la variante sea `accounting`/`cognitive` o
`stop_on_barren > 0`.

**Consecuencia de plata**: la corrección se hace **rellenando, no re-corriendo**. Iba a
proponer re-correr los dos brazos —143 filas, 46 celdas, **7,45M tokens**— y no hace falta:
como el modelo nunca vio la diferencia, los prompts son idénticos y `_backfill.py`
reconstruye desde el caché con **cero llamadas al proveedor**.

---

## 4. Lo que se construyó nuevo

| archivo | qué es |
|---|---|
| `app/context_guard.py` | el guard: acota por crecimiento y **produce** el hallazgo |
| `app/board.py` (extendido) | cola de pendientes, cobertura, dedup, directiva, e `inject()` — **todo detrás de `queue_mode`, apagado por defecto y con el render viejo byte por byte** |
| `app/policy.py` → `learnable_rows` / `Discarded` | el único portón del aprendizaje, con conteo tipado |
| `app/llm.py` → `trace_to()` | **traza por llamada**, en el cliente y no en el bucle: cubre los 27 sitios que llaman al modelo, no 1 |
| `bench/runs/_run_board.py` | el cruce `{cola, sin} × {guard, sin}` sobre `w16` |
| `bench/runs/_run_cobertura.py` | el 10×: máxima cobertura, mínimas llamadas |
| `bench/oneoff/_probe_guard_orden.py` | valida el **orden de ejecución** sobre una tarea real, con cliente guionado: cero costo, cero colisión |
| `bench/runs/_backfill.py` (corregido) | `--modelo` desde la tabla: estaba clavado a `nano`, y con la huella equivocada **ninguna clave de caché acierta** |

---

## 5. Lo que el registro dijo, y es lo más fuerte de la sesión

### 5.1 La brecha de oráculo no sobrevive al ruido

Sobre las 21 tareas donde corrieron los 9 brazos: mejor fijo `react` = 0,7460, oráculo =
0,8413, **brecha +9,5 pp**. Y contra el ruido **de cada tarea**:

> **0 de 21 tareas tienen brecha por encima de su propio ruido.** En **17 de 21 el mejor
> fijo YA es el oráculo**. Sólo **3 tareas** tienen un único mejor brazo.

Eso explica `P15` mecánicamente: θ no perdió por ser mal router — **casi no había premio que
capturar en este estrato**. Es la limitación que el paper ya nombra como *«el régimen en
ventana es casi tautológico»*, ahora con el número.

### 5.2 El costo crece como `N²` y la cobertura como `N`

| | celdas | tokens | `u` |
|---|---:|---:|---:|
| ≤ 2 llamadas | 234 | **9.779** | 0,509 |
| ≥ 8 llamadas | 65 | **136.432** | 0,631 |

**14× más tokens por +0,122 de utilidad.** La conversación se reenvía entera en cada vuelta.
Y ningún brazo pasa de **1,6 unidades leídas por llamada**; `read_all` las lee todas en una,
y **no está ofrecido en `basic`** — la variante de todos los estudios medidos.

### 5.3 Buscar de más y releer de más escalan con el ancho

| estrato | estériles | racha máx | releído |
|---|---:|---:|---:|
| `sin-w` | 30,0% | 7 | 5,0% |
| `w4` | 36,1% | 12 | 7,1% |
| **`w16`** | **63,5%** | **21** | **15,2%** |

Dos de cada tres búsquedas en `w16` no traen nada nuevo, y **21 seguidas** en una sola
celda. Un sexto del material servido es texto que el agente ya tenía. Y la retención cae
(0,990 → 0,994 → **0,943**): **relee más y retiene menos**.

**Y estos números están subestimados**: se midieron con `X-8` vivo, o sea con `supervisor` y
`handoff` reportando cero.

### 5.4 `P30` corrió, y refutó su propia hipótesis de la manera útil

Se lanzó **un solo brazo** —`readall`, el que aísla— porque el 2×2 completo daba 17,3M
tokens y `accounting` cambia dos cosas a la vez. Costó **5,5M**, por debajo del techo de
8,6M estimado contra el baseline pago.

| | tok/celda | llamadas | unidades | `u` |
|---|---:|---:|---:|---:|
| `base` | 137.211 | 4,3 | 10,0 | 0,540 |
| `readall` | **87.495** | 4,0 | 8,5 | 0,540 |

**1,57× más barato en tokens con la utilidad idéntica** — `+0,000` sobre 63 celdas
pareadas, no «dentro del ruido».

**Pero `read_all` se llamó en 3 de 63 celdas**, y las unidades leídas *bajaron*. Así que el
ahorro **no viene de leer todo en una llamada**, que era la hipótesis. El registro nombró la
causa real:

| | `base` | `readall` | |
|---|---:|---:|---:|
| caracteres releídos | 2.836.465 | **322.094** | **8,8× menos** |
| fracción del servido que se relee | **12,6%** | **1,9%** | |

La mezcla de herramientas casi no se movió —399 llamadas contra 365—. Lo que se derrumbó
fue la **repetición**. **El efecto está en la oferta, no en el uso**, y es la segunda vez que
este registro produce uno así: el board ofrecido como tool dio 1 de 125 (nulo), `read_all`
3 de 63 y movió el costo (positivo).

**Y la traza por llamada dio el número que la fila nunca pudo dar.** 273 llamadas trazadas,
primera corrida con `MAPO_TRACE=1`: el turno 0 cuesta 607 tokens de prompt, el 2 cuesta
33.548 (**55,3×**), el 8 cuesta 67.233 (**110,8×**). **El 99% del gasto de entrada es
re-envío de la conversación** — el primer turno consume 38.238 de 5.503.757. El `N²` era una
inferencia sacada de comparar poblaciones; ahora es una medición directa sobre las mismas
tareas.

### 5.5 Y una corrección que me hice a mí mismo, después de escribirlo

Miré `provider_cached_tokens` —un campo que no entraba en la conclusión— y daba **4.412.471
de 8.631.304** en el brazo base: **el proveedor sirve el 51% de la entrada de su propio
caché, a una décima parte del precio**.

| | tokens | dólares |
|---|---:|---:|
| el ahorro | **1,57×** | **1,36×** |

**Ninguno de los dos es «el verdadero»**: los tokens deciden si una tarea entra en la ventana
y dónde se cruza el acantilado de contexto largo; los dólares son lo que paga un despliegue.
Difieren **15%**, suficiente para dar vuelta qué brazo parece mejor en una comparación
ajustada. *Un resultado de costo sin su unidad no es reportable.* Lección `8.12`, y es la
cuarta vez que aparece la misma forma: **un número medido correctamente puede sostener una
afirmación equivocada si le falta la dimensión en la que vive.**

---

## 6. Decisiones del autor tomadas en la sesión

| decisión | dónde quedó |
|---|---|
| **No angostar el paper**: §5 se afirma para agentes en general, con el balance al lado | `paper-*.md` §5.6 y §9 |
| **Langfuse con su propio SDK, sin OpenTelemetry en el medio** | `ARQUITECTURA.es.md` §6bis, `PRODUCTO.es.md` `O-1` |
| **La coordinación es general**, no una propiedad de `dag` | `DISENO.es.md` §6bis |
| Cortar el cruce del board **después de la celda `base`** | 126 filas de `w16`, 42 celdas, `repeat 3` |

---

## 7. Qué quedó abierto, y en qué orden

1. **`X-11`** — rellenar `gold_h1_rows.jsonl` desde el caché (`--modelo luna`) para que las
   filas lleven `surface_version` y los `barren_*` corregidos. **Cero tokens.** Se
   interrumpió a mitad y el registro se restauró intacto; hay que volver a lanzarlo con la
   campaña detenida.
2. **`P29`** — el cruce `{cola, sin} × {guard, sin}`: falta `cola` (9 de ~63 filas),
   `guard` y `ambos`. La celda `base` está completa: 126 filas de `w16`, 42 celdas,
   `repeat 3`.
3. **`P30c`** — el brazo `accounting`, que diría si `coverage` cambia la decisión de pedir
   todo. `readall` ya corrió y cerró `P30a`, `P30b` y `P30d`.
4. **`X-9`** — decidir a partir de qué ancho `stop_on_barren` deja de ser factor y pasa a
   ser el comportamiento por defecto. Con 63,5% de esterilidad en `w16` la pregunta ya no
   es si conviene.
5. **`X-10`** — el releído, que `read_all` ataca por el mismo lado que `X-9`.
6. **`O-1`** — Langfuse, **con el producto y no antes**: hoy no hay servicio que trazar.

---

## 8. Lo que NO se hizo, dicho para que no se busque

- **No se corrió el brazo `accounting`** de `_run_cobertura.py`: quedó afuera por precio, y
  porque `readall` es el que aísla el mecanismo.
- **No se completó el cruce del board.** Sólo `base` y 9 filas de `cola`.
- **No se instrumentó nada con Langfuse.** La decisión está tomada y escrita; el código no
  existe porque el producto tampoco.
- **No se tocó `legacy/`.** Se leyó entero para comparar, y sigue congelado.
- **El push se hizo**, autorizado por el autor al cerrar. Cuatro commits, y el primero tuvo
  que **mergear** un snapshot que el autor había pusheado a las 17:01 desde otra máquina:
  dos ramas paralelas desde la misma base. El único conflicto real fue `_backfill.py`, y se
  resolvió a favor de `--modelo` —que toma la huella de la tabla— porque la versión del
  remoto estaba clavada a `nano` y **con la huella equivocada ninguna clave de caché
  acierta**: el «rellenado» habría pagado el registro entero de nuevo.
