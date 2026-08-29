# La cota nativa del ratchet

> **T-4.** Reemplaza el préstamo del Teorema 10.1 de v1, que acotaba **varianza bajo
> oscilación**. El piso que aprende no puede oscilar: es monótono y con techo. Importar
> ese teorema no era una cita floja, era un **error de categoría** — acotaba algo que el
> mecanismo no puede hacer, así que la cota se cumplía trivialmente y no decía nada.
>
> Verificado numéricamente en `tests/test_science.py` §22.

---

## Qué es exactamente el mecanismo

Una región **endurece** su piso de garantía cuando, sobre el split de propuesta:

- tiene al menos `MIN_REQUESTS_PER_REGION = 8` requests con alguna afirmación elicitada, y
- al menos `MIN_REJECTION_RATE = 0.5` de ellos tuvo **al menos un rechazo por procedencia**.

Y sólo sobrevive si el split de **validación**, que son tareas distintas, produce
independientemente el mismo nivel. El techo es `ACCOUNTABLE`; `CERTIFIED` está fuera de
alcance a propósito, porque ese nivel **restringe qué patrones son admisibles** y una
estadística sobre calidad de evidencia no es evidencia sobre certificabilidad.

El piso **nunca baja**.

---

## Parte 1 — Terminación, que es la garantía que un ratchet sí da

Los niveles son `EXPLORATORY < STANDARD < ACCOUNTABLE < CERTIFIED` y el techo aprendido es
el tercero. Entonces, **por región**:

| piso base | subidas posibles |
|---|---:|
| `EXPLORATORY` | 2 |
| `STANDARD` | 1 |
| `ACCOUNTABLE` | 0 |
| `CERTIFIED` | 0 |

**Proposición 1 (daño total acotado).** Sobre `R` regiones, el número total de eventos de
endurecimiento en toda la vida del sistema es **≤ 2R**, sea cual sea la cantidad de ciclos
de consolidación que se corran.

La demostración es la monotonía: la secuencia de pisos de una región es no decreciente en
un conjunto finito y totalmente ordenado, así que cambia a lo sumo tantas veces como
niveles haya por encima de su base. No hace falta nada probabilístico.

> **Y acá está el error de categoría del teorema prestado.** Una secuencia monótona y
> acotada tiene varianza que tiende a cero por construcción: acotarla no informa. Lo que
> un ratchet necesita que se le acote no es cuánto **oscila** sino cuánto **daño
> acumulado** puede hacer antes de detenerse — y eso es un conteo, no una varianza.

---

## Parte 2 — Endurecimiento espurio, y dónde la guarda es débil

Sea `q` la tasa **verdadera** de rechazo por procedencia de una región. Si `q < 0.5`, el
endurecimiento no está justificado y toda subida es un falso positivo.

Un split de `n = 8` observaciones califica con probabilidad `P(Bin(n, q) ≥ ⌈n/2⌉)`. Los dos
splits son **conjuntos de tareas disjuntos**, así que condicionados en `q` son
independientes y la probabilidad de que sobreviva es el producto.

| `q` real | un split | **ambos** | aproximadamente |
|---:|---:|---:|---:|
| 0,10 | 0,0050 | **0,000025** | 1 en 39.613 |
| 0,20 | 0,0563 | **0,00317** | 1 en 316 |
| 0,25 | 0,1138 | **0,01295** | 1 en 77 |
| 0,30 | 0,1941 | **0,03768** | 1 en 27 |
| 0,40 | 0,4059 | **0,16477** | **1 en 6** |
| 0,45 | 0,5230 | **0,27358** | **1 en 4** |

**Proposición 2 (la guarda es fuerte lejos del umbral y débil cerca).** La replicación
compra cuatro órdenes de magnitud cuando la región está claramente sana (`q = 0.10`) y casi
nada cuando está al borde (`q = 0.45`, 1 en 4).

Eso hay que decirlo, no esconderlo. Pero **importa menos de lo que parece, por dos
razones**, y las dos son estructurales y no consuelos:

1. **Cerca del umbral el falso positivo es casi indistinguible de un verdadero.** Endurecer
   una región cuyo `q` real es 0,45 cuando el criterio pedía 0,50 no es un error del mismo
   tipo que endurecer una con `q = 0,10`: la región efectivamente rechaza casi la mitad de
   las veces.
2. **La Proposición 1 acota el daño acumulado.** Aun con 1 en 4 cerca del umbral, el sistema
   no puede degradarse sin límite: el total de endurecimientos es ≤ 2R **para siempre**.

> La monotonía —que es lo que vuelve inaplicable el teorema de varianza— es exactamente lo
> que acota el daño de su propia tasa de falsos positivos. La propiedad que rompe la cota
> prestada es la que hace innecesaria la cota prestada.

---

## Parte 3 — Qué cuesta un endurecimiento

Un endurecimiento **no puede producir una respuesta peor**: sube el piso de procedencia, así
que lo que antes se creía ahora se sondea o se difiere. El costo es **cobertura y tokens**,
nunca corrección. Un ratchet yerra hacia la cautela por construcción.

La pérdida de cobertura de una subida en una región es la fracción de requests de esa región
cuya evidencia queda por debajo del piso nuevo.

**Medida el 2026-08-28** (`bench/analysis/_analyze_ratchet_cost.py`, `T-4b`), y el resultado
corrige cómo se lee la cota:

| nivel | brazos admisibles | cobertura | u(mejor fijo) |
|---|---:|---:|---:|
| A0 · A1 · A2 | 5 | 100% | 0,6101 |
| **A3** | **2** | **40%** | **0,4221** |

**El ratchet es gratis hasta A2 y cuesta todo de una vez en A3.** A0/A1/A2 declaran
`admissible_patterns=None`, así que subir ahí no compra garantía de catálogo ni cuesta
cobertura; el único escalón con precio se lleva **60% del catálogo y 31% de la utilidad**.

Eso cambia la lectura de la Proposición 1. «A lo sumo dos subidas» invita a imaginar un daño
que se acumula despacio, y lo medido es lo contrario: **una sola transición tiene precio, y
ahí es abrupto.** Las otras dos son gratis porque no hacen nada.

Y el promedio esconde a quien paga: la región `many/no_oracle/loose/chain` pierde **−0,5000**
con n=4, mientras que en el corpus de sonda la media es **0,0000** con una sola región
perdiendo 0,0877.

---

## Qué queda abierto, dicho como corresponde

- **La Parte 3 ya está medida** (`T-4b`, 2026-08-28), así que el «daño total acotado» está
  acotado en eventos **y** en efecto. Lo que queda abierto es más fino: la medición es sobre
  **un** registro y **un** corpus, y el precio del escalón A2→A3 depende del catálogo — si
  entran paradigmas certificables, ese 60% baja sin que la cota cambie.
- La independencia de los dos splits vale **condicionada en `q`**. Si `q` variara dentro de
  la región —o sea, si la región mezclara sub-poblaciones—, los splits estarían correlacionados
  y el producto sería optimista. Detectar eso es exactamente lo que hace el buscador de
  particiones, así que la cota y el descubrimiento de splits se necesitan mutuamente.
- Nada de esto dice que endurecer sea **correcto**, sólo que es **acotado y auditable**.
