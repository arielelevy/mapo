# Qué define un patrón, y qué es un factor

> **Por qué hace falta la distinción.** Un patrón entra al catálogo del motor y compite por
> ser elegido en cada request. Un factor no compite: se aplica o no se aplica, y si mejora,
> mejora **a todos**. Confundirlos tiene un costo medible en las dos direcciones — meter un
> factor como brazo infla el catálogo con opciones que no son alternativas, y plegar un
> factor adentro de un brazo **contamina el hallazgo** de ese brazo con el del factor.

---

## La prueba, en una línea

> **Un patrón se distingue por su ESTRUCTURA DE CONTROL DE FLUJO. Todo lo demás es un
> factor.**

Concretamente, dos candidatos son **el mismo patrón** si tienen la misma respuesta a las
cuatro preguntas siguientes. Si difieren en al menos una, son patrones distintos:

| pregunta | qué distingue |
|---|---|
| **¿Cuántas llamadas, y las decide quién?** | una fija, `n` fijas, o un bucle cuya salida decide el modelo |
| **¿Quién elige la próxima acción?** | el código, o el modelo |
| **¿Hay estado compartido entre pasos, y quién lo escribe?** | nada, un acumulador del código, o una pizarra que varios agentes escriben |
| **¿El resultado de un paso puede cambiar el plan?** | plan fijo, replanificación acotada, replanificación libre |

Y la contraprueba, que es la que más se usa en la práctica:

> **Si la diferencia se puede describir sin dibujar un grafo de control distinto, no es un
> patrón.**

---

## Lo que NO es un patrón, y por qué

**El fraseo del prompt.** Ninguna cantidad de instrucciones cambia el grafo de control: una
sola llamada sigue siendo una sola llamada. Ésta es la razón por la que el catálogo del
motor excluye el andamiaje por prompt — quedó **dominado**, misma utilidad y nunca más
barato, y se conserva sólo como control nulo. Las mejoras vienen de señales del entorno
—contables, deterministas—, no de persuadir al modelo.

**Una herramienta más en la superficie.** Ofrecer `note`, `plan` o `coverage` no cambia
quién decide ni cuántas veces. Es una dimensión de la **superficie**, y se mide como factor:
`{con, sin} × {patrones}`.

**Una rama de recuperación.** Reescribir la consulta antes de buscar, fusionar dos
rankings, generar una respuesta hipotética y buscar con ella: todo eso pasa **antes** de que
el patrón vea nada. Es una dimensión del **recuperador**.

**Una estrategia de datos adentro de un paso.** Una pizarra compartida es una estructura de
datos, no un flujo: puede colgarse de cualquier patrón que tenga más de un paso.

---

## Cómo queda clasificado hoy

**Patrones** — el catálogo, con su estado en el ejecutable:

| brazo | control de flujo que lo define |
|---|---|
| `direct` | una llamada. Caso degenerado: sólo existe cuando toda la evidencia entra en ventana |
| `react` | bucle sin cota fija; el **modelo** elige la próxima herramienta |
| `rewoo` | plan completo primero, ejecución sin volver a consultar al modelo |
| `map_reduce` | fan-out fijo de una llamada por unidad, reducción en código |
| `gist_reader` | triage barato, después lectura selectiva |
| `dag_strategy` | descomposición en sub-preguntas con dependencias, síntesis al final |
| `reflection` | una pasada más de crítica sobre la salida anterior |
| `graph_traverse` | recorrido guiado por un índice de entidades |
| `pointer_chase` | bucle guiado por código siguiendo referencias literales |
| `extract_compute` | extracción estructurada por unidad, cómputo exacto en código |
| `streaming_scan` | pasada única sobre el corpus con estado acotado |

**Factores** — no entran al catálogo; se cruzan contra él:

| factor | valores | estado |
|---|---|---|
| brazo de recuperación | `hybrid`, léxico, denso, degradados | medido |
| variante de superficie | `basic`, `accounting`, `cognitive` | medido |
| dial de garantía | A0–A3 | medido |
| respuesta hipotética antes de buscar | `{con, sin}` | decidido, **sin medir** |
| pizarra compartida | `{con, sin}` | **sin medir** — hoy está soldada adentro de un brazo |
| contratos de afirmación | `{con, sin}` | `C-NUM` y `C-COMPLETE` implementados; `C-COMPLETE` **cableado**, veredicto por fila |
| **regla de parada** (`stop_on_barren`) | `0` / `N` | implementado, apagado por defecto, **P20a-d registradas** |
| **ofrecer `read_all`** (`offer_read_all`) | `{con, sin}` | implementado, apagado por defecto, **P21a-d registradas** |

---

## La consecuencia que ya se pagó

Dos de esos factores están hoy **soldados adentro de un brazo**. La pizarra vive dentro de
un solo patrón, así que cualquier ventaja de ese patrón mezcla dos cosas que nadie separó:
su descomposición, y tener estado compartido.

> **Un factor plegado adentro de un brazo no se puede atribuir.** El brazo gana, y no se
> sabe cuál de las dos mitades ganó — lo que además impide dárselo a los demás.

Por eso el orden correcto es: **extraer el factor, medirlo cruzado, y recién entonces
decidir dónde vive.** Medirlo plegado produce un número que no responde ninguna pregunta.

---

## Y una advertencia sobre el costo

Un factor que mejora la utilidad **no es gratis**: agrega llamadas o tokens. La decisión de
adoptarlo se toma **barriendo λ**, igual que la de elegir un patrón — nunca sobre la utilidad
sola. Un factor reportado sin cobrar su costo es el punto `λ=0` de una curva que nadie
mostró.
