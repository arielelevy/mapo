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

### 7.5 Una decisión que vive en dos implementaciones se separa sola · `MEDIDO`

Pasó dos veces en el mismo día. El loop de herramientas tenía **tres copias divergentes**; y
`probe_then_decide` nombra **dos pasos** que un llamador daba y el otro no — con detectores
honestos, eso son **14 de 26 tareas** puntuando un placeholder como si fuera una decisión.

---

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
