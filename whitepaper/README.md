# El paper — v2, activa (agosto 2026)

**Dos archivos, un solo paper.** `paper-en.md` es el canónico —destino arXiv `cs.LG`— y
`paper-es.md` es su espejo. **Toda edición va a los dos, en la misma posición**, y
`../lab/bench/audits/_audit_documentos.py` lo hace cumplir comparando la secuencia de
encabezados: hoy da **49 = 49**.

---

## Orden de lectura

| # | archivo | por qué en ese orden |
|---|---|---|
| 1 | **`GATE.md`** | antes que nada. Ocho criterios binarios y su veredicto. Dice qué falta y, sobre todo, **qué no se puede afirmar todavía** |
| 2 | **`paper-en.md`** | el paper. `paper-es.md` para leer en castellano |
| 3 | **`PATTERNS.md`** | el catálogo de patrones. Es el producto separable: sirve sin el paper |
| 4 | **`ANALYSIS.md`** | dónde falla cada paradigma y por qué, con la traza |
| 5 | **`PLAN.md`** | sólo si interesa por qué la tesis cambió dos veces. Es arqueología, no tesis |

**Y `MAP.md`** es la única herencia de v1 que quedó: plasticidad Hebbiana para decisiones.

---

## Qué afirma el paper, en una frase por sección

**§4 — la factibilidad es aritmética.** Qué topología *puede* correr una tarea se computa
de cantidades declaradas, sin una llamada al modelo. Poda tres de siete candidatas antes de
gastar un token, y separa dos modos de falla que se confunden de rutina: `map_reduce` está
acotado por **cardinalidad**, no por tamaño total.

**§5 — la teoría, y es lo único no condicionado a una corrida.** Cinco resultados
estructurales, verificados con test:

| | |
|---|---|
| **§5.1** | el Teorema del Valor de Selección: una descomposición **por destino** sobre `k` brazos, con `ρ` —la selectividad de la pérdida— como parámetro del umbral de imposibilidad |
| **§5.2** | dominancia de cascada, y la partición por **verificabilidad**: `v=1` va a cascada, `v=0` a router |
| **§5.3** | soundness del ensamblador: si emite, todo número emitido está implicado por la base de creencias al piso pedido |
| **§5.4** | la cota nativa del ratchet: `≤ 2R` endurecimientos en toda la vida del sistema |
| **§5.5** | quién fija el dial: `max` es la **única** composición donde toda fuente sólo puede endurecer |
| **§5.6** | lo que la teoría **no** supone — ninguno de los cinco menciona recuperación, y eso **es** la afirmación |

**§6 — el diseño**, y §6.5 dice algo que el paper no decía: el mismo producto cruzado que
mide los paradigmas **ajusta la capa que los elige**, a costo marginal cero.

**§7 y §8 — lo medido**, y su afirmación más fuerte no es sobre topologías: decirle a un
bucle iterativo que su retriever dejó de producir cortó su costo **3,05×** contra una
dispersión de réplica de 1,62×.

---

## El estado del gate

**Sin bloqueantes, dos condicionales** — `G2` (novedad) y `G3` (soporte de afirmaciones).
`G1` se cerró el 2026-08-23; `G5` y `G7` pasaron de FAIL a PASS. El detalle y el historial
están en `GATE.md`, que es la única fuente: este README no lo repite porque **dos lugares
que dicen el estado del gate empiezan a decir cosas distintas**.

---

## Lo que el paper NO tiene, dicho acá para que no haya que buscarlo

**No hay un selector validado.** El objetivo declarado del producto —ganarle al mejor
paradigma fijo sobre datos held-out— se midió y **perdió**: `P15`, −0,087 más allá del piso
de ruido. El mecanismo está diagnosticado (el vocabulario de región no tiene eje de
horizonte) y el chequeo de sensibilidad confirma que no es un artefacto del procedimiento.
La contribución es **teoría + método + negativos**, no un sistema que anda.

**Un corpus sintético, y ningún benchmark público.** El ground truth es exacto y se
re-deriva independiente del generador, y los parámetros estructurales son diales — pero la
distribución de tareas reales sobre esos diales es desconocida.

**La superficie de acciones es arquitectura declarada y no ejercitada.** Las 12
herramientas de todo el registro leen el mundo, escriben el estado del propio agente, o
leen su contabilidad: **ninguna cambia nada fuera del proceso**. Las 6 tareas con
`irreversible = True` son una clasificación calificada por exact-match con la etiqueta de
una acción encima. Está declarado en §9, no escondido.

**Y una rama de la propia teoría está estructuralmente sin probar.** §5.2 parte el problema
sobre `v` —si existe un detector barato— y **todo corpus de este registro cae del lado
`v = 1` por construcción**: el gold es lo que vuelve la calificación libre de juez, y el
gold **es** un detector. Ser calificable implica ser verificable, así que ningún benchmark
de exact-match puede ejercitar la rama que necesita un router.

---

## Cómo leer los números

**Ya no es `n=1`.** El régimen medido hoy es `repeat = 3` por celda sobre tres modelos
(`gpt-5.4-nano`, `gpt-5.6-luna`, `gpt-5.6-terra`), con piso de ruido **por celda** y
decisiones sobre la brecha **neta**. La grilla original de `gpt-5-chat` quedó congelada
como primer modelo y ya no es referencia.

**Los mecanismos son más firmes que las magnitudes**, y eso no cambió: descansan en trazas
de uso de herramientas y no en tamaños de efecto. Una réplica accidental obligó a retirar
un efecto reportado y a partir otro al medio — está en `GATE.md` §8bis, y es la disciplina
funcionando, no fallando.

---

## Figuras

Las 6 de `diagrams/` están sólo en inglés (`_en`). Las dos de resultados llevan una banda
roja **PRELIMINARY** con la `n` **adentro del SVG**, para que la advertencia no se pueda
separar de la figura al copiarla.

`artefactos/` versiona los documentos visuales del estado vivo.

---

## La regla que gobierna todo esto

**Nada entra al paper sin implementación que lo corra en `../lab/`.** Si algo está acá como
«declarado, no medido», es deuda: se implementa o se saca. Y las novedades se enuncian como
**conjunción**, nunca como partes — cada conjunto por separado tiene un vecino publicado, y
`GATE.md` §8quater lleva la cuenta con búsquedas fechadas para que un lector pueda
re-correrlas.
