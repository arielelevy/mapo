# Pendientes — MAPO

> **Fuente única de "qué falta".** Recopilado el 2026-08-27 juntando el artefacto del
> plan de tesis, `DISENO.es.md` §5 y §8, `code-review-2026-08-27.md`, `ARQUITECTURA.es.md`,
> `CLAUDE.md` y lo que salió midiendo hoy. Lo que está acá no está hecho.
>
> **Cómo se usa**: cuando algo se cierra, se saca de acá y se registra dónde
> corresponda (`README.md` §Findings si es un hallazgo, el commit si es código). Un
> pendiente que se completa y se queda en esta lista es peor que no tenerla.

---

## Resumen — todo de un vistazo

`[x]` hecho · `[~]` empezado · `[ ]` no empezado — **P16 cerró el 2026-08-27, ya no hay nada bloqueado por ella**

**Bloqueantes**
- [x] **B1** · veredicto de P16 — **P16a REFUTADA** (−1,2888), **P16c decisiva**: +0,1211 con λ=0 y adentro del ruido en λ=0,02 · P16d 26/26 · 0 infra · 13,95M tokens
- [x] **B2** · detectores honestos aplicados — una sola función `has_runtime_detector`, falla cerrada; **P17a confirmada con el código real: cascada 2/26**
- [x] **B3** · **P17 cerrada**: P17a CONFIRMADA (cascada 2/26), **P17b REFUTADA (0 de 14: la sonda corrió, costó 83k tokens y no resolvió ninguna)**, P17c REFUTADA (−1,0425), P17d 26/26. El cuello de botella es **la sonda**

**La cuarta pre-empción — lo único que queda entre el registro y una respuesta**
- [~] **S-1** · **la sonda resuelve**: de 0/14 a **9/14** contra la verdad declarada. El verificador exigía ids de unidad y los documentos se referencian por **nombre de persona** — el prompt pedía bien y el verificador rechazaba lecturas correctas. Ahora resuelve cualquier puente **literal** entre dos unidades, con guarda de especificidad, y exige **además** que el sensor diga «no autocontenida»
- [~] **S-3** · **medido: no hay eje computable que lo cierre.** Cardinalidad no separa (C4-w4 y C5-w4 tienen los mismos 5 units); continuidad falla C3; profundidad de puentes da C2=1,22 contra C3=1,28. Los tres miden el **material**, y el acoplamiento es propiedad de **(pregunta × material)**
- [ ] **S-4** · **decidir qué se hace con eso**, y son opciones de diseño, no de calibración: (a) aceptar que el acoplamiento tope en `ELICITED` verificado —la sonda ya lo hace— y ajustar el piso de la regla en consecuencia; (b) sondear sobre **dos** unidades para poder ver profundidad; (c) declarar que la celda C4 no necesita acoplamiento sino cobertura, y darle su propia regla
- [x] **S-2** · resuelto: **no era el piso**. Era que el prompt y el verificador no pedían lo mismo

**Catálogo — la misma vara que a los candidatos nuevos**
- [x] K-3 · **la falsación de `graph_traverse` (P10a) sobrevive a su objeción más seria**: el índice está 100% anclado en el texto y las dos cadenas C3 están conectadas — la travesía tenía las aristas y aun así dio u=0,000. Riesgo de diseño registrado aparte: el índice **no exige** anclaje, así que otro corpus podría envenenarlo en silencio
- [ ] **K-5** · **`graph_traverse` pasa a STANDBY, no retirado** (decisión del autor, 2026-08-28). La falsación vale «donde resolver entidades es gratis», que no es lo mismo que «vale». Revivirlo exige (a) un corpus con resolución de entidades real y (b) un índice con la disciplina de la sonda
- [ ] **K-6** · **Corpus con entidades de verdad**: variantes de superficie, abreviaturas, anáfora, correferencia entre documentos. Sin eso, **ningún patrón de grafo se puede medir donde tiene sentido** — y es el mismo agujero estructural que el detector heredado del gold
- [ ] **K-4** · `RETIRED` sólo bloquea un brazo por código, mientras `pointer_chase` y `graph_traverse` están falsificados **sólo en un documento**. Una decisión que vive en prosa y no en el ejecutable es la misma deriva que se viene cerrando todo el día
- [ ] **K-1** · **`plan_execute` está DOMINADO** (0 únicos mejores, 0 más barato al empatar, sobre 14 celdas): retirarlo por el mismo criterio con el que se retiró el único brazo retirado hasta hoy. Salvedad: aquél cayó sobre *toda* celda medida y esto son 14
- [x] K-2 · `map_reduce` **no** está dominado — gana una celda. Reemplazarlo por handoff cambiaría cobertura medida por un brazo sin medir: van **uno contra otro**, no uno en lugar del otro

**Mediciones**
- [ ] M-1 · brazo en PROSA (E1) — implementado, sin correr
- [~] M-2 · retención de contexto — *recall medido y predictivo; falta el segundo eslabón*
- [ ] M-3 · transferencia de θ entre familias de modelos
- [ ] M-4 · corpus natural + segunda familia
- [ ] M-5 · C3 profundo en nano

**El catálogo confunde dimensiones ortogonales**
- [x] **F-1** · `Blackboard` extraído a `paradigms/blackboard.py` — comportamiento idéntico, suites en verde; **F-2 ya es formulable**
- [ ] **F-2** · medir `{blackboard, sin}` × `{react, dag}` en C2/C4 — **descontamina «el efecto dag_strategy»**
- [ ] **F-3** · HyDE como factor de pre-proceso — *decidido: se usa*
- [ ] **H-1** · portarlo como rama paralela fusionada por RRF, **no como herramienta**
- [ ] **H-2** · exponerlo como brazo `hybrid_hyde` — la dimensión ya existe en el banco
- [ ] **H-3** · medir `{hybrid, hybrid_hyde}` **con el costo cobrado** *(P16c: sin λ el número no significa nada)*
- [ ] **F-4** · escribir qué dimensión define un patrón y cuál es un factor *(gratis)*

**«Anti-RAG» — la máquina existe (REC), le falta una pieza**
- [ ] **AR-0** · medirlo como **factor** `{con, sin} × {patrones}`, no plegado en cada patrón
- [ ] **AR-1** · contratos de completitud *(= T-1; la única pieza que falta de verdad)*
- [ ] AR-2 · cablear rechazo tipado de contrato → `rec.diagnose` *(chico)*
- [ ] AR-3 · predicción falsable antes de correr
- [ ] AR-4 · baseline honesto: contra HyDE y RAG plano, no contra nada

**La fase de entendimiento — la mitad que S-3 declaró faltante**
- [ ] **U-1** · fase que emite **demandas tipadas** del request (`requires_exhaustive`, `needs_decomposition`, …), no un float de conclusión
- [ ] **U-2** · que **la regla** combine demanda × material — resuelve los 4 falsos positivos de C4 sin heurísticas nuevas
- [ ] **U-3** · entran como `ELICITED`: el modelo lee la pregunta, no puede superar ese rango
- [ ] **U-4** · `requires_exhaustive` se **verifica** con C-COMPLETE — el único camino a promoverla
- [ ] **U-5** · medirla contra λ: cuesta una llamada por request

**REC — implementado, sin registrar y sin medir**
- [ ] **REC-1** · preregistrar las seis hipótesis de `PATRON_REC.es.md` §11 *(gratis)*
- [ ] **REC-2** · congelar política, presupuesto, umbrales y regla ANTES del mundo final
- [ ] **REC-3** · generar el mundo final — `gold_transfer` está reservado a diagnóstico
- [ ] **REC-4** · correr los siete brazos *(caro; compite con P17 por cuota)*
- [ ] **REC-5** · corpus independiente del generador *(= M-4)*
- [ ] **REC-0** · **arreglar el baseline**: «router P15 congelado» es un router cuya selección nunca dispara ⇒ el baseline tiene que ser el de P17, y **REC va después de P17**

**Producto — capa de decisión**
- [ ] P-1 · que la sonda sense **recuperabilidad** (hoy sensa acoplamiento)
- [x] **P-2** · ~~sacarlo del camino activo~~ — **decisión revertida el 2026-08-27, y la revisión estaba mal planteada.** Lo demostrado es estrecho: el peso no puede mejorar la **selección de paradigma**, porque en el punto fijo es una transformación monótona de la tasa de victorias. Eso **no dice nada** sobre aprender asociaciones entre pares, que es a donde va (P-2c, P-2d, D-4). Y además ya gobierna algo: es el **reloj de decaimiento** con el que `consolidation.py:286` poda las stats sin episodios — nunca poda por peso solo, porque una stat con episodios es evidencia. Ese ciclo de vida —acotado, decae, piso, poda— es justo la maquinaria que una tabla de asociaciones necesita. **No se saca: se reusa.**
- [ ] P-2b · reintroducirlo como **detector de no estacionariedad** *(drift medido: 80%)*
- [~] **P-2c** · **la condición necesaria NO se sostiene al estratificar.** Sin estratificar la dispersión de tasas por transición daba 0,18; controlando por celda —y conservando el bloque de fila, que es la unidad de resultado— **cae a lo que produce el azar**: 0 de 4 estratos con potencia superan al null. No lo refuta (con 6-7 filas por celda, no detectar es compatible con un efecto chico), pero **la dispersión sin estratificar no puede leerse como señal**. Se re-mide cuando P17 cierre: triplica las secuencias
- [ ] P-2d · asociaciones aprendidas como creencias *(necesita un rango bajo OBSERVED)*
- [ ] P-2e · componer el patrón en vez de elegirlo *(el techo)*
- [ ] P-3 · calibración por proposición al router activo
- [ ] P-4 · horizonte con evidencia propia
- [ ] P-5 · las particiones descubiertas no gobiernan el router
- [ ] P-6 · particiones que usan truth de evaluación
- [ ] P-7 · el producto no cierra el bucle
- [ ] P-8 · promoción sin incertidumbre
- [ ] P-9 · repetir consolidación reaplica historia
- [ ] P-10 · flags declarativos del dial A0–A3
- [x] **P-11** · dependencia invertida: `app/verify.py` es el verificador del **producto** y `grading` es la cara del **banco** sobre el mismo primitivo. Relocación pura, verificada re-puntuando 390 filas: **0 discrepancias**

**Lo más grande, y no estaba en la lista**
- [ ] **A-1** · arrancar el producto — *el motor nuevo no existe*
- [ ] **A-2** · decidir qué se porta de `legacy/`
- [ ] **A-2b** · cosecha de `legacy/`: `context_guard` **sí** (mecanismo, no sus constantes) · `hyde` al producto pero medirlo acá puede no significar nada · el prompt de suficiencia **no**
- [ ] **A-3** · separar producto de banco ANTES de portar

**Apareció al aplicar B2**
- [x] **X-1** · un solo constructor `payload_for(task)` en `features.py` — los tres sitios lo usan
- [ ] **X-2** · el ledger de costo no es convertible a plata *(falta el split prompt/completion y la tarifa)*

**Riesgos que nadie estaba mirando**
- [~] **R-1** · verificar el replay sellado — *intentado y **no concluyente**: el replay de secuencias da 93/112 misses, pero es mucho más probable que sea el replay y no el caché. Hace falta un test que replaye una celda por el MISMO camino que el runner*
- [ ] R-2 · celdas † de la grilla congelada `gpt-5-chat`
- [~] **R-3** · barrido del paper: §1.3 y §5.2 ahora dicen que **la rama `v=0` de la propia partición nunca se ejercitó**, y por qué es estructural. Falta el resto del barrido
- [x] R-4 · `lab/ui/index.html` — **es la UI de prueba del autor**; se adopta
- [ ] R-5 · 11 commits locales sin pushear

**Decisiones dinámicas que hoy no gobierna nadie**
- [ ] D-1 · cuándo parar de iterar *(el más barato: las señales ya existen)*
- [~] D-2 · qué herramienta sigue — *secuencia instrumentada; el replay **no funciona**: 93/112 misses sellados, causa sin identificar (`_replay_sequences.py`)*
- [ ] D-3 · la descomposición en DAG
- [ ] D-4 · challenger multi-agente con handoff por contrato
- [ ] D-5 · la «Constant Soup» en general
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
- [ ] pip-audit nunca corrido

**Teoría — pizarra, bloquea a F6**
- [~] **T-1** · **semántica escrita y C-NUM implementada** (`app/contracts.py`) (`CONTRATOS.es.md`): tres clases con su proposición exacta, y el residuo formalizado como `⟦o⟧ ∖ π_C(o)` — que es donde vive el mis-binding. Falta implementar `π_C` para al menos una clase
- [x] **T-2** · red-team hecho por nosotros: **5 de 5 familias sobreviven, residuo 100%** (`_redteam_binding.py`). Las cinco comparten forma: lo que falsea la oración vive en la **prosa conectiva**, que no ocupa ranura
- [ ] T-3 · teorema de soundness del ensamblador
- [~] **T-4** · **cota nativa derivada y verificada** (`COTA_RATCHET.es.md`, test §22): daño total ≤ 2 subidas por región **para siempre**; la replicación es fuerte lejos del umbral (1 en 39.613) y **débil cerca** (1 en 3,7). Falta medir la pérdida de cobertura por endurecimiento (Parte 3)
- [ ] T-5 · quién fija el dial
- [~] **T-6** · **arXiv 2603.18043 leído** y ubicado en §2.4 de los dos papers: corrobora la disciplina del sensor desde el ángulo adversarial, y **ocupa «procedencia + ruteo + contratos» como frase** — la conjunción queda enunciada por lo que excluye. Faltan EnvProbe, Kintsugi, SHARP, Trace2Policy

**Paper**
- [ ] W-1 · re-encuadrar §5.1 vs §5.2
- [ ] W-2 · toda edición va a los DOS archivos
- [ ] W-3 · integrar el hallazgo de nano (P13)
- [ ] W-4 · endorser de arXiv, o Zenodo con DOI

**Plataforma** — `ARQUITECTURA.es.md` es una propuesta entera, **nada implementado**
- [ ] Docling + `pypdfium2` · [ ] Postgres como ledger · [ ] Weaviate + `live_pointer`
- [ ] work table → DBOS · [ ] FastAPI con SSE resumible · [ ] on-prem / Docker

**Fases de la tesis**
- [x] F0 · P15 cerrada y registrada
- [~] F1 · sensar y re-decidir — *tres pre-empciones diagnosticadas, la selección disparó*
- [~] F2 · routers rivales — *E2 corrido; falta E1*
- [~] F3 · retención y mediación — *recall medido; falta instrumentar retención*
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
| M-1 | Brazo en PROSA (E1) | Los dos brazos implementados y sin correr: el clasificador de producción tal cual y el router en prosa más fuerte construible. Espera a que P16 libere la cuota | ~26 llamadas |
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

## 1a. La fase de entendimiento: la mitad que falta (idea del autor, 2026-08-28)

**El diagnóstico que la pide.** S-3 midió que el acoplamiento es propiedad de
**(pregunta × material)** y que todos los ejes computables son función del material solo.
Falta la mitad de la información, y la mitad que falta es **qué exige la pregunta**.

**Y la calidad depende de eso, no sólo de la respuesta.** Que conteste **TODAS** las
direcciones y **TODOS** los nombres es un requisito real y medible — pero *no siempre es
necesario*. Hoy nada en el request lo declara, así que la cobertura se persigue igual en
tareas que no la piden y se paga sin comprarse nada.

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
