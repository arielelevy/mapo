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

## Qué sigue, en orden

> **El criterio del orden es uno solo: qué desbloquea más cosas por token gastado.** No es
> importancia — `A-1` (arrancar el producto) es lo más importante de la lista y va último,
> porque el autor decidió que se construye a partir de lo que el banco pruebe.
>
> **Sincronizado 2026-08-28.** Los tres primeros de la versión anterior ya se hicieron: la
> regla de parada está impuesta, `C-COMPLETE` está cableado, y de los dos lo que queda es
> **correrlos**. El cuello se movió de «no está construido» a «no está medido».

**Ahora, y no cuesta tokens**

1. **`X-4d` — descontar la declaración de tools del costo comparado.** El único pendiente
   que puede **cambiar un resultado ya publicado**, y sale de replayar sellado el registro y
   recomputar. Su primera corrida quedó retirada: partía de un sobrecosto estimado por
   `calls` que resultó falso, y el recorte de piso inflaba los ratios.
2. **`S-4` — el techo del acoplamiento.** Tres opciones de diseño escritas, ninguna elegida.
   Bloquea el cierre de la sonda, y es el único de los tres «ahora» que necesita una
   **decisión del autor** y no trabajo.
3. **`U-4` — que `coverage_demanded` dispare el contrato.** Hoy lo dispara que la tarea
   declare `domain_keys`, que coincide para `C9` y no para `C2`/`C4`. Cablearlo es la parte
   fácil; lo que sigue abierto es que en `C2` el dominio es **semántico** y enumerarlo **es**
   resolver la tarea.

**Las corridas, en orden de lo que decide más por token**

4. **`P20` — la regla de parada, con el factor encendido.** El premio está medido (**33%**
   del gasto) y la señal también (`barren_peak` 1,17 contra 2,28). `P20b` es la que puede
   matarla: si la utilidad cae más que el piso de ruido, ahorrar tokens contestando peor no
   es ahorrar.
5. **`U-6` — P19 sobre `C9`.** `P19d` es un control que **puede matar a la celda**: con
   `width=4` el dominio declarado y las unidades en alcance coinciden, así que si C9 se
   comporta igual en `w=4` y `w=48`, la distinción no compra nada. Corpus verificado 38/38.
6. **`P21` — ofrecer `read_all` en `basic`.** No existía en la variante de **todos** los
   estudios, y nadie lo decidió midiendo. `P21a` puede volverlo irrelevante: si los modelos
   lo ignoran, queda al lado de las tools de memoria de trabajo — ofrecidas y sin usar.
7. **`F-2` — descontaminar «el efecto `dag_strategy`».** La pizarra está soldada adentro de
   ese brazo, así que su ventaja mezcla dos cosas que nadie separó.
8. **`M-1` — el brazo en prosa (E1).** Implementado, sin correr, ~26 llamadas: el control
   más barato que queda.

**Lo que sigue abierto y no tiene camino escrito**

9. **`P-7` — el producto no cierra el bucle.** El último de la familia P, y conviene mirarlo
   con lo aprendido: `P-3`, `P-5` y `P-6` resultaron ser todos **la misma forma** — una
   capacidad completa que nadie podía usar porque el dato no llegaba a donde se decide.
10. **`K-6` — corpus con entidades de verdad.** Condición (a) para revivir el patrón de
    grafo, y donde vive el quinto punto ciego del corpus.
11. **`G-2` — la plataforma.** `ARQUITECTURA.es.md` propone la pila entera y **ninguna
    pieza está ejecutada ni medida**.
12. **`A-1` — arrancar el producto.** Lo más grande. Va después de que el registro madure,
    por decisión del autor.

**Y una que no es técnica**

- **`R-5` — 29 commits locales sin pushear.** Repo privado; no se pushea sin confirmación.

---

## Resumen — todo de un vistazo

`[x]` hecho · `[~]` empezado · `[ ]` no empezado — **59 abiertos · 16 en curso · 52 cerrados** (2026-08-28)

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
- [x] **K-8** · **`handoff` entra al catálogo como candidato nuevo**, con predicción registrada antes de correr como todos
- [x] K-3 · **la falsación de `graph_traverse` (P10a) sobrevive a su objeción más seria**: el índice está 100% anclado en el texto y las dos cadenas C3 están conectadas — la travesía tenía las aristas y aun así dio u=0,000. Riesgo de diseño registrado aparte: el índice **no exige** anclaje, así que otro corpus podría envenenarlo en silencio
- [x] **K-5** · `graph_traverse` **en `standby`**, no retirado, con sus dos condiciones de revival escritas en el ejecutable: (a) un corpus con resolucion de entidades real y (b) un indice con la disciplina de la sonda. La falsacion vale «donde resolver entidades es gratis», que no es lo mismo que «vale»
- [ ] **K-6** · **Corpus con entidades de verdad**: variantes de superficie, abreviaturas, anáfora, correferencia entre documentos. Sin eso, **ningún patrón de grafo se puede medir donde tiene sentido** — y es el mismo agujero estructural que el detector heredado del gold
- [x] **K-4** · **el catálogo vive en el ejecutable**: `CATALOG` con cinco estados —activo, retirado, standby, infactible, en revisión— cada uno con su **razón** y su **condición de revival**. `pointer_chase` y `graph_traverse` dejan de estar disponibles; el rechazo trae el porqué en vez de mandar a buscarlo a un documento
- [x] **K-1** · `plan_execute` **retirado** por decision del autor (2026-08-28). Vive en el `CATALOG` con estado `retired`, su razon y su condicion de revival, y `RETIRED` se deriva de ahi — no hay lista paralela que pueda driftear
- [x] K-2 · `map_reduce` **no** está dominado — gana una celda. Reemplazarlo por handoff cambiaría cobertura medida por un brazo sin medir: van **uno contra otro**, no uno en lugar del otro

**Mediciones**
- [ ] M-1 · brazo en PROSA (E1) — implementado, sin correr
- [x] **M-2** · **instrumentada, y el hallazgo es por qué faltaba** (lección 6.4). La retención —si la evidencia leída **sobrevive** hasta la llamada que responde— ya se registra por fila como ratio de caracteres. `basic` da **1,000** y `managed` **0,281**. Y en `basic` es 1,0 **por construcción** —no hay compactación— que es la variante de **todos** los estudios medidos: la medida no faltaba por descuido, **no tenía nada que decir donde se midió**. Medirla de verdad exige correr en `managed`/`cognitive`
- [ ] **M-3** · transferencia de θ entre familias de modelos — **y ahora está acotado qué se rompería** (`MODELO_Y_CONSTANTES.es.md`): los **mecanismos** son independientes del modelo por construcción; las **magnitudes** no. El 33% evitable **se encoge** con un modelo que para solo; el barrido de λ **se corre entero** y el orden de los brazos puede darse vuelta; las asociaciones de orden pueden desvanecerse por **falta de varianza de secuencia**, que no es lo mismo que falta de señal
- [ ] M-4 · corpus natural + segunda familia
- [ ] M-5 · C3 profundo en nano

**El catálogo confunde dimensiones ortogonales**
- [x] **F-1** · `Blackboard` extraído a `paradigms/blackboard.py` — comportamiento idéntico, suites en verde; **F-2 ya es formulable**
- [ ] **F-2** · medir `{blackboard, sin}` × `{react, dag}` en C2/C4 — **descontamina «el efecto dag_strategy»**
- [ ] **F-3** · HyDE como factor de pre-proceso — *decidido: se usa*
- [ ] **H-1** · portarlo como rama paralela fusionada por RRF, **no como herramienta**
- [ ] **H-2** · exponerlo como brazo `hybrid_hyde` — la dimensión ya existe en el banco
- [ ] **H-3** · medir `{hybrid, hybrid_hyde}` **con el costo cobrado** *(P16c: sin λ el número no significa nada)*
- [x] **F-4** · **escrito**: `PATRON_O_FACTOR.es.md`. La prueba es una — un patron se distingue por su ESTRUCTURA DE CONTROL DE FLUJO, y se decide con cuatro preguntas (cuantas llamadas y quien las decide; quien elige la proxima accion; si hay estado compartido y quien lo escribe; si un paso puede cambiar el plan). Contraprueba: si la diferencia se describe sin dibujar otro grafo de control, no es un patron. Incluye la clasificacion de todo lo que hay hoy y los tres factores que siguen **soldados adentro de un brazo**, que es lo que impide atribuirles nada

**«Anti-RAG» — la máquina existe (REC), le falta una pieza**
- [ ] **AR-0** · medirlo como **factor** `{con, sin} × {patrones}`, no plegado en cada patrón
- [x] **AR-1** · contratos de completitud — **implementado y cableado**: `C-COMPLETE` corre sobre la respuesta con el dominio declarado por el caller, y cada fila guarda su veredicto aparte de la utilidad. Su limite quedo escrito donde vive: a nivel prosa **no puede ver lo que sobra** —solo busca las claves declaradas— y detectarlo exigiria extraer entidades del texto, que es justo lo que no se acepta como sensor
- [x] **AR-2** · **cableado, y con una asimetria que lo hace mas que un cable.** `rec.diagnose` **busca** —prueba intervenciones hasta dar con la mas barata que cambie la decision— porque el registro no dice que falto. Un contrato rechazado **ya lo dice**: `C-COMPLETE` nombra las claves ausentes, `C-NUM` la ranura bajo el piso. Buscar donde ya hay respuesta no es redundante, es **peor**: la busqueda esta acotada a un esquema chico, asi que un deficit real fuera del esquema daria «no hay intervencion que lo cambie» cuando la hay. `deficit_from_contract` lo declara con `searched: False`. `test_science.py` §36
- [ ] AR-3 · predicción falsable antes de correr
- [ ] AR-4 · baseline honesto: contra HyDE y RAG plano, no contra nada

**El agujero aguas arriba de todo**
- [ ] **G-1** · **la ingesta no se mide** — y de las tres cosas que este renglón afirmaba, **una es falsa**: «independiente del patrón» quedó **refutado** por `G-3`, porque `graph_traverse` construye y persiste su índice **adentro del request**. Sigue en pie que es asíncrona y de una sola vez, y que por eso no contamina la comparación entre brazos — verificado sobre el registro. Lo que fija el espacio sigue sin medirse: `n_units`, la región, el denominador de cobertura, cuánto ve la sonda. Y su economía es otra: se amortiza sobre todas las consultas futuras, así que el resultado de λ **no le aplica**
- [x] **G-3** · **medido, y la preocupacion quedo refutada por el registro.** El mecanismo es real —`graph_traverse` construye y persiste su indice adentro del request, leyendo cada unidad con la llamada que REGISTRA lecturas, asi que la fila que lo paga carga `fraction_read` del corpus entero—. Pero **ninguna fila del registro lo ejercio**: las 6 filas del brazo tienen `fraction_read = 0,000` y costo 188-268 tokens porque el indice ya estaba en disco. La leccion 8.6 da `-0,241` con todas y `-0,242` sin el brazo. Nada que corregir; queda la regla `G-4`
- [ ] **G-4** · **regla de producto, ahora con la medicion que la respalda** (leccion 3.5): si la ingesta es asincrona, de una vez y compartida, **ningun paradigma deberia construir estado derivado propio adentro de un request**. Dos razones separadas: **economica** —el costo del indice cae sobre una fila arbitraria y promediar el brazo mezcla amortizar con responder— y **de instrumentacion** —construir lee, y leer se registra—. Falta implementarlo: levantar el indice de `graph_traverse` a la etapa de ingesta, que es tambien la condicion (b) de su revival en `K-5`
- [ ] **G-2** · `ARQUITECTURA.es.md` propone la pila entera (Docling, sensor de OCR, procedencia página+bbox) y **ninguna pieza está ejecutada ni medida**

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
- [x] **U-2** · **demanda × material como PRECONDICIÓN estructural** (lección 5.13). El primer intento fue una regla de `GATE` y **mataba a C2 entera** —exhaustiva y masiva, que es el caso que los paradigmas existen para resolver—. El error fue el **momento**: la regla corre antes de ejecutar, así que no puede saber si se cubrió; lo único conocible de antemano es la estructura (`TRAVERSES_SCOPE`). Así que **poda y no gatea**, y **no es eje del selector** —`O-4b` midió que la demanda no reordena—. Y no poda a cero: sin candidato que recorra, el EXPLAIN dice que **la precondición no se pudo imponer**
- [x] **U-3** · **DESCARTADO por medicion** (O-4b): elicitar la demanda cuesta una llamada por request y el ranking de paradigmas **no se mueve** contra su propio null (`p = 1,000` / `p = 0,447`). Si alguna vez se elicita, es para `C-COMPLETE` — no para el router
- [x] **U-4** · **el disparador es tipado y sabe cuándo NO corresponde** (`verify_coverage`, `test_science.py` §38). Son **dos** condiciones y ninguna alcanza sola: la tarea exige cobertura **y** su dominio es enumerable. Exigirla sobre un dominio `semantic` haría que el contrato **reemplace** al paradigma en vez de verificarlo (lección 8.7); sobre uno `from_scope` verificaría lo que se midió que no predice corrección (`+0,018`). Y `None` significa **sin contrato**, distinto de un contrato cumplido
- [ ] **U-6** · **correr P19** — predicciones a-d registradas en `README.md` antes de existir una fila. `P19d` es el control que puede matar a la celda: con `width=4` el dominio declarado y las unidades en alcance **coinciden**, asi que si C9 se comporta igual en w=4 y w=48, la distincion entre los dos dominios no compra nada y la celda solo mide ancho. Costo **sin estimar**
- [x] **U-7** · **resuelto entero.** El dominio lo declara el **caller**, igual que `irreversible`. Y la mitad que faltaba —qué terminal es una respuesta retenida— se resolvió con la propuesta del autor: **`retained`**, un cuarto terminal que **informa lo que falta** y **propone** reintentar. Lo que lo hace útil es que el contrato **nombra** el faltante: no «algo salió mal», sino «faltó Cora». Y el reintento es **dirigido** —sabe qué pedir— y **propuesto, nunca automático**: `P20` midió que una acción que el sistema puede repetir por su cuenta deja de ser control de flujo del código. Tope **1**, fijado por el código. Agotado, propone **aceptar incompleto sabiendo que lo está**, que es justo lo que sin contrato no se podía saber
- [x] **U-5** · **sin objeto**: medirla contra λ presupone un efecto de ruteo que O-4b midio que no existe, asi que el costo de la llamada no compite contra nada. Vuelve a tener sentido cuando `C-COMPLETE` este cableado (`U-7`)

**REC — implementado, sin registrar y sin medir**
- [x] **REC-1** · **preregistradas como `P22a`–`P22f`** en `README.md`, con fecha y con **numero**. La version en prosa no era un preregistro: «no supera costo y piso de ruido» no tiene una cifra adentro, y una afirmacion sin cifra se lee despues en la direccion en que hayan ido los datos. Con dos disciplinas que este registro ya pago: baseline el router de **P17** —no el de P15, cuya seleccion nunca dispara— y toda diferencia sobre **intervalo bootstrap pareado**. `P22f` (reproducibilidad) es la mas barata y va primero: si falla, ninguna de las otras cinco significa nada
- [ ] **REC-2** · congelar política, presupuesto, umbrales y regla ANTES del mundo final
- [ ] **REC-3** · generar el mundo final — `gold_transfer` está reservado a diagnóstico
- [ ] **REC-4** · correr los siete brazos *(caro; compite con P17 por cuota)*
- [x] **REC-0** · **desbloqueado: P17 cerró.** El diagnóstico era correcto —«router P15 congelado» es un router cuya selección **nunca dispara**, así que servía de baseline sólo para medir la cascada— y la condición que ponía ya se cumple: el baseline de REC es el de P17, con detectores honestos y cascada 2/26. **REC deja de estar bloqueado**; lo que queda de REC es correrlo (`REC-4`)

**Producto — capa de decisión**
- [ ] P-1 · que la sonda sense **recuperabilidad** (hoy sensa acoplamiento)
- [x] **P-2** · ~~sacarlo del camino activo~~ — **decisión revertida el 2026-08-27, y la revisión estaba mal planteada.** Lo demostrado es estrecho: el peso no puede mejorar la **selección de paradigma**, porque en el punto fijo es una transformación monótona de la tasa de victorias. Eso **no dice nada** sobre aprender asociaciones entre pares, que es a donde va (P-2c, P-2d, D-4). Y además ya gobierna algo: es el **reloj de decaimiento** con el que `consolidation.py:286` poda las stats sin episodios — nunca poda por peso solo, porque una stat con episodios es evidencia. Ese ciclo de vida —acotado, decae, piso, poda— es justo la maquinaria que una tabla de asociaciones necesita. **No se saca: se reusa.**
- [ ] P-2b · reintroducirlo como **detector de no estacionariedad** *(drift medido: 80%)*
- [x] **P-2c** · **ESTABLECIDA** con `P-2f` (`_analyze_p2f.py`): **3 de 13 celdas** tienen una transicion presente en todas las replicas exitosas y ausente en todas las fallidas, contra **mediana nula 0**, `p = 0,0078`. El `p = 0,055` anterior estaba medido con `n=3`, donde la **mediana nula era 7 de 13** — el criterio se satisfacia por casualidad. Con `n=9` el observado BAJA de 10 a 3 y el null cae a 0: lo que se cayo era el ruido. Debil y real: un corpus, un modelo, 3 celdas
- [x] **P-2f** · corrida completa: 13 celdas x 9 trials en `gold_p17b` (gemelo byte-identico, para no tocar el veredicto congelado de P17). **117 filas**, y el piso de `p` por celda bajo de `>= 1/3` —donde ninguna celda podia dar significativa aunque la senal fuera perfecta— a `0,008` en 10 de 13
- [x] **P-2d** · **resuelto, y el rango que faltaba no era un rango.** El reticulo ordena **como** se obtuvo una creencia; hacia falta ademas **sobre que es**. `Scope ∈ {REQUEST, POPULATION}` lo separa, y el piso de las acciones exige las dos cosas — asi la asociacion aprendida entra honesta como `COMPUTED` sobre `POPULATION` y queda **estructuralmente fuera de lo irreversible sin degradarle la procedencia**. `AssociationTable.as_beliefs()` la convierte, y afirma la **medicion** y no la recomendacion: el invariante «COMPUTED exige credencia 1,0» rechazo el primer intento —poner la fuerza como credencia— y tenia razon. `test_science.py` §37
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
- [ ] **A-1** · arrancar el producto — *el motor nuevo no existe*
- [ ] **A-2** · decidir qué se porta de `legacy/`
- [ ] **A-2b** · cosecha de `legacy/`: `context_guard` **sí** (mecanismo, no sus constantes) · `hyde` al producto pero medirlo acá puede no significar nada · el prompt de suficiencia **no**
- [ ] **A-3** · separar producto de banco ANTES de portar

**Apareció al aplicar B2**
- [x] **X-1** · un solo constructor `payload_for(task)` en `features.py` — los tres sitios lo usan
- [x] **X-3** · **cableado y medido: CERO.** El contador vive en la superficie (`malformed_json` y `dropped_items`, separados porque piden arreglos distintos) y lo anota `parsing.py`. Sobre el registro completo de `gold_p17` replayado sellado — **336 filas, cinco brazos** — no hay una sola malformacion. **Ningun paradigma pierde utilidad por el formato**; la pierde por la tarea. Y el cero significa cero: `test_science.py` §26 verifica que el contador se dispare y que **todo** sitio que parsea JSON pase la superficie
- [x] **X-4** · **cerrado.** El sobrecosto real es **6,7%** —`dag_strategy` 8,0%, `react` 4,5%, `rewoo` 0,0%— y no distorsiona la comparacion: `X-4d` lo verifico descontandolo y ningun veredicto se movio. La primera estimacion, por `calls`, era falsa: de 27 sitios que llaman al modelo **uno** pasa `tools`, y el absurdo lo delato —en 7 celdas daba mas declaracion que prompt entero
- [x] **X-4a** · **contestado: lo lazy NO aplica acá.** El patrón de 2026 —diferir las definiciones detrás de una tool de búsqueda— reporta 80-95% de ahorro y mejoras de acierto (49%→74%), **sobre catálogos de 100+ tools**; la regla publicada es que por debajo de ~10 el sobrecosto de la búsqueda no se paga. MAPO tiene **4** en `basic` y **10** en `cognitive`, y el gateo por variante **ya es** divulgación progresiva. Aplicarlo acá agregaría una llamada por request para ahorrar 528 tokens
- [x] **X-4b** · **la vía no existe, y por aritmética** (lección 5.11). El caché **sí** cubre `tools` —«both the messages array and tool definitions», documentación de primera mano— y **ya está encendido por defecto**: no hay directiva que mandar, así que esa mitad del pendiente era falsa. Pero exige **≥1.024 tokens iniciales idénticos** y el prefijo estable entero mide **~567** (533 de tools + 34 del contrato): **nunca llega**. Y el prompt arranca con `Task: {question}`, o sea lo variable primero, justo al revés de lo que la documentación pide. Dentro de una tarea sí pega y es gratis; ahora además se **mide** (`provider_cached_tokens` desde `prompt_tokens_details`), que era lo único que faltaba
- [ ] **X-4d** · **el prompt pone lo variable primero**, y eso es gratis de dar vuelta: `Task: {question}` va antes del contrato, así que ningún prefijo sobrevive entre tareas. Poner contrato y herramientas adelante no cambia lo que el modelo lee, sólo el orden — **pero cambia el payload, así que es un FACTOR** con predicción registrada, no una limpieza. Sin llegar a 1.024 tokens no compra caché igual, así que va junto con lo que engorde el prefijo estable, no solo
- [~] **X-4c** · **implementado como FACTOR y con predicción registrada** (`terse_tools`, P24a-d en README). Las descripciones son **55% del payload** de la spec y son lo único que el modelo lee para decidir QUÉ tool usar. La forma corta conserva lo que **discrimina** y tira la prosa que instruye —andamiaje por prompt, que este banco ya midió que no compra nada—: **−38,4% de la spec, −2,57% del prompt**. Y una decisión tomada antes de gastar: **2,57% está por debajo del piso de ruido de casi toda celda**, así que el factor viaja con otra corrida y **no se le encarga una propia**. Lo que ese N sí resuelve es el riesgo (P24c/P24d), que es el número por el que existe
- [x] **X-4d** · **medido con el sobrecosto real: no se mueve NADA.** Sobre `gold_p17` replayado sellado, descontando por `tooled_calls`, el mejor fijo es el mismo en los cuatro lambda y la brecha de oraculo es **identica a cuatro decimales** (0,3333 · 0,1750 · 0,0000 · 0,0000). La razon es concreta: `rewoo` es el **piso de costo** y carga **cero** declaracion, asi que descontar no mueve el piso y los ratios casi no cambian. **Ningun resultado publicado esta en riesgo**, y con eso el resto de X-4 —cache de prompt, acortar descripciones— es **optimizacion y no correccion**: baja su urgencia, no su valor
- [x] **X-5** · **el presupuesto ya no está sólo en tokens** (lección 5.9). Cerrada por `X-5a` (λ sobre plata), `X-5b` (el par es la acción), `X-5c` (capacidad como precondición) y `X-5f` (dos modelos). Lo que el banco no podía ni preguntar —«un modelo 10× más caro que necesite 37× menos tokens, ¿sale más barato?»— ahora lo pregunta la aritmética antes de gastar un token
- [x] **X-5a** · **λ barre sobre plata** (`Tariff`, `app/tariffs.py`, lección 5.7). El mejor fijo **no cambia** —misma unidad, todo λ, los dos corpus— así que nada de lo publicado sobre *quién* gana se mueve. Lo que se mueve es **cuánto**: la ventaja del más barato se parte al medio (`react` **26,0× → 11,6×**) porque el más barato es el que emite salida, 8,1% contra 0,3%. El arancel es **referencia, no medición**, así que se barre salida/entrada de ×1 a ×32: el orden **aguanta entero** y ×1 reproduce los tokens exacto. Se puede afirmar lo invariante, no un número en dólares. Y cayeron dos guardas: el clamp `max(1.0, cheapest)` —el mismo de `X-4d`— y `bounded()` sin rango semiabierto
- [x] **X-5b** · **el modelo es ACCIÓN** (`app/models.py`, `feasibility.admissible_pairs`, `Plan.model`, §44, lección 5.9). El espacio de decisión es el par `(modelo, paradigma)` y la factibilidad poda **pares** con dos cotas nuevas: **ventana** —un presupuesto no agranda una ventana, manda la menor— y **plata**. La trampa evitada: el modelo NO entra al vocabulario de región, que fue el mecanismo de `P15`
- [x] **X-5c** · **la calidad es precondición, no presupuesto** (`Capability`, `AssuranceProfile.min_capability`, §44). Piso **ordinal** —un cardinal invitaría a compensarlo con costo— y **no hizo falta mecanismo nuevo**: `required_floor` ya elevaba toda acción irreversible a A3, así que el piso en A3 **es** el que impide rutear lo irreversible al modelo barato porque salga la cuenta. Le había puesto piso a A2 también y **lo saqué**: era política mía sin medida, y obligaría a pagar 25× en cada request contable — queda como `X-5g`
- [x] **X-5d** · **la comparación entre modelos va al ANÁLISIS** (§42, `load_rows`). La guarda levanta si un archivo mezcla decodificaciones y **está bien**: promediar entre modelos no mide un paradigma, mide el modelo. El estudio multi-modelo se arma uniendo estudios por modelo. Queda escrito para que nadie «arregle» la guarda creyendo que estorba
- [x] **X-5e** · **contestada con lo ya pagado** (lección 5.4): la hipótesis del autor se confirma **condicionada a la dificultad**. En `gold_deep` el modelo caro usa **0,81×** los tokens del barato; en `gold_v2`, **1,90×**. Puntos de equilibrio **1,24×** y **0,53×** por token. Sobrio: aun donde gana, 1,24× no alcanza para pagarse — y eso **fortalece** el caso del ruteo, porque el uso correcto del caro es exactamente donde gana. Convertirlo a plata es `X-5a`, no esto
- [x] **X-5f** · **dos modelos eligiendo por caso** (`Router.plan(models=...)`). Orden de cotas: **dial primero, plata después** — al revés, un descuento compraría permiso. `A3 + USD 0,02` **se abstiene** en vez de bajar de modelo, que es el caso que prueba el orden. Sin catálogo el plan dice `model=''`, que es el régimen medido hasta hoy: decirlo vacío es distinto de mentir un nombre por omisión
- [ ] **X-5g** · **¿necesita A2 un piso de capacidad?** Es empírica y hoy está en `None` a propósito. Ponerle `DEEP` obliga a pagar 25× en cada request contable; no ponérselo admite el modelo barato donde hay que rendir cuentas. Se decide midiendo la tasa de error del barato al piso de procedencia de A2, no argumentando
- [ ] **X-5h** · **tres de cinco brazos no proyectan tokens** (lección 5.10), así que la cota de plata **no los evalúa** y lo declara (`money_unevaluated`). `dag_strategy` proyecta 165 llamadas y 0 tokens; `react`, 0 llamadas y 30.000 tokens. Llenarlo pide un modelo de tokens por paradigma declarado —como `COST_PRIORS`— o aceptar que la cota cubre sólo a los que proyectan. **No se inventa**: hoy dice qué no evaluó
- [x] **X-2** · **el diagnostico estaba mal y el arreglo era otro.** El split prompt/completion **existia** en `Usage` desde siempre; lo que pasaba es que la FILA guardaba solo el total y la informacion se tiraba al escribir. Ya lo lleva. Y el gasto acumulado esta medido desde el cache (`_analyze_spend.py`): **66,4M tokens**, de los cuales la salida es el **1,7%** — eso valida que barrer lambda sobre el total sea un proxy razonable ACA. La tarifa se declara por entorno (`MAPO_PRICE_IN_PER_M` / `_OUT_PER_M`) y **no se inventa**: un precio inventado produce un numero que parece una medicion

**Riesgos que nadie estaba mirando**
- [x] **R-1** · **CONCLUIDA A ESCALA** (`_replay_full.py`): **390 de 390 filas** de `gold_p17` replayadas selladas por el camino del runner, **0 llamadas vivas** y **0 discrepancias** en utilidad, respuesta y costo. No 27 celdas: el registro entero. La causa del fracaso anterior era que la fila no decia con que modelo se produjo; cerrado estampando la huella, con guarda de mezcla (`test_science.py` §25)
- [ ] R-2 · celdas † de la grilla congelada `gpt-5-chat`
- [x] **R-3** · **barrido hecho, y encontró lo más caro que había.** El paper decía que `P8` **no había corrido**, y había corrido: 32 filas en `gold_holdout` sin veredicto computado desde el 2026-08-26. Evaluada como estaba enunciada, **dos de cinco no transfieren** y la regla de decisión registrada dispara: los veredictos por celda pasan a **corpus-locales**. Corregido en los dos papers
- [x] R-4 · `lab/ui/index.html` — **es la UI de prueba del autor**; se adopta
- [x] **R-5** · **pusheado.** `origin/main` al día; el respaldo con los 33 mensajes originales queda en `respaldo-pre-squash-2026-08-28`

**Decisiones dinámicas que hoy no gobierna nadie**
- [x] **D-1** · **medido de punta a punta.** El premio: **33% del gasto evitable** a igual utilidad. La señal: `barren_peak` **1,17 contra 2,28**. La regla: impuesta por código. Y **P20 corrida**: `P20a` **REFUTADA** —baja 2,6%, no ≥10%— porque `P20d` también lo es: tras el rechazo el modelo **re-emite la búsqueda el 69%**. `P20b` **CONFIRMADA**: cortar **no cuesta utilidad**. La corrección que se sigue es estructural y vive en `D-1c`
- [ ] **D-1c** · **rechazar no es quitarle la decisión al modelo: quitársela es no ofrecerle la herramienta.** Medido en `P20d`: el modelo esquiva el rechazo reintentando con otras palabras el **69%** de las veces, así que la regla le agregó una vuelta en vez de quitar el desperdicio — y eso deja el flujo de control donde estaba, que es lo que el invariante prohíbe. La corrección: pasado el límite, las búsquedas **salen de la lista de specs** de las llamadas siguientes. `P20b` ya establece que cortar **no cuesta utilidad**, así que el riesgo no es contestar peor — es que el 33% siga sin ser alcanzable
- [~] **D-1b** · **`read_all` no existe en `basic`**, que es la variante de TODOS los estudios medidos: el modelo nunca pudo pedir el material entero aunque entrara comodo en su presupuesto, y eso **nadie lo decidio midiendo** — es consecuencia de en que lista quedo la tool. Expuesto como factor `offer_read_all`, apagado por defecto, ofreciendolo **sin** arrastrar el resto de la contabilidad. La guarda de tamano ya estaba y es lo que lo hace seguro. **P21a-d registradas**; falta correrlo
- [x] **D-2** · **desbloqueado y corrido: 93 misses → 0.** La causa era exactamente la de `R-1` — el script reconstruía sólo `results_dir`, así que corría con la huella del **modelo congelado** y fallaba el 100% de las claves sin que nada lo dijera. Con los ajustes correctos: **102 de 112 celdas** reconstruidas, **0 misses sellados**, 0 fallos de paradigma, **0 tokens**. Las secuencias están materializadas y las transiciones contadas por brazo — `rewoo` repite búsqueda (`search→search` 35), `dag_strategy` alterna (`keyword_search→read` 54)
- [ ] D-3 · la descomposición en DAG
- [~] **D-4** · **implementado** (`app/paradigms/handoff.py`, `test_science.py` §39) y **P23a-d registradas antes de correr**. Alcances independientes —de la **vista**, no del prompt: un agente no puede leer afuera porque las unidades **no están**— y transferencia que **autoriza el código**: el agente propone (`ELICITED`, es su lectura) y la regla exige que lo que pide exista **literal** en un alcance que todavía no corrió (`COMPUTED`). Con la lección de `P20` adentro: **no hay herramienta de transferencia que se le pueda rechazar** — la acción no existe. Falta correrlo
- [x] **D-5** · **la «Constant Soup» tiene inventario** (`MODELO_Y_CONSTANTES.es.md`): seis constantes **atadas al modelo** con cómo re-derivar cada una, y siete que **no** lo están, con por qué. La prueba: *¿su valor correcto cambiaría si el mismo corpus lo corriera otro modelo?* **Derivarlas** es trabajo distinto (`D-5b`)
- [x] **D-5b** · **derivadas** (lección 5.6): los `COST_PRIORS` **erran 2-7×**, y lo primero fue averiguar **quién consume el número** porque la respuesta obvia era la equivocada — **no** gobiernan la poda, gobiernan **el orden de la cascada**. Con `reflection` inflado 3,2×, la cascada **nunca lo prueba primero** aunque sea de los más baratos. Cambiar la referencia de la escala es `D-5c`
- [x] **D-5c** · **resuelto, y era peor de lo enunciado.** El pendiente decía que la escala estaba anclada a `direct`. Buscando dónde cambiarla apareció que **el costo medido nunca superseder­ía al prior**: el comentario del router lo prometía —«measured mean_cost supersedes them once theta has data»— y `mean_cost` sólo se usaba para **mostrar**. El prior ordenaba la cascada **para siempre**. Implementada la supersesión (`_cost_key`, §40), y de paso se cae el problema de base: el costo medido son **tokens absolutos** y no necesita referencia
- [x] **P-13** · **barrido de «declarado y no ejecutado»** (`_audit_declarado.py`, lección 7.17): cuatro veces el mismo patrón en un día es una regularidad, así que se buscó entera. 20 candidatos, mayoría falsos positivos —la lista **no es un veredicto**— y **cinco reales**. La peor: `REGION_VOCABULARY`, que lleva su propósito escrito al lado —«un θ ajustado bajo un vocabulario nunca debe consumir regiones de otro»— y **nada lo estampaba**. Ahora va en la fila con guarda de mezcla, igual que la huella de decodificación. Y una de las cinco era **mía, de una hora antes**: el patrón se comete mientras se escribe
- [x] **P-14b** · **medición y estado son dos árboles** (lección 5.8). Primero: la guarda de mezcla vivía adentro de `Runner` y **todo analizador lee el `.jsonl` a mano**, así que no protegía a nadie que analizara — `load_rows` es de módulo. Apenas aplicada agarró que el **ledger de creencias vivía en `results/`**, y mi arreglo (enseñarle al analizador a esquivarlo) era el equivocado: **si no es resultados, no va en la carpeta de resultados**. `results/` es medición, `state/` es el ledger; un solo escritor, 207 registros mudados con la cadena íntegra, y la guarda de forma en el seam. Tres intentos hasta derivar bien la ruta: aritmética de rutas, después levantar contra un temporal de test — el store ahora **recibe** su directorio en vez de inferirlo del nombre
- [ ] **P-14** · **dos muertas que quedan por decidir**, no por arreglar: `GUARANTEED_FULL_READ` declara una propiedad de tres brazos que **nada consulta ni impone**, y `PRUNE_AFTER_CYCLES = 3` significa que **la poda por ciclos nunca ocurre**. Cada una es «se implementa o se saca», que es la regla del repo para lo declarado y no medido
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
- [ ] T-3 · teorema de soundness del ensamblador
- [x] **T-4** · **cota nativa derivada y verificada** (`COTA_RATCHET.es.md`, `test_science.py` §22): daño total **≤ 2 subidas por región para siempre**, la replicación es fuerte lejos del umbral (1 en 39.613) y **débil cerca** (1 en 3,7) — y eso se **reporta**, no se esconde. La Parte 3 —pérdida de cobertura por endurecimiento— es trabajo distinto y va aparte (`T-4b`)
- [x] **T-4b** · **medida, y corrige la lectura de la cota** (`_analyze_ratchet_cost.py`, lección 5.12). El ratchet es **gratis hasta A2** —A0/A1/A2 no restringen nada, así que subir ahí no compra garantía ni cuesta cobertura— y **cuesta todo de una vez en A3**: **60% del catálogo y 31% de la utilidad** (0,6101 → 0,4221). «A lo sumo dos subidas» invita a pensar en daño que se acumula despacio; lo medido es que **una sola transición tiene precio y ahí es abrupto**. Y el promedio esconde a quien paga: `many/no_oracle/loose/chain` pierde **−0,5000** con n=4, y en el corpus de sonda la media es **0,0000** con una región perdiendo 0,0877
- [ ] T-5 · quién fija el dial
- [x] **T-6** · **los cinco leídos, y tres le sacan a la novedad.** `EnvProbe` (2606.31422) ocupa **el sondeo con presupuesto para reparar una tabla de creencias tipada** — es nuestra sonda, mecanismo por mecanismo. `Kintsugi` (2605.09487) ocupa las **ediciones gateadas por verificador sobre un artefacto ejecutable tipado** — es la consolidación con su guarda. `ProvenanceGuard` (2607.01236) ocupa **«¿está esta llamada sostenida por evidencia trazable?»** — es el piso de procedencia. Y el área ya tiene **survey** (2606.04990). La novedad queda enunciada como **conjunción**: rutear entre **topologías**, **abstenerse** con curva riesgo-cobertura, y podar por **aritmética antes de inferir**. Y **`Trace2Policy` (2606.10457) nos apoya**: en producción, 22 días y 3.349 casos, **la varianza por versión de regla supera a la del modelo**

**Paper**
- [x] **W-1** · **re-encuadrado en los dos archivos.** El punto no era el orden de las secciones: era que **el Teorema 1 es una IDENTIDAD** —una descomposicion algebraica exacta, verdadera por construccion— y **ninguna medicion puede falsarla**. Lo empirico es solo si sus terminos satisfacen la desigualdad, que es una pregunta sobre un ruteador. Y los terminos **nunca se separaron**: el margen fue 0 en todas las tareas, asi que `alpha` y `beta` no se distinguen de siempre-fallback y la identidad se cumple **vacuamente**. El AURC degenerado (0,000 contra techo +0,400) es la misma cosa vista desde la curva. Queda dicho que el trabajo que un lector le acreditaria a §5.1 lo hace §5.2
- [ ] W-3 · integrar el hallazgo de nano (P13)
- [ ] W-4 · endorser de arXiv, o Zenodo con DOI

**Plataforma** — `ARQUITECTURA.es.md` es una propuesta entera, **nada implementado**
- [ ] Docling + `pypdfium2` · [ ] Postgres como ledger · [ ] Weaviate + `live_pointer`
- [ ] work table → DBOS · [ ] FastAPI con SSE resumible · [ ] on-prem / Docker

**Fases de la tesis**
- [x] F0 · P15 cerrada y registrada
- [x] **F1** · **sensar y re-decidir: las tres pre-empciones diagnosticadas y la selección disparó.** Lo que queda de esta fase no vive acá — la sonda es `S-5`, el acoplamiento `S-4`, y el ciclo completo `REC-4`. Dejarla abierta contaba el mismo trabajo dos veces
- [x] **F2** · **routers rivales: E2 corrido.** El brazo que falta es **E1, y es `M-1`** —implementado, sin correr, ~26 llamadas—. Una fase abierta cuyo único resto ya tiene número propio es un duplicado
- [x] **F3** · **retención y mediación: el recall está medido y es la variable dominante** —brecha +0,533, y predice fuera de muestra al 60% desde el paradigma contra 3,8% desde la región—. El segundo eslabón —si la evidencia leída **sobrevive** hasta la llamada que responde— es **`M-2`**, con número propio
- [x] F4 · estadística que resista al tribunal
- [ ] F5 · teoría nativa
- [ ] F6 · contratos contra baselines directos
- [ ] F7 · validez externa

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

Del bloque de `code-review-2026-08-27.md`. Los bloques CRÍTICO y HIGH están aplicados;
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
