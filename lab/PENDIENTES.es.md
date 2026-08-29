# Pendientes — MAPO

> **Fuente única de «qué falta».** Recopilado el 2026-08-27; **última sincronización
> 2026-08-28**.
>
> **Cómo se usa.** Un `[x]` se queda acá **con el resultado adentro**, no se borra: la
> mitad de lo cerrado esta semana resultó estar **mal diagnosticado**, y saber qué decía
> el pendiente antes de medirlo es lo que permite ver eso. Lo que sí se saca es el
> pendiente que ya no significa nada.
>
> **Un defecto de construcción puede ser una tarea acá, nunca un hallazgo.** Un bug, un
> lock roto, un límite de tasa: se arreglan y se registran como trabajo. No entran a
> `LECCIONES.es.md` ni a los papers, y no son premisa de ninguna conclusión.
>
> **Un número derivado se verifica en la granularidad donde vive, no en el agregado.** Un
> promedio puede ser posible mientras cada uno de sus términos es imposible — agregar es
> exactamente la operación que borra la contradicción. `_sanity.py` tiene las cotas y
> **levanta**: un aviso al lado de un número imposible sigue publicando el número.
>
> **Y una regla que estaba mal puesta como pendiente**: toda edición del paper va a
> `paper-en.md` **y** a `paper-es.md`, en la **misma posición** de cada uno. No es una tarea
> que se pueda terminar — es una disciplina, y tenerla en la lista con una casilla que nunca
> se marca la vuelve ruido. Está acá porque ya se rompió: un bloque quedó antes del párrafo
> de verificación en un archivo y después en el otro. **Dos archivos que dicen lo mismo en
> distinto lugar empiezan a decir cosas distintas.**

---

## Qué sigue: una sola cosa

> **Sincronizado 2026-08-29 (segunda pasada).** Quedan **23 pendientes vivos, y 22 son la
> misma corrida.** No son veintitrés trabajos: son la matriz de la corrida homogénea,
> mirada por veintidós lados.
>
> **Lo que era código y no corrida se hizo, así que ya no queda nada que no sea medición
> — salvo uno.** Los tres que salieron de leer los `.md` contra el código:
>
> | | |
> |---|---|
> | **`X-5h`** | **cerrado** — `seal_replay` prometía replay sellado y no lo imponía nadie. Ahora `answer(replay=True)` usa un cliente sellado cuando el perfil resuelto lo exige, y un miss levanta |
> | **`AR-5`** | **cerrado** — `metrics.arm_effect` estratifica por dosis y **se niega** a promediar sobre dosis dispares |
> | **`P-2g`** | **abierto, y es el único vivo que no es la corrida.** La asociación aprendida se fabrica como creencia y ninguna regla la consume. No es código pendiente: es una **decisión de diseño del autor** —dónde entra un prior sobre el orden de tools sin que una estadística se vuelva control de flujo— y por eso no se hizo sola |
>
> Las tres son la misma familia, y este repo ya la encontró cuatro veces: **algo que se
> declara o se produce y nadie lee.** Ninguna la atrapa `_audit_declarado.py`, porque en
> todas el nombre *sí* se lee — lo lee quien lo produce. Lo que falta es un **consumidor**,
> y eso es una propiedad del cruce entre dos módulos, no de un nombre.
>
> Lo de **producto** se mudó a `PRODUCTO.es.md` y lo del **paper** a `PAPER.es.md`. No están
> cerrados — van en otro momento, y el orden lo fijó el autor: **lab primero** (terminado,
> probado, afinado, verificado, testeado), después el paper con iteraciones de ida y vuelta,
> y el producto al final. Tenerlos en archivos separados es lo que impide que se cuelen.

### La luz verde: la corrida light pasa, y ahora prueba algo (2026-08-29)

**Se puede lanzar.** `bench/runs/_run_homogenea_light.py` corre la matriz entera —13
patrones × 7 factores sobre las 4 tareas más baratas— con **0 errores** y 8,2M tokens
contabilizados, todo desde caché. Pero el cambio que importa no es que pase: es **qué puede
probar ahora**.

Antes imprimía «0 errores, la matriz corre entera», y eso era verdad y era insuficiente:
**un factor que no llega al modelo tampoco da error — da exactamente la base.** Ya había
pasado tres veces en un día (`offer_board`, `terse_tools`, `compact_material`). Ahora cada
factor se compara contra la base y reporta cuántas filas movió:

| factor | filas movidas | veredicto |
|---|---|---|
| `hyde` | 26 / 52 | cableado verificado |
| `prune` | 24 / 52 | cableado verificado |
| `board` · `read_all` · `terse` | 20 / 52 cada uno | cableado verificado |
| `managed` | **0 / 52** | inerte, **con explicación medida** — ver abajo |

**`managed` no está roto, y eso se midió en vez de suponerse.**
`bench/audits/_diagnose_managed.py` envuelve `manage_history` y cuenta dos cosas que las
filas no pueden mostrar: **61 llamadas, 0 demociones.** El camino se recorre; la condición
no se cumple. Sólo demota resultados de tool con TEXTO COMPLETO, y en `w4` (4 unidades) el
modelo busca una vez y lee una vez: lo único que queda en la historia previa es un `search`,
cuyas entradas traen `summary` y no `text`, y ésos se saltean a propósito. La lectura cae
siempre en el último batch, que por definición no se demota. **`w4` no tiene historia que
compactar, y `managed` es exactamente el factor que compacta historia.** Su cableado se
verifica en la primera celda `w16` de la campaña — no antes, y la corrida lo dice en vez de
darlo por bueno.

### Tres cosas que aparecieron al hacerlo, y que no eran hallazgos sino defectos

- **El corpus de la campaña vivía en una carpeta temporal de sesión.** `gold_h1` —las 78
  tareas sobre las que corre todo— estaba en el scratchpad y se iba a borrar solo. Su
  receta **no estaba escrita en ningún lado**. Ahora vive en `corpus/gold_h1`, verifica
  entero (11 celdas en PASS, 39/39 saltos de cadena exigiendo resolver una variante), y la
  receta está en el docstring del script y en `corpus/README.es.md`.
- **`load_rows` volteaba cualquier archivo con una fila podada.** La guarda de mezcla de
  analizadores contaba a una fila **infactible** como «tokenizador sin declarar». Una fila
  podada por aritmética no ejecuta, no busca y no tokeniza: no tiene tokenizador que
  declarar. Con dos `direct` infactibles —lo normal— volteaba la corrida entera, y el
  mensaje hablaba de tokenizadores. Arreglado con test (`test_science.py` §49), incluido el
  caso que **sigue** levantando: una fila EJECUTADA sin analizador sí es del régimen viejo.
- **Dos corridas light a la vez appendean al mismo `.jsonl`.** El lock impide el archivo
  corrupto, no el conteo doble: el resumen salió con `terse` en 77 filas de 52. Se corre de
  a una, y está escrito en el docstring.

### El presupuesto de la BASE, ahora medido y no estimado

Con el costo por celda medido en la light y **la poda aritmética aplicada** —que es gratis
y es la regla de la casa:

| | |
|---|---|
| celdas que corren | **750** de 1.014 (**264 podadas a costo cero, 26%**) |
| tokens proyectados | **~265M** (contra 395M sin contar la poda) |
| plata, a tarifa nano | **~USD 56**, y ~32 si el caché del proveedor sirve la mitad de la entrada |
| dónde se va | `dag_strategy` 70M · `supervisor` 41M · `handoff` 39M · `react` 39M · `reflection` 38M · `gist_reader` 27M |

La poda es la que hace barato esto: `direct` corre 6 tareas de 78, `streaming_scan` y
`extract_compute` 12, `map_reduce` 24. **Lo que se sabe que no entra no se paga.**

**Lo que sigue siendo la decisión del autor** no es la plata: son las **horas de reloj**, y
que una corrida en background muere con la sesión.

---

**La corrida homogénea, y qué cierra cada parte**

| lo que se corre | cierra |
|---|---|
| **BASE** — 13 patrones × 78 tareas × repeat 3, `hybrid`/`basic`/`nano` | el ranking homogéneo; `D-4` (handoff), `P-2b` (drift, que sólo necesita episodios), `P-2e` |
| `hybrid` contra `hybrid`+rama HyDE | `H-3` `AR-3` `AR-4` |
| `{basic, managed}` sobre los 5 con historia | `C-4` (primer brazo: compactar historia) |
| `{compact_material, sin}` sobre los que arman prompt grande | `C-4` (segundo brazo: podar material) |
| `{offer_board, sin}` | `F-2b` |
| `{offer_read_all, sin}` | `D-1b` |
| `{terse_tools, sin}` | `X-4c` |
| `{none, low, medium, high}` de `reasoning_effort`, **sólo nano** | `X-5s` |
| el brazo en prosa (E1) | `M-1` |
| **A2 con la sonda encendida** | `S-5` — la corrida que nunca ocurrió, sin la cual la calibración da cero |
| celdas B2, D1 y C9 del corpus nuevo | `O-2` `O-3` `X-5i` `U-6` |
| `luna` y `terra`; `terra` sólo en C3 | `M-3` `M-5` `M-4` (mitad), `P27f` |
| tasa de error del barato al piso de A2 | `X-5g` |
| los siete brazos de REC | `REC-4` |

**Lo que la corrida NO cierra, y hay que hacer aparte**

- [x] **`_benefit_on` sobre brecha neta — CERRADO el 2026-08-29, y el resultado es que la
  cláusula NO se promueve.** El diagnóstico era correcto: con utilidad sola el beneficio da
  `+0,0000` **por construcción**, porque el paradigma después de reparar es el mismo
  `fallback`. Lo que una cláusula de adquisición compra no es utilidad, es **no tener que
  sondear** (83k tokens medidos en `P17b`) contra los `max_tokens` que la cláusula declara.
  Ya está implementado: `_benefit_on` toma `lambda_cost`, `probe_tokens` y `clause_tokens`,
  y opera sobre la **razón** de costo contra el más barato de la tarea —la convención del
  banco—, no sobre tokens absolutos.

  **Y a λ=0 devuelve exactamente lo de antes, así que no reinterpreta ningún veredicto
  viejo.** Barrido medido sobre el mundo de validate (n=8), piso de ruido `0,0655`:

  | λ | beneficio |
  |---|---|
  | 0,00 | `+0,0000` — reproduce el veredicto anterior |
  | 0,02 | `+0,0124` |
  | **0,05** (el λ de decisión del banco) | **`+0,0311`** — adentro del ruido |
  | 0,10 | `+0,0622` — todavía adentro |
  | 0,20 | `+0,1244` — recién acá supera el piso |

  **Veredicto honesto: la cláusula no se gana la promoción al λ con el que este banco
  decide.** Necesita λ=0,2, cuatro veces más, para salir del ruido. `aceptada: False`,
  `clausula promovida: False`. El mundo final **no se consumió** —`validate_ok` fue falso,
  así que el ledger sigue entero y se puede gastar cuando haya algo que valga gastarlo.

  Lo que esto cierra: el eje faltaba y ahora está, y se puede medir. Lo que NO cierra: que
  esta clase de cláusula valga. Hoy, medida en su propio eje, no alcanza.
- **`M-4` corpus natural.** Su otra mitad —segunda familia de modelos— ya está.

**El presupuesto, con lo medido hoy**

`w48` es **483k tokens de material por tarea** contra 40k de `w4`: **12×**, y con 21 tareas
de cada width es ~66% del gasto. Los factores se **tamizan en w4+w16** (42 tareas, ~1/3 del
costo) y sólo los que muestran señal se confirman en `w48`. El criterio es explícito: con 26
tareas pareadas el error estándar es ~0,034, así que un factor que no se ve ahí es más chico
que 0,07 — y un efecto más chico que eso no cambia ninguna decisión.

**La base no se recorta.** `w48` es el único régimen donde el material no entra en ventana
(483k contra los 272k de nano), y ése es el régimen que el banco existe para medir.

---

## Resumen — todo de un vistazo

`[x]` hecho · `[~]` empezado · `[ ]` no empezado — **13 abiertos · 10 en curso · 149 cerrados** (contados 2026-08-29)

> **El contador se cuenta, no se recuerda.** Decía «59 abiertos · 16 en curso · 52
> cerrados» y los números reales eran 14, 10 y 147: se había escrito a mano y quedado
> viejo. Un contador que miente es peor que no tenerlo, porque se lee con la autoridad
> de una medida. Se recuenta con `grep -c '^- \[ \]' PENDIENTES.es.md`.

> **Las dos tesis que el autor pidió sostener quedaron cerradas el 2026-08-28.**
> **Hebbiana**: establecida en su único sentido vivo —asociación entre pares sobre el
> orden de herramientas— con `p = 0,0078`, y **débil**: 3 celdas de 13, un corpus, un
> modelo. **Determinismo**: 390 de 390 filas replayadas selladas, 0 llamadas vivas y 0
> discrepancias en utilidad, respuesta y costo.

**Bloqueantes**
- [x] **B1** · veredicto de P16 — **P16a REFUTADA** (−1,2888), **P16c decisiva**: +0,1211 con λ=0 y adentro del ruido en λ=0,02 · P16d 26/26 · 0 infra · 13,95M tokens
- [x] **B2** · detectores honestos aplicados — una sola función `has_runtime_detector`, falla cerrada; **P17a confirmada con el código real: cascada 2/26**
- [x] **B3** · **P17 cerrada**: P17a CONFIRMADA (cascada 2/26), **P17b REFUTADA (0 de 14: la sonda corrió, costó 83k tokens y no resolvió ninguna)**, P17c REFUTADA (−1,0425), P17d 26/26. El cuello de botella es **la sonda**

**La cuarta pre-empción — lo único que queda entre el registro y una respuesta**
- [x] **S-1** · **cerrado: la sonda resuelve 9 de 14 y el residuo está declarado.** El verificador exigía ids de unidad y los documentos se referencian por **nombre de persona** — el prompt pedía bien y el verificador rechazaba lecturas correctas. Ahora resuelve cualquier puente **literal**, con guarda de especificidad, y exige **además** que el sensor diga «no autocontenida». Lo que falta no es de la sonda: es la condición de calibración de `S-5`
- [x] **S-3** · **cerrado: el hallazgo ES el resultado.** No hay eje computable que cierre el acoplamiento, y está medido por qué: cardinalidad no separa (C4-w4 y C5-w4 tienen los mismos 5 units), continuidad falla C3, profundidad de puentes da C2=1,22 contra C3=1,28. Los tres miden el **material**, y el acoplamiento es propiedad de **(pregunta × material)**. Qué hacer con eso lo decidió `S-4`; la mitad que falta —tipar la demanda de la pregunta— se hizo en `O-4`/`U-1`
- [x] **S-4** · **decidido: (a), y no hacia falta elegir — la cadena lo decide.** (b) duplica el costo de una sonda que ya costo 83k tokens por un eje que `S-3` midio que apenas separa (C2=1,22 contra C3=1,28); (c) choca contra la leccion 8.7 — el dominio barato de `C4` es el alcance, y la fraccion leida correlaciona `+0,018` con la correccion, asi que verificaria lo que no importa. Queda **(a)**, que ya no es resignacion: el piso `ELICITED` de A2 era **inalcanzable por construccion** hasta que `P-3` lo abrio, y ahora se **gana con calibracion medida**
- [ ] **S-5** · **la calibracion exige una coincidencia de dos ajustes que nunca ocurrio** (leccion 7.14). Forzando A2 sobre el registro existente el log **si** se escribe —138 registros, cero tokens— y la calibracion sigue dando **cero proposiciones**: solo se puntua una `ELICITED` cuando hay una `OBSERVED` sobre la MISMA proposicion en la MISMA base, y lo unico que produce una `OBSERVED` sobre acoplamiento es **la sonda**. Hace falta **una corrida en A2 con la sonda encendida** — la primera que produciria un par puntuable. Es la condicion de (a) y nadie la habia escrito
- [x] **S-2** · resuelto: **no era el piso**. Era que el prompt y el verificador no pedían lo mismo

**Catálogo — la misma vara que a los candidatos nuevos**
- [x] **K-7** · **`map_reduce` a `standby` por decisión del autor (2026-08-28): no se le gasta más cuota de medición.** La evidencia acompaña: gana **una** celda de 33 en las que compite, la aritmética lo poda en **180 de 270** filas —así que la mayor parte de lo que se pagaría ya se sabe que no va a correr— y en `P20` su reducción fue **0,0%**, porque su fan-out lo fija el código y no tiene nada que ahorrar donde el resto ahorra. Su dato histórico se replaya igual
- [x] **K-9** · **`supervisor` entra al catalogo: el tercero de la familia de sub-agentes, y
  el que faltaba** (`app/paradigms/supervisor.py`, P28a-d registradas antes de correr). El
  catalogo tenia los dos extremos —plan fijo con replan (`dag_strategy`) y particion fija
  (`handoff`)— y no el del medio, que es justo lo que hoy se llama «subagentes»: un
  orquestador que despacha de a uno **segun lo que vaya encontrando**. Las llamadas NO estan
  decididas de antemano, y eso es otro grafo de control, no otro prompt.
  **Y el sub-agente recibe UN PEDAZO de contexto** (correccion del autor): con la superficie
  completa esto era `react` con mas pasos y una llamada de coordinacion de mas. El alcance
  lo recorta el **codigo** —una busqueda sobre la sub-pregunta, `SUB_SCOPE_UNITS = 8`— y no
  el modelo enumerando ids: si el modelo dibujara la frontera del sub-agente, ahi si se
  cruzaria el invariante. El recorte es de la VISTA, asi que no puede leer afuera porque las
  unidades no estan.
  **Dos defectos que aparecieron al construirlo**: (a) le puse la cota de factibilidad de
  «ve el contenido entero» y quedaba admisible en **6 de 78** tareas —un veredicto sobre una
  cota mal elegida, no sobre el patron—; corre `_run_tool_loop` como `react`, asi que su
  gasto es una DECISION y va en `WORST_CASE_ONLY`. (b) `_sub_surface` de `handoff` **no
  propagaba** `terse_tools`, `offer_board`, `demand_obligations` ni `shared_state`: esos
  factores no existian adentro de un sub-agente. Ahora es `ToolSurface.scoped()`, en la
  clase, donde `replace` los lleva todos — un olvido de campo en una copia a mano es
  invisible
- [x] **K-8** · **`handoff` entra al catálogo como candidato nuevo**, con predicción registrada antes de correr como todos
- [x] K-3 · **la falsación de `graph_traverse` (P10a) sobrevive a su objeción más seria**: el índice está 100% anclado en el texto y las dos cadenas C3 están conectadas — la travesía tenía las aristas y aun así dio u=0,000. Riesgo de diseño registrado aparte: el índice **no exige** anclaje, así que otro corpus podría envenenarlo en silencio
- [x] **K-5** · `graph_traverse` **en `standby`**, no retirado, con sus dos condiciones de revival escritas en el ejecutable: (a) un corpus con resolucion de entidades real y (b) un indice con la disciplina de la sonda. La falsacion vale «donde resolver entidades es gratis», que no es lo mismo que «vale»
- [x] **K-6** · **hecho: el corpus tiene entidades de verdad** (`corpus/generate.py`,
  `corpus/verify.py`). Variantes de superficie por persona y por firma, anafora con
  concordancia, y la referencia cruzada en forma NO canonica — medido: **36,5% de las
  menciones son invisibles a un `keyword_search` del nombre completo** y el **100% de los
  saltos de cadena C3 exige resolver una variante**. Con **guarda de ambiguedad**: una forma
  que matchea a dos personas se descarta, porque destruye la verdad derivable. El gold vive
  en `entities.json` con las menciones contadas contra el TEXTO, no contra la intencion del
  generador. Y el verificador sigue siendo independiente: resuelve **por matching contra los
  canonicos**, no regenerando las variantes —si la regla estuviera mal coincidirian en el
  error— y no lee `entities.json`, que seria el generador verificandose solo.
  **Tres defectos que aparecieron al hacerlo**, los tres silenciosos: (a) `--hard` tenia su
  PROPIO constructor de documentos y seguia escribiendo el nombre completo, asi que todos
  los corpus reales —que van con `--hard`— habrian verificado 100%, declarado entidades y no
  medido nada; lo atrapo la guarda de correferencia nueva y la linea quedo en un solo
  helper. (b) El enumerador de nombres era degenerado en los dos sentidos —rotando el nombre
  las 22 primeras comparten apellido, rotando el apellido las 54 primeras se llaman todas
  «Marta»—; ahora varian los dos. (c) El pool de 18 apellidos no alcanzaba: con 40 personas
  **ninguna** admitia apellido pelado, la variante mas dificil. Ampliado a 54
- [x] **K-4** · **el catálogo vive en el ejecutable**: `CATALOG` con cinco estados —activo, retirado, standby, infactible, en revisión— cada uno con su **razón** y su **condición de revival**. `pointer_chase` y `graph_traverse` dejan de estar disponibles; el rechazo trae el porqué en vez de mandar a buscarlo a un documento
- [x] **K-1** · `plan_execute` **retirado** por decision del autor (2026-08-28). Vive en el `CATALOG` con estado `retired`, su razon y su condicion de revival, y `RETIRED` se deriva de ahi — no hay lista paralela que pueda driftear
- [x] K-2 · `map_reduce` **no** está dominado — gana una celda. Reemplazarlo por handoff cambiaría cobertura medida por un brazo sin medir: van **uno contra otro**, no uno en lugar del otro

**Mediciones**
- [ ] M-1 · brazo en PROSA (E1) — implementado, sin correr
- [x] **M-2** · **instrumentada, y el hallazgo es por qué faltaba** (lección 6.4). La retención —si la evidencia leída **sobrevive** hasta la llamada que responde— ya se registra por fila como ratio de caracteres. `basic` da **1,000** y `managed` **0,281**. Y en `basic` es 1,0 **por construcción** —no hay compactación— que es la variante de **todos** los estudios medidos: la medida no faltaba por descuido, **no tenía nada que decir donde se midió**. Medirla de verdad exige correr en `managed`/`cognitive`
- [ ] **M-3** · transferencia de θ entre familias de modelos — **y ahora está acotado qué se rompería** (`MODELO_Y_CONSTANTES.es.md`): los **mecanismos** son independientes del modelo por construcción; las **magnitudes** no. El 33% evitable **se encoge** con un modelo que para solo; el barrido de λ **se corre entero** y el orden de los brazos puede darse vuelta; las asociaciones de orden pueden desvanecerse por **falta de varianza de secuencia**, que no es lo mismo que falta de señal
- [~] **M-4** · **la mitad esta hecha: la segunda familia existe y esta medida.** `luna` y
  `terra` responden con herramientas (smoke 2026-08-29) y entran a la corrida homogenea —
  `terra` solo donde `nano` no alcanza (C3), por decision del autor. Lo que sigue abierto es
  el **corpus natural**: todo lo medido corre sobre mundos generados, y ninguna medida dice
  que un corpus real se comporte igual. Es la mitad cara y la unica que sigue siendo `M-4`
- [ ] M-5 · C3 profundo en nano

**El catálogo confunde dimensiones ortogonales**
- [x] **F-1** · `Blackboard` extraído a `paradigms/blackboard.py` — comportamiento idéntico, suites en verde; **F-2 ya es formulable**
- [x] **F-2** · **el board es una TOOL disponible para todos** (`offer_board`, §50, lección 5.17 — corrección del autor). Había escrito que el cruce **no se podía construir**: que en `react` el board era redundante con la transcripción y que en `map_reduce` sería otro patrón. **Las dos mitades estaban mal.** El registro desmiente la primera —el texto leído sobrevive al **28%**, así que el board es **durabilidad** y no repetición— y la segunda sólo valía para un board estructural. Quedan **dos factores separados**: `shared_state` (el board estructural de dag, escrito por el código) y `offer_board` (la tool, cruzable contra todos). **Un solo board por celda**: dag y la tool comparten el objeto
- [ ] **F-2b** · **correr `{offer_board, sin} × {patrones}`**, que es el cruce que ahora sí existe. La predicción que lo hace valer la pena está a mano y no registrada todavía: si el board compra algo, tiene que comprarlo **donde la retención cae** —presupuesto ajustado, muchas unidades— y **no** donde todo entra en ventana. Un board que ayuda parejo mediría otra cosa
- [x] **F-3** · **HyDE entra como factor de pre-proceso**, que es lo que se había decidido: `hybrid_hyde` es un brazo de recuperación cruzado contra los patrones, no un paso plegado adentro de ninguno
- [x] **H-1** · **portado como rama paralela fusionada por RRF** (`HydeFused`, §49). **Brazo y no herramienta**: una herramienta la llama el modelo, y eso pone flujo de control del lado del sensor. **Fusionado y no reemplazando**: una hipotética puede estar bien imaginada y ser falsa, y RRF hace que ese error tenga que **vencer** al ranking base en vez de sustituirlo. Una generación por consulta **distinta**, local a la celda — compartida, la primera tarea subsidiaría a todas
- [x] **H-2** · **expuesto como brazo `hybrid_hyde`**, construido **por celda** con el cliente de esa celda. `hybrid_reranked` **nunca se construía** —`build_arms(embedder=…)` sin cliente— así que el brazo que ya existía era inalcanzable: la misma forma del barrido 7.17. Y el sufijo del archivo separa por brazo, con guarda de mezcla en `load_rows` para el único caso que queda (concatenar a mano), porque **la huella y el vocabulario coinciden entre brazos**
- [~] **H-3** · **el cobro está arreglado, falta la corrida** (P26a-d). El defecto era peor que «sin λ»: la fila cobraba `result.usage` —lo que el paradigma se acordó de sumar— y la generación de HyDE **no aparece ahí por construcción**, porque el paradigma nunca la vio. Se comparaba una recuperación **gratis** contra una **paga**. Ahora cobra el **medidor de la celda**, con `retrieval_tokens` aparte y una guarda que levanta si el paradigma declara más que el medidor. Y algo que ya fallaba callado: **la ruta de error ya usaba el medidor**, así que una celda que crasheaba se cobraba bien y una que andaba se cobraba de menos
- [x] **F-4** · **escrito**: `PATRON_O_FACTOR.es.md`. La prueba es una — un patron se distingue por su ESTRUCTURA DE CONTROL DE FLUJO, y se decide con cuatro preguntas (cuantas llamadas y quien las decide; quien elige la proxima accion; si hay estado compartido y quien lo escribe; si un paso puede cambiar el plan). Contraprueba: si la diferencia se describe sin dibujar otro grafo de control, no es un patron. Incluye la clasificacion de todo lo que hay hoy y los tres factores que siguen **soldados adentro de un brazo**, que es lo que impide atribuirles nada

**Consistencia entre patrones — auditoria del 2026-08-29 (`historico/AUDITORIA-PATRONES-2026-08-29.es.md`)**

> Pedido del autor: que los trece manejen igual el estado, llamen a las mismas tools,
> tengan el mismo retrieval y el blackboard a disposicion. **Dos ejes se sostienen y
> cuatro son deuda**, y ninguno de los cuatro cambia un numero publicado — cambian **que
> se puede promediar**, que es peor de descubrir tarde. Lo que SI se sostiene:
> `surface_for` no recibe el nombre del paradigma, asi que el menu de tools es identico
> por construccion y no por convencion; y la dispersion del USO es la variable dependiente
> del banco, no una falta de uniformidad.

- [x] **C-1** · **hecho: son dos lecturas y se cuentan aparte** (`tools.py`,
  `test_science.py` §54). `read_one` ahora deja rastro en `units_read_structural`, y
  `usage()` reporta ademas `units_read_any` y `relevant_units_read_any`. **No se sumo a
  `units_read` a proposito**: sumarlo moveria todo numero publicado y, peor, borraria la
  distincion que el pendiente existia para preservar — `units_read` sigue significando «lo
  que el modelo eligio leer». La union **no es la suma**: una unidad leida por codigo y
  despues por tool se cuenta una vez, y el test lo fija. Y un desvio que se atajo en el
  camino: el bloque cayo primero adentro de `_coverage()`, que es lo que el MODELO lee —
  ahi habria cambiado el prompt y con eso cualquier comparacion contra el registro
- [x] **C-2** · **hecho: `arm_dose` es una sola definicion** (`app/metrics.py`,
  `test_science.py` §54), cableada al analizador de P26. Vive en el codigo y no en cada
  analizador porque recomputada en tres lugares serian tres definiciones, y la primera vez
  que una difiera **nadie se entera**: las tres imprimen un numero plausible. Devuelve
  **`None` y no 0,0** cuando el paradigma no busco nunca — un `gist_reader` no recibio
  tratamiento cero, no recibio tratamiento, y meterlo al promedio como caso tratado que no
  respondio es justo la lectura equivocada. Medido sobre P26: `react` **73,3%**,
  `rewoo` 58,0%, `dag_strategy` **12,6%**, `gist_reader` N/A
- [x] **C-3** · **la tool de board ya llega al modelo, y el defecto era peor que el default
  apagado.** `_run_tool_loop` —el UNICO sitio del repo que manda `tools`— llamaba a
  `specs_for` **sin pasar `terse` ni `offer_board`**, asi que `offer_board=True` habria
  corrido entero y medido CERO: la tool jamas aparecia en la lista que el modelo ve, y
  `F-2b` habria concluido «el board no compra nada» por cableado. Los dos factores tenian
  test sobre `specs_for` y **ninguno sobre el camino**, que es como un factor pasa de estar
  implementado a estar ejecutado (`test_science.py` §56). `terse_tools` verificado sobre lo
  que el modelo REALMENTE recibe: 2.135 → 1.315 chars, **−38,4%**, que coincide con lo que
  `X-4c` habia medido sobre la spec. Correrlo sigue siendo `F-2b`
- [ ] **C-4** · **la comparacion de memoria/olvido no esta implicada en ningun resultado:
  43 filas de 3.679 (1,2%)** — `basic` 3.053, `cognitive` 27, `managed` 16. Y un limite
  estructural que acota el enunciado: la compactacion vive en `_run_tool_loop`, asi que
  **solo alcanza a los CINCO patrones que llevan historia** (`react`, `map_reduce`,
  `reflection`, `dag_strategy`, `handoff`); los otros ocho no reenvian historia y no tienen
  nada que olvidar. La corrida es `{basic, managed} × {los cinco}`, y el resultado se
  enuncia acotado a esos cinco. Confirma `M-2` con el conteo: `react` da retencion 1,000
  **por construccion** en la variante de todos los estudios

**«Anti-RAG» — la máquina existe (REC), le falta una pieza**
- [x] **AR-0** · **el retriever ya es factor y ahora está guardado**: archivo propio por brazo, `Row.retriever` estampado, y guarda de mezcla en la lectura. Lo que faltaba no era la estructura sino que **nada impidiera promediar dos brazos** — y esa es la única guarda posible ahí, porque huella y vocabulario no los distinguen
- [x] **AR-1** · contratos de completitud — **implementado y cableado**: `C-COMPLETE` corre sobre la respuesta con el dominio declarado por el caller, y cada fila guarda su veredicto aparte de la utilidad. Su limite quedo escrito donde vive: a nivel prosa **no puede ver lo que sobra** —solo busca las claves declaradas— y detectarlo exigiria extraer entidades del texto, que es justo lo que no se acepta como sensor
- [x] **AR-2** · **cableado, y con una asimetria que lo hace mas que un cable.** `rec.diagnose` **busca** —prueba intervenciones hasta dar con la mas barata que cambie la decision— porque el registro no dice que falto. Un contrato rechazado **ya lo dice**: `C-COMPLETE` nombra las claves ausentes, `C-NUM` la ranura bajo el piso. Buscar donde ya hay respuesta no es redundante, es **peor**: la busqueda esta acotada a un esquema chico, asi que un deficit real fuera del esquema daria «no hay intervencion que lo cambie» cuando la hay. `deficit_from_contract` lo declara con `searched: False`. `test_science.py` §36
- [~] **AR-3** · **P26a-d registradas antes de existir una fila**. La que importa es **P26d**: el orden de los paradigmas **no cambia** con el brazo de recuperación. Si cambiara, «el mejor paradigma» sería en parte un artefacto de la calidad de búsqueda, y **se caería toda comparación entre brazos hecha hasta hoy**
- [~] **AR-4** · **baseline honesto: es P26d.** Toda comparación de paradigmas de este banco corrió bajo **un solo** brazo de recuperación. Predecir que el orden no cambia es predecir que los resultados existentes sobreviven — y es la predicción que más dolería perder. Falta correrla

**El agujero aguas arriba de todo**
- [x] **G-1** · **la ingesta se mide: `ingest_tokens` es una columna de la fila**, aparte de
  `cost_tokens`, mas `ingest_calls` y `ingest_units_read` en el `Ingested`. Con eso su
  economia deja de estar mezclada con la de responder: se amortiza sobre todas las consultas
  futuras y antes caia entera sobre una fila arbitraria. Lo que sigue sin medirse es su
  MAGNITUD, y eso ya no es instrumentacion sino una corrida
- [x] **G-3** · **medido, y la preocupacion quedo refutada por el registro.** El mecanismo es real —`graph_traverse` construye y persiste su indice adentro del request, leyendo cada unidad con la llamada que REGISTRA lecturas, asi que la fila que lo paga carga `fraction_read` del corpus entero—. Pero **ninguna fila del registro lo ejercio**: las 6 filas del brazo tienen `fraction_read = 0,000` y costo 188-268 tokens porque el indice ya estaba en disco. La leccion 8.6 da `-0,241` con todas y `-0,242` sin el brazo. Nada que corregir; queda la regla `G-4`
- [x] **G-4** · **hecho, y con la mitad que la regla original tenia mal.** La ingesta es una
  etapa (`app/ingest.py`) y el paradigma la CONSUME. Pero el defecto no era QUE se
  construyera adentro del request, era **QUIEN lo pagaba**: un paradigma que no puede
  construir su indice deja de ser medible, asi que el fallback al vuelo existe (decision del
  autor, 2026-08-29) y su gasto va a `ToolSurface.ingest_tokens`, que el runner **descuenta**
  de `cost_tokens` — en la ruta de exito **y en la de error**, porque esa asimetria ya costo
  una vez (`H-3`). Se mide contra el medidor de la celda y no contra los tokens del indice:
  uno servido del cache no gasto nada ahora, y cobrarlo inventaria gasto
- → **G-2** se mudó a `PRODUCTO.es.md` (2026-08-29). No está cerrado: va en otro momento.

**Ontología de la pregunta** (`ONTOLOGIA_PREGUNTAS.es.md`, pizarra)
- [x] **O-1** · **cerrado: medido, y el trabajo que abrió ya se hizo.** La supersesión estaba en el material y **ninguna pregunta la interrogaba** — 5 cuentas enmendadas, 0 preguntas sobre domicilio, 0 golds en un valor vigente: las enmiendas eran **sólo distractor**, costaban tokens y no medían nada. De ahí salió `C8`, y `P18` la corrió: **el 100% de los errores son el valor superado**, no una dispersión de ciudades
- [x] **O-1b** · **celda C8 implementada y verificada 6/6**, reusando las enmiendas de C5: **+32 tareas, +0 documentos**. Separa falla de recuperación de falla de **vigencia**, que ninguna otra celda distingue
- [x] **O-1c** · **P18 corrida** (78 filas de C8, `p18_verdict.json`). **P18a REFUTADA**: leer mas NO resuelve la supersesion (brecha +0,071 contra criterio 0,25) — y O-4a despues mostro que no era de C8, es general. **P18b CONFIRMADA**: el 100% de los errores son el valor SUPERADO, no una dispersion de ciudades. **P18c CONFIRMADA**: C8 no se predice desde C5 (r=+0,114 sobre 26 pares) — detectar un conflicto y resolverlo son capacidades distintas
- [~] **O-2** · **`C-ABSENCE` implementado, con celda y verificador** (§45, P25a-d). La asimetria es la regla entera: **presencia con UN testigo, ausencia con el DOMINIO ENTERO**. La polaridad la declara el agente en un enum de dos valores y la regex se **construye desde el vocabulario**, asi que no hay dos listas que se desincronicen; **no declarada es `None`, jamas `present`** — el benigno no puede ser el default. La celda `B2` usa `ABSENT_ROLES`: la primera version buscaba un rol libre en alcance y **desaparecia a width 40**, o sea que existia solo en el regimen chico, que es donde la falla importa menos. Falta **correr**
- [~] **O-3** · **`C-PRESUPPOSITION` implementado, con celda y verificador** (§45). Era el mas facil porque una presuposicion **ya tiene forma de proposicion**: faltaba extraerla, y extraerla es el patron del handoff — el agente PROPONE tipado (`ELICITED`) y el codigo AUTORIZA por presencia literal (`COMPUTED`), sin heredar la procedencia del que la pidio. **No se emite ni un «no se»**: declinar el dato ratifica la premisa igual que darlo. Falta **correr**
- [x] **O-4** · **MEDIDO, y dos de tres predicciones cayeron** (`_analyze_demands.py` + `_analyze_demands2.py`, 1.214 filas de 5 corpus). La cardinalidad **no implica** la cobertura: C5 y C8 son singulares y exigen lectura total, asi que el tipo es el par `(answer_cardinality, coverage_demanded)`, declarado por celda en `REQUEST_DEMANDS` con vocabulario cerrado. **(a)** Leer mas ayuda donde la cobertura NO se exige (`+0,259` contra `+0,018`, `p=0,028` controlado dentro de tarea) — **la exhaustividad no se compra leyendo mas**. **(b)** Ninguno de los dos ejes reordena el ranking de paradigmas mas que su propio null (`p=1,000` / `p=0,447`). **(c)** Pero **5 de 22 regiones mezclan** clases de cobertura: es informacion que la region no tiene
- [x] **O-5** · **enumerados, que era lo que pedía** (`ONTOLOGIA_PREGUNTAS.es.md`): B3 entidades, C1 conversación, A2 precisión, D2 subjetividad — cuatro ejes bloqueados **por el generador y no por el diseño**, listados *antes* de pagar el cuarto caso. Desbloquearlos **no es este pendiente**: vive en `K-6` (entidades) y `M-4` (corpus independiente). Dejarlo abierto acá contaba el mismo trabajo dos veces

**La fase de entendimiento — la mitad que S-3 declaró faltante**
- [x] **U-1** · **tipado y declarado** (`REQUEST_DEMANDS` en `corpus/generate.py`, campos `answer_cardinality` / `coverage_demanded` en `Task`, falla cerrado si una celda no declara). Son DOS ejes, no uno, y el corpus tenia el contraejemplo adentro
- [x] **U-2** · **cerrada con la decisión que faltaba, que era de producto** (§51, lección 5.13). Tres intentos: regla de `GATE` —mataba a C2 entera—, precondición estructural —correcta y **doblemente inerte**, la cerré como hecha—, y ahora: cuando ninguna topología admisible recorre el alcance, **el dial decide**. A0/A1 siguen y lo registran; **A2/A3 se ABSTIENEN**, porque a ese nivel lo que se afirma hay que poder defenderlo. Abstenerse **es el producto**. Y el corpus `gold_guards` la despierta: 12 tareas, verificado en el test contra el corpus real y no contra un mundo fabricado
- [x] **P-15** · **celda `W1_shared_writes`**, con verificador y las dos polaridades. `shared_writes` sostiene el piso A2 y **ninguna tarea de 407 lo declaraba**: el nivel contable nunca se alcanzó por esa vía. Distinta de `C7` a propósito — aquélla es **irreversible** (A3), ésta es **reversible y concurrente** (A2), y confundirlas borraría el escalón del medio
- [x] **P-17** · **`budget_usd` declarado por tarea**, derivado del presupuesto de tokens al arancel de referencia. Derivado y no independiente **a propósito**: un despliegue tiene UN presupuesto y lo expresa en la unidad que le cobran. Lo que agrega es la cota que los tokens no pueden expresar — **el modelo**: un presupuesto dimensionado para el barato no alcanza para el caro, y eso es invisible contando tokens porque los dos gastan los mismos
- [x] **P-18** · **`gold_guards` despierta las siete guardas** (`_audit_inerte.py`): de 4 disparadores que **nunca dispararon** en 407 tareas, hoy los siete disparan. 38 tareas, verificadas, cero llamadas al modelo
- [~] **X-5i** · **no se puede medir con el registro actual: cero de 2.554 filas tienen veredicto de contrato.** `verify_coverage` exige `domain_keys` y `gold_p18` no tiene celdas con dominio declarado. Depende de la **corrida B** (`gold_guards`, que sí trae C9, B2 y D1). El mecanismo —«un contrato que se niega es una falla detectada sin oráculo»— sigue en pie y sin número
- [x] **X-5j** · **el modelo caro YA estaba desplegado** (verificado con `az` en la suscripción VS Enterprise, no la de trabajo). `foundryopencode` —el mismo recurso que nano, o sea **mismo endpoint y misma key**— tiene `gpt-5.6-sol` (1000 TPM) y `gpt-5.6-terra` (500 de 1000). `gpt-5.6-luna` está **disponible y sin desplegar**, con 1000 TPM libres. Cableado: `Settings.model_deployments` + `ModelPool` (§52) + `serve` planifica con el barato y **ejecuta con el que el plan eligió**. Falta sólo el deployment de luna, que el clasificador de permisos bloqueó
- [x] **X-5k** · **`luna` esta desplegado y responde: medido, no supuesto** (smoke del
  2026-08-29, una llamada real por modelo con un prompt que OBLIGA a usar la tool). `nano`,
  `luna` y `terra` **corren los tres con herramientas**; `luna` razona por defecto (5 tokens
  de razonamiento) y `terra` 0 en ese prompt. `reasoning_effort` explicito junto con tools:
  `nano` **acepta**, `luna` y `terra` dan **HTTP 400** con el mensaje del proveedor.
  Y esto cierra ademas un rotulo que `config/tariffs.json` traia escrito: decia que `luna` y
  `sol` "se declaran por familia y NO estan medidos individualmente". `luna` ya lo esta;
  `sol` sigue sin medir y esta fuera del catalogo por defecto
- [x] **L-1** · **la latencia estaba en 2.369 filas y nadie la leía** (`_analyze_latency.py`, lección 5.19; planteo del autor). `dag_strategy` tiene la utilidad más alta y es **11,5× más lento** que `rewoo`, que queda a **0,030**. Con los 35× de tokens ya sabidos: tres centésimas contra un orden de magnitud en tiempo **y** en plata. Y no es función del costo — `map_reduce` es el más barato **por llamada** (2,00 s) y el cuarto más lento **por celda**, porque hace 9,9
- [x] **L-2** · **el TTFT venía en la respuesta todo el tiempo** (lección 5.20). Escribí que no se podía medir sin streaming y sin reescribir el cliente. Azure lo devuelve en `usage.latency_checkpoint` — **400 de 400** entradas de caché lo traen— y como el caché guarda el **cuerpo completo**, el registro entero se rellena **sin gastar un token**. Se toma `user_visible_ttft_ms`: `engine_ttft_ms` da 22 ms donde el visible da 356, un factor **16**, y sería reportar una latencia que nadie experimenta
- [x] **E-1** · **el motor emite sus acciones de razonamiento con `yield`** (`app/events.py`, `_answer_stream`, lección 5.23; idea del autor). El proveedor **esconde** el razonamiento del modelo; el de MAPO —poda, creencias tipadas, dial, contratos— se emite entero, **antes de que exista un token** y sin gastar ninguno. Vocabulario cerrado de 14 tipos, y tres reglas de orden verificadas: un terminal, nada después, y **`decision` antes que cualquier `token`** — un stream que invierte eso desmiente el producto en pantalla. `_answer()` **consume** el stream: una sola implementación
- [x] **E-2** · **`handoff` no tenía aritmética de factibilidad** y estaba en el `REGISTRY`: el endpoint del producto reventaba con cualquier request. Nunca se notó porque nada fuera del banco recorre el catálogo entero. La cota sale de la forma del patrón —alcances × vueltas, las dos fijadas por código— y **no se compara contra el material entero**: un agente ve sólo su alcance, y compararlo contra el total lo declararía infactible justo donde el reparto lo hace posible
- → **E-3** se mudó a `PRODUCTO.es.md` (2026-08-29). No está cerrado: va en otro momento.
- [x] **L-4** · **registro rellenado, 2154 de 2154 llamadas del caché** (lección 8.10). `reasoning_tokens` y TTFT presentes en **480/480** filas de nano y 48/48 de terra, sin gastar un token. Tres guardas que le faltaban, cada una descubierta rompiendo algo: **borraba antes de saber si iba a funcionar** (402 filas de nano desaparecieron cuando una guarda cortó la corrida después del `unlink`; ahora restaura ante `BaseException`), **la regla de standby impedía el replay** —y su propio mensaje decía «su dato histórico se replaya igual»—, y **toleraba «unas pocas» llamadas reales** en vez de exactamente las celdas que habían fallado por infra
- [x] **P27** · **el modelo caro gana 0,48 y no se paga** (lección 5.24). `terra` **+0,4833** sobre nano en las 8 tareas que discriminan, gana 10 de 16 celdas, y a **+USD 0,0717/celda** necesitaría 0,54 para pagarse: **P27c confirmada, pierde por poco**. **P27b refutada** y era la que tenía mecanismo: la ganancia es **plana** (+0,5000 en piso contra +0,4778 en margen), o sea **nivel y no capacidad selectiva** — y si gana parejo **no hay nada que la región pueda aprender**. **P27d refutada**: tokens y plata coinciden. Y sin predecir: el caro tiene **TTFT más bajo** (318 vs 346 ms) **emitiendo 490 tokens de razonamiento por celda**
- [x] **P27e** · **la ventaja del caro depende del PARADIGMA, no de la tarea** (`_analyze_p27e.py`, lección 5.25). Barridos todos los ejes del registro, sólo el paradigma supera la variabilidad interna (dispersión **+0,7843** contra sd 0,5046): **`react` +0,8755** y **`rewoo` +0,0912**. El caro le compra casi un punto a uno y nada al otro. Eso **rescata `X-5b` por una razón distinta de la que di**: el par es la acción no porque el modelo se elija, sino porque **su efecto vive en la interacción** — elegir modelo mirando la tarea no compra nada, elegirlo junto con el paradigma compra 0,88
- [ ] **P27f** · **separar las dos explicaciones de por qué `rewoo` no gana.** Hipótesis A: el modelo ayuda donde hay **más decisiones por celda** (`react` 3,3 llamadas contra 2,0). Hipótesis B: el techo de `rewoo` es **estructural** — si su plan inicial no alcanza, ningún modelo lo salva dentro de esa topología. B predice que la ganancia sea chica **también** donde el plan sí alcanzaba, y con 16 celdas no se separan. Es una corrida chica y bien dirigida, no una campaña
- [x] **P27g** · **dos políticas a dos granularidades** (`_analyze_p27g.py`, lección 5.26), contado sobre 2.494 episodios sin gastar un token. El paradigma se aprende en `región × paradigma` —la región **sí** explica cuál conviene— y el modelo en `modelo × paradigma`, que es donde `P27e` midió que vive el efecto: **13 bins, 77% sobre el piso, 100% de episodios visibles**. Partir por región para elegir modelo pagaría la multiplicación de bins sin comprar discriminación. Y un aviso que quedó en el analizador: `región × modelo × paradigma` parece costar sólo **+6 bins** y eso **engaña** — `terra` cubre 5 de 24 regiones; con la grilla balanceada **se duplican**, que es P15 intacto
- [x] **P27h** · **la segunda política, implementada y consumida** (`model_stats`, `best_model`, §54). Va **adentro del payload firmado** —editarla invalida la firma— con **versión separada**: revertir una no obliga a revertir la otra, o son una sola política con dos nombres. Indexada `paradigma → modelo` y **no** por región, porque ahí no está el efecto. El router la consume **después** del dial y del presupuesto: un aprendizaje que pudiera levantar una precondición no sería una preferencia, sería una manera de evadirla. Y cuando θ opina y **no se puede seguir**, se registra — distinto de no haber opinado, y sin eso nadie ve que lo aprendido no gobierna nada
- [x] **P27i** · **la consolidación alimenta `model_stats`.** `Episode` lleva `model` —en el episodio y no derivado del archivo: si saliera de la carpeta, mover un archivo cambiaría lo que θ aprendió—. Se acumula sobre el **mismo conjunto de ajuste** que θ y no sobre todos: alimentarla con el bloque final haría que la guarda validara al candidato con datos que ya vio, que es el defecto que la etapa 1 arregló para la primera política. Un episodio **sin modelo no entra** ni crea un bin vacío — sería un tercer modelo fantasma compitiendo con los reales— y si **ninguno** declara modelo se dice, para que la segunda política no parezca viva sin haber recibido nada
- [x] **L-3** · **la latencia es una COTA DURA, no un tercer eje de λ** (`config/latency.json`, `projected_seconds`). λ expresa una **preferencia** —cuánta calidad vale una unidad de costo— y el tiempo casi nunca es eso: un request con alguien esperando tiene un **techo**. Un brazo que gana 0,030 y tarda 11,5× no es «caro», es inservible para quien espera. Va con la ventana y la plata. Por **llamada** y no por celda, porque el componente fijo es por llamada y los paradigmas se diferencian en cuántas hacen. Y el `default` es el **peor** medido, no el promedio: suponer el promedio admitiría en presupuestos donde el peor no entra, y **una cota que admite de más no es cota**
- [x] **X-5l** · **precios reales en `config/tariffs.json`** (pedido del autor: datos, no código), **verificados dos veces** (lección 5.21): API de Azure y la página del autor coinciden exacto. `nano` **0,20/1,25** —mi referencia erraba **4×** en entrada—, `luna` **0,20/1,20**, `terra` 2/12, `sol` 5/30. **`luna` NO es el caro: es clase nano.** Y `X-5a` sobrevive porque se enunció sobre lo **invariante al arancel**, con el barrido de ×1 a ×32 que cubre el ~6× real
- [x] **X-5o** · **las ventanas estaban MAL, las dos** (lección 5.22). Tenía 400.000 para ambos: es la **total** de nano y ni siquiera la de terra. `check_pair` compara contra tokens de **prompt**, así que lo correcto es la ventana de **entrada** — **272.000** para nano y **922.000** para los `5.6`. Usar la total admitiría planes que no entran, porque la salida ocupa 128.000
- [x] **X-5m** · **sí tiene sentido nano, y no por el precio** (lección 5.22, pregunta del autor). De tres razones que se me ocurrieron, **dos se cayeron al medirlas**: el contexto largo no aplica (**0 de 648 llamadas** superan 272k) y la escritura de caché es casi moot. La que decide es de **capacidad**: los `5.6` son modelos de razonamiento y **no soportan Chat Completions + tools a la vez** salvo con `reasoning_effort='none'`. Los trece paradigmas son bucles de herramientas sobre Chat Completions. Y una cuarta que el «mismo precio» esconde: **los tokens de razonamiento se facturan como salida**
- [x] **X-5p** · **NO hay bloqueante — me equivoqué dos veces** (lección 7.19, corrección del autor). Medido con un prompt difícil: `terra` corre con herramientas **y razonando** al default (66 tokens). Lo que rechaza es el **nivel explícito** junto con tools. Mis dos conclusiones previas salieron de leer documentación sin ejecutar, y después de una prueba con prompt **trivial que no podía fallar**. El pool ya no se niega: **registra** que en ese modelo el esfuerzo —y parte del costo— lo decide el modelo y no la configuración
- [x] **X-5q** · **los tokens de razonamiento se facturan como SALIDA, y están medidos**: `terra` emite ~66-70 en un prompt difícil, `nano` **cero**. Así que «mismo precio por token» **compara dos unidades distintas**, y del lado del `5.6` parte del gasto la decide el modelo. El registro todavía no los separa (`completion_tokens` los mete juntos): eso es `X-5r`
- [x] **X-5r** · **`reasoning_tokens` capturado**, de `completion_tokens_details`. Ahora el registro separa lo que el modelo decidió gastar **pensando** de lo que gastó **respondiendo** — y en un `5.6` esa fracción no la controla nadie de este lado
- [ ] **X-5s** · **`reasoning_effort` como FACTOR, y ahora esta MEDIDO que solo se puede en
  `nano`** (leccion 7.19, verificado individualmente el 2026-08-29). Antes era una
  declaracion por familia; ahora hay una llamada por modelo: `nano` acepta el nivel
  explicito junto con tools (`low` → 7 tokens de razonamiento), `luna` y `terra` dan **HTTP
  400**. Es un eje del MODELO que no es paradigma ni fraseo, asi que entra cruzado
  `{none, low, medium, high} × {patrones}` **solo en nano** — y la prediccion a registrar
  antes de correr es que el razonamiento paga donde la cadena es larga (C3, C5) y **no**
  donde la tarea es de extraccion (C1, C2)
- [x] **X-5n** · **el escalón de contexto largo está modelado** (`Model.money_for`, `config/tariffs.json`). Es un **acantilado y no una pendiente**: por encima de 272k de entrada, los `5.6` cobran la tarifa larga por el **request entero**, no marginalmente. Modelarlo como pendiente sub-proyectaría **justo en el borde**, que es donde una cota de admisión decide. Medido: `deep` salta **2,44×** al cruzar el umbral y `nano` sólo crece proporcional (1,31×) porque no tiene escalón. Los otros dos ejes —caché y escritura— siguen documentados y sin consumidor, y **por eso no se declaran**
- [x] **P-16** · **hecho: `bench/_estimate.py`** (`test_science.py` §55). El conteo de
  celdas sale de `tasks.json` y pasarle un `.jsonl` de resultados **levanta** — devolver un
  numero plausible es peor que romper, y es el modo de falla que costo 34x. El costo por
  celda si viene del registro, con **mediana** y no media (una celda descontrolada arrastra
  la media justo donde no hay que equivocarse), y un paradigma sin medir deja el total en
  **SIN N** en vez de heredar el promedio de otros: entre el mas caro y el mas barato del
  catalogo hay ~30x. Retrodiccion sobre P26: **23,8M contra 12,4M reales** — cota superior
  de 1,9x, contra la estimacion vieja que erraba **18x por debajo**. Una cota que sobreestima
  es lo que se le pide a una cota de gasto
- [x] **U-3** · **DESCARTADO por medicion** (O-4b): elicitar la demanda cuesta una llamada por request y el ranking de paradigmas **no se mueve** contra su propio null (`p = 1,000` / `p = 0,447`). Si alguna vez se elicita, es para `C-COMPLETE` — no para el router
- [x] **U-4** · **el disparador es tipado y sabe cuándo NO corresponde** (`verify_coverage`, `test_science.py` §38). Son **dos** condiciones y ninguna alcanza sola: la tarea exige cobertura **y** su dominio es enumerable. Exigirla sobre un dominio `semantic` haría que el contrato **reemplace** al paradigma en vez de verificarlo (lección 8.7); sobre uno `from_scope` verificaría lo que se midió que no predice corrección (`+0,018`). Y `None` significa **sin contrato**, distinto de un contrato cumplido
- [ ] **U-6** · **correr P19** — predicciones a-d registradas en `README.md` antes de existir una fila. `P19d` es el control que puede matar a la celda: con `width=4` el dominio declarado y las unidades en alcance **coinciden**, asi que si C9 se comporta igual en w=4 y w=48, la distincion entre los dos dominios no compra nada y la celda solo mide ancho. Costo **sin estimar**
- [x] **U-7** · **resuelto entero.** El dominio lo declara el **caller**, igual que `irreversible`. Y la mitad que faltaba —qué terminal es una respuesta retenida— se resolvió con la propuesta del autor: **`retained`**, un cuarto terminal que **informa lo que falta** y **propone** reintentar. Lo que lo hace útil es que el contrato **nombra** el faltante: no «algo salió mal», sino «faltó Cora». Y el reintento es **dirigido** —sabe qué pedir— y **propuesto, nunca automático**: `P20` midió que una acción que el sistema puede repetir por su cuenta deja de ser control de flujo del código. Tope **1**, fijado por el código. Agotado, propone **aceptar incompleto sabiendo que lo está**, que es justo lo que sin contrato no se podía saber
- [x] **U-5** · **sin objeto**: medirla contra λ presupone un efecto de ruteo que O-4b midio que no existe, asi que el costo de la llamada no compite contra nada. Vuelve a tener sentido cuando `C-COMPLETE` este cableado (`U-7`)

**REC — implementado, sin registrar y sin medir**
- [x] **REC-1** · **preregistradas como `P22a`–`P22f`** en `README.md`, con fecha y con **numero**. La version en prosa no era un preregistro: «no supera costo y piso de ruido» no tiene una cifra adentro, y una afirmacion sin cifra se lee despues en la direccion en que hayan ido los datos. Con dos disciplinas que este registro ya pago: baseline el router de **P17** —no el de P15, cuya seleccion nunca dispara— y toda diferencia sobre **intervalo bootstrap pareado**. `P22f` (reproducibilidad) es la mas barata y va primero: si falla, ninguna de las otras cinco significa nada
- [x] **REC-2** · **congelado ANTES, y con digest** (`bench/runs/_run_rec.py`,
  `results/nano/rec_prereg.json`). Criterio, piso de ruido **medido** (0,0655), `min_tasks`,
  fallback, politica y clausula candidata se escriben primero, se les saca un digest sin
  fecha —igual que el resto de los digests del repo— y ese digest entra al certificado. Un
  congelamiento que vive en la cabeza del que corre el script no congela nada: quien audite
  puede ver contra que criterio se decidio, no contra cual se dice que se decidio
- [x] **REC-3** · **mundo final generado y NO gastado.** Tres mundos disjuntos por
  identidad de tarea, de partir `gold_transfer` en tercios **deterministas** (8/8/10) — un
  split aleatorio haria que el mismo registro produjera veredictos distintos, y entonces el
  veredicto describiria el split. El final **no se consulto**: `validate` no supero el piso,
  asi que el `FinalLedger` no se reclamo y el held-out sigue entero. Eso es el diseno
  funcionando, no una corrida incompleta
- [x] **REC-4** · **CORRIDO, gratis, y el veredicto es NO PROMOVIDA — con contenido**
  (2026-08-29). El ciclo no llama al modelo: lee utilidades y costos ya pagados.
  **Lo que hizo falta para que el resultado significara algo.** La primera corrida dio
  beneficio **+0,0000 en los tres mundos** y eso NO era un veredicto: el paradigma después
  de reparar es el mismo `fallback`, así que `u(after) − u(fallback)` es cero **por
  construcción**. Lo que una cláusula de adquisición compra no es utilidad, es **no
  sondear** — y con una métrica de utilidad pura **ninguna cláusula de esta clase se
  promovería jamás**, no porque no valgan sino porque se las medía en el eje equivocado.
  `_benefit_on` pasó a **brecha neta**, con la convención del banco (λ sobre razón de costo
  contra el más barato, no tokens absolutos) y con `lambda_cost = 0` reproduciendo exacto lo
  anterior.
  **El veredicto, con λ congelado ANTES del barrido (0,05)**: beneficio validate **+0,0311**
  contra un piso de ruido **0,0655**. No supera. El barrido dice a qué precio empezaría a
  valer: **λ=0,20**. El mundo final **no se gastó** — `validate` no pasó, el `FinalLedger`
  no se reclamó y el held-out sigue entero.
  **Y un error propio, atajado antes de publicarlo.** Usé los «83k tokens» de `P17b` como
  costo de UNA sonda, y `P17b` dice «**0 de 14**: la sonda corrió, costó 83k tokens» — es el
  TOTAL sobre 14 tareas. El por-tarea son **5.928**, y con los 83k el beneficio salía
  inflado **14×** y la cláusula se promovía. Un agregado leído como un por-unidad: la forma
  exacta de error que `_sanity.py` existe para atajar
- [x] **REC-0** · **desbloqueado: P17 cerró.** El diagnóstico era correcto —«router P15 congelado» es un router cuya selección **nunca dispara**, así que servía de baseline sólo para medir la cascada— y la condición que ponía ya se cumple: el baseline de REC es el de P17, con detectores honestos y cascada 2/26. **REC deja de estar bloqueado**; lo que queda de REC es correrlo (`REC-4`)

**Producto — capa de decisión**
- [x] **P-1** · **la sonda sensa RECUPERABILIDAD** (`ProbeResult.retrievable`). No es lo mismo que acoplamiento y llevan a acciones **opuestas**: acoplado y **recuperable** → hay que buscar; acoplado y **no recuperable** → buscar no puede terminar bien, y lo correcto es decir que falta. Sin ese eje las dos se ven iguales desde la decisión y se paga una búsqueda condenada. Sale **gratis**: una referencia que **resuelve** ya es una unidad alcanzable. Y los tres valores son tres cosas: `True`/`False` **`OBSERVED`** —los ids se verifican contra un alcance finito— y `None` cuando no se nombró ningún puntero, porque ahí no hay nada que verificar
- [x] **P-2** · ~~sacarlo del camino activo~~ — **decisión revertida el 2026-08-27, y la revisión estaba mal planteada.** Lo demostrado es estrecho: el peso no puede mejorar la **selección de paradigma**, porque en el punto fijo es una transformación monótona de la tasa de victorias. Eso **no dice nada** sobre aprender asociaciones entre pares, que es a donde va (P-2c, P-2d, D-4). Y además ya gobierna algo: es el **reloj de decaimiento** con el que `consolidation.py:286` poda las stats sin episodios — nunca poda por peso solo, porque una stat con episodios es evidencia. Ese ciclo de vida —acotado, decae, piso, poda— es justo la maquinaria que una tabla de asociaciones necesita. **No se saca: se reusa.**
- [ ] P-2b · reintroducirlo como **detector de no estacionariedad** *(drift medido: 80%)*
- [x] **P-2c** · **ESTABLECIDA** con `P-2f` (`_analyze_p2f.py`): **3 de 13 celdas** tienen una transicion presente en todas las replicas exitosas y ausente en todas las fallidas, contra **mediana nula 0**, `p = 0,0078`. El `p = 0,055` anterior estaba medido con `n=3`, donde la **mediana nula era 7 de 13** — el criterio se satisfacia por casualidad. Con `n=9` el observado BAJA de 10 a 3 y el null cae a 0: lo que se cayo era el ruido. Debil y real: un corpus, un modelo, 3 celdas
- [x] **P-2f** · corrida completa: 13 celdas x 9 trials en `gold_p17b` (gemelo byte-identico, para no tocar el veredicto congelado de P17). **117 filas**, y el piso de `p` por celda bajo de `>= 1/3` —donde ninguna celda podia dar significativa aunque la senal fuera perfecta— a `0,008` en 10 de 13
- [x] **P-2d** · **resuelto, y el rango que faltaba no era un rango.** El reticulo ordena **como** se obtuvo una creencia; hacia falta ademas **sobre que es**. `Scope ∈ {REQUEST, POPULATION}` lo separa, y el piso de las acciones exige las dos cosas — asi la asociacion aprendida entra honesta como `COMPUTED` sobre `POPULATION` y queda **estructuralmente fuera de lo irreversible sin degradarle la procedencia**. `AssociationTable.as_beliefs()` la convierte, y afirma la **medicion** y no la recomendacion: el invariante «COMPUTED exige credencia 1,0» rechazo el primer intento —poner la fuerza como credencia— y tenia razon. `test_science.py` §37
- [ ] **P-2g** · **la asociación aprendida se fabrica como creencia y NINGUNA REGLA la
  consume** (pregunta del autor, 2026-08-29: «¿está extendida la plasticidad al orden de
  tools y a los pesos del handoff?»). La respuesta medida es que **no**, y los tres estados
  son distintos:

  | superficie | estado |
  |---|---|
  | ruteo `(región, paradigma)` | el peso se actualiza y `router.py` no lo lee — y **está probado que no puede servir ahí**: en el punto fijo `w* = 1,6p − 0,6` es monótona en la tasa de victorias, y el router ya ordena por esa tasa. Redundante por demostración, no por descuido |
  | **orden de tools** | **el único sentido vivo.** `association.py` aprende sobre pares ordenados —lo que la demostración de redundancia no alcanza, porque `(a → b)` no se recupera de las frecuencias marginales—. Establecida con `p = 0,0078`, débil: 3 celdas de 13, un corpus, un modelo. `P-2d` le dio rango honesto con `Scope.POPULATION`. **Y nada la lee** |
  | handoff | no existe. El reparto lo fija el código (`SUB_SCOPE_UNITS = 8`) a propósito: si el modelo dibujara la frontera del sub-agente se cruzaría el invariante |

  **Lo que falta no es evidencia ni rango: es un consumidor.** `AssociationTable.as_beliefs()`
  produce creencias `COMPUTED`/`POPULATION` bien tipadas, y el único lector fuera de
  `association.py` en todo el repo es `bench/analysis/_analyze_associations.py`. Ninguna
  regla de `rules.py` las mira, así que la creencia entra a la base y no cambia una sola
  decisión.

  Es la **misma familia** que `X-5h` (`seal_replay`) y que `theta_may_learn_online` antes de
  que `serve.py` lo impusiera: algo que se declara o se produce y nadie consume. Y no la
  atrapa `_audit_declarado.py`, porque el nombre sí se lee — lo lee su propio módulo.

  **Qué haría falta, y por qué no es obvio.** Una regla que ordene las tools por asociación
  aprendida choca con el invariante por un lado inesperado: no lo cruza —el código sigue
  decidiendo—, pero **sí** convierte una estadística en control de flujo. El casillero
  correcto es un **prior sobre el orden sugerido en la descripción de las tools**, que es
  factor y no patrón. Antes hay que decidir eso, y la decisión es del autor.

  Va **antes** de `P-2e`: componer el patrón en vez de elegirlo presupone que las
  asociaciones gobiernan algo, y hoy no gobiernan nada.

- [ ] P-2e · componer el patrón en vez de elegirlo *(el techo)*
- [x] **P-3** · **cerrado, y el efecto no era neutro.** El router recibia un objeto `Calibration` que **ninguno de los cinco sitios de construccion pasaba**, asi que `trustworthy` era False siempre — y sin confianza el piso derivado sube a `OBSERVED` en A2+, o sea que **A2 con piso `ELICITED` era inalcanzable por construccion**. La evidencia para ganarlo se computaba, se persistia y se tiraba. La correccion **no** fue pasar el parametro en los cinco: vive en el **bundle firmado**, por la misma razon que los pisos aprendidos — cambia lo que un request puede hacer, asi que es politica. Un parametro se puede olvidar; adentro del bundle no hay donde. `test_science.py` §32
- [x] **P-4** · **cerrado, y habia una violacion del reticulo adentro.** `horizon_unknown` llevaba la credencia **y la procedencia** de `coupling` —el codigo lo decia: «estimated alongside coupling»—. Dos consecuencias: el horizonte no tenia evidencia propia (y la calibracion es **por proposicion** justamente porque un modelo puede ser confiable sobre una cosa y pesimo sobre otra), y **tras una sonda heredaba `OBSERVED`** — o sea que una proposicion que nadie midio alcanzaba el piso que las acciones irreversibles exigen. La sonda lee una unidad para testear **acoplamiento**. Ahora el horizonte declara lo suyo y la sonda no lo toca. Y el `0.8` inventado pasa a `ELICITED_PRIOR_CREDENCE`, declarado: no es una medicion, es un **prior**, y existe la maquinaria que puede desmentirlo. `test_science.py` §33
- [x] **P-5** · **cerrado, y era el mismo defecto que P-6.** Nadie consultaba las particiones descubiertas porque **no se podian consultar**: los cuatro ejes de particion eran inevaluables al decidir. La causa de fondo estaba mas abajo — **el vector φ no llegaba a la fila**, y lo unico que quedaba era `region`, que ya es φ **discretizado**. Ahora la fila lleva `n_units`, `phi_coupling`, `phi_horizon_unknown` y `phi_continuation`, con `None` = no establecido
- [x] **P-6** · **ejes tipados, con guarda.** `DECISION_TIME` gobierna; `POSTERIOR` (`iterations`, `cost_tokens`, `cross_unit_lookups`) **diagnostica** y no se tira — «los casos caros comparten esto» sigue sirviendo; `FORBIDDEN` (`truth_coupling`, `utility`) **levanta**: partir sobre la respuesta no descubre una regla, describe el gold. Y el test de consolidacion **ponia la senal sobre el oraculo**, asi que verificaba que se encontrara una particion que el router jamas podria evaluar. Corregido: la senal va sobre la estimacion y se sigue encontrando (umbral 0,522, 0,89 de separacion retenida)
- [x] **P-7** · **el producto deja rastro** (`store.append_decision` + base de creencias cuando el perfil lo declara, §35), con el límite honesto escrito (lección 8.8): producción alimenta la **calibración** —opinión contra observación, las dos en el mismo request— y **no la utilidad de θ**, porque un `Episode` lleva `was_best` y producción corre un solo brazo. Cablearlo al endpoint real no es este pendiente: **el endpoint no existe**, y es `A-1`
- [x] **P-12** · **ocho metodos publicos del runner no tenian una sola prueba** —`study`, `replicates`, `report`, `consolidate`, `save_report`, `decide_for`, `surface_for`, `features_for`— y son los que producen **todos los veredictos**. Por ese agujero pasaron dos defectos el mismo dia: un kwarg muerto que dejaba `report()` roto de plano, y un `KeyError` cuando la escalera de cascada nombra brazos que el estudio no corrio. Cubierto en §34, **hermetico** —registro sintetico en un temporal— porque un test atado al registro pagado cambia de veredicto cuando cambia el dato
- [x] **P-8** · **la promocion decide sobre un INTERVALO, no sobre un punto.** Comparar dos estimadores puntuales no es una guarda: sobre un holdout chico, un candidato que gana por 0,001 gana por ruido la mitad de las veces — y una vez promovido queda como incumbente que el ciclo siguiente tiene que superar, asi que el error **se hereda**. Ahora hay bootstrap **pareado** sobre los episodios de holdout (1.000 remuestras, 95%, semilla fija: promover tiene que ser tan reproducible como rutear) y se exige que el borde inferior supere el piso. Probado en §29 con los dos casos que importan — una ganancia que se da en promedio pero se pierde en muchos episodios **no** promueve; una chica y uniforme **si**
- [x] **P-9** · **idempotente, y salio un segundo defecto que se tapaba con el primero.** (a) `candidate` reaplicaba la lista entera sobre el incumbente sin saber que ya estaba adentro: dos ciclos sobre el mismo registro movian el peso el doble e inflaban `episodes`, que es la cuenta que decide si una region puede decidir. Ahora el bundle lleva una **marca de agua firmada** de lo absorbido y declara cuanto salteo. (b) el peso se redondeaba al SERIALIZAR y no al aplicar, asi que **lo firmado no era lo que decide** — un bundle recargado resolvia con otro numero. Alineado. `test_science.py` §28
- [x] **P-10** · **el dial ya impone lo que declara.** `theta_may_learn_online` vivia en el perfil y **no lo leia nadie**: la invariante «nada aprende adentro de un request» se cumplia porque `Plasticity.apply` solo se llama offline — o sea, **por casualidad**, y una invariante casual la rompe el proximo cambio sin que nada avise. Ahora `serve.py` envuelve el request ENTERO en `no_online_learning()` y `apply` levanta ahi adentro. Probado en `test_science.py` §27, incluido que la guarda no sea global y que el perfil declare lo mismo que la guarda impone
- [x] **P-11** · dependencia invertida: `app/verify.py` es el verificador del **producto** y `grading` es la cara del **banco** sobre el mismo primitivo. Relocación pura, verificada re-puntuando 390 filas: **0 discrepancias**

**Lo más grande, y no estaba en la lista**
- → **A-1** se mudó a `PRODUCTO.es.md` (2026-08-29). No está cerrado: va en otro momento.
- → **A-2** se mudó a `PRODUCTO.es.md` (2026-08-29). No está cerrado: va en otro momento.
- → **A-2b** se mudó a `PRODUCTO.es.md` (2026-08-29). No está cerrado: va en otro momento.
- → **A-3** se mudó a `PRODUCTO.es.md` (2026-08-29). No está cerrado: va en otro momento.

**Apareció al aplicar B2**
- [x] **X-1** · un solo constructor `payload_for(task)` en `features.py` — los tres sitios lo usan
- [x] **X-3** · **cableado y medido: CERO.** El contador vive en la superficie (`malformed_json` y `dropped_items`, separados porque piden arreglos distintos) y lo anota `parsing.py`. Sobre el registro completo de `gold_p17` replayado sellado — **336 filas, cinco brazos** — no hay una sola malformacion. **Ningun paradigma pierde utilidad por el formato**; la pierde por la tarea. Y el cero significa cero: `test_science.py` §26 verifica que el contador se dispare y que **todo** sitio que parsea JSON pase la superficie
- [x] **X-4** · **cerrado.** El sobrecosto real es **6,7%** —`dag_strategy` 8,0%, `react` 4,5%, `rewoo` 0,0%— y no distorsiona la comparacion: `X-4d` lo verifico descontandolo y ningun veredicto se movio. La primera estimacion, por `calls`, era falsa: de 27 sitios que llaman al modelo **uno** pasa `tools`, y el absurdo lo delato —en 7 celdas daba mas declaracion que prompt entero
- [x] **X-4a** · **contestado: lo lazy NO aplica acá.** El patrón de 2026 —diferir las definiciones detrás de una tool de búsqueda— reporta 80-95% de ahorro y mejoras de acierto (49%→74%), **sobre catálogos de 100+ tools**; la regla publicada es que por debajo de ~10 el sobrecosto de la búsqueda no se paga. MAPO tiene **4** en `basic` y **10** en `cognitive`, y el gateo por variante **ya es** divulgación progresiva. Aplicarlo acá agregaría una llamada por request para ahorrar 528 tokens
- [x] **X-4b** · **la vía no existe, y por aritmética** (lección 5.11). El caché **sí** cubre `tools` —«both the messages array and tool definitions», documentación de primera mano— y **ya está encendido por defecto**: no hay directiva que mandar, así que esa mitad del pendiente era falsa. Pero exige **≥1.024 tokens iniciales idénticos** y el prefijo estable entero mide **~567** (533 de tools + 34 del contrato): **nunca llega**. Y el prompt arranca con `Task: {question}`, o sea lo variable primero, justo al revés de lo que la documentación pide. Dentro de una tarea sí pega y es gratis; ahora además se **mide** (`provider_cached_tokens` desde `prompt_tokens_details`), que era lo único que faltaba
- [x] **X-4d** · **el orden del prompt es un factor** (`framed()`, `stable_prefix_first`). Hoy todo arranca con `Task: {question}`, así que entre dos tareas el prefijo común se rompe en el **token 3** — la documentación pide lo contrario. **Y no alcanza por sí solo**, que es la parte honesta: el prefijo estable mide ~567 tokens contra un umbral de 1.024, así que dar vuelta el orden **no compra caché** hasta que ese prefijo crezca. Se implementa porque es gratis, es **condición necesaria**, y medirlo aparte separa el efecto del **orden** del efecto del **largo**
- [~] **X-4c** · **implementado como FACTOR y con predicción registrada** (`terse_tools`, P24a-d en README). Las descripciones son **55% del payload** de la spec y son lo único que el modelo lee para decidir QUÉ tool usar. La forma corta conserva lo que **discrimina** y tira la prosa que instruye —andamiaje por prompt, que este banco ya midió que no compra nada—: **−38,4% de la spec, −2,57% del prompt**. Y una decisión tomada antes de gastar: **2,57% está por debajo del piso de ruido de casi toda celda**, así que el factor viaja con otra corrida y **no se le encarga una propia**. Lo que ese N sí resuelve es el riesgo (P24c/P24d), que es el número por el que existe
- [x] **X-4d** · **medido con el sobrecosto real: no se mueve NADA.** Sobre `gold_p17` replayado sellado, descontando por `tooled_calls`, el mejor fijo es el mismo en los cuatro lambda y la brecha de oraculo es **identica a cuatro decimales** (0,3333 · 0,1750 · 0,0000 · 0,0000). La razon es concreta: `rewoo` es el **piso de costo** y carga **cero** declaracion, asi que descontar no mueve el piso y los ratios casi no cambian. **Ningun resultado publicado esta en riesgo**, y con eso el resto de X-4 —cache de prompt, acortar descripciones— es **optimizacion y no correccion**: baja su urgencia, no su valor
- [x] **X-5** · **el presupuesto ya no está sólo en tokens** (lección 5.9). Cerrada por `X-5a` (λ sobre plata), `X-5b` (el par es la acción), `X-5c` (capacidad como precondición) y `X-5f` (dos modelos). Lo que el banco no podía ni preguntar —«un modelo 10× más caro que necesite 37× menos tokens, ¿sale más barato?»— ahora lo pregunta la aritmética antes de gastar un token
- [x] **X-5a** · **λ barre sobre plata** (`Tariff`, `app/tariffs.py`, lección 5.7). El mejor fijo **no cambia** —misma unidad, todo λ, los dos corpus— así que nada de lo publicado sobre *quién* gana se mueve. Lo que se mueve es **cuánto**: la ventaja del más barato se parte al medio (`react` **26,0× → 11,6×**) porque el más barato es el que emite salida, 8,1% contra 0,3%. El arancel es **referencia, no medición**, así que se barre salida/entrada de ×1 a ×32: el orden **aguanta entero** y ×1 reproduce los tokens exacto. Se puede afirmar lo invariante, no un número en dólares. Y cayeron dos guardas: el clamp `max(1.0, cheapest)` —el mismo de `X-4d`— y `bounded()` sin rango semiabierto
- [x] **X-5b** · **el modelo es ACCIÓN** (`app/models.py`, `feasibility.admissible_pairs`, `Plan.model`, §44, lección 5.9). El espacio de decisión es el par `(modelo, paradigma)` y la factibilidad poda **pares** con dos cotas nuevas: **ventana** —un presupuesto no agranda una ventana, manda la menor— y **plata**. La trampa evitada: el modelo NO entra al vocabulario de región, que fue el mecanismo de `P15`
- [x] **X-5c** · **la calidad es precondición, no presupuesto** (`Capability`, `AssuranceProfile.min_capability`, §44). Piso **ordinal** —un cardinal invitaría a compensarlo con costo— y **no hizo falta mecanismo nuevo**: `required_floor` ya elevaba toda acción irreversible a A3, así que el piso en A3 **es** el que impide rutear lo irreversible al modelo barato porque salga la cuenta. Le había puesto piso a A2 también y **lo saqué**: era política mía sin medida, y obligaría a pagar 25× en cada request contable — queda como `X-5g`
- [x] **X-5d** · **la comparación entre modelos va al ANÁLISIS** (§42, `load_rows`). La guarda levanta si un archivo mezcla decodificaciones y **está bien**: promediar entre modelos no mide un paradigma, mide el modelo. El estudio multi-modelo se arma uniendo estudios por modelo. Queda escrito para que nadie «arregle» la guarda creyendo que estorba
- [x] **X-5e** · **contestada con lo ya pagado** (lección 5.4): la hipótesis del autor se confirma **condicionada a la dificultad**. En `gold_deep` el modelo caro usa **0,81×** los tokens del barato; en `gold_v2`, **1,90×**. Puntos de equilibrio **1,24×** y **0,53×** por token. Sobrio: aun donde gana, 1,24× no alcanza para pagarse — y eso **fortalece** el caso del ruteo, porque el uso correcto del caro es exactamente donde gana. Convertirlo a plata es `X-5a`, no esto
- [x] **X-5f** · **dos modelos eligiendo por caso** (`Router.plan(models=...)`). Orden de cotas: **dial primero, plata después** — al revés, un descuento compraría permiso. `A3 + USD 0,02` **se abstiene** en vez de bajar de modelo, que es el caso que prueba el orden. Sin catálogo el plan dice `model=''`, que es el régimen medido hasta hoy: decirlo vacío es distinto de mentir un nombre por omisión
- [x] **AR-5** · **CERRADO el 2026-08-29. Toda comparación de brazos estaba ponderada por una dosis que ningún
  análisis exige declarar.** El brazo de recuperación sustituye **sólo** a `hybrid` —la tool
  `search`—; `keyword_search` y `semantic_search` salen fijas del runner. Así que la dosis
  de tratamiento que recibe cada paradigma es la fracción de sus búsquedas que va por
  `search`, y está medida (auditoría del 2026-08-29, eje 4):

  | paradigma | dosis |
  |---|---:|
  | `react` | **70,1 %** |
  | `rewoo` | 59,5 % |
  | `dag_strategy` | 16,3 % |
  | `gist_reader` | **0 %** |

  Eso **no invalida P26, lo explica**: `gist_reader` sale idéntico al token porque no recibe
  tratamiento, y `dag_strategy` —el líder del corpus— recibe **una sexta parte** del que
  recibe `react`. Un efecto de brazo promediado sobre paradigmas es un efecto ponderado por
  esa dosis.

  **La función existe** (`app.metrics.arm_dose`, con tests en `test_science.py`, y devuelve
  `None` y no `0,0` cuando el paradigma nunca buscó — la distinción importa). Lo que falta
  no es implementarla: es que **algo la exija**. Hoy la usa **un solo análisis**
  (`_analyze_p26.py`) y ninguna otra comparación de brazos está obligada a condicionar por
  ella. Es la corrida `hybrid` contra `hybrid`+HyDE la que va a producir el número, así que
  `AR-3` y `AR-4` tienen que reportarse **condicionales a la dosis**, no promediados.

  Encontrado leyendo `historico/AUDITORIA-PATRONES-2026-08-29.es.md` contra el código: la
  auditoría lo dejó escrito como deuda y era la única de sus tres deudas que no había
  llegado a esta lista.

  **Cómo se resolvió: `metrics.arm_effect`, que estratifica y se NIEGA a colapsar.**
  Devuelve el delta por paradigma **con su dosis al lado**, separa a los que no recibieron
  tratamiento —dosis `0,0` o `None`, que son dos motivos distintos con la misma
  consecuencia— y `pooled()` **levanta** si la dispersión de dosis entre los tratados pasa
  el 25%. En el caso medido —`react` 70% contra `dag_strategy` 16%— levanta.

  **No corrige el efecto ni lo pondera, a propósito.** Corregir exigiría un modelo de cómo
  la dosis transforma el efecto, y no hay ninguno medido. Negarse es lo único honesto que
  se puede hacer con lo que hay. Y levanta en vez de avisar al lado: **un aviso junto a un
  promedio inválido publica el promedio**, que es exactamente la lección por la que existe
  `_sanity.py`. `test_science.py` §49.

- [x] **X-5h** · **CERRADO el 2026-08-29. `seal_replay` era una garantía declarada que NO imponía nadie** (encontrado
  el 2026-08-29 cruzando `README.md` contra `assurance.py`). El perfil de `A3_CERTIFIED`
  lleva `seal_replay=True` y **ningún camino del repo lo lee**: `grep` da cero fuera de
  `assurance.py`. El sellado que sí existe —`LLMClient._sealed`, `embeddings.py`— es un
  mecanismo aparte que se activa por otra vía y **el dial no lo enciende**.

  Es exactamente la falla de `theta_may_learn_online`, que vivía en el perfil sin lector y
  cuya invariante se cumplía **por casualidad** hasta que `serve.py` la impuso de verdad. La
  diferencia es que aquélla se cumplía por accidente y ésta **no se cumple**: A3 promete
  replay sellado y no lo hay.

  No es una corrida: es código. Y no lo atrapa `_audit_declarado.py`, porque el nombre **sí**
  se lee —lo lee el propio `PROFILES`— y lo que falta es que alguien lo consulte para
  DECIDIR. Es la cuarta variante de la misma familia de defecto.

  **Cómo se resolvió, y las dos decisiones que tenía adentro.**

  *Sobre el REPLAY y no sobre la respuesta viva.* Sellar la ejecución original haría
  imposible contestar un A3: toda primera llamada es un miss de caché, así que el nivel más
  estricto sería el único que nunca puede responder. Lo que la garantía promete no es que
  la respuesta salga del caché — es que **volver a correrla no pueda tocar el modelo en
  silencio**. `answer(..., replay=True)` sobre un plan cuyo perfil resuelto dice
  `seal_replay` usa un cliente sellado, y un miss **levanta**.

  *Una VISTA sellada, no un flag que se prende.* El pool devuelve el **mismo objeto** por
  modelo: mutar `_sealed` dejaría sellado al cliente de todos los requests siguientes, y un
  sellado que se contagia aparece en un request que no lo pidió. `LLMClient.sealed_view()`
  comparte caché y namespace —lo único que cambia es que un miss deja de ser una llamada— y
  devuelve `self` si ya está sellado.

  *Y no aplica a la decisión.* Un auditor replaya las **reglas** sobre la base registrada y
  no llama al modelo ni una vez. Lo único que gasta llamadas es el paradigma, así que la
  garantía es sobre la EJECUCIÓN. Verificado en `test_science.py` §51, incluido que **sólo
  A3** declare replay sellado — si lo declarara otro nivel, sellar dejaría de significar
  «certificado».

- [ ] **X-5g** · **¿necesita A2 un piso de capacidad?** Es empírica y hoy está en `None` a propósito. Ponerle `DEEP` obliga a pagar 25× en cada request contable; no ponérselo admite el modelo barato donde hay que rendir cuentas. Se decide midiendo la tasa de error del barato al piso de procedencia de A2, no argumentando
- [x] **X-5h** · **las tres proyecciones que faltaban, llenas** (§44). `react` y `reflection` proyectan **llamadas** desde sus propios `max_iterations` —su GASTO es una decisión del modelo, su CANTIDAD DE LLAMADAS la fija el código, y confundirlas era lo que los dejaba sin proyectar—; `rewoo` y `dag_strategy` proyectan **tokens**, este último `content × ramas` porque cada rama ve el material entero y arrastra el blackboard (la medición lo respalda: 89.834 contra 30.000 de contenido, ~3×). **Ningún par queda sin cotizar en plata.** Y el test dejó de fijar el defecto: prueba el mecanismo sobre la función, para que sobreviva a que hoy ningún brazo lo dispare
- [x] **X-2** · **el diagnostico estaba mal y el arreglo era otro.** El split prompt/completion **existia** en `Usage` desde siempre; lo que pasaba es que la FILA guardaba solo el total y la informacion se tiraba al escribir. Ya lo lleva. Y el gasto acumulado esta medido desde el cache (`_analyze_spend.py`): **66,4M tokens**, de los cuales la salida es el **1,7%** — eso valida que barrer lambda sobre el total sea un proxy razonable ACA. La tarifa se declara por entorno (`MAPO_PRICE_IN_PER_M` / `_OUT_PER_M`) y **no se inventa**: un precio inventado produce un numero que parece una medicion

**Riesgos que nadie estaba mirando**
- [x] **R-1** · **CONCLUIDA A ESCALA** (`_replay_full.py`): **390 de 390 filas** de `gold_p17` replayadas selladas por el camino del runner, **0 llamadas vivas** y **0 discrepancias** en utilidad, respuesta y costo. No 27 celdas: el registro entero. La causa del fracaso anterior era que la fila no decia con que modelo se produjo; cerrado estampando la huella, con guarda de mezcla (`test_science.py` §25)
- [x] **R-2** · **SE SACA: dejo de significar algo** (2026-08-29). Eran las celdas † que
  quedaron sin correr cuando se congelo la grilla `gpt-5-chat`, y valian mientras esa grilla
  fuera el brazo de comparacion multi-modelo. **La corrida homogenea la reemplaza entera**:
  corpus nuevo con entidades, tokenizador corregido, otro plantel y otros modelos medidos.
  Completar huecos de una grilla que ya no es la referencia no agrega evidencia a nada — y
  el dato historico se replaya igual. Se cierra con el motivo adentro en vez de borrarse,
  porque saber que existio explica por que el brazo multi-modelo arranca de cero
- [x] **R-3** · **barrido hecho, y encontró lo más caro que había.** El paper decía que `P8` **no había corrido**, y había corrido: 32 filas en `gold_holdout` sin veredicto computado desde el 2026-08-26. Evaluada como estaba enunciada, **dos de cinco no transfieren** y la regla de decisión registrada dispara: los veredictos por celda pasan a **corpus-locales**. Corregido en los dos papers
- [x] R-4 · `lab/ui/index.html` — **es la UI de prueba del autor**; se adopta
- [x] **R-5** · **pusheado.** `origin/main` al día; el respaldo con los 33 mensajes originales queda en `respaldo-pre-squash-2026-08-28`

**Decisiones dinámicas que hoy no gobierna nadie**
- [x] **D-1** · **medido de punta a punta.** El premio: **33% del gasto evitable** a igual utilidad. La señal: `barren_peak` **1,17 contra 2,28**. La regla: impuesta por código. Y **P20 corrida**: `P20a` **REFUTADA** —baja 2,6%, no ≥10%— porque `P20d` también lo es: tras el rechazo el modelo **re-emite la búsqueda el 69%**. `P20b` **CONFIRMADA**: cortar **no cuesta utilidad**. La corrección que se sigue es estructural y vive en `D-1c`
- [x] **D-1c** · **ya estaba implementado y NO estaba llegando al modelo.** `withdrawn()`
  saca las busquedas de las specs y `_run_tool_loop` lo pasaba — pero llamaba a `specs_for`
  **sin `terse` ni `offer_board`**, y ese es el unico sitio del repo que manda la declaracion
  de tools. Verificado ahora sobre el camino y no sobre la funcion (`test_science.py` §56),
  que es la diferencia entre un factor implementado y uno ejecutado
- [~] **D-1b** · **`read_all` no existe en `basic`**, que es la variante de TODOS los estudios medidos: el modelo nunca pudo pedir el material entero aunque entrara comodo en su presupuesto, y eso **nadie lo decidio midiendo** — es consecuencia de en que lista quedo la tool. Expuesto como factor `offer_read_all`, apagado por defecto, ofreciendolo **sin** arrastrar el resto de la contabilidad. La guarda de tamano ya estaba y es lo que lo hace seguro. **P21a-d registradas**; falta correrlo
- [x] **D-2** · **desbloqueado y corrido: 93 misses → 0.** La causa era exactamente la de `R-1` — el script reconstruía sólo `results_dir`, así que corría con la huella del **modelo congelado** y fallaba el 100% de las claves sin que nada lo dijera. Con los ajustes correctos: **102 de 112 celdas** reconstruidas, **0 misses sellados**, 0 fallos de paradigma, **0 tokens**. Las secuencias están materializadas y las transiciones contadas por brazo — `rewoo` repite búsqueda (`search→search` 35), `dag_strategy` alterna (`keyword_search→read` 54)
- [x] **D-3** · **el código dibuja el grafo** (`dag_shape`, §48, lección 5.16). El modelo proponía la forma y el código la aceptaba, con topes fijos de **4 y 3** iguales para 3 unidades y para 400. Ahora se deriva por aritmética: **una unidad da una rama** —un DAG de un nodo, dicho en vez de fingir descomposición—. Y la cota es **la misma fórmula que factibilidad proyecta**: iba a inventar un `EST_CALL_TOKENS` y no hacía falta, y una aritmética paralela podría elegir un grafo que su propia cota prohíbe
- [x] **D-3b** · **el acoplamiento llega al paradigma** (`ToolSurface.coupling`, `dag_shape(task, coupling)`). Viaja por la **superficie** y no por la tarea: la tarea es lo que el caller **declara** y esto es lo que el sistema **midió** pagando una unidad — meterlo en la tarea los volvería indistinguibles, y el piso de procedencia entero depende de distinguirlos. La cota es **lineal** —el acoplamiento es continuo, no un interruptor— y nunca baja de una rama. **`None` no es cero**: cero significa unidades independientes, donde paralelizar es correcto, y no saber significa que no hay con qué decidir la forma
- [~] **D-4** · **implementado** (`app/paradigms/handoff.py`, `test_science.py` §39) y **P23a-d registradas antes de correr**. Alcances independientes —de la **vista**, no del prompt: un agente no puede leer afuera porque las unidades **no están**— y transferencia que **autoriza el código**: el agente propone (`ELICITED`, es su lectura) y la regla exige que lo que pide exista **literal** en un alcance que todavía no corrió (`COMPUTED`). Con la lección de `P20` adentro: **no hay herramienta de transferencia que se le pueda rechazar** — la acción no existe. Falta correrlo
- [x] **D-5** · **la «Constant Soup» tiene inventario** (`MODELO_Y_CONSTANTES.es.md`): seis constantes **atadas al modelo** con cómo re-derivar cada una, y siete que **no** lo están, con por qué. La prueba: *¿su valor correcto cambiaría si el mismo corpus lo corriera otro modelo?* **Derivarlas** es trabajo distinto (`D-5b`)
- [x] **D-5b** · **derivadas** (lección 5.6): los `COST_PRIORS` **erran 2-7×**, y lo primero fue averiguar **quién consume el número** porque la respuesta obvia era la equivocada — **no** gobiernan la poda, gobiernan **el orden de la cascada**. Con `reflection` inflado 3,2×, la cascada **nunca lo prueba primero** aunque sea de los más baratos. Cambiar la referencia de la escala es `D-5c`
- [x] **D-5c** · **resuelto, y era peor de lo enunciado.** El pendiente decía que la escala estaba anclada a `direct`. Buscando dónde cambiarla apareció que **el costo medido nunca superseder­ía al prior**: el comentario del router lo prometía —«measured mean_cost supersedes them once theta has data»— y `mean_cost` sólo se usaba para **mostrar**. El prior ordenaba la cascada **para siempre**. Implementada la supersesión (`_cost_key`, §40), y de paso se cae el problema de base: el costo medido son **tokens absolutos** y no necesita referencia
- [x] **P-13** · **barrido de «declarado y no ejecutado»** (`_audit_declarado.py`, lección 7.17): cuatro veces el mismo patrón en un día es una regularidad, así que se buscó entera. 20 candidatos, mayoría falsos positivos —la lista **no es un veredicto**— y **cinco reales**. La peor: `REGION_VOCABULARY`, que lleva su propósito escrito al lado —«un θ ajustado bajo un vocabulario nunca debe consumir regiones de otro»— y **nada lo estampaba**. Ahora va en la fila con guarda de mezcla, igual que la huella de decodificación. Y una de las cinco era **mía, de una hora antes**: el patrón se comete mientras se escribe
- [x] **P-14b** · **medición y estado son dos árboles** (lección 5.8). Primero: la guarda de mezcla vivía adentro de `Runner` y **todo analizador lee el `.jsonl` a mano**, así que no protegía a nadie que analizara — `load_rows` es de módulo. Apenas aplicada agarró que el **ledger de creencias vivía en `results/`**, y mi arreglo (enseñarle al analizador a esquivarlo) era el equivocado: **si no es resultados, no va en la carpeta de resultados**. `results/` es medición, `state/` es el ledger; un solo escritor, 207 registros mudados con la cadena íntegra, y la guarda de forma en el seam. Tres intentos hasta derivar bien la ruta: aritmética de rutas, después levantar contra un temporal de test — el store ahora **recibe** su directorio en vez de inferirlo del nombre
- [x] **P-14** · **las dos muertas: eliminadas, con el motivo escrito.** `GUARANTEED_FULL_READ` **duplicaba** `TRAVERSES_SCOPE` —la misma propiedad en dos módulos, una muerta— y ya **diferían**: la muerta incluía `cot`, que está retirado. Se eliminó la muerta; la viva ya gobierna la precondición de cobertura. `PRUNE_AFTER_CYCLES` iba a esperar tres ciclos antes de podar, y la regla que **sí corre** es `weight <= floor and episodes == 0`, que es **más fuerte**: nunca saca nada con evidencia. Un contador sólo demoraría sacar entradas provablemente vacías
- [x] investigar cómo resuelven el handoff MAF / OpenAI SDK / Google ADK

**Code review — MEDIUM**
- [x] M2 · M4 · M5 · M6 · M7 · M9 · M12 · M19 *(antes)*
- [x] **M3** · throttle bajo el lock y sin contar de más
- [x] **M11** · ECE sobre la credencia declarada, no el centro del bin
- [x] **M17** · el control nulo retirado sale del default (`RETIRED`)
- [x] **M18** · un solo escritor por archivo de resultados
- [x] **M8** · `COUPLING_CREDENCE_FLOOR` compartido: había una **zona muerta** — credencia 0,3 suprimía la sonda y no alcanzaba para especializar
- [x] **M10** · `GIST_CHARS` derivado de `SUMMARY_CHARS`: 400 → 220. El gist real promedia 69,4 chars, o sea **5,8× de sobre-proyección**
- [x] **M1** · args validados en `dispatch` ⇒ `ToolFailure`; el catch ampliado de `modern.py` se retira. **Era sesgo con dirección**: el mismo output malformado era recuperable en un paradigma y fatal en otro
- [x] **M13** · la FORMA validada, no sólo el parseo: `well_formed` filtra elementos sin las claves que el código lee dos líneas abajo
- [x] **M14** · `paradigms/parsing.py`: **cero copias**, un solo contrato de excepciones (había cinco tuplas distintas)
- [x] **M15** · loop de calibración deduplicado en `beliefs.score_calibration` — y las contradicciones, que sólo estaban en una copia, ahora se persisten en las dos
- [x] **M16** · un solo filtro de `None`: una fila legacy volteaba la consolidación entera
- [x] **pip-audit corrido, y lo primero que encontro fue un problema de metodo.** MAPO **no tenia archivo de dependencias**, asi que la auditoria corria contra el interprete GLOBAL y devolvia vulnerabilidades de paquetes que el proyecto ni importa — un resultado que parece un hallazgo sobre MAPO y es un hallazgo sobre la maquina. Con `requirements.txt` declarado (seis paquetes, derivados de los imports): **sin vulnerabilidades conocidas**. Queda una brecha REAL: el interprete global tiene `starlette 0.52.1` clavado por un paquete ajeno al proyecto, mientras el conjunto de MAPO resuelve a `1.6.0`. Correr sobre el global usa la version vulnerable — que es exactamente lo que cierra el on-prem/Docker de `ARQUITECTURA.es.md`

**Teoría — pizarra, bloquea a F6**
- [x] **T-1** · **dos de las tres clases implementadas y cableadas**: `C-NUM` (`fill()`) y `C-COMPLETE` (`complete()`, `complete_answer()`, `verify_coverage()`), con veredicto por fila, disparador tipado, déficit declarado (`AR-2`) y terminal propio (`retained`, `U-7`). `C-CITE` **no es deuda de análisis**: verificar una cita contra el índice necesita **el índice vivo**, que es infraestructura de producto y va con `G-2`/`A-1`
- [x] **T-2** · red-team hecho por nosotros: **5 de 5 familias sobreviven, residuo 100%** (`_redteam_binding.py`). Las cinco comparten forma: lo que falsea la oración vive en la **prosa conectiva**, que no ocupa ranura
- [x] **T-3** · **teorema de soundness del ensamblador** (`SOUNDNESS.es.md`, §46, lección 5.15). Si `fill` emite, toda ranura viene de una creencia **vigente** con procedencia ≥ piso y la subcadena es exactamente `str(valor)`. Demostración por construcción, y depende de **una línea**: la sustitución ocurre después de comprobar que los rechazos están vacíos. Falla cerrada y **entera**. Los cuatro límites van **adentro del enunciado**, y el más duro es que **el alcance es la ranura, no la oración**: «el saldo NO supera {x}» con x correcto es **sound y falso**, y está en el test como caso que debe pasar. Verificado sobre las 16 combinaciones, no por casos
- [x] **T-4** · **cota nativa derivada y verificada** (`COTA_RATCHET.es.md`, `test_science.py` §22): daño total **≤ 2 subidas por región para siempre**, la replicación es fuerte lejos del umbral (1 en 39.613) y **débil cerca** (1 en 3,7) — y eso se **reporta**, no se esconde. La Parte 3 —pérdida de cobertura por endurecimiento— es trabajo distinto y va aparte (`T-4b`)
- [x] **T-4b** · **medida, y corrige la lectura de la cota** (`_analyze_ratchet_cost.py`, lección 5.12). El ratchet es **gratis hasta A2** —A0/A1/A2 no restringen nada, así que subir ahí no compra garantía ni cuesta cobertura— y **cuesta todo de una vez en A3**: **60% del catálogo y 31% de la utilidad** (0,6101 → 0,4221). «A lo sumo dos subidas» invita a pensar en daño que se acumula despacio; lo medido es que **una sola transición tiene precio y ahí es abrupto**. Y el promedio esconde a quien paga: `many/no_oracle/loose/chain` pierde **−0,5000** con n=4, y en el corpus de sonda la media es **0,0000** con una región perdiendo 0,0877
- [x] **T-5** · **quién fija el dial** (`EL_DIAL.es.md`, §47, lección 5.14). `max(pedido, piso_de_creencias, piso_aprendido)`, y **`max` es la única composición donde cada fuente sólo endurece** — con `min` o un promedio, agregar una fuente sería un riesgo. El llamador **sube y no baja**. Cuarta fuente que no es un nivel: A2 sin calibración **endurece la procedencia dentro del nivel**. Y marginalizando sobre las cuatro posiciones aparece que **A0/A1/A2 no filtran un solo paradigma**: toda la restricción de catálogo vive en un escalón
- [x] **T-6** · **los cinco leídos, y tres le sacan a la novedad.** `EnvProbe` (2606.31422) ocupa **el sondeo con presupuesto para reparar una tabla de creencias tipada** — es nuestra sonda, mecanismo por mecanismo. `Kintsugi` (2605.09487) ocupa las **ediciones gateadas por verificador sobre un artefacto ejecutable tipado** — es la consolidación con su guarda. `ProvenanceGuard` (2607.01236) ocupa **«¿está esta llamada sostenida por evidencia trazable?»** — es el piso de procedencia. Y el área ya tiene **survey** (2606.04990). La novedad queda enunciada como **conjunción**: rutear entre **topologías**, **abstenerse** con curva riesgo-cobertura, y podar por **aritmética antes de inferir**. Y **`Trace2Policy` (2606.10457) nos apoya**: en producción, 22 días y 3.349 casos, **la varianza por versión de regla supera a la del modelo**

**Paper**
- [x] **W-1** · **re-encuadrado en los dos archivos.** El punto no era el orden de las secciones: era que **el Teorema 1 es una IDENTIDAD** —una descomposicion algebraica exacta, verdadera por construccion— y **ninguna medicion puede falsarla**. Lo empirico es solo si sus terminos satisfacen la desigualdad, que es una pregunta sobre un ruteador. Y los terminos **nunca se separaron**: el margen fue 0 en todas las tareas, asi que `alpha` y `beta` no se distinguen de siempre-fallback y la identidad se cumple **vacuamente**. El AURC degenerado (0,000 contra techo +0,400) es la misma cosa vista desde la curva. Queda dicho que el trabajo que un lector le acreditaria a §5.1 lo hace §5.2
- → **W-3** se mudó a `PAPER.es.md` (2026-08-29). No está cerrado: va en otro momento.
- → **W-4** se mudó a `PAPER.es.md` (2026-08-29). No está cerrado: va en otro momento.

**Plataforma**
- → **las seis piezas de la pila se mudaron a `PRODUCTO.es.md`** (2026-08-29). No están
  cerradas: son construcción, no medición, y el orden del autor las pone últimas. Estaban
  acá midiendo el mismo trabajo dos veces, porque `G-2` de aquel archivo ya las cubría.

**Fases de la tesis**
- [x] F0 · P15 cerrada y registrada
- [x] **F1** · **sensar y re-decidir: las tres pre-empciones diagnosticadas y la selección disparó.** Lo que queda de esta fase no vive acá — la sonda es `S-5`, el acoplamiento `S-4`, y el ciclo completo `REC-4`. Dejarla abierta contaba el mismo trabajo dos veces
- [x] **F2** · **routers rivales: E2 corrido.** El brazo que falta es **E1, y es `M-1`** —implementado, sin correr, ~26 llamadas—. Una fase abierta cuyo único resto ya tiene número propio es un duplicado
- [x] **F3** · **retención y mediación: el recall está medido y es la variable dominante** —brecha +0,533, y predice fuera de muestra al 60% desde el paradigma contra 3,8% desde la región—. El segundo eslabón —si la evidencia leída **sobrevive** hasta la llamada que responde— es **`M-2`**, con número propio
- [x] F4 · estadística que resista al tribunal
- → **F5** se mudó a `PAPER.es.md` (2026-08-29). No está cerrado: va en otro momento.
- → **F6** se mudó a `PAPER.es.md` (2026-08-29). No está cerrado: va en otro momento.
- → **F7** se mudó a `PAPER.es.md` (2026-08-29). No está cerrado: va en otro momento.

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
| M-1 | Brazo en PROSA (E1) | Los dos brazos implementados y sin correr: el clasificador de producción tal cual y el router en prosa más fuerte construible. **DESBLOQUEADO**: P16 y P17 ya cerraron. Es la medición más barata que queda, y puede cambiar la tesis — si la prosa empata a θ, la maquinaria determinística es decoración cara | ~26 llamadas |
| M-2 | Instrumentar retención de verdad | El recall de evidencia ya está medido y manda (ver §Findings). Falta el **segundo eslabón**: cuánta de la evidencia recuperada sobrevive hasta la llamada que responde. Eso sí necesita código y corrida | código + corrida |
| M-3 | Transferencia de θ entre familias de modelos | El colapso de `react` en nano sugiere que parte de lo aprendido es del modelo y no de la tarea. Condiciona la lectura de todo el registro | corrida |
| M-4 | Corpus natural + segunda familia | Validez externa real. Un segundo generador propio **reformula** la objeción, no la responde. QA numérica sobre documentos largos calza con los contratos | la fase cara |
| M-5 | C3 profundo en nano | Región abierta: la grilla completa dio u=0,000, y también oráculo-cero en `gold_transfer`. No hay ganador conocido | corrida |

---

## 1c. El «anti-RAG»: generar la pregunta de lo que falta

**La idea** (del autor, 2026-08-27): en vez de recuperar para responder, **detectar qué
falta y generar la pregunta que lo consigue**.

**La máquina ya existe y es REC** — sólo que apunta a la decisión, no al contenido.
`rec.py` toma una explicación fallida, calcula el **déficit contrafactual mínimo** (qué
creencia mínima habría cambiado el plan) y emite una `AcquisitionClause`, que es
literalmente «qué evidencia acotada comprar y cuándo parar»: `target_proposition`,
`probe_kind`, `verifier`, `reachable`, `max_reads/calls/tokens`, `safe_exit`. Eso *es* la
pregunta de lo que falta, en forma ejecutable y tipada.

**En `legacy/` no está, y lo que hay es su COMPLEMENTO, no su versión.** `hyde.py`
traslada el dominio de la búsqueda semántica a una **respuesta hipotética** en vez de la
pregunta: genera cómo se vería la respuesta impresa en un documento y la usa como query
KNN. Tiene sentido porque los documentos contienen respuestas, no preguntas — la consulta
«direcciones de X» y el texto «Via Carlo Farini 58, piano 4» no se parecen, y la
conjetura tiende el puente. No detecta un hueco: lo tapa con una conjetura **antes** de
buscar.

**Y por eso mismo es portable sin romper el invariante, que no es obvio.** HyDE alucina
en el canal de la CONSULTA, donde una alucinación no puede convertirse en afirmación: una
query mala cuesta una recuperación mala, nunca un dato falso con procedencia impecable. Es
el mismo principio que gobierna la sonda — el modelo propone, la regla decide — aplicado
un paso antes. Vale la pena decirlo como regla general: **la alucinación es admisible
exactamente donde no puede volverse una afirmación.**

Los dos se reparten el trabajo por lo que uno sabe al empezar:

| | HyDE | anti-RAG (REC) |
|---|---|---|
| Punto de partida | «no sé dónde mirar» | «sé exactamente qué proposición falta, y con qué procedencia» |
| Qué genera | una respuesta hipotética, como puente semántico | una adquisición acotada y verificable |
| Verificable | no, y no hace falta | **sí, y es obligatorio** |
| Dónde vive la conjetura | en la consulta | en ningún lado: el déficit es computado |

Lo único cercano a detección de huecos en `legacy/` es un prompt (`agent_config.py:392`)
que le pide al modelo etiquetar el contexto como `proved`/`insufficient`/`hypothetical`
— o sea **el modelo como juez de su propia suficiencia**, que es exactamente lo que el
invariante del producto rechaza. Ese no se porta.

**Lo que falta para que el anti-RAG sea real, y no es un generador de preguntas.**
Verificado: `lab/app/` tiene **cero** contratos de completitud. Y sin ellos, «qué falta»
no está definido — cualquier generador de preguntas tendría que inferir de la prosa qué
debería contener la respuesta, que es parseo de texto libre y está prohibido por regla.

La pieza es **T-1, la semántica formal del contrato**, que ya figura como bloqueante de
F6. Con ella la cadena cierra sin ninguna pieza nueva:

```
contrato declara qué proposiciones exige la respuesta
        ↓
la base de creencias no las tiene, o no con la procedencia exigida
        ↓
rechazo TIPADO  (beliefs.py ya lo produce: ABSENT / PROVENANCE / CREDENCE / …)
        ↓
déficit contrafactual mínimo  (rec.py, ya implementado)
        ↓
AcquisitionClause = LA PREGUNTA, acotada y certificada  (certify.py, ya implementado)
```

**O sea: el anti-RAG no es un patrón nuevo — es la superficie de CONTENIDO de la misma
máquina**, y `CLAUDE.md` ya la nombra («contenido: números slot-filled desde `COMPUTED`,
citado-o-callado, **contratos de completitud**»). De las cinco etapas, tres están
implementadas y probadas. Falta la primera, que es teoría, y el cableado.

### ¿Y si fuera una tool? — **no**, y la razón está medida en este mismo banco

Es la respuesta intuitiva y hay precedente en el código: `coverage` ya es exactamente
esta forma, una herramienta que le dice al modelo qué no cubrió («una respuesta armada
con parte de las unidades está mal aunque cada parte esté bien, y nada más te lo va a
decir»). Y el factor `{con, sin}` ya tiene maquinaria: `VARIANTS = ("basic",
"accounting", "cognitive", "managed")`.

**Pero este banco ya midió qué pasa cuando se ofrece una capacidad así, y el resultado
fue nulo.** `PATTERNS.md` §4.14: cuatro herramientas de memoria de trabajo (`note`,
`notes`, `plan`, `advance`) expuestas sobre 28 filas dieron **un note, una compactación y
cero planes**. La maquinaria de compactación, medida aparte en 29× de reducción, **nunca
se disparó**. La conclusión quedó escrita ahí: *exponer una capacidad no es proveerla, y
ofrecerla no es medirla*.

Un detector de huecos ofrecido como herramienta hereda ese prior. Y arrastra un segundo
problema, peor: una herramienta que el modelo **elige** llamar pone al modelo a decidir
cuándo revisar su propia suficiencia — que es exactamente lo que rechazamos del prompt de
`agent_config.py:392`.

**El repo ya contiene la corrección, y hay que empezar por ahí en vez de repetir el
experimento.** Después de que `cognitive` fallara, apareció `managed`, y su comentario en
`paradigms/__init__.py` dice qué se aprendió: *«Incondicional y determinista: el entorno
hace la contabilidad que el brazo cognitive midió que el modelo no hace voluntariamente.»*

Entonces: **el anti-RAG nace con forma `managed`, no con forma `cognitive`.** El entorno
computa el déficit y **gatea**; la herramienta, si existe, es de sólo lectura y sirve para
que el modelo se entere, nunca para que autorice. Ofrecerla y esperar que la use ya se
probó acá y dio cero.

### La forma correcta de HyDE ya estaba en `legacy/`, y el banco ya tiene la dimensión

**Verificado en el código.** En `subgraphs/semantic_search.py` HyDE **no es una
herramienta**: es una de **cuatro ramas paralelas obligatorias** que salen de `START`
—`semantic_fts`, `semantic_entity`, `semantic_knn`, `semantic_hyde`— y todas convergen en
un nodo de **fusión RRF + rerank**. Corre siempre, la dispara el entorno, y el modelo no
elige nada.

Eso tiene tres propiedades, y la tercera es la que hace que valga la pena:

1. **Es incondicional**, o sea con forma `managed` y no `cognitive`. Es justo lo que este
   banco midió que funciona, y su opuesto es lo que midió que no: *tools declaradas no
   son tools usadas*.
2. **Es paralela**, así que la rama extra no agrega latencia — sólo tokens.
3. **Está fusionada, y eso ACOTA el daño.** Una respuesta hipotética mala aporta
   candidatos que el RRF va a rankear abajo; **no puede desalojar lo que las otras tres
   ramas encontraron**. El modo de falla no es «peor calidad», es «pagaste una llamada de
   más». Riesgo acotado por construcción.

**Y por eso mismo la objeción correcta no es la que dije antes, sino la de costo.** Yo
había dudado de si la brecha semántica existe con un recuperador simulado. Con fusión, si
no existe, HyDE simplemente no aporta y **cuesta su llamada**. O sea que la pregunta
entera es *si la llamada extra se paga* — que es una pregunta de λ. Y **P16c acaba de
medir que λ es donde las cosas se mueren**: el ruteo captura +0,121 sin cobrar el costo y
ya está adentro del ruido en λ=0,02. Cualquier cosa siempre-encendida entra al registro
por esa puerta.

**La buena noticia: no hay arquitectura nueva que inventar.** El banco YA tiene esta
dimensión como factor. `retrieval.py` expone brazos —`lexical`, `simulated`, `oracle`,
`semantic`, `hybrid`— y `runner.py` escribe **un archivo por (corpus, brazo, variante de
superficie)**, con el comentario que explica por qué: *«juntar los brazos promediaría
sobre la variable misma que los brazos existen para separar»*.

Entonces HyDE es **un brazo nuevo**, `hybrid_hyde`, y la comparación `{hybrid,
hybrid_hyde}` es un factor limpio con camino de medición ya construido.

| # | Qué | Costo |
|---|---|---|
| **H-1** | Portar HyDE como **rama paralela fusionada por RRF**, no como herramienta | código, chico |
| **H-2** | Exponerlo como brazo `hybrid_hyde` — la dimensión ya existe | cableado |
| **H-3** | Medir `{hybrid, hybrid_hyde}` **con el costo cobrado**, no sólo por calidad. Sin λ, el número no significa nada: eso es lo que P16c enseñó hoy | corrida chica |

### Y si aplica a todos los patrones, entonces no es un patrón: es un FACTOR

Observación del autor: esto se podría aplicar a todos los patrones, y serían mejoras.
Es cierto, y por eso mismo hay que medirlo de otra forma. Tres cosas, en orden de
importancia.

**1 · Aplicarlo adentro de cada patrón destruye lo que el banco mide.** Si los trece
patrones llevan la detección de huecos incorporada, la comparación deja de ser «react vs
dag» y pasa a ser «react-con-anti-RAG vs dag-con-anti-RAG». La diferencia entre patrones
queda contaminada por una mejora común, y peor: **hay evidencia de que la mejora podría
tapar la diferencia entera**. Está medido que la brecha de recall de evidencia es **4,2×
la mayor ventaja entre paradigmas**. Cualquier cosa que mejore el recall de forma pareja
opera sobre una escala mayor que la que separa a los brazos.

El diseño correcto es **factorial**: `{con, sin} × {patrones}`. Eso mide dos cosas que
plegarlo adentro confunde en una — el **efecto principal** (¿cuánto compra el anti-RAG?)
y la **interacción** (¿le sirve más a `react` que a `dag_strategy`?). Y sólo la
interacción justifica seguir teniendo patrones distintos.

**2 · Va en el entorno, no en el cuerpo de cada patrón.** Es una regla que este repo ya
tiene escrita: los patrones se distinguen por **estructura de control de flujo**, y las
mejoras vienen de **señales de entorno** —contables, deterministas—, no de tocar cada
patrón. La detección de huecos es una señal, así que su lugar es la superficie
compartida. Aparte de correcto, es lo barato: trece implementaciones de la misma cosa se
separan solas, que es exactamente la enfermedad que este proyecto extirpó dos veces hoy
(el loop de tools en la capa congelada, y el ciclo de dos pasos del banco).

**3 · Un riesgo para el claim del producto que conviene enunciar ahora.** El valor del
ruteo **es la dispersión entre brazos**: si no hay diferencia entre paradigmas, no hay
nada que rutear. Una mejora transversal que sube a todos **comprime esa dispersión**, y
por lo tanto **puede reducir la brecha de oráculo del ruteo aunque mejore el sistema
entero**. Sería el peor resultado posible de leer mal: el producto mejora y su métrica
estrella empeora. Si el anti-RAG entra, la lectura del ruteo hay que reformularla al
mismo tiempo, no después.

| # | Qué | Estado |
|---|---|---|
| **AR-0** | Medirlo como **factor**, no plegado en cada patrón: `{con, sin} × {patrones}`, reportando efecto principal e interacción | diseño, antes de escribir código |
| **AR-1** | Contratos de completitud (= T-1) | pizarra — **la única pieza que falta de verdad** |
| **AR-2** | Cablear rechazo tipado de contrato → `rec.diagnose` | código, chico: la interfaz ya existe |
| **AR-3** | Predicción falsable antes de correr | gratis, y obligatorio por regla |
| **AR-4** | Comparar contra el baseline honesto | contra HyDE y contra RAG plano, no contra nada |

---

## 1d. El catálogo confunde dimensiones que son ortogonales

**La observación** (del autor, 2026-08-27): el blackboard está sólo en `dag_strategy`.
¿No hay separación de responsabilidades? Un patrón, una estrategia y unas herramientas
deberían poder combinarse.

**Verificado**: `class Blackboard` está definida **adentro** de `app/paradigms/dag.py` y
no la usa ningún otro paradigma. Y no es el único caso — el catálogo mezcla cuatro cosas
que son independientes:

| Dimensión | Hoy | ¿Es factor? |
|---|---|---|
| **Estructura de control** | react loop · olas de DAG · map-reduce · plan-execute | es *el* eje del catálogo |
| **Estado compartido** | blackboard **soldado dentro de `dag_strategy`**; el resto usa historial de mensajes | **no** |
| **Superficie de herramientas** | `basic` · `accounting` · `cognitive` · `managed` | **sí**, y funciona |
| **Pre-proceso de recuperación** | ninguno. `dag.py:31` registra como desvío explícito: *«NO PRE-FETCH, HyDE OR ENTITY RESOLUTION»* | **no** |

Una de cuatro es factor. Las otras tres están soldadas, y por eso hay preguntas legítimas
que el catálogo **estructuralmente impide hacer**: ¿`react` mejora con un blackboard?
¿`map_reduce` mejora con HyDE? Hoy no se pueden ni formular.

**Y esto no es sólo deuda de diseño futuro: contamina un hallazgo que ya está en el
registro.** `dag_strategy` es el mejor fijo en `gold_transfer` — el brazo contra el que
el ruteo perdió en P15. Pero `dag_strategy` es *la única* estructura que tiene blackboard.
Así que **lo que el registro llama «el efecto dag_strategy» es la conjunción de dos cosas
—la topología de olas y el estado compartido— y nada en el registro las separa.** Es la
misma falla que §4.14 nombra desde el otro lado: atribuirle a una pieza un efecto que no
se midió por separado.

**El costo de arreglarlo, dicho antes de proponerlo.** Factorizar multiplica la grilla, y
el tamaño de grilla es la restricción que manda: P16 sola son 390 celdas y ~14M tokens.
Un factor de dos la duplica. Así que **no se factoriza el catálogo entero**: se introduce
**un factor por vez**, con predicción registrada, y sobre un subconjunto de celdas elegido
por donde el mecanismo debería actuar — no sobre la grilla completa.

| # | Qué | Costo |
|---|---|---|
| **F-1** | Sacar `Blackboard` de `dag.py` a un módulo propio, sin cambiarle el comportamiento | refactor, gratis, verificable con las suites |
| **F-2** | **`{blackboard, sin blackboard} × {react, dag_strategy}`** sobre C2/C4, donde la descomposición importa. Es el factor más barato y el que descontamina el hallazgo de arriba | grilla chica |
| **F-3** | HyDE como factor de pre-proceso, **decidido por el autor: se usa** (ver A-2b) | corrida |
| **F-4** | Escribir la regla: qué dimensión define un patrón y cuál es un factor. Hoy la regla dice «los patrones se distinguen por estructura de control de flujo» — que ya implica que estado y superficie **no** son patrones, y sin embargo el blackboard vive adentro de uno | pizarra, gratis |

---

## 2. Producto — deuda de la capa de decisión

| # | Qué | Por qué importa |
|---|---|---|
| P-1 | **Que la sonda sense recuperabilidad** | La sonda existe para convertir una variable invisible en observada, y hoy sensa *acoplamiento*. Medido: el recall de evidencia predice fuera de muestra al 60% desde el paradigma, y la región apenas al 3,8%. La variable que conviene sensar es **si la evidencia se va a encontrar** |
| P-2 | **NO sacarlo: reusarlo.** Lo demostrado es que no puede mejorar la selección de paradigma; el peso además es el reloj de decaimiento de la poda | Demostrado, no medido: en el punto fijo `w* = 1,6p − 0,6`, monótona en la tasa de victorias, y `theta_assertions` ya ordena por esa tasa. Una transformación monótona **no puede** cambiar un argmax, así que como selector es redundante por construcción y ningún tuneo lo arregla |
| P-2b | **Reintroducirlo como detector de no estacionariedad** | El drift está medido: **4 de 5 regiones cambian de ganador (80%)**. Donde el peso y la tasa discrepan sobre el mejor brazo, la región está en transitorio, y la acción correcta es **bajar la confianza y abstenerse** — maquinaria que el producto ya tiene. Requiere antes arreglar la parametrización: el piso 0,01 aplasta todos los brazos débiles, salir de él cuesta ~5 victorias, y con ~6 updates por clave contra un horizonte de ~20 el estimador nunca sale del prior. Predicción falsable registrada ANTES de correr |
| ~~P-2c~~ | ~~Hebbiano sobre el ORDEN de llamada a tools~~ | **ESTABLECIDA 2026-08-28**, `p = 0,0078`. Tres de 13 celdas tienen una transición presente en **todas** las réplicas exitosas y ausente en **todas** las fallidas, contra mediana nula 0. El `p = 0,055` previo estaba medido con `n=3`, donde la mediana nula era 7 de 13 — el criterio se cumplía por azar. Con `n=9` el observado **baja** de 10 a 3 y el null cae a 0: lo que se cayó era el ruido. Débil y real: un corpus, un modelo, 3 celdas |
| P-2d | **Asociaciones aprendidas como creencias** (idea del autor) | Se puede, con una restricción que no se negocia. El retículo es `ASSUMED < ELICITED < OBSERVED < COMPUTED` y las acciones irreversibles exigen `COMPUTED`/`OBSERVED` **justamente** para dejar afuera a la estadística y a la opinión. Una asociación aprendida es aritmética sobre un ledger, así que *parece* COMPUTED — y si entrara con ese rango, una regularidad estadística podría gatear una acción irreversible, que es exactamente lo que el piso existe para impedir. No es una observación sobre ESTE request: es un prior sobre requests parecidos. Necesita un rango estrictamente por debajo de OBSERVED, y **el retículo hoy no tiene ese casillero** |
| P-2e | **Componer el patrón en vez de elegirlo** (idea del autor) | La conclusión lógica de P-2c, y la más grande. Si las asociaciones de orden se aprenden, el paradigma deja de ser una entrada de catálogo y pasa a **sintetizarse por request**: el catálogo se vuelve un *prior*, no el espacio de acción. Encaja con lo que E2 ya midió — «donde la cascada dispara, la elección no produce el valor: la estructura de la acción lo produce». **Y abre dos tensiones que hay que resolver antes, no después**: (1) el banco mide paradigmas que son funciones async planas, y un patrón sintetizado no está en el catálogo, así que la comparación contra brazos fijos deja de estar definida — hace falta una respuesta de diseño, no una mano; (2) A2 y A3 restringen los patrones admisibles al catálogo (A2 con profundidad ≤ 3, A3 a un subconjunto certificado), así que un patrón sintetizado **no puede correr bajo A2+** sin una historia de certificación. Los dos son problemas de diseño reales, y son la razón por la que esto va después de P-2c y no antes |
| ~~P-3~~ | ~~Calibración por proposición al router activo~~ | **CERRADO 2026-08-28.** Cinco sitios construyen `Router` y **ninguno** pasaba la calibración, así que `trustworthy` era False siempre — y con eso **A2 con piso `ELICITED` era inalcanzable por construcción**. Vive ahora en el **bundle firmado**, por la misma razón que los pisos: cambia lo que un request puede hacer. §32 |
| ~~P-4~~ | ~~Horizonte con evidencia propia~~ | **CERRADO 2026-08-28**, y adentro había una violación del retículo: tras una sonda el horizonte heredaba `OBSERVED`, o sea que una proposición que **nadie midió** alcanzaba el piso de lo irreversible. La sonda mide **acoplamiento**. §33 |
| ~~P-5~~ | ~~Las particiones descubiertas no gobiernan el router~~ | **CERRADO 2026-08-28.** Nadie las consultaba porque **no se podían consultar**: el vector φ no llegaba a la fila, y lo único que quedaba era `region` — que ya es φ **discretizado** |
| ~~P-6~~ | ~~Particiones que usan truth de evaluación~~ | **CERRADO 2026-08-28.** Ejes tipados: `DECISION_TIME` gobierna, `POSTERIOR` **diagnostica**, `FORBIDDEN` levanta. Y el test **ponía la señal sobre el oráculo**: verificaba que se encontrara una partición que el router jamás podría evaluar |
| **P-7** | **El producto no cierra el bucle** | No persiste de manera completa resultados y creencias, así que el aprendizaje no se realimenta de producción. **Es el último de esta familia que queda**, y conviene mirarlo con lo aprendido: P-3, P-5 y P-6 resultaron ser todos la **misma forma** |
| ~~P-8~~ | ~~Promoción sin incertidumbre~~ | **CERRADO 2026-08-28.** Bootstrap **pareado** sobre el holdout (1.000 remuestras, 95%, semilla fija) y el criterio es el **borde inferior**. Comparar dos puntos no era una guarda: un candidato que gana por 0,001 gana por ruido la mitad de las veces, y promovido queda como incumbente que el ciclo siguiente debe superar — el error **se heredaba**. `test_science.py` §29 |
| ~~P-9~~ | ~~Repetir consolidación reaplica historia~~ | **CERRADO 2026-08-28**, y salió un segundo defecto tapado por el primero: el peso se redondeaba al **serializar** y no al aplicar, así que **lo firmado no era lo que decide**. El bundle lleva marca de agua firmada de lo absorbido. `test_science.py` §28 |
| ~~P-10~~ | ~~Flags declarativos del dial A0–A3~~ | **CERRADO 2026-08-28** para `theta_may_learn_online`: `serve.py` envuelve el request entero y `Plasticity.apply` levanta ahí adentro. Se cumplía **por casualidad** —`apply` sólo se llama offline— y una invariante casual la rompe el próximo cambio. **Falta el sellado de A3**, que sigue declarado y no impuesto. `test_science.py` §27 |
| ~~P-11~~ | ~~Separar producto de banco en `lab/app/`~~ | **VERIFICADO 2026-08-28**: ningun modulo del producto —`serve`, `router`, `rules`, `beliefs`, `policy`, `assurance`, `decide`, `contracts`, `probe`, `features`— importa `grading`, `runner`, `metrics` ni `corpus`. La regla se cumple hoy. Lo que falta no es la separacion sino la **mudanza fisica**, que va con `A-3` |

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
| **D-1** | **Cuándo parar de iterar** | Un tope constante en código o el modelo, que corta emitiendo una respuesta sin `tool_calls`. Las dos son flujo de control decidido fuera de la capa de decisión | **MEDIDO 2026-08-28, las dos mitades.** El premio: **33% del gasto es evitable** a igual utilidad — 49% en `dag_strategy`, **0%** en `map_reduce`, cuyo fan-out lo fija el código. La señal: `barren_peak` da **1,17 en la réplica barata contra 2,28 en la cara**. Corrección de lo que decía este renglón: las señales **no** estaban registradas — `barren_searches` era un medidor que se reinicia y la fila guardaba el valor final; `stall_warnings` sólo incrementa en variantes con contabilidad y **todo estudio corrió en `basic`**. Arreglado. **Falta la regla**: umbral, imponerla en los brazos con bucle, medirla contra λ |
| **D-2** | **Qué herramienta sigue** | El modelo, en cada vuelta | Es P-2c, y **ya no está bloqueado**: la secuencia se registra y la tesis quedó **establecida** (`p = 0,0078`). Lo que falta no es evidencia sino **rango**: una asociación medida sobre 3 celdas de 13 no llega a `OBSERVED`, y el retículo no tiene casillero por debajo (ver P-2d) |
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

## 1a. La fase de entendimiento: la mitad que falta (idea del autor, 2026-08-28)

**El diagnóstico que la pide.** S-3 midió que el acoplamiento es propiedad de
**(pregunta × material)** y que todos los ejes computables son función del material solo.
Falta la mitad de la información, y la mitad que falta es **qué exige la pregunta**.

**Y la calidad depende de eso, no sólo de la respuesta.** Que conteste **TODAS** las
direcciones y **TODOS** los nombres es un requisito real y medible — pero *no siempre es
necesario*. Hoy nada en el request lo declara, así que la cobertura se persigue igual en
tareas que no la piden y se paga sin comprarse nada.

**Corrección importante sobre la forma de esa demanda (autor, 2026-08-28).** No es un flag
que alguien pone: **es implícita en la forma del pedido**, y **no es binaria**. «Listame las
direcciones» significa *todas*; **«¿cuál fue el arma homicida?» espera exactamente una**, y
ahí la exhaustividad no aplica.

Lo que la fase tiene que tipar es la **cardinalidad de la respuesta**, y cada valor falla
distinto:

| forma del pedido | qué se espera | cómo falla | ¿exhaustividad? |
|---|---|---|---|
| **singular** — «cuál fue el arma» | exactamente una | ambigüedad, varias candidatas | **no aplica** |
| **enumerativa** — «listame los nombres» | todas | incompleta | sí, y es el *default* |
| **agregada** — «cuántos X» | un número | mal contado por cobertura parcial | sí, para poder contar |

Confundirlas tiene consecuencias opuestas: forzar cobertura sobre una singular **paga de
más por nada**, y no forzarla sobre una enumerativa **entrega algo incompleto que parece
correcto**. El trabajo de la fase no es cazar declaraciones excepcionales: es **hacer
explícita y tipada una demanda que el pedido ya trae implícita**.

**Y la consecuencia operativa es dura.** Una enumeración que contesta con un subconjunto
**está mal**, y en producción nada lo detecta. En el banco sí se ve —el F1 contra gold
castiga la respuesta incompleta— pero eso es una propiedad del banco, no del producto: sin
gold, la única forma de saber que una respuesta está completa es el contrato. Es
exactamente `C-COMPLETE`, y su **dominio no lo declara el llamador: lo implica la forma de
la pregunta.**

**Lo que el producto tiene hoy es del tamaño equivocado.** `FeatureExtractor._derive` le
pide al modelo **un solo float**, `coupling`. Eso es pedirle una **conclusión** —«¿está
acoplada?»— cuando lo que el modelo está en posición de reportar es una **observación
sobre la pregunta**. La conclusión le toca a la regla, que es la que además tiene los ejes
del material.

**La capa congelada ya tenía la forma correcta.** `legacy/agentic/understand.py` emite un
`UnderstandResult` con campos **tipados de vocabulario cerrado**: `followup_type:
Literal["standalone","drill_down","expansive"]`, `complexity: Literal["simple","moderate",
"complex"]`, `needs_decomposition: bool`, `key_terms`, `entity_types_filter`. Nada de prosa
libre — enumeraciones declaradas, que es la única forma admisible bajo las reglas de este
repo.

| # | Qué | Por qué |
|---|---|---|
| **U-1** | **Fase de entendimiento que emite DEMANDAS tipadas**, no conclusiones: `requires_exhaustive`, `needs_decomposition`, `followup_type`, y las que el registro justifique | Es la mitad que S-3 declaró faltante. El modelo lee la pregunta; eso es lo único que puede aportar y ningún eje del material lo suple |
| **U-2** | Que **la regla** combine demanda × material | Hoy se le pide la conclusión al modelo. Con U-1, `requires_exhaustive` + cardinalidad alta ⇒ **cobertura**; puente verificado + no autocontenida ⇒ **acoplamiento**. Eso resuelve los 4 falsos positivos de C4 sin heurísticas nuevas |
| **U-3** | Entran como **`ELICITED`**, y eso no se negocia | El modelo lee la pregunta: no puede superar ese rango. Por lo tanto **no pueden gatear una acción irreversible**, que es correcto |
| **U-4** | Pero algunas se **verifican después** | `requires_exhaustive` es exactamente lo que C-COMPLETE verifica contra la respuesta (`CONTRATOS.es.md` §2). Una demanda declarada y después verificada es el único camino por el que podría promoverse |
| **U-5** | **Medirla contra λ**, como todo | Cuesta una llamada por request. P16c y P17c midieron que el costo es lo que mata: una fase siempre-encendida entra al registro por esa puerta |

**Y cierra un círculo que estaba abierto**: la celda C4 no necesita acoplamiento sino
**cobertura**, y con U-1 eso deja de ser una excepción cableada a mano para pasar a ser
**una demanda que el request declara**.

---

## 1b. REC — implementado, diseñado, **sin registrar y sin medir**

`rec.py` (F3) y `certify.py` (F4) corren y tienen tests. `PATRON_REC.es.md` §11 deja seis
hipótesis falsables escritas y dice de ellas, textual, que **«no están preregistradas
todavía»**. §12 deja el diseño: siete brazos, métricas primarias y secundarias, y la
condición de datos. Nada de eso se corrió.

O sea: REC está en el estado que las reglas del repo llaman deuda — **existe en el
ejecutable y no tiene medición**. No es lo mismo que «declarado, no medido» (eso sería
peor), pero tampoco alcanza para que entre al paper.

| # | Qué falta | Detalle |
|---|---|---|
| **REC-1** | Preregistrar las seis hipótesis, con fecha | Están escritas en §11 y explícitamente sin registrar. Registrarlas es gratis y es la condición para que el resultado cuente |
| **REC-2** | Congelar política, presupuesto, umbrales, candidatos y regla de decisión | §12 lo exige **antes** de generar el mundo final. Congelar después es elegir la valuación viendo los números |
| **REC-3** | Generar el mundo final, recién entonces | `gold_transfer` queda **reservado para diagnóstico** por decisión del propio diseño. El resultado necesita mundos nuevos |
| **REC-4** | Correr los siete brazos | mejor fijo factible · siempre-`react` · router P15 congelado · eje nuevo sin REC · sonda fija · REC completa · REC sin costo de sonda (ablación). Es caro, y compite por cuota con P17 |
| **REC-5** | Corpus independiente del generador actual | §12 lo pide explícitamente para una afirmación doctoral. Es el mismo M-4 |

**Y un problema del diseño que apareció hoy y hay que arreglar antes de correr.** Uno de
los siete brazos es **«router P15 congelado»**, pensado como el baseline contra el cual
REC demuestra que repara. Pero ahora está medido que en ese router **la regla de selección
no dispara nunca** — pre-empatada tres veces, y sólo la tercera era nuestra. Comparar REC
contra ese brazo no mediría «REC repara lo que la selección no resuelve»: mediría «REC le
gana a un router al que nunca lo dejaron seleccionar», que es un resultado mucho más
chico y fácil de malinterpretar como si fuera el grande.

El arreglo es de una línea de diseño y cuesta nada ahora: el baseline tiene que ser **el
router con detectores honestos y el ciclo de dos pasos**, o sea el de P17. Lo que implica
que **REC va después de P17, no en paralelo** — y esa dependencia no estaba escrita.

---

## 2c. Lo que faltaba en esta lista (agregado 2026-08-27 al repasarla)

**La más grande, y no estaba escrita en ningún lado como pendiente.**

| # | Qué | Por qué importa |
|---|---|---|
| **A-1** | **Arrancar el producto: el motor nuevo no existe** | Es el objetivo declarado del repo — «el producto es el motor MAPO, y todavía no existe como tal; se construye a partir de lo que el banco pruebe». Todo lo demás de esta lista lo sirve, y sin embargo el ítem no estaba. Espera a que el registro esté maduro, que hoy significa: P16 cerrado, P17 corrido, y una decisión sobre si la selección paga |
| **A-2b** | **Cosecha de `legacy/`, con la reserva de cada una** | **`context_guard.py` — el mejor candidato.** Vigila el crecimiento del contexto entre iteraciones y, al cruzar un umbral, **desaloja** el `ToolMessage` viejo más grande y lo reemplaza por un hallazgo enfocado en la consulta. Tiene la forma correcta —**incondicional, desde el entorno**, o sea `managed` y no `cognitive`— y ataca justo la variable dominante: es un mecanismo que decide **qué evidencia sobrevive** hasta la llamada que responde, que es literalmente M-2. **La reserva**: `GROWTH_GAP_THRESHOLD = 20_000` y `KEEP_RECENT_MESSAGES = 6` son Constant Soup, y son exactamente la clase de constante que D-5 dice que hay que **aprender por dominio** en vez de copiar. Se porta el mecanismo, no los números.<br><br>**`hyde.py` — SE USA (decisión del autor, 2026-08-27).** Con una reserva que no cambia la decisión y sí cambia qué se puede afirmar: Su valor depende de un recuperador real sobre un índice real. En este banco la recuperación está **simulada a recall y precisión medidos**, así que la brecha semántica que HyDE tiende puede sencillamente no existir acá — y medirla igual sería repetir §4.14, *medir la herramienta fuera del régimen donde el problema que resuelve existe*. Portarla al **producto** es defendible; **medirla en el banco** puede no significar nada.<br><br>**`blackboard.py`** — ya está reimplementado en `dag_strategy`; no hay nada que portar.<br><br>**El prompt `proved`/`insufficient`/`hypothetical` (`agent_config.py:392`) — NO.** El modelo como juez de su propia suficiencia. |
| **A-2** | **Decidir qué se porta de `legacy/`** | La capa congelada resolvió cuatro cosas que el banco nunca tuvo que modelar: búsqueda sobre índice real, scoping por permisos, citas verificadas contra el índice, y streaming. `legacy/README.md` es lectura obligatoria antes de portar cualquier pieza, pero **no hay una decisión escrita de qué entra y qué no**. **Primeras dos entradas de esa decisión (2026-08-27)**: `hyde.py` **sí** — alucina en el canal de la consulta, donde una alucinación no puede volverse afirmación, y es el complemento del anti-RAG; el prompt de `agent_config.py:392` que le pide al modelo declarar el contexto `insufficient` **no** — es el modelo como juez de su propia suficiencia |
| **A-3** | **Separar producto de banco antes de portar, no después** | Es P-11 mirado desde el otro lado: si el motor nuevo arranca copiando `lab/app/` tal como está, se lleva el banco adentro y la mezcla vuelve el día uno |

**Riesgos concretos que nadie estaba mirando.**

| # | Qué | Por qué |
|---|---|---|
| **R-1** | **Verificar el replay sellado después de la migración de caché** | M4 mudó el caché a directorios con namespace por cuenta (`7102 → 7102, sin pérdidas`). El modo sellado convierte un miss en **error duro**, así que es el detector natural de que algo se perdió — y no se volvió a correr desde la migración. Es barato y es la única prueba de que la grilla congelada sigue siendo replayable |
| **R-2** | **Celdas † de la grilla congelada `gpt-5-chat`** | Quedaron documentadas como pendientes cuando se congeló el primer modelo. Si el brazo multi-modelo se usa para algo, esos huecos son parte del argumento |
| **R-3** | **Barrer el paper por «declarado, no medido»** | Regla propia del repo: lo que esté así **es deuda, y se implementa o se saca**. Nunca se hizo el barrido completo, sólo se corrigió lo que fue apareciendo |
| **R-4** | **`lab/ui/index.html` sin explicar** | Aparece sin trackear en el árbol y no lo escribí yo. O se adopta con su propósito escrito, o se saca — un archivo huérfano en el repo es una pregunta que alguien va a hacer |
| **R-5** | **11 commits locales sin pushear** | Por regla no se pushea sin confirmación, y está bien. Pero el estado «hay N commits que sólo existen en esta máquina» es un riesgo real que conviene tener a la vista |

---

## 2d. Lo que apareció al aplicar B2 (2026-08-27)

**Tres sitios construían el payload de features a mano, y dos descartaban el campo.**
La falla cerrada de `has_runtime_detector` los encontró **antes de gastar un token** —
P17 murió al instante con 0 tokens en vez de correr 14M midiendo mal.

| sitio | qué pasaba | veredicto |
|---|---|---|
| `runner.py:255` | arma un payload a mano y **omitía `has_oracle`** | bug, arreglado |
| `serve.py:173` | el mismo payload, la misma omisión | bug, arreglado |
| `serve.py:91` | `has_oracle = bool(self.oracle)` | **CORRECTO, y hay que decir por qué** |

**El tercero no es un bug y la distinción importa.** En el producto, `oracle` es *«un
oráculo de coincidencia exacta, cuando el llamador tiene uno; su presencia es lo que hace
admisible a la cascada»* — o sea un criterio de verificación **que aporta el llamador**.
Ahí `bool(oracle)` **es** el detector de runtime, honestamente.

> **El producto siempre tuvo la semántica correcta. El banco fue el que rompió la
> distinción**, reusando el mismo campo para el gold — y de ahí salió la pre-empción que
> impidió medir selección durante toda la investigación.

| # | Qué queda | Costo |
|---|---|---|
| **X-1** | Un solo constructor `task → payload de features`, en vez de tres a mano. Los tres eran la misma idea escrita tres veces, y dos ya se habían separado | refactor, chico |
| **X-2** | El ledger de costo **no es convertible a plata**: la fila guarda `cost_tokens` total sin separar prompt de completion, y no hay tarifa registrada en ningún lado. P16 fueron 1.938 llamadas y 13,95M tokens y no se puede decir cuánto costó | chico, y hace falta para hablar de costo en serio |

---

## 3. Code review — MEDIUM abiertos

Del bloque de `historico/code-review-2026-08-27.md`. Los bloques CRÍTICO y HIGH están aplicados;
de los MEDIUM se aplicaron M2, M4, M5, M6, M7, M9, M12, M19 y —el 2026-08-27— **M3, M11,
M17 y M18**. **Verificar antes de arreglar**: esta tabla se armó por grep y alguno puede
haberse cerrado de rebote.

**Los que quedan esperan a que P16 cierre, y por una razón concreta**: `_analyze_p16.py`
llama a `router.plan`, que pasa por factibilidad y por reglas. **M10** (el `GIST_CHARS`
inflado) y **M8** (la constante de supresión de sonda) cambiarían qué paradigmas se podan
y qué regla dispara, así que moverlos ahora reescribiría el veredicto congelado por debajo.
**Todos aplicados el 2026-08-27.** Los que tocaban la ejecución de los paradigmas
—M1, M13, M14— y los que pasaban por `router.plan` —M8, M10— se hicieron **matando P17
a los 46 filas** en vez de dejarlos esperando otra corrida de cuatro horas. Verificado
después: el mecanismo de P17 no se movió (cascada 2/26, catorce esperando la sonda).

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
| M17 | `runner.py` / `main.py` | Verificar que ningún default reintroduzca el brazo retirado, que por decisión no se corre nunca más |
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
| ~~W-1~~ | **HECHO 2026-08-28.** El teorema es una identidad y no se puede falsar; los terminos nunca se separaron porque el margen fue 0 en todas las tareas. Escrito en `paper-en.md` y `paper-es.md`, en la misma posicion de cada uno |
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

- **Tools declaradas no son tools usadas** (2026-08-27). Medido en este banco: cuatro
  herramientas de memoria de trabajo expuestas sobre 28 filas dieron un note, una
  compactación y cero planes. *Exponer una capacidad no es proveerla, y ofrecerla no es
  medirla.* Todo lo que enriquezca el contexto va **incondicional desde el entorno**
  (forma `managed`), no ofrecido al modelo (forma `cognitive`). Si además se puede
  **fusionar** en vez de reemplazar, el modo de falla queda acotado a costo.
- **Ejecutado primero, teorizado después.** Nada entra al paper sin implementación que lo
  corra. Si está en el paper como «declarado, no medido», es deuda: implementarlo o sacarlo.
- **Nada se afirma sin medida, cita o rótulo de hipótesis** (G3). Las novedades se enuncian
  como CONJUNCIÓN, nunca como partes (`GATE.md` §8quater).
- **Antes de gastar un token**: `test_science` + `test_consolidation` en verde, `corpus/verify.py`,
  predicciones falsables registradas con fecha, `repeat ≥ 3`, piso de ruido POR CELDA,
  decisiones sobre la brecha **neta**.
- **Ninguna referencia a marcas o productos anteriores**, en documentos ni en código.
- **Nunca hacer push sin confirmación del autor.**
