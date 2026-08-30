# Propuesta de §6.5 — el banco es un procedimiento de ajuste, no sólo un instrumento

> **La tesis del autor (2026-08-29):** *«es como si fuera un experimento de ML — el LLM no
> lo conoce, pero tomamos el harness para cada estilo de corpus. Si el corpus es
> representativo del dominio, debería andar.»*
>
> Encaja con lo que el ejecutable hace, y el paper **no lo dice en ningún lado**. Lo que
> sigue es la formulación, el inventario exacto de qué se ajusta, y —lo que hace que valga
> publicarla— **el estado medido, que incluye una refutación.**
>
> **APLICADO el 2026-08-29** como **§6.5** en los dos archivos. Este queda como el
> razonamiento y el inventario largo; el número en vivo del paper se refrescó al insertarlo
> (516 filas · 141 episodios · 57 pares con evidencia · 27 con `n ≥ 3`). `W-6` cerrada en
> `lab/PAPER.es.md`.

---

## La formulación

El modelo está **congelado y no se entera**. Lo que se ajusta es la capa de decisión, y se
ajusta **sobre el registro del producto cruzado**: cero llamadas nuevas, replay
contrafáctico sobre filas ya pagadas.

```
corpus de un dominio  ──►  producto cruzado (tarea × paradigma × réplica)
                                      │
                                      ▼
                           consolidación offline
                                      │
                      ┌───────────────┴───────────────┐
                      ▼                               ▼
              capa de decisión ajustada        el modelo, INTACTO
```

**Y eso da una lectura del banco que el paper no tiene:** no es sólo el instrumento que
mide los paradigmas, es **el procedimiento de ajuste de la capa que los elige**. El mismo
producto cruzado que produce el número produce el θ.

> **Un experimento de ML donde el aprendiz no es el modelo.** El gradiente no existe; lo que
> hay son estadísticas por región sobre episodios registrados, con guarda de promoción. Y
> por eso el artefacto ajustado es **legible y diffeable** — dos versiones de θ se comparan
> como código, no como pesos.

---

## Qué se ajusta, exactamente

El inventario sale del bundle firmado (`PolicyBundle`) y del ciclo de consolidación, no de
una intención:

| se ajusta | qué es | estado |
|---|---|---|
| **`stats`** | por `(región, paradigma)`: tasa de victorias y peso Hebbiano | **ejecutado**, y el peso **no lo lee el router** — está probado que no puede mejorar un argmax |
| **`floors`** | el piso de garantía por región, aprendido de estadísticas de **rechazo tipado** | **ejecutado**, con guarda de replicación y techo en `ACCOUNTABLE` |
| **`model_stats`** | idem por `(región, modelo)`: la segunda política | **ejecutado** |
| **`trusts_elicited`** | calibración de la credencia elicitada, computada desde el log de creencias | **ejecutado**, y viaja **firmado adentro del bundle** — no como parámetro |
| **`clauses`** | cláusulas de adquisición certificadas (REC) | **ejecutado**; hoy **ninguna se promueve** — el beneficio neto no supera el piso de ruido al λ de decisión |
| **asociaciones de orden** | pares ordenados de herramientas, reforzados por **resultado** | **medido** (`p = 0,0078`) y **ningún consumidor lo lee** |
| **el reparto del handoff** | qué unidades ve cada sub-agente | **NO se ajusta**: es un paso por índice, fijo |

**Las dos últimas filas son el punto.** El autor las nombró —*«orden de llamada, handoff»*—
y son exactamente las dos superficies donde el aprendizaje **existe como medición y no como
mecanismo**. Decirlo es más valioso que insinuar que ya funcionan.

---

## Las tres disciplinas que lo vuelven un ajuste y no una ilusión

**1. Un episodio es una celda, no una réplica.** Las réplicas son mediciones repetidas de lo
mismo; contarlas por separado es pseudorreplicación, y computar «fue el mejor» sobre trials
crudos deja que una réplica con suerte cobre el refuerzo que la media de su paradigma nunca
ganó.

**2. La partición en tres, por tarea.** `search` propone, `validate` puntúa, y `final` lo
toca **únicamente** la guarda de promoción. Una regla descubierta nunca puede ser puntuada
por los datos que la propusieron. Y el mundo final es de **un solo uso**, gastado *antes* de
responder.

**3. Los ejes de partición están tipados por cuándo se conocen.** Una regla sólo puede
gobernar si se la puede **evaluar en el momento de decidir**. `truth_coupling` es el oráculo
del extractor y `iterations`/`cost_tokens` son posteriores a la ejecución: partir sobre ellos
descubre una regla que no se puede aplicar. El tipo lo dice; no se descubre al cablearla.

---

## La afirmación de transferencia, y su estado medido

La tesis se completa con un condicional: *«si el corpus es representativo del dominio,
debería andar»*. Eso es falsable, y **este registro ya lo falsó una vez**.

> **`P15`.** Sobre un mundo que θ nunca había visto —seed 47, 390 celdas, cero errores de
> infraestructura— el ruteo por request perdió contra el mejor paradigma fijo por **−0,087**,
> más allá del piso de ruido, **mientras reproducía cada decisión 26/26** desde su base de
> creencias registrada.

**Y el mecanismo es el hallazgo, no el número.** El vocabulario de región **no tiene eje de
horizonte**, así que las tareas que castigan una elección fija eran indistinguibles de las
que la premian. θ ruteó contra su propio veredicto registrado porque **ninguna etiqueta le
dijo nunca que estaba en ese caso**.

> **Eso es una condición sobre la representatividad, hecha precisa.** «Representativo del
> dominio» no alcanza: el corpus tiene que ser representativo **en los ejes que el
> vocabulario de región distingue**. Un corpus que varía en una dimensión que φ no mira
> produce episodios que θ no puede separar — y θ aprende un promedio sobre dos poblaciones.

Chequeo de sensibilidad, y es lo que le da peso: reparar la validez del aprendizaje
—agregación por episodio, holdout limpio— **deja el número idéntico**. La refutación no es un
artefacto del procedimiento.

---

## Y una consecuencia práctica que el paper puede afirmar hoy

**Más inferencia no compra más ajuste.** La consolidación es replay sobre el registro, así
que el costo de aprender es **cero llamadas**: lo que la cuota compra son **episodios**, y
el ajuste es gratis sobre los que haya.

Eso separa dos decisiones que se suelen tomar juntas:

| | qué la gobierna |
|---|---|
| **cuánto medir** | la potencia estadística: cuántos episodios por región hacen falta para que la guarda pueda decidir |
| **cuánto entrenar** | nada — es gratis, y se puede correr en cualquier momento sobre lo que haya |

Y es **observable en vivo**: sobre la campaña actual, con **276 filas** hay **57 pares
`(región, paradigma)` con evidencia y cero con `n ≥ 3`**. θ todavía no puede decidir nada, y
eso se sabe **sin gastar un token más** — que es exactamente la decisión que antes se tomaba
a ciegas.

---

## Qué falta para que esto sea una contribución y no un encuadre

| # | qué | por qué importa |
|---|---|---|
| 1 | **un consumidor para las asociaciones de orden** | están medidas (`p = 0,0078`) y ninguna regla las lee. Es la superficie que el autor nombró primero |
| 2 | **el reparto del handoff, aprendido** | hoy es un paso por índice. Medido: cambiar el reparto **mueve la utilidad** —en una celda, de 0,000 a 1,000— así que no es una simetría inocua |
| 3 | **un eje de horizonte en el vocabulario de región** | es la causa medida de la refutación de `P15`. Sin él, la transferencia no puede funcionar aunque el corpus sea representativo |
| 4 | **la condición de representatividad, enunciada** | «representativo del dominio» tiene que volverse «representativo en los ejes que φ distingue», que es chequeable sobre un corpus antes de correrlo |

**El (3) es el que ordena a los otros.** La tesis de transferencia no se puede sostener
mientras el vocabulario no distinga el eje que decide — y eso ya no es una conjetura: es lo
que `P15` midió y lo que el chequeo de sensibilidad confirmó que no es un artefacto.

---

## Dónde va, y qué no toca

**§6.5**, después de §6.3 (consolidación de la política de control), que es donde el paper
ya describe la maquinaria sin nombrar lo que es. No toca §5 ni §7: es un encuadre sobre
mecanismos ya descritos, más el estado medido de su afirmación de transferencia.

Y **no reclama novedad sobre «aprender sin actualizar pesos»** — §2.6 ya cede ese terreno.
Lo que se afirma es más angosto y más defendible: **el mismo producto cruzado que mide los
paradigmas es el conjunto de ajuste de la capa que los elige, y el costo marginal de ajustar
es cero.**
