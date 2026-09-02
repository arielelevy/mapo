# GATE — Compuerta de publicación
## Criterios duros, binarios, y su veredicto actual

**Fecha de aplicación**: 2026-08-23
**Objeto evaluado**: `PLAN.md` (831 líneas) + `PATTERNS.md` (759) + `D:\Apps\MAPO\lab`
**Fecha de re-aplicación**: 2026-08-23 (tras cerrar G5 y G7)
**Veredicto global**: ⚠️ **SIN BLOQUEANTES — 2 condicionales** (G2, G3)
*(G1 cerrado el 2026-08-23; ver §8ter. G5/G7 cerrados antes. El único 🔴 vivo es R12.)*

> Historial: la primera aplicación dio 3 bloqueantes (G1, G5, G7) — el encabezado
> decía 6, que era un error de este propio documento. G5 y G7 quedaron cerrados;
> G1 sigue abierto y es trabajo de edición, no de investigación.

---

# 0. Cómo funciona este gate

Tres reglas, y la tercera es la que le da valor.

1. **Binario, no puntaje.** Un criterio pasa o no pasa. Un promedio ponderado deja
   pasar un paper con un agujero fatal y ocho virtudes.
2. **Adversarial.** Cada criterio está escrito como *aquello por lo que un revisor
   hostil lo mataría*, no como una buena práctica deseable.
3. **Bloqueante.** Con un solo criterio en FAIL, no se escribe el paper. v1 se escribió
   completo antes de validar su contribución y quedó sin aval: el costo de ese error
   fueron 3.782 líneas. Este documento existe para no repetirlo.

Un criterio en ⚠️ no bloquea pero debe estar resuelto antes de submitir.

---

# 1. G1 — CONSISTENCIA INTERNA · ⛔ FAIL

> *Un documento que se contradice le dice al revisor que el autor no lo leyó completo.*

| # | Defecto | Ubicación | Severidad |
|---|---|---|---|
| 1 | **Dos tesis rivales, ambas rotuladas como "la tesis".** §0.3 dice que la contribución es el ruteo selectivo; R3.3 dice que el ruteo selectivo es *un resultado dentro* de un marco mayor. El lector llega a §0.3 primero. | §0.3 vs R3.3 | 🔴 bloqueante |
| 2 | §0.3 se titula "la tesis (revisada)" — revisada en R1, no en R3. El rótulo miente sobre su propia vigencia. | §0.3 | 🔴 |
| 3 | La lista de "tres contribuciones" de §0.3 **no incluye la graduación de garantía**, que R3.4 declara la contribución principal. | §0.3 | 🔴 |
| 4 | §2 sigue titulada **"LA IDEA NUEVA"** cuando R3.1 la supersede explícitamente. El documento se contradice en su propia voz. | §2 | 🔴 |
| 5 | §8 fija venue **"arXiv cs.MA+cs.AI"**; la corrección R2 concluyó **cs.LG primary + cs.AI cross-list, cs.MA descartado**. | §8 vs §14 R2 | 🔴 |
| 6 | §6 se titula **"MAPO-Bench"**; se decidió soltar el acrónimo MAPO por ser un nombre heredado del enfoque cedido. | §6 | 🟡 |
| 7 | §3.3 enuncia T3 como *"Π pura + θ inmutable ⟹ decisión única"*. R3 cambió la garantía a *"misma base de creencias ⟹ misma decisión"*. El teorema quedó con el enunciado viejo. | §3.3 | 🔴 |
| 8 | §11 R7 recomienda "contactar a Jaime & Errecalde"; se descartó a Jaime como vía y se degradó a Errecalde. | §11 | 🟡 |
| 9 | §13 (resumen de la decisión) está **íntegramente** en marco R1. | §13 | 🔴 |
| 10 | `PATTERNS.md` se declara **"v0.1 · 2026-08-22"** tras haber ganado dos patrones, tres anti-patrones, cuatro figuras y una corrección de teorema. | PATTERNS.md:4 | 🟡 |
| 11 | El plan **no menciona la consolidación asíncrona** — un componente con módulo y 24 tests que no existe en el documento. | plan completo | 🔴 |

**Para pasar G1**: una sola tesis en el documento; secciones superseded reescritas o
borradas, no marcadas; el enunciado de T3 alineado con la garantía real; consolidación
incorporada.

---

# 2. G2 — NOVEDAD VERIFICADA POR AFIRMACIÓN · ⚠️ CONDICIONAL

> *Toda afirmación de novedad exige un chequeo de literatura fechado. "No lo encontré"
> no es un chequeo.*

| Afirmación | Estado | Evidencia |
|---|---|---|
| Optimizador de planes basado en costos | ⛔ **CEDIDO** | arXiv 2606.03152 |
| Álgebra de operadores | ⛔ CEDIDO | AFlow 2410.10762 |
| Portafolio + selección por query | ⛔ CEDIDO | FlowBank 2606.11290 |
| Selección de paradigma en inferencia | ⛔ CEDIDO | Select-then-Solve 2604.06753 |
| Modelo de costos de workflows | ⛔ CEDIDO | GLOW 2512.15751 |
| Capa de gobernanza simbólica sobre inferencia probabilística | ⛔ CEDIDO | SCL 2511.17673 |
| Consolidación tipo sueño de memoria | ⛔ CEDIDO | Letta, SCM 2604.20943, 2605.26099, 2606.03979 |
| **Teorema del Valor de Selección (T1)** | ✅ libre | verificado 2026-08-22 |
| **Abstención en ruteo de paradigmas** | ✅ libre | verificado 2026-08-22 |
| **Garantía graduada por request** | ✅ libre | SCL es modo global, verificado 2026-08-23 |
| **Piso de garantía derivado de creencias** | ✅ libre | verificado 2026-08-23 |
| **Espacio de patrones acotado por nivel** | ✅ libre | verificado 2026-08-23 |
| **Consolidación de la *política de control*** | ✅ libre **como conjunción** | verificado 2026-08-26 — vecinos: Trace2Policy 2606.10457 (destila control de trazas de expertos, a prompt), 2603.27299 (artefacto determinista auditable, human-authored), 2608.00106 (router interpretable offline, features textuales) |
| **Descubrimiento de proposiciones gateado por procedencia** | ✅ libre **como conjunción** | verificado 2026-08-26 — vecinos: Nous 2606.22030 (reliability techado por procedencia de canal), HEP 2607.09195 (sin jerarquía ni splitting), Eywa 2605.30771, MemIR 2605.25869; el problema del splitting está diagnosticado sin mecanismo en 2607.01507 |

**G2 cerrado el 2026-08-26** (ver §8quater): los dos 🟡 verificados con búsqueda fechada, y
Select-then-Solve y SCL releídos **completos**. Las 6 cesiones y los 6 números citados de
Select-then-Solve verifican contra el cuerpo del paper; la cesión a SCL se sostiene (y era
hasta generosa: su mitad simbólica es un metaprompt en lenguaje natural). La abstención en
ruteo de paradigmas se re-verificó libre al 2026-08-26 — con la ventana cerrándose:
2608.00106 (jul-2026) nombra un confidence gate con fallback como trabajo futuro.

---

# 3. G3 — SOPORTE DE AFIRMACIONES · ⚠️ CONDICIONAL *(sin cambio)*

> *Toda afirmación es medida, citada, o marcada como hipótesis. No hay cuarta categoría.*

| Afirmación | Soporte | Veredicto |
|---|---|---|
| Brecha de oráculo 17,1pp | Select-then-Solve, 18k corridas | ✅ citada |
| Los routers capturan 26% | ídem | ✅ citada |
| Qwen3-30B cae a 27,5% | ídem | ✅ citada |

| Cascada captura 100% a 4,4× costo | `tests/test_science.py`, **sintético** | 🟡 no es evidencia empírica |
| Detector débil → capturado −5,98 | ídem, sintético | 🟡 ídem |
| Abstracción no confabula | `tests/test_consolidation.py`, sintético | 🟡 ídem |
| `direct` gana en costo en C1 | **1 tarea, 2 trials, real** | 🟡 n=1 |
| T1 y sus tres corolarios | álgebra, verificada en test | ✅ |
| Piso A3 excluye 3 patrones | ejecutado, reproducible | ✅ |

**Defecto 12**: la evidencia de campo que motivó el trabajo era de un sistema de cliente
y **quedó fuera del paper** (ver plan §4). Lo que la reemplaza — la comparación de la
topología DAG contra el fallback general sobre corpus publicable — **todavía no se
corrió**, así que hoy el paper no tiene resultado propio de ese eje.

**Para pasar G3**: correr esa comparación en el harness. Y todo número sintético rotulado
como tal en su primera aparición.

---

# 4. G4 — FALSABILIDAD · ✅ PASS

Predicciones registradas antes de medir, con fecha, en `README.md` §"What E0 has to
answer" y en el plan §6.4. Incluyen el caso en que la tesis falla y qué se publica
entonces. Esto es lo mejor que tiene el proyecto y hay que preservarlo.

⚠️ Una sola advertencia: la predicción de §6.4 fue escrita bajo marco R1. Si la tesis
pasa a ser la garantía graduada, **hace falta una predicción falsable nueva para esa
tesis** — costo por nivel y cobertura por nivel — registrada antes de correr.

---

# 5. G5 — VALIDEZ ESTADÍSTICA · ✅ PASS *(era FAIL)*

> *El criterio más peligroso del gate, porque sus fallas producen números creíbles.*

**Defecto 13 — 🔴 BLOQUEANTE. El §10 aplica su regla de decisión a un estadístico
sesgado.** La regla dice "si algún `c*` captura > 26% de la brecha, el paper existe".
Pero la brecha se mide como `E[max_p û_p]`, y un máximo sobre estimadores ruidosos está
**sesgado hacia arriba** — incluso si todos los paradigmas fueran idénticos. Con
`gpt-5-chat` rechazando temperature explícita, el muestreo es al default del modelo y el
sesgo es real y no acotado a priori. La regla de decisión, como está escrita, puede
declarar que el paper existe sobre ruido.

**✅ Cerrado.** El §10.1 es ahora una **precondición** que ninguna regla puede saltear:
`piso_ruido < 0,5 × brecha_medida` y `repeat ≥ 3`, y **todas** las reglas de decisión de
§10.3 se aplican a la brecha **neta**. `Study.noise_floor` estima el sesgo midiéndolo —
k réplicas del **mismo** paradigma tratadas como k paradigmas distintos, así que toda la
brecha que aparece ahí es ruido por construcción.

**Defecto 14 — ✅ cerrado.** El §10 instruía *"Temperatura 0, seeds fijas"*, imposible en
`gpt-5-chat` (400 ante cualquier temperature explícita). Ahora especifica
`temperature=model_default` omitida del payload, seed pineado con +1 por réplica, y
registra la vía de escape verificada: `gpt-5.4-1` **sí** acepta `temperature=0` si el
piso de ruido no baja — con la advertencia de que es un modelo de razonamiento y eso
cambia qué se mide.

**Defecto 15 — ✅ cerrado.** Comparaciones múltiples ahora están en §11 como R10, con el
mecanismo explícito: el registro se parte en tres *por tarea*, `search` propone,
`validate` puntúa, `final` lo toca sólo la guarda de promoción.

**Queda como advertencia, no como bloqueo**: la precondición del piso de ruido es un
umbral elegido (0,5), no derivado. Es conservador y está declarado, pero un revisor puede
pedir justificación.

---

# 6. G6 — REPRODUCIBILIDAD · ✅ PASS

| Requisito | Estado |
|---|---|
| Corpus con ground truth exacto | ✅ 36/36 verificado independientemente |
| Verificador que no reusa el estado del generador | ✅ `corpus/verify.py` |
| Sin LLM-judge | ✅ set F1 determinístico |
| Cache content-addressed | ✅ replay byte a byte |
| Fingerprint de decodificación en cada fila | ✅ |
| Corridas resumibles | ✅ |
| Sin framework de agentes | ✅ HTTP directo |
| Reporte JSON parseable estricto | ✅ corregido 2026-08-23 |

---

# 7. G7 — FACTIBILIDAD OPERATIVA · ✅ PASS *(era FAIL)*

> *Un protocolo que no se puede ejecutar tal como está escrito no es un protocolo.*

**Defecto 16 — ✅ cerrado.** El §10 quedó reescrito contra el harness real, con los
comandos ejecutables, la tabla de parámetros y el costo. Lo que decía antes:

| §10 dice | La realidad |
|---|---|
| 4 estrategias | 7 paradigmas |
| corpus de campo | corpus sintético `gold_v1` |
| "no hay que construir nada" | se construyeron ~3.900 líneas |
| oráculo humano o LLM-judge | set F1 exacto, sin judge |
| 800 ejecuciones | 180×7×`repeat` |
| temperature 0 | imposible en el modelo |

El problema de fondo también quedó resuelto: la evidencia de campo era data de cliente y
salió del paper (plan §4). **E0 corre íntegramente sobre corpus propio y publicable.**

Y el §10 ganó dos secciones que no tenía: **§10.4**, la predicción falsable de la tesis
R3 (costo y cobertura crecientes de A0 a A3, medibles con cero llamadas nuevas porque el
producto cruzado ya está registrado), y **§10.5**, lo que E0 explícitamente NO puede
decidir — validez externa, latencia, y si la idea es buena.

---

# 8. G8 — PRESERVACIÓN DE v1 · ✅ PASS (como plan)

§7 mapea 22 elementos de v1 a destinos en v2, incluidas las 10 capacidades íntegras al
Apéndice D y los 47+ SVG. La regla de oro está declarada y el checklist §12 la verifica.

⚠️ Es un plan de preservación, no una preservación ejecutada. Se re-evalúa cuando exista
el manuscrito.

---

# 8bis. ADDENDUM 2026-08-23 — LA RÉPLICA ACCIDENTAL

Un tercer brazo del A/B expuso cuatro herramientas de memoria de trabajo y **el modelo no
las llamó**: 1 note, 1 compactación, 0 planes en 28 filas. Al no usarse, el brazo quedó
siendo una **réplica** de la superficie anterior, y produjo la primera medición de
varianza de este estudio.

## Qué midió

| | resultado |
|---|---|
| celdas con calidad idéntica entre réplicas | **10 de 10** en `c2`, `c4`, `c5` |
| celdas que se dieron vuelta | **2 de 4** en `c3-002-h3`, por una unidad completa |
| dispersión de costo | media 2,05×, **máx 5,43× a calidad idéntica** |

**La reproducibilidad es por tarea, no global.** Ese es el hallazgo, y refina el protocolo:
`Study.noise_floor` estima un piso **agregado**, y un piso agregado sobre una distribución
donde una celda es bimodal y tres son deterministas describe mal a las dos. **El piso de
ruido tiene que estimarse por celda.**

## Qué le costó al paper

Aplicando el test de atribución — un efecto que sólo mueve la celda inestable no es un
efecto — de los cuatro resultados del A/B:

- `reflection` **+0,250 → el efecto se retira**. Salió entero de la celda que se da vuelta
  sola. **El brazo no**: el catálogo lo tiene activo (auditoría 2026-08-28, único mejor en 1
  de 14, delgado y no dominado). Retirar un efecto no atribuible y retirar un brazo dominado
  son dos criterios distintos, y sólo se cumplió el primero.
- `dag_strategy` **+0,500 → +0,250**. La mitad era la misma celda. Su resultado de **costo**
  sobrevive limpio: 3,05× contra dispersión de réplica de 1,62×, y localizado en las dos
  celdas desbocadas que el mecanismo predice.
- `plan_execute` **−0,139 → sobrevive**, y es el único que movió dos celdas reproducibles.
- `react` **+0,000 → nulo confirmado**, ninguna celda se movió.

## Efecto sobre los criterios

**G5 sigue ✅ PASS, y es la razón por la que esto salió bien.** La precondición del piso de
ruido existía antes de los datos; sin ella hubiera reportado +0,500 y +0,250 como
evidencia. El protocolo funcionó en el único momento en que un protocolo sirve: cuando
contradice al autor.

**G3 sigue ⚠️ condicional, con una corrección concreta anotada.** Una afirmación retirada y
otra partida al medio no es una falla del gate — es lo que el gate hace.

**Nuevo requisito, no bloqueante para correr pero sí para submitir**: todo efecto de calidad
reportado tiene que declarar si movió celdas reproducibles. Un Δ de media sin desglose por
celda no es interpretable cuando la varianza está concentrada.

---

# 8ter. CIERRE DE G1 — 2026-08-23

G1 pedía **una sola tesis en el documento**, y señalaba que §0.3, §2 y §13 del plan seguían
en marco R1 mientras R3 decía otra cosa. Se cierra, pero **no como estaba planteado**, y
conviene decir la diferencia porque un cierre por reencuadre se puede leer como un cierre
por conveniencia.

## Qué cambió el diagnóstico

Cuando se escribió G1 no existía el paper: el plan *era* el documento de tesis, y tener dos
encuadres adentro era una contradicción real. Ahora existe `paper-en.md`, escrito bajo una
tesis única, y eso reparte los roles distinto:

| documento | rol | prueba de G1 |
|---|---|---|
| `paper-en.md` / `-es.md` | **la tesis** | ✅ una sola, de punta a punta |
| `PLAN.md` | **registro histórico** | no aplica: su contenido *es* la sucesión de encuadres |

## Qué se hizo, concretamente

`PLAN.md` se retituló de *"PLAN — Paper v2 (revisión R1)"* a **"REGISTRO DE REVISIONES"**,
con la tesis R1 sacada del encabezado, un puntero al paper como autoridad, y una tabla de
las cuatro revisiones con la causa de muerte de cada una. Las secciones superseded **se
conservan**, y ahora el documento dice al principio que están mal a propósito.

**No se borraron, y ésa fue una decisión.** G1 pedía borrar en vez de rotular. Se rotuló, por
dos razones que son verificables y no de gusto:

1. **R12 depende del registro.** Seis cesiones de novedad se hicieron sobre abstracts. Sin
   el rastro de qué se cedió y contra qué evidencia, una cesión equivocada es indetectable.
2. **Los dos encuadres muertos murieron por causas distintas** — uno porque ya estaba
   publicado, el otro porque perseguía determinismo con un LLM. La segunda es la que dio
   §6.2, así que borrarla borra la derivación del resultado vigente.

## Los otros dos ítems de G1

- *"alinear el enunciado de T3 con la garantía real"* — **resuelto por construcción**: el
  paper no enuncia un T3. La garantía de base de creencias se enuncia directamente en §6.2,
  en la forma *misma base → misma decisión*, sin un teorema intermedio que la desdiga.
- *"incorporar la consolidación asíncrona, que existe en código con 24 tests y no en el
  plan"* — **resuelto**: es §6.3 del paper, con la disciplina de partición en tres y el
  resultado negativo verificado (ninguna partición sobrevive sobre un registro donde la
  utilidad es independiente de todo atributo).

## Veredicto

**G1: ⛔ FAIL → ✅ PASS.** Con la advertencia declarada: pasa porque el paper es el documento
de tesis y el plan quedó explícitamente rotulado como arqueología. Un revisor que exija que
no exista ningún documento con marcos superados, ni rotulado, no está satisfecho.

---

# 8quater. CIERRE DE G2 — 2026-08-26

R12 pedía releer completos los dos trabajos ancla porque las seis cesiones se habían hecho
sobre abstracts. Se hizo, con lectura del texto completo y verificación afirmación por
afirmación:

| Verificación | Resultado |
|---|---|
| Select-then-Solve (2604.06753), 6 números citados | ✅ 6/6 verifican contra el cuerpo. Correcciones editoriales aplicadas: el 26%/31%/37% y el 42,4%/27,5% están en las §§5.2-5.3 del cuerpo, no en el abstract; el "mitad de tokens" está documentado sobre GPT-5 |
| Select-then-Solve, huecos de novedad A-E | ✅ los cinco se sostienen: sin abstención (cobertura 100% forzada), sin riesgo-cobertura, oráculo = máximo empírico **sin corrección de sesgo** (y sus propias limitaciones admiten no re-samplear seeds — munición directa para nuestro §6.1), router caja negra, cero condiciones formales |
| SCL (2511.17673) completo | ✅ cesión correcta y hasta generosa: Regulation es un **metaprompt en lenguaje natural** (soft, prompt-mediado) y Control es determinista sobre **historial de ejecución**, no sobre contenido proposicional. Modo global confirmado. Sin procedencia, sin credencia, sin calibración, un solo patrón de loop (§5.4.5 rechaza multi-agente explícitamente). Anticipar la objeción de su "risk classification" por acción: es una clase estática sobre acciones individuales, no graduación por request |
| Claims 🟡 de la tabla | ✅ ambos libres **como conjunción** (ver tabla §2 actualizada). Enunciarlos siempre como conjunción, nunca como partes |
| a.md (notas Gemini) | ⚠️ lección de método: 2 de 3 citas eran reales pero con títulos/fechas deformados ("LLM-as-Code" no existe; lo real es el survey Code as Agent Harness 2605.18747). 2606.08162 (Entropy Principle): preprint débil, citar de pasada como máximo. MemFail 2605.26667 (UC Berkeley, código abierto): **citar centralmente** — su claim "escalar degrada" es real y textual, con matiz de dependencia de tarea |

Las adiciones de trabajo relacionado quedaron aplicadas en `paper-en.md`/`-es.md`
(§2.2, §2.4, §2.6, §2.7) y la limitación de §9 reescrita: ya no hay cesiones sobre
abstracts en los trabajos ancla.

**G2: ⚠️ CONDICIONAL → ✅ PASS.** R12 cerrado.

## Adenda del mismo día: relectura de MINERVA/HADD (R7)

El autor señaló que HADD apuntaba a decisiones deterministas sobre creencias concretas en
general, no sólo al ruteo. **Verificado contra las 33 páginas: correcto — y nuestro texto
sub-acreditaba.** HADD ya contiene el LLM-como-sensor-tipado, la forma de garantía "misma
base ⟹ misma decisión" (su *decision stability*), el gate de frontera **como mecanismo**
(Invariante 4.6 + companion EVR, Zenodo 19791686), el historial de creencias auditable, la
credencia con calibración adaptativa (EMRE) y el Kautz Type-2. §2.4 y §6.2 quedaron
reescritos: esas seis cosas se **heredan y acreditan**; lo propio queda en cinco puntos —
jerarquía tipada de procedencia con semántica de admisibilidad, inadmisibilidad de lo
elicitado para irreversibles, graduación por request (en HADD la garantía es uniforme),
acotamiento del espacio de patrones por nivel, y calibración **medida** (ECE). Selección,
abstención y deferral quedan fuera del alcance de HADD.

Corrección de cita: **HYDRA-A (Zenodo 19792074) no es "verificación conductual"** de
agentes — es un paper adversarial de AML. Relevancia marginal; no usar como fundamento.

## Adenda 2026-09-01: HADD baja de «base» a «antecedente de vocabulario», y EVR no está

Verificado en vivo contra Zenodo. El registro de MINERVA (20003407) es un preprint de
**arquitectura**: seis contribuciones declaradas, invariantes, patrones, EMRE, holones, y como
única validación la frase «validated in production with real regulated-sector documents», sin
corpus, réplica ni número. Y el companion EVR (19791686), que §2.4 y las referencias citaban
como «compuerta de admisión como mecanismo», **devuelve HTTP 410 Gone** por tres rutas
distintas (record, DOI y API): fue retirado o borrado.

## Adenda 2026-09-01, segunda: el piso de ruido estaba mal construido, y G5 vuelve a ⚠️

Dos revisores externos de contexto limpio (`paper-es_REVIEW-A-2026-09-01.md` y `-B-`)
encontraron que el número que el paper llamaba piso de ruido en §7.3.3 y §7.7.1 salía de
`_predictores.py` remuestreando las réplicas de cada celda real y recalculando la brecha: la
distribución bootstrap del propio estadístico, con media ≥ la brecha observada por
construcción. Sobre un sintético con premio real +0,50 devolvía neto +0,005. **Toda brecha
neta negativa del paper era un artefacto del estimador.** Corregido en `_predictores.py` y
recomputado en `bench/analysis/_recomputo_revision.py` con el estimador que el texto siempre
describió (pseudo-brazos del mismo paradigma, emparejados por número de brazos) más el IC
pareado de la brecha: entre los tres contendientes la brecha sigue dentro del piso; sobre
ocho brazos y en el held-out es positiva y neta. El veredicto del held-out cambió de signo.

Mismo día, otros defectos de sustento corregidos: los números de C3 eran de `terra` y se
presentaban como campaña `luna`; el panel 59 × 8 excluía cinco tareas a mano; «inestable» se
definía como `0 < media < 1`; el baseline de identidad no tenía término de tarea; la tabla de
política 41 × 7 no tenía script; P30 traía utilidades anteriores al re-puntuado. Todo declarado
en el paper con el número anterior al lado.

**G5 pasa de ✅ a ⚠️ condicional** hasta que los tres episodios de §7.8 se repitan sobre el
modelo de la campaña. El test del estimador ya está: §60 de `test_science.py` verifica sobre
un sintético de premio +0,29 que el bootstrap del estadístico devuelve piso ≈ brecha, que el
piso calibrado (pseudo-brazos con medias de réplicas) queda en 0,037, y que sobre brazos
idénticos el calibrado queda a menos de 0,03 de la brecha observada. El mismo test encontró
un segundo defecto en la primera corrección del día: un pseudo-brazo hecho de una réplica
suelta infla el piso en raíz de k; `Study.noise_floor` tiene ese sesgo y queda declarado como
cota conservadora. **G3 sigue ⚠️.**

Decisión del autor (v2 del paper): HADD se acredita por las tres palabras que se comparten
—sensor, decisión determinista, estabilidad de decisión— y deja de llamarse «la base de la que
§6.2 toma sus invariantes». La diferencia que el paper reclama contra él es que **cada invariante
tiene un costo medido y la política aprende**. La cita a EVR se retira hasta que el registro
reaparezca. La adenda del 2026-08-26 de arriba queda como historia de por qué se había
acreditado más.

---

# 9. VEREDICTO

| Criterio | 1ª aplicación | Ahora |
|---|---|---|
| G1 Consistencia interna | ⛔ FAIL | ✅ **PASS** |
| G2 Novedad verificada | ⚠️ condicional | ✅ **PASS** (2026-08-26) |
| G3 Soporte de afirmaciones | ⚠️ condicional | ⚠️ condicional |
| G4 Falsabilidad | ✅ PASS | ✅ PASS |
| G5 Validez estadística | ⛔ FAIL | ✅ **PASS** |
| G6 Reproducibilidad | ✅ PASS | ✅ PASS |
| G7 Factibilidad operativa | ⛔ FAIL | ✅ **PASS** |
| G8 Preservación de v1 | ✅ PASS (plan) | ✅ PASS (plan) |

## Todavía no se escribe el paper, pero ya se puede correr E0

Y esa es la diferencia que hicieron G5 y G7. Antes, correr E0 habría producido números
que parecían evidencia y no lo eran — el sesgo del oráculo sin descontar puede declarar
que el paper existe sobre ruido. **Eso ya no puede pasar sin que el protocolo lo diga.**

Queda **un solo condicional, y es medición: G3** — la comparación fuera-de-ventana con
`repeat=3` (lo que reemplaza a la evidencia de campo retirada).

Estado 2026-08-26: predicciones P1-P5 registradas con fecha en el README del harness
**antes** de correr; barrido de factibilidad a costo cero completado sobre los 4 corpus
(135k poda `direct`/`cot` en 12/32 tareas; 483k en 24/26; 1.272k en 24/32, y a esa escala
la poda alcanza también a `map_reduce` en 18-20 tareas — `results/feasibility_sweep.json`);
el estudio pagado (`_run_oow.py`: gold_v2 ↔ gold_deep emparejados, 7 paradigmas,
`repeat=3`, piso de ruido por celda) **en ejecución**. Cuando termine: todo número
sintético rotulado en su primera aparición y cada efecto de calidad con su desglose por
celda (requisito §8bis).

## Lo que este gate NO evalúa

No dice si la idea es buena. Dice si el documento está en condiciones de defenderla.
Un paper puede pasar los ocho criterios y ser irrelevante; puede fallar seis y contener
la mejor idea del año. El gate sólo garantiza que si la idea es buena, no la va a hundir
un defecto evitable — que es exactamente lo que le pasó a v1.
