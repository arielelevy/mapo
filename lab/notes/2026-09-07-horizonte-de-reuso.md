# Registro de investigación: el horizonte de reuso como eje, y `LEARNABLE` como vía

**Fecha:** 2026-09-07
**Estado:** implementado y corrido; **sin resultado empírico y sin corpus que lo permita**.
No constituye preregistro final. Nada de esto entra al paper.

## Observación que origina el eje

La discusión arrancó por una afirmación sobre memoria biológica: que un recuerdo no es un
archivo sino un patrón distribuido, y que el avance en memoria artificial llega cuando eso se
traduce a código, con el cómputo puesto en el almacenamiento más que en la recuperación.

**La mitad del sustrato ya está hecha y es un callejón.** La atención escalada *es* la regla de
update de la Hopfield moderna (Ramsauer et al., 2008.02217) y aproxima la Sparse Distributed
Memory de Kanerva (Bricken & Pehlevan, 2111.05498); la indexación hipocampal ya está
implementada como recuperación (HippoRAG, NeurIPS 2024). Reconocer que la memoria es
distribuida no destraba nada porque ya se construye así.

**La mitad del cómputo en escritura tampoco es el hueco.** `gain × need` de Mattar & Daw
(Nat Neuro 2018) es la teoría normativa de qué conviene consolidar; el cómputo en reposo está
medido (sleep-time compute, 2504.13171: 5× menos cómputo de test para igual exactitud,
2,5× más barato amortizado). Lo que ese mismo paper reporta al costado es la restricción que
importa: **la eficacia correlaciona con la predictibilidad de la consulta**, que es el término
`need` y nada más.

Lo que sí está abierto es la condición de frontera. En biología la reconsolidación sólo se
dispara bajo **error de predicción**: sin mismatch no hay labilización, y forzarla aporta
riesgo de deterioro sin beneficio (Nader et al., 2000; Sevenster et al., 2014; Fernández
et al., 2016). La industria consolida incondicionalmente y paga: la consolidación colapsa N
entradas con procedencias distintas en un resumen, el agente **termina citando la paráfrasis
en vez de la fuente**, y es irreversible.

## El resultado que convierte esto en un problema de ruteo

`Memory Depth, Not Memory Access` (2606.26806) mide un *depth flip* con compuerta de escritura
por **sorpresa × valencia**, 2,4-2,6 escrituras cada 200 eventos:

| tarea | escritura selectiva | recuperación |
|---|---|---|
| recall factual corto | 0,463-0,483 | **0,956-0,973** |
| persistencia de meta tras descargar el contexto | **0,812-0,904** | 0,394-0,398 |

Leído como resultado de memoria dice «depende». Leído como resultado de **ruteo** dice otra
cosa: ningún lado gana los dos, así que el ganador lo determina un eje, y ese eje no está en φ.
Es la forma exacta de `P15`, donde θ perdió `−0,087` porque el vocabulario de región no
representaba continuidad ni horizonte. Éste es el horizonte, del lado que faltaba.

## Hipótesis de diseño

Toda la ontología de `ONTOLOGIA_PREGUNTAS.es.md` mira hacia atrás: `C1` pregunta qué alcance
heredó este pedido del anterior, y nada pregunta **qué le deja al siguiente**. El eje simétrico
—horizonte de reuso— no lo puede medir ningún sensor, porque no es una propiedad del material
ni del enunciado: es una frecuencia sobre la población de pedidos, y vive en el ledger.

Eso obliga a un tercer casillero en el sistema de creencias. `Provenance` ordena **cómo** se
obtuvo una creencia y `Scope` dice **sobre qué** es; los dos describen una creencia que ya
existe. Faltaba el eje que describe un **hueco**: cómo se llegaría a creer lo que hoy no se
cree.

## Lo implementado (2026-09-07)

Todo corre y las tres suites pasan. Ninguna llamada paga: el autor no tiene créditos hasta el
2026-09-13, y nada de esto los necesita.

**`beliefs.Acquisition`** — el tercer eje, con cinco vías y su resolución:

```
MEASURED     función pura del payload            -> COMPUTED  / REQUEST
PROBEABLE    una sonda lo mide, pagando          -> OBSERVED  / REQUEST
ELICITABLE   se le pregunta al modelo            -> ELICITED  / REQUEST
LEARNABLE    de este pedido nadie; del ledger sí -> COMPUTED  / POPULATION
UNAVAILABLE  nadie, por ninguna vía              -> nada
```

`LEARNABLE` es el casillero que faltaba. Hoy un eje así cae en `permanent_gaps()` —«nadie
puede»— que es la misma mentira que §78 arregló con `horizon_unknown`, y con la misma
consecuencia: abstenerse para siempre sobre algo que el registro ya contesta.

Y **es seguro sin agregar ninguna guarda**, que es lo que lo hace admisible. Una creencia
aprendida entra `COMPUTED` sobre `POPULATION`, y `admissible_for_action` ya exige
`Scope.REQUEST` desde que entraron las asociaciones: una regularidad estadística no puede
gatear lo irreversible porque el retículo ya lo impide.
`acquisition_closes_for_action` deja eso contestable **antes** de gastar una sonda que no iba
a alcanzar igual.

**`features.FEATURE_ACQUISITION`** — retrofit del binario de §78: `coupling` es `PROBEABLE`,
`horizon_unknown` es `UNAVAILABLE`. El `None` deja de significar dos cosas a la vez («nadie
puede» y «nadie lo declaró»), que era la queja literal de §78: un campo sin clasificar se cae
del filtro en silencio.

**`app/reuse.py`** — el primer eje `LEARNABLE`. **No es un feature y ésa es la decisión de
diseño del módulo**: meterlo en `Features` lo haría entrar a `region()` y a la proyección D2, y
lo declararía como creencia sobre este request cuando es una frecuencia sobre otros. Es el
mismo error de categoría que `Scope` existe para impedir. `learnable_gaps()` devuelve vacío por
construcción, y eso es la frontera entre las dos capas escrita como código.

Dos negativas del módulo que son parte del diseño y no descuidos. No usa `task_id` como
sesión —dos réplicas de la misma tarea no son dos pedidos encadenados— y **descarta entera
toda sesión con `orden` repetido**: el eje afirma precedencia («más adelante en la misma
sesión»), y ordenar por un campo empatado dejaría que el orden del archivo decida quién vino
antes. Las dos se cuentan y se reportan en vez de resolverse adivinando.

**`capacidades.PERSISTE_ENTRE_REQUESTS`** — la capacidad del lado profundo del flip. **Cero de
los doce brazos la tiene**, y el nuevo eje de ontología `reuso_diferido` no tiene ningún brazo
capaz. Es el segundo hueco que el catálogo encuentra sin correr nada, después de `ausencia`.

## Lo medido: la ausencia, con su motivo

Corrido sobre el registro completo, **7.838 filas, 0 sesiones, 7.838 sin sesión**. El eje no es
establecible en este banco, por construcción del banco. `porque_no()` lo dice con esa frase en
vez de devolver un cero que se leería como «no hay reuso».

Y no se inventa la columna. Usar `task_id` como sesión sería una mentira con forma de dato: dos
réplicas de la misma tarea no son dos pedidos encadenados, son la misma pregunta hecha de
nuevo, y contarlas como reuso mediría el diseño del banco y lo reportaría como propiedad del
mundo.

El encabezado de `ONTOLOGIA_PREGUNTAS.es.md` dice que el corpus ya decidió en silencio tres
veces qué hipótesis podían ponerse a prueba —el detector heredado del gold, las entidades sin
ambigüedad, el turno único— «y este documento existe en parte para que la cuarta no pase
desapercibida». **Ésta es la cuarta, y queda contada.**

## Contribución provisional

Ninguna pieza es nueva por separado, y la lista de abajo lo demuestra. La conjunción bajo
estudio es:

> un eje de horizonte de reuso aprendido del ledger como creencia de alcance **poblacional**
> —y por eso estructuralmente inadmisible para gatear una acción irreversible, sin regla que lo
> imponga—, usado para **rutear entre profundidad y acceso por request** en vez de para elegir
> un sistema de memoria, con el veredicto decidido sobre brecha NETA contra un piso de ruido
> por celda.

**Y la conjunción es delgada; conviene decirlo antes que descubrirlo en revisión.** Dos de sus
tres partes son maquinaria que este repo ya tenía aplicada a un eje nuevo. La parte que no
tiene vecino directo es la primera: en toda la lista de abajo no hay un sistema de memoria con
un retículo epistémico donde el alcance de una creencia decida qué puede gatear.

## Vecinos encontrados en la búsqueda

| Línea | Vecino | Riesgo para el claim |
|---|---|---|
| Teoría del engrama | Josselyn & Tonegawa, Science 2020 | Allocation y ecphory ya formalizados; el trazo es distribuido **y direccionable**, no una mancha. |
| Sistemas complementarios | McClelland et al. 1995; Kumaran et al. 2016 | Replay como puente rápido→lento ya es la teoría canónica de consolidar. |
| Replay normativo | Mattar & Daw, Nat Neuro 2018 | `gain × need` ya es la teoría formal de qué computar al almacenar. |
| Memoria asociativa = atención | Ramsauer et al., 2008.02217; Bricken & Pehlevan, 2111.05498 | El transformer ya **es** memoria distribuida direccionable. |
| Índice hipocampal en RAG | HippoRAG, NeurIPS 2024 | Separación y completado de patrón ya implementados sobre KG. |
| Compuerta de escritura por sorpresa | Titans, NeurIPS 2025 (2501.00663); Nested Learning / HOPE, 2512.24695 | Sorpresa con momento y decay ya es la compuerta; CMS ya es memoria multi-escala. |
| Cómputo en reposo | Sleep-time compute, 2504.13171; Auto-Dreamer, 2605.20616 | Consolidación offline ya medida, con su restricción de predictibilidad. |
| Consolidación destructiva | Wire, 2026 | La crítica de procedencia ya está hecha, y las aristas tipadas ya propuestas. |
| Profundidad contra acceso | 2606.26806 | **El vecino más cercano**: ya mide el flip y ya gatea la escritura por sorpresa × valencia. |
| Reconsolidación bajo error de predicción | Nader 2000; Sevenster 2014; Fernández 2016 | La condición de frontera ya está establecida en biología. |
| Confounds de evaluación | MemDelta, 2606.29914; Same Ranking Different Winner, 2605.24060 | La crítica metodológica ya existe, y es la que este banco ya practica. |

Dos contras que hay que registrar porque debilitan la moda, no el claim. La reimplementación
crítica de Titans (2510.09551) reproduce que la memoria ayuda pero encuentra que **el
aprendizaje en test-time no funciona**: tras 50 épocas la variación queda en el cuarto decimal
y después degrada. Y sobre los benchmarks: hay sistemas que ganan LongMemEval con 2,6M de
caracteres recuperados por consulta cuya ventaja **desaparece al controlar el presupuesto de
retrieval**. Nadie pone piso de ruido — que es exactamente lo que `REC` no cruzó y por eso no
se promovió.

## Lo que NO se hizo, y por qué

- **No hay regla que lea `reuse_horizon`.** Asentar una creencia que nadie lee es el defecto de
  `horizon_unknown` repetido. Entra cuando haya con qué medirla.
- **No se tocó el vocabulario de región** ni `REGION_VOCABULARY`. θ no se invalida, y el eje no
  entra a la clave de aprendizaje mirando ningún dato.
- **No se implementó la compuerta de escritura por error de predicción**, que es la mitad que
  la biología tiene y la industria no. Es la apuesta siguiente y va sola.
- **No se tocó el paper.** Nada de esto está medido.

## Lo que bloquea la medición, y no son los créditos

`P42` queda registrada en `historico/BITACORA-PREDICCIONES.es.md`. El bloqueo no es de plata:
es que **el corpus es de turno único y este eje necesita sesiones encadenadas**. Correrlo exige
un corpus nuevo con secuencias, que es una decisión del autor y un costo aparte. La parte
aritmética —si la tasa de reuso varía por región— cuesta cero llamadas una vez que ese registro
exista, porque es contar.
