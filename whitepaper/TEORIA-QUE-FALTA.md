# `F5` ya no es pizarra: tres teoremas construidos que el paper no tiene

> **Propuesta de §5.3, §5.4 y §5.5.** No hay que demostrar nada nuevo: los tres están
> escritos, verificados con test y —dos de ellos— medidos. Lo que falta es que entren.
>
> **APLICADO el 2026-08-29.** Entraron a `paper-en.md` y a `paper-es.md` como **§5.3, §5.4 y
> §5.5**, en la misma posición. Este archivo queda como el razonamiento que las produjo —el
> inventario contra el ejecutable, y por qué el préstamo de v1 era un error de categoría—,
> no como una propuesta abierta. `F5` cerrada en `lab/PAPER.es.md`.

---

## El estado, medido

`PAPER.es.md` lista `F5 · teoría nativa` como pendiente y `PENDIENTES.es.md` lo describe
como *«pizarra — T-1 a T-5»*. **Eso ya no es cierto.** Contado contra el ejecutable:

| | qué es | dónde vive | test | estado |
|---|---|---|---|---|
| **T-3** | soundness del ensamblador | `SOUNDNESS.es.md` | `test_science.py` §46 | **cerrado** |
| **T-4** | cota nativa del ratchet | `COTA_RATCHET.es.md` | §22 | **cerrado** |
| **T-4b** | y su precio, **medido** | `_analyze_ratchet_cost.py` | — | **cerrado** |
| **T-5** | quién fija el dial | `EL_DIAL.es.md` | §47 | **cerrado** |
| **T-6** | vecinos leídos completos | — | — | **cerrado, y ya está en §5** |
| **T-1** | semántica del contrato | `CONTRATOS.es.md` | §45 | **dos de sus tres clases** |

Y el paper, contado a mano:

```
menciones de «soundness»      en paper-en.md :  0
menciones de «ratchet»                       :  0
menciones de «assurance dial»                :  0
```

**§5 «Theory» tiene dos secciones y el lab tiene tres teoremas más.** No es que falte
teoría: falta transportarla.

> **Y hay un motivo para hacerlo ahora y no al final.** Los tres son **resultados
> estructurales** —no dependen del corpus ni del modelo— así que son lo único de este paper
> que no queda pendiente de una corrida. La sección empírica está condicionada; ésta no.

---

## §5.3 propuesta — Soundness del ensamblador

**Qué se afirma, y el enunciado es corto a propósito.** Un teorema sobre una función de
treinta líneas, no sobre el sistema. Un enunciado que abarcara «la respuesta» sería falso, y
decir exactamente hasta dónde llega es la mitad del valor.

> **Teorema 2 (soundness del ensamblador).** Sea `T` una plantilla con ranuras
> `S = {s₁ … sₙ}`, `B` una asignación ranura→proposición, `Γ` una base de creencias y `φ`
> un piso de procedencia. Si `fill(T, B, Γ, φ)` emite una cadena `R`, entonces para toda
> ranura `sᵢ` existe `βᵢ ∈ Γ` tal que:
>
> 1. `βᵢ` es la creencia **vigente** sobre la proposición que `B` asigna a `sᵢ`;
> 2. `rank(procedencia(βᵢ)) ≥ rank(φ)`;
> 3. la subcadena de `R` en la posición de `sᵢ` es **exactamente** `str(valor(βᵢ))`.
>
> Y `R` no contiene ninguna otra subcadena que no venga de `T` o de esos valores.

En una línea: **si el ensamblador emite, todo número que emitió está implicado por la base
de creencias al piso pedido.** No «probablemente». No «salvo alucinación».

**La demostración es por construcción** y depende de **una línea**: la sustitución ocurre
*después* de comprobar que la lista de rechazos está vacía. Las tres condiciones se
corresponden una a una con las tres guardas, y no hay un cuarto camino por el que un valor
llegue a la salida.

**Falla cerrada y entera, y eso es una decisión.** Si una sola ranura no llega al piso, no
se emite una versión parcial. Emitir *«El saldo de la cuenta es ___»* no es más honesto que
emitir un número inventado: **es el mismo acto con mejor caligrafía**, y deja que el lector
complete lo que el contrato rechazó.

**Los cuatro límites van adentro del teorema, no en una nota al pie:**

| límite | qué significa |
|---|---|
| **el alcance es la ranura, no la oración** | *«el saldo NO supera {x}»* con `x` correcto es **sound y falso**. No es un defecto de la implementación: es la frontera de la familia entera, y `_redteam_binding.py` la mide en vez de suponerla |
| **la procedencia es del registro, no del mundo** | `COMPUTED` significa que alguien la computó y la asentó. El teorema **traslada** confianza desde el piso hacia la salida; no la crea |
| **vigente, no histórica** | la garantía es sobre el estado de creencias **al ensamblar**, no sobre todo lo que alguna vez se creyó |
| **`str()` es parte del teorema** | la condición 3 dice `str(valor)`, no «el valor». El ensamblador **no formatea**, porque formatear sería empezar a decidir algo sobre el número |

**Verificación exhaustiva, no por casos elegidos:** el producto cartesiano de las cuatro
procedencias por las condiciones de rechazo — un espacio chico, y por eso se recorre entero.

> **Por qué esto vale una sección.** Todo el aparato —procedencia tipada, pisos por acción,
> base con historia— existe para poder terminar en un enunciado de esta forma. Sin él la
> procedencia es contabilidad: se registra, se muestra, y nadie puede decir qué compra.
> **El teorema es lo que compra.** Que sea corto es la propiedad, no la limitación.

---

## §5.4 propuesta — La cota del ratchet, y su precio medido

**Qué reemplaza, y por qué el préstamo estaba mal.** Una versión anterior importaba un
teorema de varianza bajo oscilación. El piso que aprende **no puede oscilar**: es monótono y
con techo. Importarlo no era una cita floja, era un **error de categoría** — acotaba algo que
el mecanismo no puede hacer, así que la cota se cumplía trivialmente y no decía nada.

### Parte 1 — terminación

Los niveles son `EXPLORATORY < STANDARD < ACCOUNTABLE < CERTIFIED`, y el techo aprendido es
el tercero: `CERTIFIED` queda fuera de alcance a propósito, porque **restringe qué patrones
son admisibles** y una estadística sobre calidad de evidencia no es evidencia sobre
certificabilidad.

> **Proposición 1 (daño total acotado).** Sobre `R` regiones, el número total de eventos de
> endurecimiento en **toda la vida del sistema** es **≤ 2R**, sea cual sea la cantidad de
> ciclos de consolidación.

La demostración es la monotonía: una secuencia no decreciente en un conjunto finito y
totalmente ordenado cambia a lo sumo tantas veces como niveles haya por encima de su base.
**No hace falta nada probabilístico.**

> **Y ahí está el error de categoría del préstamo.** Una secuencia monótona y acotada tiene
> varianza que tiende a cero **por construcción**: acotarla no informa. Lo que un ratchet
> necesita que se le acote no es cuánto **oscila** sino cuánto **daño acumulado** puede hacer
> antes de detenerse — y eso es un conteo, no una varianza.

### Parte 2 — endurecimiento espurio, con la debilidad dicha

Con `q` la tasa verdadera de rechazo de una región, y dos splits de tareas **disjuntas**:

| `q` real | un split | **ambos** | aprox. |
|---:|---:|---:|---:|
| 0,10 | 0,0050 | **0,000025** | 1 en 39.613 |
| 0,25 | 0,1138 | 0,01295 | 1 en 77 |
| 0,40 | 0,4059 | 0,16477 | **1 en 6** |
| 0,45 | 0,5230 | 0,27358 | **1 en 4** |

> **Proposición 2.** La replicación compra **cuatro órdenes de magnitud** cuando la región
> está claramente sana, y **casi nada** cuando está al borde.

**Eso se dice, no se esconde.** E importa menos de lo que parece, por dos razones
estructurales: cerca del umbral un falso positivo es casi indistinguible de un verdadero —una
región con `q = 0,45` **efectivamente rechaza casi la mitad de las veces**—, y la Proposición
1 acota el daño acumulado pase lo que pase.

> **La monotonía —que es lo que vuelve inaplicable el teorema de varianza— es exactamente lo
> que acota el daño de su propia tasa de falsos positivos.** La propiedad que rompe la cota
> prestada es la que la hace innecesaria.

### Parte 3 — qué cuesta, **medido**

| nivel | brazos admisibles | cobertura | `u`(mejor fijo) |
|---|---:|---:|---:|
| A0 · A1 · A2 | 5 | 100% | 0,6101 |
| **A3** | **2** | **40%** | **0,4221** |

**El ratchet es gratis hasta A2 y cuesta todo de una vez en A3**: el único escalón con precio
se lleva **60% del catálogo y 31% de la utilidad**.

Eso **corrige cómo se lee la Proposición 1**. «A lo sumo dos subidas» invita a imaginar daño
que se acumula despacio; lo medido es lo contrario — **una sola transición tiene precio, y
ahí es abrupto**. Las otras dos son gratis porque no hacen nada.

**Y el promedio esconde a quien paga:** la región `many/no_oracle/loose/chain` pierde
**−0,5000** con n=4, mientras la media del corpus de sonda es **0,0000**.

---

## §5.5 propuesta — Quién fija el dial

**La pregunta parece de gobernanza y es de diseño.** Si el dial lo elige el llamador, un
llamador apurado lo baja; si lo elige el sistema, el llamador no puede pedir más rigor del
que el sistema cree necesario. **Ninguna de las dos.**

```
nivel efectivo = max( pedido , piso_de_creencias , piso_aprendido )
```

| fuente | quién la produce | qué puede hacer |
|---|---|---|
| **pedido** | el llamador, en el request | **subir**, nunca bajar |
| **piso de creencias** | `required_floor(Γ)` sobre creencias `COMPUTED` del request | **subir**, y no se desactiva |
| **piso aprendido** | `θ.floors[región]`, dentro del bundle firmado | **subir**, y sólo si está promovido |

> **Proposición 3.** `max` es la **única** composición bajo la cual cada fuente sólo puede
> endurecer. Con `min` o con un promedio, agregar una fuente podría ablandar el resultado —
> y entonces una fuente nueva sería un **riesgo** en vez de una garantía.

**Por qué el llamador sube y no baja.** Conoce cosas que el sistema no: que el request va a
un informe regulatorio, que se publica, que hay un auditor mirando. Nada de eso está en el
material. Lo que no puede es pedir **menos**, porque el piso sale de propiedades **del
request mismo** — `irreversible` eleva a A3, `shared_writes` a A2, y las dos entran como
creencias `COMPUTED` **declaradas por el caller, nunca inferidas del texto**. Un llamador que
pudiera bajar el piso podría declarar una acción irreversible y después pedir tratarla como
exploratoria, que es exactamente la combinación que el piso existe para impedir.

**Y el piso aprendido viaja firmado, a propósito.** Si llegara por fuera de la firma,
cualquier estadística de rechazo podría endurecer una región sin que nadie la revisara.

### La cuarta fuente, que no es un nivel sino una degradación

A2 admite creencias `ELICITED`, **pero sólo una vez que la calibración se ganó**. Admitirlas
antes anula el propósito del nivel: diría que rinde cuentas mientras acepta opiniones sin
contrastar. Así que `resolve()` **no baja el nivel: endurece el piso de procedencia dentro
del nivel**. Es la misma idea del `max`, aplicada al otro eje.

### Cómo se evalúa: marginalizando, no fijando una posición

**Reportar métricas a un dial fijo es reportar una política, no un sistema.** Y marginalizar
produjo un hallazgo sobre el propio dial:

> **Tres de las cuatro posiciones son indistinguibles.** A0, A1 y A2 declaran
> `admissible_patterns = None`, así que **el dial no restringe el catálogo hasta A3**. Dos de
> sus tres transiciones no hacen nada en esa dimensión, y toda la diferencia se paga en un
> solo escalón.

Lo que sí distingue A1 de A2 vive en otros ejes —`require_signed_theta`, `log_belief_base`,
`max_composition_depth`, el piso de procedencia—, así que el dial **no es inerte ahí**: es
inerte **en la dimensión que esa tabla mide**. Decir cuál es cuál es el punto de marginalizar.

---

## Y una decisión que hay que declarar, no esconder

**`min_capability` en A2 está en `None` a propósito**, y eso es una decisión con historia:
se le había puesto `DEEP` por el argumento de «rinde cuentas», y eso era **política sin una
sola medición detrás** — obligaría a pagar 25× en cada request contable. Si el modelo barato
alcanza a ese nivel de procedencia es una pregunta **empírica**, y está registrada.

En A3 el argumento **sí** es estructural y no hace falta medirlo: `decide_level` ya eleva a
A3 toda acción irreversible, así que ese piso **es** el que impide rutear lo irreversible al
modelo más barato porque salga la cuenta. **No se agregó mecanismo nuevo: se completó el que
había.**

---

## Qué hacer con esto

| # | acción | costo |
|---|---|---|
| 1 | **cerrar `F5`**: ya no es pizarra. Cuatro de sus cinco piezas están construidas y probadas | actualizar `PAPER.es.md` |
| 2 | **§5.3, §5.4, §5.5** al paper, en los dos archivos | el material está escrito; es transporte, no investigación |
| 3 | reformular §5 «Theory» | hoy dice dos cosas; va a decir cinco, y **tres de ellas no dependen de ninguna corrida** |
| 4 | `T-1` sigue parcial | dos de tres clases. La tercera exige parsear prosa, y está declarado |

> **Lo que esto le cambia al paper.** Su sección teórica pasa de *una identidad que no se
> puede falsar más un argumento de dominancia* a **eso más tres resultados estructurales con
> demostración y test**. Y —lo que más importa dado que la campaña recién corre— **ninguno de
> los tres queda pendiente de un número**.
