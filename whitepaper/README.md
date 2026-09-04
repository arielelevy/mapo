# El paper — v2.1 activa (septiembre de 2026)

`paper-es.md` es la única versión extensa mantenida. `paper-corto-es.md` es la versión de
conferencia y se sincroniza cuando cambia la tesis, una definición o un resultado central. La
redacción inglesa quedó congelada en `historico/paper-en-congelado.md`; no se edita.

---

## Orden de lectura

| # | archivo | por qué en ese orden |
|---|---|---|
| 1 | **`GATE.md`** | antes que nada. Ocho criterios binarios y su veredicto. Dice qué falta y, sobre todo, **qué no se puede afirmar todavía** |
| 2 | **`paper-corto-es.md`** | el argumento principal en versión de conferencia |
| 3 | **`paper-es.md`** | el registro completo, con demostraciones y apéndices |
| 4 | **`PATTERNS.md`** | el catálogo de patrones. Es el producto separable: sirve sin el paper |
| 5 | **`ANALYSIS.md`** | dónde falla cada paradigma y por qué, con la traza |
| 6 | **`PLAN.md`** | sólo si interesa por qué cambió la tesis. Es arqueología, no tesis |

**Y `MAP.md`** es la única herencia de v1 que quedó: plasticidad Hebbiana para decisiones.

---

## Qué afirma el paper, en una frase por sección

**§3 — el motor.** Ejecuta `proponer → tipar → verificar/admitir → decidir`: factibilidad
aritmética, base de creencias con procedencia y alcance, dial efectivo por `max`, policy-as-code
y abstención.

**§4 — la teoría mínima.** Distingue desacuerdo de trayectoria `V_T` y de salida `V_Y`. Bajo un
stack no-modelo determinista, `d(T)=0` implica `V_T=0` e independencia entre la trayectoria y la
aleatoriedad del modelo. Una clave `COMPUTED` conserva esa propiedad.

**§5 — el método.** Fija corrector sin juez LLM, paneles mecánicos, pisos de ruido y preguntas de
investigación antes de leer resultados.

**§6 — lo medido.** El 12–28% es desacuerdo de utilidad entre réplicas, no una medición directa
de `V_T`. La intervención sobre control es en muestra. Capacidades y adaptación de política son
evidencia secundaria; θ de costo ahorra 41% contra una constante con IC95 que cruza cero.

---

## El estado del gate

**Sin bloqueantes, un condicional** — `G3` (soporte de afirmaciones). `G2` quedó cerrado tras la
verificación fechada de literatura. El detalle y el historial
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

**Los mecanismos son más firmes que las magnitudes.** La intervención de control es en muestra;
el desacuerdo entre réplicas mezcla ramificación y stack de servicio; y el leave-one-arm-out
tiene ocho puntos. El paper los declara como límites, no como notas al pie.

---

## Figuras

Los SVG activos están en `figuras/`. `contrato-de-garantia.svg` y
`metodo-determinista.svg` se regeneran con `py _figuras_arquitectura.py`; las versiones previas
viven en `historico/`.
Las tres que pidió la revisión C (estabilidad contra ramificación, riesgo contra cobertura,
frontera de costo y utilidad) salen de `py bench/analysis/_figuras_revision.py`, desde `lab/`,
y leen sus números de los JSON de `_predictores.py` y `_p34_costo.py`.

`artefactos/` versiona los documentos visuales del estado vivo.

---

## La regla que gobierna todo esto

**Nada entra al paper sin implementación que lo corra en `../lab/`.** Si algo está acá como
«declarado, no medido», es deuda: se implementa o se saca. Y las novedades se enuncian como
**conjunción**, nunca como partes — cada conjunto por separado tiene un vecino publicado, y
`GATE.md` §8quater lleva la cuenta con búsquedas fechadas para que un lector pueda
re-correrlas.
