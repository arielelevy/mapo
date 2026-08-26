# REGISTRO DE REVISIONES — Paper v2

> ## ⚠️ Este documento NO es la tesis. Es cómo llegó a ser.
>
> **La tesis está en [`paper-en.md`](paper-en.md)** (castellano: [`paper-es.md`](paper-es.md)).
> Si algo de acá contradice al paper, manda el paper.
>
> Lo que queda registrado son **tres encuadres, dos de ellos superados**, y por qué se
> cayeron. Se conserva por dos razones concretas y no por sentimentalismo:
>
> 1. **R12 depende de esto.** Seis afirmaciones de novedad se cedieron a trabajo previo, y
>    varias sobre abstracts y no papers completos. Sin el registro de qué se cedió y con qué
>    evidencia, una cesión equivocada es indetectable — y cuesta tanto como una afirmación
>    equivocada.
> 2. **Dos encuadres murieron por razones distintas**, y la distinción es informativa: el
>    primero porque ya estaba publicado, el segundo porque perseguía algo imposible.

| revisión | encuadre | por qué se cayó |
|---|---|---|
| **R0** | "MAPO: un optimizador de consultas para orquestación agéntica" | Ya publicado. AFlow, GLOW y el paralelo con optimización de consultas cubren la idea. |
| **R1** | "Selección selectiva de paradigma: por qué el ruteo casi siempre pierde y cuándo gana" | No se cayó — **se absorbió**. Es el §5 del paper. Pero como tesis única dejaba afuera la parte determinista. |
| **R3** | Garantía por solicitud sobre una capa de creencias | Vigente en el paper como §6.2, y **acotada**: SCL (arXiv:2511.17673) ya hace gobernanza simbólica en modo global, así que lo que queda es la graduación por solicitud. |
| **actual** | La factibilidad antes de la selección | El paper. Las tres afirmaciones van *delante* del problema de aprendizaje, no dentro. |

**Fecha original**: 2026-08-22 · **Autor**: Ariel Edgardo Levy
**Documento origen**: los whitepapers v1 (v1.0, dic-2025, 3.782 líneas — quedaron en su
repo de origen, fuera de MAPO; la única pieza heredada es `MAP.md`)

**Cómo leer lo que sigue**: como arqueología. Las secciones marcadas *superseded* están
mal a propósito — mostrar qué se pensaba antes es el único valor que tienen. Para saber qué
se sostiene hoy, el paper y [`GATE.md`](GATE.md).

---

---

# ⚠️ REVISIÓN R3 (2026-08-23) — supersede §0.3 y §2

R1 movió el paper de "optimizador de planes" a "ruteo selectivo con abstención". R3 lo
mueve otra vez, y esta es la última capa: **el ruteo selectivo pasa a ser un resultado
*dentro* de un marco más grande, no el marco.**

## R3.1 Los dos errores de diseño que se corrigen

**(a) Determinismo por exclusión.** El plan buscaba reproducibilidad *prohibiendo* que
el LLM participara en la decisión: features derivadas descartadas, router abstenido. Eso
tira información real, trata al LLM como contaminante en vez de instrumento, y sigue
prometiendo una garantía que no existe. Un LLM es probabilístico y ningún pineo lo
cambia.

**Corrección — capa de creencias.** El LLM es un **sensor** que emite proposiciones
tipadas con credencia, procedencia y evidencia. Una capa simbólica determinística razona
sobre la base de creencias. La garantía cambia de forma:

```
NO   "el mismo prompt da la misma respuesta"           ← falso, siempre
SÍ   "la misma base de creencias da la misma decisión" ← verdadero, y auditable
```

La base de creencias es un artefacto registrado, así que el auditor **no replica el
modelo**: inspecciona qué afirmó y con qué evidencia, y replica las reglas.

La **procedencia** es el campo que carga el peso: `COMPUTED` (función pura, credencia
1,0) > `OBSERVED` (medido por sonda — evidencia) > `ELICITED` (el modelo lo dijo, sujeto
a calibración) > `ASSUMED`. Una regla puede exigir procedencia mínima: una acción
irreversible admite sólo `COMPUTED`/`OBSERVED`, porque *la opinión de un modelo de que
una acción es segura no es evidencia admisible para tomarla*. Ese es el EVR gate de
MINERVA/HADD, bien hecho, y el encuadre es **Kautz Type-2** (`Symbolic[Neuro]`) — que es
justamente el keyword de Jaime que R1 había subutilizado.

**(b) Modo determinístico global.** La escalera D0-D3 aplicaba a todo el sistema. Eso
obliga a *todo* el tráfico a pagar el costo del request más estricto, y como la garantía
cuesta cobertura, un modo global estricto degrada las decisiones que no necesitaban
garantía ninguna.

**Corrección — la garantía es por request.** El default es el extremo **flexible**; la
estrictez es escalamiento pedido y pagado. El piso lo derivan las creencias *sobre* el
request; el caller puede pedir más, nunca menos.

## R3.2 La relación central

**El nivel de garantía acota el espacio de patrones admisibles. La plasticidad permuta
libremente dentro de ese espacio.** Garantía y plasticidad son perillas **ortogonales**,
no opuestas — que es lo que el diseño de modo global tapaba.

| Nivel | Procedencia | θ aprende online | Sellado | Patrones |
|---|---|---|---|---|
| **A0** exploratorio | `ASSUMED` | **sí** | no | álgebra completa |
| **A1** estándar | `ELICITED` | no | no | catálogo |
| **A2** rendible | `ELICITED`* | no | no | catálogo, profundidad ≤3 |
| **A3** certificado | `OBSERVED` | no | **sí** | subconjunto certificado |

\* sube a `OBSERVED` si la calibración no está ganada.

Medido en el harness: un caller que pide A0 sobre una tarea irreversible obtiene **A3
igual**, y el espacio de planes cae de 7 patrones a 4 (`dag_strategy`, `plan_execute` y
`reflection` quedan excluidos — no por ser peores, suelen ser mejores, sino porque su
control de flujo no es acotado ni sus modos de fallo enumerables).

## R3.3 La tesis revisada

> La reproducibilidad en sistemas agénticos se ha planteado como una propiedad del
> sistema, y por lo tanto como un costo que todo el tráfico paga. Sostenemos que es una
> propiedad **del request**: una dimensión tarifada y graduable cuyo nivel acota el
> espacio de planes admisibles, con el piso derivado deterministamente de creencias
> sobre el propio request. Dentro de cada nivel, la plasticidad recombina patrones
> libremente y aprende de resultados. El determinismo no se obtiene excluyendo al
> modelo — imposible — sino tratándolo como sensor cuyas afirmaciones, con su
> procedencia y su credencia calibrada, son la entrada registrada de una capa de
> decisión simbólica.

**El ruteo selectivo (T1) y la partición por verificabilidad quedan como resultados
dentro de este marco**: T1 gobierna A1/A2, la partición gobierna A0/A1. Siguen siendo
contribuciones; dejan de ser *la* contribución.

## R3.4 Por qué esto es mejor que R1

| | R1 (ruteo selectivo) | R3 (garantía graduable) |
|---|---|---|
| Riesgo de scoop | **alto** — el campo se mueve en meses | bajo — nadie lo plantea así |
| Respaldo externo | Select-then-Solve (competidor) | [agenda de investigación](https://arxiv.org/html/2606.13405v1) **pidiéndolo** |
| Uso de Jaime | citado y diferenciado | **BDI-HTN / Kautz Type-2 como fundamento** |
| Uso de MAP (v1) | capa de estadísticas | capa de estadísticas **con procedencia** |
| Falsabilidad | curva riesgo-cobertura | + diagrama de calibración, + costo por nivel |
| Alcance de producción | un router | una dimensión de la plataforma |

**Nuevo riesgo a verificar antes de escribir**: [Soft Symbolic Control / structured
cognitive loop with a governance layer](https://arxiv.org/abs/2511.17673) ya publica una
capa de gobernanza simbólica sobre inferencia probabilística. **Hay que leerlo completo
antes de comprometerse.** Lo que no parece cubierto es la **graduación por request con
piso derivado de creencias** y el acotamiento del espacio de patrones — pero eso hay que
confirmarlo, no asumirlo.

## R3.5 Experimento nuevo que R3 habilita

**Calibración de credencias elicitadas.** Diagrama de confiabilidad y ECE: cuando el
modelo declara 0,8 de confianza sobre una propiedad estructural de la tarea, ¿acierta el
80%? Si no, es un resultado publicable por sí solo y ataca directo el hallazgo de
[creencias superficiales](https://arxiv.org/pdf/2606.11016). Y es la variable que decide
si A2 puede admitir `ELICITED` o tiene que sondear.

**Costo por nivel de garantía.** Tokens y cobertura de A0 a A3 sobre el mismo corpus.
Convierte "la garantía cuesta" de afirmación en número, que es lo que un comité de
arquitectura necesita para elegir nivel por caso de uso.

---

# 0. LA SITUACIÓN, EN NÚMEROS

## 0.1 Lo que la literatura ya resolvió (y hay que ceder)

| Idea del plan original | Ya publicado | Veredicto |
|---|---|---|
| Optimizador de planes basado en costos para agentes | **Cost-Aware Optimization for Agentic Query Execution** (arXiv 2606.03152): *"agent workflow optimization becomes the analogue of classical query optimization"* | ⛔ Cedido |
| Álgebra de combinadores / operadores | **AFlow** (arXiv 2410.10762): "Operators" encapsulan Ensemble/Review/Revise combinando nodos y aristas | ⛔ Cedido como novedad |
| Portafolio + selección por query | **FlowBank** (arXiv 2606.11290): portafolio compacto offline + selección por query en inferencia | ⛔ Cedido |
| Selección de paradigma en tiempo de inferencia | **Select-then-Solve** (arXiv 2604.06753) | ⛔ Cedido |
| Modelo de costos / predicción de performance de workflows | **GLOW** (2512.15751), **Multi-View Encoders** (2505.19764) | ⛔ Cedido |
| Ruteo con restricción de budget | **On Time, Within Budget** (2605.06110) | ⛔ Cedido |
| Ruteo a nivel de traza de task | **TRACE-Router** (2607.22465) | ⛔ Cedido |
| Descomposición + dispatch a (modelo, primitiva) | **Uno-Orchestra** (2605.05007) | ⛔ Cedido |

**Búsqueda automática de workflows** (AFlow / ADAS / GPTSwarm / A2Flow-AAAI) está madura.
El riesgo §9.1 del plan original se materializó por completo.

## 0.2 ⭐ Lo que esos mismos papers revelan (y es el paper nuevo)

**Select-then-Solve** (arXiv 2604.06753) corre el experimento definitivo:
6 paradigmas (Direct, CoT, ReAct, Plan-Execute, Reflection, ReCode) × 4 LLMs frontera ×
10 benchmarks ≈ **18.000 corridas**. Resultados:

| Hallazgo | Número | Implicancia |
|---|---|---|
| Ningún paradigma domina | — | El problema es real |
| **Brecha del oráculo** vs mejor paradigma fijo | **+17,1pp promedio** | **El premio es GRANDE** |
| Varianza por task | ReAct +44pp sobre Direct en GAIA; CoT −15pp en HumanEval | La elección importa muchísimo |
| Su router (embedding-based) recupera | **26%** de la brecha (31% GPT-5, 37% Gemini) | **74% del premio queda sin capturar** |
| Auto-ruteo zero-shot del LLM | Qwen3-Max **cae a 42,4%**, Qwen3-30B **a 27,5%** — *por debajo de sus propios baselines* | **Rutear mal es peor que no rutear** |
| Sesgo sistemático | Los modelos débiles eligen paradigmas con herramientas sin importar el task | Falso positivo estructural |
| Costo | El router iguala/supera a ReAct a **la mitad de los tokens** | La eficiencia sí se captura |

### Lectura

1. **El premio existe y está cuantificado: 17,1pp.** Esto *destruye* la hipótesis
   pesimista del plan original (§9.2: "quizá el premio no existe"). No hace falta el
   piloto para averiguarlo — ya está medido con 18.000 corridas.
2. **Nadie lo captura.** El mejor router publicado se queda con el 26%. Hay **74% de
   valor sin reclamar** y eso es un objetivo de investigación explícito y medible.
3. **El fallo del auto-ruteo LLM está medido y publicado.** Qwen cayendo por debajo de
   su propio baseline al intentar elegir su estrategia no es un accidente de un
   despliegue: son cuatro modelos y diez benchmarks. **Rutear mal es peor que no
   rutear, y es literatura.**
4. **El cuello de botella no es el modelo, es el encuadre decisional.** Todos estos
   routers están obligados a **elegir siempre**. Ninguno puede **abstenerse**.

## 0.3 La tesis de v2 (revisada)

> La selección de paradigma tiene un premio grande y medido (17,1pp de brecha de oráculo)
> que los routers actuales capturan sólo en un 26%, y que el auto-ruteo por LLM captura
> en valor **negativo**. Sostenemos que el cuello de botella no es la capacidad del
> selector sino su **encuadre decisional**: un router obligado a elegir siempre está
> dominado por un router **selectivo**, que emite un paradigma especializado únicamente
> dentro de su región de alta confianza y **se abstiene hacia un fallback seguro** en el
> resto. Formalizamos la condición exacta bajo la cual la selección paga (Teorema del
> Valor de Selección), la instanciamos como un **procedimiento de decisión determinístico
> e interpretable** sobre features estructurales del task, y mostramos que captura más
> de la brecha del oráculo que un router neuronal — siendo además auditable, requisito
> que los routers neuronales no pueden satisfacer en despliegue regulado.

Tres contribuciones, en orden de fuerza:

1. **Teórica** — Teorema del Valor de Selección + formulación como *clasificación
   selectiva / learning-to-defer*. Explica el 26% y explica el colapso de Qwen.
2. **Metodológica** — curvas riesgo-cobertura para selección de paradigma. Métrica nueva:
   no "accuracy del router" sino *fracción de la brecha de oráculo capturada a cobertura c*.
3. **Sistémica** — el selector como artefacto determinístico, versionado, firmable y
   diffeable. Aprendizaje que **compila a una política inspeccionable, no a pesos**.

---

# 1. EL HUECO PRECISO

## 1.1 Lo que todos hacen

Select-then-Solve, FlowBank, TRACE-Router, Uno-Orchestra: **cobertura 100%**. Todo task
recibe un paradigma. El router es un clasificador multiclase.

## 1.2 Por qué eso es un error decisional

Sea `p*` el fallback general (ReAct+herramientas) y `p_s` un paradigma especializado.
Con `π = P(p_s domina)`, precisión `α`, falso positivo `β`, ganancia `G`, pérdida `L`:

```
Valor de la selección = π·α·G − (1−π)·β·L
```

Un clasificador de cobertura 100% **no tiene ningún grado de libertad sobre `β`**. Paga
todos los falsos positivos. Y la evidencia dice que `L` es enorme: Qwen3-30B cae a 27,5%,
CoT destruye 15pp en HumanEval. **La distribución de pérdidas tiene cola gruesa.**

## 1.3 La corrección: abstención

Un **router selectivo** con función de confianza `κ` y umbral `τ` emite `p_s` sólo si
`κ > τ`, y `p*` en caso contrario. Ahora `β` es *controlable por diseño*:
`β(τ) → 0` cuando `τ → 1`, a costa de cobertura.

**Corolario operativo**: existe `τ*` que maximiza el valor capturado, y en general
`cobertura(τ*) ≪ 1`. **El router óptimo se abstiene la mayor parte del tiempo.**

Esto es la regla de Chow (1970) de rechazo óptimo, trasladada a selección de paradigma.
Es teoría establecida, citable, y **nadie la aplicó acá**. Es también exactamente la
disciplina del optimizador de bases de datos: *sequential scan* por defecto, índice sólo
cuando la estimación lo justifica.

## 1.4 Por qué esto no lo cubre la literatura encontrada

| Trabajo | Cobertura | Determinístico | Auditable | Abstención formal |
|---|---|---|---|---|
| Select-then-Solve | 100% | No (embeddings) | No | No |
| FlowBank | 100% | No | No | No |
| TRACE-Router | 100% | No | No | No |
| Uno-Orchestra | 100% | No (política RL) | No | No |
| AFlow / ADAS / GPTSwarm | offline, workflow único | No | No | N/A |
| Auto-ruteo LLM zero-shot | 100% | **No** | No | No |
| **Este trabajo** | **selectiva, `c` óptima** | **Sí** | **Sí** | **Sí (T1)** |

## 1.5 El ángulo de determinismo (segundo hueco, independiente)

La búsqueda confirmó que existe presión regulatoria real (EU AI Act en enforcement desde
ago-2026; alto riesgo exige explicabilidad y auditabilidad) y que hay trabajo
neurosimbólico de **políticas interpretables y editables** — *Neural DNF-MT* (2501.03888),
*ORCAID* (2607.07235) — pero aplicado a **control RL**, no a orquestación de agentes.
También hay literatura de gobernanza en runtime (*Runtime Governance for AI Agents:
Policies on Paths*, 2603.16586) que exige que la función de política sea determinística
para que los logs de auditoría sean verificables.

**Nadie conectó**: aprendizaje de política interpretable ⟷ selección de topología
agéntica ⟷ certificabilidad. Ese cruce está libre y es donde MINERVA/HADD
(Zenodo 20003407) y la verificación conductual de HYDRA-A (Zenodo 19792074) entran como
<!-- ⚠️ CORRECCIÓN 2026-08-26: HYDRA-A leído — NO es "verificación conductual" de agentes;
es un paper adversarial de AML (mens rea / zero-knowledge behavioral verification como
defensa). Relevancia marginal. No citarlo como fundamento de verificación conductual. -->>
fundamento externo.

---

# 2. LA IDEA NUEVA: APRENDIZAJE QUE COMPILA A UN ARTEFACTO AUDITABLE

Esto responde directo al pedido de "una nueva manera de hacer un agente que aprenda".

## 2.1 Cómo aprende hoy el estado del arte

La búsqueda mostró que la línea dominante de agentes que aprenden sin actualizar pesos es
**memoria experiencial**: ExpeL, *Experiential Reflective Learning* (2603.24639),
*MemSkill* (2602.02474), *R²-Mem* (2605.13486), *Rethinking Continual Experience
Internalization* (2606.04703), reglas conductuales acumuladas (2607.13091),
*Truly Self-Improving Agents Require Intrinsic Metacognitive Learning* (2506.05109).

Todas aprenden **contenido**: insights, reglas de dominio, entradas de memoria,
trayectorias. El artefacto aprendido es texto que se reinyecta en el prompt.

Ninguna aprende **su propia política de control**. Y las que sí eligen control
(Select-then-Solve, FlowBank) lo aprenden como **pesos neuronales opacos**.

## 2.2 La propuesta

**Plasticidad que compila a una política certificable.**

El agente aprende de la experiencia, pero la **salida del aprendizaje no son pesos ni un
blob de memoria: es un procedimiento de decisión determinístico e inspeccionable.**

```
Ejecución  →  (φ, plan, outcome, costo)  →  [aprendizaje offline]  →  θ_v
                                                                      │
                          θ_v = lista de decisión selectiva sobre φ   │
                                versionada, firmada, diffeable        │
                                                                      ▼
Runtime:   plan = Π(φ(t), θ_v)     ← función PURA, misma entrada = mismo plan
                  con abstención:  κ(φ) ≤ τ  ⟹  fallback p*
```

Tres propiedades que ningún trabajo encontrado tiene juntas:

1. **Determinismo en el instante** — `Π` es pura, `θ_v` inmutable. Replayable, diffeable.
   El aprendizaje ocurre **entre** épocas, nunca dentro de un request.
2. **Interpretabilidad por construcción** — `θ_v` es una lista de decisión oblicua sobre
   ~7 features, no una red. Se lee, se audita, se **edita a mano**. Se importa la
   maquinaria de Neural DNF-MT / ORCAID a un dominio nuevo.
3. **Abstención calibrada** — `τ` se fija con la curva riesgo-cobertura para mantener
   `β < β_max` del T1. El sistema *sabe cuándo no sabe*.

La analogía honesta: es **profile-guided optimization**. El PGO cambia las decisiones del
compilador, pero un compilador+perfil dado es determinístico. Y es **SQL Plan Management**
de Oracle: un plan nuevo se promueve sólo si no regresiona.

## 2.3 Por qué MAP (v1) es el substrato correcto

Esto redime la elección central de v1. MAP aprende pesos Hebbianos **interpretables**
(`W[intent][aᵢ→aⱼ] ∈ [0,1]`), no una red. Eso lo hace un candidato natural para `θ_v`:
un peso Hebbiano *se puede leer, auditar y firmar*. Un embedding de router no.

v1 tenía la pieza correcta y el encuadre equivocado. v2 conserva MAP íntegro y lo
recontextualiza como la capa de estadísticas que alimenta `κ` y `Π`.

## 2.4 Features estructurales, no léxicas

El modo de fallo típico de los routers en prosa — reglas sobre `"how many"`,
`"extract ALL"` — es condicionar sobre forma de superficie. `φ` condiciona sobre
estructura medible:

| # | Feature | Símbolo | Obtención | Gobierna |
|---|---|---|---|---|
| F1 | Cardinalidad de subunidades | `n` | conteo directo | paralelizar o no |
| F2 | Acoplamiento | `κ_c` | grafo de dependencias | barrera vs pipeline |
| F3 | Oráculo barato disponible | `v` | ¿tests/compilador/schema? | loop vs voto |
| F4 | Incertidumbre de horizonte | `h` | ¿nº de pasos conocido? | loop vs DAG fijo |
| F5 | Reversibilidad / riesgo | `ρ` | ¿acciones irreversibles? | gate crítico |
| F6 | Contención de escritura | `χ` | ¿estado compartido? | aislamiento |
| F7 | Budget | `B` | dado por el caller | restricción |

**Requisito duro**: costo de extraer `φ` = `o(costo de ejecución)`. F1/F5/F6/F7 son casi
gratis. F2/F3/F4 pueden requerir un modelo chico cacheado. Medirlo y reportarlo aunque
salga mal — es amenaza a la validez de primer orden.

---

# 3. NÚCLEO FORMAL

## 3.1 ⭐ T1 — Teorema del Valor de Selección

Con `p*` fallback, `p_s` especializado, `π = P(t ∈ S)` donde `S` = tasks donde `p_s`
domina, precisión `α = P(elige p_s | t∈S)`, falso positivo `β = P(elige p_s | t∉S)`,
`G = E[u(p_s) − u(p*) | t∈S] > 0`, `L = E[u(p*) − u(p_s) | t∉S] > 0`:

```
La selección supera al mejor fijo  ⟺  π·α·G > (1−π)·β·L
```

**Cor. 3.1 (Precisión sobre cobertura).** Si `p*` es casi-óptimo en amplias regiones,
`G` es chico y `L` grande ⟹ hay que minimizar `β` aun sacrificando `α`.

**Cor. 3.2 (Umbral de imposibilidad).** `β_max = π·α·G / ((1−π)·L)`. Todo router con
`β > β_max` **pierde garantizado** contra siempre-fallback, por buenas que sean sus
estrategias. → *Predice el colapso de Qwen3-30B a 27,5%.*

**Cor. 3.3 (Cobertura óptima).** Con `κ` calibrada y `τ` variable, el valor capturado
es unimodal en `τ`; el óptimo `τ*` tiene en general `cobertura ≪ 1`.
→ *Predice que Select-then-Solve, forzado a cobertura 100%, deja ~74% en la mesa.*

**Este es el teorema del paper.** No lo encontré en la literatura. Y ahora tiene respaldo
empírico externo (18.000 corridas ajenas) además del propio.

## 3.2 T2 — Cota riesgo-cobertura

Trasladar las garantías de clasificación selectiva (Chow; El-Yaniv & Wiener; teoría de
learning-to-defer) al espacio de paradigmas: cota sobre el riesgo condicionado a
cobertura `c`, con `κ` estimada del modelo de costos. Da la curva que reemplaza la
métrica "accuracy del router".

## 3.3 T3 — Determinismo y replayabilidad

`Π` pura + `θ_v` inmutable ⟹ `Π(φ(r), θ_v)` único para todo `(r, v)`. Demostración
trivial, pero es la propiedad que exige el despliegue regulado (EU AI Act, DORA) y el
enganche formal con MINERVA/HADD y con verificación conductual.

## 3.4 T4 — Calibración ⇒ optimalidad de la abstención

Si `κ` está `ε`-calibrada y la brecha real supera `2ε`, la decisión de abstención es
correcta. Condición usable: dice cuándo confiar y cuándo hace falta un probe.

## 3.5 T5 — Monotonía de seguridad bajo composición

Retículo de riesgo sobre combinadores; el riesgo del plan compuesto acotado por el join
de sus partes ⟹ gatear una hoja gatea el plan. Habilita certificación compositiva.

## 3.6 T6 — Re-optimización acotada

Con a lo sumo `m` replanificaciones y budget monótono decreciente, el costo total está
acotado y el proceso termina. Da garantía al tope de replan que las estrategias tipo DAG
fijan hoy como constante arbitraria.

---

# 4. EVIDENCIA DE CAMPO (reservada)

La motivación original de este trabajo salió de observar un portafolio de estrategias de
orquestación en producción cuya regla de selección era un prompt en prosa, y que perdió
contra una sola estrategia general. **Ese sistema es de un cliente y no entra en el
paper**: ni su código, ni sus rutas, ni sus conteos, ni el resultado atribuido a él.

Esto no debilita el argumento tanto como parecería, y conviene ser preciso sobre por qué.
El fenómeno **ya está documentado en forma pública y citable**: Select-then-Solve reporta
que el auto-ruteo zero-shot hace caer a Qwen3-Max a 42,4% y a Qwen3-30B a 27,5%, *por
debajo de sus propios baselines*. Rutear mal es peor que no rutear, y eso es literatura,
no anécdota.

Y lo que sí queda como aporte propio es mejor que una anécdota: el harness incluye una
topología DAG con verificar-replanificar sobre pizarra compartida como séptimo paradigma,
así que **la comparación se mide sobre corpus publicable** en vez de descansar en un
reporte de campo que nadie puede reproducir. El resultado, si se sostiene, es una
medición; antes era un recuerdo.

---

# 5. EVIDENCIA DE SISTEMAS: CLAUDE CODE

Los contratos de herramientas del harness exponen en prosa exactamente las decisiones a
formalizar:

| Decisión observable | Feature que la gobierna |
|---|---|
| Responder inline vs delegar | costo de contexto |
| Un subagente vs fan-out | independencia (F1) |
| `pipeline()` vs `parallel()` | **acoplamiento (F2)** |
| `loop-until-dry` | cardinalidad desconocida (F1/F4) |
| Verificación adversarial con quórum | ausencia de oráculo (F3) |
| `isolation: 'worktree'` | **contención (F6)** |
| `effort`/`model` por etapa | modelo de costos |
| Escalar profundidad al budget | restricción (F7) |

La documentación argumenta literalmente: *"a barrier is correct ONLY when stage N needs
cross-item context from all of stage N-1"* — **una heurística escrita a mano para F2**.

**Framing**: el mejor sistema desplegado hoy toma estas decisiones bien pero de forma
implícita, no determinística y no auditable. Este trabajo las hace explícitas,
deterministas y certificables. Presentarlo como *comportamiento observable en contratos
públicos*, no como conocimiento de implementación interna.

---

# 6. MAPO-Bench

## 6.1 Métrica principal (nueva)

No "accuracy del router" sino **fracción de la brecha de oráculo capturada como función de
la cobertura** — la curva riesgo-cobertura. Select-then-Solve reporta un punto (26% a
cobertura 100%). Nosotros reportamos la curva completa. **Ese gráfico es el paper.**

## 6.2 Reproducir y extender el setup de Select-then-Solve

Ventaja enorme: el baseline está publicado con números. Replicar su grilla (paradigmas ×
modelos × benchmarks) y agregar:
- el eje de cobertura (abstención)
- `π, α, β, G, L` medidos por celda → **verificación empírica directa de T1**
- distribución de `L` (mostrar la cola gruesa)
- el despliegue de referencia como dominio

## 6.3 Baselines

Cada paradigma fijo · **siempre-ReAct** (el fuerte) · router LLM zero-shot (el que pierde)
· router de embeddings à la Select-then-Solve · oráculo (cota superior) · nuestro selector
a varias coberturas.

## 6.4 Predicción falsable (registrar antes de correr)

> Existe `c* < 0,5` tal que el router selectivo a cobertura `c*` captura **>40%** de la
> brecha de oráculo, superando el 26% del router de cobertura total; y la ventaja se
> concentra en las celdas de `n` alto y `v = 1`. A cobertura 100% nuestro selector
> **empata o pierde** contra el de embeddings — y eso *confirma* T1 en vez de refutarlo.

---

# 7. MAPA DE PRESERVACIÓN v1 → v2

Regla de la skill: nada se borra. Todo se recontextualiza.

| # | Elemento v1 | v1 | Destino v2 | Acción |
|---|---|---|---|---|
| 1 | Def. 1.1 + Condiciones 1-3 | §1.2 | §3 Preliminares | Copia literal |
| 2 | Patrones CoT/ReAct/Reflection/Planning | §1.4 | §4 Espacio de paradigmas | Copia literal + mapeo a los 6 paradigmas de Select-then-Solve |
| 3 | **Las 11 arquitecturas** | §2.2 | §4 | **Conjunto generador del espacio.** Figura, texto y caso de uso íntegros + fila nueva con su expresión composicional |
| 4 | Nota Swarm vs Blackboard vs MAP | §2.2.2 | §4 | Copia literal — ya distingue arquitectura/patrón/mecanismo |
| 5 | Def. 11.1 Sistema plástico | §10.2.1 | §5 Capa de estadísticas | Copia literal |
| 6 | Def. 11.2 Regla Hebbiana | §10.2.2 | §5 | Copia literal, reinterpretada como actualización de `θ` |
| 7 | Def. 11.6 Memoria estructural | §10.2.5 | §5 | **Generalizar** `M_s: I×E→[0,1]` → `M_s: Φ×Ops→Est.`; conservar la original como caso particular |
| 8 | Supuestos A1-A4 | §10.2 | §5 | Copia literal + A5 (costo de extracción de `φ`) |
| 9 | Prop. 11.1 Convergencia | §10.2.2 | §5 | Copia literal — justifica estabilidad de `θ` |
| 10 | Thm 10.1 Cota de varianza + Cor. 11.1 | §10.3 | §5 | Copia literal + reforzar demostración (justificar independencia condicional) |
| 11 | Plasticidad L1/L2/L3 | §10.2.3 | §5 | Copia literal; L3 (prompt patching) pasa a ser edición manual de `θ` |
| 12 | Trust Graph | §10.2.4 | §5 | Copia literal + figura |
| 13 | 9 métricas MAP-Bench + protocolo | §10.4-10.5 | §6 | Copia literal, integradas |
| 14 | Cap. 2 Routing (Two-Layer) | Cap. 2 | **Cuerpo §4** | Two-Layer Routing = `Π` degenerado con abstención implícita. **Precursor directo del aporte** |
| 15 | Cap. 4 Orquestación | Cap. 4 | **Cuerpo §4** | Álgebra en forma informal |
| 16 | Cap. 8 Escalabilidad, Cap. 9 Observabilidad | Cap. 8-9 | **Cuerpo §8** + Ap. D | El ejecutor necesita runtime; EXPLAIN es observabilidad |
| 17 | Cap. 1,3,5,6,7 (Memoria, RAG, Datos, Visualización, Seguridad) | — | **Apéndice D íntegro** | Valiosas, no sirven a la tesis |
| 18 | Los 12 patrones | §5.5 | §4 | Varios son combinadores (Graceful Degradation = `SEQ` con fallback) |
| 19 | Evaluación v1 (+20pp, ablación, comparativas, SUS) | Cap. 5 | Ap. D + §6 | Reetiquetada honestamente: valida la premisa multi-agente, **no** la tesis de v2 |
| 20 | Limitaciones, casos de fallo, seguridad MAP, ética | §6.4-6.6 | §9 íntegro | Material fuerte, se expande |
| 21 | Apéndices A/B/C | — | A/B/C | Expandidos con demostraciones T1-T6 |
| 22 | 47+ diagramas SVG | — | Todos | + nuevos: curva riesgo-cobertura, espacio de features |

---

# 8. ESTRUCTURA DE v2

Objetivo: **20-25 páginas** de cuerpo. Venue: AAMAS / NeurIPS D&B / JAIR. arXiv cs.MA+cs.AI.

```
Título: "Cuándo Rutear y Cuándo Abstenerse: Selección Selectiva de Paradigma
         para Agentes LLM"
   (alt EN: "To Route or To Defer: Selective Paradigm Selection for LLM Agents")

Abstract (250 palabras)

1. Introducción
   1.1 El premio medido: 17,1pp de brecha de oráculo
   1.2 Nadie lo captura: 26%, y el auto-ruteo captura valor negativo
   1.3 Tesis: el problema es el encuadre decisional, no el selector
   1.4 Contribuciones (3)
   1.5 Organización

2. Trabajo relacionado  ⚠️ sección crítica, tiene que ser generosa y precisa
   2.1 Búsqueda automática de workflows (AFlow, ADAS, GPTSwarm, A2Flow)
   2.2 Selección en tiempo de inferencia (Select-then-Solve, FlowBank, TRACE-Router,
       Uno-Orchestra) — nuestro punto de partida
   2.3 Modelos de costos de workflows (GLOW, Multi-View Encoders, Cost-Aware Agentic
       Query Execution, Batch Query Processing)
   2.4 Agentes que aprenden sin actualizar pesos (ExpeL, ERL, MemSkill, R²-Mem,
       reglas conductuales, aprendizaje metacognitivo)
   2.5 Clasificación selectiva y learning-to-defer (Chow, El-Yaniv & Wiener)
   2.6 Políticas interpretables (Neural DNF-MT, ORCAID) y gobernanza en runtime
   2.7 Determinismo en dominios regulados (MINERVA/HADD, verificación conductual)
   2.8 Posicionamiento (tabla §1.4)

3. Preliminares  [← v1 §1.2, §1.4]
4. Espacio de paradigmas  [← v1 §2.2 íntegro, §5.5]
5. Capa de estadísticas: MAP como base de θ  [← v1 cap. 10 íntegro]
6. Selección selectiva
   6.1 Features estructurales  6.2 La función de confianza κ
   6.3 θ como lista de decisión interpretable  6.4 Calibración de τ
   6.5 El artefacto EXPLAIN  6.6 Aprendizaje offline y promoción versionada
7. Resultados teóricos  T1 (+3 corolarios), T2-T6
8. Evaluación
   8.1 PI1-PI5  8.2 Replicación del setup de Select-then-Solve
   8.3 ⭐ Curvas riesgo-cobertura  8.4 ⭐ Verificación empírica de T1
   8.5 Ablaciones  8.6 Overhead de φ
   8.7 ⭐ La topología DAG frente al fallback general
9. Discusión  [← v1 §6.4-6.6 íntegros]
10. Trabajo futuro  11. Conclusión

Apéndices: A definiciones · B demostraciones T1-T6 · C reproducibilidad ·
D despliegue de referencia (las 10 capacidades ÍNTEGRAS) ·
E Catálogo de paradigmas del harness y su parametrización
```

---

# 9. HOJA DE RUTA A PRODUCCIÓN

| Etapa | Entregable | Valor propio | Esfuerzo |
|---|---|---|---|
| **E0** | **Piloto revisado** (§10) | Mide `β` y la curva riesgo-cobertura | 1-2 sem |
| E1 | Logger EXPLAIN: `(φ, plan, outcome, costo)` en el despliegue de referencia | Observabilidad + dataset para `θ`. Útil sin rutear nada | 1 sem |
| E2 | Extractor `φ` + medición de overhead | Telemetría de forma de tasks | 2 sem |
| E3 | Ejecutor de combinadores (reemplaza estrategias ad-hoc por composición) | Elimina la duplicación entre estrategias | 3-4 sem |
| E4 | `κ` calibrada + `θ` como lista de decisión versionada | Confianza medible | 2 sem |
| E5 | **Selector en modo shadow** (decide y loguea, no ejecuta) | Mide `α,β,G,L` en producción con **cero riesgo** | 1 sem |
| E6 | Activación con `τ*` y abstención al fallback | La ganancia real, con la disciplina de T1 | 2 sem |
| E7 | Promoción de `θ` con guarda anti-regresión (estilo SPM) | Aprendizaje continuo sin regresiones | 2 sem |

**E5 es el punto clave**: permite medir todo lo que el paper necesita, en producción, sin
riesgo. Y es el paso que los routers en prosa nunca dan — sin él no hay señal por
estrategia, y sin señal el set de reglas sólo se puede parchear por anécdota.

---

# 10. ⛔ CRITERIOS DE DESCARTE — CORRER ANTES DE ESCRIBIR

v1 se escribió completo antes de validar su contribución y quedó sin aval. No repetir.

Ya no hace falta medir si el premio existe: Select-then-Solve lo midió en 17,1pp con
18.000 corridas. **E0 mide si la abstención lo captura, y a qué costo por nivel de
garantía.**

## 10.1 ⚠️ La precondición que ninguna regla de decisión puede saltear

**El oráculo está sesgado hacia arriba y hay que descontarlo antes de decidir nada.**

La brecha del oráculo se mide como `E[max_p û_p]`, y un máximo sobre estimadores
ruidosos excede el máximo de las medias **incluso si todos los paradigmas fueran
idénticos**. No es un detalle: `gpt-5-chat` rechaza cualquier `temperature` explícita
(devuelve 400, verificado 2026-08-23), así que el muestreo va al default del modelo y el
sesgo es real y no acotado a priori.

Aplicar la regla *"si algún `c*` captura > 26% de la brecha, el paper existe"* a la
brecha **medida** puede declarar que el paper existe sobre ruido. Y todo lo que venga
después hereda ese error sin que nada avise.

**El descuento se mide, no se modela.** `Study.noise_floor` toma `k` réplicas del
**mismo** paradigma en cada tarea y las trata como si fueran `k` paradigmas distintos:
toda la brecha que aparece ahí es ruido por construcción, porque los "paradigmas" son la
misma cosa. `credible_oracle_gap` reporta `medida`, `piso` y `neta = medida − piso`.

| Precondición | Si no se cumple |
|---|---|
| `piso_ruido < 0,5 × brecha_medida` | 🔧 **Nada es decidible todavía.** Subir `repeat` (el piso baja con √k), o migrar a `gpt-5.4-1`, que **sí acepta `temperature=0`** (verificado). Es más caro y es un modelo de razonamiento — lo que cambia qué se mide — pero elimina la fuente del sesgo |
| `repeat ≥ 3` | 🔧 Con una sola réplica el piso no es estimable y el punto anterior no se puede evaluar |

**Todas las reglas de §10.3 se aplican a la brecha NETA.** Nunca a la medida.

## 10.2 El protocolo, contra el harness que existe

```powershell
cd "D:\Apps\MAPO\paperlab"

# 1. La capa de medición, antes de gastar un token
py tests\test_science.py            # 39 checks
py tests\test_consolidation.py      # 24 checks, incluye el guard de confabulación

# 2. Corpus con ground truth exacto, y su verificación independiente
py corpus\generate.py --seed 7 --people 48 --per-cell 5 --widths 4,16,48 --out corpus\gold_v1
py corpus\verify.py --corpus corpus\gold_v1

# 3. Costo por tarea antes de comprometer la corrida
py -c "from app.config import Settings; from app.runner import Runner; \
       r=Runner(Settings.from_env(),'gold_v1'); r.run_cross_product(limit=2, repeat=3)"

# 4. La corrida
py -c "from app.config import Settings; from app.runner import Runner; \
       r=Runner(Settings.from_env(),'gold_v1'); r.run_cross_product(repeat=3)"
```

| Parámetro | Valor | Por qué |
|---|---|---|
| Corpus | `gold_v1` sintético | ground truth exacto, publicable, cardinalidad y acoplamiento como diales |
| Paradigmas | **7** | los 5 de Select-then-Solve + map-reduce + DAG con verificar-replanificar |
| `temperature` | `model_default` (omitida) | explícita da 400 en `gpt-5-chat` |
| `seed` | pineado, +1 por réplica | réplicas independientes con cache separado |
| `repeat` | **≥ 3** | sin esto el piso de ruido no existe |
| Calificación | **set F1 exacto, sin judge** | el efecto es de pocos pp; el ruido de un judge es del mismo orden e indistinguible |
| Escala | ~60 tareas × 7 × 3 = **1.260 corridas** | `--per-cell 5`. Dominada en costo por `dag_strategy` (~12× el prior más barato) |

El cache es content-addressed: la segunda pasada es gratis e idéntica, y una corrida
interrumpida retoma sin repetir trabajo.

## 10.3 Reglas de decisión (sobre la brecha NETA)

| Resultado | Decisión |
|---|---|
| Precondición §10.1 no se cumple | 🔧 **No decidir.** Subir `repeat` o migrar de modelo |
| brecha neta ≤ 0 | ⛔ **No hay premio medible en este corpus.** Revisar si el corpus estratifica de verdad antes de concluir sobre el mundo |
| Existe `c*` con capturado **> 26%** de la brecha **neta** | ✅ **El paper existe.** Adelante con §8 |
| Capturado máximo en `c* ≈ 1` | ⚠️ T1 sobrevive como teoría; el aporte empírico de la abstención se debilita. La tesis R3 (garantía graduada) no depende de esto |
| `L` de cola fina y `π` alto | ⚠️ Sospechar del baseline: quizá `react` está mal implementado. Verificar antes de festejar |
| `dag_strategy` pierde contra `react` | ✅ Resultado propio: la topología más elaborada no le gana al fallback general |
| Nada supera a siempre-`react` a ninguna cobertura | ⛔ Publicar el **resultado negativo con T1 como explicación formal**. Sigue siendo un paper, y honesto |

## 10.4 El experimento que exige la tesis R3

§10.3 evalúa el ruteo selectivo, que bajo R3 es un resultado *dentro* del marco y no el
marco. La tesis de la garantía graduada necesita su propia predicción falsable,
**registrada antes de correr**:

> Sobre el mismo corpus, el costo en tokens y la cobertura crecen monótonamente de A0 a
> A3, y existe al menos una celda de features donde A3 excluye el paradigma que A0
> habría elegido. Si el costo NO crece con el nivel, la graduación no compra nada y la
> tesis R3 se cae.

Se mide corriendo `Runner.report()` a los cuatro niveles sobre las mismas filas — cero
llamadas nuevas al LLM, porque el producto cruzado ya está registrado.

Y el segundo, que decide si A2 puede admitir creencias elicitadas: **el diagrama de
confiabilidad**. Cuando el modelo declara 0,8 de confianza sobre una propiedad
estructural de la tarea, ¿acierta el 80%? `Calibration.expected_calibration_error` lo
mide por proposición. Un ECE alto es un resultado publicable por sí solo.

## 10.5 Lo que E0 NO puede decidir

- **Validez externa.** Un corpus sintético dice qué propiedad estructural gobierna qué
  paradigma; no dice que la distribución de tareas del mundo tenga esas proporciones.
  Para eso hacen falta los benchmarks públicos, y eso es la corrida siguiente.
- **Latencia.** `dag_strategy` corre secuencial en el harness. Calidad y tokens son
  comparables; latencia **no**, y no se puede reportar como si lo fuera.
- **Si la idea es buena.** E0 decide si es *medible*.

---

# 11. RIESGOS

| # | Riesgo | Estado | Mitigación |
|---|---|---|---|
| R1 | Novedad del optimizador de planes | ⛔ **Materializado** | Cedido. El aporte se movió a abstención + determinismo |
| R2 | Que el premio no exista | ✅ **Descartado** | 17,1pp medidos externamente |
| R3 | Que la abstención no ayude | 🔴 **Riesgo principal ahora** | E0 lo mide directo |
| R4 | Alguien publique abstención en ruteo de paradigmas antes | 🟡 Vivo — **re-verificado libre 2026-08-26** | La ventana se cierra a la vista: 2608.00106 (jul-2026) nombra un confidence gate con fallback a ruteo estático como trabajo futuro; ReDAct (2604.07036) y 2605.07805 tienen la maquinaria de deferral en dominios vecinos. **Hay que ir rápido o aceptar quedar segundo** |
| R5 | Costo de extraer `φ` ≈ costo de ejecutar | 🟡 | Medir y reportar (§6.2) |
| R6 | "Es un árbol de if-else" | 🟡 | Es el punto: un if-else *auditable y calibrado*. T1+T2 lo hacen más que heurística |
| R7 | Solapamiento con MINERVA/HADD | 🟡 | Citar generoso, diferenciar preciso. Es el antecedente del EVR gate y del encuadre Kautz Type-2 |
| R9 | **SCL / Soft Symbolic Control** (2511.17673) publica una capa de gobernanza simbólica sobre inferencia probabilística | ✅ **Resuelto 2026-08-23** | Verificado: es **modo global único**, sin graduación por request, sin procedencia, sin acotamiento de patrones, sin calibración. Es el trabajo relacionado más cercano y hay que diferenciarlo con precisión — pero el núcleo de R3 está libre. ✅ Leído completo el 2026-08-26: la cesión se sostiene (GATE §8quater) |
| R10 | **Comparaciones múltiples** en el descubrimiento de proposiciones | 🟡 | Mitigado en código: el registro se parte en tres *por tarea* — `search` propone, `validate` puntúa, `final` lo toca sólo la guarda de promoción. Una partición nunca se puntúa con los datos que la propusieron. Es el mecanismo por el que "detectar verdades" no degenera en confabularlas |
| R11 | El sesgo del oráculo hace pasar ruido por premio | ✅ **Resuelto** | Precondición §10.1: `piso_ruido < 0,5 × brecha_medida` y `repeat ≥ 3`, con todas las reglas contra la brecha neta |
| R12 | Cesiones de novedad hechas sobre abstracts, no papers completos | ✅ **Resuelto 2026-08-26** | Select-then-Solve y SCL leídos completos: 6/6 números verificados contra el cuerpo, cesión a SCL correcta (y generosa: su capa simbólica es un metaprompt). Huecos de novedad A-E confirmados libres. Ver GATE §8quater |
| R8 | Calibración de `κ` es difícil | 🟡 | Literatura de calibración establecida; declarar como limitación |

---

# 12. CHECKLISTS

## Antes de escribir
- [ ] **E0 corrido**: `π, α, β, G, L`, distribución de `L`, curva riesgo-cobertura
- [ ] **Leer Select-then-Solve (2604.06753) completo** — es el trabajo de partida
- [ ] Leer FlowBank (2606.11290), TRACE-Router (2607.22465), Uno-Orchestra (2605.05007)
- [ ] Leer Cost-Aware Agentic Query Execution (2606.03152), AFlow (2410.10762)
- [ ] Leer Neural DNF-MT (2501.03888), ORCAID (2607.07235)
- [ ] Buscar específicamente: ¿alguien ya hizo *abstención* en ruteo de paradigmas?
- [ ] Predicción §6.4 registrada con fecha
- [ ] Decidido si contactar a Jaime & Errecalde
- [ ] Nombre decidido

## Preservación v1 (regla de oro: nada se borra)
- [ ] Las 11 arquitecturas íntegras (figura + texto + caso de uso) en §4
- [ ] Def. 1.1, Condiciones 1-3 literales
- [ ] Cap. 10 (MAP) completo en §5: Def. 11.1/11.2/11.6, A1-A4, Prop. 11.1, Thm 10.1,
      Cor. 11.1, L1/L2/L3, Trust Graph, Memoria Estructural
- [ ] Def. 11.6 original conservada como caso particular de la generalizada
- [ ] 9 métricas MAP-Bench + protocolo
- [ ] Las 10 capacidades íntegras en Apéndice D
- [ ] Los 12 patrones presentes
- [ ] Evaluación v1 completa (ablación, comparativas, SUS) en Ap. D + §6
- [ ] §6.4 limitaciones, §6.4.4 casos de fallo, §6.4.5 seguridad MAP, §6.6 ética
- [ ] Apéndices A/B/C de v1
- [ ] Los 47+ SVG referenciados
- [ ] **Nada eliminado, resumido ni condensado**

## Estructural v2
- [ ] Abstract 250 palabras
- [ ] 3 contribuciones enumeradas y medibles
- [ ] Trabajo relacionado con las 8 subsecciones de §8
- [ ] T1 con 3 corolarios + demostraciones en Ap. B
- [ ] Curva riesgo-cobertura como figura principal
- [ ] Verificación empírica de T1 (`α,β,G,L,π` por celda)
- [ ] La topología DAG medida contra el fallback general (§8.7)
- [ ] Overhead de `φ` reportado
- [ ] Limitaciones, amenazas a la validez, ética
- [ ] 60-80 referencias

---

# 13. RESUMEN DE LA DECISIÓN

**Lo que se cede**: el optimizador de planes agéntico, el álgebra como novedad, el
portafolio con selección por query, el modelo de costos. Todo publicado entre oct-2024 y
jul-2026.

**Lo que queda, y es mejor**: el premio está medido en **17,1pp** y **nadie captura más
del 26%**. La razón es que todos los routers publicados están obligados a elegir siempre.
Un router **selectivo con abstención calibrada** ataca directo ese 74% no reclamado, y
T1 dice exactamente cuándo y cuánto. Encima, hacerlo **determinístico e interpretable**
abre el despliegue regulado que los routers neuronales no pueden tocar — y ahí MAP de v1
resulta ser el substrato correcto.

**El activo propio**: el harness con siete paradigmas sobre corpus publicable, que
convierte la comparación en medición reproducible en vez de reporte de campo.

**Riesgo principal**: R3 — que la abstención no capture más que la cobertura total.
**Mitigación**: E0, dos semanas, sobre código que ya existe.

**Riesgo secundario y real**: R4 — el campo se mueve en meses. Hay que ir rápido.

**Próximo paso**: aprobar o ajustar. Con el OK, Fase 2 arranca por **E0**, no por escribir.

---

# 14. ESTRATEGIA DE PUBLICACIÓN Y AVAL

> ### ⚠️ CORRECCIÓN R2 — leer antes que el resto de §14
>
> Dos afirmaciones de §14 quedaron mal y se corrigen acá:
>
> **(a) `cs` es UN solo dominio de endorsement.** La doc de arXiv dice: *"most high-level
> subject areas are currently endorsement domains, with the notable exception of physics,
> in which individual subject classes are endorsement domains."* Por lo tanto cs.LG,
> cs.AI, cs.CL y cs.MA **están todos en el mismo dominio**. Un aval para cs habilita
> todas. ⇒ **§14.3 queda ANULADA**: elegir cs.LG para "coincidir con el dominio de
> Errecalde" no tiene sentido. La categoría se elige por mérito y audiencia.
> Recomendación por contenido: **cs.LG primary + cs.AI cross-list**.
>
> **(b) El autor YA publicó en arXiv en matemática.** `math` y `cs` son dominios
> distintos, así que ese paper **no transfiere** y sigue haciendo falta un aval para cs.
> Pero cambia la naturaleza del pedido: es un autor verificable con historial, no un
> desconocido. ⇒ **§14.1 se corrige**: el aval directo es viable; la co-autoría pasa a
> ser plan B, no la única vía.
>
> **(c) Consecuencia sobre los blancos.** Como cualquier persona elegible en cs sirve, el
> pool es enorme y conviene apuntar a autores **citados centralmente**. Errecalde se
> degrada (su línea propia —eRisk, detección temprana— no toca orquestación de agentes;
> el único puente era MINERVA, y Jaime queda descartado como vía). **Blanco principal
> nuevo: la comunidad de learning-to-defer / clasificación selectiva**, que es la
> maquinaria formal de T1:
> - Hussein Mozannar & David Sontag (MIT) — fundadores de L2D
> - Rajeev Verma & Eric Nalisnick — L2D calibrado (arXiv 2202.03673)
> - Mehryar Mohri (NYU/Google) — L2D con múltiples expertos, consistencia Bayes (2407.13732)
> - Philip Torr / Zhenfei Yin — co-autores de Select-then-Solve (2604.06753)
>
> Pitch: *"aplicamos su framework de learning-to-defer a la selección de paradigma en
> agentes LLM y derivamos la condición exacta bajo la cual rutear paga"*. Es una
> aplicación nueva de **su** teoría, en un área caliente, con 17,1pp de brecha sin capturar.
>
> **(d) Requisito del avalista**: papers en el dominio enviados **entre 3 meses y 5 años**
> atrás. El umbral numérico arXiv no lo publica.
>
> **(e) Primer paso, gratis**: arrancar la submission a cs.LG con la cuenta existente.
> arXiv muestra la pantalla de solicitud con avalistas elegibles sugeridos. No adivinar.

## 14.1 ⚠️ arXiv cambió la política el 2026-01-21

El email institucional **ya no es suficiente**. Un submitter nuevo necesita ahora
**email institucional Y autoría previa en un paper del dominio de endorsement** de la
categoría destino. Se aplicó primero a Matemática (dic-2025) y se extendió a todas las
secciones, incluidas cs.AI y cs.LG.
Fuente: https://blog.arxiv.org/2026/01/21/attention-authors-updated-endorsement-policy/

**Consecuencia**: conseguir una afiliación universitaria ya no resuelve el problema.
**La vía es la CO-AUTORÍA, no el aval.**

## 14.2 Candidato principal: Marcelo Errecalde (UNSL)

Tiene standing en arXiv confirmado:

| Paper | ID | Categorías | Fecha |
|---|---|---|---|
| Gambling Disorder: UNSL at MentalRiskES 2025 | 2511.23325 | **primary cs.CL** | nov-2025 |
| Time-Aware Early Detection of Anorexia: UNSL at eRisk 2024 | 2410.17963 | primary cs.CY, cross cs.CL + cs.LG | oct-2024 |

Co-autor en ambos: Horacio Thompson. Registro largo en dblp (pid 66/1156), eRisk/CLEF
desde varios años. Profesor en UNSL. **Y es co-autor de MINERVA (Zenodo 20003407), que
este paper cita centralmente.**

**Su dominio de endorsement es cs.CL / cs.LG / cs.CY — NO cs.AI ni cs.MA.**

## 14.3 ⭐ Decisión de categoría (consecuencia táctica)

**Apuntar primary a cs.LG, cross-list a cs.AI.** No es un truco: el núcleo teórico del
paper es **clasificación selectiva / learning-to-defer** (T1, T2), que es machine learning
puro. cs.LG es su casa natural. Alinear la categoría con el dominio del avalista es gratis
y mejora el encuadre. **Descartar cs.MA como primary.**

⚠️ Verificar: no está confirmado si los cross-lists cuentan igual que las submissions
primarias para elegibilidad de endorsement. No adivinar — arXiv le muestra al endorser
exactamente para qué categorías puede avalar.

## 14.4 Plan ordenado por probabilidad

| # | Vía | Standing | Probabilidad | Notas |
|---|---|---|---|---|
| 1 | **Co-autoría con Errecalde (UNSL)** | ✅ cs.CL/cs.LG | **Alta** | Si él sube el paper, el problema desaparece. Y quedás con autoría previa en el dominio → habilitado para siempre |
| 2 | **Jaime (UNLP) como puente** | ❌ (sólo Zenodo) | Alta como contacto | No es el avalista: es la puerta de entrada a Errecalde. Temáticamente el colaborador más cercano que existe |
| 3 | Grupo Select-then-Solve (Philip Torr, Zhenfei Yin, Heng Zhou et al.) | ✅ masivo | Baja (frío) | **Escribirles igual**: se está extendiendo su resultado. Su feedback vale más que el aval, y avisar es buena práctica |
| 4 | Zenodo primero con DOI | N/A | 100% | Fallback. Es lo que hizo Jaime, probablemente por este mismo problema |

## 14.5 El pitch (oferta de colaboración, no pedido de favor)

Errecalde co-firmó un paper que argumenta que los dominios regulados necesitan decisiones
deterministas en las fronteras del sistema. MINERVA es un **paradigma**; le falta un
**mecanismo concreto con garantías**. Este trabajo aporta exactamente eso:

- Un problema concreto donde el determinismo importa: selección de paradigma.
- Un teorema (T1) que dice **cuándo** la decisión paga y cuándo hay que abstenerse.
- La construcción que **unifica determinismo y abstención**: la zona no determinística
  cae al fallback por diseño, así que toda decisión ruteada es replayable.
- El encuadre **Kautz Type-2** (`Symbolic[Neuro]`) que él ya usa como keyword: selector
  simbólico determinístico invocando paradigmas neuronales.
- El colapso de Qwen al auto-rutear como evidencia pública de que
  reporta Select-then-Solve.

Es una contribución a *su* línea de investigación, en *su* vocabulario. La probabilidad
de que le interese es alta.

## 14.6 Checklist de aval
- [ ] Contactar a Jaime (UNLP) presentando la conexión con MINERVA/HADD
- [ ] Vía Jaime o directo (UNSL / academia.edu / dblp), contactar a Errecalde
- [ ] Preguntarle para qué categorías puede avalar (arXiv se lo muestra)
- [ ] Confirmar cs.LG como primary
- [ ] Mail de cortesía al grupo de Select-then-Solve (hengzzzhou/STS en GitHub)
- [ ] Preparar Zenodo con DOI como fallback
