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
| `handoff` | agentes con alcance propio y transferencia **autorizada por código**: las llamadas las acota la cantidad de alcances, no un bucle que el modelo corta |
| `supervisor` | orquestador que despacha el próximo sub-agente **después** de ver lo que volvió el anterior — las llamadas **no** están decididas de antemano |

Y los dos que están en el registro pero **fuera del ruteo**, que es donde esta prueba se
aplicó con consecuencias: `cot` quedó afuera porque **el fraseo no es un patrón** (mismo
grafo de control que `direct`, misma utilidad, nunca más barato), y `plan_execute` por
dominado. Los dos siguen ejecutándose para replay.

**Factores** — no entran al catálogo; se cruzan contra él:

| factor | valores | estado |
|---|---|---|
| brazo de recuperación | `hybrid`, léxico, denso, degradados | medido |
| variante de superficie | `basic`, `accounting`, `cognitive` | medido |
| dial de garantía | A0–A3 | medido |
| respuesta hipotética antes de buscar | `{con, sin}` | decidido, **sin medir** |
| pizarra compartida (`shared_state`) | `{con, sin}` | **extraída** a `app/board.py` y cruzable; el brazo `dag_strategy` ya no la tiene soldada. Falta correrla |
| contratos de afirmación | `{con, sin}` | `C-NUM` y `C-COMPLETE` implementados; `C-COMPLETE` **cableado**, veredicto por fila |
| **regla de parada** (`stop_on_barren`) | `0` / `N` | implementado, apagado por defecto, **P20a-d registradas** |
| **ofrecer `read_all`** (`offer_read_all`) | `{con, sin}` | implementado, apagado por defecto, **P21a-d registradas** |
| **descripciones cortas de tools** (`terse_tools`) | `{con, sin}` | implementado, **P24a-d registradas**. Las descripciones son 55% del payload, y acortarlas no cambia quién decide la próxima acción — de ahí que sea factor |
| **ofrecer la pizarra a todos** (`offer_board`) | `{con, sin}` | implementado. Es la extracción del factor que estaba soldado adentro de `dag_strategy` — ver «la consecuencia que ya se pagó», abajo |
| **podar el material** (`compact_material`) | `{con, sin}` | implementado. Acorta lo que el modelo recibe sin tocar el grafo de control |
| **compactar la historia** (`managed`) | `{basic, managed}` | implementado. Mismas tools que `basic` **a propósito**: lo que cambia no es lo que el modelo PUEDE llamar, sino lo que el harness le HACE a la historia |

> **Los cuatro de arriba llegaron con la misma cicatriz.** `offer_board`, `terse_tools` y
> `compact_material` se implementaron y **no llegaban al modelo**: la única función del repo
> que declara las tools no los recibía. Tenían test sobre `specs_for` y ninguno sobre el
> **camino**. Un factor inerte no da error — da exactamente la base, que es el resultado más
> difícil de distinguir de «no sirve». Hoy lo atrapa `test_science.py` §59 y la corrida
> light comparando cada factor contra la base.

---

## La consecuencia que ya se pagó, y cómo se saldó

La pizarra vivía **soldada adentro de `dag_strategy`**, y no la usaba nadie más. Eso tiene
una consecuencia medible: `dag_strategy` es de los mejores del catálogo, y cualquier ventaja
suya mezclaba dos cosas que nadie había separado — su descomposición, y tener estado
compartido.

> **Un factor plegado adentro de un brazo no se puede atribuir.** El brazo gana, y no se
> sabe cuál de las dos mitades ganó — lo que además impide dárselo a los demás.

**Saldada** (2026-08-29): la pizarra vive en `app/board.py`, es una **dimensión**
(`shared_state`) que se cruza contra todo el catálogo, y `offer_board` la ofrece como tool a
cualquier patrón. Lo que falta es correrla, no extraerla.

El orden correcto quedó escrito por haberlo pagado: **extraer el factor, medirlo cruzado, y
recién entonces decidir dónde vive.** Medirlo plegado produce un número que no responde
ninguna pregunta.

---

## Y una advertencia sobre el costo

Un factor que mejora la utilidad **no es gratis**: agrega llamadas o tokens. La decisión de
adoptarlo se toma **barriendo λ**, igual que la de elegir un patrón — nunca sobre la utilidad
sola. Un factor reportado sin cobrar su costo es el punto `λ=0` de una curva que nadie
mostró.
