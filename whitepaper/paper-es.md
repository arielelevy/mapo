# La factibilidad antes de la selección: cuándo importa realmente la topología de orquestación en agentes LLM

**Borrador 0.1 — 2026-08-23**
**Autor**: Ariel Edgardo Levy
**Estado**: borrador de trabajo. La teoría está completa y verificada por máquina; las
mediciones son preliminares, n=1 por celda. Toda afirmación empírica lleva su tamaño de
muestra. Destino: arXiv cs.LG (primario), cs.AI (cross-list).

> **Traducción de `paper-en.md`, que es la versión canónica.** Si difieren, manda el inglés.

---

## Resumen

Elegir el paradigma de razonamiento por tarea tiene un premio grande y medido: la
selección oráculo supera al mejor paradigma fijo por 17,1pp, el mejor ruteador publicado
recupera cerca de un cuarto de esa brecha, y el auto-ruteo zero-shot recupera valor
negativo. Sostenemos que el cuello de botella no es la capacidad del selector sino el
encuadre de la decisión, y desarrollamos tres resultados **delante** del problema de
aprendizaje en lugar de dentro de él.

Primero, **la factibilidad es aritmética**. Si una topología puede correr una tarea es
computable a partir de cantidades declaradas — cuántas unidades, cuán largas, cuál es el
presupuesto — sin una sola llamada al modelo y sin estadística. Sobre un corpus escalado
de 16k a 1,27M de tokens esto poda tres de siete topologías candidatas antes de gastar un
token, y separa dos modos de falla que se confunden de rutina: a map-reduce lo acota la
**cardinalidad**, no el tamaño total.

Segundo, **la selección paga sólo bajo una condición precisa**. Damos el Teorema del Valor
de Selección, `π·α·G > (1−π)·β·L`, y sus corolarios: un ruteador obligado a elegir siempre
no tiene control sobre su tasa de falsos positivos, así que la cobertura óptima está
generalmente muy por debajo de uno. Mostramos además que donde existe un detector de falla
barato, escalar domina a predecir — un ruteador que se equivoca paga una pérdida de
calidad, una cascada paga una pérdida de costo — lo que particiona el problema por
**verificabilidad** y no por tipo de tarea.

Tercero, y empíricamente, **la superficie de herramientas gobierna la varianza que se le
atribuye a la elección de topología**. Sobre cuatro celdas de features, los paradigmas que
no usan herramientas abarcan un rango de costo de 1,2×; los que sí, de 50×. Agregar una
sola señal — que el retriever no devuelve nada nuevo desde tres búsquedas — cortó el costo
de la topología más elaborada 3,05× contra una dispersión de réplica de 1,62× sobre la
misma medida.

Contribuimos la teoría, una capa de medición verificada por máquina, un generador de
corpus con ground truth exacto en cuatro escalas, y un análisis preliminar de fallas de
siete topologías. **No** contribuimos todavía un selector validado.

**Palabras clave**: agentes LLM, orquestación, predicción selectiva, aprender a diferir,
generación aumentada por recuperación, diseño de herramientas, evaluación de agentes

---

# 1. Introducción

## 1.1 Un premio medido que nadie cobra

El *paradigma* de un agente LLM — la estructura de control que envuelve al modelo: una
llamada única, un bucle de razonamiento, una descomposición, un grafo de
verificar-replanificar — normalmente se elige una vez en tiempo de diseño y se congela en
el código. Trabajo reciente mide lo que eso cuesta. Sobre seis paradigmas, cuatro modelos
frontera y diez benchmarks (~18.000 corridas), la selección oráculo por tarea supera al
mejor paradigma fijo por **17,1pp** en promedio, con oscilaciones individuales de hasta
+44pp y −15pp según el emparejamiento [Select-then-Solve, arXiv:2604.06753].

El mismo trabajo muestra que el premio no se está cobrando. Un ruteador entrenado sobre
embeddings recupera aproximadamente un cuarto de la brecha. El auto-ruteo zero-shot —
pedirle al modelo que elija su propio paradigma — recupera valor *negativo*: dos modelos
caen por debajo de sus propias líneas base de paradigma único, uno hasta 27,5%.

Entonces: el premio es grande, el mejor intento publicado captura una minoría, y el
intento ingenuo es peor que no intentar. Ese patrón invita a concluir que hacen falta
mejores selectores. Nosotros sostenemos que invita a otra conclusión.

## 1.2 Tres afirmaciones que preceden al problema de aprendizaje

**La factibilidad es aritmética, y es gratis.** Antes de preguntar cuál topología es
*mejor*, se puede preguntar cuál puede *correr*. Esa pregunta se responde con cantidades
que la tarea ya declara. Una política aprendida que gasta episodios descubriendo que
map-reduce pierde en tareas de 500 unidades está aprendiendo aritmética por el camino
difícil; el tope era computable antes del primer token.

**La selección paga sólo bajo una condición precisa.** Un ruteador que debe elegir siempre
no tiene ningún grado de libertad sobre su tasa de falsos positivos y por lo tanto paga
cada error de ruteo. Formalizamos cuándo la selección le gana a un fallback fijo y
mostramos que el punto de operación óptimo generalmente implica **abstenerse en la mayoría
de las solicitudes** — lo que no es un ruteador más débil sino un objetivo distinto.

**Mucho de lo que se le atribuye a la topología es atribuible a las herramientas.** En
nuestras mediciones los paradigmas que usan herramientas de recuperación abarcan un rango
de costo de cincuenta veces mientras los que no lo hacen abarcan 1,2×. Un benchmark que no
reporta la calidad de su superficie de herramientas no está comparando topologías; está
comparando un retriever envuelto de siete maneras.

## 1.3 Qué establece y qué no establece este borrador

**Establecido**: la teoría (§5), verificada por máquina contra distribuciones sintéticas de
respuesta conocida; una capa de factibilidad (§4) validada sobre cuatro escalas de corpus;
un generador de corpus cuyo ground truth se re-deriva de forma independiente a partir de
los documentos (§6).

**Preliminar**: cada número empírico de §7 y §8 es n=1 por celda, sobre un corpus, con un
modelo. La varianza entre réplicas sobre la topología más elaborada se midió en hasta
3,93× en costo, así que las magnitudes son indicativas. Los *mecanismos* son más robustos
que las magnitudes, porque descansan en trazas de uso de herramientas y no en tamaños de
efecto.

**No establecido**: un selector validado, ningún resultado sobre benchmarks públicos, y
ninguna afirmación sobre otro régimen que no sea extracción de respuesta exacta sobre
colecciones de documentos.

**Estructuralmente no puesto a prueba**, que es más fuerte que «no establecido» y salió de
medir. §5.2 parte el problema según `v`, la disponibilidad de un detector barato en runtime,
y manda `v = 1` a una cascada y `v = 0` a un ruteador. **Todos los corpus de este registro
caen del lado `v = 1`.** No por elección: corregir sin juez significa corregir por
coincidencia exacta, la coincidencia exacta necesita una respuesta de referencia, y el mismo
campo se leía como el detector de runtime — así que 25 de 26 tareas por corpus declaraban
`v = 1`. La regla de cascada dispara con prioridad más alta que la de selección, así que
sobre dos corpus held-out independientes **la regla de selección no disparó nunca**, y los
dos veredictos de ruteo son mediciones de la cascada.

La forma general es una advertencia sobre toda una clase de experimento, no sobre éste:

> Un benchmark que establece corrección por coincidencia exacta contra una referencia
> **tiene un detector barato en cada tarea por construcción**, y por lo tanto no puede
> ejercitar la rama `v = 0` de su propia partición. Ser corregible implica ser verificable.

Si la selección paga donde verificar es genuinamente imposible queda, en este registro,
**abierto** — y necesita un corpus cuya disponibilidad de detector se declare por tarea en
vez de heredarse de la clave de respuestas.

---

# 2. Trabajo relacionado

## 2.1 Búsqueda automática de workflows

AFlow reformula la optimización de workflows como búsqueda sobre workflows representados
como código, con MCTS sobre operadores [arXiv:2410.10762]; ADAS y GPTSwarm buscan en
espacios afines. Estos producen **un** workflow por benchmark, offline. Nuestro interés es
la selección por solicitud dentro de un conjunto fijo y — antes de eso — qué miembros del
conjunto pueden correr siquiera.

## 2.2 Selección de paradigma en tiempo de inferencia

Select-then-Solve entrena un ruteador liviano sobre embeddings para elegir un paradigma por
tarea [arXiv:2604.06753]. FlowBank construye un portafolio offline y selecciona por consulta
[arXiv:2606.11290]. TRACE-Router rutea a granularidad de traza de tarea y no de solicitud
[arXiv:2607.22465]. Uno-Orchestra aprende una política conjunta de descomposición y despacho
[arXiv:2605.05007].

Todos operan a **cobertura uno**: toda tarea recibe un paradigma. §5.1 sostiene que ésa es
la restricción vinculante, más que la capacidad del modelo, y ninguno reporta una curva de
riesgo-cobertura. Dos detalles de Select-then-Solve, verificados contra el paper completo y
no contra su abstract (2026-08-26): su oráculo es un *máximo empírico sin corregir* por
tarea, y sus propias limitaciones anotan que la muestra es fija, sin re-muestreo entre
seeds — exactamente el sesgo hacia arriba que nuestro protocolo de piso de ruido (§6.1)
existe para descontar. Y la maquinaria de deferral existe al lado, sin haber cruzado:
ReDAct difiere decisiones individuales a un modelo más grande sobre un umbral calibrado de
incertidumbre [arXiv:2604.07036]; el ruteo por descomposición de incertidumbre unifica
abstención y ruteo con garantías distribution-free, para clasificadores [arXiv:2605.07805];
y el meta-ruteo composicional entrena un ruteador interpretable sobre features textuales y
nombra un confidence gate con fallback a ruteo estático como trabajo futuro sin evaluar
[arXiv:2608.00106]. Nadie aplica abstención a la selección de paradigmas (buscado
2026-08-26); la ventana se está cerrando a la vista.

## 2.3 Modelos de costo para workflows

GLOW predice performance de workflows agénticos a partir de features de grafo y de lenguaje
[arXiv:2512.15751]; Cost-Aware Optimization for Agentic Query Execution hace explícita la
analogía con la optimización clásica de consultas [arXiv:2606.03152]. Tomamos la analogía
como establecida y no la reclamamos. Nuestro aporte está aguas arriba: un filtro duro de
factibilidad que un modelo de costo no reemplaza, porque **un plan infactible no tiene
costo**.

## 2.4 Gobernanza simbólica sobre inferencia probabilística

El Structured Cognitive Loop introduce Soft Symbolic Control, un mecanismo de gobernanza
sobre inferencia probabilística [arXiv:2511.17673]. Es el trabajo más cercano a §6.2, y
leído completo (2026-08-26) su gobernanza se parte en dos: *Regulation*, un metaprompt
persistente en lenguaje natural cuya efectividad el propio paper anota que depende de qué
tan bien el LLM interprete instrucciones, y *Control*, un runtime determinista que aplica
reglas duras fijas al historial de ejecución del turno — llamadas duplicadas, conteo de
errores, profundidad de ciclos — no al contenido proposicional. Control sí carga una
clasificación de riesgo por acción (cachear una lectura segura, bloquear una llamada
crítica repetida, congelar para autorización humana), pero es una clase estática sobre
acciones individuales dentro de un único loop fijo. Opera como **un modo global único**: no
gradúa la garantía por solicitud, no deriva el nivel requerido de creencias sobre la
solicitud, no restringe el espacio de planes admisibles por nivel, y no calibra la
confianza declarada por el modelo. Esas cuatro cosas son lo que agregamos — sobre una base
de creencias sobre la que decide la capa simbólica, no un metaprompt que se le pide al
modelo obedecer.

Cerca, en la capa de creencias misma: Nous acota la confiabilidad de una creencia por la
procedencia del canal [arXiv:2606.22030], MemIR tipa la memoria por procedencia para
impedir el colapso de fuentes [arXiv:2605.25869], Eywa promueve hechos sólo cuando pasan
validadores contra evidencia inmutable [arXiv:2605.30771], y HEP hace auditable la
evolución de hipótesis — aunque toda evidencia validada mueve la creencia por igual, sin
jerarquía de procedencia que gatee la promoción [arXiv:2607.09195]. El problema del jardín
de senderos que se bifurcan — agentes que proponen y puntúan hipótesis sobre los mismos
datos — está diagnosticado empíricamente en [arXiv:2607.01507] sin un mecanismo; la
partición proponer/puntuar de §6.3 es uno.

MINERVA/HADD es el antecedente más cercano de la capa de creencias misma, y leído completo
(2026-08-26) aporta **mecanismo, no vocabulario** [Zenodo 10.5281/zenodo.20003407]. Los
invariantes HADD ya contienen: el LLM confinado a sensor tipado que nunca toma decisiones
de flujo de control; una capa de cognición determinista que es función pura de la base de
creencias — "mismo estado → misma acción", que es la forma de garantía que §6.2 adopta —;
una compuerta epistémica de admisión de creencias en la frontera de percepción (el EVR
gate, especificado en un paper companion [Zenodo 10.5281/zenodo.19791686]); un historial
de creencias append-only que un auditor puede reproducir; credencia numérica por creencia
con calibración adaptativa (EMRE); y el encuadre Kautz Tipo-2. Su alcance es general — la
generación de metas, la selección de planes y el control de ejecución son todos
deterministas sobre creencias de estado concreto — dentro de una librería de planes
pre-verificada y una topología fija.

Lo que HADD no tiene es lo que §6.2 agrega: la procedencia como **jerarquía tipada con
semántica de admisibilidad** y no como campo de trazabilidad; la regla de que las
afirmaciones elicitadas son inadmisibles para acciones irreversibles (el dispositivo más
cercano de HADD es la confirmación humana obligatoria — un mecanismo de consentimiento, no
epistémico); la garantía **graduada por solicitud** — en HADD la garantía es uniforme, y
su único dial adaptativo es un umbral de escalación por tenant; el espacio de **patrones
acotado por nivel** — HADD acota su librería de planes globalmente; y la calibración
**medida** (EMRE aprende confianza pero nunca la mide — sin ECE, sin diagramas de
confiabilidad). La selección de paradigma, la abstención y el deferral quedan enteramente
fuera de su alcance.

**Contratos de delegación e identidad atestiguada.** El vecino más cercano del lado del
ruteo es la *paradoja de la procedencia* en ruteo multi-agente [arXiv:2603.18043], y está
lo bastante cerca como para que la superposición se diga en vez de dejársela a un revisor.
Su resultado es que rutear sobre calidad **auto-reportada** selecciona a los peores
delegados y rinde peor que al azar (0,55 contra 0,68), y su remedio es gobernanza
determinista: contratos de delegación que acotan la autoridad con objetivos, presupuestos y
políticas de falla explícitos, más un modelo de identidad **reclamada contra atestiguada**
para que el ruteo consuma métricas verificadas y no reclamos. Es empírico, con delegados
simulados y modelos reales, y el brazo atestiguado llega a ruteo casi óptimo.

De ahí salen dos cosas, y una de ellas achica lo que podemos afirmar.

*Corrobora la disciplina del sensor desde una dirección adversarial.* Nuestra razón para
rechazar la auto-evaluación del modelo como entrada admisible es epistémica — una
afirmación sobre su propia suficiencia no tiene procedencia por encima de `ELICITED`. La de
ellos es adversarial: un delegado tiene incentivo a inflar. Las dos llegan a la misma
prohibición, y `reclamada`/`atestiguada` se parece a `ELICITED`/`OBSERVED` restringido a
una sola proposición.

*Ocupa «procedencia + ruteo + contratos» como frase, así que la conjunción hay que
enunciarla por lo que excluye.* Su procedencia es una propiedad del **reclamo de calidad de
un delegado**; la nuestra es un orden sobre **tipos de evidencia**, y ese orden es lo que
una regla lee. No reportan retículo, ni piso sobre acciones irreversibles, ni curva
riesgo-cobertura — miden exactitud de ruteo. Lo que queda nuestro es la conjunción de: un
**retículo de procedencia sobre evidencia**, un **piso que gatea acciones irreversibles**
con él, la abstención tasada como **curva riesgo-cobertura medida**, y el mismo cálculo
aplicado a factibilidad, control y contenido. Cualquier término suelto de eso tiene
antecedentes.

## 2.5 Predicción selectiva y aprender a diferir

Nuestra teoría es una aplicación de un marco establecido. La regla de Chow da el rechazo
óptimo; Mozannar y Sontag dan un surrogate consistente para diferir a un experto
[PMLR v119]; Verma y Nalisnick agregan deferral one-vs-all calibrado [arXiv:2202.03673];
Mohri y colegas dan formulaciones multi-experto principiadas. Contribuimos la aplicación a
la selección de paradigmas y los corolarios específicos de §5.1, no el marco.

## 2.6 Agentes que aprenden sin actualizar pesos

Los enfoques de memoria experiencial — ExpeL, aprendizaje reflexivo experiencial, MemSkill,
R²-Mem — acumulan insights, reglas o entradas de memoria. Sleep-time compute corre inferencia
en tiempo ocioso y reporta ~1/5 de los tokens en inferencia [Letta]; SCM y trabajo afín
agregan consolidación de inspiración biológica [arXiv:2604.20943, arXiv:2605.26099]. Todos
consolidan **contenido**. §6.3 consolida la **política de control**, y la afirmación
sobrevive una búsqueda fechada (2026-08-26) sólo como conjunción, así que la enunciamos
como tal: la política se aprende de los episodios propios del agente, se consolida offline,
en un artefacto determinista versionado que se ejecuta fuera del LLM, sobre features
estructurales de la tarea. Cada conjunto tiene un vecino fuerte. Trace2Policy destila
control desde trazas de *expertos* a bases de reglas que se reinyectan *como texto de
prompt* [arXiv:2606.10457]; la compilación declarativa de políticas le da a las políticas
de orquestación exactamente la forma de artefacto que queremos — determinista, auditable,
versionada — pero *escrita por humanos*, no aprendida [arXiv:2603.27299]; el meta-ruteo
composicional aprende un ruteador interpretable offline, sobre features textuales y no
estructurales [arXiv:2608.00106]. Ninguno aprende su propia política de control hacia un
artefacto así.

## 2.7 Evaluación y jueces

Deliberadamente **no usamos juez LLM**. Un estudio a gran escala sobre 21 modelos y 541.000
juicios reporta confiabilidad sin validez, y que el acuerdo crudo sobreestima la capacidad
discriminativa [arXiv:2606.19544]. Las métricas estilo RAGAS exhiben sesgo de posición, de
verbosidad y de auto-preferencia, y la mitigación recomendada es corridas repetidas con
inspección de dispersión. Como nuestros tamaños de efecto son de un dígito de puntos
porcentuales y la varianza del juez es del mismo orden — y como el sesgo de verbosidad
favorecería sistemáticamente a los paradigmas caros cuyo valor está justamente en cuestión —
un juez introduciría **un sesgo alineado con la hipótesis**. §6.1 explica la alternativa.

Sobre atribución de fallos, MemFail aísla los fallos de sistemas de memoria en modos de
resumen, almacenamiento, recuperación y razonamiento, y puede atribuir un error a uno de
ellos sólo porque las operaciones intermedias quedan registradas [arXiv:2605.26667] —
convergente con el requisito de §8.4, aunque su atribución corre sobre un juez LLM donde la
nuestra corre sobre trazas deterministas de herramientas. Su titular es también el nuestro
en miniatura: escalar las memorias recuperadas o la fuerza del modelo rinde poco y a veces
degrada, dependiendo de la tarea.

## 2.8 Posicionamiento

| | cobertura | decisión determinista | auditable | filtro de factibilidad | abstención |
|---|---|---|---|---|---|
| AFlow / ADAS / GPTSwarm | offline, un workflow | no | no | no | n/c |
| Select-then-Solve | 1,0 | no | no | no | no |
| FlowBank | 1,0 | no | no | no | no |
| TRACE-Router | 1,0 | no | no | no | no |
| SCL | modo global | sí | sí | no | no |
| **Este trabajo** | **selectiva** | **sí** | **sí** | **sí** | **sí** |

---

# 3. Preliminares

Una **tarea** `t` aporta una pregunta, un conjunto de *unidades* (documentos), un
presupuesto declarado de tokens, y flags de irreversibilidad y escritura de estado
compartido. Un **paradigma** `p ∈ P` es una estructura de control que puede llamar
herramientas y debe emitir una respuesta. La **calidad** `q(t,p) ∈ [0,1]` es F1 de conjuntos
contra un oráculo exacto. El **costo** `c(t,p)` es el total de tokens sobre cada llamada que
el paradigma hace.

El **mejor paradigma fijo** es `p⋆ = argmax_p E_t[u(t,p)]`. El **oráculo** es
`E_t[max_p u(t,p)]`, y la **brecha del oráculo** es su diferencia. La utilidad es calidad
neta de una preferencia de costo:

```
u(t,p) = q(t,p) − λ · (c(t,p) / min_{p'} c(t,p') − 1)
```

Normalizar por el paradigma más barato en esa tarea hace a λ interpretable — la calidad que
uno está dispuesto a cambiar por un múltiplo extra del costo mínimo — y λ=0 recupera calidad
pura exactamente. **No se elige ningún λ**: la calidad y el costo crudos se guardan sin
modificar y el trade-off se aplica en tiempo de análisis, de modo que los resultados se
reportan como función de λ y no bajo un supuesto sobre λ.

Los siete paradigmas son Direct, CoT, ReAct, Map-Reduce, Plan-Execute, Reflection, y un DAG
con verificar-replanificar sobre un blackboard compartido. Cinco espejan la grilla de
Select-then-Solve para poder cotejar números contra los suyos; Map-Reduce se agrega porque
debería ganar en cardinalidad alta, y el DAG porque una comparación que omite la topología
más elaborada disponible está sesgada a favor de las simples.

---

# 4. La factibilidad es aritmética

## 4.1 El chequeo

Que `p` pueda correr `t` depende de cantidades que `t` ya declara. Con `n` unidades,
contenido `C` tokens, presupuesto `B`, y una asignación `A = 0,6·B` que deja lugar para la
conversación:

| paradigma | restricción vinculante | infactible cuando |
|---|---|---|
| Direct, CoT | un prompt con todas las unidades | `C > A` |
| Map-Reduce | una llamada por unidad, más un reduce sobre todos los parciales | `n > 80` o `n·f > A` |
| DAG | sub-preguntas × iteraciones × replanificaciones | llamadas proyectadas > 200 |
| ReAct, Reflection | tope propio de iteraciones; lee selectivamente | nunca |

donde `f` es el tamaño proyectado de un hallazgo. Sin llamada al modelo, sin estadística,
sin aprendizaje.

## 4.2 Separa dos modos de falla que se confunden de rutina

Aplicado a **168 tareas sobre cinco corpus** del mismo generador, cada tarea con su propio
presupuesto declarado:

| corpus | tokens/unidad | unidades/tarea | contenido máx | Direct, CoT | Map-Reduce |
|---|---|---|---|---|---|
| gold_v2 | 232 | 60 | 16k | 39/39 | 39/39 |
| gold_v3 | 2.147 | 60 | 152k | 12/39 | 39/39 |
| gold_wide | 264 | 500 | 135k | 20/32 | **18/32** |
| gold_deep | 7.161 | 60 | **483k** | 2/26 | **26/26** |
| gold_xl | 2.499 | 500 | 1.272k | 8/32 | 18/32 |

Tareas factibles sobre el total. Los otros cuatro paradigmas son factibles en **168/168**.

Agregado sobre paradigmas, el espacio de planes admisibles se contrae monótonamente con la
escala — **273/273 celdas en gold_v2, 186/224 en gold_wide, 134/182 en gold_deep, 162/224 en
gold_xl**: de 100% admisible a 72%, íntegramente por aritmética y antes de gastar un token.
Un selector que opere sin esta capa tendría que aprender que ese cuarto del espacio es
inalcanzable, un episodio fallado a la vez.

**El par decisivo es gold_wide contra gold_deep.** gold_deep lleva 3,6× más contenido, y
Map-Reduce pasa de 18/32 factibles a **26/26** mientras Direct y CoT se derrumban a 2/26. El
tamaño total no predice la factibilidad de Map-Reduce; **la cardinalidad sí**. Con 483k
tokens en 60 unidades corre, porque nunca las tiene juntas. Con 135k en 500 unidades no: 501
llamadas, y un reduce que concatena 500 hallazgos. Tratar su límite como un límite de
contexto lleva a descartarlo exactamente donde funciona.

El mismo tope de acumulación aplica al blackboard del DAG, que renderiza cada hallazgo
dentro de cada prompt de sub-agente.

**Cuán fuerte muerde la restricción de leer-todo es fácil de subestimar.** En gold_deep una
tarea de **una sola unidad** es infactible para Direct, porque un documento son 8.075 tokens
contra una asignación de 4.800. La restricción no es "el corpus es grande" sino "la pieza
más chica que se puede direccionar ya no entra", y ninguna cantidad de lectura selectiva
cambia eso para un paradigma cuyo único movimiento es leer.

**Una segunda lectura que conviene decir en voz alta.** Los cuatro paradigmas selectivos son
factibles en las 168 tareas. Es una propiedad real — acotan sus propias iteraciones y leen a
demanda — pero también acota lo que esta capa puede hacer. La factibilidad restringe sólo a
los paradigmas que retienen material en contexto o se abren por unidad; **no ofrece ninguna
protección contra un paradigma selectivo gastando a través de un corpus de 1,27M tokens**.
Esa protección tiene que venir de un presupuesto, no de aritmética sobre el corpus, y §7.2
muestra por qué hace falta: los selectivos son justamente los que varían cincuenta veces en
costo.

## 4.3 Por qué esto va delante del problema de aprendizaje

La factibilidad es determinista, gratis, y aguas arriba de todo lo demás. Poda el espacio de
planes antes de cualquier selección, aprendida o no. **El corolario para producción es que
saber el largo y declinar no es una degradación** — es la diferencia entre un sistema acotado
y uno desbocado.

\1

**Medido, y la distinción no es académica.** Sobre cuatro celdas de gold_deep, Direct quedó
podado en tres y corrió en una, donde sacó 1,000. Registradas como respuestas equivocadas,
esas tres dejarían la media de Direct en 0,250 — el peor paradigma de la tabla. Registradas
como infactibles, el enunciado es el correcto: *el mejor donde puede correr, no disponible
donde no.* La misma capa que protege al estudio de una conclusión falsa es la que un sistema
en producción necesita para declinar en lugar de fallar.

---

# 5. Teoría

## 5.1 El Teorema del Valor de Selección

Sea `p⋆` el fallback y `p_s` un especialista. Sea `S = {t : u(t,p_s) > u(t,p⋆)}` con
`π = Pr[t ∈ S]`. Sea `α = Pr[rutear a p_s | t ∈ S]` y `β = Pr[rutear a p_s | t ∉ S]`, y sean
`G_α`, `L_β` la ganancia y la pérdida medias **condicionadas a los subconjuntos ruteados**.

**Teorema 1.** `V(r) − V(p⋆) = π·α·G_α − (1−π)·β·L_β`, exactamente. Por lo tanto la selección
le gana al mejor paradigma fijo si y sólo si

```
π · α · G_α  >  (1 − π) · β · L_β
```

Condicionar la ganancia y la pérdida a los subconjuntos *ruteados* y no a `S` hace la
identidad exacta sin ningún supuesto de independencia, y separa la calidad de cobertura
(`α`, `β`) de la calidad de selección dentro de la cobertura (`G_α` frente al `G`
incondicional).

**Corolario 1 (precisión sobre cobertura).** Cuando `p⋆` es casi óptimo en regiones amplias,
`G` es chico y `L` grande, así que la condición exige `β → 0` incluso a costa de `α`. El
recall no es el objetivo.

**Corolario 2 (umbral de imposibilidad).** `β_max = π·α·G_α / ((1−π)·L)`. Cualquier ruteador
por encima le pierde a siempre-fallback por buenos que sean sus especialistas. Acá `L` debe
ser la pérdida **distribucional**, no la realizada: computado desde la pérdida realizada el
umbral es circular, y un ruteador perfecto — que no realiza pérdida — reportaría un límite
infinito y parecería no tener restricción.

**Corolario 3 (cobertura óptima).** Con una confianza calibrada y un umbral variable, el valor
capturado es unimodal en la cobertura y el óptimo generalmente tiene cobertura ≪ 1. Un
ruteador obligado a elegir no tiene control alguno sobre `β`.

**Identidad.** La brecha del oráculo iguala `π·G`. Los 17,1pp reportados para una suite
publicada *son* `π·G` para esa suite, lo que permite recuperar el `β` implícito de un ruteador
a partir de sus números de portada.

Todo lo anterior está verificado en `tests/test_science.py` contra distribuciones cuyos
términos se conocen por construcción, incluido el caso negativo en el que se confirma que un
ruteador por encima de `β_max` captura valor negativo.

## 5.2 Dominancia de la cascada, y su corrección medida

Un **ruteador** que se equivoca paga `L`, una pérdida de calidad: se entrega una respuesta peor
y nada la recupera. Una **cascada** que se equivoca paga `cost(p_1)`, una pérdida de costo: el
intento barato se desperdicia y la buena respuesta llega de todas formas tras escalar.

Con sensibilidad de detector `s`:

```
regret(ruteador) = (1−π)·β·L
regret(cascada)  = E[costo de la escalera] + (1−s)·L
```

**Una corrección que le debemos a la medición.** Un enunciado anterior de este resultado daba
el término de costo como `cost(p_1)`. Es falso. Cuando ningún escalón satisface al detector, la
cascada corre la escalera *completa*: en nuestro estudio sintético capturó el 100% de la brecha
a **4,4×** el costo del mejor paradigma fijo. El límite es el costo esperado de la escalera, y
el patrón requiere un tope de presupuesto.

**La sensibilidad del detector es la variable crítica, y un detector débil es catastrófico y no
simplemente subóptimo.** Con `s = 0,6` la fracción capturada midió **−5,98**: una falla no
detectada deja a la cascada detenida en un escalón barato con una respuesta mala. Es el análogo
estructural del Corolario 2 — como un ruteador con `β` alto pierde, una cascada con `s` bajo
pierde, y pierde más fuerte.

**Corolario (la partición por verificabilidad).**

```
v = 1  (existe un oráculo barato)  ->  cascada; no hace falta ruteador
v = 0  (no hay oráculo)            ->  rutear, bajo la disciplina del Teorema 1
```

Predecir sólo es necesario donde verificar es imposible. Si esto se sostiene, buena parte de la
literatura de ruteo está resolviendo el problema equivocado en el régimen verificable.

**Y la partición tiene una consecuencia metodológica filosa que pagamos por aprender.** La
rama `v = 0` es la que necesita un ruteador, y es precisamente la rama que un benchmark de
coincidencia exacta no puede contener: el gold es lo que hace que corregir no necesite juez,
y el gold es un detector. En este registro la conflación fue literal —un mismo campo servía
para las dos cosas— y el resultado es que dos predicciones de ruteo preregistradas, sobre
dos corpus held-out independientes, las contestó la regla de cascada mientras la de
selección no se evaluó nunca. Los números son reales; lo que miden es la rama `v = 1`.

Separar las dos no es un cambio de calibración. Requiere un corpus que **declare la
disponibilidad de detector por tarea** sobre bases independientes de la clave de respuestas
—para nosotros, si verificar es más barato que resolver— y mueve la cascada de disparar en
22 de 26 tareas a disparar en 2.

---

# 6. Diseño

## 6.1 Medir sin juez

Cada tarea trae un oráculo de conjunto, así que la calidad es F1 de conjuntos tras
normalización. §2.7 da la razón: el efecto es de un dígito de puntos porcentuales y la varianza
del juez es del mismo orden, así que un juez no agregaría solamente ruido sino un **sesgo** —
el sesgo de verbosidad favorece las respuestas largas que producen los paradigmas caros, que es
precisamente la comparación bajo prueba.

Un oráculo vacío es una pregunta legítima e importante — *listá todos los X* donde no hay
ningún X — y testea si un paradigma inventa items. Se califica exigiendo un enunciado explícito
de vacuidad; el silencio saca cero, porque un paradigma que no devolvió nada porque se cayó no
debe puntuar igual que uno que buscó y reportó no haber encontrado nada.

## 6.2 Creencias, procedencia y garantía por solicitud

El determinismo pleno no está disponible con un LLM, y perseguirlo excluyendo al modelo de la
decisión descarta información que el modelo tiene. La inversión es de HADD (§2.4): el modelo es
un **sensor** que emite proposiciones tipadas, una capa simbólica determinista decide sobre la
base de creencias, y la garantía toma la única forma que puede tener:

> no *"el mismo prompt da la misma respuesta"* — falso, siempre
> sino *"la misma base de creencias da la misma decisión"* — la estabilidad de decisión de HADD,
> con la base registrada

Lo que esta sección agrega es la **epistemología de la creencia misma**. En HADD la procedencia
es un campo de trazabilidad; acá carga el peso de la decisión como jerarquía tipada: `COMPUTED`
(una función pura, credencia 1,0) > `OBSERVED` (medido
ejecutando una sonda) > `ELICITED` (el modelo lo afirmó, sujeto a calibración) > `ASSUMED`. Una
regla puede exigir una procedencia mínima, así que una acción irreversible puede restringirse a
evidencia computada y observada: *la opinión de un modelo de que una acción es segura no es
evidencia admisible para tomarla.*

La garantía es entonces una propiedad **de la solicitud**, no del sistema. Un modo global hace
que todo el tráfico pague por la solicitud más estricta. Cuatro niveles graduán el piso de
procedencia, si θ puede aprender online, si la corrida es reproducible desde caché, y **qué
patrones son admisibles** — el nivel certificado excluye topologías cuyo flujo de control es no
acotado, no porque sean peores (a menudo son mejores) sino porque sus modos de falla no son
enumerables. El piso se deriva de creencias sobre la solicitud: quien llama puede pedir más y
nunca menos. La derivación misma aprende, offline: una categoría de solicitudes cuyas
afirmaciones elicitadas son rechazadas repetidamente por la compuerta es una categoría
cuyo piso sube — las estadísticas de rechazo son evidencia sobre la clase de solicitud, y
consumirlas cierra el bucle sin ajustar jamás nada adentro de una solicitud.

Tres propiedades lo vuelven seguro de correr, y cada una está impuesta, no pretendida.

**El evento es tipado, no parseado.** Un rechazo lleva su motivo como valor — la
procedencia que se tenía contra la que la regla exigía — de modo que la estadística cuenta
el evento. Contarlo emparejando subcadenas de la explicación mediría el fraseo, y el
fraseo es prosa que se reescribe. Sólo cuentan los rechazos por PROCEDENCIA insuficiente:
una creencia rechazada por credencia baja, o por tener el valor equivocado, es el sistema
funcionando, y no dice nada sobre el régimen de evidencia de la clase.

**La guarda es replicación, no utilidad.** El registro se parte por tarea; una mitad
propone las regiones cuyo piso debería subir, y el piso se instala sólo si la otra mitad
—solicitudes que la propuesta nunca vio— dice lo mismo de manera independiente. La
utilidad sería el criterio equivocado acá, y descartarla no es una concesión: subir un
piso hace que el sistema exija evidencia medida donde habría actuado sobre una
afirmación, lo que cuesta tokens y sólo puede bajar la utilidad medida en el corto plazo. Un piso de gobierno puntuado por la utilidad que
produce es un piso que nunca sube.

**El aumento es acotado y monótono.** Se detiene en accountable y nunca llega a
certified, porque certified además restringe qué patrones pueden correr y una estadística
sobre calidad de evidencia no es evidencia sobre certificabilidad — un piso que aprende no
puede quedar habilitado a descalificar una topología. Y nunca baja solo: la ausencia de
rechazos después de que un piso sube es justamente lo que ese piso se instaló para
producir, así que leer esa ausencia como motivo para bajarlo sería una oscilación puesta
en el diseño.

Los pisos aprendidos viajan en el bundle de política firmado, así que nada puede elevar el
nivel de una solicitud salvo por el mismo camino de promoción que recorre θ. Verificado:
una región cuyos rechazos replican a través de la partición recibe su piso; una región que
califica sólo en la mitad que la propuso, no.

Credencia y tamaño de efecto no deben confundirse. Un margen aprendido es una creencia *certera*
sobre un efecto *grande* — credencia 1,0, valor 0,9 — y codificar la magnitud como credencia
reporta un hecho computado como incierto, destruyendo la distinción para la cual existe la capa.

## 6.3 Consolidación de la política de control

El aprendizaje es offline y copy-on-write. Los episodios se reproducen en orden de **sorpresa** y
no cronológico, lo que elimina el sesgo de recencia que la actualización online tiene por
construcción; las estadísticas se reducen en escala y las entradas sin uso se podan; y una etapa
de abstracción busca particiones de features que separen paradigmas mejor que el binning actual.

Dos disciplinas hacen esto seguro. Una política candidata se instala sólo si no regresa sobre
episodios retenidos. Y el registro se parte en tres **por tarea** — una parte propone
particiones, una las puntúa, una la toca sólo el guardia de promoción — porque buscar muchas
particiones contra un solo holdout es la forma en que detectar una verdad se vuelve confabularla.
Una partición descubierta entra con cero episodios, por debajo del piso de confianza, y no puede
gobernar una decisión hasta haber ganado evidencia: **un sueño es una hipótesis, no un hecho.**

Verificado: dado un registro donde la utilidad es independiente de todo atributo, ninguna
partición sobrevive la validación.

## 6.4 La superficie de herramientas es parte de la topología

Elegir *cuál* modalidad de recuperación, a *qué* granularidad, en *qué* secuencia, con cuánto
*batching* es asunto propio del agente — **es** la topología. Un harness que ofrece una búsqueda
tosca y un read ya decidió las cuatro cosas y después mide lo que queda.

Cuatro herramientas en tres granularidades, con lo léxico y lo denso expuestos por separado junto
al punto de entrada fusionado:

| herramienta | devuelve | tamaño medido, 3 unidades |
|---|---|---|
| `search` | resúmenes | 312 chars |
| `keyword_search` | highlights `<< >>` | 937 |
| `semantic_search` | texto completo | 3.502 |
| `read` | texto completo, en batch | 3.501 |

**11× entre resumir y leer**, y esa diferencia es invisible cuando toda búsqueda devuelve un
extracto de tamaño fijo. Fusionar léxico y denso en una sola herramienta híbrida fue un error
concreto: híbrido es el default correcto, pero exponer sólo la vista fusionada significa que el
agente nunca puede pedir coincidencia exacta para un identificador — y las respuestas de dos de
nuestras celdas *son* identificadores.

La calidad de recuperación es una variable registrada con cinco brazos: híbrido (BM25 + denso,
fusión RRF), léxico, semántico, dos simulaciones degradadas a recall y precisión declarados, y un
oráculo. Las simulaciones son funciones deterministas de `(tarea, consulta, unidad)`, así que la
calidad de recuperación es un dial controlado y no otra fuente de ruido. Los vectores se cachean
por hash de contenido, así que después de una primera pasada la fusión es aritmética local.

**Un hallazgo contra la visión recibida**: en la celda acoplada, denso solo midió recall 0,75,
híbrido 0,50, léxico 0,25. RRF promedia rangos, así que un componente que anda mal arrastra a uno
que anda bien. "Híbrido siempre es mejor" no se sostiene cuando un componente está muy por debajo
del otro.

---

# 7. Mediciones preliminares

> **Todos los números de §7 y §8 son n=1 por celda**, sobre un corpus sintético, con un modelo
> (`gpt-5-chat`), bajo recuperación híbrida. La varianza entre réplicas sobre la topología DAG se
> midió en hasta 3,93× en costo. Las magnitudes son indicativas; los mecanismos descansan en
> trazas de uso de herramientas y son más robustos.

## 7.1 El agregado sobre cuatro celdas de features

| paradigma | calidad media | tokens totales | rango de costo | unidades alucinadas |
|---|---|---|---|---|
| **Direct** | **0,938** | **46.101** | 1,2× | 0 |
| CoT | 0,938 | 46.272 | 1,2× | 0 |
| ReAct | 0,688 | 116.524 | **27,6×** | 0 |
| Reflection | 0,688 | 126.254 | 6,9× | 0 |
| Map-Reduce | 0,438 | 62.321 | 1,2× | 0 |
| DAG | 0,438 | **439.319** | 24,5× | 0 |
| Plan-Execute | 0,250 | 123.175 | 2,0× | **78** |

El paradigma más simple gana en calidad y es simultáneamente el más barato; el más elaborado
devuelve menos de la mitad de la calidad por 9,5× el costo.

**Esto está gobernado por una amenaza de validez que enunciamos en lugar de enterrar**: en este
corpus toda tarea entra en un prompt, y en ese régimen leer todo es óptimo y el orden es casi
tautológico. §4 existe para escapar de eso, y §9 registra que la escapatoria está construida pero
no medida.

## 7.2 La calidad de las herramientas gobierna la varianza que se le atribuye a la topología

| grupo | rango de costo |
|---|---|
| no usan herramientas (Direct, CoT, Map-Reduce) | **1,2×** |
| usan herramientas (ReAct, Reflection, Plan-Execute, DAG) | **50×** |

La calidad de las herramientas no mueve la media; gobierna la varianza — y de forma asimétrica.
Los lectores son caros y estables; los buscadores son baratos-o-ruinosos, y qué cara sale de la
moneda lo decide la recuperación. Un paradigma que cuesta entre 2.877 y 251.374 tokens según si la
búsqueda funcionó no es algo para lo que se pueda presupuestar.

**Implicancia**: un benchmark que no reporta la calidad de su superficie de herramientas no está
midiendo topologías. Está midiendo su retriever envuelto de siete maneras.

## 7.3 Un A/B sobre tres señales de contabilidad, y lo que una réplica le hizo

Mismo corpus, mismo retriever, mismas cuatro celdas; lo único distinto es la superficie de
herramientas, registrada como variable por fila.

Los tres paradigmas que no usan herramientas fueron **idénticos al token** entre brazos. Ese
control es lo que hace atribuible el resto; sin él cualquier diferencia podría ser ruido de
corrida.

Un tercer brazo agregó cuatro herramientas de memoria de trabajo (`note`, `notes`, `plan`,
`advance`) y produjo un resultado que no habíamos planeado. **El modelo no las llamó nunca**:
sobre 28 filas, un note, una compactación y cero planes. En un corpus donde todo entra en un
prompt no hay presión de contexto, así que una herramienta de memoria de trabajo no tiene
trabajo — **exponer una capacidad no es lo mismo que proveerla**. Ese brazo es entonces un
resultado nulo sobre las herramientas, y algo más útil: una **réplica** accidental de la
superficie de contabilidad.

Como réplica dice lo que el agregado esconde. **La reproducibilidad es por tarea, no
global.** En tres de las cuatro celdas, 10 de 10 valores de calidad son idénticos entre el
par. En la cuarta — la cadena de tres saltos — 2 de 4 se dieron vuelta, y ambas por la unidad
completa. La inestabilidad no está repartida finamente sobre el estudio; está concentrada en
la tarea más difícil, donde el resultado es bimodal. El costo no fue reproducible en ninguna
parte: dispersión media 2,05×, máxima 5,43× a calidad *idéntica*.

Eso convierte al A/B de una lista de efectos en una lista de efectos **con un test de
atribución**. Un efecto que mueve sólo la celda que sale cara o cruz no es atribuible; uno
que mueve una celda reproducible, sí.

| paradigma | Δ reportado | celdas que movió | atribuible | veredicto |
|---|---|---|---|---|
| DAG | +0,500 | c3 (inestable), c5 (estable) | **+0,250** | sobrevive la mitad |
| Reflection | +0,250 | sólo c3 (inestable) | **0,000** | **retirado** |
| ReAct | +0,000 | ninguna | 0,000 | nulo, confirmado |
| Plan-Execute | −0,139 | c2, c5 (ambas estables) | **−0,139** | sobrevive |

**Retiramos el resultado de Reflection.** Salió íntegro de la celda que se da vuelta sola, y
con n=1 no se distingue del ruido.

**El resultado de costo del DAG sobrevive, y es lo más fuerte que hay acá.** El costo total
cayó **3,05×** contra una dispersión de réplica de 1,62× sobre la misma medida, y cayó
exactamente donde el mecanismo lo predice: las dos celdas desbocadas, 251k → 51k y
143k → 10k, ambas con avisos de estancamiento. Las otras dos celdas no cayeron nada. Así que
decirle a un bucle iterativo que su retriever dejó de producir vale una reducción de costo de
3×, con el mecanismo visible en la traza — mientras la ganancia de calidad que lo acompañaba
es la mitad de lo que reportamos primero.

**La degradación de Plan-Execute sobrevive, y sobre celdas reproducibles**: +0,444 en una y
−1,000 completo en otra. Nuestro propio análisis había llamado a la contabilidad de cobertura
"la adición de mayor apalancamiento" para este paradigma. La empeoró. Saber que la respuesta
está incompleta es inútil cuando la arquitectura no puede completarla: los sub-agentes ya
terminaron cuando la síntesis se entera de que faltan unidades. **Un diagnóstico sin capacidad
de actuar es peor que ninguno** — y es el único efecto del A/B que movió celdas estables *y*
contradijo nuestra predicción.

**Un efecto de segundo orden que no previmos.** `read_all` redujo el costo de una lectura
completa 7,6× y **subió** el costo neto de ReAct un 27%: abarató el *acto*, y por lo tanto la
*decisión*, de leer todo.

**Una celda no corrió.** Dos filas registraron cero tokens y respuesta vacía — no una
respuesta equivocada sino una ausente. Están excluidas de toda cifra de arriba en lugar de
puntuadas como cero, porque un paradigma que nunca ejecutó no debe mezclarse con uno que
respondió mal.

## 7.4 El estudio de dos regímenes, con réplicas

> Segundo estudio, corrido el 2026-08-26 con las predicciones P1–P5 registradas antes
> (README del harness). Sets de tareas emparejados sobre `gold_v2` (en ventana, ~18k
> tokens) y `gold_deep` (fuera de ventana, ~483k), `repeat = 3`, estabilidad por celda.
> 126 + 158 filas válidas. Dos celdas pesadas fuera de ventana (`react`/`reflection`/
> `dag` en c2-w48 y c5-w48) perdieron réplicas y se están re-corriendo; sus medias se
> apoyan en menos trials que el resto y van marcadas †.

Primero el barrido de factibilidad, porque no cuesta nada: a 135k tokens la aritmética
poda leer-todo en 12 de 32 tareas; a 483k en **24 de 26**; a 1,27M en 24 de 32 — y a esa
escala la poda alcanza a `map_reduce` en 18–20 tareas, cuyo gasto proyectado excede el
presupuesto declarado (P1, confirmada). En ventana no se poda nada. El claim de régimen
es aritmética, no medición.

**En ventana (utilidad media / tokens medios por celda; flips = celdas cuya utilidad
cambió entre réplicas):**

| paradigma | C2 | C3 | C4 | C5 | flips | costo mediana (rango) |
|---|---|---|---|---|---|---|
| `direct` | 0,75 / 13k | **1,00** / 11k | 1,00 / 13k | **1,00** / 11k | **0/6** | **10,5k (1×)** |
| `react` | 0,75 / 25k | 0,67 / 63k | 1,00 / **3k** | 1,00 / 61k | 3/6 | 23,8k (**70×**) |
| `map_reduce` | 0,75 / 16k | **0,00** / 14k | 1,00 / 16k | **0,00** / 16k | 0/6 | 15,1k (1×) |
| `plan_execute` | **0,00** / 27k | **0,00** / 11k | **0,00** / 32k | 0,33 / 29k | 1/6 | 19,0k (12×) |
| `reflection` | 0,83 / 31k | 0,44 / 40k | 1,00 / 8k | 0,67 / 113k | 3/6 | 21,2k (27×) |
| `dag_strategy` | 0,75 / 27k | 0,33 / 77k | 1,00 / 6k | 0,67 / 66k | 3/6 | 33,1k (**82×**) |

**Fuera de ventana (misma convención; `direct` infactible salvo en las tareas chicas):**

| paradigma | C2 | C3 | C4 | C5 | flips | costo mediana (rango) |
|---|---|---|---|---|---|---|
| `direct` | INFACTIBLE | INFACTIBLE | INFACTIBLE | 1,00 / 23k* | 0/8 | 22,9k (1×) |
| `react` | 0,97† / 61k | **1,00** / 14k | 1,00 / 18k | 1,00† / 40k | **0/7** | **14,6k** (40×) |
| `map_reduce` | 0,95 / 107k | **0,00** / 276k | 1,00 / 29k | **0,00** / 23k | 1/8 | 28,7k (15×) |
| `plan_execute` | 0,62 / 88k | 0,33 / 18k | 0,33 / 80k | 0,33 / 94k | **4/8** | 34,4k (52×) |
| `reflection` | 1,00† / 106k | 1,00 / 50k | 1,00 / 17k | 1,00† / 89k | 0/7 | 30,0k (47×) |
| `dag_strategy` | 1,00† / 50k | **0,67** / 86k | 1,00 / 14k | 1,00† / 26k | 1/7 | 21,0k (59×) |

\* sólo en tareas cuya propia evidencia entra: la poda es por tarea, no por corpus.

Tres hallazgos que el primer estudio no podía ver:

**El ranking se invierte con el régimen, según la predicción y más allá de ella.** En
ventana, los lectores dominan en calidad, costo y estabilidad a la vez. Fuera de ventana
no existen, y los paradigmas que el primer estudio rankeó últimos — `react`,
`reflection`, `dag` — ocupan la cima de la tabla. `plan_execute` es la excepción en ambos
regímenes: sin región ganadora, y fuera de ventana es lo menos estable que se midió
(4 de 8 celdas dadas vuelta).

**El cero de `map_reduce` en las acopladas es estructural, y ahora está medido a dos
escalas** (P3, confirmada): 0,00 en ventana y 0,00 fuera, deterministamente — sus fallos
ni siquiera se dan vuelta. §8.3 carga la mitad de costo de esto.

**La estabilidad vive donde el retrieval no decide.** En ventana, los paradigmas con
herramientas dieron vuelta 3 de 6 celdas cada uno mientras los lectores ninguna. Fuera de
ventana, `react` no dio vuelta ninguna de 7 — sin el competidor leer-todo, su búsqueda
tiene un trabajo que sí puede terminar — y la inestabilidad migró a `plan_execute`. La
varianza no es propiedad de un paradigma; es propiedad de *a quién se le pide decidir
cuándo parar*.

## 7.5 La topología elaborada contra el fallback general

La pregunta que este estudio existe para responder en lugar del reporte de campo
retirado: ¿la topología más elaborada le gana al fallback general? La respuesta medida es
que la pregunta tiene forma de régimen — y que donde más importa, el diferenciador no es
la topología.

En ventana, `dag_strategy` es la peor compra medida: el rango de costo más ancho (82×, de
3,1k a 251k sobre sets idénticos), un 0,33 en las acopladas que `direct` resuelve por
11k, y 3 de 6 celdas dándose vuelta entre réplicas. Fuera de ventana se transforma:
utilidad perfecta en C2, C4 y C5 a costos que rivalizan o superan los de `react`†.

Excepto en la cadena acoplada profunda, donde produjo la peor fila individual del
estudio: **395.960 tokens en 35 iteraciones para un cero**, en una tarea que `react`
resuelve por 10–14k con utilidad 1,0 en las tres réplicas. Esta corrida usó la superficie
**basic** — sin señales contables — y la traza muestra el mecanismo de §8.2 a escala: el
verificador sigue encontrando la respuesta incompleta, el replan sigue ensanchándose, y
nada en el entorno dice *basta*. §7.3 midió que las señales cortan exactamente ese bucle
3,05×. Juntos, los dos resultados dicen algo más filoso que "el DAG pierde": **la
topología elaborada es viable fuera de ventana sólo bajo contabilidad impuesta desde
afuera — lo que faltaba no era inteligencia del bucle.**

## 7.6 Dos paradigmas entran por predicción registrada — uno sobrevive

Contra las dos raíces de falla de §8 que ningún paradigma existente ataca barato,
agregamos dos paradigmas con predicciones registradas antes de correr (P6–P7, README del
harness) y los tamizamos sobre las tareas discriminantes fuera de ventana.

**`rewoo`** — todas las tool calls planificadas en una pasada con placeholders de
dataflow explícito, ejecutadas sin el modelo en el loop, una llamada de resolución; dos
llamadas LLM en total, sin reenvío de historial [ReWOO, arXiv:2305.18323]. Las dos
predicciones registradas se cumplieron, la primera más allá de su cota declarada: calidad
idéntica a `react` en cobertura independiente (0,88 en C2, 1,00 en C4) al **3–8% del
costo de react** en las mismas celdas (la predicción decía ≤50%), y utilidad 0,00 en las
celdas acopladas y de horizonte desconocido — un plan que no puede observar no puede
descubrir el hop que depende de un resultado previo. Sus utilidades fueron idénticas
entre réplicas en las cuatro tareas. Un especialista de manual del Teorema 1: G grande
dentro de una región de borde nítido, fallo total afuera.

**`gist_reader`** — una tabla determinística de gists por unidad en un prompt, después
lecturas completas dirigidas y batcheadas. **Su predicción principal fue falsificada**:
se predijo u ≥ 0,75 en tres celdas y se alcanzó en una (C5: 1,00 a 8k donde `react` paga
20–103k); en cobertura masiva y agregación exacta los gists de 312 caracteres no cargan
el dato (0,29 en C2, 0,00 en C4) — precisamente el mecanismo de summary-failure que la
predicción secundaria nombraba. Su cota de cardinalidad también se comportó según lo
registrado: la tabla de gists queda infactible por aritmética en tareas de 400 unidades,
registrado gratis. El paradigma queda medido y no promovido. Lo reportamos con el mismo
largo que el éxito a propósito: la disciplina de predicciones registradas sólo vale la
pena si una falsificación cuesta un párrafo y no una retractación.

---

# 8. Mecanismos de falla

Éstos descansan en trazas y no en magnitudes, y son lo que defenderíamos.

## 8.1 La descomposición destruye la dependencia secuencial

Ambas topologías que descomponen fallan ambas celdas acopladas, y ambas **con la evidencia
leída**. El DAG gastó 251.374 tokens en la cadena de tres saltos, leyó 4 de 4 unidades de la
cadena, y sacó cero. Una cadena es secuencial por definición — el salto 2 no se puede formular
antes de responder el salto 1 — así que partirla en sub-preguntas paralelas deja el blackboard con
las unidades correctas y sin la estructura que las ordena. Es una propiedad de descomponer, no una
coincidencia de dos implementaciones.

## 8.2 Los bucles iterativos amplifican la falla de recuperación en lugar de absorberla

En la celda de dos saltos el DAG emitió 31 búsquedas por palabra clave, leyó **cero** unidades
relevantes, y gastó 142.694 tokens. Después de la tercera búsqueda el retriever ya había
demostrado que no iba a encontrar el objetivo; el bucle de verificar-replanificar lo leyó como
*buscar otra vez*.

Esto invierte una intuición de diseño. Los bucles de verificación se agregan **para** robustez;
acá el bucle **es** el mecanismo de amplificación. Sin él la falla habría costado 10k tokens en
lugar de 143k.

## 8.3 Una falla que ninguna herramienta arregla

Map-Reduce falla ambas celdas acopladas y lee cero unidades relevantes en las cuatro, porque por
construcción ve cada unidad aislada. Una cadena y una comparación entre unidades son irresolubles
así por muchas veces que se las examine.

El arreglo no es una herramienta mejor sino una negativa: el acoplamiento es una
propiedad declarada de la tarea, así que la capa de factibilidad puede excluir al
paradigma antes de gastar un token — lo que es más barato que cualquier cantidad de
aprendizaje de que pierde.

**Y el precio de esa falla escala con el corpus, la falla no.** El mismo paradigma, sobre la
misma celda, a dos tamaños de unidad:

| corpus | unidades | llamadas | unid. relevantes leídas | costo | calidad |
|---|---|---|---|---|---|
| gold_v2 | 48 | 49 | **0** | 13.931 | 0,000 |
| gold_deep | 48 | 49 | **0** | **276.355** | 0,000 |

Cardinalidad idéntica, mismas llamadas, mismo cero — y **19,8× el costo**. Treinta veces más
texto por unidad compró exactamente treinta veces más de nada, porque el obstáculo nunca fue
la cantidad de evidencia. Es el argumento más filoso que tenemos para decidir **antes** de
correr y no después: un paradigma cuya limitación es estructural no falla más fuerte a
escala, sólo más caro, y un enfoque que aprende de resultados paga esa cuenta en cada
episodio hasta aprender lo que la aritmética le podía decir gratis.

## 8.4 La atribución exige la traza

La traza de uso de herramientas separa *nunca vio la evidencia* de *la vio y razonó mal*. Sin
ella un cero es un misterio; con ella, es un diagnóstico. "La topología que busca perdió" es
ininterpretable cuando el buscador nunca llegó a una unidad relevante — eso es una afirmación
sobre la superficie de herramientas, y sólo una falla **con la evidencia en la mano** es evidencia
sobre la estructura de control.

---

# 9. Limitaciones y amenazas a la validez

**El régimen en-ventana es casi tautológico, y §7.4 es la escapatoria — parcialmente
recorrida.** El corpus detrás de §7.1–7.3 tiene 16k tokens en su punto más ancho, así que
leer-todo es correcto y lo más barato ahí. El régimen fuera-de-ventana ya está medido a
483k con `repeat = 3` (§7.4–7.5), y el claim de régimen a través de 135k/483k/1,27M
descansa en el barrido de factibilidad a costo cero. Sigue abierto: no hay corrida
completa a 1,27M (sólo su aritmética de factibilidad), dos celdas pesadas fuera de
ventana re-corriéndose tras exclusiones por rate limit (marcadas † en §7.4), y un mundo
held-out con seed nueva, generado y verificado independientemente, cuyo test de
transferencia está registrado como P8 y no corrió todavía — **hasta que corra, los
veredictos por celda son afirmaciones sobre mundos seed-7.**

**Ya existen réplicas, y el ruido es por celda.** La réplica accidental del primer
estudio (§7.3) y el `repeat = 3` del segundo coinciden: la reproducibilidad es por tarea
— los lectores no dan vuelta nada, los que usan herramientas dan vuelta las celdas donde
decide el retrieval, y el costo no fue reproducible en ninguna parte (dispersión media
2,05×, máxima 5,43× a calidad idéntica en el primer estudio; el mismo patrón de
concentración en el segundo). Por eso todo delta de calidad se reporta con su conteo de
flips por celda, nunca como media pelada. El piso de ruido formal por celda y la brecha
de oráculo neta (`Study.noise_floor`, decisiones contra la brecha neta) se computan en el
análisis final sobre la grilla completa — pendiente de las celdas en re-corrida.

**Un modelo, y no se lo puede fijar.** `gpt-5-chat` rechaza una temperatura explícita, así que el
sampleo queda en el default del modelo. Hay un deployment de razonamiento que acepta temperatura 0
como escape, pero cambia qué se está midiendo.

**Corpus sintético.** El ground truth es exacto y se re-deriva de forma independiente, y los
parámetros estructurales son diales y no esperanzas — pero la distribución de tareas reales sobre
esos diales es desconocida. Hacen falta benchmarks públicos para validez externa y no se usan
todavía.

**La latencia no es comparable.** El DAG acá corre secuencial donde correría en oleadas
concurrentes; y una vez que los workers compiten, el wall-clock por fila deja de medir latencia.
La calidad y los conteos de tokens siguen siendo exactos.

**Las afirmaciones de novedad están verificadas como conjunciones, no como partes.** Los dos
trabajos ancla se leyeron completos el 2026-08-26: todos los números citados de Select-then-Solve
verifican contra su cuerpo, y la cesión a SCL se sostiene. Las afirmaciones restantes — la
consolidación de la política de control (§6.3), el descubrimiento de proposiciones con compuerta
de procedencia, la abstención en el ruteo de paradigmas — sobreviven búsquedas fechadas sólo como
conjunciones cuyos conjuntos individuales tienen cada uno un vecino publicado (§2.2, §2.4, §2.6).
Un campo que se mueve así de rápido puede cerrar cualquiera de ellas en meses; las búsquedas
están fechadas para que un lector pueda re-correrlas.

**Advertencia de reproducibilidad.** Una semilla sola no fija un corpus. Cuando el algoritmo de
generación cambió, la misma semilla produjo un mundo distinto; los manifiestos ahora estampan
versión de generador y los resultados entre versiones no deben mezclarse.

---

# 10. Conclusión

El premio en la selección de paradigmas es real y está medido, y la literatura lo persigue con
selectores que deben elegir siempre. Sostenemos que tres cosas van delante de ese problema. La
factibilidad es aritmética y poda el espacio gratis, separando un límite de cardinalidad de un
límite de contexto que se confunden de rutina. La selección paga sólo bajo una condición que
podemos enunciar y verificar, y la condición implica abstenerse la mayor parte del tiempo. Y la
varianza que se le atribuye a la elección de topología la gobierna en gran medida la superficie de
herramientas: cincuenta veces entre los paradigmas que usan herramientas contra 1,2× entre los que
leen.

Nuestro resultado medido más fuerte no es sobre topologías en absoluto. Decirle a una
topología iterativa que su retriever había dejado de producir cortó su costo 3,05× contra
una dispersión de réplica de 1,62×, con la caída localizada exactamente en las dos celdas
desbocadas que el mecanismo predice. Una réplica no planeada además nos obligó a retirar un
efecto reportado y partir otro por la mitad, que es la disciplina funcionando y no
fallando. Las tres fallas de costo más grandes que
encontramos no se arreglaron con topologías mejores ni con modelos mejores, sino con señales de
contabilidad que no existían.

Lo que no tenemos es un selector validado, un piso de ruido, ni ninguna medición en el régimen
donde leer todo es imposible. El harness para las tres cosas está construido y el protocolo está
registrado de antemano, incluida la regla de decisión para el resultado en que ningún selector le
gane al fallback — que sería un resultado, y se declara publicable **antes** de tener los datos.

---

# Apéndice A — Artefactos

| artefacto | contenido |
|---|---|
| `PATTERNS.md` | catálogo de patrones: 10 estructurales, 4 de control, 15 anti-patrones, con aplicabilidad enunciada sobre el vector de features |
| `ANALYSIS.md` | el análisis de fallas de §8 completo, por paradigma y por celda |
| `GATE.md` | ocho criterios binarios de publicación y su veredicto actual |
| `PLAN.md` | historia de revisiones de la tesis, incluidos dos encuadres superados y por qué |
| `D:\Apps\MAPO\lab` | el harness: 7 paradigmas, 5 brazos de recuperación, 3 superficies de herramientas, 4 niveles de garantía, generador de corpus con verificador independiente, 63 aserciones chequeadas por máquina |

Siete de los quince anti-patrones del catálogo son errores cometidos y medidos en el curso de este
trabajo, incluidos dos que contradijeron nuestras propias predicciones publicadas.
