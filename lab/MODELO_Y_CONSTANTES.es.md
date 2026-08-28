# Qué se rompe si cambiamos de modelo — y qué no

> **La pregunta del autor (2026-08-28):** «todo esto está tuneado para el modelo nano; con
> uno más potente, ¿no deberíamos aflojar las riendas del harness?»
>
> **La respuesta corta es que no**, y la razón importa más que la respuesta. Pero la
> pregunta acierta en algo distinto de lo que enuncia, y eso sí hay que atacarlo.

---

## Las riendas y la estructura no son lo mismo

Lo que este banco le impone al modelo es de **dos clases**, y responden al revés ante un
modelo mejor:

| clase | ejemplo | qué le pasa con un modelo más potente |
|---|---|---|
| **compensar una debilidad** | una NOTA que le avisa al modelo que el recuperador se secó | **debería encogerse**: si lo nota solo, la nota sobra |
| **garantía estructural** | rechazo tipado de la búsqueda, piso de procedencia, contrato, abstención | **no cambia** — no depende de qué tan bueno sea el modelo |

Y acá está el punto: **este proyecto pasó el día convirtiendo la primera clase en la
segunda.** El aviso de estancamiento era persuasión —«considerá leer»— y pasó a ser un
rechazo del código. Esa conversión existe **precisamente para dejar de depender de la
capacidad**.

> Aflojar las riendas con un modelo mejor desharía la tesis. El invariante no dice «el
> modelo es débil, hay que ayudarlo»: dice **«el LLM es sensor y jamás maneja flujo de
> control»**, y eso no se afloja porque el sensor mejore.

---

## Pero la pregunta acierta en otra cosa, y es real

**Los mecanismos son independientes del modelo por construcción. Las magnitudes no.**

Un modelo más potente no afloja nada — **cambia la economía**:

| lo medido | qué le pasa | por qué |
|---|---|---|
| **33% del gasto evitable** (D-1) | **se encoge** | un modelo que para solo desperdicia menos. El prize es del modelo; la regla no |
| **barrido de λ** | **se corre entero** | otro precio por token mueve el punto donde cada brazo conviene, y el **orden de los brazos puede darse vuelta** |
| **0 malformaciones** (X-3) | **robusto** | ya es cero; no puede empeorar hacia abajo |
| **leer más no compra exhaustividad** (8.6) | probablemente **sigue** | es sobre **componer**, no sobre leer — pero la brecha puede achicarse |
| **asociaciones de orden** (P-2c) | **desconocido, y en las dos direcciones** | un modelo más determinista podría tener **menos** varianza de secuencia, y ahí el efecto se desvanece por falta de variación, no por falta de señal |

Eso ya estaba anotado como deuda —«una sola familia de modelos; parte de lo aprendido puede
ser del modelo y no de la tarea, y eso está sin medir»— y es `M-3`.

---

## Lo que sí hay que hacer, y es concreto

No aflojar riendas: **separar las constantes que suponen algo del modelo de las que no**,
para que un cambio de modelo tenga una lista y no una sorpresa. Es lo que `D-5` viene
pidiendo bajo el nombre de «Constant Soup», y hasta hoy era una queja sin inventario.

### Atadas al modelo — hay que re-derivarlas

| constante | qué supone | cómo se re-deriva |
|---|---|---|
| `max_iterations` (20 · 10 · 8 · 4) | cuántas vueltas necesita **este** modelo | medir la distribución de vueltas hasta responder, y cortar en el percentil que no pierda utilidad |
| `max_tokens` por llamada (800 · 600) | cuánto escribe de salida | percentil de `completion_tokens` observado |
| `stop_on_barren = 3` | cuándo **este** modelo deja de encontrar cosas nuevas | de `barren_peak` en réplicas de igual utilidad |
| `ELICITED_PRIOR_CREDENCE = 0.8` | qué tan confiable es su opinión | **es un prior y la calibración existe para desmentirlo** — con otro modelo se vuelve a ganar desde cero |
| `COUPLING_CREDENCE_FLOOR = 0.7` | qué credencia alcanza para actuar | ídem: sale de la calibración, no de un número elegido |
| `COST_PRIORS` por brazo | multiplicadores de costo relativos | del registro: son el ratio observado, no una opinión |

### **No** atadas al modelo — se quedan como están

| constante | por qué no depende del modelo |
|---|---|
| `BUDGET_SHARE`, `MAX_MAP_CALLS`, la aritmética de factibilidad | corren contra el **presupuesto declarado por la tarea**, no contra una ventana de contexto. Un modelo con ventana más grande no las mueve |
| `CHARS_PER_TOKEN = 4` | aproximación de tokenizador, estable dentro de una familia |
| pisos de procedencia, el retículo, `Scope` | son sobre **qué evidencia admite una acción**, no sobre quién la produjo |
| los contratos | verifican una salida contra un dominio declarado; el que la escribió es irrelevante |
| la guarda de promoción, la firma, el replay sellado | aritmética y criptografía |

> **La prueba para decidir de qué lado cae una constante:** ¿su valor correcto cambiaría si
> el mismo corpus lo corriera un modelo distinto? Si sí, es del modelo y hay que
> re-derivarla. Si no, es del problema y se queda.

---

## El riesgo que conviene enunciar antes de cambiar de modelo

**Un modelo mucho más capaz podría volver innecesario el ruteo, y eso no sería un fracaso
del producto: sería el resultado.**

Si un solo brazo resuelve todo a un costo aceptable, la brecha de oráculo se va a cero y no
hay nada que capturar. Ya pasó parcialmente: con λ ≥ 0,05 la brecha **ya es 0,0000** en los
tres corpus medidos, y `rewoo` domina.

Ése es exactamente el resultado que este banco existe para poder ver — y verlo exige medirlo
con la misma disciplina, no aflojar las riendas hasta que el número salga favorable.
