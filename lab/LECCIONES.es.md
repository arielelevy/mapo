# Lecciones — lo que este banco probó, no lo que se supuso

> **Qué es esto.** Reglas que salieron de medir, cada una con el número que la sostiene.
> No es una lista de buenas prácticas: si una entrada no tiene medición o demostración
> detrás, no va acá.
>
> **Para qué sirve.** Varias son material de paper por sí solas — sobre todo las que son
> resultados negativos bien instrumentados, que es lo que casi nadie publica. Las otras
> son reglas de método que este proyecto pagó para aprender.
>
> **Cómo se lee cada entrada.** `MEDIDO` trae número y de dónde sale. `DEMOSTRADO` es
> aritmética, no medición. `MÉTODO` es una regla de trabajo que se ganó en carne propia.

---

## 1. Sobre herramientas y capacidades

### 1.1 Tools declaradas no son tools usadas · `MEDIDO`

Cuatro herramientas de memoria de trabajo (`note`, `notes`, `plan`, `advance`) expuestas
sobre 28 filas dieron **un note, una compactación y cero planes**. La maquinaria de
compactación, medida aparte en **29× de reducción**, nunca se disparó.

> **Exponer una capacidad no es proveerla, y ofrecerla no es medirla.**

**Consecuencia de diseño**: todo lo que enriquezca el contexto va **incondicional desde el
entorno** (forma `managed`), no ofrecido al modelo (forma `cognitive`). El propio repo
registró la corrección después de ese fallo: *«Incondicional y determinista: el entorno
hace la contabilidad que el brazo cognitive midió que el modelo no hace voluntariamente.»*

**Corolario de instrumentación**: antes de atribuirle un efecto a una herramienta, hay que
verificar en la traza que se la llamó. Un contador por herramienta convierte «no ayudó» en
«no se usó», que son diagnósticos opuestos.

### 1.2 Una capacidad sin presión no se evalúa · `MEDIDO`

El mismo experimento, dicho al revés: en un corpus donde todo entra en un prompt no hay
presión de contexto, así que una herramienta de memoria de trabajo **no tiene trabajo**.
Medir una herramienta fuera del régimen donde existe el problema que resuelve no es
medirla.

### 1.3 Un resultado nulo bien instrumentado paga · `MEDIDO`

Ese brazo quedó siendo una **réplica accidental**, y como réplica produjo el piso de ruido
que obligó a retirar otro resultado.

---

## 2. Sobre alucinación y procedencia

### 2.1 La alucinación es admisible exactamente donde no puede volverse una afirmación · `MÉTODO`

HyDE genera una respuesta **hipotética** —inventada— y la usa como consulta. Es legítimo
porque alucina en el **canal de la consulta**: una query mala cuesta una recuperación mala,
nunca un dato falso con procedencia impecable.

Es el mismo principio que gobierna la sonda: **el modelo propone, la regla decide.**

### 2.2 Fusionar acota el modo de falla · `MÉTODO`

Cuando la conjetura entra **fusionada** (RRF sobre cuatro ramas) en vez de reemplazar, una
hipótesis mala aporta candidatos mal rankeados y **no puede desalojar lo que las otras
ramas encontraron**. El modo de falla deja de ser «peor calidad» y pasa a ser «pagaste una
llamada de más» — riesgo acotado por construcción.

### 2.3 El modelo no puede ser juez de su propia suficiencia · `MÉTODO`

Un prompt que le pide al modelo etiquetar su contexto como `proved` / `insufficient` /
`hypothetical` traslada al modelo la decisión de si tiene evidencia suficiente. Es la misma
falla que gatear una acción con la opinión del modelo, escrita de otra manera.

---

## 3. Sobre qué se puede medir, y qué el diseño impide medir

### 3.1 Ser corregible implicaba tener detector · `MEDIDO`

El campo `has_oracle` servía para dos cosas a la vez —«el banco tiene clave de respuestas»
y «existe un detector barato en runtime»— y valía `True` siempre. Con detector en todas las
tareas, la regla de **cascada** dispara en prioridad 90 y la de **selección**, en 70, no se
evalúa nunca.

**El banco no podía medir selección porque el corpus se lo impedía por construcción.**
Medido: declarar el detector por celda hace caer la cascada de **22 a 2 de 26**.

> Una hipótesis que el diseño experimental no deja disparar no está siendo puesta a prueba,
> aunque el experimento corra y produzca números.

### 3.1b Un generador que vuelve trivial una dependencia no puede falsificar el patrón que existe para esa dependencia · `MEDIDO`

`graph_traverse` quedó falsificado con u=0,000 tras construir un índice de entidades. La
objeción obvia era que el índice se arma con output del modelo sin verificar, así que
podía estar midiendo el extractor. Se chequeó: **177/177 entidades aparecen literalmente**
en la unidad que las declara, y **las dos cadenas C3 están conectadas**, salto por salto.
La travesía tenía sus aristas.

Pero el 100% no es tranquilizador: **es el hallazgo**. El corpus tiene **cero** formas
abreviadas, **cero** anáfora, y cada entidad en una sola forma canónica escrita completa.
No hay nada que deduplicar ni que agrupar. El extractor acierta todo porque **la parte
difícil de extraer entidades no existe ahí**.

> Una falsación vale para el régimen en el que corrió. Si el generador vuelve gratis
> justamente la dependencia que le da sentido al patrón, lo que se falsificó es el patrón
> **en un mundo donde no hacía falta**.

Es la misma forma que «ser corregible implicaba tener detector», llegando desde otro lado:
en los dos casos el diseño del corpus decide qué hipótesis pueden siquiera ponerse a
prueba, y en los dos casos lo hace en silencio.

---

### 3.2 Una mejora que aplica a todos los patrones no es un patrón: es un factor · `MÉTODO`

Si se pliega adentro de cada brazo, la comparación deja de ser «A vs B» y pasa a ser
«A-con-la-mejora vs B-con-la-mejora». El diseño correcto es **factorial**, reportando
**efecto principal e interacción** — y sólo la interacción justifica seguir teniendo brazos
distintos.

**Y hay un riesgo específico para cualquier claim de ruteo**: el valor del ruteo *es la
dispersión entre brazos*. Una mejora transversal **comprime esa dispersión**, así que puede
reducir la brecha de oráculo del ruteo **aunque mejore el sistema entero**.

### 3.3 Soldar una dimensión adentro de un brazo contamina el hallazgo · `MEDIDO`

`Blackboard` está definido dentro de `dag_strategy` y no lo usa nadie más. `dag_strategy`
es el mejor fijo en `gold_transfer`. Entonces **«el efecto dag_strategy» es la conjunción de
la topología de olas y el estado compartido, y nada en el registro las separa.**

### 3.4 Contestá la pregunta antes de pagarla · `MÉTODO`

Dos veces en un día:

- **P17a** —qué regla decide— depende de prioridades y features, no del modelo. Se contestó
  **offline, con cero tokens**, y confirmó que el corpus hacía lo que se decía.
- **La cobertura de θ** —si hay estadísticas donde el corpus nuevo aterriza— también.
  Resultó que **265 de 270 episodios vivían en regiones `oracle`** mientras 20 de 26 tareas
  nuevas eran `no_oracle`. Correr sin verificarlo habría gastado ~14M tokens para descubrir
  «θ no tiene datos» en vez de «la selección no paga».

---

## 4. Sobre estimadores y aprendizaje

### 4.1 Una transformación monótona no puede cambiar un argmax · `DEMOSTRADO`

La regla Hebbiana del proyecto, `w ← (1−δ)·w + η·Δ` con Δ = +0,5 si fue el mejor, tiene
punto fijo

```
w* = η(0,8p − 0,3)/δ = 1,6p − 0,6
```

estrictamente creciente en la tasa de victorias `p`. Y el router ya ordena por `p`. Así que
**«los tres selectores eligen idéntico» no es una coincidencia empírica ni un
hiperparámetro mal puesto: está forzado.**

> Un estimador **con** memoria sólo puede diferir de uno **sin** memoria cuando lo que
> estima **se mueve**.

**Y hay que leer la demostración por lo que dice, no por lo que sugiere.** Prueba que el
peso no puede mejorar **la selección de paradigma**. No prueba que el peso sea inútil, y
casi lo tiramos por confundir las dos cosas: ya gobierna la **poda** —es el reloj de
decaimiento con el que una stat sin episodios llega al piso y se elimina— y la propiedad
que lo vuelve redundante para un argmax (ser marginal y monótono) **no aplica a una
asociación entre pares**, que es la dirección donde puede servir.

> Una demostración de redundancia acota **un uso**, no una pieza.

### 4.2 El blanco se mueve · `MEDIDO`

**4 de 5 regiones comparables cambian de ganador entre corpus (80%).** O sea que hay un
trabajo real para un rastreador de deriva — que no es «estimar mejor» sino «detectar que la
región está en transitorio», y cuya acción correcta es **bajar la confianza y abstenerse**.

### 4.3 Un piso duro convierte un rastreador en un ancla · `DEMOSTRADO`

Con piso `0,01`, todo brazo con `p ≤ 0,375` se aplasta contra él y **los brazos débiles se
vuelven indistinguibles entre sí**. Salir del piso cuesta ~5 victorias consecutivas: el
rastreador se atrasa justo cuando debería adelantarse.

### 4.4 Un episodio es una celda, no un trial · `MÉTODO`

Las réplicas son mediciones repetidas de lo mismo, no evidencia independiente. Contarlas por
separado es **pseudorreplicación**, y computar «fue el mejor» sobre trials crudos deja que
una réplica con suerte cobre el refuerzo que la media de su paradigma nunca ganó.

### 4.5 La candidata no puede ajustarse con el bloque que la va a juzgar · `MÉTODO`

Ajustar con todos los episodios y después entregarle ese mismo bloque a la guarda de
promoción es marcarse el propio examen.

---

## 5. Sobre el costo

### 5.1 La selección compra calidad sólo cuando los tokens son gratis · `MEDIDO`

Barrido de λ sobre el cohorte de ruteo de `gold_p16`:

| λ | neto vs mejor fijo |
|---:|---:|
| **0,00** | **+0,1211** |
| 0,02 | −0,4043 |
| 0,05 | −1,2888 |
| 0,40 | −11,6089 |

**Sin cobrar el costo, el ruteo captura. Cobrar cualquier precio realista lo borra.** La
frase estaba escrita antes de que existieran los números.

> Cualquier resultado de orquestación reportado **sin** cobrar el costo debería leerse como
> el punto λ=0 de una curva que nadie mostró.

### 5.2 Rutear hacia una región muerta paga el precio entero y no compra nada · `MEDIDO`

C3 da **−3,7804**: es la región oráculo-cero, donde todos los paradigmas puntúan 0,000 y la
penalidad de costo convierte una ruta cara en pérdida profunda. **Es el argumento más claro
a favor de la abstención que tiene este registro.**

---

## 6. Sobre la variable que domina el resultado

### 6.1 El recall de evidencia es varias veces más grande que la diferencia entre paradigmas · `MEDIDO`

En `gold_transfer`: utilidad **0,869** con recall completo contra **0,336** con recall
parcial. Esa brecha de **+0,533 es 4,2× la mayor ventaja entre paradigmas** (0,126).

**Sobrevive estratificando** por celda —C1 +0,333, C2 +0,183, C4 +0,398, C7 +0,417— así que
no es dificultad de tarea disfrazada. Y es **máxima en C5 (+0,721)**, exactamente la celda
donde el ruteo más perdió.

### 6.2 Lo determina el paradigma, no la tarea — y la región casi no lo ve · `MEDIDO`

Fuera de muestra, ajustando en tres corpus y prediciendo en uno nunca visto:

| predictor | R² fuera de muestra |
|---|---:|
| constante | −1,3% |
| **región** — lo que la decisión *ve* | **3,8%** |
| **paradigma** — lo que la decisión *elige* | **60,0%** |

**Elegir paradigma es elegir cuánta evidencia se va a leer.** El ruteo no arbitra al margen
de la variable dominante: **es la palanca principal sobre ella, y la acciona casi a ciegas.**

---

## 7. Sobre el registro y la disciplina experimental

### 7.1 Preregistrar en prosa deja margen; congelar el código del veredicto no · `MÉTODO`

Una predicción en prosa se puede leer de varias maneras después de ver los números. El
archivo que **juzga** entra a la historia de git antes de que exista una sola fila, y el
veredicto es lo que imprima.

### 7.2 Un preregistro se disuelve si la regla cambia por debajo · `MEDIDO`

Demostrado, no argumentado. Sobre **las mismas filas** de `gold_p16`, aplicar el
prerrequisito de detectores honestos mueve el número prerregistrado:

| | antes | después |
|---|---:|---:|
| neto vs mejor fijo | **−1,2888** | −1,6931 |
| acciones | casc 20 · sonda 1 · defer 1 | **casc 22** |

Dos tareas con gold vacío pasan de «sin detector» a «con detector» y entran a la cascada.
**Nada en la salida habría dicho que la regla cambió.**

### 7.3 La región es una función de los features, no un dato de la corrida · `MÉTODO`

Congelarla adentro de cada fila es lo que hizo que un cambio de vocabulario —de tres
segmentos a cuatro— pasara desapercibido: se comparaban dos vocabularios distintos y se lo
llamaba transferencia.

### 7.4 Un conteo no distingue estrategias · `MÉTODO`

`{búsqueda: 2, lectura: 2}` no separa «busco, leyó, busco, leyó» de «busco, busco, leyó,
leyó»: mismo histograma, dos políticas distintas. La **secuencia** es lo único que permite
aprender asociaciones entre pares.

## 8. Sobre la frontera entre el producto y el modelo

### 8.1 El invariante se cumple entre patrones y se rompe adentro de cada uno · `MEDIDO`

«El LLM es sensor: jamás maneja flujo de control» se cumple en la **elección** de paradigma.
No se cumple adentro de ninguno: el tope de iteraciones es una constante en código **o el
modelo cortando**, la herramienta siguiente la elige el modelo, y en el DAG **el modelo
dibuja el grafo** — produce las sub-preguntas y sus dependencias, y el código sólo las
topologiza.

El propio módulo ya nombraba el olor: *«una topología con una docena de umbrales es una
topología cuyo comportamiento se fija a mano en vez de derivarse»* — **Constant Soup**.

### 8.2 Los frameworks resuelven el handoff con el mismo anti-patrón · `MEDIDO`

Microsoft Agent Framework inyecta herramientas de handoff que el agente invoca; OpenAI
Agents SDK genera `transfer_to_<agente>`; Google ADK llama a `transfer_to_agent()` por
«LLM-driven delegation». **Los tres transfieren el control con una llamada que emite el
modelo.**

La alternativa medible: misma **estructura** —alcances independientes, transferencia de
propiedad, contexto completo— y **otra autoridad**: una regla determinista sobre la base de
creencias, con piso de procedencia. Reproducible, gateable y auditable.

### 8.3 Una constante que depende del dominio no debería ser una constante · `MÉTODO`

Cuándo parar, cuántos nodos, qué orden de herramientas: todo eso depende del dominio, del
corpus y de cómo está armado el sistema. Un umbral ajustado sobre un corpus sintético y
horneado en el código es Constant Soup otra vez, sólo que con un número mejor elegido.

**Y ya hay maquinaria probada para la alternativa**: el piso de garantía se aprende de
estadísticas de rechazo tipado por región, con guarda de replicación, y viaja en el bundle
firmado. La generalización es una frase: **toda constante que dependa del dominio debería
ser una cantidad aprendida por región, protegida por la guarda.**

---

### 2.4 Un contrato constructivo detiene el token, no la proposición · `MEDIDO`

C-NUM hace que el modelo escriba **nombres de ranura y nunca dígitos**, así que ningún
numeral inventado puede aparecer: el proyector lo garantiza por construcción. Contra eso se
construyeron cinco familias de contraejemplo y **las cinco pasaron el contrato sin una sola
queja**, mientras el control positivo emitía normalmente.

Las cinco comparten una forma: **lo que falsea la oración vive en la prosa conectiva**
—referente, modificador, negación, verbo, condicional— y **la prosa conectiva no ocupa
ninguna ranura**. El proyector y el residuo son complementarios por construcción.

> «Imposible de producir» es **falso** mientras el binding lo medie el modelo. Lo defendible
> es *«verificado por construcción sobre `π_C`, con residuo declarado y medido»* — y un
> residuo sin número no es una salvedad, es una excusa.

La única dirección que lo achica es **agrandar el proyector**: llevar la prosa conectiva de
«lo que el modelo escribe» a «lo que el contrato genera». Eso no elimina el residuo, lo
**relocaliza** a la distancia entre la plantilla elegida y la que correspondía — más chica y,
sobre todo, **enumerable**.

---

### 7.8 Lo que es función de un registro se recomputa; sólo lo irreducible se guarda · `MÉTODO`

Una fila es el registro de lo que pasó. Pero **la utilidad no es lo que pasó: es una función
de lo que pasó**, igual que la región es una función de los features (7.3).

Congelar una función adentro de la fila tiene una consecuencia que no se ve hasta que es
tarde: el día que la función cambia, el registro queda partido en dos épocas y **nada en el
archivo dice a cuál pertenece cada fila**. Dos filas con la misma utilidad escrita pueden
haber sido puntuadas por reglas distintas.

> **La regla: lo derivado se recomputa al leer, no se guarda al escribir.** Si el costo
> obliga a guardarlo, hay que guardar **también la versión de la función** que lo produjo —
> que es lo mismo que exige la huella de decodificación para el modelo.

Vale para las tres capas donde el banco guarda algo derivado: la utilidad, la región, y el
vector de features.

### 7.9 Un null tiene que respetar la estructura de bloque, y un test sin potencia no mide · `MÉTODO`

Dos chequeos que deciden si un `p` significa algo, y ninguno de los dos es opcional.

**El null tiene que romper sólo la hipótesis.** Al probar si el orden de llamadas lleva
señal, la unidad de resultado es la **fila**: una fila tiene una utilidad y todas sus
transiciones heredan la misma etiqueta, así que están perfectamente correlacionadas.
Permutar **por transición** rompe ese bloque y le regala al azar más variación independiente
de la que existe — el null sale más disperso de lo que corresponde y el test se vuelve
imposible de pasar *por una razón que no es la señal*. El null correcto permuta **qué filas**
salieron bien, conservando cada fila con sus transiciones.

**Y hay que chequear la potencia antes de leer el `p`.** Con `n` filas de las que `k`
salieron bien hay `C(n,k)` asignaciones, así que el `p` mínimo alcanzable es `1/C(n,k)`. Si
ese piso ya supera 0,05, el estrato **no puede** dar significativo aunque la señal fuera
perfecta, y leerlo como «no hay efecto» confunde ausencia de potencia con ausencia de
efecto.

Esto no es teórico: es lo que separó a la tesis Hebbiana de un veredicto falso en las dos
direcciones. Con `n=3` el piso por celda era `1/C(3,k) ≥ 1/3` —ninguna celda podía dar
significativa— y además el criterio se satisfacía por azar en 7 de 13 celdas. Con `n=9` el
piso bajó a 0,008 y el null cayó a 0 (ver 4.6).

> Un test que no puede rechazar **no está midiendo**. Y un null que rompe la estructura de
> correlación de los datos produce números perfectamente publicables sobre una hipótesis que
> nadie puso a prueba.

### 8.3b El acoplamiento es una propiedad de la PREGUNTA, y todos los ejes computables miden el MATERIAL · `MEDIDO`

Buscando separar «hay que encadenar» de «hay que barrer» se probaron tres ejes, y ninguno
lo hace:

| eje | qué acierta | qué falla |
|---|---|---|
| **cardinalidad** | nada | C4-w4 y C5-w4 tienen **los mismos 5 units** y coupling 0,20 contra 0,70 |
| **continuidad** (COMPUTED) | C5 perfecto 6/6, C4 y C2 correctos | **C3 lee `flat`** con coupling 0,80 |
| **profundidad de puentes** | — | C2 (0,00) da 1,22 y C3 (0,60) da 1,28: indistinguibles, y C4 da **más** que los dos |

Y la sonda es complementaria a la continuidad: acierta C3 y C5, falla C4. Ninguna
combinación de dos de estos cierra, porque **los tres miden lo mismo** — el material.

**Y el material no alcanza, por una razón que no es de calibración.** Los mismos documentos
sostienen «seguí la línea de reporte un paso hacia arriba», que exige encadenar, y «cuántos
X hay», que no. Mismo corpus, mismo grafo denso de personas que se repiten, acoplamiento
distinto.

> El acoplamiento que una tarea requiere es una propiedad de **(pregunta × material)**, y
> todos los ejes computables disponibles son función del **material solo**. No es que falte
> el eje correcto: es que la mitad de la información no está ahí.

**Consecuencia sobre el retículo, y es incómoda.** El único componente que lee la pregunta
es el modelo, así que el acoplamiento **no puede ser `COMPUTED`**. Lo máximo alcanzable es
`ELICITED` sobre la pregunta, *verificado* contra el material — que es exactamente lo que la
sonda hace. Sus 9 de 14 pueden estar cerca del techo de una lectura de una sola unidad, y
no de un umbral mal puesto.

*Salvedad de la medición de profundidad*: usa una regex de nombres propios como proxy de
puente, y sobre C5 no encontró ninguno. El contraste C2 contra C3 —el que decide— no
depende de eso.

---

### 8.4 «Esta unidad no alcanza» tiene dos causas y una sonda de una unidad no las separa · `MEDIDO`

La sonda quedó arreglada —de resolver **0 de 14** a acertar **9 de 14** contra la verdad
declarada— y los cinco fallos que quedan no son ruido: **cuatro son las cuatro tareas C4**,
donde `truth_coupling` es 0,20 y la sonda dice 0,85.

El sensor tiene razón en lo que observa: la unidad **no** se basta para contestar. El
código tiene razón en lo que verifica: hay un puente literal a otra unidad. Y la conclusión
igual es falsa, porque **«no me alcanza» tiene dos causas distintas**:

| causa | qué hace falta | celda |
|---|---|---|
| la respuesta está **en otro lado** | seguir un vínculo | C3, C5 — acoplamiento |
| la respuesta está **en todos lados** | leerlo todo | C4 — cobertura |

**Desde adentro de una sola unidad, las dos se ven igual.** No es un bug del prompt ni del
verificador: es lo que una unidad puede decir. Un memo que participa de un agregado nombra
gente que aparece en otros memos exactamente como lo hace un eslabón de cadena.

> Una sonda no puede reportar una propiedad **del conjunto** desde un elemento. Lo que
> observa es local; «hay que encadenar» y «hay que barrer» son globales, y distinguirlas
> exige un dato que la sonda no tiene — **la cardinalidad, que φ sí tiene desde el
> principio y gratis**.

La consecuencia de diseño: la sonda debe reportar lo que vio —no autocontenida, puente
verificado— y **la regla** combinar eso con la cardinalidad, en vez de que la sonda emita
un veredicto de acoplamiento que no está en posición de emitir.

---

### 8.5 La cardinalidad de la RESPUESTA es implícita en la pregunta, y cada valor falla distinto · `MÉTODO`

«Listame las direcciones» significa **todas** las direcciones: nadie escribe «listame
*todas* las direcciones», el plural imperativo ya lo carga. Pero **«¿cuál fue el arma
homicida?» espera exactamente una**, y ahí la exhaustividad no aplica — pedir «todas las
armas homicidas» sería otra pregunta.

Así que no es un flag de exhaustividad: es una **cardinalidad de respuesta tipada**,
implícita en la forma gramatical del pedido, y **cada valor tiene un criterio de corrección
y un modo de falla distintos**:

| forma del pedido | qué se espera | cómo falla | ¿exhaustividad? |
|---|---|---|---|
| singular — «cuál fue el arma» | **exactamente una** | ambigüedad, varias candidatas, la equivocada | **no aplica** |
| enumerativa — «listame los nombres» | **todas** | incompleta | **sí, y es el default** |
| agregada — «cuántos X» | **un número** | mal contado por cobertura parcial | sí, para poder contar |

Confundirlas tiene consecuencias opuestas: forzar cobertura sobre una singular es pagar de
más por nada, y no forzarla sobre una enumerativa es entregar una respuesta incompleta que
parece correcta.

**Y en producción nada de esto se verifica.** Una enumeración que contesta con un
subconjunto está mal, punto. En un banco se ve, porque el F1 contra gold castiga la
respuesta incompleta — pero eso es una propiedad del *banco*. Sin gold, la única forma de
saberlo es un contrato de completitud, y **su dominio no lo declara el llamador: lo implica
la forma de la pregunta.**

> Las demandas que el diseño olvida son las que el lenguaje ya expresa sin decirlas. Y son
> justamente las que un sistema sin gold no puede recuperar después.

---

### 8.6 La cardinalidad no implica la cobertura, y leer más no compra la exhaustividad · `MEDIDO`

Al tipar la demanda por celda —vocabulario cerrado, declarado, sin parsear el enunciado—
apareció que **un eje no alcanza**. El corpus ya tenía los contraejemplos:

| celda | cardinalidad de la respuesta | cobertura que exige |
|---|---|---|
| C1 «cuál es la cuenta de X» | singular | **suficiente** — parar en el acierto es correcto |
| C5 «nombrá al único con datos contradictorios» | **singular** | **exhaustiva** — la contradicción puede estar en cualquier unidad |
| C8 «cuál es el domicilio vigente» | **singular** | **exhaustiva** — hay que ver el memo base *y* la enmienda |

En C5 y C8 la cardinalidad dice «una sola» y la lectura correcta es total. Así que el tipo
es un **par**: `(answer_cardinality, coverage_demanded)`, y `coverage` es la que decide si
parar temprano es un atajo legítimo o una respuesta que **parece bien formada y está mal**.

**Tres preguntas, registradas antes de computar, sobre 1.214 filas ya pagadas de cinco
corpus.** Las tres se miden **controlando dentro de tarea** y contra un **null que permuta a
nivel celda**, por lo que 7.9 exige: sin lo primero, las clases se comparan con
denominadores distintos —las celdas suficientes tienen pocas unidades y las exhaustivas
corren sobre anchos 4/16/48—; sin lo segundo, un eje de cuatro clases parece separar más que
uno de dos por pura granularidad.

**(a) Leer más ayuda donde la cobertura se exige.** `p = 0,028` — **y al revés de lo
predicho.** Controlando dentro de tarea, la correlación entre fracción leída y utilidad es
`+0,259` en las celdas **suficientes** y `+0,018` en las **exhaustivas** (mediana `−0,055`).

> Sobre una tarea de cobertura suficiente, leer más rastrea el éxito porque leer *es*
> buscar. Sobre una exhaustiva **no compra nada**: lo difícil no es haber visto, es
> **componer** lo visto.

Y eso mata el arreglo obvio. Frente a una enumeración incompleta la reacción natural es
«que lea todo», y el registro dice que **no funciona**: la exhaustividad no se satisface
leyendo más. Necesita una verificación **estructural** —un contrato de completitud, no un
presupuesto de lectura más grande. Es la misma forma que P18a encontró en C8, y resulta
que no era de C8.

**(b) Ninguno de los dos ejes sirve para elegir paradigma.** Contra su propio null
—permutando la etiqueta a nivel celda, que es donde vive el bloque— cobertura da `p = 1,000`
y cardinalidad `p = 0,447`. El ranking de paradigmas **no se reordena** entre clases más de
lo que se reordena por azar. La diferencia cruda que parecía favorecer a la cardinalidad
(2,56 contra 2,25) era el artefacto de tener 4 clases en vez de 2.

**(c) Y sin embargo es información que la región no tiene.** De 22 regiones observadas,
**5 mezclan las dos clases de cobertura** — `few/oracle/loose`, `many/oracle/loose`,
`many/oracle/mixed` y dos más. La región no la determina.

> **Una demanda puede ser información nueva y aun así no ser una feature de ruteo.** La
> cobertura no dice *qué paradigma elegir*: dice **qué hace falta verificar antes de
> emitir**. Es una precondición de contrato, no un eje del selector — y meterla en el
> vector de features habría sido gastar una llamada por request para no mover nada.

Es el resultado que decide `U-3`: elicitar la demanda **no se paga** con mejor ruteo. Se
paga, si se paga, con `C-COMPLETE` — la promoción que `U-4` ya enunciaba y que ahora tiene
la única justificación que le servía.

---

### 8.7 El contrato que la medición justificó no se puede medir en este corpus · `MEDIDO`

`C-COMPLETE` verifica una enumeración contra un **dominio que el código enumera**. Cruzando
las dos tablas declaradas del corpus —quién tiene detector barato y quién exige cobertura
total— la intersección es **vacía**:

| celda | detector barato | cobertura |
|---|---|---|
| C1, C7 | **sí** | suficiente |
| C2, C4, C5, C8 | **no** | **exigida** |

No es coincidencia, y una vez visto es aritmética: **exigir cobertura total y tener un
verificador barato son casi contradictorios.** Si el código pudiera enumerar el dominio de
la respuesta más barato que resolver la tarea, la tarea no sería exhaustiva — sería una
consulta. Para C2 —«listame todos los que tienen el rol R»— enumerar el dominio **es** la
extracción: el contrato no verificaría al paradigma, lo reemplazaría.

**Y el dominio que sí es barato es el que no sirve.** `view.unit_ids` se enumera gratis, así
que `C-COMPLETE` sobre unidades corre hoy. Pero es exactamente lo que 8.6 midió que **no
predice corrección**: en celdas exhaustivas la fracción leída correlaciona `+0,018` con la
utilidad. Verificar que leíste todo verifica lo que no importa.

| dominio | ¿lo enumera el código barato? | ¿predice corrección? |
|---|---|---|
| las unidades en alcance | **sí** | **no** (`+0,018`) |
| los ítems de la respuesta | **no** — enumerarlo es resolver | sí, por definición |

> **Quinto punto ciego del corpus, y de la misma familia que los otros cuatro:** ser
> gradeable implicaba tener detector; una forma canónica por entidad hacía trivial resolver
> entidades; el turno único borraba toda demanda conversacional; la ingesta no se modelaba.
> Ahora: **la demanda de cobertura y la disponibilidad de detector están perfectamente
> anti-correlacionadas**, así que el contrato que la propia medición justificó no tiene
> dónde ejercitarse.

**Lo destraba una celda, está escrita, y fue barata.** `C9_declared_roster`
(2026-08-28): el dominio de la respuesta es **estructural y está en el enunciado**, no
semántico y descubierto — «para cada una de estas cinco personas, la cuenta de
liquidación». Las cinco nombradas son el dominio: `COMPUTED`, enumerable, sin resolver
nada, y a una respuesta que trae cuatro **le falta una de una forma que el código ve**.
Reutiliza los memos que ya existen: **cero documentos nuevos**.

**Dos restricciones de construcción, y las dos cambian qué mide la celda:**

| restricción | qué mediría sin ella |
|---|---|
| el roster se toma **con paso**, no consecutivo | localidad del índice: un bloque contiguo de memos se recupera por vecindad y no por nombre |
| el roster sale de **las unidades en alcance** | ausencia (O-2), otro eje: un nombre fuera de alcance hace que la respuesta correcta sea «no está» |

El verificador exige tres cosas, y cada una bloquea una forma distinta de que el dominio
deje de serlo: cada nombre **literal** en el enunciado; cada nombre con su memo **en
alcance**; y el oráculo re-derivado con la **misma cardinalidad** que el dominio — si dos
compartieran cuenta, el F1 de conjuntos no separaría faltar de sobrar.

**Y hubo que agregar un tercer eje para poder declararla.** `has_oracle` no alcanzaba: C9
**no** tiene detector de corrección —saber qué cuenta le toca a cada nombre sigue costando
la búsqueda— y **sí** tiene dominio verificable. Son hechos distintos, y colapsarlos habría
repetido exactamente la conflación que `has_oracle` ya costó una vez. De ahí
`completeness_domain ∈ {none, from_question, from_scope, semantic}`.

Es la misma maniobra con la que C8 entró sobre la enmienda de C5, y por la misma razón: un
punto ciego se cierra con la celda que lo interroga, no con un párrafo que lo admite.
Predicciones P19a-d registradas en `README.md` antes de que exista una fila; **sin correr**.

---

### 7.11 El registro se replaya sellado, y eso es lo que sostiene la palabra «determinismo» · `MEDIDO`

La garantía del producto tiene una sola forma: **misma base de creencias ⟹ misma decisión.**
Del lado del banco eso descansa sobre una propiedad que hasta ahora estaba **supuesta**: que
una fila ya pagada se puede volver a producir sin llamar al modelo.

**Medido.** Replayando por el camino del runner —misma clase, mismos argumentos, modo
sellado— sobre 27 celdas de `gold_p17`:

| | |
|---|---|
| llamadas vivas | **0** |
| celdas comparadas | 27 |
| discrepancias en utilidad, respuesta y costo | **0** |

Que no haya *miss* demuestra que el caché alcanzó. Que la fila **coincida** demuestra que el
camino entero es determinista, y no son la misma cosa: un paradigma podría consumir las
mismas completions y componer otra respuesta.

**Y hay una condición sin la cual el replay no es posible, que conviene enunciar como
requisito y no como anécdota.** La clave de caché es `sha256(huella, payload)`, y la huella
lleva el modelo. Entonces:

> **El registro tiene que decir bajo qué decodificación se produjo cada fila.** Sin eso, un
> replay reconstruye los ajustes **adivinando**, y con el modelo equivocado no puede acertar
> **una sola clave** — un síntoma idéntico al de un caché dañado, con arreglos opuestos.

Por eso la huella se estampa en la fila y no sólo en la clave, con dos invariantes que son
distintos: un archivo **no puede mezclar** decodificaciones (error), pero que el **lector**
coincida no hace falta para analizar (aviso) — analizar no llama al modelo.

### 6.3 El formato no explica nada: los paradigmas fallan en la tarea, no en la forma · `MEDIDO`

Una explicación cómoda para una utilidad baja es que al modelo **no le sale el formato**:
devuelve prosa donde se le pidió JSON, o un objeto sin la clave, el código cae al valor por
defecto, y el paradigma queda puntuado como si no hubiera resuelto. Las dos cosas dan la
misma utilidad y piden arreglos opuestos — una se arregla en el prompt o en el esquema, la
otra retirando el brazo.

**Medido sobre el registro completo**, replayado sellado sin gastar un token:

| paradigma | filas | malformadas | descartadas | utilidad |
|---|---:|---:|---:|---:|
| `dag_strategy` | 78 | **0** | 0 | 0,610 |
| `gist_reader` | 78 | **0** | 0 | 0,429 |
| `map_reduce` | 24 | **0** | 0 | 0,625 |
| `react` | 78 | **0** | 0 | 0,422 |
| `rewoo` | 78 | **0** | 0 | 0,547 |

> **Cero.** Ninguna de las 336 filas factibles perdió nada por la forma. Las diferencias de
> utilidad entre brazos —y son grandes, de 0,422 a 0,625— son sobre la **tarea**.

**Y un cero sólo vale si el contador podía no serlo.** Un contador que nadie cablea da cero
igual, y leerlo como hallazgo sería el error que este banco existe para no cometer. Por eso
el test verifica dos cosas separadas: que el contador **se dispare** en las cuatro formas de
no entregar (sin JSON, JSON roto, clave ausente, respuesta vacía), y que **todo** sitio que
parsea salida del modelo pase la superficie.

Dos cosas se cuentan aparte, porque no son la misma falla: **malformada** —el modelo no
entregó la forma— y **descartada** —entregó la forma con elementos incompletos adentro—.

---

### 3.5 Un paradigma que construye índice adentro de un request mezcla dos economías · `MEDIDO`

Se suponía que la ingesta es asíncrona, se hace una vez, y es **independiente del patrón** —
por eso no contamina la comparación entre brazos. **Es falso para un brazo:**
`graph_traverse` construye y persiste su propio índice de entidades **adentro de un
request**, una llamada corta por unidad, pagada por la primera tarea que lo necesita.

Eso tiene dos consecuencias, y son distintas:

**La económica.** El costo del índice cae entero sobre una fila arbitraria y las demás lo
reciben gratis. Promediar el brazo mezcla **dos economías**: la de amortizar sobre todas las
consultas futuras, y la de responder una. No son comparables con un brazo que sólo responde.

**La de instrumentación**, que es la que casi se cuela sin verse: la construcción lee cada
unidad con la misma llamada que registra lecturas, así que **la fila que paga el índice
carga `units_read` y `fraction_read` del corpus entero** — y `fraction_read` es la variable
sobre la que se midió 8.6.

**Y acá el registro refuta la preocupación, que es lo que había que verificar antes de
corregir nada.** Sobre 1.214 filas:

| | |
|---|---|
| filas de `graph_traverse` | 6 |
| su `fraction_read` | **0,000** — el índice ya estaba en disco, no se construyó |
| su costo | 188–268 tokens, mediana 250 |
| 8.6 con todas | brecha `−0,241` |
| 8.6 sin ese brazo | brecha `−0,242` |

> **El mecanismo es real y ninguna medición del registro está contaminada.** No porque la
> fuga no exista, sino porque **ninguna fila de este registro la ejerció**: el índice se
> construyó antes y las seis filas lo recibieron hecho.

Lo que deja es una regla de producto, no una corrección:

> **Si la ingesta es asíncrona, de una sola vez y compartida, ningún paradigma debería
> construir estado derivado propio adentro de un request.** Levantar ese índice a la etapa
> de ingesta cambia la economía del paradigma por completo — y lo vuelve comparable, que hoy
> no lo es.

---

### 5.3 Un tercio del gasto se va en no saber cuándo parar, y la señal para saberlo existe · `MEDIDO`

En los brazos con bucle, quién decide seguir o parar es **el modelo**. El código no impone
ninguna cota que dependa de lo que ya se vio.

**El premio se mide sin gastar nada.** Dentro de una misma celda `(tarea, paradigma)` las
réplicas resuelven la misma tarea con el mismo brazo. Si dos llegan a la **misma utilidad**
y una cuesta la mitad, la diferencia no es dificultad: es cuándo cada una paró.

| brazo | celdas | gastado | evitable | | peor celda |
|---|---:|---:|---:|---:|---:|
| `dag_strategy` | 81 | 9.465.396 | 4.633.145 | **49%** | 90% |
| `react` | 78 | 2.785.139 | 556.286 | 20% | 75% |
| `rewoo` | 82 | 221.852 | 73.157 | 33% | 67% |
| `gist_reader` | 85 | 2.239.829 | 132.375 | 6% | 95% |
| `map_reduce` | 31 | 645.636 | 1.488 | 0% | 3% |
| **total** | | **17.068.519** | **5.698.802** | **33%** | |

> **Un tercio del gasto compra exactamente cero utilidad.** Y no está repartido parejo:
> los brazos con más autonomía de bucle son los que más pierden — `map_reduce`, cuyo
> fan-out lo fija el código, pierde **0%**.

**Y la señal para gobernarlo existe, pero no llegaba a la fila.** Dos defectos distintos,
que estaban dando el mismo síntoma:

| señal | por qué no servía |
|---|---|
| `barren_searches` | es un **medidor** que se reinicia al primer acierto, y la fila guardaba el valor final: casi siempre 0. No es que no pase — es que no se guarda |
| `stall_warnings` | sólo incrementa en variantes de superficie con contabilidad, y **todo estudio medido corrió en `basic`**. Su cero dice que el aviso no existe ahí, no que el sistema no se estanque |

Recuperados el **pico** y el **total** —que sí sobreviven al request— la señal discrimina:

| | réplica barata | réplica cara |
|---|---:|---:|
| `barren_peak` | 1,17 | **2,28** |
| `barren_total` | 1,24 | **2,40** |

Casi el doble. Y es del tipo que este proyecto prefiere: **contable, determinista, del
entorno** — no una instrucción más en el prompt.

**Lo que NO sirve, y hay que decirlo porque parece que sirve.** `units_read` e `iterations`
también difieren (+1,15 y +1,86), y son **el costo con otro nombre**: «hizo más» cuesta más
por definición. Una regla de parada sobre eso es circular.

> **Ausente no es cero.** La primera lectura tomó la ausencia de `barren_searches` en la
> fila por un cero medido y concluyó que la señal no discriminaba. Un `.get(clave, 0)`
> vuelve indistinguibles «se midió y dio cero» de «nunca se guardó», y son diagnósticos
> opuestos: uno cierra la línea, el otro dice que hay que instrumentar.

---

### 7.13 Una regla que no se puede evaluar al decidir no es una regla · `MÉTODO`

Dos pendientes distintos resultaron ser el mismo hecho: **«las particiones descubiertas no
gobiernan el router»** y **«algunas usan variables posteriores a la ejecución»**. El segundo
**explica** al primero, y verlo así lo cierra en vez de dejarlo como dos misterios.

El descubrimiento de particiones buscaba umbrales sobre cuatro ejes, y **ninguno de los
cuatro** es evaluable en el momento de decidir:

| eje | por qué no sirve |
|---|---|
| `truth_coupling` | es el **oráculo** del extractor de features. El corpus lo declara: *«NEVER fed to the router: it is the answer key»* |
| `iterations` | sólo existe **después** de correr. «Si iteraciones > 3, usar X» no se puede evaluar antes de decidir cuántas iteraciones habrá |
| `cost_tokens` | ídem |
| `cross_unit_lookups` | ídem |

> Nadie consultaba las particiones descubiertas porque **no se podían consultar**. La regla
> existía y era inaplicable por construcción — no por falta de cableado.

**Y la causa de fondo estaba una capa más abajo: el vector φ no llegaba a la fila.** Lo
único que el registro guardaba de la decisión era `region`, que ya es φ **discretizado**:
partir sobre una etiqueta categórica no encuentra el umbral, encuentra la grilla que alguien
eligió antes. Así que el descubrimiento sólo podía partir sobre lo que quedaba — el oráculo
y tres variables posteriores.

Cerrado en tres piezas:

1. **φ va a la fila** (`n_units`, `phi_coupling`, `phi_horizon_unknown`, `phi_continuation`),
   conservando `None` como «no establecido» y nunca como cero.
2. **Los ejes quedan tipados**: `DECISION_TIME` gobierna, `POSTERIOR` **diagnostica** —«los
   casos caros comparten esto» sigue siendo útil— y `FORBIDDEN` **levanta**.
3. **El test ponía la señal sobre el oráculo.** Verificaba que el descubrimiento encontrara
   una partición que el router jamás podría evaluar: encontraba la regla y la regla no
   servía, y el test pasaba igual. Ahora la señal va sobre la **estimación**, que es lo que
   el router ve — y sigue encontrándola, con umbral 0,522 y 0,89 de separación retenida
   fuera de muestra.

> **Un test puede verificar exactamente lo que se le pide y aun así no verificar nada útil,
> si lo que se le pidió es que encuentre algo inaplicable.**

---

### 7.14 La confianza sólo se gana donde dos ajustes coinciden, y nunca coincidieron · `MEDIDO`

`S-4` preguntaba qué hacer con el acoplamiento: aceptar que tope en `ELICITED` verificado,
sondear sobre dos unidades, o darle a `C4` una regla de cobertura propia. Se leía como una
elección de diseño. **Resultó ser una cadena causal completa, y ninguno de sus eslabones lo
decidió nadie.**

| eslabón | verificado en el código |
|---|---|
| los estudios corren en **A1** | es el default del parámetro `assurance` de `report()` |
| `log_belief_base` es `True` **sólo en A2/A3** | los dos perfiles bajos lo tienen en `False` |
| ⇒ nunca se escribió un log de creencias | `results/*/beliefs/` estaba **vacío** |
| ⇒ la calibración nunca se computó | ningún archivo de calibración existía |
| ⇒ `trusts_elicited` nunca se ganó | y el default es **no confiar** |
| ⇒ el piso derivado es `OBSERVED` | `BeliefPolicy.from_trust(False, …)` |
| ⇒ la regla de acoplamiento exige la **sonda** | y la sonda resuelve **9 de 14** |

**Y hay un eslabón más, que es el que lo cierra del todo.** Forzando `A2` sobre el registro
existente el log **sí** se escribe —138 registros, sin gastar un token— y aun así la
calibración da **cero proposiciones**. La razón está en su propia definición:

> Sólo se puntúa una creencia `ELICITED` cuando existe una `OBSERVED` **sobre la misma
> proposición, en la misma base**. Evidencia adjudicando opinión.

La única cosa que produce una `OBSERVED` sobre acoplamiento **es la sonda**. Así que un par
puntuable requiere que, en el mismo request, la sonda haya corrido **y** la base se haya
registrado — o sea A2 **y** sonda a la vez.

> **La maquinaria que permite ganar la confianza exige una coincidencia de dos ajustes que
> nunca ocurrió.** No está rota ni mal diseñada: nunca tuvo la oportunidad de correr.

**Y eso decide `S-4` sin necesidad de elegir entre las tres opciones.** (b) —sondear dos
unidades— duplica el costo de una sonda que ya costó 83k tokens, para un eje que `S-3` midió
que apenas separa (C2 = 1,22 contra C3 = 1,28). (c) —darle a `C4` una regla de cobertura—
choca contra 8.7: el dominio barato de `C4` es el alcance, y la fracción leída correlaciona
`+0,018` con la corrección. Verificaría lo que no importa.

Queda **(a)**, y ya no es una resignación: hasta hoy el piso `ELICITED` de A2 era
**inalcanzable por construcción** (7.12), y ahora hay un camino — que exige **ganarlo con
calibración medida**, que es exactamente la disciplina del proyecto. Lo que falta no es una
decisión: es **una corrida en A2 con la sonda encendida**, la primera que produciría un par
puntuable.

---

### 8.8 Producción puede alimentar la calibración, nunca la utilidad · `MÉTODO`

`serve.py` decidía, ejecutaba, respondía — y **no escribía nada**. Dos consecuencias, y son
las mismas que el banco ya pagó tres veces:

| lo que no se escribía | qué se pierde |
|---|---|
| la decisión | el EXPLAIN existe **sólo mientras dura la respuesta**. Un artefacto de explicación que no se puede consultar después no explica: decora |
| la base de creencias | la calibración nunca se computa, así que `trusts_elicited` **no se gana nunca en producción** — la misma cadena de 7.14 |

Se cierra persistiendo las dos cosas, y con una asimetría que hay que enunciar porque no es
obvia: **lo que se registra no es simétrico entre lo que el producto sabe y lo que θ
necesita.**

> Un `Episode` —que es lo que θ aprende— lleva `was_best`, y eso exige saber qué habrían
> hecho **los otros paradigmas**. Producción corre **uno solo**. Fabricar ese campo
> enseñaría que el brazo elegido siempre gana, que es la forma exacta de que un sistema
> aprenda de su propia elección.

Así que el bucle se cierra **hasta donde la evidencia alcanza**:

| producción alimenta | por qué puede |
|---|---|
| **calibración** | opinión contra observación, y las dos existen en el mismo request: la sonda observa lo que el extractor había estimado. Se adjudica sin contrafáctico |
| **utilidad de θ** | **no puede** — sin detector barato no hay con qué saber si otro brazo lo habría hecho mejor |

Cerrarlo del todo necesita exactamente lo que `has_oracle` declara, y **casi ninguna tarea
real lo tiene**. Ése es el límite honesto del aprendizaje desde producción, y decirlo es
preferible a un bucle que parece cerrado porque se alimenta de sí mismo.

**Y una nota sobre cómo apareció.** Nada ejercitaba `serve.answer()`. Un residuo de otra
corrección —un parámetro que ya no existía— quedó ahí, **en el mismo día en que el mismo
residuo apareció en `report()`**: dos caminos sin cubrir, el mismo descuido dos veces. Ocho
métodos públicos del runner tampoco tenían una sola prueba, y son los que producen todos
los veredictos.

---

### 2.5 El retículo ordenaba una dimensión y hacían falta dos · `MÉTODO`

`ASSUMED < ELICITED < OBSERVED < COMPUTED` ordena **cómo** se obtuvo una creencia, y
alcanzaba mientras todo lo que entraba a la base fuera **sobre el request de adelante**.

Una asociación aprendida rompe eso. Es aritmética exacta sobre un ledger —por procedencia
**es** `COMPUTED`— y sin embargo no dice nada sobre este pedido: dice que en pedidos
parecidos, antes, tal transición acompañó al éxito.

| dónde ponerla | qué mentira sería |
|---|---|
| `COMPUTED` a secas | una **regularidad estadística podría gatear una acción irreversible**, que es exactamente lo que el piso existe para impedir |
| degradada a `ELICITED` | no es la opinión de un modelo: es una frecuencia **medida y reproducible** |

> **El problema no era que faltara un casillero en la escala: era que la escala mide una
> cosa y hacían falta dos.** `Scope ∈ {REQUEST, POPULATION}` separa *sobre qué es* la
> creencia de *cómo se obtuvo*, y el piso de las acciones pasa a exigir las dos: procedencia
> suficiente **y** alcance de este request.

Así la asociación entra honesta en los dos ejes —`COMPUTED` sobre `POPULATION`— y queda
estructuralmente fuera de lo irreversible **sin degradarle la procedencia**.

**Y un invariante viejo atajó un error de diseño en el camino.** `Belief` exige que
`COMPUTED` lleve credencia exactamente 1,0, porque una computación con credencia menor no
es una función pura del payload y la procedencia sería mentira. El primer intento ponía la
*fuerza* de la asociación como credencia — y el invariante lo rechazó, con razón:

> Lo que el ledger sostiene con certeza no es **que convenga** la transición: es que **su
> fuerza medida vale lo que vale**. Eso sí es aritmética exacta. La proposición pasa a
> afirmar la **medición**, con la fuerza en el valor, y quien quiera actuar la lee y decide
> — la creencia no decide por él.

---

### 5.4 Un modelo caro resuelve con menos tokens — pero sólo donde la tarea es difícil · `MEDIDO`

La hipótesis del autor: un modelo más caro cuesta más por token **y debería resolver con
menos llamadas**, así que el presupuesto no puede estar en tokens. Contestable **sin gastar
un token**: `gold_v2` y `gold_deep` están corridos en los dos modelos, y la comparación se
arma **uniendo estudios**, nunca juntando filas.

| corpus | utilidad del caro | del barato | tokens del caro / del barato | **punto de equilibrio** |
|---|---:|---:|---:|---:|
| `gold_v2` (~18k) | 0,551 | 0,277 | **1,90×** | 0,53× |
| `gold_deep` (~483k) | 0,680 | 0,381 | **0,81×** | **1,24×** |

> **La hipótesis se confirma, y la condición es la dificultad.** En el corpus difícil el
> modelo caro usa **menos** tokens para el mismo trabajo; en el fácil usa casi el doble.
> «Resuelve con menos llamadas» no es una propiedad del modelo: es una propiedad del par
> **(modelo × dificultad)**.

**Y el número sobrio es el punto de equilibrio.** Aun donde gana, el caro puede costar hasta
**1,24×** por token y nada más. Las diferencias de precio reales entre gamas suelen ser de
un orden de magnitud, así que **no se paga solo ni siquiera donde usa menos tokens**.

**Lo cual hace más fuerte el caso del ruteo, no más débil.** Si el modelo caro no puede
pagarse globalmente, el uso correcto es **exactamente donde gana** — y eso es 3 de 6 tareas
en un corpus y 3 de 8 en el otro. En cada uno hay al menos una tarea donde **el barato
alcanza más alto**: no es que el caro domine y el resto sea ruido.

**Dos disciplinas que este resultado obligó a fijar antes de mirarlo.** Al agregar el eje de
modelo, el baseline **también** se fortalece: «mejor fijo» pasa a ser el mejor **par**
`(modelo, paradigma)`, porque es lo que elegiría un despliegue que no rutea. Compararse
contra el mejor paradigma de **un solo** modelo habría manufacturado la brecha. Con el
baseline correcto queda en `+0,042` y `+0,009` — chica, y honesta.

Y el eje de costo sigue siendo **tokens**, lo que favorece sistemáticamente al caro. Por eso
lo que se reporta es el **punto de equilibrio** y no una cuenta: con la tarifa declarada
(`X-5a`) esto se vuelve plata.

---

### 5.5 Un rechazo que el modelo puede reintentar no es flujo de control · `MEDIDO`

`D-1` midió que **el 33% del gasto es evitable** a igual utilidad. La regla de parada se
implementó para capturarlo: pasado el umbral de búsquedas estériles, buscar **se rechaza**
con motivo tipado, y leer y responder quedan intactos. Predicciones registradas antes de
correr.

| | resultado |
|---|---|
| **P20a** el costo baja ≥ 10% | **REFUTADA** — baja **2,6%** |
| **P20b** la utilidad no cae más que el ruido | **CONFIRMADA** — cae 0,0057 contra un piso de 0,0773 |
| **P20c** muerde donde el modelo controla el bucle | **CONFIRMADA** — 2,8% contra 0,0% |
| **P20d** después del rechazo el modelo lee o responde | **REFUTADA** — **re-emite búsqueda el 69%** |

> **`P20d` explica a `P20a`.** El código rechaza la búsqueda y el modelo **vuelve a pedirla
> con otras palabras**, 69 de cada 100 veces. La regla no removió el desperdicio: le agregó
> una vuelta.

**Y eso toca el invariante, no la eficiencia.** El producto dice que el LLM es sensor y
**jamás maneja flujo de control**. Un rechazo que el modelo puede esquivar reintentando deja
el flujo de control exactamente donde estaba:

> **Rechazar una llamada no es quitarle la decisión al modelo. Quitársela es no ofrecerle la
> herramienta.**

La corrección que se sigue de la medición es estructural y no un umbral distinto: pasado el
límite, las herramientas de búsqueda tienen que **salir de la lista de specs** de las
llamadas siguientes. Ahí el modelo no puede reintentar — no porque se le diga que no, sino
porque la acción no existe.

**Lo que sí quedó establecido, y es lo que hace segura la corrección.** `P20b` confirma que
cortar la búsqueda **no cuesta utilidad**: 0,0057 de caída contra un piso de ruido de
0,0773. Así que el riesgo de la versión estructural no es contestar peor — es que el 33%
siga sin ser alcanzable, y eso lo dirá la corrida.

**Y una nota sobre `P20c`, que está «confirmada» y no significa mucho.** 2,8% contra 0,0%
cumple el criterio, pero `react` —el brazo de bucle más puro— tuvo **cero rechazos**: casi
no se estanca. La predicción acertó por `dag_strategy` y `rewoo`, no por el mecanismo que
enunciaba. Estaba anotado antes de correr y por eso se puede decir ahora.

---

### 7.15 El agregado esconde la imposibilidad que la celda muestra · `MÉTODO`

Cinco números derivados salieron mal en un solo día, y los cinco de la **misma forma**: un
valor plausible a la vista, reportado antes de chequear una cota que lo refutaba — y en los
cinco la cota estaba a una línea.

| lo reportado | qué lo refutaba |
|---|---|
| «la declaración de tools es el 43% del gasto de `rewoo`» | una declaración **no puede superar al prompt que la contiene**. Real: **0%** |
| «la brecha de oráculo cae a cero al descontar» | la utilidad está **acotada**, y el cálculo daba **−463** |
| «la señal de estancamiento no discrimina» | la clave estaba **ausente**, no en cero |

Ninguno rompió nada. Los tres **devolvieron un número que se podía leer como resultado**, que
es la forma cara: un error que rompe cuesta una corrida, uno que devuelve un número cuesta
una conclusión y no se sabe cuál.

**Y acá está la parte que no es obvia, y que sólo se ve al construir la guarda.** La cota
`parte ≤ todo` **no ataja** el 43%: a nivel agregado, 82.368 sobre 189.899 es perfectamente
posible. La imposibilidad aparece **una granularidad más abajo** — en la celda `c1-000`,
1.056 tokens de declaración sobre un prompt de 664.

> **Un promedio puede ser posible mientras cada uno de sus términos es imposible.** Agregar
> es exactamente la operación que hace desaparecer la contradicción, así que la verificación
> tiene que correr **en la granularidad donde el hecho vive** — no donde es cómodo mirarlo.

Es la misma forma que ya había aparecido dos veces con otro nombre: el piso de ruido se mide
**por celda** y no global, y la comparación pareada compara **réplicas de la misma celda** y
no medias de brazos. Las tres veces el error es agregar antes de verificar.

**Lo ejecutable**, porque una resolución de ser más cuidadoso no es una mejora: `_sanity.py`
—`share`, `bounded`, `required`, `all_present`, `paired`— **levanta** en vez de avisar, y se
llama **por celda**. Un aviso al lado de un número imposible sigue publicando el número.

---

### 7.16 «General» era una propiedad de los mundos donde se midió · `MEDIDO`

`P8` se registró el 2026-08-26 con cinco predicciones y una regla de decisión escrita, el
mundo se generó y se verificó, la corrida se hizo — **y el veredicto nunca se computó**. El
paper siguió diciendo «not yet run» durante dos días. Apareció barriendo por «declarado, no
medido», que la regla del repo llama deuda.

| | |
|---|---|
| **P8a** `react` u ≥ 0,9 en toda celda | **NO TRANSFIERE** — bajo 0,9 en **4 de 4**, mínimo **0,000** |
| **P8b** `map_reduce` u = 0 en la acoplada | **SIN N** — no corrió en este corpus |
| **P8c** `rewoo` gana C2/C4, falla acoplada | transfiere |
| **P8d** `gist_reader` u ≥ 0,75 a costo ≤ react | **NO TRANSFIERE** — u **0,118**, y **más caro** |
| **P8e** `dag_strategy` en riesgo en la acoplada profunda | transfiere |

**Dos fallan ⇒ la regla registrada dispara: los veredictos por celda pasan a ser
corpus-locales.**

**Y la objeción obvia la contesta el dato, no un argumento.** Si nada funcionara en ese
mundo, `P8a` fallaría por el mundo y no por `react`:

| tarea | mejor brazo | `react` |
|---|---|---:|
| `c2-000-w48` | `rewoo` **1,000** | 0,667 |
| `c4-000-w48` | `dag_strategy` **1,000** | **0,000** |
| `c3-001-h2` | nadie llega a nada | 0,000 |
| `c5-000-w48` | nadie llega a nada | 0,000 |

> En las dos celdas donde el mundo **es demostrablemente resoluble**, otro brazo saca
> puntaje perfecto y el «fallback general» saca 0,667 y **0,000**. La refutación no se apoya
> en las celdas que nadie resolvió.

> **`react` no es malo: «general» era una propiedad de los mundos donde se lo midió.** Un
> veredicto por celda derivado de una sola semilla no es estructural hasta que sobrevive a
> otra, y éste no sobrevivió.

**Y hay algo que decir sobre cómo se llegó acá.** Al computar el veredicto conté `P8b` —que
**no tiene celdas donde evaluarse**— como una predicción que falla, y con eso la regla
disparaba con tres en vez de dos. Es exactamente el error que 7.15 acababa de describir y
para el que se había escrito una guarda, **cometido minutos después**. Que el resultado no
cambie de dirección no lo vuelve inofensivo: cambiaba el margen con el que se afirma, y una
regla de decisión que dispara con tres cuando debería disparar con dos es una regla que
alguien puede empujar.

**Límite honesto**: 32 filas y 4 tareas es un diseño de screening, registrado como tal.
Alcanza para **refutar** una afirmación universal —un contraejemplo basta— y no para
establecer un reemplazo.

---

### 5.6 El costo que ordena la cascada está puesto a mano, y erra 2-7× · `MEDIDO`

`COST_PRIORS` son multiplicadores escritos a mano contra `direct = 1,0`. Derivados del
registro, **pareados sobre las tareas donde `direct` corrió de verdad**:

| brazo | prior | observado pareado | |
|---|---:|---:|---|
| `dag_strategy` | 12,0 | **4,0** | 3× de más |
| `map_reduce` | 8,0 | **1,2** | 6,6× |
| `reflection` | 5,0 | **1,6** | 3,2× |
| `react` | 3,0 | **2,1** | 1,4× |
| `plan_execute` | 6,0 | **7,5** | 0,8× — el único corto, y está retirado |

**Y lo primero fue averiguar quién consume ese número, porque la respuesta obvia era la
equivocada.** Iba a escribir que gobiernan la **poda de factibilidad**. Es falso:
`feasibility.admissible()` corre su propia aritmética sobre el material y el presupuesto
declarado, y **no los mira**. La poda no está afectada.

Gobiernan **dos ordenamientos**, y el segundo importa más de lo que parece:

| dónde | qué decide |
|---|---|
| `min(admissible, key=priors)` | el brazo al que se cae cuando el fallback no es admisible |
| `sorted(admissible, key=priors)` | **el orden de la cascada** |

> Con `reflection` estimado en 5,0 cuando mide **1,6**, la cascada **nunca lo prueba
> primero** aunque sea de los más baratos. Y la cascada es el mecanismo al que el paper le
> acredita haber capturado el 100% de la brecha: **empezar por el peldaño equivocado es
> exactamente el costo que la escalera existe para evitar.**

**La base de la escala también es floja, y eso no se arregla midiendo mejor.** `direct` es
el denominador y **sólo es factible donde toda la evidencia entra en ventana** — 7 tareas
en 1.008 filas. Una escala anclada a un brazo que no corre en el régimen que el producto
apunta no tiene base medible ahí.

**Y el propio código dice que el prior es transitorio**: *«relative priors only… measured
mean_cost supersedes them once theta has data»*. Así que el error vive exactamente en la
ventana donde θ todavía no aprendió — **cada despliegue nuevo y cada región nueva**, que es
donde un producto se juega la primera impresión.

---

### 6.4 La retención no se podía medir donde se midió todo lo demás · `MEDIDO`

El recall de evidencia es la variable dominante del resultado —brecha `+0,533`, y predice
fuera de muestra al 60% desde el paradigma contra 3,8% desde la región—. Pero mide si la
evidencia **se leyó**. El segundo eslabón —si **sobrevivió** hasta la llamada que
responde— nunca estuvo instrumentado.

Instrumentado ahora, y lo primero que dice es por qué faltaba:

| variante | leído | retenido | retención |
|---|---:|---:|---:|
| `basic` | 29.600 | 29.600 | **1,000** |
| `managed` | 29.600 | **8.314** | **0,281** |

> **En `basic` la retención es 1,0 por construcción**: nada saca evidencia de la historia,
> porque no hay compactación. Y `basic` es la variante de **todos** los estudios medidos.
> La medida no faltaba por descuido: **no tenía nada que decir donde se midió**.

Es el mismo patrón que ya apareció con los detectores, las entidades y el turno único: **el
banco no puede ver una variable que su propio régimen vuelve constante.**

**Y construirla mostró un punto ciego que casi la deja inservible.** El primer intento
contaba **unidades** cuyo texto siguiera presente, buscando sus primeros caracteres. Pero la
compactación **no borra**: degrada a un stub que conserva el id **y los primeros ~220
caracteres**. Ese conteo daba **4 de 4 retenidas** mientras el texto real caía al 28%.

> **Medir la mención en lugar del texto reporta «todo sobrevivió» exactamente donde nada
> sobrevivió.** Queda una sola medida —el ratio de caracteres— en vez de dos, una de las
> cuales mentía. Y sin umbral: cortar «retenido / no retenido» sería otra constante a mano.

---

### 5.7 «El costo medido supersede al prior» estaba en un comentario y en ningún lado más · `MEDIDO`

El constructor del router lo dice desde siempre: *«relative priors only… measured
`mean_cost` supersedes them once theta has data»*. **No lo hacía nadie.** `mean_cost` sólo
aparecía en `as_dict` y en un formato de impresión; el router ordenaba por el prior y por
nada más.

O sea que el prior no era transitorio: **ordenaba la cascada para siempre.**

Y el prior erra 2-7× (5.6). Con `reflection` declarado en 5,0 cuando mide 1,6, **la cascada
nunca lo probaba primero** aunque fuera de los más baratos — y la cascada es el mecanismo al
que el paper le acredita haber capturado el 100% de la brecha.

Implementado, el orden cambia donde hay evidencia y sólo ahí:

| | primer peldaño |
|---|---|
| con evidencia (`episodes ≥ 8`) | **`reflection`** — el más barato medido |
| bajo el piso de evidencia | `react` — el prior, que es lo único que hay |

**Y el costo medido resuelve además el problema de base.** Son **tokens absolutos**: no
necesitan referencia. El prior está escalado contra `direct`, que sólo es factible donde
toda la evidencia entra en ventana —7 tareas en 1.008 filas— así que su escala **no tiene
base medible en el régimen que el producto apunta**. La medida sí.

> Es el cuarto caso del mismo patrón en un día: **una capacidad completa, declarada en
> prosa, que ningún camino ejecutaba.** `theta_may_learn_online`, la calibración, las
> particiones descubiertas — y ahora la supersesión del costo.

---

### 7.17 Cuatro veces el mismo patrón es una regularidad, y se busca entera · `MÉTODO`

En un día aparecieron cuatro capacidades **completas, declaradas, que ningún camino
ejecutaba**: `theta_may_learn_online` en el perfil que nadie leía, la calibración que
ninguno de cinco sitios pasaba, las particiones descubiertas sobre ejes inevaluables, y la
supersesión del costo prometida en un comentario. **Ninguna rompía nada.** El sistema
andaba, y una garantía que alguien enunció no existía.

Buscarlas de a una es esperar a tropezarse. Un barrido mecánico —nombres definidos cuyo
único uso es su propia serialización o un `print`— produjo **20 candidatos**. La mayoría
son falsos positivos (un prompt usado dentro de un f-string), y eso está bien: **la lista no
es un veredicto**, cada caso se decide leyendo, y esa diferencia no la puede hacer un grep.

Cinco eran reales, y la peor lleva su propósito escrito al lado:

> `REGION_VOCABULARY = "regions/2-continuation"`, con este comentario encima: *«un θ
> ajustado bajo un vocabulario **nunca debe consumir regiones de otro**, y el EXPLAIN
> registra cuál habló la decisión»*. **Nada lo estampaba en ninguna parte.**

Es el mismo agujero que la huella de decodificación, con la misma consecuencia: dos filas
de vocabularios distintos son indistinguibles al leerlas, así que se promedian. **P15 pagó
exactamente eso** — el cuarto segmento del vocabulario le costó a θ toda su confianza, y
ninguna fila decía bajo cuál había sido computada. Ahora se estampa, y la lectura **se
niega** a mezclar.

Las otras cuatro, con lo que cada una enseña:

| muerta | qué enseñaba |
|---|---|
| `MAX_ATTEMPTS = 5` | resto del diseño anterior, **contradicho por el comentario ocho líneas abajo** —el presupuesto de reintento es tiempo, no intentos—. Una constante muerta que nombra un tope **se lee como un tope que existe** |
| `GUARANTEED_FULL_READ` | una propiedad declarada de tres brazos que nada consulta ni impone |
| `PRUNE_AFTER_CYCLES = 3` | la poda por ciclos **nunca ocurre** |
| `HANDOFF_FLOOR` | **mía, de una hora antes**: declarada en el patrón que escribí y reemplazada por un literal dos funciones más abajo |

> La última es la que hace útil al barrido. **El patrón no es de código viejo**: se comete
> mientras se escribe, y se comete incluso sabiendo que existe.

---

### 4.6 La tesis Hebbiana, en tres estados que conviene no mezclar · `MEDIDO`

Después de atacarla desde cuatro ángulos distintos, no es una tesis: son tres, y sólo una
sigue viva.

**(a) Como selector de paradigma: redundante, y es aritmética.** En el punto fijo
`w* = 1,6p − 0,6`, monótona en la tasa de victorias, que es por lo que el router ya ordena.
Una transformación monótona no cambia un argmax. No hace falta medirlo y ningún tuneo lo
arregla.

**(b) Como reloj de decaimiento: vivo y gobernando.** Es con lo que `consolidation.py`
poda las stats sin episodios, y nunca poda por peso solo. Funciona. Es trabajo de
conserjería, no la tesis.

**(c) Como asociación entre pares: la única dirección donde (a) no aplica**, porque una
asociación `(a → b)` no es una estadística marginal de un brazo. Cuatro intentos de
medirla, en orden de fuerza creciente:

| test | qué controla | resultado |
|---|---|---|
| dispersión de tasas por transición | nada | 0,18 — **confundido con dificultad de tarea** |
| estratificado por celda, permutación por fila | celda | 2 de 12 con potencia, **ninguno sobrevive a Benjamini-Hochberg** |
| largo de secuencia, pareado dentro de celda | tarea **y** paradigma | 6 contra 7, **p = 1,000** |
| transición que separa éxito de fallo, dentro de celda, **n=3** | tarea **y** paradigma | 10 contra 7 de mediana nula, p = 0,055 — **y el null delataba el problema** |
| **la misma, con n=9** (`P-2f`) | tarea **y** paradigma | **3 contra 0 de mediana nula, p = 0,0078** |

Los dos últimos comparan réplicas de **la misma celda**, así que tarea y paradigma quedan
fijos por diseño. La diferencia entre ellos es sólo `n`, y cambia el veredicto.

**Lo que el `n=3` estaba midiendo era el azar, y su propio null lo decía.** Con 3 réplicas,
«presente en todas las exitosas y en ninguna fallida» se satisface por casualidad casi
siempre: **la mediana nula era 7 de 13**. Un observado de 10 contra un null de 7 es una
diferencia chica entre dos números grandes, y los dos venían del mismo lugar.

Con **9 réplicas** el criterio se vuelve exigente y las dos cifras se separan:

| | n=3 | n=9 |
|---|---|---|
| celdas con transición separadora | 10 de 13 | **3 de 13** |
| mediana nula | **7** | **0** |
| `p` | 0,055 | **0,0078** |
| celdas con potencia (`1/C(n,k) < 0,05`) | 0 de 13 | **10 de 13** |

El observado **bajó** de 10 a 3, y por eso el resultado vale: lo que se cayó era el ruido.

> **La tesis Hebbiana sobre orden de herramientas queda ESTABLECIDA** — `p = 0,0078`, en
> el único de sus tres sentidos que no se deduce de la aritmética. Y queda establecida
> **débil**: 3 celdas de 13, un corpus, un modelo. Existe; no es general.

**Y hay un test previo que es lo que la hace ser sobre la TRANSICIÓN.** El largo de la
secuencia, pareado dentro de celda, dio `p = 1,000`: cuánto hizo el paradigma no predice si
acertó. Sin eso, «los éxitos tienen secuencias más largas y por lo tanto más transiciones»
explicaría el resultado entero. Con eso, no queda esa salida.

**Lo que compró P-2f, en una línea:** con `n=3` y `k` éxitos, el `p` mínimo alcanzable por
celda es `1/C(3,k) ≥ 1/3` — **ninguna celda podía dar significativa aunque la señal fuera
perfecta**. Seis réplicas más sobre 13 celdas elegidas bajaron ese piso a `0,008`.

**Y hay una condición previa que resultó cumplirse contra mi pronóstico.** Supuse que con
`t=0` + seed la secuencia estaría determinada por (paradigma, tarea) y no habría nada que
medir. Falso: **60% de las celdas tienen secuencia variable entre réplicas**, y de las 27
donde el resultado varía, 17 varían también la secuencia. Hay señal disponible; lo que
falta es `n`.

**Y la condición previa se cumplió del todo**: las 13 celdas elegidas siguen mostrando
resultado variable con 9 réplicas, así que el gasto fue donde había señal y en ningún otro
lado. 78 filas nuevas, no 1.170.

---

## 9. Lo que este registro NO estableció

Se escribe acá para que no se lo confunda con lo de arriba.

- **Que la selección no paga.** El claim de ruteo falla en dos corpus held-out
  independientes, y eso es un negativo robusto. Pero en **ninguno de los dos la regla de
  selección pudo disparar** — quedó pre-empatada tres veces. Es un resultado sobre la
  **cascada**, no sobre la selección.
- **Que el recall causa la utilidad.** La comparación de magnitudes es robusta; el cambio de
  signo de un paradigma al condicionar **no lo es**, porque el recall es consecuencia del
  paradigma y condicionar sobre una variable posterior al tratamiento no da un efecto
  directo insesgado.
- **Que la retención importa.** Está medido el **recall** —si la evidencia se leyó—, no la
  **retención** —si sobrevivió hasta la llamada que responde—. El segundo eslabón no está
  instrumentado.
- **Que el detector honesto arregla el ruteo.** Arregla que la pregunta **se pueda hacer**.
  La respuesta es P17.
