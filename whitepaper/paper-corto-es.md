# Hardness Over Hope: Policy-as-Code and Deterministic Governance in LLM Agent Orchestration

## Confinamiento de varianza en agentes LLM mediante un plano de control determinista y plástico

Versión breve, v2, 2026-09-01. Autor: Ariel Edgardo Levy.

> Versión de conferencia. La extensa (trece figuras, tres algoritmos en pseudocódigo, los dos
> teoremas con sus demostraciones completas, el registro por celda y la cronología de
> predicciones) es `paper-es.md`.

---

## Resumen

Un arnés de agentes es la estructura de control que envuelve a un LLM y decide qué llamada
viene después: un bucle de razonamiento, una descomposición en sub-tareas, un grafo de
verificar-replanificar. La práctica moderna de arneses arrastra una deficiencia de diseño.
Hereda las propiedades probabilísticas del componente que envuelve. El arnés está hecho de
llamadas al modelo, así que toda propiedad que se le quiera exigir al sistema (reproducibilidad,
trazabilidad, cobertura) queda condicionada a la salida de algo que no la tiene.

El caso más claro son las guardas. Un verificador de alucinación implementado como otra llamada
al modelo padece la misma deficiencia que vino a corregir. Verificar con el mismo material del
que se desconfía no produce una garantía. Produce una segunda estimación correlacionada con la
primera. La forma general es la premisa de este trabajo:

> Apilar instancias del componente puede subir una probabilidad. No puede producir una
> propiedad.

Así que la garantía tiene que venir de un componente de otra clase. Interponemos entre el
modelo y el flujo un motor determinista y plástico que decide sobre creencias tipadas, y le
dejamos al modelo un solo papel. Se le pregunta qué dice el material y lo que devuelve se tipa
como proposiciones («esta cuenta figura a nombre de X») que entran a una base de creencias, cada
una con la unidad de la que salió. Por eso se lo llama sensor, y estocástico, porque la misma
pregunta sobre el mismo material puede devolver otra cosa. El motor separa dos funciones que la
práctica corriente colapsa:

```
    decisión  = f(creencias)          f determinista, tipada, auditable
    creencias = g(mundo, sensor)      g estocástica
```

La garantía que eso compra tiene una forma precisa. Misma base de creencias, misma decisión. Y
`f` es determinista dentro de un request y plástica entre requests. Lo que aprende son
políticas, que consolidan offline con guarda anti-regresión en un artefacto firmado y se
ejecutan como código. El sensor tiene los pesos congelados. El que aprende es el sistema.

Y lo que aprende no es cuál paradigma gana. El banco que sostiene este trabajo corre doce
paradigmas sobre las mismas tareas, y la lectura obvia, un torneo, es la que el registro refuta.
Los brazos que comparten capacidades empatan, y elegir entre ellos por calidad no tiene premio
neto. El banco se lee de otra forma. Es la fuente de episodios de la que el sistema extrae qué
exige un request, qué puede hacer cada brazo, y qué predice su comportamiento. Los paradigmas
no compiten. Son un repertorio de capacidades.

Sobre un corpus de análisis forense de hechos, con doce paradigmas medidos bajo condiciones
idénticas y sin juez LLM (la campaña con `gpt-5.6-luna`, los tres episodios del ciclo con
`gpt-5.4-nano`, y §5.4 declara qué transfiere entre los dos), contribuimos:

1. La máquina, con su costo medido. Un agente confina su varianza cuando ninguna ramificación
   de su trayectoria depende del sensor. La Proposición 1 prueba que entonces toda discrepancia
   entre réplicas tiene un nodo responsable. Entre el 17% y el 34% de las celdas devuelven
   resultados distintos a temperatura cero con semilla fija, y absorber ramificaciones lleva un
   paradigma de 0,33 a 0,89 haciendo coincidir sus réplicas. El dial de garantía es gratis
   hasta A2 y en A3 se lleva el 60% del catálogo y el 31% de la utilidad.
2. La interfaz aprendible. Un paradigma es un paquete de capacidades auditables contra su
   propio código, y la pregunta exige capacidades, no nombres. Declaradas así, predicen un
   paradigma nunca visto mejor que la identidad del paradigma, incluso cuando a ésta se le
   permite ver la respuesta, sobre ocho brazos y sin cruzar su nulo (`p = 0,065`): sugestivo,
   y más brazos lo sentencian. El catálogo encuentra un hueco sin correr nada, y queda como
   predicción registrada hasta que ese brazo se construya. La ontología de la pregunta separa a
   los brazos 40% más por segmento que la partición estructural, medido sobre la etiqueta de
   diseño.
3. El ciclo que repara su propio vocabulario. Tres refutaciones preregistradas sobre tres
   mundos que la política nunca vio, cada una con su decisión reproducida 26 de 26, y cada una
   produjo un sensor nuevo, `COMPUTED` y sin modelo. Quién lo ejecutó hay que decirlo. El ciclo
   lo corrieron personas, leyendo cada refutación y agregando el eje. El sistema consume los
   sensores que el ciclo produjo, y la automatización de ese paso está diseñada y no medida. Lo
   que el ciclo establece es el método y su condición.
4. Lo que la política aprende, y qué compra. Entre brazos capaces, el desempate por costo paga
   fuera de muestra: 42% de ahorro con una señal suelta sobre 59 × 8, 46% con la política
   entera sobre 41 × 7, los dos a utilidad indistinguible. Y los predictores que el registro
   entrega. El paradigma determina el recall de evidencia seis veces más que la tarea, y
   ofrecer una herramienta cambia la conducta del agente aunque no la use.

Lo que une las cuatro es que una clave de política tiene que ser `COMPUTED`, y la Proposición 2
lo enuncia. Sólo se puede aprender sobre lo que se puede sensar sin el modelo. Por eso
determinismo y aprendizaje no compiten. El primero es la condición del segundo.

Palabras clave: confinamiento de varianza, agentes LLM, plano de control, procedencia,
capacidades, ontología de la pregunta, aprendizaje plástico, reproducibilidad.

---

![El contrato de garantía, y qué pasa cuando la evidencia no alcanza](figuras/contrato-de-garantia.svg)

Figura 1. El request entra por la izquierda y sale por la derecha, y los cuatro pasos del riel
no gastan un token hasta el último. La rama de rechazo: cuando ninguna procedencia alcanza el
piso exigido, abstenerse es una salida y no un fallo. El lazo es la plasticidad. El registro
sube el piso del próximo request, offline y con guarda anti-regresión, sin que nadie toque un
peso. La flecha punteada que sube del carril de abajo es la única que cruza la frontera, y lleva
proposiciones tipadas. Nunca control de flujo.


# 1. Introducción

Un arnés de agentes se elige una vez en tiempo de diseño y se congela en el código, y sobre él
se construyen sistemas que firman números, disparan acciones y contestan a usuarios. Cualquier
otra capa de un sistema de producción da tres propiedades por sentadas. En un agente hay que
construirlas.

1. El flujo de control vive en el código. El modelo es aleatorio y va a seguir siéndolo. Lo que
un arnés decide es cuánto del sistema depende de esa aleatoriedad. Delegarle ramificaciones
(qué buscar después, cuántas vueltas dar, cuándo parar) vuelve aleatoria la trayectoria misma.
Su precio está medido. Entre el 17% y el 34% de las celdas cambian de resultado entre réplicas a
temperatura cero con el mismo prompt y la misma semilla (§5.2).

2. Cada valor emitido exhibe de dónde salió. Una respuesta correcta y una inventada llegan con
la misma cara, así que la fuente tiene que viajar con el valor.

3. El sistema puede callarse. En la celda más difícil del corpus, el paradigma que gana lo hace
con 12 correctas, 3 abstenciones y cero respuestas equivocadas. Los demás contestan siempre y
devuelven un número plausible y falso.

Las tres se consiguen en el mismo lugar. Moviendo decisiones de flujo de control desde el
modelo hacia el código, sobre señales del entorno que son contables y verificables.

## 1.1 Una expectativa de la literatura, y qué mide de verdad

La motivación habitual para trabajar sobre arneses es que elegir el paradigma por tarea paga.
La selección oráculo por tarea supera al mejor fijo por 17,1pp sobre seis paradigmas, cuatro
modelos frontera y diez benchmarks [arXiv:2604.06753], y los ruteadores reales recuperan un
cuarto de esa brecha, lo que invita a concluir que hacen falta mejores selectores.

Este registro dice otra cosa, y es lo que reordenó el programa. El premio neto del ruteo por
calidad es −0,008 contra el mejor fijo en muestra y negativo en los tres estratos del held-out
(§5.6). El mecanismo es que la interacción tarea×paradigma es enorme, 48% de la varianza, pero
vive entre los paradigmas que nadie elegiría, y los tres que competirían tienen las mismas
capacidades (§5.3). Elegir por nombre entre brazos que hacen lo mismo no tiene premio porque no
hay nada que elegir.

Eso no vuelve inútil al ruteo. Muestra que la pregunta estaba mal formulada. Los paradigmas no
son competidores comparables sobre un eje de calidad. Son paquetes distintos de capacidades, y
el premio aparece sobre los ejes donde las capacidades difieren (costo, cobertura, abstención)
y no sobre el que comparten. El banco no existe para coronar un paradigma. Existe para que el
sistema aprenda qué exige cada request y qué le puede dar cada brazo.

## 1.2 Dominio y alcance

Lo que se evalúa es capacidad de RAG sobre análisis forense de hechos. Preguntas del tipo que
hace un auditor o un analista de cumplimiento sobre un conjunto documental. Qué cuenta figura a
nombre de quién, quién le reporta a quién subiendo N escalones, si existe registro de una
transferencia, si alguien debía escalar y no lo hizo.

El corpus es heterogéneo por construcción, y sus once modos son los modos de falla de ese
dominio. Hecho único verificable, enumeración independiente, cadena acoplada, agregación
exhaustiva, horizonte desconocido, acción irreversible, vigencia, plantel declarado, ausencia,
presuposición falsa y escritura compartida. Sobre eso se apilan tres anchos (5, 20 y 60
unidades) y entidades con variantes de superficie, anáfora y señuelos. El 36,5% de las menciones
son invisibles a una búsqueda del nombre completo y el 100% de los saltos de cadena exige
resolver una variante.

Medido: 78 tareas × 12 paradigmas × 3 réplicas, 121,4M tokens, cero errores de infraestructura,
sin juez LLM y con el corrector auditado, más un held-out por el mismo camino de código y una
réplica del consenso sobre una segunda familia de modelo. Los tres episodios de §5.4 son
anteriores a la campaña y corrieron sobre `gpt-5.4-nano`; transfiere el mecanismo, no las
magnitudes. Fuera de alcance: un selector validado, benchmarks públicos, y un clasificador que
recupere los ejes de la ontología desde un request real.

## 1.3 Organización

§2 ubica el trabajo. §3 describe el motor. §4 es la teoría: confinamiento, la identidad
contable del valor de seleccionar, y la clave de la política. §5 son los resultados por
contribución: plantel y varianza, la interfaz aprendible, el ciclo, lo que la política compra,
por qué no hay premio de calidad, el consenso. §6 son las amenazas y el impacto. §7 concluye.

---

# 2. Trabajo relacionado

Cada pieza del motor viene de una línea con décadas de trabajo, y cada línea asume algo sobre
su fuente de creencias que un LLM viola. Lo que sigue es el catálogo de supuestos que hubo que
reemplazar.

Tabla 1. El linaje, y qué supuesto rompe un sensor estocástico.

| línea | qué aporta | qué asume | qué rompe un LLM |
|---|---|---|---|
| Revisión de creencias, AGM (1985) | qué se retracta al entrar evidencia contradictoria | el postulado de éxito: la creencia entrante se acepta | una fuente que puede equivocarse vuelve inadmisible aceptar por defecto |
| Mantenimiento de verdad: Doyle (1979), de Kleer (1986) | cada creencia exhibe su justificación | que la justificación existe | fabrica justificaciones plausibles y bien formadas |
| Procedencia: Buneman *et al.* (2001), Green *et al.* (2007) | de dónde vino un valor, aparte de cuánto se le cree | que se deriva de la operación | no hay operación, hay una emisión |
| BDI (Rao y Georgeff, 1995) | deliberación separada de ejecución | sensores que no alucinan | alucina consistentemente |
| Políticas como datos: Soar (1987), ACT-R | la política es artefacto inspeccionable | condiciones de regla observables | las condiciones las emite el sensor, y la clave hereda su varianza (§5.6) |
| Plasticidad hebbiana (Hebb, 1949) | una asociación entre pares tiene contenido propio | que los eventos asociados son eventos | la traza es lo que el sensor pidió, no lo que ocurrió |
| Opción de rechazo (Chow, 1970) | cubrir menos a cambio de errar menos | una confianza calibrada | la confianza declarada no está calibrada; §5.7 construye una |
| Argumentación abstracta (Dung, 1995) | una conclusión vale si sobrevive los ataques | una relación de ataque dada | el espacio de respuestas plausibles y falsas no es construible |

Qué se hizo con cada supuesto roto. La procedencia deja de derivarse y pasa a declararse y
verificarse. La confianza deja de leerse del modelo y pasa a calibrarse contra el registro. Y
las condiciones de la política pasan a exigirse `COMPUTED`, porque una clave elicitada convierte
la tabla de decisión en una variable aleatoria.

Los vecinos contemporáneos. La búsqueda automática de workflows (AFlow, ADAS, GPTSwarm) optimiza
offline un workflow. Select-then-Solve, FlowBank y TRACE-Router seleccionan en inferencia con
cobertura total, sin filtro de factibilidad, sin decisión determinista y sin abstención. §5.6
mide que el premio que los motiva no existe entre brazos capaces, y §5.3 da el mecanismo. El
Structured Cognitive Loop [arXiv:2511.17673] gobierna la inferencia con un runtime determinista
en un modo global único. Este trabajo gradúa la garantía por solicitud, la deriva de creencias
y acota con ella el espacio de planes. El ruteo sobre features textuales [arXiv:2608.00106]
aprende un ruteador interpretable offline. Acá las features son capacidades declaradas del
código y ejes de la pregunta, y el ruteador puede abstenerse.

Cuatro líneas más tienen dueño y se nombran. La cascada de modelos es FrugalGPT
[arXiv:2305.05176], con el ruteo híbrido [arXiv:2404.14618], RouterBench [arXiv:2403.12031] y
RouteLLM [arXiv:2406.18665] detrás; deciden entre modelos con el mismo control de flujo, y su
detector es un puntaje aprendido sobre la respuesta, elicitado. Lo que §4 agrega es la partición
por verificabilidad, y la exigencia de que el detector sea `COMPUTED` u `OBSERVED`. El voto entre
respuestas es Self-Consistency [arXiv:2203.11171] y su versión universal [arXiv:2311.17311]; §5.7
vota con estructuras de control distintas, replica sobre otra familia contra criterio
registrado, y no deja que el voto suba de procedencia. La separación «el modelo es un módulo, el
control es del programa» es DSPy [arXiv:2310.03714], que optimiza el fraseo de los módulos; acá
el fraseo es control nulo y lo que se aprende es qué exige la pregunta. Y las tarjetas de
habilidades de agentes (Agent2Agent y antecesores) son texto que el agente escribe sobre sí
mismo, `ELICITED`; una capacidad de §5.3 es un booleano declarado desde el código y auditado
contra el registro. Búsqueda fechada 2026-09-01: no se encontró trabajo que declare capacidades
de control de flujo desde el código y las someta a leave-one-arm-out.

MINERVA/HADD (Jaime y Errecalde, 2026, Zenodo 10.5281/zenodo.20003407) es el antecedente de
vocabulario más cercano. Una arquitectura declarada donde el LLM queda confinado a sensor tipado
y la cognición es determinista sobre la base de creencias, en el encuadre neurosimbólico de
Kautz [Kautz, 2022]. Se lo acredita por las tres palabras que se comparten. Es un documento de arquitectura y no de medición. Su única validación
enunciada es «validado en producción», sin corpus ni número. Nada en él tiene un costo medido y
nada en él aprende. Su compuerta companion no está disponible públicamente a la fecha de este
borrador y no se cita como mecanismo.

Tres mecanismos que ya están ocupados y este paper no reclama. Sondeo con presupuesto sobre un
estado de creencias tipado [arXiv:2606.31422], ediciones de política filtradas por un
verificador [arXiv:2605.09487] y pisos de procedencia sobre acciones [arXiv:2607.01236]. Lo que
queda libre, como conjunción, es una capa de decisión que elige qué topología de control correr
por request, puede abstenerse, poda por aritmética antes de cualquier inferencia, y aprende
sobre capacidades y ejes de la pregunta en vez de sobre nombres de paradigma.

---

# 3. El motor

![El método determinista: qué decide el código y qué emite el modelo](figuras/metodo-determinista.svg)

Un request declara su material, su presupuesto y sus banderas de riesgo (`irreversible`,
`shared_writes`, `regulated`), siempre declaradas por el caller y jamás inferidas del texto. El
motor decide en cuatro pasos, y los dos primeros no gastan un token.

1. Factibilidad aritmética. Cada paradigma declara cuántas unidades necesita leer y cuántas
   llamadas emite. Con el material y el presupuesto eso es una desigualdad. Los que no entran se
   podan antes de la primera inferencia. En el registro esto poda a `direct` en el 94% de las
   celdas. No falla ahí. No corre.
2. Creencias con procedencia. Toda proposición entra a una base tipada por un retículo
   `ASSUMED < ELICITED < OBSERVED < COMPUTED`. La procedencia no es credencia. Dice de dónde vino
   el valor, no cuánto se le cree.
3. Dial de garantía, en cuatro niveles A0–A3. El nivel se deriva de creencias sobre la
   solicitud y acota el espacio de paradigmas admisibles. Una acción irreversible exige piso
   `COMPUTED` u `OBSERVED`. La opinión del modelo no es evidencia admisible para apretar un
   botón. El nivel efectivo es el `max` del pedido, el piso de creencias y el piso aprendido, y
   `max` es la única composición bajo la cual cada fuente sólo puede endurecer.
4. Selección sobre capacidades, con abstención. Sobre lo que sobrevivió, la política decide qué
   exige la pregunta y qué brazos lo tienen, elige entre esos, o se abstiene y difiere.

Cada decisión deja un registro `EXPLAIN` con la creencia que la disparó y su procedencia. El LLM
emite proposiciones. Jamás maneja flujo de control ni decide compuertas.

Qué es plástico. El sensor tiene los pesos congelados y sin embargo el sistema cambia de
comportamiento con la experiencia, por tres pasos. Uno, cada decisión deja su huella epistémica
(la creencia que la disparó, su procedencia, el paradigma elegido y lo que salió). Es la base de
creencias creciendo con la misma estructura tipada que gobierna una decisión en vivo. Dos, la
consolidación reproduce ese registro offline, en orden de sorpresa y no cronológico, y emite una
política. Una tabla de condiciones sobre features, versionada y firmada, que se ejecuta como
código determinista. Tres, la política entra sólo si no regresa sobre episodios retenidos, y el
registro se parte en tres por tarea (una parte propone, una puntúa, una la toca sólo la guarda),
porque buscar muchas particiones contra un solo holdout es la forma en que detectar una verdad
se vuelve confabularla.

> Un sistema plástico suele ser opaco, y uno auditable suele ser fijo. Poner el aprendizaje en la
> base de creencias da las dos. Lo aprendido es un artefacto legible, diffeable, versionado y
> revertible, y su instalación pasa por una guarda. Un motor de *policy-as-code* es una
> realización posible de esa tabla, y no es la que este trabajo corre. La capa de decisión no
> depende de ningún motor externo.

Sobre qué superficies aprende. Qué paradigma admite una región de features y cuál es el barato
entre los capaces. Qué índice sirve a una consulta según su clase. Qué asociación
`tool_i → tool_j` predice. Cómo repartir el alcance entre sub-agentes. Dónde sube el piso de
garantía porque las aserciones del modelo se rechazan. Y la calibración de credencia por
proposición. Un nivel arriba de todas está lo que §5.4 mide. El vocabulario mismo sobre el que
una política puede aprender.

---

# 4. Teoría

## 4.1 Confinamiento de varianza

**Definición 1** (Trayectoria). Una trayectoria `T(q, M)` es la secuencia ordenada de nodos
visitados por un agente sobre el request `q` y el material `M`. Cada nodo es un par ⟨unidad
leída, llamada emitida⟩.

**Definición 2** (Punto de ramificación delegado). Un nodo `nᵢ ∈ T` es delegado si la identidad
de `nᵢ₊₁` es función de la salida del sensor. `d(T)` es la cantidad de nodos delegados. Un agente
que le pregunta al modelo «¿qué dice esta unidad?» no delega ramificación. Uno que le pregunta
«¿dónde busco ahora?» sí.

**Definición 3** (Confinamiento). La varianza está confinada sobre `(q, M)` si `d(T) = 0`. La
secuencia de nodos es función determinista de `q` y `M`, y el sensor sólo determina el contenido
atribuido a cada nodo.

**Proposición 1** (Localización). Si la varianza está confinada, dos ejecuciones cualesquiera
sobre el mismo `(q, M)` visitan la misma secuencia de nodos, y toda discrepancia entre sus
salidas es atribuible a un nodo identificable.

*Demostración.* Por inducción sobre la longitud. El nodo inicial es función de `q` y `M`. Dado
`nᵢ` idéntico en ambas, `nᵢ₊₁` es función de `(q, M, n₁…nᵢ)` y no del sensor porque `d(T) = 0`,
luego coincide. Una discrepancia de salida exige que algún nodo haya recibido contenido distinto,
y ese nodo es el testigo. ∎

Lo que compra y lo que no. Una discrepancia localizable es depurable, auditable y corregible. Una
repartida sobre una historia entera, no. El confinamiento no reduce la varianza del sensor ni
mejora la calidad. Reordena dónde puede manifestarse. Que además suba la utilidad (§5.2) es un
resultado de este corpus. Consecuencia observable: `pass^k`, la probabilidad de que las `k`
réplicas acierten todas. No es `pass@k`, que crece con `k`. `pass^k` decrece. Nombre y métrica
vienen de `tau2-bench`.

## 4.2 El valor de seleccionar es una identidad contable

Sea `p⋆` el fallback y `p_1 … p_k` los brazos, con `Δ_j(t) = u(t,p_j) − u(t,p⋆)`. Partir el
espacio de tareas en tres por brazo, con desigualdad estricta:

```
S₊ʲ = { Δ_j > 0 }   ganancia    π_j = Pr[S₊ʲ]
S₀ʲ = { Δ_j = 0 }   empate      τ_j = Pr[S₀ʲ]
S₋ʲ = { Δ_j < 0 }   pérdida     ν_j = Pr[S₋ʲ]
```

y, condicionadas a lo efectivamente ruteado, `α_j = Pr[rutear a p_j | S₊ʲ]`,
`G_j = E[Δ_j | rutear a p_j, S₊ʲ]`, `β_j = Pr[rutear a p_j | S₋ʲ]`,
`L_j = E[−Δ_j | rutear a p_j, S₋ʲ]`.

**Teorema 1.** Para todo `k ≥ 1`, `V(r) − V(p⋆) = Σⱼ ( π_j α_j G_j − ν_j β_j L_j )` exactamente,
sin ningún supuesto de independencia.

*Demostración.* `V(r) − V(p⋆) = E[Δ_{r(t)}(t)·1{r(t) ≠ p⋆}]`. Descomponiendo por destino y
partiendo cada esperanza según el signo de `Δ_j`. `S₊ʲ` pesa `π_j α_j` con media `G_j`, `S₋ʲ` pesa
`ν_j β_j` con media `−L_j`, y `S₀ʲ` aporta exactamente cero. ∎

El empate no es un tecnicismo. En este catálogo un brazo es el más barato al empatar en 46 de
96 celdas, y una versión anterior que definía `β` sobre el complemento de `S₊` le cobraba al
ruteador haber ruteado sobre un empate, un acto que no cuesta nada.

> Es una identidad contable, no un resultado empírico, y se usa como instrumento. No afirma que
> rutear convenga. Descompone el valor de rutear en términos medibles por separado, y por eso
> permite que una evaluación de ruteo sea falsable. En este registro, además, muestra qué se
> pierde al colapsar dos ejes. `π`, `α`, `β` dicen si el ruteador acierta. `G`, `L` dicen cuánto
> cuesta cuando no.

## 4.3 La clave de la política y su procedencia

Todo lo que §3 llama aprender se ejecuta como una tabla. La política mira una clave y devuelve
una decisión. Esta sección dice de qué depende que esa tabla conserve la garantía de §4.1.

**Definición 4** (Clave de la política). Sea `κ = φ(q, M, σ)` una tupla de ejes calculada sobre
el request, el material y la salida `σ` del sensor. Un eje es `COMPUTED` si es función de
`(q, M)` solamente, y `ELICITED` si depende de `σ`. Una política `θ` es una función
determinista de la clave a una decisión, brazo, abstención o sonda.

**Proposición 2** (La procedencia de la clave hereda o rompe el confinamiento). Si todos los
ejes de `κ` son `COMPUTED`, `θ(φ(q, M))` es función determinista de `(q, M)`, la elección del
brazo no es una ramificación delegada, y la trayectoria completa conserva la Proposición 1. Si
algún eje es `ELICITED`, para `(q, M)` fijos la decisión es una variable aleatoria sobre la
distribución de `σ`, aun con `d(T) = 0` en cada brazo: dos réplicas del mismo request pueden
ejecutar brazos distintos, y la discrepancia no tiene nodo responsable en ninguna trayectoria.

*Demostración.* La primera parte es composición de funciones y la inducción de la Proposición 1
arrancando un nodo antes. La segunda, que un eje que depende de `σ` vuelve a `κ` no constante
sobre `(q, M)`, así que la elección del brazo es delegada por la Definición 2. ∎

Es la exigencia que §5.6 mide. El vocabulario de región tenía un eje elicitado y ese eje
cambió de valor en el 27% de las tareas según qué modelo las sensó. Y explica por qué cada
sensor del ciclo de §5.4 tuvo que ser `COMPUTED`. Lo que no afirma es que una clave `COMPUTED`
sea informativa. Una clave puede ser determinista e inútil, y §5.4 mide ese caso.

---

# 5. Resultados

Tres términos, una vez cada uno. Una celda es un par tarea × paradigma, la unidad de medición.
Un modo es una de las once clases de falla del corpus. La etiqueta de diseño es el modo del que
salió una tarea. Se conoce al construirla y no al decidir, así que funciona como cota superior
y nunca como señal disponible.

Régimen. Doce paradigmas sobre condiciones idénticas con `repeat = 3` sobre 78 tareas, 121,4M
tokens, cero errores de infraestructura, sin juez LLM. Cada panel declara el rectángulo tarea ×
paradigma del que sale. Cada comparación, su piso de ruido por celda. El corrector se audita
sobre toda respuesta de utilidad cero. De 567 ceros, ninguno presenta señal fuerte de defecto de
emparejamiento.

Ocho preguntas, con criterio fijado antes de mirar el dato. PI1, cuánta varianza de trayectoria
hay y si confinarla cambia el resultado (§5.2). PI5, si las capacidades declaradas transfieren a
un paradigma no visto, y PI6, si la ontología de la pregunta separa mejor que la partición
estructural (§5.3). PI7, si cada refutación produjo un sensor nuevo sin romper la
reproducibilidad (§5.4). PI8, qué aprende la política que pague fuera de muestra y qué predice el
comportamiento (§5.5). PI2, si elegir por identidad captura brecha neta positiva, y PI3, si
alguna señal explica la interacción (§5.6). PI4, si el acuerdo entre paradigmas predice
corrección sin oráculo ni juez (§5.7).

## 5.1 El plantel

Tabla 2. Los doce paradigmas, con sus denominadores.

| brazo | aplica | u | u × aplica | pass^3 | tok/celda | USD/1k celdas | serie |
|---|---:|---:|---:|---:|---:|---:|---:|
| `react` | 100% | 0,850 | 0,850 | 0,734 | 108.137 | 22 | 1,35 s |
| `dag_strategy` | 100% | 0,830 | 0,830 | 0,703 | 105.293 | 22 | 2,87 s |
| `reflection` | 100% | 0,808 | 0,808 | 0,688 | 133.574 | 27 | 1,76 s |
| `rewoo` | 100% | 0,678 | 0,678 | 0,531 | 10.840 | 2 | 0,77 s |
| `supervisor` | 100% | 0,591 | 0,591 | 0,406 | 64.079 | 13 | 2,66 s |
| `gist_reader` | 100% | 0,584 | 0,584 | 0,516 | 23.075 | 5 | 0,91 s |
| `handoff` | 96% | 0,604 | 0,581 | 0,438 | 120.500 | 27 | 2,04 s |
| `pointer_chase` | 96% | 0,515 | 0,492 | 0,359 | 9.787 | 2 | 1,38 s |
| `graph_traverse` | 52% | 0,511 | 0,266 | — | 21.356 | 4 | — |
| `streaming_scan` | 12% | 0,750 | 0,090 | — | 26.380 | 5 | — |
| `extract_compute` | 12% | 0,583 | 0,070 | — | 26.184 | 5 | — |
| `direct` | 6% | 0,917 | 0,055 | — | 22.822 | 5 | — |

`aplica` es qué fracción de las celdas ofrecidas a ese brazo pasa la compuerta de factibilidad, y
`u` promedia sólo las que pasan, con `λ = 0`; las cuatro primeras columnas se recomputaron
contra el registro el 2026-09-01. `pass^3`, `serie` y USD son del cierre de campaña del
2026-08-30. `pass^3` y `serie` salen del rectángulo de 64 tareas × 8 brazos porque exigen que
todos hayan corrido las mismas tareas con tres réplicas. Las
cuatro correcciones de §5.2 sobre `pointer_chase` son posteriores a esta corrida, tocan 3 de 78
tareas y no se propagaron a esta tabla.

Tres regularidades. `u` y `u × aplica` son dos números. `direct` es el mejor del plantel donde
corre y aporta 0,055 porque corre en el 6% de las celdas. En el resto no corre, y eso lo decide
la aritmética antes del primer token. `pass^3` siempre está por debajo de `u`. Es varianza que
vive dentro de una celda, invisible para cualquier piso de ruido entre brazos. El margen está en
el costo y no en la calidad. Entre `react` y `rewoo` hay 0,172 de utilidad y un factor 11× de
costo. En utilidad los brazos se separan por centésimas. En lo que cuestan, por órdenes de
magnitud. Y el costo es de 98,6% a 100% de entrada en todos. Los paradigmas no se diferencian en
lo que generan. Se diferencian en lo que arrastran al prompt.

## 5.2 PI1. La varianza de trayectoria, y confinarla

```
brazo            pass@1   pass^3    caída   inestables
react             0,875    0,797   −0,078          17%
dag_strategy      0,874    0,763   −0,112          20%
rewoo             0,718    0,576   −0,142          27%
supervisor        0,637    0,441   −0,196          34%
```

Entre el 17% y el 34% de las celdas cambian de resultado entre réplicas, con `t = 0`, semilla
fija y el mismo prompt. Sobre una llamada la varianza del sensor es un token distinto. Sobre una
trayectoria, una elección distinta en el paso uno cambia qué documento se lee en el paso dos. La
varianza no se promedia. Se ramifica.

![Una ramificación delegada, resuelta por código](figuras/sensor-determinista.svg)

La intervención. La celda de cadenas acopladas tenía un brazo en 0,33. Cuatro correcciones,
todas de flujo de control o de tipado y ninguna de prompt. Una entidad nombrada se busca con el
índice léxico y no con el híbrido. La salida del sensor se tipa a entidad antes de usarse. Un
salto a una unidad que no nombra a quien se persigue no es un salto, y entre empatados gana el
que la nombra antes. Y el ancla la resuelve el código. De 0,33 a 0,89, empatando al mejor de la
celda. La cuarta corrección prueba el punto sola. Con el mismo prompt y los mismos resultados de
búsqueda, la réplica 0 elegía el ancla correcta (`u = 1,000`) y las réplicas 1 y 2 otra (0,000).
Una decisión de flujo delegada al sensor se lleva el determinismo.

Y la varianza no crece con el número de ramificaciones. La conjetura ingenua
`pass^k ≈ pass@1 · q^d` se refuta. La correlación entre `d` y la caída de `pass^3` es `r = −0,24`.
Importa cuál se absorbe, y eso convierte el diseño de un arnés en un problema tratable.

## 5.3 PI5 y PI6. La interfaz aprendible: capacidades y ejes de la pregunta

`P15` se refutó mapeando ontología de la pregunta a nombre de paradigma. Perdió −0,087 contra el
mejor fijo (§5.4). El eslabón que faltaba:

    ontología de la pregunta  →  capacidades que EXIGE  →  brazos que las tienen  →  el barato

**Definición 5** (Capacidad, exigencia, brazo capaz). Una capacidad es un predicado booleano
sobre el código de un brazo, declarado con su definición, el sitio del código donde se ve y el
número medido que la justifica. `TIENE(p)` es el conjunto de capacidades de un brazo, y está
definido para un brazo que todavía no corrió. `EXIGE(e)` es el conjunto de capacidades sin las
cuales un eje de la pregunta no se satisface, declarado por eje y no por celda. Los brazos
capaces para una pregunta con ejes `E` son `{ p : ⋃_{e ∈ E} EXIGE(e) ⊆ TIENE(p) }`, un conjunto y
no un ranking. Si los ejes son `COMPUTED`, una política sobre capaces hereda la Proposición 2.

Diez capacidades declaradas desde el código, cada una con el número que se explica con ella y no
sin ella, y con el sitio del código donde se ve. Payload completo, adapta tras ver un resultado,
costo que no escala con el alcance, lectura sin pérdida, cobertura garantizada, verifica y
replanifica, resuelve referencia, largo gobernado por código, elige índice por consulta,
abstiene sin prueba. Una auditoría contrasta lo declarado contra lo corrido. Un brazo que
declara abstenerse y nunca se abstuvo tiene una declaración falsa, y eso se ve.

| eje de la pregunta | capacidades que exige |
|---|---|
| cadena acoplada | resolver referencia, largo gobernado por código, adapta |
| contradicción | payload completo, lectura sin pérdida |
| cobertura exhaustiva | cobertura garantizada |
| ausencia | cobertura garantizada, abstiene sin prueba. Ningún brazo las junta |
| horizonte desconocido | adapta |
| entidad nombrada | elige índice por consulta |
| material mayor que la ventana | costo que no escala con el alcance |

La función que la consume devuelve el conjunto de capaces, nunca un ganador. Y encuentra un
hueco sin correr nada. La pregunta de ausencia no tiene brazo capaz. Para eso sirve declarar
capacidades. Predice sobre un brazo que todavía no existe.

![El EDA de capacidades](figuras/eda-capacidades.svg)

PI5. La prueba es dejar un brazo afuera, no una tarea. Un modelo con la identidad del paradigma
no puede decir nada de un brazo que no vio. Uno con capacidades sí, porque el brazo nuevo trae
su vector del código.

```
modelo                                          MAE
media global                                  0,364
dificultad de la tarea sola                   0,257
CAPACIDADES                                   0,233
identidad del brazo (viendo al que falta)     0,339
```

Las capacidades ganan 6 de 8 pliegues, y los dos que pierden son `gist_reader` y
`pointer_chase`, los dos brazos con el canal con pérdida más marcado: ahí la dificultad de la
tarea predice mejor, y eso dice que al catálogo le falta una capacidad o tiene una mal
declarada. La cuarta fila iba a ser un techo y no lo es. Sale peor pese a hacer trampa, porque
ignora la dificultad de la tarea, el 41% de la varianza. La
identidad del paradigma no es una buena representación ni cuando se la deja mirar la respuesta.
Contra capacidades barajadas, `p = 0,065`. Sugestivo y no establecido, porque ocho brazos son
ocho puntos. Lo que lo sentencia son más brazos, no más tareas. Y la tabla tiene su
contraejemplo escrito. `dag_strategy` saca 0,89 en la cadena acoplada sin dos de las tres
capacidades exigidas, por otra ruta. A la tabla le falta expresar «A y B, o bien C y D», y se
deja como conjunción para que siga siendo falsable.

PI6. La ontología separa más con menos segmentos. La salvedad va antes del número: la
segmentación se mide con la etiqueta de diseño, el modo del que salió cada tarea, que se conoce
al construir el corpus y no al decidir. Dentro de cada segmento, varianza entre brazos contra
ruido entre réplicas, sobre el registro ya pagado.

| segmentación | señal/ruido | segmentos | ganancia por segmento |
|---|---:|---:|---:|
| ninguna | 1,00 | 1 | — |
| región estructural, primer eje | 1,04 | 3 | 0,013 |
| ontología por eje | 1,74 | 5 | 0,148 |
| región estructural completa | 1,84 | 8 | 0,105 |

Sin controlar por cantidad de segmentos, la región completa gana por poco. Controlado, la
ontología extrae 40% más separación por segmento, y un solo eje, la contradicción, da
`S/R = 1,82` con una partición binaria. El caso concreto. Horizonte desconocido y vigencia son
idénticos en los seis campos computables de la región y tienen efecto opuesto. Lo que los separa
es si la pregunta pide el valor vigente o el valor a una fecha. Esto establece que hay
estructura ontológica y que la política debería segmentar por ella. No establece que se la pueda
detectar en un request real. Dos ejes ya son `COMPUTED` desde lo que el caller declara. Los demás
tienen a `ELICITED` como techo, y ése es el experimento que sigue.

## 5.4 PI7. El ciclo que repara su propio vocabulario

El registro que sostiene esta sección es la cronología de predicciones del laboratorio, cada
una anotada antes de correr y con su script de veredicto congelado en el mismo commit. Tres
refutaciones sobre tres mundos nuevos, y cada una produjo un sensor.

Dos cosas antes de los números. Quién ejecutó el ciclo: cada refutación la leyeron el autor y
su asistente, y el eje que faltaba lo diagnosticaron y lo agregaron a mano. El sistema no
propuso ningún eje. Consume los sensores `COMPUTED` que el ciclo produjo y reajusta la política
sobre ellos con guarda. La automatización de ese paso está diseñada en §3 y no corrió, así que
lo que esta sección establece es un método con su condición formal, no una propiedad autónoma
del sistema. Y sobre qué modelo: los tres episodios son anteriores a la campaña y corrieron
sobre `gpt-5.4-nano`, con 390 filas y unos 13 a 14M tokens cada uno, en tres mundos de 26
tareas. Transfiere el mecanismo, que a la clave le faltaba un eje, y la reproducibilidad. No
transfieren las magnitudes. Ninguna estadística mezcla los dos modelos.

Primer episodio, semilla 47. La política ruteó por región hacia un nombre de paradigma y perdió
−0,087 contra el mejor fijo, más allá del piso de ruido de 0,057, reproduciendo cada decisión 26
de 26. El mecanismo, verificado. Las tareas de horizonte desconocido caían en las mismas
regiones que las de cobertura porque el vocabulario no tenía eje para «no se sabe cuántos saltos
hay». La política mandó ahí al brazo que gana en cobertura, contra su propio veredicto
registrado de que ese brazo falla en horizonte, porque ninguna etiqueta le dijo en qué caso
estaba. Donde el registro sí tenía la señal, funcionó. +0,121 sobre cobertura. Dos
incertidumbres, y el criterio registrado llevaba una: contra el piso de ruido por celda, −0,087
está fuera de ±0,057 y la predicción falla su propio test; el intervalo de muestreo sobre 26
tareas, bootstrap pareado, incluye al cero, [−0,228, +0,037], `p = 0,19`. Se reportan las dos, y
bajo Benjamini-Hochberg ningún contraste de ese episodio sobrevive. Lo que produjo el ciclo fue
el eje de continuidad, recurrencia de una clave literal entre unidades, función pura del
material. Separa el horizonte 6 de 6 en tres corpus, con cero falsos positivos. Y agregarlo sin
más fragmentó las regiones por debajo del piso de confianza, de 12 tareas con margen a 0. Con
retroceso jerárquico a la región padre, 16 de 26.

Segundo episodio, semilla 61. Con el eje nuevo, la acción real puntuada y el costo cobrado, la
medición preregistrada como decisiva fue el barrido sobre λ.

| λ | neto contra el mejor fijo | neto contra siempre-`react` |
|---:|---:|---:|
| 0,00 | +0,121 | +0,177 |
| 0,02 | −0,404 | +0,000 |
| 0,05 | −1,289 | −0,265 |

Con el costo a cero, rutear por identidad captura +0,121. A λ = 0,02 ya está dentro del ruido. La
oración se escribió antes del número. La selección por nombre compra calidad sólo cuando los
tokens son gratis. Lo que produjo el ciclo es la corrección de la valuación, y el hallazgo de
que en un corpus de coincidencia exacta la cascada precede a la selección en 20 de 22 tareas, porque la propiedad que hace gradeable a una
tarea es la que hace correcta a la escalación. El tercer mundo se generó con detectores
declarados por tarea y la cascada bajó de 22 a 2 de 26. La sonda disparó en 14 y no resolvió
ninguna, así que la decisión honesta fue diferir. Reproducibilidad, 26 de 26 en los tres.

Tercer episodio, el literal. El vocabulario vigente agrega en cuántas unidades aparece el
literal que la pregunta cita. Forma de token cerrada, sin modelo, y no es un disparador léxico
porque cambia de valor si cambia el material. Medido leave-one-out sobre 41 tareas × 7 brazos
contra el anterior: 0,951 y 46% de ahorro contra 0,928 y 37%. Y midiendo apareció un defecto del
sensor. Una pregunta booleana cita sus opciones de respuesta, no un término, y la guarda usa la
cardinalidad que el caller declara.

| episodio | qué faltaba | qué se agregó | procedencia | reproducida |
|---|---|---|---|---:|
| semilla 47 | eje de horizonte | continuidad entre unidades | `COMPUTED` | 26/26 |
| semilla 61 | valuación de la acción real | costo de la escalera; detector separado del gold | — | 26/26 |
| semilla 73 | vía para que la selección dispare | detector declarado por tarea | `COMPUTED` | 26/26 |
| vigente | separación entre brazos capaces | eje literal | `COMPUTED` | — |
| §5.3 | segmentación que la región no ve | ontología de la pregunta | dos `COMPUTED`, el resto `ELICITED` | — |

Cada sensor nuevo es `COMPUTED`, y por eso ninguno rompió la garantía: es la Proposición 2
respetada tres veces. La reproducibilidad no se perdió en ningún episodio. Y lo que el ciclo
produjo no es una política sobre paradigmas. Es el vocabulario sobre el que una política puede
aprender. Qué parte es del sistema hay que decirlo con precisión: la consolidación aprende la
política sobre el vocabulario que tiene; el vocabulario lo repararon personas, y esa reparación
es lo que este registro muestra como método. La disciplina que lo separa de un ajuste post hoc
es la de §5.6. Piso de ruido por sesgo del máximo, corrección por selección,
partición por tarea, y predicciones escritas antes del número.

## 5.5 PI8. Lo que la política aprende, y lo que predice

Entre brazos capaces, el desempate por costo paga y transfiere. Sobre el panel de 59 × 8, la
señal `cardinalidad × término` da 42% de ahorro a −0,017 de utilidad, leave-one-task-out. Sobre
41 × 7 con la política entera, 0,951 y 46% contra un mejor fijo de 0,930. La pregunta «qué
paradigma da la mejor respuesta» está agotada en este corpus. «Cuál es el más barato que da una
respuesta indistinguible» no, y es aprendible. Fragilidad declarada. 14 regiones sobre 41 tareas
son 2,9 por región.

El paradigma determina cuánta evidencia se lee, y eso vale más que el paradigma. Sobre el corpus
fuera de ventana del primer episodio (semilla 47, `gpt-5.4-nano`, 90 celdas), las celdas que
leyeron toda la evidencia portadora dan 0,869 y las que no, 0,336. Una brecha de +0,533, 4,2 veces la mayor diferencia entre paradigmas, y máxima en
horizonte desconocido, +0,721, la celda donde el primer episodio más perdió. Quién la determina:

| qué determina el recall | participación en su varianza |
|---|---:|
| la región, lo que la decisión ve | 5,2% |
| el paradigma, lo que la decisión elige | 62,2% |
| la tarea | 10,5% |

Seis veces más el paradigma que la tarea. Rutear es la palanca principal sobre la variable
dominante, y se la tira casi a ciegas porque la región apenas la ve. Reencuadra qué es rutear.
No la estructura que razona mejor. La estructura que va a leer la evidencia. Son participaciones
marginales sobre grupos desbalanceados, y el recall es consecuencia del paradigma y no covariable
previa. La magnitud se sostiene sola. La causalidad fina no.

Ofrecer una herramienta cambia la conducta, aunque no se use. Registrado antes de correr, sobre
el modelo de la campaña. Ofrecerle a `react` leer todo el material en una llamada, 63 celdas
pareadas. La predicción era
que la usaría. Se refutó al revés y el ahorro apareció igual.

| | tokens por celda | `u` | caracteres releídos |
|---|---:|---:|---:|
| sin la herramienta | 137.211 | 0,540 | 2.836.465 |
| con la herramienta ofrecida | 87.495 | 0,540 | 322.094 |

1,57× más barato con utilidad exactamente igual, la herramienta llamada en 3 de 63 celdas, y el
releído 8,8 veces menor. El efecto está en la oferta, no en el uso. La especificación de
herramientas es parte de la política.

El costo de una vuelta es reenvío, medido por llamada. Primera corrida con traza. El prompt del
turno 2 es 55,3× el del turno 0 y el del turno 8, 110,8×. El primer turno consume el 1% de la
entrada. El 99% es material ya pagado viajando otra vez. Y el registro da la señal para una
regla de parada. Entre réplicas de la misma celda con la misma utilidad, el 33% de los tokens
son evitables (49% en `dag_strategy`, 0% donde el abanico lo fija el código), y la racha máxima
de búsquedas estériles es 1,17 en la réplica barata contra 2,28 en la cara. La regla que la
consume está registrada como factor y no corrió.

| predictor | procedencia | qué anticipa antes de correr |
|---|---|---|
| capacidades declaradas | `COMPUTED` del código | si un brazo puede resolver lo que la pregunta exige |
| ley de costo del brazo | medida | si su costo escala con el material, con las vueltas, o con nada |
| paradigma → recall | medida | cuánta evidencia va a leer |
| oferta de herramientas | medida | que el releído cae con una salida barata a la vista |
| racha estéril | contable en runtime | que la trayectoria se desboca, antes de que termine |

Ninguno es un nombre de paradigma. Todos son cosas que una regla puede leer al decidir.

## 5.6 PI2 y PI3. Por qué no hay premio de calidad entre brazos capaces

Descomponiendo `u = μ + α(tarea) + β(brazo) + γ + ε` sobre 59 tareas × 8 brazos:

```
α  dificultad de la tarea     0,0632    41%
β  calidad del brazo          0,0160    10%
γ  INTERACCIÓN                0,0736    48%     (39% contando ε)
ε  ruido entre réplicas       0,0351
```

γ descontado el ruido da 0,0619, señal/ruido 5,30. Bajo el argumento habitual, correspondería
rutear. PI3, con la corrección que casi nunca se hace. Se probaron nueve señales y se eligió la
mejor, así que la vara es el máximo de los nueve nulos por permutación. Sólo `cardinalidad ×
término literal` la cruza, con 0,309 y `p` corregido `< 0,001`.

PI2. `var(γ)` grande no es premio grande. El premio es `E[max_p u] − max_p E[u]`, y γ puede ser
enorme porque los brazos malos son malos en lugares distintos. Restringido a los tres que
competirían, los que están a menos de 0,05 del mejor fijo:

```
oráculo entre contendientes  0,932
mejor fijo                   0,875
premio máximo               +0,058
piso de ruido               +0,065
premio NETO                 −0,008
```

> El piso de ruido, del que depende todo veredicto negativo de este paper. Un oráculo toma un
> máximo sobre estimaciones ruidosas, y `E[max_p û_p] > max_p E[u_p]` incluso cuando todos los
> paradigmas son idénticos. Es la maldición del optimizador [Smith y Winkler, 2006]; lo propio
> es el estimador. Las `k` réplicas del mismo paradigma se tratan como `k` paradigmas distintos
> y se calcula la brecha sobre ellas. Cada punto es ruido por construcción. Y ese piso no
> decrece con más tareas. No es el error de una media. Crece con la dispersión del plantel.

Y ninguna señal separa a los tres contendientes entre sí, `p > 0,29`. Tienen las mismas
capacidades (§5.3). En la figura del espacio de capacidades caen en el mismo punto, y son el
mismo brazo para decidir. La clave de la política hereda la varianza del sensor. De los cinco
ejes del vocabulario de región, el único `ELICITED` cambia de valor en el 27% de las tareas
según qué modelo las sensó. De ahí la exigencia de que las condiciones sean `COMPUTED`.

Fuera de muestra, mundo con semilla nueva por el mismo camino de código, 26 tareas × 12
paradigmas × 3 réplicas, 48,5M tokens:

```
                     base+w4      + w16      + w48
mejor fijo             0,833      0,813     0,802
brecha observada      +0,139     +0,168    +0,128
piso de ruido (p95)   +0,167     +0,187    +0,162
brecha NETA           −0,028     −0,019    −0,034
```

Negativa en los tres estratos, y sin ganador estable. Los dos primeros quedan a 0,025 contra un
piso de 0,162. El mejor fijo no cambia entre corpus. No hay uno.

## 5.7 PI4. El acuerdo entre paradigmas es una curva de calibración

```
k brazos coinciden    celdas    P(la respuesta es correcta)
        0                208               0,424
        1                 36               0,389
        2                 24               0,600
        3                 64               0,812
       ≥ 4               180               1,000
```

180 de 180 con `k ≥ 4`, igualdad exacta de la cadena normalizada. Cota inferior de Wilson al 95%,
0,980. Tres controles. En las mismas 27 tareas, los brazos fuera del consenso sacan 0,100 contra
1,000, así que discrimina dentro de la tarea. Aguanta en las cuatro cardinalidades. Y no
abarata. Las 56 cascadas probadas suben el costo. Replicado sobre una segunda familia de modelo
contra un criterio registrado antes de correr: 1,000 con `k ≥ 3` sobre 115 celdas, 374 filas
contra 3.519. El umbral es del modelo. El fenómeno no.

Qué autoriza y qué no. Mueve credencia, nunca procedencia. Cuatro paradigmas de acuerdo siguen
siendo el modelo hablando, y nada asciende a `OBSERVED` por votar. La tabla es la curva de
calibración que la superficie de credencia de §3 pedía, y su lugar es el dial, como regla de
abstención. Dice cuándo no hace falta verificar.

---

# 6. Amenazas a la validez

§4 no depende del corpus. La Proposición 1 y el Teorema 1 se comprueban sobre distribuciones
sintéticas de respuesta conocida, 573 aserciones chequeadas por máquina. Lo que sigue toca §5.

Interna. El régimen en-ventana es casi tautológico donde el corpus mide 16k tokens. El fuera de
ventana está medido a 483k con `repeat = 3`. Hasta 1,27M sólo por factibilidad. Hay un
confundente de PI1 que este montaje no separa. La varianza a `t = 0` puede venir de la
ramificación delegada o del no-determinismo del stack de servicio, y separarlo exige un servidor
de un solo request por lote. La Proposición 1 no depende de cuál domine. Y hay dos modelos en el
paper: la campaña y el held-out sobre `gpt-5.6-luna`, los episodios de §5.4 y el recall de §5.5
sobre `gpt-5.4-nano`. Ninguna estadística los mezcla. Cruza la inferencia cualitativa, que a la
clave le faltaba un eje y que la decisión se reproduce. No cruzan las magnitudes de esas dos
secciones. Repetir los tres episodios sobre `luna` cerraría esa costura y no está hecho.

Externa. El corpus es sintético con ground truth re-derivado independientemente, y la
distribución de tareas reales sobre sus diales es desconocida. La ontología separa a los brazos
sobre la etiqueta de diseño, que no se conoce al decidir. Recuperarla desde el request está sin
medir (§5.3). El leave-one-arm-out tiene ocho puntos. Y una rama de la propia teoría no se pudo
ejercitar. Un benchmark que corrige por coincidencia exacta tiene un detector barato en cada
tarea por construcción, así que la cascada precede a la selección. El tercer episodio de §5.4 es
el primer corpus donde la selección pudo disparar, y no disparó por falta de evidencia con
procedencia, no por falta de señal.

De constructo. El ciclo de §5.4 lo ejecutaron personas, y es la amenaza más importante del
paper. Lo que se midió es un ciclo de desarrollo dirigido por refutaciones preregistradas. El
sistema hace solo lo de abajo del lazo, consumir el sensor, reajustar la política con guarda,
reproducir la decisión. No hace solo lo de arriba, proponer el eje. Quien lea «plasticidad»
como que el sistema descubrió qué sensar lee algo que el registro no sostiene. Lo que sostiene
es que cada reparación conservó la garantía y quedó auditada, y que el paso que falta tiene un
lugar en el diseño, la etapa de abstracción de §3. La superficie de acciones es arquitectura
declarada y no está ejercitada. Las doce herramientas son internas al proceso, y la compuerta
que existe para lo irreversible nunca tuvo un acto irreversible que filtrar. §4 se afirma para
agentes en general y está verificado como tal. §5 se afirma para extracción de respuesta exacta
sobre documentos y se midió ahí.

Impacto más amplio. Cuatro cosas del otro lado de la norma que §1.1 invoca. Un sistema que se
abstiene traslada la decisión a una persona cuando la evidencia no alcanza, y su modo de falla
es un registro impecable que se calló en las preguntas que importaban; por eso la curva
riesgo-cobertura se reporta con la utilidad. Un piso de garantía que sube solo, aun con guarda
y artefacto firmado, es una decisión de gobierno que nadie tomó; el diseño la hace legible, y
falta quien tenga la obligación de leerla. Si la ontología se recupera con un clasificador
elicitado, un error puede mandar una pregunta de acción irreversible por el camino de una
consulta; por eso las banderas de riesgo las declara el caller y la Proposición 2 exige que lo
que gobierna sea `COMPUTED`. Y un valor superado encontrado en un documento real, con
procedencia correcta, sale con una credencial que una respuesta sin procedencia no tiene; el
Teorema de soundness lo deja pasar porque es sound y falso, y eso obliga a que la vigencia sea
un eje de la clave.

Reproducibilidad. Una semilla sola no fija un corpus. Los manifiestos estampan versión de
generador, analizador léxico y superficie de herramientas, y el cargador levanta si un archivo
las mezcla.

---

# 7. Conclusión

Una sola máquina que aprende con los pesos del sensor congelados, y cuatro cosas medidas sobre
ella. La máquina dice dónde puede aparecer la varianza y qué cuesta gobernarla. La interfaz
aprendible dice sobre qué se aprende. Capacidades del brazo y ejes de la pregunta, nunca
nombres. El ciclo dice cómo se reparó el vocabulario. Cada refutación preregistrada produjo un
sensor `COMPUTED`, agregado por personas y consumido por el sistema, sobre tres mundos, con la
decisión reproducida en todos. Y lo que compra dice qué paga. 42% de costo a utilidad
indistinguible, el recall que el paradigma decide seis veces más que la tarea, el releído que
cae con una herramienta a la vista.

Lo que las une es la condición que el registro midió y el ciclo respetó. Una clave de política
tiene que ser `COMPUTED`. Determinismo y aprendizaje no compiten. El primero define sobre qué
puede aprender el segundo. Y el piso de ruido, la corrección por selección y la partición por
tarea son lo que separa aprender del registro de confabular sobre él.

El ruteo por identidad de paradigma no tiene premio de calidad, y compra calidad sólo con el
costo a cero, porque los brazos que competirían tienen las mismas capacidades. Ese resultado no
cierra el ruteo. Cierra la pregunta mal formulada.

Lo que sigue, en orden. Construir el brazo que el catálogo predice (cobertura garantizada más
abstención sin prueba) y correrlo en las celdas de ausencia. Un paradigma diseñado desde la tabla
y medido después, que además sube el `n` que el leave-one-arm-out necesita. Medir si un
clasificador recupera los ejes de la ontología desde un request real. La celda de vigencia,
treinta y dos tareas sobre las enmiendas que el corpus ya tiene y ninguna pregunta interroga. Que
las exigencias admitan rutas alternativas aprendidas del registro, que es, literalmente,
extraer el motivo del comportamiento. Que el sistema proponga el eje: darle a la etapa de
abstracción el registro del primer episodio y medir si propone sola una partición equivalente a
la continuidad; eso convertiría el ciclo en plasticidad del sistema. Y repetir los tres
episodios sobre el modelo de la campaña, unos 40M tokens, para cerrar la única costura de modelo
que el paper tiene.

Una corrección gratis para cómo se evalúan agentes. Un banco que reporta `pass@1` sin `pass^k`
no distingue un sistema que acierta de uno con el que se puede contar, y la diferencia llega a
0,196 en este registro. Uno que reporta varianza de interacción como evidencia de que rutear
conviene mide la estructura equivocada. Y uno que lee sus doce brazos como un torneo tira lo
único que el registro tenía para enseñar.

---

# Referencias

Los trabajos se identifican por su identificador persistente. Los marcados con ★ se leyeron
completos en la fecha indicada. De los demás se verificó lo que este paper les atribuye.

★ Jaime y Errecalde (2026). MINERVA/HADD. *A Production Architecture for Hybrid Agents with
Deterministic Decisions in Regulated Domains.* Zenodo 10.5281/zenodo.20003407 (leído
2026-08-26). Antecedente de vocabulario. Arquitectura declarada, sin medición. Su compuerta
companion (EVR, Zenodo 19791686) no está disponible públicamente al 2026-09-01.

★ Select-then-Solve. arXiv:2604.06753 (leído 2026-08-26). Selección de paradigma por tarea sobre
seis paradigmas, cuatro modelos frontera y diez benchmarks.

SCL / Soft Symbolic Control. *Structured Cognitive Loop.* arXiv:2511.17673. Gobernanza
determinista sobre inferencia probabilística, en un modo global único.

Meta-ruteo composicional. arXiv:2608.00106. Ruteador interpretable offline sobre features
textuales. Confidence gate declarado como trabajo futuro.

FrugalGPT. Chen, Zaharia y Zou (2023). arXiv:2305.05176. Hybrid LLM. Ding et al. (2024).
arXiv:2404.14618. RouterBench. Hu et al. (2024). arXiv:2403.12031. RouteLLM. Ong et al. (2024).
arXiv:2406.18665. Cascadas y ruteo entre modelos; citados por sus afirmaciones de portada.

Self-Consistency. Wang et al. (2022). arXiv:2203.11171. Universal Self-Consistency. Chen et al.
(2023). arXiv:2311.17311. Antecedentes directos de §5.7.

DSPy. Khattab et al. (2023). arXiv:2310.03714. El modelo como módulo de un programa cuyo control
es del programador.

Kautz (2022). *The Third AI Summer.* AI Magazine 43(1). Taxonomía neurosimbólica.

Smith y Winkler (2006). *The Optimizer's Curse.* Management Science 52(3). El sesgo del máximo
que el piso de ruido descuenta.

Agent2Agent. Protocolo de tarjetas de agente (Google, 2025). Vecino de ingeniería de §5.3.

EnvProbe. *Ask the World Before Acting: Budgeted Environment Probing for World-Model
Calibration.* arXiv:2606.31422.

Kintsugi. *Learning Policies by Repairing Executable Knowledge Bases.* arXiv:2605.09487.
Establece el paso de instalación filtrada por verificador.

ProvenanceGuard. *Safeguarding LLM Agents from Misalignment through Provenance Analysis.*
arXiv:2607.01236.

Survey. *From Agent Traces to Trust: A Survey of Evidence Tracing and Execution Provenance in
LLM Agents.* arXiv:2606.04990.

tau2-bench. Sierra, 2025. `github.com/sierra-research/tau2-bench`. Origen de `pass^k`.

El linaje clásico de la Tabla 1. Alchourrón, Gärdenfors y Makinson (1985), *On the logic of
theory change*. Doyle (1979), *A truth maintenance system*. De Kleer (1986), *An
assumption-based TMS*. Buneman, Khanna y Tan (2001), *Why and where: a characterization of data
provenance*. Green, Karvounarakis y Tannen (2007), *Provenance semirings*. Rao y Georgeff (1995),
*BDI agents: from theory to practice*. Laird, Newell y Rosenbloom (1987), *SOAR: an architecture
for general intelligence*. Hebb (1949), *The Organization of Behavior*. Chow (1970), *On optimum
recognition error and reject tradeoff*. Dung (1995), *On the acceptability of arguments and its
fundamental role in nonmonotonic reasoning, logic programming and n-person games*.

Marco normativo. Reglamento (UE) 2024/1689 de Inteligencia Artificial, arts. 12 y 14. Reglamento
(UE) 2016/679 (RGPD), art. 22.
