# Análisis de fallo por estrategia
## Dónde falla cada patrón, por qué, y qué herramienta lo arreglaría

**Datos**: 28 de 28 celdas · corpus `gold_v2` (endurecido) · retriever `hybrid` (BM25+denso, RRF)
· `gpt-5-chat` · **1 réplica por celda**
**Fecha**: 2026-08-23

> ⚠️ **n=1 por celda.** Con la varianza entre réplicas medida antes en hasta 3,93× para
> `dag_strategy`, los números de costo son indicativos y no estimaciones. Los fallos de
> **calidad** son más robustos: un 0,000 con la evidencia leída es un fallo estructural,
> no ruido de muestreo. Los mecanismos que siguen se sostienen en la traza de uso de
> herramientas, no en la magnitud.

---

# 0. La tabla

| celda | qué exige | ganador | costo ganador | peor | costo peor |
|---|---|---|---|---|---|
| **C2** bulk independiente | cobertura exhaustiva de 60 unidades | `react` 0,750 | **3.701** | `plan_execute` 0,000 | 41.955 |
| **C3** cadena 3 hops | resolver referencias en orden | `direct` 1,000 | 10.503 | `dag_strategy` 0,000 | **251.374** |
| **C4** conteo agregado | cobertura total + aritmética | `react` 1,000 | **2.877** | `plan_execute` 0,000 | 28.278 |
| **C5** contradicción 2 hops | comparar dos unidades entre sí | `direct` 1,000 | 10.474 | `dag_strategy` 0,000 | **142.694** |

Dos patrones ganan y ninguno de los dos es elaborado. Y el patrón más elaborado produce
el peor resultado de la tabla en las dos dimensiones a la vez.

---

# 1. `plan_execute` — falla en 3 de 4, **con la evidencia en la mano**

| celda | u | rel leídas | alucinaciones | llamadas |
|---|---|---|---|---|
| C2 | **0,000** | 6 de 6 | **13** | 31 |
| C3 | 0,000 | 1 de 4 | 0 | 19 |
| C4 | **0,000** | 4 de 6 | **34** | 34 |
| C5 | 1,000 | 1 de 2 | 31 | 40 |

**El mecanismo.** Descompone en sub-preguntas *independientes*, cada sub-agente corre con
4 iteraciones y una vista parcial, y después la síntesis tiene que reconstruir una
respuesta global desde vistas parciales. Para *"listá todos los X"* y *"contá los X"* eso
está estructuralmente roto: un sub-agente que vio 1/5 de las unidades reporta 1/5 de la
respuesta, y **la síntesis no tiene forma de saber que está incompleta**.

En C2 leyó las 6 unidades relevantes de 6 y sacó cero. La atribución es inequívoca:
**fallo de razonamiento, no de retrieval**. Tenía todo.

**Y las alucinaciones son sintomáticas, no accidentales.** 13, 34 y 31 ids inventados —
por lejos la tasa más alta. Los sub-agentes reciben una sub-pregunta *sin la lista de
unidades del contexto padre*, así que inventan ids plausibles. Es un defecto de diseño de
la descomposición: **descompone la pregunta pero no el contexto**.

**Qué lo arreglaría.** Contabilidad de cobertura: *"viste las unidades X; la tarea tiene
Y; quedan Y−X sin visitar"*. Es la adición de mayor apalancamiento del análisis, porque
convierte una incompletitud silenciosa en una señal. Y pasar la lista de unidades a cada
sub-agente elimina la fuente de alucinación de raíz.

---

# 2. `map_reduce` — el único fallo que **ninguna herramienta arregla**

| celda | u | herramientas usadas |
|---|---|---|
| C2 | 0,750 | ninguna |
| C3 | **0,000** | ninguna |
| C4 | 1,000 | ninguna |
| C5 | **0,000** | ninguna |

Falla exactamente en las dos celdas acopladas, y `rel=0` en todas porque **por
construcción no usa herramientas**: lee cada unidad aislada.

**El mecanismo es la definición del patrón.** C3 exige una cadena — la unidad *i* te dice
qué buscar en la unidad *j*. Una vista por-unidad aislada **no puede** resolverla, no
importa cuántas veces la mires. C5 exige comparar dos unidades entre sí; el patrón nunca
tiene dos en la misma vista.

**Esto es lo más valioso del análisis para la tesis.** Es el único fallo que no se puede
atribuir al surface, al retriever, ni al modelo. Es la limitación definitoria del patrón,
y la única solución es **no usarlo ahí** — que es precisamente lo que un selector debería
hacer. Si hay un caso donde la selección de topología paga, es este.

---

# 3. `dag_strategy` — dos fallos distintos, ambos ruinosos

| celda | u | tokens | rel leídas | llamadas |
|---|---|---|---|---|
| C3 | **0,000** | **251.374** | **4 de 4** | 58 (43 `keyword_search`) |
| C5 | **0,000** | 142.694 | 0 de 2 | 41 (31 `keyword_search`) |

Los dos ceros tienen mecanismos **opuestos**, y confundirlos habría sido un error de
lectura.

## 3a. C3 — encontró todo y no pudo armarlo

`rel=4 de 4`. Leyó **la cadena completa** y sacó cero, gastando un cuarto de millón de
tokens. No es fallo de retrieval: es fallo de **ensamblado**.

El planificador partió la cadena en sub-preguntas y las corrió en olas. Pero una cadena es
*secuencial por definición* — el hop 2 no se puede formular hasta conocer la respuesta del
hop 1. Al descomponerla en preguntas paralelas, cada sub-agente buscó su pedazo a ciegas,
la pizarra acumuló los cuatro memos correctos, y la síntesis tuvo la evidencia completa
sin la estructura que la ordena.

> **Y esto une a `plan_execute` y `dag_strategy` bajo un mismo fallo raíz: la
> descomposición destruye la dependencia secuencial.** Los dos patrones que descomponen
> fallan en las celdas acopladas, y los dos con la evidencia leída. No es una
> coincidencia de dos patrones: es una propiedad de descomponer.

## 3b. C5 — el bucle amplifica el fallo de retrieval

**142.694 tokens, u=0,000, 31 `keyword_search`, `rel=0`.**

Buscó treinta y una veces y **nunca leyó una unidad relevante**. Después de la búsqueda
número tres el retriever ya había demostrado que no iba a encontrarlo; el bucle
verify-replan lo interpretó como *"seguí buscando"*.

**El mecanismo.** El verificador ve completitud baja → replanifica → los sub-agentes
buscan de nuevo con queries apenas distintas → el verificador ve completitud baja otra
vez. **El bucle no tiene memoria de que el retriever ya falló**, así que trata un fallo
sistemático como si fuera mala suerte.

> ### El hallazgo que generaliza
>
> Una topología iterativa sobre un retriever que falla **no degrada con gracia: multiplica
> el fallo**. Treinta y una búsquedas con recall 0,50 no son mejores que tres — son
> catorce veces más caras y exactamente igual de inútiles.
>
> Y esto invierte la intuición de diseño. Se agregan bucles de verificación *para*
> robustez. Acá el bucle es el mecanismo de amplificación: sin él, el fallo habría costado
> 10k tokens en vez de 143k.

**Qué arreglaría cada uno.** Para C5, un detector de fallo de retrieval: *"tus últimas 3
búsquedas no devolvieron contenido nuevo"*, y el bucle **escala a leer todo** en vez de
buscar otra vez — convierte un blowup de 14× en una lectura de 10k. Para C3 el arreglo es
distinto y más profundo: el planificador tiene que **detectar que la tarea es secuencial y
no descomponerla**. Descomponer una cadena es la operación equivocada, y ninguna cantidad
de olas, pizarra o replanificación lo compensa.

---

# 4. `react` — gana barato, o gana carísimo, y la diferencia es el retrieval

| celda | u | tokens | unidades leídas | vs `direct` |
|---|---|---|---|---|
| C4 | 1,000 | **2.877** | 0 | **4,3× más barato** |
| C2 | 0,750 | **3.701** | 0 | **3,4× más barato** |
| C3 | 0,000 | 30.611 | 3 | 2,9× más caro, y falla |
| C5 | 1,000 | **79.335** | **49 de 49** | **7,6× más caro** |

**27× de rango de costo en el mismo paradigma.** Y las dos caras tienen mecanismos
distintos:

**Cuando gana** (C2, C4): responde desde resúmenes y highlights, `rel=0`, **sin leer una
sola unidad completa**. Dos llamadas. Es la escalera de granularidad pagando exactamente
como se diseñó: 312 chars de resumen en vez de 16k de texto.

**Cuando gana caro** (C5): la búsqueda no superficializó la contradicción — 2 unidades
relevantes entre 49, y hay que compararlas — así que **degeneró en leer todo, de la manera
caraʼ**: 49 unidades en lecturas incrementales, con el historial completo reenviado cada
turno. `direct` lee las mismas 49 en **una** llamada por 10.474 tokens. `react` pagó
79.335 por el mismo contenido.

**Qué lo arreglaría.** Si va a leer todo, leer todo de una vez. Falta una herramienta
`read_all`, o mejor: una **señal de presupuesto** — *"leíste el 40% de las unidades;
leer el resto de una cuesta menos que seguir buscando"*. El desperdicio no está en leer,
está en leer de a poco.

---

# 5. `direct` y `cot` — ganan las acopladas, y por una razón incómoda

Ganan C3 y C5 — las dos que exigen razonamiento cruzado — y son las más baratas ahí.

**El mecanismo.** Una cadena de 3 hops sobre 48 unidades **entra en un prompt**. Y con
todo a la vista **no hay hops**: la referencia y su destino están en el mismo contexto, así
que "seguir la cadena" es lectura local, no búsqueda iterada.

> **El multi-hop sólo es difícil si no podés ver todo.** El corpus a 16k no crea esa
> condición, así que la dificultad estructural que creía haber construido en C3 y C5 es
> difícil **para los que buscan** y trivial para los que leen.
>
> Eso es una amenaza a la validez de esta corrida, no un resultado sobre el mundo. En un
> corpus donde no entra todo, C3 y C5 serían duras para todos — y ahí recién se vería si
> alguna topología las resuelve.

`cot` no aporta nada sobre `direct` en ninguna celda: mismo resultado, +0,1% de tokens. El
andamiaje de razonamiento explícito no compra nada cuando la tarea es extracción sobre
material visible.

---

# 6. La dependencia de la calidad de herramientas, cuantificada

Partiendo los siete en los que usan herramientas y los que no:

| grupo | paradigmas | rango de costo |
|---|---|---|
| **No usan herramientas** | `direct`, `cot`, `map_reduce` | 10.474 – 16.207 = **1,5×** |
| **Usan herramientas** | `react`, `plan_execute`, `reflection`, `dag_strategy` | 2.877 – 142.694 = **50×** |

**La calidad de las herramientas no corre la media: gobierna la varianza.** Y la varianza
es donde está la plata — un paradigma que cuesta entre 2.877 y 142.694 tokens según si la
búsqueda funcionó no es presupuestable.

Eso confirma con número la intuición de que *todo depende de la calidad de las tools*, y
la refina: **depende asimétricamente**. Los que leen son robustos y caros-estables; los
que buscan son baratos-o-ruinosos, y qué cara sale la moneda lo decide el retrieval.

**Implicación para el paper.** Cualquier afirmación sobre un patrón que busca es
condicional a la calidad del surface, y esa condición hay que declararla. Un benchmark que
no reporta la calidad de sus herramientas no está midiendo topologías: está midiendo su
retriever con siete envoltorios distintos.

---

# 7. Las cinco herramientas que faltan, ordenadas por apalancamiento

| # | Herramienta | Arregla | Costo de implementar |
|---|---|---|---|
| **1** | **Contabilidad de cobertura** — `units_seen / units_total`, y qué falta | la incompletitud silenciosa de `plan_execute`; el bucle ciego de `dag` | trivial, no necesita modelo |
| **2** | **Señal de fallo de retrieval** — *"las últimas N búsquedas no trajeron nada nuevo"* | la amplificación de 14× de `dag`; da a los bucles una condición de salida | trivial |
| **3** | **`read_all`** — todas las unidades en una llamada | el blowup de 7,6× de `react` en C5 | trivial |
| **4** | **`neighbors(unit_id)`** — seguir una referencia sin búsqueda de texto | las cadenas, que es lo que rompe a todos los que buscan en C3 | necesita índice de referencias |
| **5** | **`count(predicate)`** — agregación exacta | C4 es conteo y los LLM cuentan mal; es el `analyze_table` que un surface maduro tiene | medio |

Las tres primeras son **triviales y no requieren modelo**, y entre las tres atacan los
tres peores fallos de la tabla. Eso es la conclusión práctica más fuerte del análisis:
**los blowups de costo más grandes no se arreglan con mejores topologías ni con mejores
modelos, sino con tres señales de contabilidad que hoy no existen.**

---

# 8. El agregado sobre las cuatro celdas

| paradigma | u media | tokens totales | rango de costo | alucinaciones |
|---|---|---|---|---|
| **`direct`** | **0,938** | **46.101** | 1,2× | 0 |
| `cot` | 0,938 | 46.272 | 1,2× | 0 |
| `react` | 0,688 | 116.524 | **27,6×** | 0 |
| `reflection` | 0,688 | 126.254 | 6,9× | 0 |
| `map_reduce` | 0,438 | 62.321 | 1,2× | 0 |
| `dag_strategy` | 0,438 | **439.319** | 24,5× | 0 |
| `plan_execute` | 0,250 | 123.175 | 2,0× | **78** |

**El patrón más simple gana en calidad y es el más barato a la vez.** `direct` saca 0,938
con 46k tokens; `dag_strategy` saca 0,438 con 439k — **9,5× el costo por menos de la mitad
de la calidad**.

Y el orden es casi monótonamente inverso a la elaboración: cuanto más estructura de
control, peor calidad. La única inversión es `map_reduce`, que es barato y malo porque no
usa herramientas en absoluto.

> Con la advertencia que gobierna todo el documento: **este es un corpus donde todo entra
> en un prompt**. En ese régimen leer todo es óptimo y la conclusión es casi tautológica.
> El resultado interesante no es "lo simple gana" — es *por qué* pierde cada elaborado,
> y eso sí generaliza porque los mecanismos son estructurales.

---

---

# 9. El A/B de herramientas: ¿las tres señales arreglan lo que el análisis dijo?

Las §1-7 identificaron tres fallos y propusieron tres herramientas *sin modelo* para
cada uno. Esto es la prueba. Mismo corpus, mismo retriever, mismas 4 celdas; la única
diferencia es el surface, registrado como variable en cada fila.

## 9.1 El grupo de control valida la comparación

| paradigma | u basic | u acct | tokens basic | tokens acct |
|---|---|---|---|---|
| `direct` | 0,938 | 0,938 | 46.101 | 46.101 |
| `cot` | 0,938 | 0,938 | 46.272 | 46.272 |
| `map_reduce` | 0,438 | 0,438 | 62.321 | 62.321 |

**Idénticos hasta el token.** Los tres que no usan herramientas no se movieron, que es lo
que se predijo antes de mirar. Eso es lo que hace atribuibles las diferencias de abajo:
sin este control, cualquier cambio podría ser ruido de la corrida.

## 9.2 Los resultados, después del test de atribución

§9.4 explica de dónde sale la columna *atribuible*: una réplica accidental mostró que
`c3-002-h3` se da vuelta sola, así que un efecto que sólo mueve esa celda no es un efecto.

| paradigma | Δu reportado | celdas movidas | **atribuible** | costo | mecanismo en la traza |
|---|---|---|---|---|---|
| **`dag_strategy`** | +0,500 | c3 (inestable), c5 (estable) | **+0,250** | **0,33×** | 2 avisos de estancamiento |
| `reflection` | +0,250 | sólo c3 (inestable) | **0,000** | 0,77× | 2 `coverage`, 2 `read_all` |
| `react` | +0,000 | ninguna | 0,000 | 1,27× | 2 `read_all` |
| **`plan_execute`** | −0,139 | c2, c5 (ambas estables) | **−0,139** | 0,81× | 2 `coverage`, **5 avisos** |

### `dag_strategy`: el costo sobrevive, la calidad se parte al medio

De 439.319 a 144.125 tokens: **3,05× más barato**, contra una dispersión de réplica de
1,62× sobre la misma medida. Y la caída está localizada donde el mecanismo la predice —
las dos celdas desbocadas, 251k → 51k y 143k → 10k, ambas con avisos de estancamiento. Las
otras dos no cayeron. **El resultado de costo se sostiene.**

La calidad no del todo. De las dos celdas que se movieron, una es `c3-002-h3` — la que se
da vuelta sola. Descontada, el efecto atribuible es **+0,250, la mitad** de lo que reporté
primero.

Lo que sí queda intacto es la hipótesis: el bucle recibió *"tus últimas 3 búsquedas no
trajeron nada nuevo"* y en vez de buscar por cuadragésima tercera vez, cambió de
estrategia. **Una topología iterativa sobre un retriever que falla no necesita mejor
topología ni mejor modelo — necesita saber que el retriever falló.** La señal que le
faltaba era una línea de texto y valía una reducción de costo de 3×.

### `reflection`: retirado

+0,250 salió íntegro de `c3-002-h3`, y esa celda cambia de valor entre dos corridas de la
misma superficie. **No es un efecto.** Se retira.

### `plan_execute`: empeoró, y la predicción falló

§1 dijo que la contabilidad de cobertura era *"la adición de mayor apalancamiento"* para
este patrón. **Fue al revés: 0,250 → 0,111.** Usó `coverage` dos veces y recibió cinco
avisos de estancamiento, el máximo de la tabla.

La lectura honesta: **saber que la respuesta está incompleta no sirve si la arquitectura
no permite completarla.** Los sub-agentes ya terminaron cuando la síntesis se entera de
que faltaban unidades, y no hay camino de vuelta. Gastó tokens en enterarse de algo que
no podía accionar.

> **Un diagnóstico sin capacidad de acción es peor que no tenerlo.** Y refuerza el
> hallazgo estructural: el problema de descomponer no es informacional, así que ninguna
> señal lo compensa. §1 se equivocó al llamarlo el de mayor apalancamiento.

### `react`: sin cambio de calidad, 27% más caro

`read_all` le facilitó leer más de lo que necesitaba. La herramienta pensada para
abaratar una lectura completa terminó abaratando *la decisión de leer todo*, que no es lo
mismo. Efecto de segundo orden que no había previsto.

## 9.3 Qué se aprende del A/B, más allá de los números

**De cuatro predicciones: una acertó, una falló con efecto inverso, una era ruido y una
fue nula.** Eso es información sobre el método y no sólo sobre las herramientas. El
análisis de mecanismos predice bien cuándo el fallo es de *información faltante* (`dag`) y
mal cuando el fallo es *estructural* (`plan_execute`). Una señal arregla lo primero y no
toca lo segundo.

El ordenamiento por apalancamiento de §7 hay que corregirlo, pero en el eje correcto: la
**señal de estancamiento** es la número uno **en costo** — 3× — no en calidad. La ganancia
de calidad que le había atribuido era mitad ruido.

## 9.4 La réplica que no planeé

El tercer brazo agregó cuatro herramientas de memoria de trabajo (`note`, `notes`, `plan`,
`advance`). **El modelo no las llamó nunca**: en 28 filas, un note, una compactación, cero
planes.

Resultado nulo sobre las herramientas, y la explicación es la misma amenaza de validez que
persigue a todo el estudio: en `gold_v2` **no hay presión de contexto**, así que una
herramienta de memoria de trabajo no tiene trabajo. La maquinaria de compactación que medí
en 29× de reducción nunca se disparó porque ningún paradigma acumuló lo suficiente.
**Exponer una capacidad no es proveerla.**

Pero al no usarse, ese brazo quedó siendo una **réplica** de la superficie `accounting`. Y
como réplica dice lo que el agregado escondía:

| celda | paradigmas que cambiaron de calidad |
|---|---|
| `c2-000-w48` | 0 de 2 |
| **`c3-002-h3`** | **2 de 4** |
| `c4-000-w48` | 0 de 4 |
| `c5-000-w48` | 0 de 4 |

**La reproducibilidad es por tarea, no global.** Diez de diez valores idénticos en tres
celdas; en la cuarta, dos se dan vuelta por una unidad completa. La inestabilidad no está
repartida — está concentrada en la tarea más difícil, donde el resultado es bimodal.

El costo no fue reproducible en ninguna parte: dispersión media 2,05×, máxima **5,43× a
calidad idéntica** (`dag` en c5: 10.359 → 47.550 tokens, ambos con u=1,000).

De ahí sale el test de atribución de §9.2, y de ahí sale la regla: **todo efecto de calidad
igual o menor a ±0,250 en una media de cuatro tareas es indistinguible del ruido con
n=1.** Vale una vuelta de moneda en una sola celda.

**Dos filas no corrieron** — cero tokens, respuesta vacía. Excluidas de toda cifra en lugar
de puntuadas como cero: un paradigma que nunca ejecutó no se mezcla con uno que respondió
mal. Es el mismo error de normalizador que ya me había mordido una vez.

---

# 10. Qué se sostiene y qué no

**Se sostiene** (mecanismo estructural, no magnitud):
- `map_reduce` no puede resolver acoplamiento. Definitorio del patrón, no arreglable con herramientas.
- **Descomponer destruye la dependencia secuencial.** `plan_execute` y `dag_strategy`
  fallan las dos celdas acopladas, y ambos con la evidencia leída. Dos patrones, un
  mecanismo.
- El bucle de `dag` amplifica el fallo de retrieval en vez de absorberlo.
- La escalera de granularidad funciona: `react` responde de resúmenes a 1/4 del costo.

**No se sostiene todavía**:
- Cualquier magnitud de costo. n=1, y la varianza medida entre réplicas llega a 3,93×.
- Que C3/C5 sean "duras": son duras para los que buscan y triviales para los que leen,
  porque todo entra en un prompt. Amenaza a la validez de la corrida.
- Que `react` sea el mejor patrón. Ganó dos celdas por costo y perdió una por 27×.

**Lo próximo que decide algo**: `repeat=3` para tener piso de ruido, y las tres
herramientas de contabilidad — que probablemente cambien el orden de la tabla más que
cualquier cambio de topología.
