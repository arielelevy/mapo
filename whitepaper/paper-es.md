# Hardness Over Hope: Policy-as-Code and Deterministic Governance in LLM Agent Orchestration

## Confinamiento de varianza en agentes LLM mediante un plano de control determinista y plástico

Borrador 3.0 (v2 de la tesis), 2026-09-01
Autor: Ariel Edgardo Levy
Estado: borrador de trabajo. Los dos teoremas están verificados por máquina; toda
afirmación empírica lleva su tamaño de muestra y su piso de ruido, y §1.3 declara el alcance.
Destino: arXiv cs.LG (primario), cs.AI (cross-list).

> Ésta es la única versión mantenida. La redacción inglesa quedó congelada en
> `historico/paper-en-congelado.md`, anterior a este borrador y superada por él. El borrador
> 2.0 quedó en `historico/paper-es-borrador-2.0-2026-08-31.md`.
>
> Qué cambió en v2. El título y la máquina son los mismos. Cambia qué se pone como
> columna vertebral: el banco deja de leerse como torneo entre paradigmas y pasa a leerse
> como fuente de episodios para un sistema que aprende. Lo que se aprende no es cuál
> paradigma gana (los que comparten capacidades empatan, y §7.3 mide que ese premio es
> cero). Es qué exige un request, qué puede hacer cada brazo, y qué predice su
> comportamiento. Los resultados negativos del borrador anterior siguen todos, con sus
> números, pero reubicados como lo que fueron: los episodios que repararon el vocabulario
> del sistema (§7.8).
>
> Qué cambió en la revisión doctoral del 2026-09-01 (plan en `paper-es_PLAN.md`). El modelo
> de cada medición está declarado (§7.0, §7.8.0): la campaña corre con `gpt-5.6-luna` y los
> tres episodios de §7.8 con `gpt-5.4-nano`. Las dos tablas del plantel se reconciliaron
> contra el registro. La agencia de la contribución 3 se corrigió: el ciclo lo ejecutaron
> personas dirigidas por refutaciones preregistradas, y el sistema consume lo que el ciclo
> produjo. Entraron la Proposición 5.7 (clave de la política), las definiciones de capacidad
> (§7.4.0), el régimen de los episodios, el impacto amplio (§8.5) y siete líneas de
> literatura que faltaban.

---

## Resumen

Un arnés de agentes es la estructura de control que envuelve a un LLM y decide qué llamada
viene después: un bucle de razonamiento, una descomposición en sub-tareas, un grafo de
verificar-replanificar. La práctica moderna de arneses arrastra una deficiencia de diseño:
hereda las propiedades probabilísticas del componente que envuelve. El arnés está hecho de
llamadas al modelo, así que toda propiedad que se le quiera exigir al sistema
(reproducibilidad, trazabilidad, cobertura) queda condicionada a la salida de algo que no la
tiene.

El caso más claro son las guardas. Un verificador de alucinación implementado como otra llamada
al modelo padece exactamente la deficiencia que vino a corregir: verificar con el mismo
material del que se desconfía no produce una garantía, produce una segunda estimación
correlacionada con la primera. La forma general, y es la premisa de este trabajo:

> Apilar instancias del componente puede subir una probabilidad; no puede producir una
> propiedad. §7.5 mide las dos mitades de esa frase: el acuerdo entre paradigmas predice la
> corrección con precisión total a partir de cuatro coincidencias (eso es la probabilidad) y aun
> así no habilita una acción irreversible, porque mueve credencia y nunca procedencia.

Así que la garantía tiene que venir de un componente de otra clase. Interponemos entre el
modelo y el flujo un motor determinista y plástico que decide sobre creencias tipadas, y le
dejamos al modelo un solo papel: se le pregunta qué dice el material y lo que devuelve se tipa
como proposiciones («esta cuenta figura a nombre de X») que entran a una base de creencias, cada
una con la unidad de la que salió. De ahí que se lo llame sensor, y estocástico porque la
misma pregunta sobre el mismo material puede devolver otra cosa. El motor separa dos funciones
que la práctica corriente colapsa:

```
    decisión  = f(creencias)          f determinista, tipada, auditable
    creencias = g(mundo, sensor)      g estocástica
```

La garantía que eso compra tiene una forma precisa: misma base de creencias ⟹ misma
decisión. Es una propiedad de la decisión, se verifica repitiéndola, y se exhibe junto con la
creencia que la disparó. Y `f` es determinista dentro de un request y plástica entre
requests: lo que aprende son políticas, que consolidan offline con guarda anti-regresión en
un artefacto firmado y se ejecutan como código (§6.3). El sensor tiene los pesos congelados;
el que aprende es el sistema, porque la base de creencias acumula el registro de sus propias
decisiones y de ahí se destila la política. Las reglas escritas a mano dan
determinismo; un andamiaje entrenado extremo a extremo da aprendizaje. El motor da los dos a
la vez, y ahí está la novedad: las garantías del sistema vienen del envoltorio y no de lo
envuelto.

Y lo que aprende no es cuál paradigma gana. El banco que sostiene este trabajo corre doce
paradigmas sobre las mismas tareas, y la lectura obvia (un torneo, con un ganador por tarea)
es la que este registro refuta: los brazos que comparten capacidades empatan, y el premio de
elegir entre ellos por calidad es cero neto (§7.3). El banco se lee de otra forma: es la
fuente de episodios de la que el sistema extrae qué exige un request, qué puede hacer
cada brazo, y qué predice su comportamiento. Los paradigmas no compiten; son un repertorio
de capacidades, y la política aprende sobre las capacidades y no sobre los nombres.

Sobre un corpus de análisis forense de hechos, con doce paradigmas medidos bajo condiciones
idénticas y sin juez LLM (campaña con `gpt-5.6-luna`; los tres episodios de §7.8 con
`gpt-5.4-nano`, y §7.8.0 declara qué transfiere entre los dos), contribuimos:

1. La máquina, con su costo medido. Sensor estocástico, creencia tipada con procedencia,
   regla determinista, registro. Un agente confina su varianza cuando ninguna ramificación de
   su trayectoria depende del sensor; la Proposición 5.4 prueba que entonces toda discrepancia
   entre réplicas tiene un nodo responsable. Empíricamente: entre el 17% y el 34% de las
   celdas devuelven resultados distintos a temperatura cero con semilla fija, y absorber
   ramificaciones en el motor lleva un paradigma de `0,33` a `0,89` haciendo coincidir sus
   réplicas (§5.0, §7.2). El dial de garantía es gratis hasta A2 y en A3 se lleva el 60% del
   catálogo y el 31% de la utilidad (§5.4).
2. La interfaz aprendible: capacidades declaradas desde el código y ontología de la
   pregunta. Un paradigma es un paquete de capacidades auditables contra su propio código,
   y la pregunta exige capacidades, no nombres. Declaradas así, predicen un paradigma nunca
   visto mejor que la identidad del paradigma, incluso cuando a ésta se le permite ver la
   respuesta, sobre ocho brazos y sin cruzar su nulo de capacidades barajadas (`p = 0,065`):
   un resultado sugestivo que más brazos sentencian. El catálogo encuentra un hueco sin correr
   nada, ningún brazo junta cobertura garantizada con abstención por prueba faltante, y eso
   queda como predicción registrada hasta que ese brazo se construya. La ontología de la
   pregunta separa a los brazos 40% más por segmento que la partición estructural, medido
   sobre la etiqueta de diseño (§7.4).
3. El ciclo que repara su propio vocabulario. Tres refutaciones preregistradas sobre tres
   mundos que la política nunca vio, cada una con su decisión reproducida 26 de 26, y cada
   una produjo un sensor nuevo, computado y sin modelo: el eje de horizonte, el de literal, la
   ontología. Quién lo ejecutó hay que decirlo: el ciclo lo corrieron personas, leyendo cada
   refutación y agregando el eje; el sistema consume los sensores que el ciclo produjo, y la
   automatización del paso está diseñada en §6.3 y no medida. Lo que el ciclo establece es
   el método y su condición: cada sensor nuevo es `COMPUTED`, y la reproducibilidad no se
   perdió en ningún paso. El estimador de piso de ruido que separa señal de sesgo del máximo
   es la disciplina que impide que aprender del registro sea confabular sobre él (§7.3, §7.8).
4. Lo que la política aprende, y qué compra. Entre brazos capaces, el desempate por costo
   paga fuera de muestra: 42% de ahorro a −0,017 con una sola señal sobre el panel de 59 × 8,
   y 46% a +0,021 con la política entera sobre 41 × 7 (§7.3.5); la regla de índice por
   clase de consulta lleva una celda de `0,33` a `0,89`; el acuerdo entre paradigmas es una
   curva de calibración de credencia que se reproduce sobre una segunda familia de modelo. Y
   los predictores del comportamiento que el registro entrega: el paradigma determina el
   recall de evidencia seis veces más que la tarea, y ofrecer una herramienta cambia la
   conducta del agente aunque no la use (§7.5, §7.9).

Lo que une las cuatro es una condición, y §7.3.6 la mide: una clave de política tiene que
ser `COMPUTED`. Un eje elicitado describe lo que el modelo cree sobre la tarea, y usarlo para
indexar convierte la tabla de decisión en una variable aleatoria. Sólo se puede aprender sobre
lo que se puede sensar sin el modelo, y por eso determinismo y aprendizaje no compiten: el
primero es la condición del segundo.

Ninguna pieza del motor es nueva: §2.9 tabula las ocho líneas de las que sale y qué supone
cada una sobre su fuente de creencias que un LLM viola. Ahí está el aporte, sostener esa
disciplina cuando la fuente inventa con forma correcta, y aprender sobre ella sin dejar de
sostenerla.

Palabras clave: confinamiento de varianza, agentes LLM, plano de control, procedencia,
predicción selectiva, aprendizaje plástico, capacidades, reproducibilidad, trazabilidad

![El contrato de garantía, y qué pasa cuando la evidencia no alcanza](figuras/contrato-de-garantia.svg)

**Figura 1.** El request entra por la izquierda y sale por la derecha, y los cuatro pasos del
riel no gastan un token hasta el último. Dos cosas que el resto del paper desarrolla en prosa
están acá dibujadas: la rama de rechazo (cuando ninguna procedencia alcanza el piso exigido, abstenerse es una salida y no un fallo) y el lazo, que es la plasticidad: el registro de
rechazos sube el piso del próximo request, offline y con guarda anti-regresión, sin que nadie
toque un peso. La flecha punteada que sube del carril de abajo es la única que cruza la
frontera, y lleva proposiciones tipadas: nunca control de flujo.


## Cómo se decide un request

![El método determinista: qué decide el código y qué emite el modelo](figuras/metodo-determinista.svg)

La figura es el argumento del paper en una imagen. El carril de arriba es determinista y
auditable: sensores de forma cerrada, creencias tipadas con procedencia, un compuerta aritmética,
las capacidades que la pregunta exige, y recién ahí una elección entre los brazos capaces (o una abstención). El carril de abajo es el modelo, y sólo emite proposiciones: qué dice una
unidad, hacia dónde sigue un rastro. Nunca decide cuántas vueltas dar, qué índice usar ni
cuándo parar.

Toda decisión que cruza al carril de abajo se lleva el determinismo con ella, y eso está
medido, no argumentado. La guarda que cierra el ciclo (tipar la salida del sensor antes de usarla) es del 2026-08-30 y salió de un caso concreto: el modelo emitía
`'M. Arrieta settlement account'` y esa cola arrastraba la consulta a clasificarse como prosa,
mandándola al índice equivocado. La regla era correcta y la entrada estaba sucia.

| lo que decide el código | lo que emite el modelo |
|---|---|
| cuántas vueltas dar (del largo declarado en la pregunta) | qué dice esta unidad |
| qué índice usar (léxico para entidad nombrada, híbrido para prosa) | hacia dónde sigue el rastro |
| qué unidad es el ancla, y cuál el término de la cadena | qué hecho aporta lo leído |
| si hay evidencia suficiente para responder, o si hay que abstenerse | la redacción de la respuesta |


# 1. Introducción

## 1.1 Tres propiedades que un sistema de producción exige

Un *arnés* de agentes es la estructura de control que envuelve al modelo: una llamada única, un
bucle de razonamiento, una descomposición, un grafo de verificar-replanificar. Se elige una vez
en tiempo de diseño y se congela en el código, y sobre él se construyen sistemas que firman
números, disparan acciones y contestan a usuarios. Cualquier otra capa de un sistema de
producción da tres propiedades por sentadas, y en un agente hay que construirlas.

1. El flujo de control vive en el código. El modelo es aleatorio y va a seguir siéndolo; lo
que un arnés decide es cuánto del sistema depende de esa aleatoriedad. Delegarle
ramificaciones (qué buscar después, cuántas vueltas dar, cuándo parar) vuelve aleatoria la
trayectoria misma. Es una decisión de arquitectura, y su precio está medido: entre el 17% y el
34% de las celdas cambian de resultado entre réplicas a temperatura cero con la misma huella
(§7.2.2).

2. Cada valor emitido exhibe de dónde salió. Una respuesta correcta y una inventada llegan
con la misma cara, así que la fuente tiene que viajar con el valor. Con una base de creencias
tipada se puede exigir que un número esté implicado por evidencia de cierto nivel; el sustituto
es la confianza en que «el modelo suele acertar».

3. El sistema puede callarse. En la celda más difícil del corpus, el paradigma que gana lo
hace con 12 correctas, 3 abstenciones y cero respuestas equivocadas; los demás contestan
siempre y devuelven un número plausible y falso (§7.2.3). El banco puntúa las dos con `0,000`,
que es correcto para medir utilidad y ciego justo sobre el eje que producción necesita.

La tesis es que las tres se consiguen en el mismo lugar: moviendo decisiones de flujo de
control desde el modelo hacia el código, sobre señales del entorno que son contables y
verificables. Este trabajo las construye, las mide y dice qué cuestan.

### 1.1.1 La instrucción llega hasta la probabilidad, y una norma pide una propiedad

Hasta ahora el comportamiento determinista se buscó instruyendo al modelo: «citá siempre»,
«si no sabés, decilo», «no inventes números». Los modelos siguen instrucciones cada vez mejor y
cada generación se acerca más. Pero una instrucción es un prior sobre la distribución de
salidas, no una restricción sobre la muestra: seguirla mejor sube la probabilidad, y el límite
de esa sucesión queda del lado abierto.

En un chat la brecha da igual. Una norma pide otra cosa: el Reglamento de IA de la Unión Europea
exige trazabilidad y supervisión humana sobre sistemas de alto riesgo; el artículo 22 del RGPD
condiciona las decisiones automatizadas sobre personas; una auditoría exige exhibir por qué
se afirmó algo. Los tres piden una propiedad del sistema, y eso se consigue con una
restricción, no con un pedido. Este trabajo reemplaza la instrucción por una restricción fuera
del modelo.

### 1.1.2 Una expectativa de la literatura, y qué mide de verdad

La motivación habitual para trabajar sobre arneses es que elegir el paradigma por tarea
paga: la selección oráculo por tarea supera al mejor paradigma fijo por 17,1pp sobre seis
paradigmas, cuatro modelos frontera y diez benchmarks [Select-then-Solve, arXiv:2604.06753]. El
mismo trabajo mide que el premio no se cobra (un ruteador sobre embeddings recupera un cuarto de la brecha, el auto-ruteo zero-shot recupera valor *negativo*), lo que invita a concluir que
hacen falta mejores selectores.

Este registro dice otra cosa, y es lo que reordenó el programa. El premio neto del
ruteo por calidad es `−0,008` contra el mejor fijo, y §7.3 da el mecanismo: la interacción
tarea×paradigma existe y es enorme (48% de la varianza) pero vive entre los paradigmas que
nadie elegiría, y restringida a los que competirían se desvanece. Y la razón por la que se
desvanece es la que §7.4 nombra: los tres contendientes tienen las mismas capacidades, y
por eso son el mismo brazo para decidir. Elegir por nombre entre brazos que hacen lo mismo no
tiene premio porque no hay nada que elegir.

Eso no dice que rutear sea inútil. Dice que la pregunta estaba mal formulada: los
paradigmas no son competidores comparables sobre un eje de calidad, son paquetes distintos de
capacidades, y el premio aparece sobre los ejes donde las capacidades difieren (costo, cobertura, abstención) y no sobre el que comparten. §7.3.5 mide el primero, con dos paneles
declarados: 42% de ahorro con una señal suelta y 46% con la política entera, los dos a
utilidad indistinguible del mejor fijo y fuera de muestra. El banco no existe para coronar un
paradigma; existe para que el sistema aprenda qué exige cada request y qué le puede dar cada
brazo.

## 1.2 Cuatro afirmaciones que preceden al problema de aprendizaje

El banco es fuente de episodios, no torneo. Un banco que corre doce paradigmas sobre las
mismas tareas produce dos cosas: un ranking, y un registro de qué hizo cada brazo sobre cada
pregunta. El ranking es lo que se lee primero y lo que menos vale: sobre calidad los brazos
capaces empatan (§7.3) y el mejor fijo cambia de mundo a mundo (§7.7.2). El registro es lo que
alimenta al sistema, y lo que se extrae de él es el motivo del comportamiento, no un
ganador. Qué capacidad faltaba donde un brazo falló, qué eje de la pregunta separaba
dos celdas que la región confundía, qué señal contable predice que una trayectoria se va a
desbocar. Todo lo que este paper llama aprendizaje es eso, y por eso una refutación es un
episodio y no un fracaso (§7.8).

La factibilidad es aritmética, y es gratis. Antes de preguntar cuál topología es
*mejor*, se puede preguntar cuál puede *correr*. Esa pregunta se responde con cantidades
que la tarea ya declara. Una política aprendida que gasta episodios descubriendo que
map-reduce pierde en tareas de 500 unidades está aprendiendo aritmética por el camino
difícil; el tope era computable antes del primer token.

La selección paga sólo bajo una condición precisa. Un ruteador que debe elegir siempre
no tiene ningún grado de libertad sobre su tasa de falsos positivos y por lo tanto paga
cada error de ruteo. Formalizamos cuándo la selección le gana a un fallback fijo y
mostramos que el punto de operación óptimo generalmente implica abstenerse en la mayoría
de las solicitudes. Eso es un objetivo distinto, no un ruteador más débil.

Mucho de lo que se le atribuye a la topología es atribuible a la superficie. Entre el
paradigma más caro y el más barato del plantel hay un factor 11× de costo y `0,17` de
utilidad: en calidad se separan por centésimas y en lo que cuestan, por órdenes de magnitud
(§7.1). Y lo que gobierna esa diferencia es cuánto material arrastra cada uno al prompt, no
la estructura de control. El costo es de 98,6% a 100,0% de entrada en todos ellos. Un
benchmark que no reporta la calidad de su superficie de herramientas no está comparando
topologías: está comparando un retriever envuelto de doce maneras.

## 1.3 Alcance de las afirmaciones

Establecido: la teoría (§5), verificada por máquina contra distribuciones sintéticas de
respuesta conocida; una compuerta de factibilidad (§4) validada sobre cuatro escalas de corpus;
un generador de corpus cuyo ground truth se re-deriva de forma independiente a partir de
los documentos (§6).

Medido: todo §7, sobre una campaña homogénea de 78 tareas × 12 paradigmas × 3
réplicas (121,4M tokens, cero errores de infraestructura, sin juez LLM y con el corrector auditado) más un held-out corrido por el mismo camino de código y una réplica del hallazgo de
consenso sobre una segunda familia de modelo. Cada panel declara su rectángulo y cada
comparación su piso de ruido. Los tres episodios del ciclo (§7.8) son anteriores a la campaña
y corrieron sobre otro modelo, `gpt-5.4-nano`; §7.8.0 declara qué de ellos transfiere a la
campaña y qué no.

### 1.3.1 El dominio

Lo que se evalúa es capacidad de RAG sobre análisis forense de hechos: un sistema que
recibe preguntas del tipo que hace un auditor, un analista de cumplimiento o un investigador
sobre un conjunto documental. Qué cuenta figura a nombre de quién, quién le reporta a quién
subiendo N escalones, si existe registro de una transferencia, si una designación sigue
vigente, si alguien debía escalar y no lo hizo.

El corpus es heterogéneo por construcción, y sus once modos son los modos de falla de ese
dominio, no una muestra de dificultad: hecho único verificable, enumeración independiente,
cadena acoplada, agregación con cobertura exhaustiva, horizonte desconocido, acción
irreversible, vigencia, plantel declarado, ausencia, presuposición falsa y escritura
compartida. Ausencia y presuposición falsa son las dos que un benchmark de extracción no suele
tener y las que un sistema forense necesita: la respuesta correcta es que el hecho no está, o que la
pregunta da por cierto algo que es falso.

Sobre eso se apilan tres anchos (5, 20 y 60 unidades) y entidades con variantes de superficie,
anáfora y señuelos: el 36,5% de las menciones son invisibles a una búsqueda del nombre
completo y el 100% de los saltos de cadena exige resolver una variante.

La maquinaria no depende del dominio. Sensor estocástico, motor determinista, procedencia
tipada, compuerta aritmética y abstención son propiedades de cómo se decide, no de qué se
pregunta; §6 las instancia sobre otras tres superficies (datos, acciones, gobierno) con el
mismo enunciado sobre otro tipo de proposición. Lo que este registro establece es que la
separación funciona y qué cuesta en un dominio; que el número transfiera a otro es una
predicción, no un resultado.

Fuera de alcance: un selector validado; ningún resultado sobre benchmarks públicos;
ninguna medición fuera del dominio descrito arriba; y un clasificador que recupere los ejes
de la ontología desde un request real. Que la ontología separe a los brazos está medido sobre
el registro (§7.4.3). Que se la pueda detectar afuera del corpus es la medición que sigue.

## 1.4 Organización del paper

§2 ubica el trabajo: los vecinos contemporáneos en selección de paradigmas, cascadas y
gobernanza simbólica, el linaje clásico con el supuesto que cada línea hace sobre su fuente
de creencias, y los mecanismos que ya están ocupados. §3 fija los preliminares: tarea,
paradigma, utilidad, ley de costo. §4 es la compuerta de factibilidad, aritmética y gratis. §5
es la teoría: el confinamiento de varianza (§5.0), el valor de seleccionar como identidad
contable (§5.1), la cascada (§5.2), la máquina (§5.3 a §5.5), su alcance (§5.6) y la clave de
la política (§5.7), que es el puente hacia lo que se aprende. §6 es el diseño: medir sin juez,
creencias con procedencia, consolidación. §7 son los resultados, ordenados por contribución:
el plantel y la varianza (§7.1, §7.2), por qué no hay premio de calidad entre brazos capaces
(§7.3), la interfaz aprendible (§7.4), el consenso (§7.5), la ventana frontera (§7.6), el
held-out (§7.7), el ciclo que repara el vocabulario (§7.8) y los predictores del
comportamiento (§7.9). §8 son las amenazas a la validez y el impacto amplio. §9 concluye y
ordena lo que sigue.

---

# 2. Trabajo relacionado

## 2.1 Búsqueda automática de workflows

AFlow reformula la optimización de workflows como búsqueda sobre workflows representados
como código, con MCTS sobre operadores [arXiv:2410.10762]; ADAS y GPTSwarm buscan en
espacios afines. Estos producen un workflow por benchmark, offline. Nuestro interés es
la selección por solicitud dentro de un conjunto fijo y, antes de eso, qué miembros del
conjunto pueden correr siquiera.

## 2.2 Selección de paradigma en tiempo de inferencia

Select-then-Solve entrena un ruteador liviano sobre embeddings para elegir un paradigma por
tarea [arXiv:2604.06753]. FlowBank construye un portafolio offline y selecciona por consulta
[arXiv:2606.11290]. TRACE-Router rutea a granularidad de traza de tarea y no de solicitud
[arXiv:2607.22465]. Uno-Orchestra aprende una política conjunta de descomposición y despacho
[arXiv:2605.05007].

Todos operan a cobertura uno: toda tarea recibe un paradigma. §5.1 sostiene que ésa es
la restricción vinculante, más que la capacidad del modelo, y ninguno reporta una curva de
riesgo-cobertura. Dos detalles de Select-then-Solve, verificados contra el paper completo y
no contra su abstract (2026-08-26): su oráculo es un *máximo empírico sin corregir* por
tarea, y sus propias limitaciones anotan que la muestra es fija, sin re-muestreo entre
seeds, exactamente el sesgo hacia arriba que el protocolo de piso de ruido (§6.1)
existe para descontar. Y la maquinaria de deferral existe al lado, sin haber cruzado:
ReDAct difiere decisiones individuales a un modelo más grande sobre un umbral calibrado de
incertidumbre [arXiv:2604.07036]; el ruteo por descomposición de incertidumbre unifica
abstención y ruteo con garantías distribution-free, para clasificadores [arXiv:2605.07805];
y el meta-ruteo composicional entrena un ruteador interpretable sobre features textuales y
nombra un confidence gate con fallback a ruteo estático como trabajo futuro sin evaluar
[arXiv:2608.00106]. Nadie aplica abstención a la selección de paradigmas (buscado
2026-08-26); la ventana se está cerrando a la vista.

La cascada de §5.2 tiene una línea propia, anterior y sobre modelos en vez de paradigmas, y
hay que nombrarla. FrugalGPT encadena modelos de menor a mayor costo con un puntaje de
aceptación por escalón y reporta ahorros grandes a igual calidad [arXiv:2305.05176]; el ruteo
híbrido entrena un clasificador de dificultad para mandar la consulta al modelo chico o al
grande [arXiv:2404.14618]; RouterBench fija el banco para comparar ruteadores de modelos
[arXiv:2403.12031] y RouteLLM aprende el ruteador desde datos de preferencia [arXiv:2406.18665].
Las cuatro deciden entre modelos con el mismo control de flujo. Lo que §5.2 agrega no es la
cascada, es la partición por verificabilidad: cuándo la cascada precede a la selección porque
existe un detector barato, y la observación de que un benchmark de coincidencia exacta trae ese
detector por construcción (§8.2). Y el detector de FrugalGPT es un puntaje aprendido sobre la
respuesta, es decir, elicitado; acá el detector tiene que ser `COMPUTED` u `OBSERVED` para
disparar la cascada, por la misma razón que §7.3.6 le exige a la clave de la política.

## 2.3 Modelos de costo para workflows

GLOW predice performance de workflows agénticos a partir de features de grafo y de lenguaje
[arXiv:2512.15751]; Cost-Aware Optimization for Agentic Query Execution hace explícita la
analogía con la optimización clásica de consultas [arXiv:2606.03152]. Tomamos la analogía
como establecida y no la reclamamos. Nuestro aporte está aguas arriba: un filtro duro de
factibilidad que un modelo de costo no reemplaza, porque un plan infactible no tiene
costo.

## 2.4 Gobernanza simbólica sobre inferencia probabilística

Es la vecindad más cercana a §6.2 y hay cuatro trabajos dentro. Los dos primeros se leyeron
completos el 2026-08-26; la tabla dice qué aporta cada uno y qué de §6.2 queda afuera de su
alcance.

> Cómo leer la columna «qué no tiene». No señala defectos: enumera dónde se apoya el
> incremento. Lo mismo vale para los tres mecanismos de §2.10.

| trabajo | qué aporta | qué no tiene |
|---|---|---|
| SCL / Soft Symbolic Control [arXiv:2511.17673] | gobernanza sobre inferencia probabilística, partida en *Regulation* (metaprompt persistente, cuya efectividad el propio paper hace depender de qué tan bien el modelo interprete instrucciones) y *Control* (runtime determinista sobre el historial del turno: llamadas duplicadas, conteo de errores, profundidad de ciclos) más clasificación de riesgo por acción | opera como un modo global único: no gradúa la garantía por solicitud, no la deriva de creencias sobre la solicitud, no restringe el espacio de planes por nivel, y no calibra la confianza declarada. Sus reglas leen el historial de ejecución, no el contenido proposicional |
| MINERVA / HADD, Jaime y Errecalde (2026) [Zenodo 10.5281/zenodo.20003407] | el antecedente de vocabulario más cercano: una arquitectura declarada donde el LLM queda confinado a sensor tipado, la cognición es determinista sobre la base de creencias («mismo estado → misma acción») y hay una compuerta de admisión en la frontera de percepción, con el encuadre neurosimbólico de Kautz (Tipo 2, simbólico que envuelve a lo neuronal) [Kautz, 2022]. Se lo acredita por las tres palabras que se comparten | es un documento de arquitectura, no de medición: sus invariantes se declaran y su única validación enunciada es «validado en producción con documentos reales de sectores regulados», sin corpus, sin réplica ni número. Nada en él tiene un costo medido, y nada en él aprende: la garantía es uniforme, los planes se acotan globalmente, la confianza se ajusta y no se mide. Su compuerta companion (EVR, Zenodo 19791686) no está disponible públicamente (verificado el 2026-09-01 por tres rutas: el registro devuelve *Gone*), así que no se cita como mecanismo. Procedencia con semántica de admisibilidad, garantía por solicitud, selección, abstención, deferral y toda la plasticidad de §6.3 quedan fuera de su alcance |
| Motores de creencias: Nous [arXiv:2606.22030], MemIR [arXiv:2605.25869], Eywa [arXiv:2605.30771], HEP [arXiv:2607.09195] | acotar la confiabilidad por procedencia del canal; tipar la memoria para impedir colapso de fuentes; promover hechos sólo tras validadores contra evidencia inmutable; hacer auditable la evolución de hipótesis | en HEP toda evidencia validada mueve la creencia por igual, sin jerarquía que filtre la promoción. El jardín de senderos que se bifurcan (agentes que proponen y puntúan sobre los mismos datos) está diagnosticado empíricamente [arXiv:2607.01507] sin mecanismo; la partición proponer/puntuar de §6.3 es uno |
| Contratos de delegación e identidad atestiguada [arXiv:2603.18043] | el vecino más cercano del lado del ruteo, y empírico: rutear sobre calidad auto-reportada selecciona a los peores delegados y rinde peor que al azar (`0,55` contra `0,68`). Su remedio es determinista (contratos que acotan autoridad con objetivos, presupuestos y políticas de falla) más identidad reclamada contra atestiguada, y el brazo atestiguado llega a ruteo casi óptimo | su procedencia es una propiedad del reclamo de calidad de un delegado; el de este trabajo es un orden sobre tipos de evidencia, y ese orden es lo que una regla lee. No reportan retículo, ni piso sobre acciones irreversibles, ni curva riesgo-cobertura: miden exactitud de ruteo |

Dos observaciones que salen de la tabla. La primera corrobora la disciplina del sensor desde
una dirección adversarial: la razón de este trabajo para rechazar la auto-evaluación es epistémica (una afirmación sobre su propia suficiencia no supera `ELICITED`) y la de los contratos es que un
delegado tiene incentivo a inflar; las dos llegan a la misma prohibición, y
`reclamada`/`atestiguada` es `ELICITED`/`OBSERVED` restringido a una proposición.

La segunda achica lo que se puede afirmar: «procedencia + ruteo + contratos» ya está
ocupado como frase, así que la conjunción se enuncia por lo que excluye. Queda sin
antecedente el conjunto de: un retículo de procedencia sobre evidencia, un piso que filtra acciones
irreversibles con él, la abstención tasada como curva riesgo-cobertura medida, y el mismo
cálculo sobre factibilidad, control y contenido. Cualquier término suelto tiene antecedentes.

## 2.5 Predicción selectiva y aprender a diferir

Nuestra teoría es una aplicación de un marco establecido. La regla de Chow da el rechazo
óptimo; Mozannar y Sontag dan un surrogate consistente para diferir a un experto
[PMLR v119]; Verma y Nalisnick agregan deferral one-vs-all calibrado [arXiv:2202.03673];
Mohri y colegas dan formulaciones multi-experto principiadas. Contribuimos la aplicación a
la selección de paradigmas y los corolarios específicos de §5.1, no el marco.

El consenso de §7.5 también tiene antecedente directo. Self-Consistency muestrea varias
cadenas de razonamiento del mismo modelo y vota la respuesta final [arXiv:2203.11171];
Universal Self-Consistency extiende el voto a respuestas de formato libre con el propio modelo
como agregador [arXiv:2311.17311]. §7.5 es esa idea con tres diferencias que hay que decir en
vez de esconder: los votantes son estructuras de control de flujo distintas y no muestras de
la misma, el fenómeno se replica sobre una segunda familia de modelo contra un criterio
registrado antes de correr, y el resultado del voto mueve credencia dentro de `ELICITED` y
nunca procedencia, así que no habilita una acción irreversible. La agregación por votación es
prestada; la epistemología de qué autoriza el voto es lo que se agrega.

## 2.6 Agentes que aprenden sin actualizar pesos

Los enfoques de memoria experiencial, ExpeL, aprendizaje reflexivo experiencial, MemSkill,
R²-Mem, acumulan insights, reglas o entradas de memoria. Sleep-time compute corre inferencia
en tiempo ocioso y reporta ~1/5 de los tokens en inferencia [Letta]; SCM y trabajo afín
agregan consolidación de inspiración biológica [arXiv:2604.20943, arXiv:2605.26099]. Todos
consolidan contenido. §6.3 consolida la política de control, y la afirmación
sobrevive una búsqueda fechada (2026-08-26) sólo como conjunción, así que la enunciamos
como tal: la política se aprende de los episodios propios del agente, se consolida offline,
en un artefacto determinista versionado que se ejecuta fuera del LLM, sobre features
estructurales de la tarea. Cada conjunto tiene un vecino fuerte. Trace2Policy destila
control desde trazas de *expertos* a bases de reglas que se reinyectan *como texto de
prompt* [arXiv:2606.10457]; la compilación declarativa de políticas le da a las políticas
de orquestación exactamente la forma de artefacto que queremos, determinista, auditable,
versionada, pero *escrita por humanos*, no aprendida [arXiv:2603.27299]; el meta-ruteo
composicional aprende un ruteador interpretable offline, sobre features textuales y no
estructurales [arXiv:2608.00106]. Ninguno aprende su propia política de control hacia un
artefacto así.

Y el antecedente de ingeniería de «el flujo de control vive en el código» es DSPy, que trata
al modelo como un módulo invocado desde un programa cuyo control es del programador, y
optimiza los prompts de los módulos sin tocar la estructura [arXiv:2310.03714]. La separación
es la misma que este trabajo hereda. La diferencia es qué se optimiza: DSPy ajusta el
fraseo de cada módulo contra una métrica, y este trabajo excluye el fraseo del catálogo por
control nulo (§3) y aprende sobre qué exige la pregunta y qué puede hacer cada estructura.

## 2.7 Evaluación y jueces

Deliberadamente no usamos juez LLM. Un estudio a gran escala sobre 21 modelos y 541.000
juicios reporta confiabilidad sin validez, y que el acuerdo crudo sobreestima la capacidad
discriminativa [arXiv:2606.19544]. Las métricas estilo RAGAS exhiben sesgo de posición, de
verbosidad y de auto-preferencia, y la mitigación recomendada es corridas repetidas con
inspección de dispersión. Como los tamaños de efecto medidos son de un dígito de puntos
porcentuales y la varianza del juez es del mismo orden, y como el sesgo de verbosidad
favorecería sistemáticamente a los paradigmas caros cuyo valor está justamente en cuestión,
un juez introduciría un sesgo alineado con la hipótesis. §6.1 explica la alternativa.

Sobre atribución de fallos, MemFail aísla los fallos de sistemas de memoria en modos de
resumen, almacenamiento, recuperación y razonamiento, y puede atribuir un error a uno de
ellos sólo porque las operaciones intermedias quedan registradas [arXiv:2605.26667],
convergente con el requisito de §7.2.3, aunque su atribución corre sobre un juez LLM donde la
ésta corre sobre trazas deterministas de herramientas. Su titular es también el de este trabajo
en miniatura: escalar las memorias recuperadas o la fuerza del modelo rinde poco y a veces
degrada, dependiendo de la tarea.

## 2.8 Posicionamiento

| | cobertura | decisión determinista | auditable | filtro de factibilidad | abstención | aprende sobre | clave de la política |
|---|---|---|---|---|---|---|---|
| AFlow / ADAS / GPTSwarm | offline, un workflow | no | no | no | n/c | la estructura del workflow, por benchmark | n/c |
| Select-then-Solve | 1,0 | no | no | no | no | identidad del paradigma | embedding de la tarea |
| FlowBank | 1,0 | no | no | no | no | identidad del workflow | embedding de la consulta |
| TRACE-Router | 1,0 | no | no | no | no | identidad del paradigma, por traza | features de la traza |
| FrugalGPT y cascadas de modelos | 1,0 | sí, el orden | parcial | no | no | umbral de aceptación por escalón | puntaje elicitado sobre la respuesta |
| SCL | modo global | sí | sí | no | no | no aprende | n/c |
| Este trabajo | selectiva | sí | sí | sí | sí | capacidades del brazo y ejes de la pregunta | `COMPUTED` por construcción (§5.7) |

---

## 2.9 El linaje clásico, y qué supuesto rompe un sensor estocástico

Las piezas del motor no son nuevas. Cada una viene de una línea con décadas de trabajo, y cada
línea asume algo sobre su fuente de creencias que un LLM viola. Ese es el aporte y por eso
el linaje va en esta sección y no en una nota. Lo que sigue es el catálogo de supuestos que
hubo que reemplazar, y no una lista de precursores.

| línea | qué aporta | qué asume sobre la fuente | qué rompe un LLM |
|---|---|---|---|
| Revisión de creencias, AGM (Alchourrón, Gärdenfors y Makinson, 1985) | qué se retracta cuando entra evidencia contradictoria | el postulado de éxito: la creencia entrante se acepta | una fuente que puede equivocarse vuelve inadmisible aceptar por defecto; de ahí la compuerta de admisión |
| Mantenimiento de verdad con justificaciones: Doyle (1979), ATMS de de Kleer (1986) | cada creencia exhibe la justificación que la sostiene | que la justificación existe y es recuperable | fabrica justificaciones plausibles y sintácticamente bien formadas |
| Procedencia de primera clase: Buneman, Khanna y Tan (2001); semianillos de Green, Karvounarakis y Tannen (2007) | de dónde vino un valor, separado de cuánto se le cree | que la procedencia se deriva de la operación, no se declara | no hay operación: hay una emisión, y su procedencia no está en la salida |
| Arquitectura BDI (Rao y Georgeff, 1995) | deliberación separada de ejecución | sensores que no alucinan, un sensor roto se detecta por inconsistencia | alucina consistentemente, así que la inconsistencia no lo delata |
| Políticas como datos, aprendidas offline: Soar (Laird, Newell y Rosenbloom, 1987), ACT-R | la política es un artefacto inspeccionable, no un peso | que las condiciones de las reglas son observables | las condiciones interesantes las emite el sensor, y entonces la clave de la política hereda su varianza (§7.3.6) |
| Plasticidad hebbiana (Hebb, 1949) | una asociación entre pares tiene contenido propio sobre sus marginales | que los eventos asociados son eventos, no descripciones de eventos | la traza es lo que el sensor pidió, no lo que ocurrió |
| Opción de rechazo (Chow, 1970) y predicción selectiva | cubrir menos a cambio de errar menos | que hay una puntuación de confianza calibrada | la confianza declarada por el modelo no está calibrada, y §7.5 tuvo que construir una |
| Argumentación abstracta (Dung, 1995) | una conclusión vale si su prueba sobrevive a los ataques disponibles | el marco se define sobre una relación de ataque dada; instanciarlo exige construirla | el espacio de respuestas plausibles y falsas no es construible, así que la admisión se decide por procedencia y no por supervivencia |

La lectura crítica, en una línea por columna. Las tres primeras líneas aportan la
maquinaria de creencias y las tres suponen sinceridad, existencia de justificación o
derivabilidad de procedencia, y las tres suposiciones caen a la vez cuando la fuente puede
inventar con forma correcta. BDI aporta la separación que este trabajo hereda y su detección de
sensores rotos no funciona sobre un sensor que alucina de forma consistente. Soar aporta la
política como dato y su supuesto de condiciones observables es exactamente lo que §7.3.6 mide
que falla. Chow aporta la abstención y su supuesto de confianza calibrada es el que §7.5
reemplaza por una curva medida.

Qué se hizo con cada supuesto roto. La procedencia deja de derivarse y pasa a declararse
y verificarse: un valor es admisible si el código puede exhibir de qué unidad salió, y si no
puede, no se emite (Teorema 2). La confianza deja de leerse del modelo y pasa a calibrarse
contra el registro. Y las condiciones de la política pasan a exigirse `COMPUTED`, porque una
clave elicitada convierte la tabla de decisión en una variable aleatoria (§7.3.6).

---

## 2.10 Tres mecanismos que ya están ocupados

Tres trabajos ocupan, cada uno por su lado, mecanismos que esta sección podría reclamar
(leídos completos el 2026-08-28).

| trabajo | qué ocupa |
|---|---|
| EnvProbe, *Ask the World Before Acting: Budgeted Environment Probing for World-Model Calibration* (arXiv 2606.31422) | un operador de sondeo con presupuesto cuyo único propósito es reparar una tabla de creencias estructurada. Es la sonda de §6.2, mecanismo por mecanismo |
| Kintsugi, *Learning Policies by Repairing Executable Knowledge Bases* (arXiv 2605.09487) | ediciones a un artefacto ejecutable tipado, filtradas por un verificador, con las fallas diagnosticadas y localizadas en ediciones candidatas. Es la consolidación de §6.3 con su guarda de promoción |
| ProvenanceGuard, *Safeguarding LLM Agents from Misalignment through Provenance Analysis* (arXiv 2607.01236) | la desalineación como si una llamada propuesta está sostenida por evidencia trazable en el contexto. Es el piso de procedencia de §5.5 sobre las acciones |

Y el área está lo bastante poblada como para tener survey: *From Agent Traces to Trust:
A Survey of Evidence Tracing and Execution Provenance in LLM Agents* (arXiv 2606.04990).

Sondeo con presupuesto sobre un estado de creencias tipado, ediciones de política filtradas por
verificador, y pisos de procedencia sobre acciones están cada uno establecido, y ninguno de
los tres es original de este trabajo.

Lo que queda es una conjunción, enunciada por lo que excluye: una capa de decisión que
(a) elige qué topología de control de flujo correr, por request, de un catálogo de ellas,
ninguno de los tres rutea entre *paradigmas*; (b) puede abstenerse, con la curva
riesgo–cobertura reportada en vez de la utilidad de lo que eligió contestar; y (c) poda por
aritmética sobre el presupuesto declarado antes de cualquier inferencia. Sacando
cualquiera de las tres, el resto queda cubierto por el trabajo de arriba.

Y uno de los cuatro nos apoya, desde un lugar al que no llegamos. *Trace2Policy: From
Expert Behavior Traces to Self-Evolving Decision Agents* (arXiv 2606.10457) reporta un
despliegue en producción de 22 días sobre 3.349 casos resueltos, y encuentra que a lo
largo de cinco escalas de modelo, la varianza atribuible a la versión de la regla supera a
la atribuible a la elección de modelo. Independiente, a escala de producción, y lo más
parecido a corroboración externa que tiene esta línea: la estructura decide más que el
modelo.

## 2.11 Capacidades declaradas contra descripciones de habilidades

El vecino de §7.4 del lado de la ingeniería es el ruteo por habilidades: agentes que publican
una tarjeta con lo que saben hacer y un orquestador que despacha por esa tarjeta, como en el
protocolo Agent2Agent y sus antecesores en sistemas multiagente. La diferencia es de
procedencia, y es la misma de todo el paper. Una tarjeta de habilidades es texto que el agente
o su autor escriben sobre sí mismos, se lee con un modelo o con un matcher semántico, y nada
la verifica contra la conducta. Una capacidad de §7.4 es un booleano declarado desde el código
del brazo, con el sitio donde se ve y con una auditoría que contrasta lo declarado contra lo
corrido. La primera es `ELICITED` sobre el propio agente, que es exactamente la clase de
evidencia que los contratos de delegación de §2.4 midieron que selecciona a los peores; la
segunda es `COMPUTED`. Y la tabla de exigencias va del eje de la pregunta a la capacidad, nunca
al nombre del agente, así que predice sobre un brazo que todavía no existe. Búsqueda fechada
2026-09-01: no se encontró trabajo que declare capacidades de control de flujo desde el código
y las someta a leave-one-arm-out.

---

# 3. Preliminares

Una tarea `t` aporta una pregunta, un conjunto de *unidades* (documentos), un
presupuesto declarado de tokens, y flags de irreversibilidad y escritura de estado
compartido. Un paradigma `p ∈ P` es una estructura de control que puede llamar
herramientas y debe emitir una respuesta. La calidad `q(t,p) ∈ [0,1]` es F1 de conjuntos
contra un oráculo exacto. El costo `c(t,p)` es el total de tokens sobre cada llamada que
el paradigma hace.

El mejor paradigma fijo es `p⋆ = argmax_p E_t[u(t,p)]`. El oráculo es
`E_t[max_p u(t,p)]`, y la brecha del oráculo es su diferencia. La utilidad es calidad
neta de una preferencia de costo:

```
u(t,p) = q(t,p) − λ · (c(t,p) / min_{p'} c(t,p') − 1)
```

Normalizar por el paradigma más barato en esa tarea hace a λ interpretable, la calidad que
uno está dispuesto a cambiar por un múltiplo extra del costo mínimo, y λ=0 recupera calidad
pura exactamente. No se elige ningún λ: la calidad y el costo crudos se guardan sin
modificar y el trade-off se aplica en tiempo de análisis, de modo que los resultados se
reportan como función de λ y no bajo un supuesto sobre λ. Convención de §7: toda `u` reportada
usa `λ = 0`, calidad pura con el costo en su propia columna, salvo donde se indique otro λ.

Dos términos más que §7.3 usa. Sobre un panel de tareas y brazos, la utilidad se descompone
como `u(t, p) = μ + α(t) + β(p) + γ(t, p) + ε`, donde `α` es la dificultad de la tarea, `β` la
calidad del brazo, `γ` la interacción y `ε` el ruido entre réplicas de la misma celda; una celda
es un par tarea × paradigma. Y una región es una celda de la partición del espacio de features
que la política usa como clave (§5.7, §6.3).

El plantel son doce paradigmas, y se agrupan por de qué es función su costo (que es lo que predice quién sobrevive cuando el material crece) y no por su nombre de familia:

| ley de costo | paradigmas | qué los define |
|---|---|---|
| estructural | `direct`, `rewoo`, `graph_traverse`, `extract_compute`, `streaming_scan` | número fijo de llamadas, pase lo que pase |
| por vueltas | `react`, `reflection`, `dag_strategy`, `supervisor`, `gist_reader`, `pointer_chase` | el costo escala con cuántas veces vuelven al modelo |
| por alcance | `handoff` | el costo escala con cuánto material hay |

Cinco existen para cotejar contra grillas publicadas. Los otros siete entran cada uno contra
un modo de falla concreto: `rewoo` porque planifica todo de antemano y su costo no depende del
alcance; `dag_strategy` porque una comparación que omite la topología más elaborada disponible
está sesgada a favor de las simples; `handoff` y `supervisor` porque reparten alcance entre
sub-agentes de dos maneras distintas; `gist_reader`, `pointer_chase` y `graph_traverse` porque
cada uno interpone una representación intermedia más chica que el material (un resumen, un puntero, un índice de entidades) y §7.2.1 mide qué cuesta eso.

La ingeniería de prompts no es un paradigma y no está en el plantel de decisión. Un brazo
que sólo cambia el fraseo quedó como control nulo: en toda celda medida da la misma utilidad
que la llamada directa y nunca cuesta menos. Los paradigmas se distinguen por estructura de
control de flujo, jamás por redacción, y esa regla es lo que hace que las mejoras de §7.2.4
sean transferibles en vez de anecdóticas.

---

# 4. La factibilidad es aritmética

**Algoritmo 3.** La compuerta, entera. No hay ninguna llamada al modelo y no hay ningún parámetro
aprendido: es una desigualdad sobre cantidades que la tarea ya declara.

```
ALGORITMO 3  Portón de factibilidad
────────────────────────────────────────────────────────────────────────────────
Entrada : tarea t con unidades U, presupuesto Β tokens, plantel P
Salida  : P′ ⊆ P, los que PUEDEN correr

 1  N ← |U|                                    ▷ cardinalidad
 2  C ← Σ_{u ∈ U} tokens(u)                    ▷ contenido total
 3  A ← Β − reserva_de_conversación(t)         ▷ lo disponible de verdad
 4  P′ ← ∅
 5  for cada p ∈ P do
 6      según ley_de_costo(p):
 7          alcance     : coste ← C
 8          estructural : coste ← C / ramas(p)
 9          vueltas     : coste ← unidad_máxima(U) · techo_de_llamadas(p)
10      if coste ≤ A then P′ ← P′ ∪ {p}
11  return P′
────────────────────────────────────────────────────────────────────────────────
```

La línea 6 es la que separa dos modos de falla que se confunden de rutina: a un paradigma
que reparte por unidad lo acota `N` y no `C`, y a uno que lee todo lo acota `C` y no `N`. Un
corpus con pocas unidades enormes poda a los primeros; uno con muchas unidades chicas, a los
segundos. Sin la línea 6 los dos casos se reportan como «no alcanzó el contexto».

> Los corpus de esta sección son la escalera de escala, no el corpus de medición.
> `gold_v2`, `gold_wide` y `gold_deep` existen para barrer cuatro órdenes de magnitud de
> material (16k a 1,27M tokens) y mostrar que la compuerta de factibilidad se comporta como su
> aritmética predice en los cuatro. Los resultados de §7 corren sobre otro corpus, con
> entidades reales y variantes de superficie. La factibilidad no depende del modelo ni del
> corpus: es una desigualdad sobre cantidades declaradas, y por eso se puede validar en un
> lugar y aplicar en otro.

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

Aplicado a 168 tareas sobre cinco corpus del mismo generador, cada tarea con su propio
presupuesto declarado:

| corpus | tokens/unidad | unidades/tarea | contenido máx | Direct, CoT | Map-Reduce |
|---|---|---|---|---|---|
| gold_v2 | 232 | 60 | 16k | 39/39 | 39/39 |
| gold_v3 | 2.147 | 60 | 152k | 12/39 | 39/39 |
| gold_wide | 264 | 500 | 135k | 20/32 | 18/32 |
| gold_deep | 7.161 | 60 | 483k | 2/26 | 26/26 |
| gold_xl | 2.499 | 500 | 1.272k | 8/32 | 18/32 |

Tareas factibles sobre el total. Los otros cuatro paradigmas son factibles en 168/168.

Agregado sobre paradigmas, el espacio de planes admisibles se contrae monótonamente con la
escala, 273/273 celdas en gold_v2, 186/224 en gold_wide, 134/182 en gold_deep, 162/224 en
gold_xl: de 100% admisible a 72%, íntegramente por aritmética y antes de gastar un token.
Un selector que opere sin esta capa tendría que aprender que ese cuarto del espacio es
inalcanzable, un episodio fallado a la vez.

El par decisivo es gold_wide contra gold_deep. gold_deep lleva 3,6× más contenido, y
Map-Reduce pasa de 18/32 factibles a 26/26 mientras Direct y CoT se derrumban a 2/26. El
tamaño total no predice la factibilidad de Map-Reduce; la cardinalidad sí. Con 483k
tokens en 60 unidades corre, porque nunca las tiene juntas. Con 135k en 500 unidades no: 501
llamadas, y un reduce que concatena 500 hallazgos. Tratar su límite como un límite de
contexto lleva a descartarlo exactamente donde funciona.

El mismo tope de acumulación aplica al blackboard del DAG, que renderiza cada hallazgo
dentro de cada prompt de sub-agente.

Cuán fuerte muerde la restricción de leer-todo es fácil de subestimar. En gold_deep una
tarea de una sola unidad es infactible para Direct, porque un documento son 8.075 tokens
contra una asignación de 4.800. La restricción real es que la pieza más chica que se puede
direccionar ya no entra, no que el corpus sea grande, y ninguna cantidad de lectura selectiva
cambia eso para un paradigma cuyo único movimiento es leer.

Una segunda lectura que conviene decir en voz alta. Los cuatro paradigmas selectivos son
factibles en las 168 tareas. Es una propiedad real, acotan sus propias iteraciones y leen a
demanda, pero también acota lo que esta capa puede hacer. La factibilidad restringe sólo a
los paradigmas que retienen material en contexto o se abren por unidad; no ofrece ninguna
protección contra un paradigma selectivo gastando a través de un corpus de 1,27M tokens.
Esa protección tiene que venir de un presupuesto, no de aritmética sobre el corpus, y §7.2
muestra por qué hace falta: los selectivos son justamente los que varían cincuenta veces en
costo.

## 4.3 Por qué esto va delante del problema de aprendizaje

La factibilidad es determinista, gratis, y aguas arriba de todo lo demás. Poda el espacio de
planes antes de cualquier selección, aprendida o no. El corolario para producción es que
saber el largo y declinar no es una degradación, es la diferencia entre un sistema acotado
y uno desbocado.

Medido, y la distinción no es académica. Sobre cuatro celdas de gold_deep, Direct quedó
podado en tres y corrió en una, donde sacó 1,000. Registradas como respuestas equivocadas,
esas tres dejarían su media en 0,250, de mejor a peor del plantel, por un artefacto de
registro. Registradas
como infactibles, el enunciado es el correcto: *el mejor donde puede correr, no disponible
donde no.* La misma capa que protege al estudio de una conclusión falsa es la que un sistema
en producción necesita para declinar en lugar de fallar.

---

# 5. Teoría

Cómo leer esta sección respecto de la tesis. §5.0 define la propiedad que da nombre al
trabajo. §5.1 y §5.2 son el instrumento con el que §7.3 y §7.8 midieron que el ruteo por
identidad no tiene premio: una identidad contable y una partición por verificabilidad, y
ninguna de las dos afirma que rutear convenga. §5.3 a §5.5 son la máquina: qué garantiza el
ensamblador, cuánto daño puede hacer un piso que sólo sube, y quién fija el nivel. §5.6 dice
sobre qué se afirma todo eso. Y §5.7 enuncia la única condición formal que la tesis v2
necesita y que §7.3.6 mide: sobre qué clase de clave puede aprender una política sin perder
la garantía de §5.0. Los enunciados de §5.1 a §5.5 son identidades, construcciones y
monotonías; se los rotula como teoremas y proposiciones por consistencia con los tests que los
verifican, no porque su demostración sea difícil.

## 5.0 Confinamiento de varianza

El título de este trabajo nombra una propiedad, así que la propiedad necesita definición antes
que evidencia.

**Definición 5.1** (Trayectoria). Sea `q` un request y `M` el material declarado. Una
*trayectoria* `T(q, M)` es la secuencia ordenada de nodos visitados por un agente: cada nodo es
un par ⟨unidad leída, llamada emitida⟩.

**Definición 5.2** (Punto de ramificación delegado). Un nodo `nᵢ ∈ T` es un *punto de
ramificación delegado* si la identidad de `nᵢ₊₁` es función de la salida del sensor. Se escribe
`d(T) = |{nᵢ ∈ T : nᵢ es delegado}|`.

La distinción es entre qué se extrae de un nodo y cuál es el nodo siguiente. Un agente
que le pregunta al modelo «¿qué dice esta unidad?» no delega ramificación; uno que le pregunta
«¿dónde busco ahora?» sí.

**Definición 5.3** (Confinamiento de varianza). La varianza de un agente está *confinada* sobre
`(q, M)` si `d(T(q, M)) = 0`: la secuencia de nodos visitados es una función determinista de `q`
y de `M`, y la salida del sensor sólo determina el contenido atribuido a cada nodo.

**Proposición 5.4** (Localización). Si la varianza está confinada, entonces para dos ejecuciones
cualesquiera `T₁` y `T₂` sobre el mismo `(q, M)` se cumple `T₁ = T₂` como secuencia de nodos, y
toda discrepancia entre sus salidas es atribuible a un nodo identificable.

*Demostración.* Por inducción sobre la longitud. El nodo inicial es función de `q` y `M` por
hipótesis. Dado `nᵢ` idéntico en ambas ejecuciones, `nᵢ₊₁` es función de `(q, M, n₁…nᵢ)` y no de
la salida del sensor, porque `d(T) = 0` excluye la dependencia; luego `nᵢ₊₁` coincide. Las dos
secuencias son iguales. Una discrepancia de salida exige entonces que algún nodo haya recibido
contenido distinto, y ese nodo es el testigo. ∎

Lo que la proposición compra, y es la razón de ser del confinamiento. Sin él, dos réplicas
que difieren pueden diferir porque leyeron material distinto, y no hay forma de localizar la
causa: la discrepancia se reparte sobre una historia entera. Con él, la discrepancia siempre
tiene un nodo responsable, y una discrepancia localizable es depurable, auditable y
corregible, mientras una repartida no.

Y lo que NO afirma. El confinamiento no reduce la varianza del sensor ni mejora la calidad
de la respuesta: reordena dónde puede manifestarse. La afirmación empírica de §7.2 (que confinar sube la utilidad *además* de estabilizar) es un resultado de ese corpus y no una
consecuencia de la Proposición 5.4.

**Definición 5.5** (Consecuencia observable). Para `k` réplicas de una misma celda,
`pass^k = P(todas las k réplicas aciertan)`. La Proposición 5.4 implica que con varianza
confinada `pass^k` está acotado inferiormente por `pass@1` menos la varianza de extracción de
contenido, y no por el producto de las varianzas de ramificación. §7.2.2 mide la brecha en el
régimen no confinado.

## 5.1 El Teorema del Valor de Selección

> Es una identidad contable, no un resultado empírico, y se usa como instrumento. No
> afirma que rutear convenga: descompone exactamente el valor de rutear en términos que se
> pueden medir por separado, y por eso permite que una evaluación de ruteo sea falsable.
> §5.1.5 desarrolla la distinción. Un teorema presentado como evidencia del sistema sería el
> error que §2.4 le audita a otros.

Sea `p⋆` el fallback y `p_1 … p_k` los especialistas. Sea `Δ_j(t) = u(t,p_j) − u(t,p⋆)`.
Para cada brazo, partir el espacio de tareas en tres, la tercera parte no es un
tecnicismo, y §5.1.1 muestra qué cuesta colapsarla:

```
S₊ʲ = { Δ_j > 0 }   ganancia estricta   π_j = Pr[S₊ʲ]
S₀ʲ = { Δ_j = 0 }   empate              τ_j = Pr[S₀ʲ]
S₋ʲ = { Δ_j < 0 }   pérdida estricta    ν_j = Pr[S₋ʲ]
```

y sean, condicionadas a lo efectivamente ruteado.

```
α_j = Pr[rutear a p_j | S₊ʲ]      G_j = E[  Δ_j | rutear a p_j , S₊ʲ ]
β_j = Pr[rutear a p_j | S₋ʲ]      L_j = E[ −Δ_j | rutear a p_j , S₋ʲ ]
```

**Teorema 1.** Para todo `k ≥ 1`.

```
V(r) − V(p⋆)  =  Σⱼ ( π_j · α_j · G_j  −  ν_j · β_j · L_j )
```

*exactamente*, sin ningún supuesto de independencia. Por lo tanto la selección le gana al
mejor paradigma fijo si y sólo si `Σⱼ π_j α_j G_j > Σⱼ ν_j β_j L_j`.

*Demostración.* `V(r) − V(p⋆) = E[Δ_{r(t)}(t)·1{r(t) ≠ p⋆}]`. Descomponiendo por destino
queda `Σⱼ Pr[rutear a p_j]·E[Δ_j | rutear a p_j]`, y partiendo cada esperanza condicional
según el signo de `Δ_j`: la parte de `S₊ʲ` pesa `π_j α_j` con media `G_j`, la de `S₋ʲ` pesa
`ν_j β_j` con media `−L_j`, y `S₀ʲ` aporta exactamente cero porque ahí `Δ_j = 0`. ∎

Dos decisiones lo vuelven exacto y no aproximado. Condicionar `G` y `L` a los subconjuntos
*ruteados* elimina todo supuesto de independencia entre dónde vive la ganancia y dónde el
ruteador elige ir. Y descomponer por destino en vez de por un único «especialista» lo
hace valer para un catálogo: con `k` brazos, equivocarse tiene un *destino*, y mandar una
tarea a un brazo apenas peor no es el mismo evento que mandarla al peor de doce.

**Corolario 1 (precisión sobre cobertura).** Cuando `p⋆` es casi óptimo en regiones amplias,
`G` es chico y `L` grande, así que la condición exige `β → 0` incluso a costa de `α`. El
recall no es el objetivo.

### 5.1.1 Un empate no es un misruteo

`S` se define con desigualdad *estricta*, así que los empates quedan afuera. Una versión
anterior de este teorema definía `β` sobre el complemento de `S₊`, lo que le cobraba al
ruteador haber ruteado sobre un empate, un acto que no cuesta absolutamente nada.
Construido: un ruteador que rutea sólo donde gana o empata, y nunca donde pierde, registra
β = 0,714 sin haber hecho un solo daño.

El producto `β·L` seguía siendo correcto, porque `L` absorbía el cero. Pero `β` sola dejaba
de ser la *tasa* de misruteo, y el Corolario 2 usa `β` y `L` por separado. Definir `β` sobre
`S₋` restituye la lectura esperada y deja el Teorema 1 intacto: los empates
aportan cero a los dos lados.

No es un caso de borde en ningún catálogo donde varios paradigmas resuelven la misma tarea.
Acá, un brazo es el más barato al empatar en 46 de 96 celdas.

### 5.1.2 El umbral de imposibilidad, y contra qué pérdida se mide

Definir, por brazo.

```
L̄_j = E[ −Δ_j | S₋ʲ ]     la pérdida media de la TAREA        (no depende del ruteador)
ρ_j = L_j / L̄_j           la SELECTIVIDAD DE PÉRDIDA          (ρ_j := 1 cuando β_j = 0)
```

**Corolario 2.** El ruteador le pierde a siempre-fallback si y sólo si
`Σⱼ π_j α_j G_j < Σⱼ ν_j β_j ρ_j L̄_j`, y con un solo brazo

```
β_max(ρ) = π · α · G / ( ν · ρ · L̄ )
```

| `ρ` | qué ruteador es | qué hace el umbral |
|---|---|---|
| ρ = 1 | ciego a la magnitud de la pérdida, se equivoca de forma representativa | el enunciado clásico, y ahí es exacto |
| ρ < 1 | evita las equivocaciones caras | se afloja |
| ρ > 1 | anti-calibrado: falla justo donde más duele | se endurece |

Por qué el parámetro es necesario y no un refinamiento. Enunciado sólo con la pérdida
distribucional, el umbral no es una imposibilidad. Alcanzan tres tareas: una ganancia de
`+0,10` con probabilidad `0,10`, ruteada; una pérdida de `−0,001` con `0,45`, ruteada; y una
de `−1,00` con `0,45`, *no* ruteada. Entonces `β = 0,500` supera `β_max = 0,0222` por 23× y
el ruteador igual captura `+0,00955`. Un ruteador que se equivoca *seguido pero barato*
es exactamente lo que produce un ruteo selectivo bien construido.

Tampoco alcanza con sustituir por la pérdida realizada: un ruteador perfecto no realiza
pérdida, así que el umbral reportaría infinito y parecería no imponer restricción alguna,
la objeción que motivó la forma distribucional en primer lugar. Las dos objeciones son
correctas. Se disuelven juntas en cuanto la pérdida realizada entra como *factor de la
pérdida* y no como *denominador de un umbral*: con `β = 0` el término entero se anula antes
de que `ρ` se consulte.

**Corolario 2b.** Un ruteador obligado a elegir no controla ni `β` ni `ρ`. Uno selectivo
controla los dos, y `ρ` es la palanca más barata: bajar `β` exige acertar más seguido;
bajar `ρ` sólo exige abstenerse donde la apuesta es cara. Eso le da al Corolario 1 un
mecanismo y no sólo una desigualdad, y `ρ` se recupera de cualquier registro que reporte
pérdida potencial y realizada.

### 5.1.3 Cobertura óptima

Sea `V(c)` el valor capturado a cobertura `c`, admitida bajando un umbral de confianza.
Entonces `dV/dc = E[Δ | tarea marginal en c]`, y por lo tanto:

(a) `V` es unimodal si y sólo si `c ↦ E[Δ | marginal en c]` es no creciente, es
decir, si y sólo si la señal de confianza ordena las tareas por *ganancia esperada*. La
calibración sola no da eso. La calibración restringe la probabilidad de ganar; el valor
depende de su magnitud. Construido, con `Pr[acertar | κ] = κ` exactamente en cada grupo:
tres grupos con `E[Δ]` de `+0,008`, `−0,170` y `+0,593` a confianzas `0,90`, `0,60` y `0,30`
producen una curva de valor capturado que sube, baja y vuelve a subir, con su óptimo en
cobertura total.

(b) Sin ningún supuesto: la cobertura óptima es `< 1` siempre que alguna tarea con
`Δ_{r(t)}(t) < 0` fuera ruteada a cobertura total. Esto es lo que el argumento necesita, y
se sigue en una línea, sacar un término negativo aumenta la suma.

**Corolario 3.** Afirmamos (b). Afirmar unimodalidad afirma más de lo que el diseño
necesita, y regala un contraejemplo.

### 5.1.4 La identidad de la brecha del oráculo, y su alcance

Con un solo especialista, la brecha del oráculo iguala `π·G`, lo que permite recuperar el
`β` implícito de un ruteador publicado a partir de sus números de portada. Con `k` brazos
no factoriza: la brecha es `E[maxⱼ Δ_j⁺]`, que no es `π_j·G_j` de ningún par fijo. Los
17,1pp reportados para una suite publicada pueden leerse como `π·G` sólo donde ese trabajo
reporte un *par*; sobre una grilla, la lectura del `β` implícito no está disponible.

### 5.1.5 Qué es el Teorema 1, y qué no es

Es una *identidad*: una descomposición algebraica exacta, verdadera por construcción.
Ninguna medición puede falsarla, y nada en este paper debe leerse como que la confirmó.
Lo empírico es sólo si sus términos satisfacen la desigualdad sobre una distribución dada,
una pregunta sobre un ruteador, no sobre el teorema.

El Teorema 1 y los tres corolarios están verificados en `tests/test_science.py` contra
distribuciones cuyos términos se conocen por construcción. La identidad se chequeó además
sobre 4.000 distribuciones al azar con `k` de 1 a 4 (3.269 de ellas con empates) con
discrepancia máxima `1,67 × 10⁻¹⁶`. Los Corolarios 2 y 3 están enunciados arriba en su forma
corregida; los contraejemplos que forzaron la corrección se reproducen ahí.

Y la distinción importa en este punto porque los términos nunca se separaron. En los dos corpus
held-out el margen de decisión del ruteador fue 0 en todas las tareas, así que la curva
riesgo–cobertura colapsa a un solo punto en el origen: AURC 0,000 contra un techo de
+0,400. Un ruteador que nunca se abstiene no tiene `α` ni `β` distintos de
siempre-fallback, así que la identidad se cumple vacuamente, con los dos términos medidos
sobre una cobertura que el ruteador no eligió.

> El Teorema 1 aporta la contabilidad; §5.2 aporta las afirmaciones falsables que este
> registro resolvió, dominancia de cascada y sensibilidad del detector. La rama de
> selección de la partición sigue sin ejercitarse (§8.2).

Una observación une las tres correcciones. `π`, `α` y `β` responden *si* el ruteador
acierta; `G`, `L` y `ρ` responden *cuánto cuesta cuando no*. Cada lugar donde el enunciado
anterior falló (el umbral, los empates, la unimodalidad) es un lugar donde esos dos ejes se
trataron como uno.

## 5.2 Dominancia de la cascada, y su corrección medida

Un ruteador que se equivoca paga `L`, una pérdida de calidad: se entrega una respuesta peor
y nada la recupera. Una cascada que se equivoca paga `cost(p_1)`, una pérdida de costo: el
intento barato se desperdicia y la buena respuesta llega de todas formas tras escalar.

Con sensibilidad de detector `s`:

```
regret(ruteador) = ν·β·ρ·L̄
regret(cascada)  = E[costo de la escalera] + (1−s)·L
```

Una corrección que le debemos a la medición. Un enunciado anterior de este resultado daba
el término de costo como `cost(p_1)`. Es falso. Cuando ningún escalón satisface al detector, la
cascada corre la escalera *completa*: en el estudio sintético capturó el 100% de la brecha
a 4,4× el costo del mejor paradigma fijo. El límite es el costo esperado de la escalera, y
el patrón requiere un tope de presupuesto.

La sensibilidad del detector es la variable crítica, y un detector débil es catastrófico y no
simplemente subóptimo. Con `s = 0,6` la fracción capturada midió −5,98: una falla no
detectada deja a la cascada detenida en un escalón barato con una respuesta mala. Es el análogo
estructural del Corolario 2, como un ruteador con `β` alto pierde, una cascada con `s` bajo
pierde, y pierde más fuerte.

**Corolario (la partición por verificabilidad).**

```
v = 1  (existe un oráculo barato)  ->  cascada; no hace falta ruteador
v = 0  (no hay oráculo)            ->  rutear, bajo la disciplina del Teorema 1
```

Predecir sólo es necesario donde verificar es imposible. Si esto se sostiene, buena parte de la
literatura de ruteo está resolviendo el problema equivocado en el régimen verificable.

Y la partición tiene una consecuencia metodológica filosa que pagamos por aprender. La
rama `v = 0` es la que necesita un ruteador, y es precisamente la rama que un benchmark de
coincidencia exacta no puede contener: el gold es lo que hace que corregir no necesite juez,
y el gold es un detector. En este registro la conflación fue literal (un mismo campo servía para las dos cosas) y el resultado es que dos predicciones de ruteo preregistradas, sobre
dos corpus held-out independientes, las contestó la regla de cascada mientras la de
selección no se evaluó nunca. Los números son reales; lo que miden es la rama `v = 1`.

Separar las dos no es un cambio de calibración. Requiere un corpus que declare la
disponibilidad de detector por tarea sobre bases independientes de la clave de respuestas
(para nosotros, si verificar es más barato que resolver) y mueve la cascada de disparar en
22 de 26 tareas a disparar en 2.

---

## 5.3 Soundness del ensamblador

Los tres resultados que siguen son estructurales: ninguno depende de un corpus, de un
modelo ni de una corrida. Están en esta sección porque la maquinaria que describe §6 existe para hacer
posibles enunciados de esta forma, y sin ellos la procedencia es contabilidad, se registra,
se muestra, y no compra nada que alguien pueda nombrar.

Sea `T` una plantilla con ranuras `S = {s₁ … sₙ}`, `B` una asignación de ranuras a
proposiciones, `Γ` una base de creencias y `φ` un piso de procedencia.

**Teorema 2 (soundness del ensamblador).** Si `fill(T, B, Γ, φ)` emite una cadena `R`,
entonces para toda ranura `sᵢ ∈ S` existe `βᵢ ∈ Γ` tal que

1. `βᵢ` es la creencia vigente sobre la proposición que `B` asigna a `sᵢ`;
2. `rank(procedencia(βᵢ)) ≥ rank(φ)`;
3. la subcadena de `R` en la posición de `sᵢ` es exactamente `str(valor(βᵢ))`.

Y `R` no contiene ninguna subcadena que provenga de otro lado que no sea `T` o esos valores.

En una línea: si el ensamblador emite, todo número que emitió está implicado por la base de
creencias al piso pedido. No «probablemente». No «salvo alucinación».

*Demostración.* Por construcción, y depende de una línea. `fill` recorre `slots_of(T)` (las ranuras que la plantilla realmente usa, extraídas de ella y no declaradas aparte) y para cada
una hace exactamente tres cosas: resuelve la proposición asignada, pide la creencia vigente y
compara el rango de procedencia contra el piso. Cualquier fallo anota el motivo y sigue, sin
emitir. La sustitución ocurre después de comprobar que la lista de rechazos está vacía,
así que `values` tiene una entrada por cada ranura de `T`, todas provenientes de una creencia
vigente que pasó el piso; y la sustitución reemplaza ocurrencias del patrón de ranura dejando
intacto el resto de la plantilla, que es texto fijo escrito por el código. Las tres
condiciones se corresponden una a una con las tres guardas, y no hay un cuarto camino por el
que un valor llegue a la salida. ∎

Falla cerrada y falla ENTERA, que es una decisión y no una consecuencia. Si una sola
ranura no llega al piso, no se emite una versión parcial. Emitir *«el saldo de la cuenta es
___»* no es más honesto que emitir un número inventado: es el mismo acto con mejor caligrafía,
e invita al lector a completar lo que el contrato rechazó.

Cuatro límites, dichos adentro del teorema y no en una nota al pie.

| límite | qué significa |
|---|---|
| el alcance es la ranura, no la oración | *«el saldo NO supera {x}»* con `x` correcto es sound y falso. No es un defecto de la implementación: es la frontera de la familia entera, y un red-team la mide en vez de suponerla |
| la procedencia es del registro, no del mundo | `COMPUTED` significa que alguien la computó y la asentó. El teorema traslada confianza desde el piso hacia la salida; no la crea. Un sensor que miente se emite con procedencia impecable |
| vigente, no histórica | la garantía es sobre el estado de creencias al ensamblar, no sobre todo lo que alguna vez se creyó |
| `str()` es parte del teorema | la condición 3 dice `str(valor)`, no «el valor». El ensamblador no formatea, porque formatear sería empezar a decidir algo sobre el número |

Verificado exhaustivamente y no por casos elegidos: sobre el producto cartesiano de las
cuatro procedencias por las condiciones de rechazo, un espacio chico, y por eso uno que se
puede recorrer entero.

## 5.4 La cota nativa del ratchet

El piso de garantía aprendido sólo sube. Un borrador anterior lo acotaba importando un
teorema sobre varianza bajo oscilación. Eso era un error de categoría, no una cita floja.
Una secuencia monótona y acotada tiene varianza que tiende a cero por construcción, así que
la cota se cumplía vacuamente y no decía nada. Lo que un ratchet necesita que se le acote es
cuánto daño acumulado puede hacer antes de detenerse, no cuánto oscila, y eso es un conteo.

Los niveles son `EXPLORATORY < STANDARD < ACCOUNTABLE < CERTIFIED`, y el techo aprendido es
el tercero: `CERTIFIED` queda fuera de alcance a propósito, porque ese nivel restringe qué
patrones son admisibles y una estadística sobre calidad de evidencia no es evidencia sobre
certificabilidad.

**Proposición 4 (daño total acotado).** Sobre `R` regiones, el número total de eventos de
endurecimiento en toda la vida del sistema es `≤ 2R`, sea cual sea la cantidad de ciclos
de consolidación.

*Demostración.* Monotonía: el piso de cada región es una secuencia no decreciente en un
conjunto finito y totalmente ordenado, así que cambia a lo sumo tantas veces como niveles
haya por encima de su base. No hace falta nada probabilístico. ∎

**Proposición 5 (la guarda de replicación es fuerte lejos del umbral y débil cerca).** Con
`q` la tasa verdadera de rechazo de la región y dos splits de tareas disjuntos:

| `q` | un split | ambos | ≈ |
|---:|---:|---:|---:|
| 0,10 | 0,0050 | 0,000025 | 1 en 39.613 |
| 0,25 | 0,1138 | 0,01295 | 1 en 77 |
| 0,40 | 0,4059 | 0,16477 | 1 en 6 |
| 0,45 | 0,5230 | 0,27358 | 1 en 4 |

Eso se dice y no se esconde, e importa menos de lo que parece por dos razones
estructurales. Cerca del umbral un falso positivo es casi indistinguible de un verdadero (una región cuyo `q` real es 0,45 efectivamente rechaza casi la mitad de las veces). Y la
Proposición 4 acota el daño acumulado pase lo que pase.

> La monotonía que vuelve inaplicable el teorema de varianza prestado es exactamente lo que
> acota el daño de su propia tasa de falsos positivos. La propiedad que rompe la cota
> prestada es la que la hace innecesaria.

Y lo que cuesta está medido, lo cual corrige cómo se lee la Proposición 4.

| nivel | brazos admisibles | cobertura | `u`(mejor fijo) |
|---|---:|---:|---:|
| A0 · A1 · A2 | 5 | 100% | 0,6101 |
| A3 | 2 | 40% | 0,4221 |

El ratchet es gratis hasta A2 y cuesta todo de una vez en A3: la única transición con
precio se lleva 60% del catálogo y 31% de la utilidad. «A lo sumo dos subidas» invita a
imaginar un daño que se acumula despacio; lo medido es lo contrario, una sola transición
tiene precio, y ahí es abrupto. Las otras dos son gratis porque no hacen nada. Y el
promedio esconde a quien paga: una región pierde −0,5000 mientras la media del corpus es
0,0000.

## 5.5 Quién fija el dial

La pregunta parece de gobernanza y es de diseño. Si el nivel de garantía lo elige el
llamador, un llamador apurado lo baja; si lo elige el sistema, el llamador no puede pedir más
rigor del que el sistema cree necesario. Ninguna de las dos.

```
nivel efectivo = max( pedido , piso de creencias , piso aprendido )
```

| fuente | quién la produce | qué puede hacer |
|---|---|---|
| pedido | el llamador, en el request | subir, nunca bajar |
| piso de creencias | `required_floor(Γ)` sobre las creencias `COMPUTED` del request | subir, y no se puede desactivar |
| piso aprendido | `θ.floors[región]`, dentro del bundle firmado | subir, y sólo si está promovido |

**Proposición 6.** `max` es la única composición bajo la cual cada fuente sólo puede
endurecer. Con `min` o con un promedio, agregar una fuente podría ablandar el resultado, y
entonces una fuente nueva sería un riesgo en vez de una garantía.

Por qué el llamador sube y no baja. Conoce cosas que el sistema no: que este request va a
un informe regulatorio, que el resultado se publica, que hay un auditor mirando. Nada de eso
está en el material. Lo que no puede es pedir menos, porque el piso sale de propiedades
del request mismo, `irreversible` eleva a A3, `shared_writes` a A2, y las dos entran
como creencias `COMPUTED` declaradas por el caller, nunca inferidas del texto. Un llamador
que pudiera bajar el piso podría declarar una acción irreversible y después pedir tratarla
como exploratoria, que es exactamente la combinación que el piso existe para impedir.

Una cuarta fuente, que es una degradación y no un nivel. A2 admite creencias
`ELICITED`, pero sólo una vez que la calibración se ganó; admitirlas antes anula el propósito
del nivel. Así que la resolución no baja el nivel: endurece el piso de procedencia dentro
del nivel. La misma idea del `max`, aplicada al otro eje.

Y se evalúa marginalizando sobre sus posiciones, no fijando una, reportar métricas a un
dial fijo reporta una política, no un sistema. Marginalizar produjo un hallazgo sobre el
propio dial:

> Tres de las cuatro posiciones son indistinguibles. A0, A1 y A2 declaran
> `admissible_patterns = None`, así que el dial no restringe el catálogo hasta A3. Dos de
> sus tres transiciones no hacen nada en esa dimensión, y toda la diferencia se paga en un
> solo escalón.

Lo que sí distingue A1 de A2 vive en otros ejes (θ firmada, log de creencias, profundidad de composición, y el piso de procedencia), así que el dial no es inerte ahí: es inerte en la
dimensión que esa tabla mide. Decir cuál es cuál es el punto de marginalizar.

## 5.6 Lo que la teoría no supone, y por qué eso es la afirmación

Todo lo de §5.1–§5.5 está enunciado sobre un catálogo de brazos, una utilidad, una base de
creencias y un retículo de procedencia. Ninguno de los cinco resultados menciona
recuperación, documentos ni respuesta a preguntas. No es un accidente de redacción ni una
salvedad: es la afirmación. Lo que se describe es una capa de decisión sobre *acciones que
el sistema puede tomar*, y el ruteo de paradigmas sobre un corpus documental es la instancia
que pudimos medir sin juez.

La distinción sobre la que el motor realmente gira es qué se sabe y cuándo, no qué clase de
tarea es. Una regla sólo puede gobernar si se la puede evaluar al momento de decidir;
un valor sólo se puede emitir si una creencia vigente lo lleva a la procedencia exigida; un
nivel sólo se puede subir. Las tres son propiedades de la decisión, no del dominio.

La misma maquinaria, enunciada sobre cuatro superficies. Los teoremas de arriba son la
forma general; las columnas son lo que instanciarlos exige.

| superficie | el sensor emite | la regla decide | el registro guarda |
|---|---|---|---|
| contenido | números con procedencia | emitir o negarse, por ranura (§5.3) | qué creencia llenó qué ranura |
| datos | una consulta propuesta, su grano, su resolución temporal | admitir la consulta o exigir elicitación | la consulta, y contra qué se la chequeó |
| acciones | una llamada a herramienta y sus precondiciones | el piso de procedencia sobre lo irreversible (§5.5) | un ledger de idempotencia |
| gobierno | una edición candidata de la política | la guarda de promoción sobre episodios held-out | el diff entre dos bundles firmados |

La selección entre topologías de control es la primera columna instanciada sobre un
catálogo de recuperación. Es el caso medido, no el alcance de lo que se afirma.

Y la rama no probada de la teoría y la superficie no medida son el mismo lugar. §5.2
parte el problema sobre `v`, la disponibilidad de un detector barato, y §1.3 registra que
todos los corpus de este registro caen del lado `v = 1` por construcción, porque el gold es lo que
vuelve la calificación libre de juez y el gold *es* un detector. Así que la rama `v = 0` (la que necesita un router) no la puede alcanzar ningún benchmark que califique por exact-match.

¿Dónde está `v = 0`, entonces? Predominantemente en la superficie de acciones. Chequear *si
un archivo se escribió* es barato; chequear *si éste era el reembolso correcto* no lo es, y
no hay clave de respuestas que lo abarate. El dominio que este registro no mide es el
dominio donde la partición central de la teoría por fin tiene dos lados.

> Así que la ambición se enuncia en vez de matizarse. La teoría es general por
> construcción y está verificada como tal (sobre distribuciones sintéticas con respuesta
> conocida, no sobre corpus). Las mediciones son sólo de recuperación, y §8 dice exactamente
> qué herramientas existieron y cuáles nunca. §5 se afirma para agentes en general; §7–§8,
> para extracción de respuesta exacta sobre documentos. La brecha entre las dos es el
> alcance real, y está declarada en vez de estrechada.

## 5.7 La clave de la política y su procedencia

Todo lo que §6.3 llama aprender se ejecuta como una tabla: la política mira una clave y
devuelve una decisión. Esta sección dice de qué depende que esa tabla conserve la garantía de
§5.0, y es la condición que une las cuatro contribuciones.

**Definición 5.6** (Clave de la política). Sea `φ` una función que lleva un request `q` y su
material `M` a una tupla de ejes, `κ = φ(q, M, σ)`, donde `σ` es la salida del sensor sobre
`(q, M)`. La *clave* es `κ`, y una *región* es una celda de la partición del espacio de claves.
Un eje de `κ` es `COMPUTED` si es función de `(q, M)` solamente, y `ELICITED` si depende de `σ`.

**Definición 5.7** (Política). Una *política* `θ` es una función determinista de la clave a una
decisión, `θ(κ) ∈ D`, donde `D` incluye a los brazos del catálogo, la abstención y la sonda.

**Proposición 5.7** (La procedencia de la clave hereda o rompe el confinamiento). Sea `θ` una
política y `κ = φ(q, M, σ)` su clave.

1. Si todos los ejes de `κ` son `COMPUTED`, entonces `θ(φ(q, M))` es función determinista de
   `(q, M)`, y la decisión de qué brazo correr no es un punto de ramificación delegado en el
   sentido de la Definición 5.2. La trayectoria completa, decisión incluida, conserva la
   Proposición 5.4.
2. Si algún eje de `κ` es `ELICITED`, entonces para `(q, M)` fijos la decisión `θ(κ)` es una
   variable aleatoria sobre la distribución de `σ`, aun cuando `d(T) = 0` para cada brazo del
   catálogo. Dos réplicas del mismo request pueden ejecutar brazos distintos, y la discrepancia
   entre sus salidas no tiene nodo responsable dentro de ninguna trayectoria: está antes de
   todas.

*Demostración.* (1) es composición de funciones: `φ` restringida a ejes `COMPUTED` es función de
`(q, M)`, `θ` es función de `κ`, así que `θ ∘ φ` es función de `(q, M)`, y la Definición 5.2
excluye que sea delegada porque no depende de `σ`. La inducción de la Proposición 5.4 arranca
entonces un nodo antes, en la elección del brazo, y sigue igual. (2) Si un eje depende de `σ` y
`σ` no es constante sobre `(q, M)`, entonces `κ` no es constante y `θ(κ)` tampoco tiene por qué
serlo; la elección del brazo es entonces una ramificación cuyo siguiente nodo es función de la
salida del sensor, es decir, delegada por la Definición 5.2, y la Proposición 5.4 pierde su
hipótesis en el primer paso. ∎

Lo que la proposición compra. Da la forma exacta de la exigencia que §7.3.6 mide: el
vocabulario de región tenía un eje elicitado, el acoplamiento, y ese eje cambió de valor en el
27% de las tareas según qué modelo las sensó, así que la política buscaba en filas distintas de
la tabla para el mismo request. No es un defecto de calibración. Es (2). Y explica por qué cada
sensor que el ciclo de §7.8 agregó tuvo que ser `COMPUTED`: era la única forma de agregar
información a la clave sin volver a (2).

Lo que no afirma. No dice que una clave `COMPUTED` sea informativa. Una clave puede ser
determinista e inútil, y §7.8.1 mide exactamente ese caso: la región no veía el horizonte. La
proposición separa dos preguntas que el diseño suele mezclar, si la tabla es una tabla y si la
tabla sabe algo. La primera es esta sección; la segunda es §7.4 y §7.8.

---

# 6. Diseño

## 6.1 Medir sin juez

Cada tarea trae un oráculo de conjunto, así que la calidad es F1 de conjuntos tras
normalización. §2.7 da la razón: el efecto es de un dígito de puntos porcentuales y la varianza
del juez es del mismo orden, así que un juez no agregaría solamente ruido sino un sesgo,
el sesgo de verbosidad favorece las respuestas largas que producen los paradigmas caros, que es
precisamente la comparación bajo prueba.

Un oráculo vacío es una pregunta legítima e importante, *listá todos los X* donde no hay
ningún X, y testea si un paradigma inventa items. Se califica exigiendo un enunciado explícito
de vacuidad; el silencio saca cero, porque un paradigma que no devolvió nada porque se cayó no
debe puntuar igual que uno que buscó y reportó no haber encontrado nada.

## 6.2 Creencias, procedencia y garantía por solicitud

El determinismo pleno no está disponible con un LLM, y perseguirlo excluyendo al modelo de la
decisión descarta información que el modelo tiene. La inversión tiene el vocabulario que §2.4
acredita y el linaje que §2.9 tabula: el modelo es un sensor que emite proposiciones
tipadas, una capa simbólica determinista decide sobre la base de creencias, y la garantía toma
la única forma que puede tener:

> no *"el mismo prompt da la misma respuesta"*, falso, siempre
> sino *"la misma base de creencias da la misma decisión"*, la estabilidad de decisión de esa base,
> con la base registrada

Lo que esta sección agrega es la epistemología de la creencia misma. En los antecedentes la
procedencia es un campo de trazabilidad; en este trabajo carga el peso de la decisión como
jerarquía tipada: `COMPUTED`
(una función pura, credencia 1,0) > `OBSERVED` (medido
ejecutando una sonda) > `ELICITED` (el modelo lo afirmó, sujeto a calibración) > `ASSUMED`. Una
regla puede exigir una procedencia mínima, así que una acción irreversible puede restringirse a
evidencia computada y observada: *la opinión de un modelo de que una acción es segura no es
evidencia admisible para tomarla.*

La garantía es entonces una propiedad de la solicitud, no del sistema. Un modo global hace
que todo el tráfico pague por la solicitud más estricta. Cuatro niveles graduán el piso de
procedencia, si θ puede aprender online, si la corrida es reproducible desde caché, y qué
patrones son admisibles, el nivel certificado excluye topologías cuyo flujo de control es no
acotado, no porque sean peores (a menudo son mejores) sino porque sus modos de falla no son
enumerables. El piso se deriva de creencias sobre la solicitud: quien llama puede pedir más y
nunca menos. La derivación misma aprende, offline: una categoría de solicitudes cuyas
afirmaciones elicitadas son rechazadas repetidamente por la compuerta es una categoría
cuyo piso sube, las estadísticas de rechazo son evidencia sobre la clase de solicitud, y
consumirlas cierra el bucle sin ajustar jamás nada adentro de una solicitud.

Tres propiedades lo vuelven seguro de correr, y cada una está impuesta, no pretendida.

El evento es tipado, no parseado. Un rechazo lleva su motivo como valor, la
procedencia que se tenía contra la que la regla exigía, de modo que la estadística cuenta
el evento. Contarlo emparejando subcadenas de la explicación mediría el fraseo, y el
fraseo es prosa que se reescribe. Sólo cuentan los rechazos por PROCEDENCIA insuficiente:
una creencia rechazada por credencia baja, o por tener el valor equivocado, es el sistema
funcionando, y no dice nada sobre el régimen de evidencia de la clase.

La guarda es replicación, no utilidad. El registro se parte por tarea; una mitad
propone las regiones cuyo piso debería subir, y el piso se instala sólo si la otra mitad
(solicitudes que la propuesta nunca vio) dice lo mismo de manera independiente. La
utilidad sería el criterio equivocado para esto, y descartarla no es una concesión: subir un
piso hace que el sistema exija evidencia medida donde habría actuado sobre una
afirmación, lo que cuesta tokens y sólo puede bajar la utilidad medida en el corto plazo. Un piso de gobierno puntuado por la utilidad que
produce es un piso que nunca sube.

El aumento es acotado y monótono. Se detiene en accountable y nunca llega a
certified, porque certified además restringe qué patrones pueden correr y una estadística
sobre calidad de evidencia no es evidencia sobre certificabilidad, un piso que aprende no
puede quedar habilitado a descalificar una topología. Y nunca baja solo: la ausencia de
rechazos después de que un piso sube es justamente lo que ese piso se instaló para
producir, así que leer esa ausencia como motivo para bajarlo sería una oscilación puesta
en el diseño.

Los pisos aprendidos viajan en el bundle de política firmado, así que nada puede elevar el
nivel de una solicitud salvo por el mismo camino de promoción que recorre θ. Verificado:
una región cuyos rechazos replican a través de la partición recibe su piso; una región que
califica sólo en la mitad que la propuso, no.

Credencia y tamaño de efecto no deben confundirse. Un margen aprendido es una creencia *certera*
sobre un efecto *grande*, credencia 1,0, valor 0,9, y codificar la magnitud como credencia
reporta un hecho computado como incierto, destruyendo la distinción para la cual existe el motor.

## 6.3 Consolidación de la política de control

El aprendizaje es offline y copy-on-write. Los episodios se reproducen en orden de sorpresa y
no cronológico, lo que elimina el sesgo de recencia que la actualización online tiene por
construcción; las estadísticas se reducen en escala y las entradas sin uso se podan; y una etapa
de abstracción busca particiones de features que separen paradigmas mejor que el binning actual.

Dos disciplinas hacen esto seguro. Una política candidata se instala sólo si no regresa sobre
episodios retenidos. Y el registro se parte en tres por tarea, una parte propone
particiones, una las puntúa, una la toca sólo el guardia de promoción, porque buscar muchas
particiones contra un solo holdout es la forma en que detectar una verdad se vuelve confabularla.
Una partición descubierta entra con cero episodios, por debajo del piso de confianza, y no puede
gobernar una decisión hasta haber ganado evidencia: un sueño es una hipótesis, no un hecho.

Verificado: dado un registro donde la utilidad es independiente de todo atributo, ninguna
partición sobrevive la validación.

Dos términos, para que «episodio» y «política» no sean prosa. Un episodio es una tupla
`(κ, p, u, c)` asentada en el registro: la clave del request al momento de decidir (Definición
5.6), el brazo que corrió, la utilidad que obtuvo y su costo, más la procedencia de cada eje
de la clave. La política consolidada es la función `θ` de la Definición 5.7 materializada como
tabla de condiciones sobre ejes de la clave, con un episodio mínimo por celda antes de que una
fila pueda gobernar, firmada y versionada. Aprender es, en este paper, producir una `θ` nueva
desde episodios y dejarla entrar sólo si la guarda la deja.

> La política de control es código: una tabla de condiciones sobre features, versionada,
> firmada y evaluada de forma determinista. Un motor de *policy-as-code* (Open Policy Agent con
> reglas en Rego, o equivalente) es una realización posible de esa tabla, y no es la que este
> trabajo corre: la capa de decisión no depende de ningún motor externo (§9.1).

### 6.3.1 El sistema aprende con los pesos del sensor congelados

El sensor tiene los pesos congelados. No aprende de este despliegue, no guarda nada entre
requests, y dos llamadas idénticas no se enteran una de la otra. Y sin embargo el sistema
cambia de comportamiento con la experiencia. Ésa es la propiedad, y sale de un mecanismo de
tres pasos:

1. Cada decisión deja su huella epistémica. Al registro va la creencia que la disparó, su
   procedencia, el paradigma elegido y lo que salió. No es un log de texto: es la base de
   creencias creciendo, con la misma estructura tipada que gobierna una decisión en vivo.
2. La consolidación reproduce ese registro offline (en orden de sorpresa, no cronológico) y
   emite una política: una tabla de condiciones sobre features, versionada y firmada, que se
   ejecuta como código determinista.
3. La política entra sólo si no regresa sobre episodios retenidos, y una partición nueva
   arranca por debajo del piso de confianza: no puede gobernar hasta haber ganado evidencia.

Así que el aprendizaje vive en la base de creencias y en la política que se destila de ella,
nunca en pesos. Y de ahí sale lo que hace a esta forma valer la pena, porque son dos cosas que
normalmente se pagan una con la otra:

> Un sistema plástico suele ser opaco, y uno auditable suele ser fijo. Un artefacto
> entrenado extremo a extremo aprende y no se puede leer; una tabla de reglas escrita a mano se
> lee y no aprende. Poner el aprendizaje en la base de creencias en vez de en pesos da las dos:
> lo aprendido es un artefacto legible, diffeable, versionado y revertible, y su instalación
> pasa por una guarda. Se puede preguntar *qué* aprendió el sistema y contestarlo mostrando dos
> versiones de una tabla.

La plasticidad es una propiedad del diseño, y hereda su forma de una genealogía que §2.9
hace explícita: consolidar episodios en reglas ejecutables es lo que los sistemas de producción
hicieron con *chunking* (Soar, ACT-R), y que un par de decisiones tenga contenido propio por
encima de sus marginales es plasticidad hebbiana llevada a decisiones en vez de a neuronas. Lo
que se agrega es sostenerla cuando quien emite las creencias puede inventar con forma correcta.

### 6.3.2 Sobre qué superficies

Lo que el motor aprende no es un modelo: son políticas, que consolidan offline en un
artefacto firmado y versionado y después se ejecutan como código determinista.

| superficie | qué se aprende |
|---|---|
| ruteo | qué paradigma admite una región de features |
| herramientas | qué índice sirve a una consulta según su clase (§7.2.4) |
| pares de herramientas | qué asociación `tool_i → tool_j` predice, que un histograma marginal no captura |
| handoff | cómo repartir el alcance entre sub-agentes |
| comportamiento | el piso de garantía sube donde el registro muestra que las aserciones del modelo se rechazan |
| credencia | calibración por proposición en vez de un interruptor global de confianza |

Las dos últimas son las que cambian lo que el sistema *promete*, no lo que elige: un modelo
puede estar bien calibrado sobre cardinalidad y ser inútil sobre acoplamiento, y una política
de confianza global no puede representar eso. Qué predictores medidos alimentan hoy a cada
superficie, y con qué procedencia, está en §7.9.4.

### 6.3.3 De dónde viene esta forma

El linaje está en §2.9, con la tabla de qué supone cada línea sobre su fuente de creencias y
qué de eso rompe un sensor estocástico. Lo que importa para el argumento es la consecuencia de diseño: la
procedencia no se deriva, se declara y se verifica, y esa inversión es la que permite que las
ocho líneas sigan funcionando cuando la fuente puede inventar con forma correcta.

### 6.3.4 La afirmación de transferencia, y su refutación medida

La lectura se completa con un condicional: *si el corpus es representativo del dominio, la
capa ajustada debería transferir*. Eso es falsable, y este registro ya lo falsó una vez.

> **P15.** Sobre un mundo que la política nunca había visto (seed 47, 390 celdas, cero
> errores de infraestructura, modelo `gpt-5.4-nano`) el ruteo por request perdió contra el
> mejor paradigma fijo por −0,087, más allá del piso de ruido, mientras reproducía cada
> decisión 26/26 desde su base de creencias registrada. §7.8.1 lo desarrolla como primer
> episodio del ciclo.

El mecanismo es el hallazgo, no el número. El vocabulario de región no tiene eje de
horizonte, así que las tareas que castigan una elección fija eran indistinguibles de las
que la premian. La política ruteó contra su propio veredicto registrado porque ninguna
etiqueta le dijo nunca en qué caso estaba. Chequeo de sensibilidad: reparar la validez del
aprendizaje (agregación por episodio, holdout limpio) deja el número idéntico, así que la
refutación no es un artefacto del procedimiento.

Eso afila la condición hasta volverla chequeable:

> La representatividad hay que enunciarla sobre los ejes que el vocabulario de región
> distingue. «Representativo del dominio» no alcanza. Un corpus que varía en una dimensión
> que el mapa de features no mira produce episodios que la política no puede separar, y
> entonces aprende un promedio sobre dos poblaciones. La condición se puede chequear sobre
> un corpus *antes* de correrlo, porque la región es una función determinista de los
> features.

### 6.3.5 Una consecuencia afirmable

Más inferencia no compra más ajuste. La consolidación es replay sobre el registro, así
que el costo de aprender es cero llamadas: lo que la cuota compra son *episodios*, y el
ajuste es gratis sobre los que haya. Eso separa dos decisiones que se suelen tomar juntas,
cuánto medir lo gobierna la potencia estadística, cuánto entrenar no lo gobierna nada.

Y es observable mientras una campaña corre. Sobre la campaña actual, 516 filas dan 141
episodios sobre 6 regiones, 57 pares `(región, paradigma)` con evidencia y 27 con
`n ≥ 3`, leído del registro entre dos tandas, sin costo adicional. La potencia estadística
la fija el corpus, no la cuota: un par junta un episodio *por tarea* de su región, así
que cruzar el piso de evidencia exige esa cantidad de tareas. Gastar más agrega tareas, y
sólo cuentan si caen en la región justa.

---

# 7. Resultados

## 7.0 Preguntas de investigación

Las mediciones de esta sección contestan ocho preguntas, y cada una tiene un criterio de
decisión fijado antes de mirar el dato. Las predicciones falsables quedaron registradas con
fecha en el cuaderno del laboratorio; en esta tabla se enuncia lo que cada una decide. Las
preguntas van ordenadas por la contribución a la que responden, no por el orden en que se
midieron, y la última columna dice sobre qué modelo y qué registro corre cada una, porque no
es el mismo en todas.

| | contribución | pregunta | criterio | sección | modelo y registro |
|---|---|---|---|---|---|
| **PI1** | la máquina | ¿Cuánta varianza de trayectoria hay en el régimen no confinado, y confinarla cambia el resultado? | fracción de celdas con `pass^k < pass@1`, y el efecto de absorber ramificaciones sobre una celda con `d > 0` | §7.2 | `luna`, campaña 78 × 12 × 3 |
| **PI5** | la interfaz | ¿Las capacidades declaradas transfieren a un paradigma no visto? | error de predicción dejando un paradigma afuera, contra el nulo de capacidades barajadas | §7.4 | `luna`, rectángulo 64 × 8 |
| **PI6** | la interfaz | ¿La ontología de la pregunta separa a los brazos mejor que la partición estructural? | señal/ruido entre brazos dentro de cada segmento, controlado por número de segmentos | §7.4.3 | `luna`, registro completo, sobre la etiqueta de diseño |
| **PI2** | el ciclo | ¿Elegir paradigma por identidad captura brecha de oráculo neta positiva? | brecha observada menos el piso de ruido por remuestreo, en muestra y sobre held-out | §7.3, §7.7 | `luna`, 59 × 8 y held-out 26 × 12 × 3 |
| **PI3** | el ciclo | ¿Existe una señal disponible al decidir que explique la interacción tarea×paradigma? | fracción de `γ` explicada, contra el máximo de los nulos por permutación (corrección por selección) | §7.3.2 | `luna`, 59 × 8 |
| **PI7** | el ciclo | ¿Cada refutación del ruteo produjo un sensor nuevo que la siguiente corrida pudo usar, sin romper la reproducibilidad? | por episodio: el eje que faltaba, si es `COMPUTED`, y decisión reproducida desde la base registrada | §7.8 | `nano`, tres mundos de 26 tareas, anteriores a la campaña |
| **PI8** | lo que compra | ¿Qué aprende la política que pague fuera de muestra, y qué predice el comportamiento de un brazo antes de correrlo? | desempate por costo leave-one-task-out; participación del paradigma en la varianza del recall; efecto de una herramienta ofrecida sobre el releído | §7.3.5, §7.9 | `luna` en §7.3.5 y §7.9.2; `nano` en §7.9.1 |
| **PI4** | lo que compra | ¿El acuerdo entre paradigmas predice corrección sin oráculo ni juez? | `P(correcta \| k coinciden)`, con tres controles: dificultad de tarea, largo de respuesta y costo | §7.5 | `luna`, con réplica en `terra` |

Dos secciones de este capítulo, §7.8 y §7.9.1, no salen de la campaña sino del registro
anterior a ella, sobre `gpt-5.4-nano`. Se incluyen porque miden algo que la campaña no puede
medir, el ciclo de reparación del vocabulario y su mecanismo, y §7.8.0 dice qué transfiere.

Tres términos que el paper usa con precisión. Una celda es un par tarea × paradigma, y es
la unidad de medición. Un modo es una de las once clases de falla del corpus (§1.3). La
etiqueta de diseño es el modo del que salió una tarea: se conoce al construirla y no al
decidir, así que en §7.3.2 funciona como cota superior y nunca como señal disponible.

Régimen de medición. Doce paradigmas sobre condiciones idénticas (mismo corpus, mismo modelo, misma superficie de herramientas, misma decodificación) con `repeat = 3`, sin juez LLM,
con el corrector auditado (§7.0.1), y cada panel declarando su rectángulo. Los fallos de
infraestructura se registran como tales y se excluyen de toda estadística: la campaña tuvo
cero.

### 7.0.1 Validez del corrector

El pitfall más caro de un banco de agentes es que sus ceros no sean del sistema sino del
corrector: una auditoría manual de fallos en un benchmark público de código encontró que el
59,4% de los fallos atribuidos al modelo eran defectos del arnés de evaluación. Acá el
corrector se audita con una prueba automática que barre toda respuesta con utilidad cero y
marca las que traen señal de defecto de emparejamiento (el oráculo presente en la respuesta sin sobrantes, un rechazo no reconocido, un ítem parcial no acreditado, un número equivalente con otro formato). Sobre 567 ceros, ninguno presenta señal fuerte. La auditoría no prueba
que el corrector sea correcto: prueba que esas cuatro clases de defecto no están.

> La campaña homogénea, y es la única fuente de los números de esta sección. Doce
> paradigmas × 78 tareas × 3 réplicas sobre un corpus con entidades reales, un modelo, mismas
> condiciones, sin juez LLM y con el corrector auditado: 121,4M tokens, cero errores de
> infraestructura. Toda `u` usa `λ = 0` (calidad pura, con el costo en su propia columna) y
> cada panel declara su rectángulo.

## 7.1 Los doce paradigmas, en una tabla

Las secciones que siguen miden a cada brazo por un lado distinto (cobertura, degradación con el ancho, fiabilidad, latencia, decisiones delegadas) y cada una tiene su tabla. Ésta las
junta, porque cinco tablas que nadie cruza son menos útiles que una que declara sus
denominadores.

| brazo | aplica | u | u × aplica | pass^3 | tok/celda | USD/1k celdas | serie | ley de costo |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| `react` | 100% | 0,850 | 0,850 | 0,734 | 108.137 | 22 | 1,35 s | vueltas |
| `dag_strategy` | 100% | 0,830 | 0,830 | 0,703 | 105.293 | 22 | 2,87 s | vueltas |
| `reflection` | 100% | 0,808 | 0,808 | 0,688 | 133.574 | 27 | 1,76 s | vueltas |
| `rewoo` | 100% | 0,678 | 0,678 | 0,531 | 10.840 | 2 | 0,77 s | estructural |
| `supervisor` | 100% | 0,591 | 0,591 | 0,406 | 64.079 | 13 | 2,66 s | vueltas |
| `gist_reader` | 100% | 0,584 | 0,584 | 0,516 | 23.075 | 5 | 0,91 s | vueltas |
| `handoff` | 96% | 0,604 | 0,581 | 0,438 | 120.500 | 27 | 2,04 s | alcance |
| `pointer_chase` | 96% | 0,515 | 0,492 | 0,359 | 9.787 | 2 | 1,38 s | vueltas |
| `graph_traverse` | 52% | 0,511 | 0,266 | — | 21.356 | 4 | — | estructural |
| `streaming_scan` | 12% | 0,750 | 0,090 | — | 26.380 | 5 | — | estructural |
| `extract_compute` | 12% | 0,583 | 0,070 | — | 26.184 | 5 | — | estructural |
| `direct` | 6% | 0,917 | 0,055 | — | 22.822 | 5 | — | estructural |

Los denominadores, y son tres. `aplica`, `u`, `u × aplica` y `tok/celda` salen del registro
entero y se recomputaron contra él el 2026-09-01 (2.511 filas, cero `infra_error`): `aplica`
es qué fracción de las celdas ofrecidas a ese brazo pasa la compuerta aritmética de
factibilidad, y `u` promedia sólo las que pasan. `pass^3`, `serie` y `USD` son del cierre de
campaña del 2026-08-30 y no se recomputaron; los dos brazos cuyo registro se corrigió después
de ese cierre son `handoff`, por una corrección de contabilidad de la superficie compartida, y
`graph_traverse`, por una re-corrida de sus celdas anchas, y sus filas dicen el valor vigente
en las cuatro primeras columnas. `pass^3` y `serie` salen del rectángulo de 64 tareas × 8
brazos (el 82% de las medidas) porque exigen que todos los brazos hayan corrido las mismas
tareas con tres réplicas cada una; los cuatro brazos sin valor son los que la factibilidad
poda en casi todas las celdas. Toda `u` usa `λ = 0`: calidad pura, con el costo en su propia
columna.

Cuatro cosas que sólo se ven con las columnas juntas:

1. `u` y `u × aplica` son dos números y ninguno reemplaza al otro. `direct` es el mejor
   del plantel donde su mecanismo corre (`0,917`) y aporta `0,055` sobre el corpus porque
   corre en el 6% de las celdas. No falla en el 94% restante: no corre, y eso lo decide la
   aritmética antes del primer token.
2. `pass^3` siempre está por debajo de `u`, y la distancia no es proporcional. `react`
   pierde `0,116` y `supervisor` `0,185`. Esa diferencia es varianza que vive *dentro* de una
   celda, invisible para cualquier piso de ruido calculado entre brazos.
3. La columna de dólares no es la de tokens reescalada. Entrada y salida se cobran 6×
   distinto, y los brazos se diferencian justo en esa proporción: dos brazos pueden costar lo
   mismo en dólares con miles de tokens de diferencia por celda, según cuánto de cada uno sea
   salida.
4. El margen está en la última columna, no en la primera. Entre `react` y `rewoo` hay
   `0,172` de utilidad y un factor 11× de costo y 1,8× de latencia serial. En utilidad
   los brazos se separan por centésimas; en lo que cuestan, por órdenes de magnitud.

> El `pass^3` de esta tabla y el de §7.2.2 son rectángulos distintos y no se deben cruzar.
> Acá sale de las 64 tareas comunes a los ocho brazos; allá, del subconjunto donde los cuatro
> brazos comparados corrieron sus tres réplicas, que es más chico y más fácil. De ahí que `react`
> figure con `0,734` en esta tabla y `0,797` en §7.2.2.

> `pointer_chase` figura en esta tabla con su número de campaña. Las cuatro correcciones de §7.2.4
> (que lo llevan de `0,33` a `0,89` en la celda de cadenas acopladas) son posteriores a esta
> corrida y tocan 3 de las 78 tareas, así que su efecto sobre el agregado del corpus está
> dentro del ruido y no se propagó a esta tabla. Se dice en el cuerpo y no al pie porque una tabla
> que mezcla dos versiones del mismo brazo sin declararlo es exactamente el defecto que este
> paper audita en otras partes.

### 7.1.1 Un paradigma tiene dos números y colapsarlos esconde el caso que importa

| brazo | aplica | u donde aplica | u × cobertura | tokens/celda |
|---|---:|---:|---:|---:|
| `react` | 100% | 0,850 | 0,850 | 108.137 |
| `dag_strategy` | 100% | 0,830 | 0,830 | 105.293 |
| `reflection` | 100% | 0,808 | 0,808 | 133.574 |
| `rewoo` | 100% | 0,678 | 0,678 | 10.840 |
| `handoff` | 96% | 0,604 | 0,581 | 120.500 |
| `supervisor` | 100% | 0,591 | 0,591 | 64.079 |
| `gist_reader` | 100% | 0,584 | 0,584 | 23.075 |
| `pointer_chase` | 96% | 0,515 | 0,492 | 9.787 |
| `graph_traverse` | 52% | 0,511 | 0,266 | 21.356 |
| `streaming_scan` | 12% | 0,750 | 0,090 | 26.380 |
| `extract_compute` | 12% | 0,583 | 0,070 | 26.184 |
| `direct` | 6% | 0,917 | 0,055 | 22.822 |

![Bueno donde aplica, contra lo que aporta sobre el corpus](figuras/aplica-contra-aporta.svg)

Un paradigma tiene dos números y colapsarlos esconde el caso que importa. `direct` es el
mejor del plantel donde su mecanismo corre (0,917) y su mecanismo corre en el 6% de las
celdas (12 filas de 201, y ese número va junto al porcentaje porque «el mejor del plantel» sobre doce filas es una afirmación de otra clase que sobre doscientas), porque la aritmética de factibilidad lo poda en cuanto el material no entra. Sobre el
corpus aporta 0,055. Reportar un solo número obliga a elegir cuál de las dos afirmaciones
falsear.

La cobertura es una propiedad de la intersección entre el mecanismo del brazo y la
distribución de tareas, no del brazo solo, y por eso se decide antes de gastar: `direct`, `streaming_scan` y
`extract_compute` no fallan en el 88–94% restante, no corren.

### 7.1.2 La degradación con el ancho separa lo que la utilidad media junta

![Cómo se degrada cada brazo cuando el material crece](figuras/degradacion-por-ancho.svg)

El eje son los tres anchos declarados (5, 20 y 60 unidades). Las tareas sin sufijo de
ancho quedan fuera: agrupan celdas de 1, 8, 9 y 60 unidades, así que no son el extremo
angosto de nada y meterlas convertía el eje en algo que no está ordenado.

| brazo | w4 (5 u.) | w16 (20 u.) | w48 (60 u.) | Δ |
|---|---:|---:|---:|---:|
| `react` | 0,94 | 0,82 | 0,81 | −0,13 |
| `dag_strategy` | 0,83 | 0,83 | 0,80 | −0,03 |
| `reflection` | 0,89 | 0,80 | 0,71 | −0,18 |
| `rewoo` | 0,60 | 0,73 | 0,66 | +0,06 |
| `handoff` | 0,72 | 0,62 | 0,51 | −0,22 |
| `supervisor` | 0,64 | 0,59 | 0,43 | −0,20 |
| `gist_reader` | 0,86 | 0,59 | 0,42 | −0,45 |
| `pointer_chase` | 0,68 | 0,49 | 0,39 | −0,30 |
| `graph_traverse` | 0,91 | 0,44 | 0,42 | −0,49 |

Todos se degradan menos uno. `graph_traverse` pierde 0,49 y `gist_reader` 0,45 al pasar
de 5 a 60 unidades, el gist de 180 caracteres y el índice de entidades dejan de discriminar
cuando hay sesenta candidatos. `rewoo` es la única excepción, y sube: `+0,06`. No es
casualidad, es el único brazo cuyo costo no es función del alcance.

Un promedio sobre anchos que no separara los tres declarados habría acercado a `gist_reader` y
a `rewoo`, y habría escondido que uno se desploma exactamente donde el otro se sostiene.

### 7.1.3 Tres clases de costo, y no son las del catálogo

Ajustando `log(costo)` contra `log(alcance)` por brazo, y preguntando por separado qué
explica mejor el costo (el alcance o la cantidad de vueltas) aparece una taxonomía que
corta transversal a la de control de flujo:

| clase | brazos | qué la define |
|---|---|---|
| alcance | `handoff` | `R² = 0,77` contra el alcance, exponente 0,73. El costo lo fija cuánto material arrastra cada llamada |
| vueltas | `react`, `reflection`, `dag_strategy`, `supervisor`, `gist_reader`, `pointer_chase` | el costo lo fija cuántas veces itera, y eso es endógeno: gasta hasta que algo lo detiene |
| estructural | `rewoo`, `direct`, `graph_traverse`, `extract_compute`, `streaming_scan` | ni una ni la otra: el costo está fijado por la forma del patrón |

El dato que obliga a separar estas clases de los techos declarados: `handoff` tiene un
techo de 12 llamadas y gasta 120.500 tokens; `dag_strategy` tiene uno de 160 y gasta
105.293. Del mismo orden, con un factor 13 de diferencia en el techo.

> Contar llamadas para acotar esfuerzo es contar envases para acotar peso.

Y una consecuencia operativa: la clase vueltas es la única sobre la que una regla de
parada puede actuar. Medido en el mismo registro, el 46,5% de las búsquedas de `react` no
traen ninguna unidad nueva, con rachas de hasta 14.

### 7.1.4 El espacio de capacidades

![El espacio de capacidades](figuras/espacio-capacidades.svg)

La taxonomía de control de flujo («plan-ejecuta», «supervisor», «cadena») no predice
rendimiento. Lo que sí predice es qué capacidades le da cada topología al modelo, y son
tres:

| eje | qué es | de dónde sale |
|---|---|---|
| payload por llamada | cuántas unidades ve el modelo de una vez | del código |
| adaptabilidad | ¿puede corregir el plan tras ver un resultado? | del código |
| ley de costo | de qué es función su costo | medida |

Las dos primeras se leen del código, y por eso ubican a un brazo que todavía no se
corrió, cosa que una tabla de resultados no puede hacer.

El caso que las valida es la pregunta de contradicción, donde la respuesta es una relación
entre dos unidades y ninguna unidad la contiene:

| capacidades | utilidad |
|---|---:|
| payload ≥ 2 unidades y adaptabilidad | 0,71 – 0,91 |
| sólo payload | 0,13 |
| ninguna | 0,00 – 0,40 |

`handoff` lee las dos unidades relevantes y saca 0,067, porque cada sub-agente ve su
mitad y ninguna llamada tiene el par. La capacidad que cuenta es tenerlas juntas, no leerlas.
Y `rewoo` saca 0,133 aunque *puede* tenerlas juntas, porque le falta la otra, poder elegir
cuáles dos exige ver un resultado antes de pedir el siguiente.

En la figura, `react`, `dag_strategy` y `reflection` caen prácticamente en el mismo punto.
Eso no es un defecto del dibujo: son el mismo brazo para decidir, y por eso sus
utilidades quedan dentro de 0,05 entre sí.

### 7.1.5 Dónde está el margen

![El negocio de cada brazo](figuras/utilidad-contra-costo.svg)

En el ancho mayor, `react` saca 0,81 a 108.137 tokens por celda y `rewoo` 0,66 a 10.840:
+0,15 de utilidad por un factor 10 de costo. Y el costo es casi enteramente de entrada
(de 98,6% a 100,0% según el brazo, con la salida entre 0,0% y 1,4%), lo cual dice que los
paradigmas no se diferencian en lo que generan sino en lo que arrastran al prompt. Es la
misma afirmación que la ley de costo, medida por otro lado.

> Un brazo queda afuera del rango. En `graph_traverse` la suma de
> entrada y salida da `101,9%` del costo registrado. Entrada y salida son las dos particiones
> del mismo total, así que por encima de 100% no hay una tercera categoría: es un defecto
> de contabilidad de ese brazo, no una propiedad medida. Se excluye del rango y queda
> anotado como deuda, no como hallazgo.

### 7.1.6 La ley de costo, dibujada

![La ley de costo](figuras/ley-de-costo.svg)

El paper afirma desde el principio que el costo de un bucle de herramientas crece como `N²`
y la cobertura como `N`, porque la conversación se reenvía entera en cada vuelta. Hasta
esto lo sostenían dos números sueltos («≤2 llamadas dan 9.779 tokens, ≥8 dan 136.432») y esos
dos son compatibles con crecimiento lineal si uno no mira el resto.

Hacen falta dos paneles y no uno, porque un total creciente no distingue «cada llamada
cuesta lo mismo y hay más llamadas» de «cada llamada cuesta más». El panel derecho separa las
dos: si no hubiera reenvío, esas líneas serían planas.

| brazo | 3-5 llamadas | 11-12 llamadas | factor |
|---|---:|---:|---:|
| `dag_strategy` | 4.002 | 15.592 | 3,9× |
| `supervisor` | 6.052 | 12.910 | 2,1× |
| `pointer_chase` | 1.544 | 4.107 | 2,7× |
| `reflection` | 9.410 | 35.030 | 3,7× |

El panel derecho condiciona por brazo, y esa es la única forma de leerlo. Agregado sobre
todos, el costo por llamada zigzaguea (7.411, 18.654, 29.528, 13.815, 19.113) porque distintos
brazos dominan distintos conteos de llamadas y sus alcances difieren en un orden de magnitud:
«más llamadas» y «qué brazo» quedan confundidos, y el zigzag es esa confusión y no el fenómeno.
Condicionado por brazo el trazo sube monótono en los cuatro que tienen puntos suficientes.

No se estima ningún exponente ni se reporta un `R²`: las curvas `N` y `N²` del panel izquierdo
están ancladas en el primer punto para que el ojo compare, y el hallazgo es cualitativo. Con
`n` desparejo por punto (de 26 a 540 filas) un exponente ajustado tendría más precisión
aparente que evidencia.

## 7.2 Dónde entra la varianza del sensor, y cómo el motor la confina

Las secciones anteriores comparan brazos. Ésta abre uno: por qué gana el más simple, qué
varianza esconde el promedio, y qué pasa cuando una decisión de control se le saca al
modelo. Las tres preguntas se contestan sobre el mismo registro, sin gastar un token más.


> CADA PANEL DECLARA SU RECTÁNGULO, y por eso `u` toma valores distintos según qué se
> compare. `react` figura con `0,850` en §7.1.1, `0,843` en §7.2.1 y `0,875` en §7.2.2: son
> tres poblaciones distintas, cada una elegida por lo que la pregunta de esa sección exige.
>
> | sección | panel | por qué ése |
> |---|---|---|
> | §7.1.1 | 78 tareas × 12 brazos, cada brazo sobre las celdas donde CORRIÓ | mide cobertura y aporte, que exigen incluir a los brazos podados |
> | §7.2.1 | 64 × 8 (rectángulo completo) | el embudo compara etapas entre brazos: exige que todos hayan corrido las mismas tareas |
> | §7.2.2 y §7.3 | 59 × 8 (rectángulo con ≥3 réplicas) | `pass^3` y la descomposición necesitan las tres réplicas de cada celda |
>
> La regla del rectángulo se aplica desde un solo lugar y devuelve también lo descartado:
> un panel que se achica sin declarar cuánto miente por omisión. Toda `u` reportada usa
> `λ = 0` (calidad pura, con el costo en su propia columna) salvo donde se indique lo
> contrario.

### 7.2.1 El embudo: `react` no gana buscando

![Ver contra usar](figuras/embudo-ver-contra-usar.svg)

La utilidad de una celda es el producto de dos cosas que fallan por razones distintas:

    u  ≈  P(vio TODAS las unidades portadoras)  ×  P(contestó bien | las vio)

| brazo | u | vio | u \| vio | u \| no vio | leídas |
|---|---:|---:|---:|---:|---:|
| `react` | 0,843 | 60% | 0,970 | 0,708 | 7,8 |
| `dag_strategy` | 0,822 | 57% | 0,945 | 0,720 | 11,6 |
| `gist_reader` | 0,611 | 77% | 0,594 | 0,667 | 28,8 |
| `supervisor` | 0,577 | 40% | 0,778 | 0,479 | 6,8 |

`react` no ve más que nadie, 60%, y `gist_reader` ve el 77%. Toda su ventaja está en la
segunda etapa: con el material a la vista da 0,970, y `gist_reader` da 0,594, *peor que
cuando no lo vio todo*. Pareado por tarea, `Δvio` es chico o negativo y `Δ(u|vio)` se lleva
la brecha entera.

> El mecanismo: cada representación intermedia más chica que el material es una pérdida
> que no se recupera aguas abajo. Un gist de 180 caracteres, una ventana recortada para el
> sub-agente, un índice de entidades, los tres tiran información *antes* de saber cuál
> hacía falta. `react` no tiene ninguna.

La simplicidad no es en este caso una virtud estética: es la ausencia de un canal con pérdida, y
eso se mide.

### 7.2.2 `pass^k`: el promedio esconde la mitad que importa

> `pass^k` NO es `pass@k`, y significa casi lo opuesto. En la literatura de código
> `pass@k` mide «al menos un acierto en `k` intentos» y crece con `k`. `pass^k` mide «los
> `k` intentos acertaron todos» y decrece con `k`. El nombre viene de `tau2-bench`, que lo
> introdujo para agentes multi-turno por esta misma razón; lo conservamos por consistencia con
> esa literatura y se señala porque el parecido tipográfico invita a leer la tabla al
> revés.

Todo lo anterior es `pass@1` (el promedio sobre réplicas) y responde «cuánto acierta».
`pass^k` responde «se puede contar con que acierte», que para un sistema que promete
«misma base de creencias ⟹ misma decisión» es la mitad que importa.

| brazo | pass@1 | pass^3 | caída | celdas inestables |
|---|---:|---:|---:|---:|
| `react` | 0,875 | 0,797 | −0,078 | 17% |
| `dag_strategy` | 0,874 | 0,763 | −0,112 | 20% |
| `rewoo` | 0,718 | 0,576 | −0,142 | 27% |
| `supervisor` | 0,637 | 0,441 | −0,196 | 34% |

Entre el 17% y el 34% de las celdas cambian de resultado entre réplicas, con `t=0`,
semilla fija y la misma huella.

> La varianza de una llamada y la de una trayectoria son cantidades distintas. Sobre una
> llamada, la varianza del sensor se manifiesta como un token distinto: el resultado se mueve
> poco y de forma acotada. Sobre una trayectoria, una elección distinta en el paso uno cambia
> qué documento se lee en el paso dos, y de ahí en adelante las dos réplicas ya no comparan
> la misma evidencia. La varianza no se promedia: se ramifica.
>
> Si la trayectoria delega `d` puntos de ramificación a la salida del modelo, la trayectoria es una variable aleatoria
> sobre un árbol de profundidad `d`. Con `d = 0` la trayectoria es fija, y la varianza del
> sensor entra únicamente como el contenido que extrae de cada nodo: un error acotado y
> localizable en vez de una historia distinta.

Esta varianza es invisible para el instrumento habitual: vive dentro de una celda, así que
ningún piso de ruido calculado *entre* brazos la muestra. Por eso hace falta `pass^k`, y por
eso no basta con más réplicas del mismo promedio.

### 7.2.3 En una cadena acoplada, el modo dominante es cortarla un escalón antes

![Modos de falla de C3](figuras/c3-modos-de-falla.svg)

`C3_coupled_chain` pide subir N escalones de una línea de reporte sobre 60 unidades y
reportar un dato del último. La cadena está minada a propósito: cada unidad del camino
lleva un dato del mismo tipo pegado al nombre que la ancla, el enlace va por anáfora
(«The above-named», «That person»), y el destino del salto viene abreviado (`A. Vallejos`
apunta a `Agustina Vallejos`).

Clasificar las respuestas por modo, y no por puntaje, invierte el diagnóstico. El modo
dominante es cortarla un escalón antes (7 casos), y no saltarse la cadena (2). Los
brazos devuelven el dato de un intermedio, que está a la vista y es indistinguible del
correcto. Y `dag_strategy`, que gana la celda, no encadena mejor: hace 12 correctas, 3
abstenciones y cero respuestas equivocadas. Los demás contestan igual.

> El banco puntúa «se abstuvo» y «contestó mal» los dos con 0,000. Es correcto para medir
> utilidad y ciego justo en el eje que el motor de decisión existe para gobernar.

### 7.2.4 Sustituir una ramificación delegada al modelo por un medidor de entorno

Sobre ese diagnóstico se corrigió `pointer_chase` (el brazo cuyo mecanismo *es* seguir cadenas y que sacaba 0,33 en C3). Cuatro correcciones, todas de flujo de control o de
tipado, ninguna de fraseo:

1. Regla de creencias: una entidad nombrada se busca con el índice léxico, no con el
   híbrido. Un vector denso codifica *de qué habla* un texto, y sesenta documentos con la
   misma plantilla hablan de lo mismo; el nombre propio es justo la parte que no es
   semántica, y fusionarle la rama densa le mete ruido a la única señal que discrimina.
   Medido: el híbrido devuelve la unidad equivocada para `Ramiro Herrera` y deja a
   `M. Arrieta` fuera del top-5; el léxico las pone primera y tercera.
2. La salida del sensor se tipa antes de usarse. El modelo emitía
   `'M. Arrieta settlement account'`, y esa cola arrastraba la consulta a clasificar como
   prosa: la regla era correcta y la entrada estaba sucia.
3. Un salto a una unidad que no nombra a quien se persigue no es un salto, y entre
   candidatos empatados gana el que la nombra antes, un documento que trata *sobre* una
   entidad la nombra antes que uno que la referencia de paso. Se resuelve con predicados que
   devuelven un booleano o una posición, nunca texto: no cuestan un token.
4. El ancla es el salto cero y lo resuelve el código. Era una llamada al modelo, y ahí
   quedaba la última decisión de flujo en manos del sensor.

![Una ramificación delegada, resuelta por código](figuras/sensor-determinista.svg)

El panel izquierdo dibuja cada réplica por separado, y ahí se ve lo que un promedio
esconde. El «antes» era inestable, no peor en promedio. La misma pregunta, la misma
huella y los mismos resultados de búsqueda daban 1,000 o 0,000 según la réplica. El panel
derecho muestra los dos ejes moviéndose juntos, que es la afirmación entera.

![Flujo de control del Algoritmo 1](figuras/algoritmo-1-flujo.svg)

**Algoritmo 1.** La caminata, con la frontera modelo/código explícita. `SENSOR` es la única
llamada al modelo y devuelve una proposición; todo lo demás lo decide el código.

```
ALGORITMO 1  Caminata determinista sobre una cadena de referencias
────────────────────────────────────────────────────────────────────────────────
Entrada : pregunta q, vista del corpus V, plantel de índices I
Salida  : valor pedido, o ABSTENER

 1  n  ← saltos_declarados(q)              ▷ forma cerrada sobre q; ∅ si no declara
 2  e  ← sujeto_declarado(q)               ▷ forma cerrada sobre q
 3  ι  ← índice_para(e)                    ▷ REGLA DE CREENCIAS: entidad ⇒ léxico
 4  u  ← primer_hit_que_nombra(buscar(ι, e, κ), e, ∅)      ▷ ancla = salto cero
 5  if u = ⊥ then return ABSTENER
 6  camino ← ⟨u⟩
 7  for i ← 1 to n do                      ▷ el LARGO lo fija q, no el modelo
 8      τ ← leer(u)
 9      ρ ← SENSOR(τ, «¿hacia dónde sigue el rastro?»)     ▷ ← única llamada
10      ρ ← entidad_en(ρ)                  ▷ se TIPA la salida del sensor
11      ι ← índice_para(ρ)
12      u ← primer_hit_que_nombra(buscar(ι, ρ, κ), ρ, camino)
13      if u = ⊥ then return ABSTENER      ▷ cadena incompleta ⇒ no se responde
14      camino ← camino ⌢ ⟨u⟩
15  return SENSOR(leer(camino[n]), «el valor pedido»)      ▷ ← el CÓDIGO fija cuál
────────────────────────────────────────────────────────────────────────────────
primer_hit_que_nombra(C, ρ, visitadas):
16  A ← {c ∈ C \ visitadas : c menciona ρ en forma COMPLETA}    ▷ ancla
17  M ← {c ∈ C \ visitadas : c menciona ρ en forma ABREVIADA}   ▷ referencia
18  return argmin_{c ∈ (A si A≠∅ si no M)} posición_primera_mención(c, ρ)
```

Las cuatro líneas que son el aporte. La 3 y la 11 aplican la regla de creencias: una
entidad nombrada se busca con el índice léxico, porque un vector denso codifica *de qué habla*
un texto y sesenta documentos con la misma plantilla hablan de lo mismo. La 10 tipa la salida
del sensor antes de usarla: el modelo emite prosa, y esa prosa arrastraría la consulta a
clasificarse mal. La 7 pone el largo bajo control del código. Y la 4 resuelve el ancla como
cualquier otro salto, en vez de preguntárselo al modelo.

Las líneas 16–18 son el desempate, y son la parte que no es obvia: entre candidatos que
mencionan la entidad, el que la nombra en forma completa es el que trata sobre ella y el
que la abrevia sólo la referencia; con empate, gana el que la menciona antes. Ambas pruebas
son predicados sobre el índice (devuelven un booleano o una posición, nunca texto) así que no
cuestan un token.

Resultado: `pointer_chase` pasa de 0,33 a 0,89 en C3, empatando al mejor brazo de la
celda. Y la corrección (4) prueba el punto por sí sola: con la misma huella y los mismos
resultados de búsqueda, la réplica 0 elegía el ancla correcta y recorría la cadena entera
(u=1,000) mientras las réplicas 1 y 2 elegían otra y sacaban 0,000. Una decisión de flujo en
el sensor se lleva puesto el determinismo.

> La hipótesis, y es falsable: sustituir una ramificación de control delegada al modelo por un medidor
> determinista sobre una señal del entorno mejora la utilidad y el determinismo a la vez.
> `pass^k` es la métrica que faltaba para medir el segundo efecto, y sin ella la mitad de la
> mejora era invisible.

Lo que queda declarado y no resuelto: la réplica que todavía falla se abstiene en vez de
contestar mal, que es el comportamiento buscado y que el banco puntúa igual que un error.

### 7.2.5 La latencia serial varía 3,6× entre paradigmas y no entra en ninguna decisión

![Latencia serial](figuras/latencia-serial.svg)

Hay dos relojes y confundirlos invalida el número. El tiempo de pared no sirve: el 63-67%
de las filas de `react` y `dag_strategy` están por debajo de medio segundo porque son replays
del caché en disco, eso mide cuánto tarda el banco en releer, no cuánto tarda el sistema en
contestar. Lo que sí sirve viene del proveedor, en el objeto `usage` de cada respuesta, y por
eso el caché lo conserva: es la latencia de la llamada que efectivamente se hizo.

| brazo | u | primer token | latencia serial | u por segundo |
|---|---:|---:|---:|---:|
| `react` | 0,843 | 265 ms | 1,35 s | 0,62 |
| `dag_strategy` | 0,822 | 410 ms | 2,87 s | 0,29 |
| `rewoo` | 0,677 | 304 ms | 0,77 s | 0,88 |
| `supervisor` | 0,577 | 360 ms | 2,66 s | 0,22 |

El primer token es prácticamente igual en todos (250 a 410 ms, es una llamada al mismo modelo). Lo que cambia 3,6× es la latencia serial: la suma sobre todas las llamadas, o
sea la parte que no se acelera con más tokens por segundo porque cada llamada espera a la
anterior. Es la ley de costo `turn-driven` cobrada en tiempo del usuario en vez de en tokens,
y es un eje que ninguna decisión del ruteador mira hoy.

Y no destraba nada, que es lo que hay que decir: `react` es a la vez el de mayor utilidad y
el de menor latencia serial entre los contendientes. El único que compra tiempo es `rewoo`
(1,8× más rápido) y cuesta 0,165 de utilidad. Es un intercambio explícito, no un almuerzo
gratis: sólo lo compra quien tenga un techo de latencia declarado.

### 7.2.6 La varianza de trayectoria no crece con el número de ramificaciones

La sección anterior invita a una conjetura general, y el registro la refuta en su forma
ingenua:

> Si un brazo delega `d` decisiones de control al modelo, y cada una vuelve a salir igual
> entre réplicas con probabilidad `q`, entonces `pass^k ≈ pass@1 · q^d`. Más decisiones en el
> sensor ⟹ menos determinismo, multiplicativamente.

Es contable: `d` se mide como iteraciones por celda, y `pass^3` ya está. Sobre los ocho brazos
del panel:

| brazo | decisiones | pass@1 | pass^3 | `q` implícita |
|---|---:|---:|---:|---:|
| `dag_strategy` | 8,9 | 0,822 | 0,703 | 0,983 |
| `supervisor` | 8,6 | 0,587 | 0,406 | 0,958 |
| `reflection` | 5,9 | 0,798 | 0,688 | 0,975 |
| `react` | 4,3 | 0,843 | 0,734 | 0,968 |
| `pointer_chase` | 3,8 | 0,515 | 0,359 | 0,909 |
| `rewoo` | 2,0 | 0,688 | 0,531 | 0,879 |
| `gist_reader` | 1,9 | 0,611 | 0,516 | 0,913 |

La correlación entre número de decisiones y caída de `pass^3` es `r = −0,24` con `n = 8`,
débil, y con el signo contrario al que la conjetura predice: los brazos con más decisiones
pierden *menos*. La explicación que el propio dato sugiere es que una decisión no sólo agrega
varianza sino también una oportunidad de corregir: un brazo adaptativo que dobla mal puede
volver, y uno de dos llamadas no. Los dos efectos casi se cancelan en este corpus.

Lo que sí se sostiene, y es más útil que la conjetura original, son dos cosas:

1. `q` está acotada lejos de 1 para todos. El máximo es `0,983` (`dag_strategy`) y el
   mínimo `0,879` (`rewoo`). Ninguna arquitectura de las medidas recupera la reproducibilidad
   por decisión, así que toda trayectoria con decisiones delegadas pierde determinismo, y
   la pregunta es cuánto se pierde, no si se pierde.
2. Importa más CUÁL decisión se saca que CUÁNTAS. La evidencia de esta sección no es correlacional
   sino una intervención: sacar una sola decisión (el ancla) llevó a `pointer_chase` de
   réplicas que discrepaban (1,000 / 0,000 / 0,000) a réplicas que coinciden, sin tocar las
   otras. Ocho puntos de correlación no compiten con eso.

> El no-determinismo no se reparte por igual entre las decisiones de una trayectoria. Contar
> decisiones no predice; identificar cuál decide el resultado, sí.

Ésta es una limitación declarada del análisis, no un resultado: con ocho brazos y un corpus,
lo correlacional no puede decidir casi nada. Lo que la sostiene es la intervención.

## 7.3 Por qué no hay premio de calidad entre brazos capaces, aunque la interacción sea enorme

Éste es el resultado que reordenó el programa, y es negativo con un mecanismo preciso. La forma
en que suele argumentarse que rutear conviene («hay mucha interacción entre tarea y método, así que elegir por tarea tiene que pagar») no se sostiene, y este registro muestra dónde se
rompe. Lo que se sostiene en su lugar lo dice §7.4: los brazos que competirían tienen las mismas
capacidades, y el premio que existe está sobre el costo (§7.3.5), no sobre la calidad.

### 7.3.1 Hay interacción, y es grande

Descomponiendo `u(tarea, brazo) = μ + α(tarea) + β(brazo) + γ(interacción) + ε` sobre un
panel de 59 tareas × 8 brazos, que es el 76% de las 78 medidas. El criterio de recorte
es mecánico y está en un solo lugar del código, no se elige por sección: primero las
tareas que tienen al menos 7 brazos medidos (lo que impide que una tarea corrida por un experimento parcial redefina el universo), después los brazos que cubren ≥95% de ésas, y
al final las tareas donde están todos. Los cuatro brazos que quedan afuera son los que la
factibilidad poda en casi todas las celdas (`direct`, `streaming_scan`, `extract_compute`) más
`graph_traverse`, que se declara infactible en el 56-59% de las celdas anchas.

> Se declara porque ésta es la sección que más insiste en corregir por selección, y un
> recorte sin criterio sería exactamente lo que audita en otros.

| componente | varianza | % |
|---|---:|---:|
| α, dificultad de la tarea | 0,0632 | 41% |
| β, calidad del brazo | 0,0160 | 10% |
| γ, interacción | 0,0736 | 48% |
| ε, ruido entre réplicas | 0,0351 | |

El denominador, porque cambia el titular. Los porcentajes son sobre la varianza
explicada (`α + β + γ = 0,1528`). Contando `ε`, el total es `0,1879` y γ pesa 39%. Las
dos lecturas son legítimas y la primera es la convención en descomposiciones de este tipo, pero
un `48%` sin denominador declarado es un número que se lee más grande de lo que es.

γ descontado el ruido da 0,0619, con señal/ruido 5,30. Bajo el argumento habitual,
correspondería rutear.

### 7.3.2 Una señal la explica y sobrevive la corrección por selección

![Qué señal explica la interacción](figuras/predictores-de-la-interaccion.svg)

La figura ordena diez señales por cuánto de γ explican, con su propio nulo por permutación
dibujado como una raya negra sobre cada barra. Varias la superan, y esa comparación es
exactamente la falacia que el nulo existía para evitar, porque se probaron nueve candidatas
y se eligió la mejor. La vara correcta es la línea punteada: el máximo de los nueve nulos
en cada permutación.

Sólo `cardinalidad × término literal` la cruza, con 0,309 y `p` corregido `< 0,001`, y captura
dos tercios del techo que marca la etiqueta de diseño (el modo del que salió la tarea), que está en el gráfico como cota superior,
no como candidata: es la etiqueta de diseño del corpus, no se conoce al decidir, y ninguna
señal real puede superarla.

### 7.3.3 El premio neto es negativo

`var(γ)` grande ≠ premio de ruteo grande. El premio es `E[max_p u] − max_p E[u]`, y γ
puede ser enorme porque los brazos malos son malos en lugares distintos. Esa estructura es
real, es predecible, y no vale nada: nadie va a elegir el brazo que pierde por poco en vez
del que pierde por mucho.

Lo único cobrable es la interacción entre los brazos que competirían. `gist_reader` aporta
el 20% de `var(γ)` y `rewoo` el 15%; los tres punteros, 6-7% cada uno. Restringido a esos tres
(los que están a menos de 0,05 del mejor fijo):

```
gamma real estimado          0,0046      señal/ruido  0,38
oráculo entre contendientes  0,932
mejor fijo                   0,875
premio máximo               +0,058
piso de ruido (bootstrap)   +0,065
premio NETO                 −0,008
```

> El piso de ruido, que es la cantidad de la que depende todo veredicto negativo de este
> paper. Un oráculo toma un máximo sobre estimaciones ruidosas de utilidad por tarea, y un
> máximo sobre estimaciones ruidosas está sesgado hacia arriba: `E[max_p û_p] > max_p E[u_p]`
> incluso cuando todos los paradigmas son idénticos. Así que toda brecha de oráculo medida
> contiene una componente de ruido, y reportarla entera exagera el premio.
>
> La estimación es directa y no modelada: se toman las `k` réplicas del mismo paradigma sobre
> cada tarea, se las trata como si fueran `k` paradigmas distintos, y se calcula la brecha de
> oráculo sobre ellas. Cada punto del resultado es ruido por construcción, porque los
> «paradigmas» son la misma cosa. En el held-out se reporta el p95 sobre remuestreos de
> tareas (la tarea es la unidad de muestreo, no la fila). Implementación en
> `app/metrics.py`; los deltas se computan sobre valores sin redondear, así que una resta de las
> cifras impresas puede diferir en la última posición.
>
> El fenómeno tiene nombre en la literatura de decisión: es la maldición del optimizador,
> el sesgo positivo del valor esperado de la alternativa elegida cuando se elige por el
> máximo de estimaciones ruidosas [Smith y Winkler, 2006], y la misma desigualdad de Jensen
> que la sostiene. Lo propio de este paper es el estimador directo por réplicas del mismo
> paradigma, no el fenómeno.

Y ninguna señal separa a los tres contendientes entre sí: todas con `p > 0,29`. Sólo `la
celda` lo logra (`p = 0,007`), y ésa no se conoce al decidir.

> El 48% de interacción es real y vive entre los brazos que nadie elegiría. Reportar
> `var(γ)` como evidencia de que rutear conviene mide la estructura equivocada.

### 7.3.4 El premio no reaparece agrupando paradigmas en familias

Una respuesta natural es que las señales quizá no separen individuos pero sí grupos: un
ruteador que elige familia y después toma el más barato de la familia es otro ruteador, con
otro premio. Se probó, declarando las familias desde el código (por cuándo el brazo decide su próxima llamada) y no desde el resultado:

| familia | brazos | u media |
|---|---|---:|
| `adaptativo` | `react`, `reflection` | 0,818 |
| `plan_fijo` | `dag_strategy`, `rewoo` | 0,750 |
| `canal_con_pérdida` | `gist_reader`, `handoff`, `pointer_chase`, `supervisor` | 0,571 |

Valuar una familia por su máximo sería hacer trampa dos veces (le regala una elección por tarea que el ruteador de familias no puede hacer, y premia a la familia más numerosa por puro sesgo del máximo), así que cada familia se representa por su brazo de mejor media, elegido
una vez sobre todo el panel.

```
adaptativo          gana en 54 de 64 tareas  (84%)
plan_fijo                       5 de 64       (8%)
canal_con_pérdida               5 de 64       (8%)

premio de rutear FAMILIAS   +0,079   (piso de ruido +0,065)
premio de rutear BRAZOS     +0,110
```

Y hay que hacer la resta que el paper acaba de enseñar, porque los dos premios
superan el piso: `+0,079 − 0,065 = +0,014` para familias y `+0,110 − 0,065 = +0,045` para
brazos. Los dos netos son positivos, y aun así ninguno es cobrable, por una razón
distinta de la de §7.3.3:

> allá el premio no existía; en este panel existe y no hay con qué agarrarlo. El premio es lo que
> capturaría un oráculo, y un oráculo no es una política: ninguna señal predice la familia
> ganadora. La mejor, `cardinalidad`, da información mutua `0,092` y no sobrevive la
> corrección por selección (`p = 0,365`).

Un premio sin señal que lo prediga es una cota superior, no un resultado. La distinción
importa porque las dos secciones concluyen lo mismo por caminos opuestos, y presentarlas
juntas sin la resta invita al lector a pensar que nos contradecimos.

> No falla porque las señales sean débiles: falla porque no hay frontera que cruzar. Una
> familia que gana el 84% de las veces no es un cluster que rutear, es un default.

### 7.3.5 Lo que este corpus sí premia

Sobre calidad la decisión no tiene premio. Sobre costo a utilidad igualada, el mismo
registro da un ahorro grande con una pérdida dentro del ruido, y a diferencia del premio de
calidad sobrevive evaluarlo fuera de muestra (leave-one-task-out):

| señal | utilidad vs mejor fijo | ahorro |
|---|---:|---:|
| `cardinalidad × término` | −0,017 | 42% |
| `región` | −0,110 | 74% |
| `n_units` | +0,000 | 1% |

Es un intercambio, no una mejora. Una medición previa sobre un panel más chico daba `+0,008` de utilidad con 69% de ahorro (un almuerzo gratis) y con el
registro completo desapareció. La pregunta «qué paradigma da la mejor respuesta» está
agotada en este corpus; la pregunta «cuál es el más barato que da una respuesta
indistinguible» no.

Y ésa es la superficie donde la política aprendida sí paga, y transfiere. Con el
vocabulario de región vigente (cuatro ejes computados más el literal (§7.8.4)) y el desempate
por costo evaluado leave-one-task-out sobre 41 tareas × 7 brazos, contra el mejor fijo de
ese panel (`reflection`, `u = 0,930`, 125.169 tokens por celda):

| vocabulario de la política | utilidad | ahorro |
|---|---:|---:|
| con eje literal | 0,951 | 46% |
| sin eje literal | 0,928 | 37% |

Son dos paneles distintos y no se cruzan: el de arriba mide una señal suelta sobre 59 × 8, éste
mide la política entera sobre 41 × 7. Los dos dicen lo mismo con distinto rectángulo: entre
brazos que empatan en calidad, elegir el barato es una decisión aprendible que sobrevive fuera
de muestra. Y tiene su fragilidad declarada: 14 regiones sobre 41 tareas son 2,9 tareas por
región, y ése es el límite real hasta que el panel se amplíe.

### 7.3.6 La región de una tarea depende del modelo que la sensó

El vocabulario de región tiene cinco ejes. Cuatro son `COMPUTED` (se calculan del texto de la pregunta y del material) y uno, el acoplamiento, es `ELICITED`: lo emite el modelo. Sobre las
26 tareas medidas con dos familias de modelo:

| eje de la región | procedencia | cambia entre modelos |
|---|---|---:|
| cardinalidad | `COMPUTED` | 0% |
| oráculo disponible | `COMPUTED` | 0% |
| acoplamiento | `ELICITED` | 27% |
| continuidad | `COMPUTED` | 0% |
| término literal | `COMPUTED` | 0% |

Los cuatro ejes computados son idénticos en las 26 tareas; el elicitado cambia en 7. La
misma pregunta, con el mismo material, cae en regiones distintas según qué modelo la sensó:
`few/oracle/loose/flat/no_lit` con una familia y `few/oracle/mixed/flat/no_lit` con la otra.

Esto no es ruido de medición: es la clave de la política corriendo aguas abajo del sensor.
Una política keyed en región hereda la estocasticidad del modelo en su propia clave, dos
corridas del mismo request pueden buscar en dos filas distintas de la tabla. Es el mismo
mecanismo de §7.2 aplicado un nivel más arriba: una ramificación delegada al sensor, sólo que
la ramificación es qué política se consulta.

> Una clave de política tiene que ser `COMPUTED`. Un eje elicitado describe lo que el
> modelo cree sobre la tarea, no la tarea, y usarlo para indexar convierte la tabla de
> decisión en una variable aleatoria.

Y da un mecanismo verificable para el fracaso del ruteo por región que §7.3.3 mide: parte de la
señal que una política de este tipo puede aprender está en un eje que no se reproduce entre
modelos, así que lo aprendido sobre un sensor no transfiere a otro aunque el corpus sea el
mismo. Es la Proposición 5.7 en su caso (2), medida.

Cierre de la sección, y puente. §7.3 mostró tres cosas sobre el ruteo por identidad: que la
interacción es grande y vive entre brazos dominados, que entre los contendientes no hay premio
de calidad ni señal que los separe, y que la clave elicitada le agrega varianza a la tabla. Las
tres tienen la misma causa, que §7.1.4 ya dibujó y §7.4 formaliza: los contendientes caen en el
mismo punto del espacio de capacidades. Son el mismo brazo para decidir. Lo que sigue es qué
pasa cuando la clave deja de ser un nombre y pasa a ser lo que el brazo puede hacer.

## 7.4 Qué es aprendible: la capacidad, no la identidad del paradigma

`P15` se refutó mapeando ontología de la pregunta → nombre de paradigma: perdió `−0,087`
contra el mejor fijo. La sección anterior explica por qué ese premio no existía; ésta propone
el eslabón que faltaba y lo somete a la prueba que lo puede matar.

    ontología de la pregunta  →  capacidades que EXIGE  →  brazos que las tienen

Diez capacidades declaradas desde el código, cada una con la medición que la justifica y
con el sitio donde se ve: `PAYLOAD_COMPLETO`, `ADAPTA`, `COSTO_NO_ESCALA_CON_ALCANCE`,
`LECTURA_SIN_PERDIDA`, `COBERTURA_GARANTIZADA`, `VERIFICA_Y_REPLANIFICA`,
`RESOLVER_REFERENCIA`, `LARGO_GOBERNADO_POR_CODIGO`, `ELIGE_INDICE_POR_CONSULTA` y
`ABSTIENE_SIN_PRUEBA`. Las cuatro últimas las destapó resolver la celda de cadenas acopladas,
y ninguna es visible desde la taxonomía de control de flujo.

Y el catálogo encuentra un hueco sin correr nada: ningún brazo del plantel junta
`COBERTURA_GARANTIZADA` con `ABSTIENE_SIN_PRUEBA`, que es exactamente lo que una pregunta de
ausencia exige. Eso es para lo que sirve declarar capacidades en vez de medir paradigmas,
predice sobre un brazo que todavía no existe. Es una predicción registrada, no un resultado:
el brazo no está construido y §9.1 lo pone primero en el orden de lo que sigue.

### 7.4.0 Definiciones: capacidad, exigencia, brazo capaz

![La interfaz aprendible: de la pregunta a los brazos capaces](figuras/interfaz-aprendible.svg)

**Figura 15.** La interfaz aprendible en una imagen. El carril de arriba es `COMPUTED` de punta
a punta: los ejes de la pregunta salen de lo que el caller declara o de lo que se mide sobre el
material, la tabla de exigencias va del eje a la capacidad y nunca al nombre, y la salida es un
conjunto de brazos capaces entre los que decide el costo. El carril de abajo es lo que cada
brazo declara desde su código y una auditoría contrasta con lo corrido. Lo que no entra en la
clave está a la izquierda: el nombre del paradigma y cualquier eje elicitado.

**Definición 7.1** (Capacidad). Una *capacidad* es un predicado booleano sobre el código de un
brazo, `c(p) ∈ {0, 1}`, que se declara con tres cosas: qué es, el sitio del código donde se
ve, y el número medido que se explica con ella y no sin ella. El *catálogo* `C` es el conjunto
de capacidades declaradas; hoy tiene diez.

**Definición 7.2** (Lo que tiene un brazo). `TIENE(p) = { c ∈ C : c(p) = 1 }`. Es una
propiedad del código y no del registro, así que está definida para un brazo que todavía no
corrió. La auditoría contrasta cada `c ∈ TIENE(p)` con la conducta registrada: un brazo que
declara `ABSTIENE_SIN_PRUEBA` y nunca se abstuvo tiene una declaración falsa.

**Definición 7.3** (Lo que exige un eje). Para cada eje `e` de la ontología de la pregunta,
`EXIGE(e) ⊆ C` es el conjunto de capacidades sin las cuales el eje no se satisface. Se declara
por eje y no por celda del corpus, porque una celda es un artefacto de este banco y un eje es
una propiedad de la pregunta. Hoy `EXIGE` es una conjunción; §7.4.2 anota el contraejemplo que
pide una disyunción de conjunciones.

**Definición 7.4** (Brazos capaces). Para una pregunta con ejes activos `E(q, M)`,
`capaces(q, M) = { p : ⋃_{e ∈ E(q, M)} EXIGE(e) ⊆ TIENE(p) }`. Es un conjunto y no un ranking:
entre los capaces decide el costo, la utilidad esperada o lo que la política diga. Si
`capaces(q, M) = ∅`, el catálogo tiene un hueco, y eso es información antes de gastar.

Las cuatro definiciones son `COMPUTED` en el sentido de la Definición 5.6 siempre que los ejes
de `E(q, M)` lo sean, así que una política keyed en capacidades hereda la Proposición 5.7 (1).

| brazo | capacidades declaradas |
|---|---|
| `direct` | `PAYLOAD_COMPLETO`, `LECTURA_SIN_PERDIDA`, `COBERTURA_GARANTIZADA` |
| `react`, `reflection` | `PAYLOAD_COMPLETO`, `ADAPTA`, `LECTURA_SIN_PERDIDA` |
| `dag_strategy` | las tres anteriores más `VERIFICA_Y_REPLANIFICA`, `ABSTIENE_SIN_PRUEBA` |
| `rewoo` | `COSTO_NO_ESCALA_CON_ALCANCE`, `LECTURA_SIN_PERDIDA` |
| `gist_reader` | `COBERTURA_GARANTIZADA`, y el gist es la pérdida |
| `handoff` | `COBERTURA_GARANTIZADA`, y cada sub-agente ve su mitad |
| `supervisor` | `ADAPTA`, con ventana recortada de ocho unidades |
| `pointer_chase` | `ADAPTA`, `RESOLVER_REFERENCIA`, `LARGO_GOBERNADO_POR_CODIGO`, `ELIGE_INDICE_POR_CONSULTA`, `ABSTIENE_SIN_PRUEBA` |
| `graph_traverse` | `RESOLVER_REFERENCIA`, por su índice de entidades, y nada más |
| `extract_compute` | `COBERTURA_GARANTIZADA`, `COSTO_NO_ESCALA_CON_ALCANCE` |
| `streaming_scan` | `COBERTURA_GARANTIZADA` |

Que `react`, `reflection` y `dag_strategy` compartan las tres primeras es lo que §7.3 midió como
empate de calidad entre contendientes, ahora leído desde la tabla.

Por qué se declara y no se mide, y por qué eso no es opinar. Una capacidad es una propiedad
del código, no del registro: se lee del paradigma y por eso vale para un brazo que todavía no
corrió. Cada declaración nombra dónde en el código se ve (`RESOLVER_REFERENCIA` de `pointer_chase` es la función que exige que un candidato nombre a la entidad perseguida, `VERIFICA_Y_REPLANIFICA` de `dag_strategy` es su tope de replanificaciones) y una auditoría
contrasta lo declarado contra lo corrido: un brazo que declara `ABSTIENE_SIN_PRUEBA` y nunca se
abstuvo tiene una declaración falsa, y eso se ve. Cada una de las diez entra al catálogo con el
número que se explica con ella y no sin ella; una capacidad sin ese número es vocabulario.

El eslabón del medio, declarado por eje de la pregunta y no por celda del corpus. Una celda
es un artefacto de este banco; un eje es una propiedad de la pregunta, y por eso la tabla va de
eje a capacidad y nunca a nombre de paradigma:

| eje de la pregunta | capacidades que exige |
|---|---|
| cadena acoplada | `RESOLVER_REFERENCIA`, `LARGO_GOBERNADO_POR_CODIGO`, `ADAPTA` |
| contradicción | `PAYLOAD_COMPLETO`, `LECTURA_SIN_PERDIDA` |
| cobertura exhaustiva | `COBERTURA_GARANTIZADA` |
| ausencia | `COBERTURA_GARANTIZADA`, `ABSTIENE_SIN_PRUEBA`, ningún brazo las junta |
| horizonte desconocido | `ADAPTA` |
| entidad nombrada | `ELIGE_INDICE_POR_CONSULTA` |
| material mayor que la ventana | `COSTO_NO_ESCALA_CON_ALCANCE` |

La función que la consume devuelve el conjunto de brazos capaces, nunca un ganador: entre
los capaces decide el costo, la utilidad esperada o lo que la política diga. Mezclar «puede» con
«conviene» es exactamente lo que `P15` hizo mal al mapear ontología a nombre.

### 7.4.1 La prueba es dejar un BRAZO afuera, no una tarea

![El EDA de capacidades](figuras/eda-capacidades.svg)

La asimetría es el punto: un modelo con la identidad del paradigma no puede decir nada de un
brazo que no vio (no tiene parámetro para él, y es un límite estructural, no de ajuste).
Uno con capacidades sí, porque el brazo nuevo trae su vector declarado del código.

| modelo | MAE al predecir el brazo dejado afuera |
|---|---:|
| media global | 0,364 |
| dificultad de la tarea sola | 0,257 |
| capacidades | 0,233 |
| identidad del brazo *(viendo al brazo dejado afuera)* | 0,339 |

Y por pliegue, porque con ocho puntos la media sola esconde dónde gana y dónde no. El asterisco
marca el mejor de cada fila:

| brazo dejado afuera | media global | dificultad de la tarea | capacidades |
|---|---:|---:|---:|
| `dag_strategy` | 0,328 | 0,225 | 0,204 * |
| `gist_reader` | 0,399 | 0,297 * | 0,315 |
| `handoff` | 0,392 | 0,346 | 0,345 * |
| `pointer_chase` | 0,411 | 0,272 * | 0,305 |
| `react` | 0,327 | 0,218 | 0,161 * |
| `reflection` | 0,342 | 0,218 | 0,162 * |
| `rewoo` | 0,340 | 0,251 | 0,183 * |
| `supervisor` | 0,370 | 0,231 | 0,186 * |

Las capacidades ganan 6 de 8 pliegues y bajan el error contra la dificultad de la tarea
sola. Los dos que pierden son los dos brazos con canal con pérdida más marcado, `gist_reader` y
`pointer_chase`, donde la dificultad de la tarea predice mejor que las capacidades declaradas.
Es un dato y no una excusa: dice que el catálogo describe peor a los brazos que tiran
información antes de saber cuál hacía falta, y eso es una capacidad que falta declarar o una
que está mal declarada. La cuarta fila la puse creyendo que sería un techo y no lo es: sale peor que
capacidades pese a hacer trampa, porque ignora α (la dificultad de la tarea, el 41% de la varianza). Saber qué brazo es, sin saber qué pregunta es, predice mal. Ese fracaso es parte
del argumento: la identidad del paradigma no es una buena representación ni cuando se la
deja mirar la respuesta.

### 7.4.2 El efecto no cruza su nulo de capacidades barajadas

El nulo correcto no es la media global: es barajar las capacidades entre brazos. Mismos
vectores, mismo número de rasgos, misma estructura, asignados al brazo equivocado. Si el
modelo con capacidades reales no le gana a ése, lo que mide es la capacidad de ajustar, no
la de transferir.

```
MAE con capacidades REALES      0,2327
MAE del nulo (barajadas)        media 0,2599 · p5 0,2299
p = 0,065
```

No cruza. Queda como resultado sugestivo y no establecido: ocho brazos son ocho puntos, y con esa
`n` la prueba no puede decidir. Lo que la sentenciaría son más brazos, no más tareas.

Y la tabla ya tiene su propio contraejemplo anotado. `EXIGE` declara que una cadena
acoplada pide `RESOLVER_REFERENCIA` y `LARGO_GOBERNADO_POR_CODIGO`, y bajo esa regla el único
candidato es `pointer_chase`. Pero `dag_strategy` saca `0,89` en esa celda sin ninguna de las
dos: llega por otra ruta, con `VERIFICA_Y_REPLANIFICA` para insistir y `ABSTIENE_SIN_PRUEBA`
para no contestar cuando no llegó. A `EXIGE` le falta expresar rutas alternativas (hoy es una conjunción, y la realidad admite «A y B, o bien C y D»). Se deja como conjunción y con el
contraejemplo escrito, porque una tabla que se arregla sola para tapar su propio contraejemplo
deja de ser falsable.

### 7.4.3 La ontología de la pregunta separa más con menos segmentos

La otra mitad de la interfaz es qué exige la pregunta, y la pregunta del autor que la
motivó fue si la segmentación de la política tenía que ser por ontología en vez de por
estructura del material. Se contestó con el registro ya pagado, sin una llamada nueva. Y antes
del número, la salvedad que gobierna toda la sección: la segmentación ontológica se mide acá
usando la etiqueta de diseño, el modo del que salió cada tarea, que se conoce al construir el
corpus y no al decidir. Lo que sigue establece que hay estructura ontológica; no establece que
se la pueda ver desde un request.

Un eje de la ontología es una propiedad de la pregunta tipada con vocabulario cerrado, nunca
con prosa libre: cardinalidad de la respuesta (singular, enumerativa, agregada), cobertura
demandada (suficiente, exhaustiva), acoplamiento requerido, ausencia, vigencia, contradicción.
Cada eje entra con su modo de falla propio; un eje sin modo de falla no es un eje. Dos ya son
`COMPUTED` desde lo que el caller declara; los demás tienen a `ELICITED` como techo.

La cuenta: dentro de cada segmento, varianza entre brazos contra ruido entre réplicas. Si un
segmento agrupa tareas donde gana el mismo brazo, la señal sube y el ruido no, que es
exactamente lo que una política necesita de su clave.

| segmentación | señal/ruido | segmentos | ganancia por segmento |
|---|---:|---:|---:|
| ninguna, todo junto | 1,00 | 1 | — |
| región estructural, sólo el primer eje | 1,04 | 3 | 0,013 |
| ontología por eje | 1,74 | 5 | 0,148 |
| región estructural completa | 1,84 | 8 | 0,105 |
| ontología por celda | 1,92 | 11 | — |

Hay que controlar por cantidad de segmentos, porque más segmentos inflan la señal solos.
Sin controlar, la región estructural completa gana por poco. Controlado, la conclusión se da
vuelta: la ontología extrae 40% más separación por segmento que la región. Y un solo eje
ontológico, la contradicción, da `S/R = 1,82` con una partición binaria, contra `1,84` de
los ocho segmentos estructurales.

El caso que lo vuelve concreto. Dos modos del corpus, horizonte desconocido y vigencia, son
idénticos en los seis campos computables del vocabulario de región, caen en la misma
región, y tienen efecto opuesto sobre los brazos. Lo que los separa es un eje que la ontología
ya nombraba y la región no puede ver: si la pregunta pide el valor vigente o el valor a
una fecha. Una política keyed en región promedia sobre las dos poblaciones; una keyed en el
eje, no.

Lo que esto establece y lo que no. Establece que hay estructura ontológica en el corpus y
que la política debería segmentar por ella. No establece que se la pueda detectar en un
request real: agrupar por celda usa la etiqueta de diseño, que se conoce al construir la
tarea y no al decidir. Dos de los ejes ya son `COMPUTED` desde el request (cardinalidad de la respuesta y cobertura demandada, que el caller declara y el corpus tipa por celda, con falla cerrada si una celda no declara); los demás tienen a `ELICITED` como techo, y ése es el
siguiente experimento (§9.1).

## 7.5 El consenso entre paradigmas es un verificador sin oráculo ni juez

Este resultado no se buscó. El banco corre ocho brazos sobre la misma pregunta y siempre los
comparó contra el oráculo, nunca entre sí, y en el registro había ocho respuestas por
tarea que nadie había mirado juntas.

    ¿El acuerdo entre paradigmas predice la corrección, sin oráculo y sin juez?

La idea de votar respuestas tiene dueño y hay que nombrarlo antes del número: es
Self-Consistency [arXiv:2203.11171] con votantes heterogéneos. Lo que esta sección agrega
está en tres lugares. Los votantes son estructuras de control de flujo distintas y no
muestras de la misma cadena. El fenómeno se somete a una réplica sobre otra familia de modelo
con el criterio escrito antes de correr (§7.5.4). Y el voto mueve credencia y nunca
procedencia (§7.5.3), así que no habilita lo que un voto en la literatura habilita por
defecto.

### 7.5.1 La curva

| k brazos coinciden | celdas | P(la respuesta es correcta) |
|---:|---:|---:|
| 0 | 208 | 0,424 |
| 1 | 36 | 0,389 |
| 2 | 24 | 0,600 |
| 3 | 64 | 0,812 |
| 4 | 20 | 1,000 |
| 5 | 42 | 1,000 |
| 6 | 70 | 1,000 |
| 7 | 48 | 1,000 |

180 de 180 celdas correctas con `k ≥ 4`, sobre igualdad exacta de la cadena normalizada. La
curva tiene un umbral en 4 y no una pendiente suave. Dos salvedades que un `1,000` invita a
saltear: sobre 180 casos la cota inferior de Wilson al 95% es `0,980`, así que lo afirmable es
«≥ 0,98»; y el 4 es el punto donde la perfección aparece en este registro, no un umbral
derivado de nada.

### 7.5.2 Tres controles: no marca dificultad, no depende del largo, y no abarata

¿El acuerdo sólo marca «tarea fácil»? No. En las mismas 27 tareas donde existe
consenso:

```
brazos DENTRO del consenso        n=180   u = 1,000
brazos FUERA, en esas MISMAS tareas n= 36   u = 0,100
```

Sobre la misma pregunta, estar adentro o afuera del consenso es la diferencia entera:
discrimina dentro de la tarea, no entre tareas. Si sólo marcara dificultad, los dos grupos
rendirían igual.

¿Es un artefacto de comparar cadenas cortas? Tampoco. Una cuenta se compara fácil y una
enumeración de cuatro ítems no, así que el efecto podría vivir sólo en `singular`. No lo hace:

| cardinalidad | con consenso | sin consenso |
|---|---:|---:|
| `aggregate` | 1,000 (n=34) | 0,267 |
| `boolean` | 1,000 (n=41) | 0,000 |
| `enumerative` | 1,000 (n=28) | 0,555 |
| `singular` | 1,000 (n=77) | 0,532 |

¿Sirve para abaratar? No, y se reporta igual. Es la lectura comercial obvia (comité barato, escalar sólo al discrepar) y se probaron las 56 cascadas de dos y tres brazos:
ninguna ahorra. El comité se paga en todas las tareas y el brazo caro se paga igual en la
mayoría, así que el total sube. El consenso no es un ruteador barato.

**Algoritmo 2.** El verificador, y qué le está permitido tocar de la base de creencias.

```
ALGORITMO 2  Verificación por consenso, sin oráculo ni juez
────────────────────────────────────────────────────────────────────────────────
Entrada : pregunta q, plantel P, umbral k, base de creencias Β
Salida  : Β con la credencia actualizada

 1  R ← ⟨ ejecutar(p, q) : p ∈ P ⟩                      ▷ |P| trayectorias
 2  R ← ⟨ normalizar(r) : r ∈ R, r ≠ ε ⟩                ▷ vacía ≠ abstención
 3  for cada respuesta distinta a ∈ R do
 4      m(a) ← |{ r ∈ R : r = a }| − 1                  ▷ cuántos coinciden
 5  a* ← argmax_a m(a)
 6  if m(a*) ≥ k then
 7      Β ← asentar(Β, a*, procedencia = ELICITED,      ▷ NO sube de nivel
 8                          credencia  = calibración[m(a*)])
 9  else
10      Β ← asentar(Β, a*, procedencia = ELICITED,
11                          credencia  = calibración[m(a*)])
12      marcar_para_verificación(Β, a*)                 ▷ el dial decide si se paga
13  return Β
────────────────────────────────────────────────────────────────────────────────
calibración : m ↦ P(correcta | m coinciden), medida en §7.5.1
```

La línea 7 es la que hay que leer con cuidado, y dice lo contrario de lo que uno espera:
la procedencia no cambia. El consenso mueve la credencia y nunca el nivel.

### 7.5.3 Qué es, y qué NO autoriza

Es un detector de corrección de precisión total y cobertura parcial (27 de 64 tareas), que
es exactamente la forma de una regla de abstención: no dice qué brazo usar, dice cuándo no
hace falta verificar. Hasta este punto, la única forma de saber si una respuesta estaba bien era
tener el gold.

Y hay una tentación que hay que cortar de raíz. La lectura natural es «si cuatro brazos
coinciden, la creencia sube de nivel». No. La escalera de procedencia (`ASSUMED < ELICITED < OBSERVED < COMPUTED`) clasifica cómo se obtuvo algo, no cuánta confianza merece.
Cuatro paradigmas de acuerdo siguen siendo el modelo hablando: votar no toca el documento,
así que nada puede ascender a `OBSERVED` por consenso. Permitirlo sería exactamente la falla
que la escalera existe para impedir, que una mayoría del sensor se promueva sola al rango de
un hecho computado.

Lo que sí autoriza es mover la credencia dentro de `ELICITED`, que en el motor de decisión
es un campo distinto del de procedencia. Y ahí la tabla de arriba es la curva de
calibración: `0,42 · 0,39 · 0,60 · 0,81 · 1,00`. El módulo de creencias declara como riesgo
abierto que «las credencias elicitadas pueden estar mal calibradas… hasta que existan datos de
calibración». Éstos son datos de calibración.

> procedencia = de dónde vino · credencia = cuánto se le cree. El consenso mueve la
> segunda y no puede tocar la primera, y confundirlas convierte un detector útil en un permiso
> para que el modelo se autoacredite.

### 7.5.4 El efecto se reproduce sobre una segunda familia de modelo

Los ocho brazos no son independientes: comparten modelo, corpus y recuperador. Hay dos
mecanismos compatibles con la curva de §7.5.1, y sólo uno la hace utilizable:

  · convergencia de trayectorias, estructuras de control distintas llegan al mismo lugar
    cuando ese lugar es el correcto, y se dispersan cuando no. Sería una propiedad de los
    paradigmas, y debería reproducirse con otro modelo debajo
  · el mismo modelo repitiéndose, ocho envoltorios alrededor del mismo sensor producen la
    misma salida por la misma razón, y el acuerdo no es evidencia de nada

Se registró la predicción `P29` antes de correr, con los tres desenlaces escritos:
`P(correcta | k>=4) >= 0,90` sería convergencia; `<= 0,65` (cerca de la tasa base) sería el
mismo modelo; entre medio no distinguiría. Se corrió sobre otra familia de modelo, 23
tareas × 8 brazos × 1 réplica, 209 celdas, cero errores de infraestructura. El tamaño relativo
hay que decirlo: son 374 filas contra las 3.519 de la familia principal, un décimo, porque
ese modelo cuesta diez veces la entrada, así que la réplica cubre un subconjunto de celdas y no
la grilla.

| segunda familia de modelo | celdas | `P(correcta)` | cobertura |
|---|---:|---:|---:|
| `k >= 4` | 99 | 1,000 | 14 de 23 tareas |
| `k >= 3` | 115 | 1,000 | 18 de 23 tareas |

`1,000` contra un criterio de `0,90`: convergencia. El consenso se reproduce sobre otra
familia, así que la explicación barata (que sea el mismo modelo repitiéndose) queda descartada.
Y el control dentro de la tarea también se reproduce: donde hay consenso a `k>=3`, los
brazos que quedan afuera sacan `0,272` (n=29) contra `1,000` de los que están adentro.

### 7.5.5 El umbral es del modelo; el fenómeno no

El umbral se movió, y hacia abajo: `k>=4` en el primer modelo, `k>=3` en el segundo. La
guarda registrada en `P29` anticipaba exactamente este caso («si el umbral se mueve, eso ya es información») y lo que dice es que el número exacto de acuerdos es una propiedad del modelo y
la señal no. Sobre el modelo mejor hacen falta menos acuerdos para la misma precisión, que es
lo que uno esperaría si la señal fuera convergencia y no coincidencia.

La cobertura también sube: 18 de 23 tareas (78%) en el segundo modelo contra 27 de 64 (42%)
en el primero. El detector es más útil sobre el modelo mejor, no menos, lo cual descarta la
lectura de que el consenso sea una muleta para modelos flojos.

El umbral se compara sobre planteles del mismo tamaño, y esa condición no es opcional.
`k` acuerdos no significan lo mismo sobre planteles distintos: `k=4` sobre ocho paradigmas son
4 de 7 otros (57%), sobre doce son 4 de 11 (36%). Comparar el conteo crudo entre corridas con
planteles distintos mide el denominador y no la señal. Las dos lecturas de esta sección están
restringidas a los mismos ocho.

Lo que sigue sin estar probado. Dos familias no son la población de los modelos, y las dos
comparten corpus y recuperador. Lo que se descartó es la explicación más barata; no se probó
que valga para cualquier modelo ni para cualquier corpus.

## 7.6 Contra una ventana frontera: qué compra el arnés, y qué no

La objeción obvia a todo lo anterior es que un modelo grande con una ventana enorme lee todo
el material de una vez y se ahorra la orquestación. Sobre calidad, la objeción es correcta y
los datos de este registro la respaldan: el embudo de §7.2.1 muestra que toda representación
intermedia más chica que el material es una pérdida, y una ventana grande es el caso extremo
de *no tener canal con pérdida*. Medido: `direct` (leer todo en una sola llamada) saca
0,917, el mejor del plantel donde corre.

El arnés no le compite ahí. Le compite en otros cuatro ejes, y conviene decirlos con número.

### 7.6.1 El precio

Una tarea de la banda ancha lleva 455.476 tokens de material. Con los aranceles vigentes,
y contando que por encima de 272.000 tokens de entrada se cobra tarifa larga por el request
entero:

| leer todo de una | USD por pregunta |
|---|---:|
| ventana de 922k, gama media | 0,18 |
| ventana de 922k, gama alta | 1,82 |
| ventana de 922k, tope de gama | 4,55 |
| `react` sobre el modelo de la campaña (medido) | 0,0216 |

211×. Y el escalón es un acantilado, no una pendiente: cruzar el umbral por un token
duplica la tarifa del request completo.

### 7.6.2 Lo que no entra, y lo que no es un archivo

El corpus de este trabajo cabe en una ventana de 922k. Un corpus de producción no. Y ése
es el caso fácil: el difícil es que el material no siempre es un texto que se pueda pegar.
Un arnés extiende el alcance a lugares donde una ventana no llega por definición:

  · búsqueda externa, un índice que cambia entre una pregunta y la siguiente, o que vive
    detrás de permisos por usuario. No hay ventana que contenga un índice vivo
  · corpus sin cota, cuando el material crece con el negocio, «entra en la ventana» es una
    propiedad que vence. La ley de costo de §7.1.6 dice qué pasa cuando no entra
  · herramientas con efecto, una escritura, una transacción, un ticket. Un modelo que lee
    no ejecuta, y lo que gobierna una acción irreversible es una precondición verificada, no
    un contexto grande

Y hay que tomarlo en cuenta con honestidad: nada de esto está medido en este trabajo. El corpus de este
paper es estático, cabe, y no tiene herramientas con efecto. Son razones por las que un arnés
existe, no resultados de este trabajo.

### 7.6.3 Los tres ejes donde una ventana no ayuda

Éstos sí están medidos, y son la parte que no depende del tamaño del modelo:

Abstención. El paradigma que gana la celda de cadenas acopladas lo hace con 12 correctas,
3 abstenciones y cero respuestas equivocadas; los demás contestan igual y se equivocan. No
gana por razonar mejor: gana porque cuando no llegó, lo dice. Saber *cuándo no contestar* es
una decisión de flujo de control, y §7.2.4 muestra que sacarla del sensor sube la utilidad y
el determinismo a la vez.

Procedencia. Un contexto grande no dice de qué unidad salió un número. El Teorema 2
(soundness del ensamblador) garantiza que si se emite, todo valor emitido está implicado por
la base de creencias al piso pedido; eso exige una base de creencias tipada, no una ventana.

Determinismo. `pass^3` mide 17-34% de celdas inestables con temperatura cero y semilla
fija, y esa varianza no es del tamaño del modelo: es la trayectoria componiéndola. Un
modelo más grande con las mismas decisiones delegadas al sensor tiene el mismo problema.

> El arnés no existe para ganarle a un modelo grande en calidad. Existe para que la respuesta
> cueste dos órdenes de magnitud menos, para alcanzar material que ninguna ventana contiene, y
> para poder decir de dónde salió y cuándo no la hay, que es lo único que un dial de
> garantía puede prometer.

La comparación directa no está corrida. No se midió un modelo de ventana frontera sobre
las celdas anchas: el precio de §7.6.1 sale de los aranceles y del tamaño del material, y la
calidad de `direct` sale de las celdas donde la factibilidad lo dejó correr. Es una inferencia
bien apoyada, no una medición, y sería una corrida acotada (18 tareas de banda ancha, unos USD 82) que decidiría el punto de una vez.

## 7.7 Fuera de muestra: el corpus held-out completo

Todo lo anterior es en muestra. El criterio de éxito declarado del producto es otro
(brecha de oráculo neta positiva sobre datos que el sistema nunca vio) y hasta este borrador
no existía como medición válida: la única corrida del corpus held-out estaba en un archivo
anterior al cambio de tokenizador, sin `analyzer`, sin huella y sin vocabulario de región
estampados, o sea no replayable.

El held-out corre por el mismo camino de código que la campaña, con el corpus como
argumento del runner. Es una condición y no un detalle de implementación: un held-out medido
con otro arnés no mide generalización, mide dos arneses.

### 7.7.1 El premio neto es negativo en los tres estratos

26 tareas × 12 paradigmas × 3 réplicas, 927 filas, 48,5M tokens, 135 minutos, cero
errores de infraestructura. El rectángulo queda en 24 tareas × 8 paradigmas (el 92% de las medidas) bajo el mismo criterio mecánico que el resto del paper.

| paradigma | u |
|---|---:|
| `dag_strategy` | 0,802 |
| `react` | 0,777 |
| `reflection` | 0,722 |
| `supervisor` | 0,666 |
| `gist_reader` | 0,623 |
| `rewoo` | 0,613 |
| `pointer_chase` | 0,498 |
| `handoff` | 0,466 |

```
                     base+w4      + w16      + w48
tareas del panel          12         18        24
oráculo por tarea      0,972      0,981     0,931
mejor fijo             0,833      0,813     0,802
brecha observada      +0,139     +0,168    +0,128
piso de ruido (p95)   +0,167     +0,187    +0,162
brecha NETA           −0,028     −0,019    −0,034
```

La brecha queda por debajo de su piso de ruido en los tres estratos, sobre 5, 20 y 60
unidades de alcance. Fuera de muestra el ruteo por calidad no tiene premio, que es el mismo
veredicto de §7.3 (`−0,008` en muestra) por un camino independiente y sobre un corpus con otra
mezcla de celdas.

El piso de ruido no decrece al agregar tareas, y eso es una propiedad del estimador. Un
piso construido sobre la media decrece como `1/√n`; éste no es una media. Es
`E[max_p u] − max_p E[u]` bajo remuestreo (el sesgo del máximo) y crece con la dispersión
entre paradigmas y con cuántos compiten. Cada ancho nuevo agrega dispersión, así que el piso se
mueve con la composición del panel y no con su tamaño.

> El piso de un premio de máximo se recomputa, no se proyecta. Cualquier cálculo de
> potencia que use la intuición de una media subestima el piso justo donde la comparación se
> decide.

### 7.7.2 El plantel no tiene un ganador estable, y eso es el resultado

Sobre el corpus completo los dos primeros quedan en `0,802` y `0,777`, con una brecha de
`0,025` contra un piso de `0,162`. Sobre sub-paneles del mismo corpus el orden entre los
punteros se permuta (tres paneles anidados dan tres punteros distintos) sin que ninguno se
despegue.

> No es que el mejor paradigma fijo cambie entre corpus: es que no hay uno. La afirmación
> «el paradigma X es el mejor» exige una separación que este registro no tiene, y un panel más
> chico no la produce, la fabrica, porque el máximo de pocas muestras es sesgado hacia arriba.

Es el mismo mecanismo de §7.3.3 mirado desde otro lado: donde los candidatos empatan, el máximo
por tarea es el sesgo del máximo y no una elección mejor.

### 7.7.3 Costo de la corrida

| estrato | tareas | material medio | celdas | tokens | tiempo |
|---|---:|---:|---:|---:|---:|
| `base` + `w4` | 14 | 91k | 500 | 16,0M | 75 min |
| `w16` | 6 | 150k | 216 | 13,7M | 27 min |
| `w48` | 6 | 451k | 216 | 18,8M | 33 min |
| total | 26 | | 932 | 48,5M | 135 min |

Las seis tareas de `w48` cruzan el umbral de contexto largo, así que pagan el doble de
tarifa sobre el request entero: es el acantilado de §7.7 aplicado a la propia corrida, y la
razón de que el estrato más grande cueste 1,4× lo que su material sugiere.

Puente. Este held-out es el ruteo por identidad medido sobre el modelo de la campaña y con el
vocabulario vigente, y da el mismo veredicto que §7.3. Es, en el orden lógico, el episodio cero
de lo que sigue: el resultado que la campaña confirma y que los tres episodios de §7.8, sobre
otro modelo y con vocabularios anteriores, habían producido uno por uno. La diferencia entre
§7.7 y §7.8 no es el veredicto, es qué se hizo con él.

## 7.8 El ciclo que repara su propio vocabulario

Las secciones anteriores miden a los brazos. Ésta mide el ciclo que reparó el vocabulario
sobre el que la política decide, y el registro que la sostiene es la cronología de
predicciones falsables del laboratorio, con cada predicción anotada y fechada antes de correr
y su script de veredicto congelado en el mismo commit. Tres refutaciones sobre tres mundos que
la política nunca había visto, y cada una produjo un sensor nuevo. Lo que sigue son los
episodios, en orden.

Quién ejecutó el ciclo, dicho antes de los números. Cada refutación la leyeron el autor y su
asistente, y el eje que faltaba lo diagnosticaron y lo agregaron a mano al vocabulario. El
sistema no propuso ningún eje: consume los sensores `COMPUTED` que el ciclo produjo, y la
consolidación de §6.3 reajusta la política sobre ellos con su guarda. La automatización del
paso que falta, que la etapa de abstracción proponga el eje desde el registro, está diseñada
en §6.3 y no corrió. Así que lo que esta sección establece es un método con su condición
formal, no una propiedad autónoma del sistema, y §8.3 lo registra como amenaza de constructo.

### 7.8.0 Régimen de los episodios

Los tres episodios son anteriores a la campaña de §7 y corrieron sobre otro modelo y otros
corpus. Se declara todo lo que difiere:

| episodio | fecha de registro | mundo | modelo | filas | tokens | veredicto congelado antes |
|---|---|---|---|---:|---:|---|
| `P15` | 2026-08-27 | `gold_transfer`, semilla 47 | `gpt-5.4-nano`, `t = 0`, semilla fija | 390 | 14,07M | sí |
| `P16` | 2026-08-27 | `gold_p16`, semilla 61 | `gpt-5.4-nano` | 390 | 13,95M | sí, en el mismo commit |
| `P17` | 2026-08-27 | `gold_p17`, semilla 73, detectores declarados por tarea | `gpt-5.4-nano` | 390 | 12,69M | sí |
| vocabulario vigente | 2026-08-30 | registro completo, leave-one-out | `gpt-5.6-luna` | 41 × 7 | ninguno nuevo | n/c |

Qué transfiere a la campaña y qué no. Transfiere el mecanismo: que a la clave le faltaba un
eje es una propiedad del vocabulario y del corpus, no del modelo, y el eje de continuidad
separa el horizonte 6 de 6 en tres corpus con cualquiera de los dos modelos porque es función
pura del material. Transfiere la reproducibilidad 26 de 26, que es una propiedad de que la
decisión sea función de la base registrada. No transfieren las magnitudes: `−0,087`, `+0,121`
y el cruce de λ son números de `nano` sobre esos tres mundos, y sobre `luna` la campaña dio su
propia versión del mismo veredicto en §7.3 y §7.7. Los dos modelos no se mezclan en ninguna
estadística; el cargador del registro levanta si un archivo los mezcla.

### 7.8.1 Primer episodio: el vocabulario no tenía eje de horizonte

`P15`, mundo con semilla 47, 390 celdas, cero errores de infraestructura. La política ruteó por
región de features hacia un nombre de paradigma y perdió `−0,087` contra el mejor fijo,
más allá del piso de ruido de `0,057`, mientras reproducía cada decisión 26 de 26 desde su
base de creencias registrada.

El mecanismo, verificado contra el registro y no conjeturado: las tareas de horizonte
desconocido caían en las mismas regiones que las de cobertura independiente, porque el
vocabulario tenía cardinalidad, oráculo y acoplamiento y no tenía ningún eje para «no se
sabe cuántos saltos hay». La política mandó a esas tareas el brazo que gana en cobertura,
contra su propio veredicto registrado de que ese brazo falla en horizonte, porque ninguna
etiqueta le dijo nunca en qué caso estaba. Donde el registro sí tenía la señal, la selección
funcionó: `+0,121` sobre cobertura.

Dos incertidumbres, y el registro llevaba una sola. El criterio preregistrado era el piso de
ruido por celda, y contra él `−0,087` está fuera de `±0,057`, así que `P15` falla su propio
test. Pero el intervalo de muestreo sobre 26 tareas, bootstrap pareado con 10.000 remuestreos,
incluye al cero: `[−0,228, +0,037]`, `p = 0,19`. Son dos cosas distintas, ruido de medición y
ruido de muestreo, y se reportan las dos: `P15` está refutada contra su criterio registrado y
no está establecida en ninguna dirección por un intervalo de 26 tareas. Puntuando la acción
real en vez del primer escalón, el neto contra el mejor fijo queda en `−0,011`,
`[−0,121, +0,091]`, y contra siempre-`react` en `+0,112`, `[+0,001, +0,238]`, `p = 0,045`; bajo
Benjamini-Hochberg con `q = 0,05` sobre los cuatro contrastes, ninguno sobrevive, ése incluido.

Lo que produjo el ciclo. Un eje nuevo, la continuidad: recurrencia de una clave
literal entre unidades distintas, función pura del material, `COMPUTED`. Separa el horizonte
desconocido 6 de 6 en tres corpus, con cero falsos positivos sobre las demás celdas. Y una
corrección al método, medida: agregar el eje sin más fragmentó el espacio de regiones por
debajo del piso de confianza (de 12 tareas con margen sobre 26 a 0), así que la política
dejó de especializarse en absoluto. Con acumulación jerárquica y retroceso a la región padre,
16 de 26. Un vocabulario más expresivo cuesta potencia estadística, y a este tamaño de
registro el costo se ve.

### 7.8.2 Segundo episodio: la selección por identidad compra calidad sólo a costo cero

`P16`, semilla 61, con el eje nuevo, la acción real puntuada y el costo de escalar cobrado. El
veredicto lo decidió un barrido sobre λ, que estaba preregistrado como la medición:

| λ | neto contra el mejor fijo | neto contra siempre-`react` |
|---:|---:|---:|
| 0,00 | +0,121 | +0,177 |
| 0,02 | −0,404 | +0,000 |
| 0,05 | −1,289 | −0,265 |

Con el costo a cero, rutear por identidad captura `+0,121`. A λ igual a 0,02 ya está dentro
del ruido. La oración honesta se escribió antes de que existieran los números: la selección
por nombre compra calidad sólo cuando los tokens son gratis. Reproducibilidad, de nuevo 26 de
26.

Lo que produjo el ciclo. Que la valuación tiene que puntuar la acción real y cobrar la
escalera, y que en un corpus de coincidencia exacta la cascada precede a la selección en 20 de
22 tareas (§5.2): la propiedad que hace gradeable a una tarea es la que hace correcta a la
escalación. El tercer mundo, `P17`, se generó con detectores honestos y la cascada bajó de 22 a
2 de 26; la sonda disparó en 14 y no resolvió ninguna, así que la decisión honesta fue
diferir. Reproducibilidad 26 de 26. La restricción que quedó es una sola y está nombrada: la
evidencia que la sonda devuelve no alcanza el piso de procedencia que tiene que alcanzar.

### 7.8.3 Tercer episodio: el literal, medido contra el eje anterior

El vocabulario vigente agrega un eje: en cuántas unidades aparece el literal que la pregunta
cita. Es hermano de la continuidad (forma de token cerrada, verificada por contención, sin modelo en el medio) y no es un disparador léxico: la misma pregunta cambia de valor si
cambia el material. No se eligió; se midió contra el anterior, leave-one-out sobre 41 tareas ×
7 brazos (tabla en §7.3.5): `0,951` y 46% de ahorro contra `0,928` y 37%.

Y midiendo se encontró un defecto del sensor que sólo se ve midiendo: una pregunta booleana
cita sus opciones de respuesta, no un término de búsqueda, y esos literales no están en el
material por construcción. La guarda usa la cardinalidad de la respuesta, que el caller
declara. Recomputado con el sensor corregido, el vocabulario sobrevive.

### 7.8.4 Lo que el ciclo establece

![El ciclo que repara el vocabulario](figuras/ciclo-vocabulario.svg)

**Figura 16.** El lazo, con los tres episodios debajo. Predicción registrada con veredicto
congelado, mundo nuevo, refutación con mecanismo, sensor `COMPUTED`, consolidación con guarda,
y la próxima predicción sobre el vocabulario reparado. Los pasos 3 y 4 los ejecutaron personas;
los pasos 1, 2 y 5 son código. Ésa es la frontera que §8.3 declara.

| episodio | qué faltaba | qué se agregó | procedencia | decisión reproducida |
|---|---|---|---|---:|
| `P15` | eje de horizonte | continuidad entre unidades | `COMPUTED` | 26/26 |
| `P16` | valuación de la acción real | costo de la escalera cobrado; detector separado del gold | — | 26/26 |
| `P17` | vía para que la selección dispare | corpus con detector declarado por tarea | `COMPUTED` | 26/26 |
| vocabulario vigente | separación entre brazos capaces | eje literal | `COMPUTED` | — |
| §7.4.3 | segmentación que la región no ve | ontología de la pregunta | dos ejes `COMPUTED`, el resto `ELICITED` | — |

Tres cosas se leen de la tabla. Cada sensor nuevo es `COMPUTED`: ninguno pasó por el
modelo, y por eso ninguno rompió la garantía; es la Proposición 5.7 (1) respetada tres veces.
La reproducibilidad no se perdió en ningún episodio: cambiar qué se sensa no cambió que la
decisión sea función de la base registrada. Y lo que el ciclo produjo es el vocabulario sobre
el que una política puede aprender, no una política sobre paradigmas. Eso está un nivel arriba
de lo que §6.3 describe, y hay que decir con precisión qué parte es del sistema: la
consolidación aprende la política sobre el vocabulario que tiene, con guarda y sin tocar un
peso; el vocabulario lo repararon personas, con la disciplina de abajo, y esa reparación es lo
que este registro tiene para mostrar como método. La plasticidad autónoma del vocabulario es
la superficie de gobierno de §5.6, diseñada y sin medir.

La disciplina que lo hace posible. Aprender del registro y confabular sobre el registro son
la misma operación con distinto control. Lo que separa una de otra es lo que §7.3 construyó:
el piso de ruido por sesgo del máximo, la corrección por selección con el máximo de los nulos,
la partición proponer/puntuar/promover por tarea, y las predicciones escritas antes del número.
Sin eso, tres refutaciones serían tres ajustes post hoc. Con eso, son tres episodios.

## 7.9 Predictores del comportamiento, extraídos del registro

Lo que la política aprende se escribe en §6.3.2 como superficies. Esta sección reporta los
predictores que el registro entrega sobre cómo se va a comportar un brazo antes de
correrlo, que es lo que una regla puede consumir. Ninguno se obtuvo con una llamada nueva.

### 7.9.1 El paradigma determina cuánta evidencia se lee, y eso vale más que el paradigma

Sobre el corpus fuera de ventana donde `P15` corrió (`gold_transfer`, semilla 47, modelo
`gpt-5.4-nano`, cinco brazos estructurados, 90 celdas), la diferencia entre las celdas que
leyeron toda la evidencia portadora y las que no:

| | celdas | `u` | brecha | mayor diferencia entre paradigmas | razón |
|---|---:|---:|---:|---:|---:|
| recall completo | 29 de 90 | 0,869 | | | |
| recall parcial | 61 de 90 | 0,336 | +0,533 | 0,126 | 4,2× |

Leer la evidencia vale cuatro veces lo que vale elegir el paradigma. La brecha sobrevive
dentro de cada modo que tiene los dos grupos, así que no es la dificultad de la tarea con otro
nombre; y es máxima en horizonte desconocido, `+0,721`, la celda donde `P15` más perdió.

La pregunta que decide si esto es accionable es quién determina el recall:

| qué lo determina | participación en la varianza del recall | grupos |
|---|---:|---:|
| la región, lo que la decisión ve | 5,2% | 5 |
| el paradigma, lo que la decisión elige | 62,2% | 5 |
| la tarea, lo que el mundo aporta | 10,5% | 21 |

El paradigma determina el recall seis veces más que la tarea. Rutear no arbitra al margen
de la variable dominante: es la palanca principal sobre ella. Y reencuadra qué es rutear: no
«elegir la estructura que razona mejor» sino «elegir la estructura que va a leer la
evidencia». El 5,2% es el problema, y es el mismo problema de §7.8.1 llegando por otro lado:
la clave de la política casi no ve la variable que decide.

Son participaciones marginales sobre grupos desbalanceados; no suman nada y región y paradigma
no son ortogonales. Lo que carga el argumento es el contraste entre las dos filas de cinco
grupos. Y una salvedad de método: el recall es consecuencia del paradigma, no una covariable
previa, así que condicionar por él no da un efecto directo insesgado. La magnitud se sostiene
sola; la lectura de «tal brazo no resolvía mejor, encontraba mejor» es una pista y no un
resultado.

### 7.9.2 Ofrecer una herramienta cambia la conducta, aunque no se use

`P30`, registrada antes de correr y corrida sobre el modelo de la campaña, `gpt-5.6-luna`:
ofrecerle a `react` la herramienta de leer todo el material en una llamada, sobre 21 tareas del
ancho medio con tres réplicas, 63 celdas pareadas. La
predicción era que el brazo la usaría y leería más unidades por llamada. Se refutó en la
dirección contraria, y el ahorro apareció igual:

| | tokens por celda | llamadas | `u` |
|---|---:|---:|---:|
| sin la herramienta | 137.211 | 4,3 | 0,540 |
| con la herramienta ofrecida | 87.495 | 4,0 | 0,540 |

`1,57×` más barato en tokens, `1,36×` en dinero por el caché del proveedor, con la utilidad
exactamente igual. Y la herramienta se llamó en 3 de 63 celdas. El ahorro no vino de
usarla:

| | sin | con | |
|---|---:|---:|---:|
| caracteres releídos | 2.836.465 | 322.094 | 8,8× menos |
| fracción releída | 12,6% | 1,9% | |

El efecto está en la oferta, no en el uso. Con una salida barata a la vista, el agente
dejó de releer lo que ya había leído. Es la misma forma que dio un pizarrón ofrecido como
herramienta (llamado 1 vez en 125) pero con signo positivo: la especificación de herramientas
es parte de la política, y su efecto no se mide contando llamadas.

### 7.9.3 El costo de una vuelta es reenvío, medido por llamada

La misma corrida fue la primera con traza por llamada, 273 llamadas. La ventana crece así:

| turno | prompt, tokens | contra el turno 0 |
|---:|---:|---:|
| 0 | 607 | 1,0× |
| 1 | 9.914 | 16,3× |
| 2 | 33.548 | 55,3× |
| 8 | 67.233 | 110,8× |

El primer turno consume 38.238 tokens de 5.503.757: el 1%. El 99% restante es material que
ya se pagó, viajando otra vez. Es la ley `N²` de §7.1.6 medida directo por primera vez, y no
inferida de comparar poblaciones. La consecuencia para la política es que la clase de costo
por vueltas es la única sobre la que una regla de parada puede actuar, y el registro da la
señal: entre réplicas de la misma celda con la misma utilidad, el 33% de los tokens son
evitables (49% en `dag_strategy`, 0% en el brazo cuyo abanico lo fija el código), y la
racha máxima de búsquedas estériles es `1,17` en la réplica barata contra `2,28` en la cara,
sobre 72 pares empatados. Es contable, determinista, y es el tipo de señal que este trabajo
prefiere sobre el andamiaje por prompt. La regla que la consume está registrada como factor
(`P20`) y no corrió; se reporta como predictor medido y regla pendiente, no como resultado.

### 7.9.4 Qué predice cada uno, en una línea

| predictor | procedencia | qué anticipa antes de correr |
|---|---|---|
| capacidades declaradas (§7.4) | `COMPUTED` del código | si un brazo puede resolver lo que la pregunta exige |
| ley de costo del brazo (§7.1.3) | medida, estable entre corpus | si su costo va a escalar con el material, con las vueltas, o con nada |
| paradigma → recall (§7.9.1) | medida | cuánta evidencia va a leer, que explica cuatro veces más que su nombre |
| oferta de herramientas (§7.9.2) | medida | que el releído cae con una salida barata a la vista |
| racha estéril (§7.9.3) | contable en runtime | que la trayectoria se está desbocando, antes de que termine |

Ninguno es un nombre de paradigma. Todos son cosas que una regla puede leer al decidir, y eso
es lo que la interfaz aprendible de §7.4 pide de sus entradas.

# 8. Limitaciones y amenazas a la validez

Las amenazas se agrupan por el tipo de inferencia que ponen en riesgo. Validez interna:
si el efecto medido es del mecanismo o del arreglo experimental. Validez externa: hasta
dónde llega lo medido fuera de este corpus. Validez de constructo: si lo que se mide es
lo que se dice medir. Ninguna toca la Proposición 5.4 ni los dos teoremas (esos son verificados por máquina y no dependen del corpus); todas tocan las afirmaciones empíricas de
§7.

## 8.1 Validez interna

El régimen en-ventana es casi tautológico, y §7.4 es la escapatoria, parcialmente
recorrida. El corpus detrás de §7.1–7.3 tiene 16k tokens en su punto más ancho, así que
leer-todo es correcto y lo más barato ahí. El régimen fuera-de-ventana ya está medido a
483k con `repeat = 3` (§7.4–7.5), y el claim de régimen a través de 135k/483k/1,27M
descansa en el barrido de factibilidad a costo cero. Sigue abierto: no hay corrida
completa a 1,27M (sólo su aritmética de factibilidad), dos celdas pesadas fuera de
ventana todavía sin réplica completa (marcadas † en §7.4).

Ya existen réplicas, y el ruido es por celda. La réplica accidental del primer
estudio (§7.3) y el `repeat = 3` del segundo coinciden: la reproducibilidad es por tarea,
los lectores no dan vuelta nada, los que usan herramientas dan vuelta las celdas donde
decide el retrieval, y el costo no fue reproducible en ninguna parte (dispersión media
2,05×, máxima 5,43× a calidad idéntica en el primer estudio; el mismo patrón de
concentración en el segundo). Por eso todo delta de calidad se reporta con su conteo de
flips por celda, nunca como media pelada. El piso de ruido formal por celda y la brecha
de oráculo neta (`Study.noise_floor`, decisiones contra la brecha neta) se computan en el
análisis final sobre la grilla completa, pendiente de las celdas en re-corrida.

La amenaza del sampleo es la combinación de `tools` con razonamiento, no la
temperatura. Medido sobre las tres familias disponibles: los deployments de razonamiento
rechazan `temperature` de plano, y `terra` en su propio default es el más reproducible de los
tres. La restricción viva es otra y es estructural: en la familia `5.6`, `tools` y un
`reasoning_effort` distinto de `none` no se pueden combinar en Chat Completions, y la diferencia
que eso hace es total, 0,000 contra 1,000 sobre la misma tarea. Así que toda fila de campaña
corre con `reasoning_effort = none`, que es un régimen declarado y no un default.

Dos modelos en el mismo paper, y lo que eso permite y no permite decir. La campaña de §7 y el
held-out de §7.7 corren sobre `gpt-5.6-luna`; los tres episodios de §7.8 y el análisis de
recall de §7.9.1 corren sobre `gpt-5.4-nano`, sobre corpus anteriores y con vocabularios de
región anteriores. Ninguna estadística los mezcla, y el cargador del registro levanta si un
archivo lo hace. Lo que sí cruza el paper es la inferencia cualitativa: que a la clave le
faltaba un eje, que los sensores agregados son `COMPUTED`, que la decisión se reproduce. Lo que
no cruza son las magnitudes de §7.8 y §7.9.1, que valen para `nano` y para esos mundos. §7.8.0
lo tabula. Un lector que quiera el ciclo entero sobre un solo modelo tiene que esperar a que
los tres episodios se repitan sobre `luna`, y eso no está hecho.

## 8.2 Validez externa

Una rama de la propia partición no se pudo ejercitar, y es estructural. §5.2 parte el
problema según `v`, la disponibilidad de un detector barato en runtime, y manda `v = 1` a una
cascada y `v = 0` a un ruteador. Todos los corpus de este registro caen del lado `v = 1`, y
no por elección: corregir sin juez significa corregir por coincidencia exacta, la coincidencia
exacta necesita una respuesta de referencia, y el mismo campo se leía como detector de runtime.
La regla de cascada dispara con prioridad más alta que la de selección, así que sobre dos
corpus held-out la regla de selección no disparó nunca y los dos veredictos de ruteo son
mediciones de la cascada. La forma general es una advertencia sobre toda una clase de
experimento:

> Un benchmark que establece corrección por coincidencia exacta contra una referencia tiene
> un detector barato en cada tarea por construcción, y por lo tanto no puede ejercitar la
> rama `v = 0` de su propia partición. Ser corregible implica ser verificable.

Si la selección paga donde verificar es genuinamente imposible queda abierto, y necesita un
corpus cuya disponibilidad de detector se declare por tarea en vez de heredarse de la clave.

La transferencia entre mundos está medida, y es parcial. El mundo held-out con seed nueva (generado y verificado independientemente) ya corrió su
test de transferencia registrado, P8. Dos de sus cinco predicciones no transfieren, así
que por su propia regla de decisión registrada los veredictos por celda de más abajo son
corpus-locales: afirmaciones sobre mundos seed-7, cada una con salvedad por mundo. La
refutación no se apoya en las celdas que nadie resolvió, en las dos donde otro brazo llega
a puntaje perfecto, el fallback general devuelve 0,667 y 0,000.

Un confundente de la varianza de trayectoria que este montaje no puede separar. Las celdas
inestables se miden con `t = 0`, semilla fija y el mismo prompt, así que la varianza observada
tiene dos fuentes posibles: la ramificación delegada al modelo, que es la que §7.2 estudia, y el
no-determinismo del stack de servicio (agrupamiento dinámico de requests, orden de reducción en punto flotante, versión del kernel) que produce logits distintos para entradas idénticas sin
que el cliente lo pueda ver. La Proposición 5.4 no depende de cuál domine: con `d(T) = 0` la
trayectoria es fija cualquiera sea la fuente del jitter. Lo que sí depende es atribuir el
`17–34%` a la ramificación, y separarlo exige un servidor de un solo request por lote, que este
montaje no tuvo.

Corpus sintético. El ground truth es exacto y se re-deriva de forma independiente, y los
parámetros estructurales son diales y no esperanzas, pero la distribución de tareas reales sobre
esos diales es desconocida. Hacen falta benchmarks públicos para validez externa y no se usan
todavía.

La ontología se midió sobre la etiqueta de diseño. §7.4.3 agrupa por el modo del que salió
cada tarea, que se conoce al construir el corpus. Eso establece que la estructura existe y que
la política debería segmentar por ella; no establece que un clasificador la recupere desde un
request real con la precisión que una regla necesita. Dos ejes son `COMPUTED` desde lo que el
caller declara; los demás tienen a `ELICITED` como techo, y una clave elicitada es el caso (2)
de la Proposición 5.7. Recuperar la ontología desde el request es la medición que decide si la
interfaz de §7.4 sirve afuera de este banco, y está en §9.1 como segunda prioridad.

El leave-one-arm-out tiene ocho puntos. Las capacidades ganan 6 de 8 pliegues y no cruzan su
nulo de capacidades barajadas (`p = 0,065`). Con esa `n` la prueba no puede decidir, y lo que
la decide son más brazos, no más tareas. El brazo de ausencia que el catálogo predice es el
primero, y está en §9.1 como primera prioridad.

La latencia no es comparable. El DAG de este banco corre secuencial donde correría en oleadas
concurrentes; y una vez que los workers compiten, el wall-clock por fila deja de medir latencia.
La calidad y los conteos de tokens siguen siendo exactos.

## 8.3 Validez de constructo

La superficie de acciones es arquitectura declarada y no está ejercitada. §5.5 filtra las acciones
irreversibles con un piso de procedencia y §5.6 afirma la maquinaria sobre cuatro
superficies. Una de esas cuatro nunca corrió. El inventario completo de herramientas, sobre
todos los corpus y los quince paradigmas registrados, son doce:

| qué hacen | cuáles |
|---|---|
| leen el mundo | `search` `keyword_search` `semantic_search` `read` `read_all` |
| escriben el estado del propio agente | `note` `notes` `plan` `advance` `post` `board` |
| leen su propia contabilidad | `coverage` |

Ninguna de las doce cambia nada fuera del proceso. No se escribe un archivo, no se manda
un mensaje, no se actualiza una fila. Seis tareas de setenta y ocho llevan
`irreversible = True` y tres llevan `shared_writes = True`, y esas banderas sí levantan el
dial de garantía, pero la tarea que etiquetan es *«decidí si esta relación debe escalarse
para congelamiento; contestá 'escalate' o 'no escalation'»*, calificada por exact-match
contra una clave. Es una clasificación sobre documentos con la etiqueta de una acción
encima. No existe una herramienta que congele una cuenta, así que el piso que existe para
filtrar lo irreversible nunca tuvo un acto irreversible que filtrar.

Resolverlo es otro experimento. El balance exacto: §5 se afirma para agentes en general y está verificado como tal; §7–§8 se afirman para extracción
de respuesta exacta sobre documentos y se midieron ahí; la superficie de acciones está
diseñada, tipada, probada en unidad y sin medir. Lo más parecido a evidencia sobre una
capacidad que no es recuperación es el resultado del blackboard en §7.7, y es un nulo.

El ciclo de §7.8 lo ejecutaron personas, y ésa es la amenaza de constructo más importante del
paper. La contribución 3 se enuncia como «el ciclo que repara su propio vocabulario», y lo que
se midió es un ciclo de desarrollo dirigido por refutaciones preregistradas: el autor y su
asistente leyeron cada veredicto, diagnosticaron el eje que faltaba y lo agregaron. Lo que el
sistema hace solo es lo de abajo del lazo: consumir el sensor nuevo, reajustar la política
offline con guarda, reproducir la decisión. Lo que no hace solo es lo de arriba: proponer el
eje. Si un lector entiende «plasticidad» como que el sistema descubrió qué sensar, entiende
algo que el registro no sostiene. Lo que el registro sostiene es que, hecho con esa disciplina,
cada reparación conservó la garantía y quedó auditada, y que el paso que falta tiene un lugar
definido en el diseño, la etapa de abstracción de §6.3, que hoy busca particiones sobre ejes
existentes y no propone ejes nuevos. Convertir el ciclo en plasticidad del sistema es medir
que esa etapa, sola, proponga la continuidad o el literal a partir del registro de `P15`; está
en §9.1.

Las afirmaciones de novedad están verificadas como conjunciones, no como partes. Los dos
trabajos ancla se leyeron completos el 2026-08-26: todos los números citados de Select-then-Solve
verifican contra su cuerpo, y la cesión a SCL se sostiene. Las afirmaciones restantes, la
consolidación de la política de control (§6.3), el descubrimiento de proposiciones con compuerta
de procedencia, la abstención en el ruteo de paradigmas, sobreviven búsquedas fechadas sólo como
conjunciones cuyos conjuntos individuales tienen cada uno un vecino publicado (§2.2, §2.4, §2.6).
Un campo que se mueve así de rápido puede cerrar cualquiera de ellas en meses; las búsquedas
están fechadas para que un lector pueda re-correrlas.

## 8.4 Reproducibilidad

Advertencia de reproducibilidad. Una semilla sola no fija un corpus. Cuando el algoritmo de
generación cambió, la misma semilla produjo un mundo distinto; los manifiestos ahora estampan
versión de generador y los resultados entre versiones no deben mezclarse.

## 8.5 Impacto más amplio

§1.1.1 invoca el Reglamento de IA y el artículo 22 del RGPD para motivar que una norma pide una
propiedad y no una probabilidad. Corresponde decir qué implica un sistema así del otro lado, y
son cuatro cosas.

Abstenerse ante un auditor. Un sistema que puede callarse traslada la decisión a una persona
en el momento en que la evidencia no alcanza, y eso es lo que la supervisión humana pide. Pero
la abstención tiene su propio modo de falla: un sistema que se abstiene en las preguntas
difíciles y contesta las fáciles produce un registro que se ve impecable y no dice nada sobre
lo que importaba. La curva riesgo-cobertura tiene que reportarse junto con la utilidad, y este
paper la reporta; un despliegue que exhiba sólo la precisión de lo contestado está ocultando el
denominador.

Responsabilidad sobre lo aprendido. Un piso de garantía que sube solo, aunque suba con guarda
de replicación y quede en un artefacto firmado y diffeable, es una decisión de gobierno que
nadie tomó explícitamente. La Proposición 4 acota cuántas veces puede pasar y §6.2 exige que
nunca baje solo, pero quién responde por un piso aprendido es una pregunta organizacional que el
diseño hace posible contestar y no contesta. El artefacto está hecho para que un auditor lea
dos versiones de una tabla; falta que alguien tenga la obligación de leerlas.

Clasificar mal una pregunta regulada. Si la ontología de §7.4.3 se recupera desde el request
con un clasificador elicitado, un error de clasificación puede mandar una pregunta de acción
irreversible por el camino de una pregunta de consulta. Por eso las banderas de riesgo las
declara el caller y nunca se infieren del texto (§5.5), y por eso la Proposición 5.7 exige que
lo que gobierna la decisión sea `COMPUTED`. La ontología elicitada puede informar el costo,
nunca el piso.

El valor superado con procedencia impecable. La celda de vigencia de §9.1 existe por una
falla que este sistema hace más peligrosa y no menos: un valor viejo, encontrado en un
documento real, con procedencia `OBSERVED` correcta, emitido como vigente. El Teorema 2 lo deja
pasar, porque es sound y falso. Un sistema con procedencia le da a una respuesta equivocada una
credencial que una respuesta sin procedencia no tiene, y eso obliga a que la vigencia sea un
eje de la clave y no un detalle del material.

---

# 9. Conclusión

Una sola máquina (sensor estocástico, creencia tipada, regla determinista, registro) que
aprende con los pesos del sensor congelados, y cuatro cosas que se pueden decir de ella con
medida.

| | qué dice | evidencia |
|---|---|---|
| La máquina | dónde puede aparecer la varianza, y qué cuesta gobernarla | absorber cuatro ramificaciones lleva un paradigma de `0,33` a `0,89` y hace coincidir sus réplicas; el dial es gratis hasta A2 y en A3 se lleva el 60% del catálogo y el 31% de la utilidad |
| La interfaz aprendible | sobre qué se aprende: capacidades del brazo y ejes de la pregunta, nunca nombres | capacidades declaradas superan a la identidad del paradigma incluso cuando ésta ve la respuesta; la ontología separa 40% más por segmento; el catálogo predice un brazo que no existe |
| El ciclo | cómo se reparó el vocabulario: cada refutación preregistrada produjo un sensor `COMPUTED`, agregado por personas y consumido por el sistema | tres mundos held-out sobre `nano`, tres ejes nuevos (horizonte, literal, ontología), decisión reproducida 26/26 en cada uno |
| Lo que compra | qué paga fuera de muestra, y qué predice | 42% a 46% de costo a utilidad indistinguible, según el panel; el paradigma determina el recall seis veces más que la tarea; ofrecer una herramienta baja el releído 8,8× sin usarla |

Lo que las une es la condición que la Proposición 5.7 enuncia, §7.3.6 midió y §7.8 respetó en
cada paso: una clave de política tiene que ser `COMPUTED`. Determinismo y aprendizaje no
compiten; el primero define sobre qué puede aprender el segundo. Y el estimador de piso de ruido, la corrección por
selección y la partición por tarea son lo que separa aprender del registro de confabular sobre
él: sin esa disciplina los tres episodios de §7.8 serían tres ajustes post hoc.

Dos cosas más quedan medidas y en su lugar. El consenso entre paradigmas es una curva de
calibración de credencia que se reproduce sobre una segunda familia de modelo, y no abarata: su
lugar es el dial, como regla de abstención. Y el ruteo por identidad de paradigma no tiene
premio de calidad (`−0,008` en muestra, `−0,034` held-out, y compra calidad sólo con el costo a cero) porque los brazos que competirían tienen las mismas capacidades. Ese resultado no
cierra el ruteo: cierra la pregunta mal formulada, y abre la que el sistema puede aprender.

## 9.1 Lo que sigue, en orden

Construir el brazo que el catálogo predice. Ningún paradigma junta cobertura garantizada
con abstención por prueba faltante, y ésa es la capacidad que la pregunta de ausencia exige.
Construirlo y correrlo en las celdas de ausencia es la prueba más fuerte posible de que las
capacidades predicen: un brazo diseñado desde la tabla, medido después. Y sube el `n` del
leave-one-arm-out, que hoy está en ocho y da `p = 0,065`; lo cruzan más brazos, no más
tareas.

Recuperar la ontología desde el request. §7.4.3 establece que la ontología separa; no
establece que se la pueda ver afuera del corpus. Dos ejes ya son `COMPUTED` desde lo que el
caller declara. Para los demás, la medición es si un clasificador (calibrado, con techo `ELICITED`) recupera el eje de una pregunta real con precisión suficiente para que la regla lo
consuma.

La celda de vigencia. El corpus ya tiene enmiendas con precedencia declarada en forma fija,
y ninguna pregunta las interroga. Treinta y dos tareas y cero documentos nuevos miden el eje
que separa horizonte de vigencia, y separan dos fallas que el F1 confunde: no encontrar la
enmienda, y encontrarla y devolver el valor superado con procedencia impecable.

Las exigencias como rutas alternativas. La tabla de §7.4 es una conjunción con su
contraejemplo escrito: `dag_strategy` resuelve la cadena acoplada sin dos de las tres
capacidades que la tabla exige, por otra ruta. Que el sistema aprenda del registro que una
demanda se satisface con «A y B, o bien C y D» es, literalmente, extraer el motivo del
comportamiento; y es una partición más que la consolidación de §6.3 puede proponer y la guarda
puede puntuar.

Que el sistema proponga el eje. Es lo que convertiría el ciclo de §7.8 en plasticidad del
sistema y no en método de desarrollo. La medición es concreta: darle a la etapa de abstracción
de §6.3 el registro de `P15`, con sus episodios y sus features crudos, y ver si propone sola una
partición equivalente a la continuidad, es decir, una función del material que separe el
horizonte desconocido 6 de 6 sin falsos positivos. Si la propone, el lazo de la Figura 16 se
cierra sin personas en los pasos 3 y 4. Si no la propone, el paper dice lo que dice hoy, y lo
dice con la medición hecha.

Repetir los tres episodios sobre el modelo de la campaña. §7.8 vale para `nano`; §7.3 y §7.7
dan el mismo veredicto sobre `luna` por otro camino. Correr `P15`, `P16` y `P17` sobre `luna`
cerraría la única costura de modelo que el paper tiene, y cuesta lo que costaron: unos 40M
tokens.

Y lo que ya estaba pendiente sigue. Las superficies que cambian lo que el sistema
*promete* (piso por estadísticas de rechazo, calibración por proposición) piden un corpus con
evidencia insuficiente en algunas tareas. La comparación directa contra una ventana frontera
sobre las 18 tareas anchas decidiría §7.6 por unos 82 dólares. La superficie de acciones exige
una herramienta que cambie algo fuera del proceso. Y una corrección gratis para cómo se
evalúan agentes: un banco que reporta `pass@1` sin `pass^k` no distingue un sistema que acierta
de uno con el que se puede contar, y la diferencia llega a `0,196` en este registro.

---

# Apéndice A, Artefactos

| artefacto | contenido |
|---|---|
| el control nulo | el andamiaje por prompt se conserva en el registro y no se ejecuta nunca: dominado por `direct` en toda celda medida, a igual utilidad y jamás más barato. Es la evidencia de que andamiar por fraseo no compra nada, no un brazo |
| `PATTERNS.md` | catálogo de patrones: 10 estructurales, 4 de control, 15 anti-patrones, con aplicabilidad enunciada sobre el vector de features |
| `ANALYSIS.md` | el análisis de fallas de §8 completo, por paradigma y por celda |
| `GATE.md` | ocho criterios binarios de publicación y su veredicto actual |
| `PLAN.md` | historia de revisiones de la tesis, incluidos dos encuadres superados y por qué |
| `D:\Apps\MAPO\lab` | el harness: 15 paradigmas registrados, de los cuales 12 corren la campaña, 9 brazos de recuperación implementados de los cuales 2 corrieron alguna vez, 4 superficies de herramientas, 4 niveles de garantía, 12 herramientas, generador de corpus con verificador independiente, 573 aserciones chequeadas por máquina (521 + 52 en dos suites) |

Siete de los quince anti-patrones del catálogo son errores cometidos y medidos en este trabajo,
dos de ellos contra predicciones registradas de antemano.

---

# Referencias

Los trabajos se identifican por su identificador persistente. Los marcados con ★ se leyeron
completos en la fecha indicada; de los demás se verificó lo que este paper les atribuye, y donde
el original no aporta un título corto se lo cita por identificador con la atribución que el cuerpo
le hace.

### Búsqueda y selección de workflows

Select-then-Solve. arXiv:2604.06753, selección de paradigma por tarea; ★ leído completo
el 2026-08-26. · FlowBank. arXiv:2606.11290, portafolio offline, selección por consulta. ·
TRACE-Router. arXiv:2607.22465, ruteo a granularidad de traza de tarea. ·
Uno-Orchestra. arXiv:2605.05007, política conjunta de descomposición y despacho. ·
Optimización de workflows como código, con MCTS sobre operadores: arXiv:2410.10762. ·
Query Optimization for Agentic Query Execution. arXiv:2606.03152, la analogía con la
optimización clásica de consultas. · arXiv:2608.00106, ruteo sobre features textuales, con
*confidence gate* declarado como trabajo futuro sin evaluar.

### Cascadas y ruteo de modelos

FrugalGPT. Chen, Zaharia y Zou (2023), *FrugalGPT: How to Use Large Language Models While
Reducing Cost and Improving Performance*. arXiv:2305.05176, la cascada de modelos con puntaje
de aceptación por escalón. · Hybrid LLM. Ding et al. (2024), *Hybrid LLM: Cost-Efficient and
Quality-Aware Query Routing*. arXiv:2404.14618. · RouterBench. Hu et al. (2024). arXiv:2403.12031.
· RouteLLM. Ong et al. (2024), *RouteLLM: Learning to Route LLMs with Preference Data*.
arXiv:2406.18665. Las cuatro deciden entre modelos con el mismo control de flujo; ninguna
declara detector por tarea ni capacidades del brazo. Citadas por sus afirmaciones de portada,
no leídas completas (2026-09-01).

### Votación y programación con módulos de lenguaje

Self-Consistency. Wang et al. (2022), *Self-Consistency Improves Chain of Thought Reasoning in
Language Models*. arXiv:2203.11171. · Universal Self-Consistency. Chen et al. (2023).
arXiv:2311.17311. Antecedentes directos de §7.5; lo que se agrega está dicho en §2.5. · DSPy.
Khattab et al. (2023), *DSPy: Compiling Declarative Language Model Calls into Self-Improving
Pipelines*. arXiv:2310.03714, antecedente de ingeniería de «el flujo de control vive en el
código». · Kautz (2022), *The Third AI Summer*, AI Magazine 43(1), la taxonomía neurosimbólica
que §2.4 usa para ubicar a HADD. · Agent2Agent, protocolo de tarjetas de agente (Google, 2025),
vecino de ingeniería de §7.4 por el lado de las descripciones de habilidades.

### Gobernanza simbólica y motores de creencias

★ Jaime y Errecalde (2026). MINERVA/HADD. *A Production Architecture for Hybrid Agents
with Deterministic Decisions in Regulated Domains.* Zenodo 10.5281/zenodo.20003407 (leído
2026-08-26). Antecedente de vocabulario de §6.2: arquitectura declarada, sin medición. Su
compuerta companion (EVR, Zenodo 19791686) no está disponible públicamente al 2026-09-01 y no
se cita como mecanismo. · SCL / Soft Symbolic Control. *Structured Cognitive Loop.* arXiv:2511.17673.
· Nous. arXiv:2606.22030, confiabilidad acotada por la procedencia del canal. · MemIR.
arXiv:2605.25869, memoria tipada por procedencia. · Eywa. arXiv:2605.30771, promoción de
hechos tras validadores. · HEP. arXiv:2607.09195, evolución auditable de hipótesis. ·
arXiv:2607.01507, diagnóstico empírico del jardín de senderos que se bifurcan. · arXiv:2603.27299
política determinista, auditable y versionada, *escrita por humanos*. · ProvenanceGuard.
arXiv:2607.01236, pisos de procedencia sobre acciones. · Contratos de delegación e identidad
atestiguada. arXiv:2603.18043. · arXiv:2605.26667, atribución de error por registro de
operaciones intermedias.

### Aprendizaje sin actualizar pesos

Kintsugi. *Learning Policies by Repairing Executable Knowledge Bases.* arXiv:2605.09487,
establece el paso de instalación filtrada por verificador que §2.10 le cede. · EnvProbe.
*Ask the World Before Acting: Budgeted Environment Probing for World-Model Calibration.*
arXiv:2606.31422. · SCM y afines, consolidación de inspiración biológica: arXiv:2604.20943,
arXiv:2605.26099. · arXiv:2606.10457, destilación de control desde trazas de expertos a reglas
reinyectadas *como texto de prompt*.

### Predicción selectiva, deferral y evaluación

Smith y Winkler (2006), *The Optimizer's Curse: Skepticism and Postdecision Surprise in
Decision Analysis*, Management Science 52(3), el sesgo del máximo que el piso de ruido de §7.3.3
descuenta. · Chow (1970), *On optimum recognition error and reject tradeoff*. · Mozannar y Sontag, deferral con
surrogate consistente [PMLR v119]; Verma y Nalisnick, deferral one-vs-all calibrado:
arXiv:2202.03673. · arXiv:2605.07805, descomposición de incertidumbre que unifica abstención y
ruteo con garantías *distribution-free*. · eDAct. arXiv:2604.07036, deferral por umbral
calibrado de incertidumbre. · arXiv:2606.19544, confiabilidad sin validez en jueces LLM, y sobre-
estimación por acuerdo crudo. · arXiv:2512.15751. · Survey. *From Agent Traces to Trust: A
Survey of Evidence Tracing and Execution Provenance in LLM Agents.* arXiv:2606.04990.

### Métrica y linaje clásico

tau2-bench. Sierra, 2025. `github.com/sierra-research/tau2-bench`, origen de `pass^k`.

El linaje de §2.9. Alchourrón, Gärdenfors y Makinson (1985), *On the logic of theory change*.
Doyle (1979), *A truth maintenance system*. de Kleer (1986), *An assumption-based TMS*.
Buneman, Khanna y Tan (2001), *Why and where: a characterization of data provenance*. Green,
Karvounarakis y Tannen (2007), *Provenance semirings*. Rao y Georgeff (1995), *BDI agents: from
theory to practice*. Laird, Newell y Rosenbloom (1987), *SOAR: an architecture for general
intelligence*. Hebb (1949), *The Organization of Behavior*. Dung (1995), *On the acceptability
of arguments and its fundamental role in nonmonotonic reasoning, logic programming and n-person
games*.

Marco normativo. Reglamento (UE) 2024/1689 de Inteligencia Artificial, arts. 12 y 14.
Reglamento (UE) 2016/679 (RGPD), art. 22.
