# Informe de revisión A. `paper-es.md`, borrador 3.0 (2026-09-01)

Revisor: cs.LG / cs.AI, agentes LLM y sistemas de producción. Lectura completa de las 3.389 líneas
antes de abrir cualquier otro documento. Después, verificación contra el laboratorio:
`lab/results/luna/gold_h1_rows.jsonl` (2.511 filas), `lab/results/luna/gold_holdout_rows.jsonl`
(936 filas), `lab/results/terra/gold_h1_rows.jsonl` (350 filas) y sus backups,
`lab/results/nano/*.json`, `lab/results/eda_capacidades.json`, `lab/app/capacidades.py`,
`lab/bench/panel.py`, `lab/bench/analysis/_analyze_ratchet_cost.py` y la bitácora
`lab/historico/BITACORA-PREDICCIONES.es.md`. Los conteos los corrí con `py` sobre el JSONL; digo
qué corrí y qué dio en cada caso. Las líneas citadas son las del archivo tal como está hoy.

---

## 1. Veredicto

Revisión mayor. No rechazo, y tampoco menor.

El registro existe y reproduce: recomputé la tabla de §7.1 (aplica, `u`, `u × aplica`, tokens por
celda) contra las 2.511 filas y coincide dígito a dígito en los doce brazos; la curva de consenso
de §7.5.1 da 180 de 180 en `k ≥ 4` con una normalización burda; el `pass^3` de la tabla de §7.1
sale idéntico sobre el rectángulo 64 × 8. El protocolo de predicciones registradas es real y las
refutaciones están anotadas antes del número. Eso vale y es raro.

Lo que no se sostiene es la relación entre los titulares y su fuente. El número más repetido del
paper (`0,33 → 0,89` en cadenas acopladas, y "12 correctas, 3 abstenciones, cero equivocadas") no
sale de la campaña `luna` que el paper declara como única fuente de §7: sale de `terra` (8 de 9
celdas) y de un pool `terra + luna` (8 + 4 correctas, 1 + 2 ceros), en contra de la afirmación de
§8.1 de que ninguna estadística mezcla modelos. La definición formal de confinamiento (`d = 0`)
no la cumple el Algoritmo 1 que es el caso estrella. La contribución 2 no cruza su nulo. La
contribución 3 dice en el resumen algo que su propia tabla de §7.8.4 desmiente. Y §8.1 y §8.2
tienen párrafos heredados de otra versión que contradicen a §7. Todo eso se arregla; parte con
redacción, parte con una corrida acotada sobre `luna`. Hasta que se arregle, el paper afirma
más de lo que su registro muestra.

---

## 2. Las cinco objeciones más graves

### O1. Los números de C3 vienen de otro modelo, sin declararlo, y la corrección se iteró sobre las celdas que la evalúan

Dónde: resumen l.94-97, l.118-121; §1.1 l.196-198; §7.2.3 l.1859-1860; §7.2.4 l.1939;
§7.4.2 l.2389; §7.6.3 l.2656-2657; §9 l.3216; `capacidades.py` l.116 y l.170.

Qué dice el paper: que `pointer_chase` pasó de `0,33` a `0,89` en C3 y que `dag_strategy` gana esa
celda con 12 correctas, 3 abstenciones y cero equivocadas. §7.2 abre diciendo que sus tres
preguntas "se contestan sobre el mismo registro" (l.1762). §7.0.1 dice que la campaña `luna` "es
la única fuente de los números de esta sección" (l.1528). §8.1 dice que "ninguna estadística los
mezcla, y el cargador del registro levanta si un archivo lo hace" (l.3051-3052).

Qué dio la verificación:

- `results/luna/gold_h1_rows.jsonl`, celda C3, `dag_strategy`: 6 filas (dos tareas, `c3-000-h1`
  y `c3-001-h2`), utilidades `[1, 0, 0, 1, 1, 1]`, media `0,667`. Uno de los dos ceros tiene por
  respuesta `'The settlement account on file for M. Ar…'`, que es una respuesta y no una
  abstención. `pointer_chase`: 6 filas, `[1, 0, 0, 0, 0, 0]`, media `0,167`.
- `results/terra/gold_h1_rows.jsonl` (`gpt-5.6-terra`), C3: `dag_strategy` 9 filas, media
  `0,889`, un solo cero (`'Cannot be determined'`); `pointer_chase` 9 filas, media `0,889`, un
  cero (`'cannot be determined'`).
- 8 + 4 = 12 correctas; 1 + 2 = 3 ceros. El "12 / 3 / 0" es la suma de los dos modelos, y el "cero
  equivocadas" es falso sobre `luna`.
- La secuencia de backups de `terra` muestra la corrección de `pointer_chase` iterada sobre las
  mismas 9 celdas: `bak-pointer_chase-20260830-201915` da `0,333`; `bak-pc2-20260830-202301` da
  `0,000`; `bak-pc3-203030` da `0,000`; el archivo final da `0,889`. Tres intentos visibles
  sobre el mismo conjunto de prueba. El "antes" de la Figura de §7.2.4 (réplica 0 con 1,000 y
  réplicas 1 y 2 con 0,000) coincide con `luna` `c3-000-h1`; el "después" es `terra`.

Por qué es grave: es el número que sostiene la contribución 1 en el resumen y en la conclusión,
y la comparación con §7.1 (l.1590-1595, que dice que las correcciones "tocan 3 de las 78 tareas"
de la campaña) le hace creer al lector que es la misma corrida. Además, una intervención
desarrollada en tres iteraciones sobre las 9 celdas en que se la mide no es evidencia de
transferencia; es un ajuste en muestra, sobre 3 tareas, en un modelo distinto al de la campaña.

Qué haría falta: exige medir. (a) Declarar el modelo de cada número de C3. (b) Correr
`pointer_chase` corregido sobre `luna` en las tres tareas C3 y reportar ese número, que es el
que corresponde a la campaña. (c) Retirar el "cero equivocadas" o restringirlo a `terra`.
(d) Generar tareas C3 nuevas (otra semilla) para medir la corrección fuera de las celdas donde se
la desarrolló. Sin (d), la afirmación de §7.2.6 punto 2 ("la evidencia es una intervención")
hay que rebajarla a "ajuste en muestra sobre tres tareas".

### O2. La definición de confinamiento no la cumple el algoritmo que la ilustra

Dónde: Definiciones 5.2 y 5.3 (l.777-788), Proposición 5.4 (l.789-798), Algoritmo 1
(l.1904-1918), §7.2.4 l.1940-1943, §7.2.6 l.2014-2020.

Qué dice el paper: la varianza está confinada si `d(T) = 0`, donde un nodo es delegado "si la
identidad de `nᵢ₊₁` es función de la salida del sensor" (l.778-779). Y presenta a
`pointer_chase` corregido como el caso en que "una decisión de flujo en el sensor se lleva
puesto el determinismo" y la corrección lo recupera.

Por qué está mal: en el Algoritmo 1, la línea 9 pide al sensor `ρ`, la línea 10 lo tipa, y la
línea 12 calcula `u ← primer_hit_que_nombra(buscar(ι, ρ, κ), ρ, camino)`. El nodo siguiente `u` es
función de `ρ`, que es salida del sensor. Por la Definición 5.2 eso es un punto de ramificación
delegado, uno por salto. `d(T) = n`, no `0`. La corrección (4) sacó el ancla del sensor (línea 4),
pero los `n` saltos siguen delegados. La Proposición 5.4 no aplica a este algoritmo y, por lo
tanto, la afirmación de que el motor "confina" la varianza de `pointer_chase` no está cubierta
por la teoría que el paper ofrece. Lo que el registro muestra es otra cosa, más interesante y no
formalizada: tipar la salida del sensor (línea 10) achica el dominio de la rama a un conjunto
finito verificable contra el índice, y eso baja la varianza sin eliminar la delegación. §7.2.6
lo intuye ("importa más cuál decisión se saca que cuántas", l.2014) pero la Definición 5.3 es
binaria y no puede expresarlo.

Qué haría falta: redacción y teoría, no medición. O bien se restringe la afirmación de
confinamiento a los brazos que de verdad tienen `d = 0` (ninguno de los que siguen cadenas), o
bien se reemplaza la Definición 5.3 por una graduada: rama delegada con dominio tipado y finito
(la salida del sensor se proyecta sobre un conjunto de candidatos computado desde el índice) contra
rama delegada con dominio abierto. La Proposición 5.4 pasaría a ser un caso límite. La
Definición 5.5 (l.809-814) tampoco es una proposición: no tiene enunciado preciso ni prueba, y
"acotado inferiormente por `pass@1` menos la varianza de extracción" no define ninguna cantidad.

### O3. El piso de ruido no depende del número de brazos, los rectángulos no se reproducen, y el titular en muestra es el panel que da negativo

Dónde: §7.3.3 l.2086-2113; §7.3.4 l.2141-2147; §7.7.1 l.2723-2727; recuadro de §7.2 l.1765-1778;
§7.3.1 l.2034-2040; §7.3.5 l.2179-2193; `bench/panel.py`.

Qué dice el paper: el piso de ruido es `+0,065` tanto para el panel de tres contendientes
(l.2091) como para el de ocho brazos (l.2141). El estimador descrito (l.2101-2104) toma las `k`
réplicas del mismo paradigma "como si fueran `k` paradigmas distintos". Y §7.7.1 afirma que el
piso "crece con la dispersión entre paradigmas y con cuántos compiten" (l.2725-2726).

Por qué es débil: las dos afirmaciones son incompatibles. Un estimador que maximiza sobre 3
réplicas no puede ser el mismo piso para un máximo sobre 3 brazos y para un máximo sobre 8. Si
§7.7.1 tiene razón, el `0,065` es demasiado bajo para el panel de 8, y el neto `+0,045` de
l.2146 está inflado (a favor del paper, casualmente, es el neto que el paper descarta por otra
vía). Si el estimador de §7.3.3 tiene razón, la explicación de §7.7.1 sobre por qué el piso no
baja con `n` es falsa. Además, el titular "premio neto `−0,008` en muestra" (l.229, l.2092, l.3230)
es el panel de tres contendientes; el mismo registro sobre ocho brazos da `+0,110 − 0,065 =
+0,045` (l.2146), positivo. El paper lo desestima con "no hay señal que lo prediga", que es un
argumento distinto del que usa para el `−0,008`. El resumen y la conclusión eligen el panel que
da negativo.

Sobre los rectángulos: el recuadro de §7.2 (l.1773) define el panel 59 × 8 como "rectángulo con
≥3 réplicas". Recomputé: las 64 tareas del rectángulo 64 × 8 tienen 3 réplicas en los 8 brazos
(la distribución de réplicas por celda factible es 609 con 3, 4 con 2, 3 con 1). El criterio
declarado da 64, no 59. Apliqué la regla de `bench/panel.py` (`MIN_BRAZOS = 7`,
`COBERTURA_MINIMA = 0,95`) al registro actual: 67 tareas ricas, 8 brazos, 64 tareas en el
rectángulo. El docstring de `panel.py` dice "hoy son 41 de 78 tareas". Así que el paper reporta
tres rectángulos (64 × 8, 59 × 8, 41 × 7) que atribuye a una regla "en un solo lugar del código"
(l.2036), y sobre el registro vigente esa regla produce uno solo. Los otros dos son snapshots
anteriores del registro, y el paper no dice cuáles.

Sobre §7.2.1 y §7.2.5: declaran el panel 64 × 8 y dan `supervisor = 0,577`, `rewoo = 0,677`.
Recomputado sobre el 64 × 8 actual: `supervisor = 0,587`, `rewoo = 0,688`, que son los valores
que la propia tabla de §7.2.6 usa (l.1995, l.1999). Dos secciones del mismo panel con dos
valores.

Qué haría falta: exige recomputar, no correr. (a) Un piso de ruido por panel, con un nulo que
respete el número de brazos (por ejemplo, permutar etiquetas de réplica dentro de tarea y tomar
el máximo sobre el mismo número de brazos del panel). (b) Fijar un snapshot del registro por
panel y declararlo (hash o fecha del archivo). (c) Reportar en el resumen el neto del panel de
ocho brazos junto con el de tres, y explicar por qué se descarta el positivo.

### O4. La contribución 2 se enuncia como resultado y su evidencia es sugestiva, contra un baseline débil, con un modelo no especificado

Dónde: resumen l.99-108; §7.4.1 l.2340-2369; §7.4.2 l.2378-2385; §7.4.3 l.2415-2427;
`results/eda_capacidades.json`; §8.2 l.3106-3109.

Qué dice el paper: las capacidades declaradas "predicen un paradigma nunca visto mejor que la
identidad del paradigma, incluso cuando a ésta se le permite ver la respuesta" (l.101-103), y la
ontología "separa a los brazos 40% más por segmento" (l.107).

Por qué es débil:

- El nulo de capacidades barajadas no se cruza: `p = 0,065`, `MAE 0,2327` contra `p5 0,2299`
  (l.2379-2381, verificado en `eda_capacidades.json`). El paper lo admite en §7.4.2 y §8.2, pero
  el resumen lo enuncia como propiedad ("predicen... mejor que la identidad").
- El baseline "identidad viendo al brazo dejado afuera" (`0,339`) ignora la dificultad de la
  tarea, que es el 41% de la varianza. El paper mismo lo dice (l.2366-2367: "sale peor que
  capacidades pese a hacer trampa, porque ignora α"). Un baseline que ignora el predictor
  principal no es una comparación; es un hombre de paja. La comparación honesta es contra
  `α + identidad`, y no está.
- La ganancia real contra "dificultad de la tarea sola" es `0,257 → 0,233`, sobre 8 puntos, y
  pierde en 2 de los 8 pliegues.
- El modelo de capacidades no está especificado. Son 10 predicados booleanos (más α) ajustados
  sobre 7 brazos por pliegue. Sin regularización el sistema está sobreparametrizado; con
  regularización hay un hiperparámetro que no se declara. `eda_capacidades.json` no lo dice.
- §7.4.3: la "ganancia por segmento" es `(S/R − 1) / n_segmentos` (verificado: `0,74/5 = 0,148`,
  `0,84/8 = 0,105`, `0,04/3 = 0,013`). Dividir por `n` y no por `n − 1` es una elección sin
  justificar: con `n − 1` la ventaja de la ontología es 54%, no 40%. Y la fila "ontología por
  celda" (11 segmentos, `S/R 1,92`) no tiene ganancia reportada; con la misma fórmula da `0,084`,
  por debajo de la región estructural (`0,105`). La celda queda en blanco justo donde la métrica
  del paper le da la contra.

Qué haría falta: redacción en el resumen (rebajar a "sugestivo, no cruza su nulo con n = 8",
que es lo que dice §7.4.2). Especificar el modelo y el ajuste. Agregar el baseline
`α + identidad`. Reemplazar la corrección por número de segmentos por un nulo por permutación
con el mismo número de segmentos. Completar la fila en blanco. Y medir: más brazos, como el
propio paper dice en §9.1.

### O5. La contribución 3 dice en el resumen lo que su tabla desmiente, y omite el veredicto de P17

Dónde: resumen l.109-117; §7.8.4 tabla l.2883-2889 y l.2891-2892; §9 l.3218; §7.8.2 l.2854-2860;
`results/nano/p17_verdict.json`.

Qué dice el paper: "Tres refutaciones preregistradas... cada una produjo un sensor nuevo,
computado y sin modelo: el eje de horizonte, el de literal, la ontología" (l.109-111). La
conclusión: "tres ejes nuevos (horizonte, literal, ontología), decisión reproducida 26/26 en
cada uno" (l.3218). §7.8.4: "Cada sensor nuevo es `COMPUTED`... la Proposición 5.7 (1) respetada
tres veces" (l.2891-2892).

Por qué está mal, según la tabla del mismo paper (l.2883-2889):

- `P16` produjo "costo de la escalera cobrado; detector separado del gold", procedencia "—". Es
  una corrección de valuación, no un sensor.
- `P17` produjo "corpus con detector declarado por tarea". Es un corpus, no un sensor.
- El literal está en la fila "vocabulario vigente", no salió de una refutación (§7.8.3 dice que
  "no se eligió; se midió contra el anterior"), y su decisión reproducida figura como "—".
- La ontología figura con "dos ejes `COMPUTED`, el resto `ELICITED`" y reproducción "—". No es un
  sensor `COMPUTED`.

De los tres sensores del resumen, uno (continuidad) cumple lo que se dice de él. El "26/26 en
cada uno" de la conclusión vale para P15, P16 y P17, que son las tres refutaciones, y no para
literal ni ontología, que son los otros dos "ejes nuevos" de la misma frase.

Además, §7.8.2 relata P17 sin su número. `p17_verdict.json`: `P17c` REFUTADA, neto contra el
mejor fijo `−1,0425` a λ = 0,05 y `−0,1464` a λ = 0; contra siempre-`react`, `0,000` a λ = 0 porque
20 de 22 tareas terminan en el fallback. El paper dice "la decisión honesta fue diferir"
(l.2858-2859) y no dice que a λ = 0 el ruteador perdió `0,146` contra el mejor fijo. Es el único
de los tres episodios cuyo neto no está en el texto.

Y la agencia: el paper ya declara que el ciclo lo ejecutaron personas (l.112-114, l.2775-2781,
l.3142-3154). Bien. Pero el título de la contribución sigue siendo "el ciclo que repara su propio
vocabulario" (l.109, l.2766). "Su propio" dice lo que §8.3 niega.

Qué haría falta: redacción. Reescribir la contribución 3 con la tabla de §7.8.4 delante: una
refutación produjo un sensor `COMPUTED` (continuidad); dos produjeron correcciones de método
(valuación, corpus); un eje (literal) salió de una medición comparativa; la ontología es una
hipótesis mayormente `ELICITED`. Agregar el neto de P17 en §7.8.2. Cambiar el título de la
contribución.

---

## 3. Inconsistencias internas

Numeración por línea del archivo actual. Donde verifiqué contra el registro, digo qué dio.

Conteos de la campaña:

1. l.283-284, l.1529-1530: "78 tareas × 12 paradigmas × 3 réplicas". Registro: 67 tareas se
   ofrecieron a 12 paradigmas y 11 tareas sólo a 3 (`rewoo`, `handoff`, `graph_traverse`):
   `b2-001-w4`, `b2-002-w4`, `c2-002-w4`, `c3-002-h3`, `c4-002-w4`, `c5-002-w4`, `c8-002-w4`,
   `c9-002-w4`, `d1-001-w4`, `d1-002-w4`, `w1-002-pos`. Por eso 2.511 filas y no 2.808. La
   campaña no es homogénea en el sentido de la frase; es 67 × 12 más 11 × 3.
2. l.284, l.1530: "121,4M tokens". Suma de `cost_tokens` sobre las 2.511 filas: 123.263.836.
3. l.2694 "927 filas" contra l.2754 "932 celdas" contra el archivo `gold_holdout_rows.jsonl`:
   936 filas (26 × 12 × 3), 282 infactibles, 48.502.438 tokens, cero `infra_error`. Los tres
   números del paper difieren entre sí y del archivo.
4. l.2570-2572: "23 tareas × 8 brazos × 1 réplica, 209 celdas" y "374 filas contra las 3.519 de
   la familia principal". Bitácora l.1641-1651: las 209 celdas factibles son sobre los 12 brazos
   que corrieron, filtradas a 8 al analizar. Las 374 filas son 350 de `gold_h1` más 24 de
   `gold_p18`, otro corpus. Las 3.519 son la suma de los cuatro `.jsonl` de `results/luna`
   (2.511 + 936 + 63 + 9), es decir, incluye el held-out y dos experimentos laterales. "Familia
   principal" es un rótulo que no corresponde a esa suma.
5. l.1773: "59 × 8 (rectángulo con ≥3 réplicas)". Ver O3: el criterio produce 64.
6. l.2035: 59 tareas "es el 76% de las 78 medidas", y l.1562 "64 tareas × 8 brazos (el 82%)", y
   `panel.py` "hoy son 41 de 78". Tres rectángulos, una regla declarada, un registro. Ver O3.
7. l.1790-1793 y l.1965-1968 (`supervisor 0,577`, `rewoo 0,677`) contra l.1995 y l.1999
   (`supervisor 0,587`, `rewoo 0,688`) para el mismo panel 64 × 8. Recomputado: 0,587 y 0,688.
8. l.1989 "sobre los ocho brazos del panel" y l.2002 "`r = −0,24` con `n = 8`": la tabla de
   l.1992-2000 tiene siete filas, falta `handoff`.

Modelos mezclados o sin declarar:

9. Todo lo de O1: C3 (`0,33 → 0,89`, `12/3/0`) es `terra` o `terra + luna`, y el paper lo
   presenta como campaña `luna`.
10. l.1119-1129 (tabla del dial: 5 brazos, `u 0,6101`, `0,4221`), repetida en el resumen
    (l.97-98) y la conclusión (l.3216). Fuente: `bench/analysis/_analyze_ratchet_cost.py`, l.64
    `raiz = Path("results/nano")`. Es un número de `nano`, sobre un catálogo de 5 brazos que no
    coincide con el plantel de 12, y ni el corpus ni el modelo ni cuáles son los 5 están
    declarados. §8.1 (l.3048-3056) enumera lo que corre sobre `nano` y no lo incluye.
11. l.878-879: "un brazo es el más barato al empatar en 46 de 96 celdas". Panel no declarado. El
    único con 96 celdas no es ninguno de los de §7.
12. l.1474-1476: "516 filas dan 141 episodios sobre 6 regiones". Registro no declarado. El
    registro actual tiene 14 regiones (contado sobre el campo `region`).

Referencias cruzadas rotas y texto heredado:

13. l.3022-3028 (§8.1): "el corpus detrás de §7.1–7.3 tiene 16k tokens en su punto más ancho".
    Contradice l.2620 (455.476 tokens en una tarea de banda ancha) y l.2753 (material medio 451k
    en `w48`). "Medido a 483k con `repeat = 3` (§7.4–7.5)": §7.4 son capacidades y §7.5 es
    consenso. "Marcadas † en §7.4": no hay ningún † en el paper. Es texto de una versión anterior
    donde esas secciones eran otras.
14. l.3030-3038 (§8.1): "La réplica accidental del primer estudio (§7.3) y el `repeat = 3` del
    segundo", "pendiente de las celdas en re-corrida", `Study.noise_floor`. Contradice l.283-284
    ("campaña homogénea... cero errores") y l.1516-1517. Texto heredado.
15. l.3077-3082 (§8.2): párrafo sobre P8 que menciona "los veredictos por celda de más abajo"
    (no hay ninguno debajo), "mundos seed-7" (no aparece en otro lado) y "el fallback general
    devuelve 0,667 y 0,000" sin contexto. La bitácora l.626-672 tiene el veredicto completo; el
    párrafo del paper es un resto.
16. l.3140: "el resultado del blackboard en §7.7, y es un nulo". §7.7 es el held-out. El pizarrón
    ofrecido como herramienta ("llamado 1 vez en 125") está en l.2973-2974, en §7.9.2.
17. l.365 "ReDAct" contra l.3370 "eDAct", mismo arXiv 2604.07036.
18. Figuras: sólo tres tienen número (Figura 1 l.143, Figura 15 l.2259, Figura 16 l.2878). Las
    otras catorce no tienen numeración ni leyenda formal. Los números 2 a 14 no existen.

Afirmaciones del resumen que el cuerpo sostiene con otro número o no sostiene:

19. l.94-97 "absorber ramificaciones... haciendo coincidir sus réplicas" contra l.1950-1951 "la
    réplica que todavía falla se abstiene". Después de la corrección `pointer_chase` da 8 de 9
    (`terra`), no 9 de 9. Las réplicas no coinciden.
20. l.51-53 "predice la corrección con precisión total a partir de cuatro coincidencias" contra
    l.2473 "lo afirmable es ≥ 0,98". El resumen usa el punto, el cuerpo usa la cota.
21. l.196-198 "los demás contestan siempre y devuelven un número plausible y falso" contra el
    registro `luna` de C3: los 5 ceros de `pointer_chase` son abstenciones (`'Not available…'`,
    `'Not provided'`, `'Cannot be determined…'`) y 6 de los 9 ceros de `rewoo` también. Los
    demás también se abstienen; `dag_strategy` no es el único.
22. l.101-103 "predicen un paradigma nunca visto mejor que la identidad del paradigma" contra
    l.2384 "queda como resultado sugestivo y no establecido". Ver O4.
23. l.109-111 contra l.2883-2889. Ver O5.
24. l.317 "Fuera de alcance: un selector validado" contra l.2179 "ésa es la superficie donde la
    política aprendida sí paga, y transfiere" y l.2190-2192. Si el desempate por costo aprendido
    transfiere fuera de muestra, hay un selector validado sobre costo. O el alcance está mal o
    §7.3.5 afirma de más.
25. l.2186-2187: política con literal `0,951` contra mejor fijo `0,930`. Eso es `+0,021` por
    encima del mejor fijo, sin intervalo, sin piso, con 14 regiones sobre 41 tareas (2,9 por
    región, l.2192-2193). El resumen lo reporta como "a +0,021" y l.239-240 como "utilidad
    indistinguible del mejor fijo". Indistinguible respecto de qué ruido, no se dice.

Términos con dos sentidos y conteos que no cierran:

26. Ejes del vocabulario de región: l.2297 "cinco ejes. Cuatro son `COMPUTED`"; l.2280 "cuatro
    ejes computados más el literal"; l.2430 "los seis campos computables del vocabulario de
    región". Registro: la clave `region` tiene 5 componentes en las 14 regiones. Cuatro, cinco o
    seis según la sección.
27. "Celda": l.1509 la define como tarea × paradigma; l.1618, l.1867, l.2279 y l.2389 la usan como
    modo del corpus ("celda de cadenas acopladas", "celda del corpus"). Dos sentidos en la misma
    sección.
28. l.1024 "mueve la cascada de disparar en 22 de 26 tareas a disparar en 2" contra l.2855-2858
    "precede a la selección en 20 de 22 tareas (§5.2)" y "bajó de 22 a 2 de 26". Son dos corpus
    (`gold_p16` bajo P16: 20 de 22 de la cohorte; `gold_p17` bajo el régimen de P16: 22 de 26) y
    el texto los presenta como el mismo número.
29. l.2429 y l.299 tratan "vigencia" como modo medido del corpus (C8_currency tiene 297 filas
    en el registro). l.3247-3250 (§9.1) dice "La celda de vigencia... ninguna pregunta las
    interroga" y la pone como trabajo futuro con "treinta y dos tareas". O es otra celda, y
    entonces le falta nombre, o la afirmación de §9.1 está mal.
30. l.2405-2407 lista "contradicción" como eje de la ontología y l.2426 le atribuye `S/R = 1,82`
    con partición binaria; los once modos de l.298-301 no incluyen contradicción. No se dice de
    qué modo del corpus sale el eje.
31. "P29" rotula dos predicciones distintas en la bitácora (l.1456 board/guard, l.1595
    consenso). El paper cita P29 para el consenso (l.2568). Hay que desambiguar en el paper o en
    la bitácora.
32. Título: "Policy-as-Code" aparece en el cuerpo sólo en l.1376-1379, como "una realización
    posible de esa tabla, y no es la que este trabajo corre". El título nombra algo que el paper
    dice no correr.
33. l.3129-3130 "Seis tareas de setenta y ocho llevan `irreversible = True` y tres llevan
    `shared_writes = True`". Las filas del registro no traen esas banderas. Los conteos por
    celda son consistentes (C7: 216 filas = 6 × 12 × 3; W1: 81 filas = 3 × 9 × 3), pero W1 corrió
    sólo 9 paradigmas y eso no se dice.

---

## 4. Originalidad

Lo que el paper ya cede está bien cedido (§2.4, §2.9, §2.10, §2.11). Lo que falta ceder, con
referencia:

Sobre "el modelo es un sensor, la decisión es simbólica y computada":

- SayCan (Ahn et al., 2022, arXiv:2204.01691): el LLM propone, una función de affordance
  computada desde el entorno filtra. Es exactamente "proposición elicitada, compuerta computada"
  sobre acciones, cuatro años antes.
- LLM+P (Liu et al., 2023, arXiv:2304.11477): el modelo traduce a PDDL y un planificador clásico
  decide. Modelo como traductor, control en el símbolo.
- CoALA (Sumers et al., 2023, arXiv:2309.02427): arquitecturas cognitivas para agentes de
  lenguaje, con el linaje Soar/ACT-R que §2.9 y §6.3.1 reclaman como propio ("consolidar
  episodios en reglas ejecutables es lo que hicieron con chunking"). CoALA ya hizo ese puente.
- NeMo Guardrails (Rebedea et al., 2023, arXiv:2310.10501) con Colang, y LMQL (Beurer-Kellner et
  al., 2023): flujo de control determinista en código alrededor del modelo, con salida tipada.
  Es el antecedente de ingeniería de "el flujo de control vive en el código" junto con DSPy, y
  de "se tipa la salida del sensor antes de usarla" (l.1913).
- Guardas de acciones en runtime: AgentSpec (Wang et al., 2025, arXiv:2503.18666), GuardAgent
  (Xiang et al., 2024). Pisos deterministas sobre acciones de agentes, anteriores a
  ProvenanceGuard.

Sobre selección de paradigma por request en RAG, que §2.2 y §2.10 dicen que nadie hace:

- Adaptive-RAG (Jeong et al., 2024, NAACL, arXiv:2403.14403): un clasificador de complejidad
  rutea cada consulta entre no recuperar, RAG de un paso y RAG multi-paso. Es ruteo entre
  paradigmas de recuperación por request. La afirmación "ninguno de los tres rutea entre
  paradigmas" (l.554-555) y "nadie aplica abstención a la selección de paradigmas" (l.370) hay
  que enunciarlas con este vecino delante.
- Self-RAG (Asai et al., 2023, arXiv:2310.11511) y FLARE (Jiang et al., 2023): decidir cuándo
  recuperar y cuándo abstenerse, adaptativo por request.
- Self-Route (Li et al., 2024, arXiv:2407.16833): rutea entre RAG y ventana larga por
  auto-reflexión del modelo. Es la comparación de §7.6 hecha y medida, con la lección de que el
  selector elicitado funciona en ese caso.
- AutoMix (Aggarwal et al., 2023, arXiv:2310.12963): cascada con auto-verificación como detector.
  Falta junto a FrugalGPT en §5.2.

Sobre predicción selectiva:

- El-Yaniv y Wiener (2010, JMLR), Geifman y El-Yaniv (2017), Geifman, Uziel y El-Yaniv (2019):
  curva riesgo-cobertura y AURC. El paper usa AURC (l.965) sin citar de dónde sale.
- Madras, Pitassi y Zemel (2018, "Predict Responsibly"): aprender a diferir, anterior a
  Mozannar y Sontag.
- "Mohri y colegas" (l.427-428) sin referencia: Mao, Mohri y Zhong (2023-2024), aprender a
  diferir con múltiples expertos. Verma, Barrejón y Nalisnick (2023, AISTATS) para el caso
  multi-experto también.
- Wen et al. (2024, arXiv:2407.18418), survey de abstención en LLMs: para §1.1 propiedad 3.

Sobre no-determinismo a temperatura cero, el fenómeno de §7.2.2 y el confundente de §8.2:

- Ouyang et al. (2023, arXiv:2308.02828) y Atil et al. (2024, arXiv:2408.04667) miden exactamente
  la inestabilidad entre corridas a `t = 0`. "Defeating Nondeterminism in LLM Inference" (He,
  Thinking Machines, 2025) explica la fuente (invariancia por lote) que §8.2 l.3084-3091 describe
  sin nombre. Bouthillier et al. (2021, "Accounting for variance in machine learning
  benchmarks") para la disciplina de reportar varianza entre semillas, que es lo que `pass^k` y
  el piso por celda hacen.

Sobre métricas y estadística:

- `pass^k` lo introdujo τ-bench (Yao et al., 2024, arXiv:2406.12045). El paper se lo atribuye a
  tau2-bench (l.1812-1813, l.3377). Está mal atribuido.
- El "máximo de los nueve nulos en cada permutación" (l.2067-2068) es el procedimiento maxT de
  Westfall y Young (1993). Tiene nombre y hay que dárselo.

Sobre los paradigmas del plantel: ReAct (Yao et al., 2022, arXiv:2210.03629), Reflexion (Shinn et
al., 2023, arXiv:2303.11366) y ReWOO (Xu et al., 2023, arXiv:2305.18323) no están citados en
ninguna parte. El paper mide doce estructuras de control y no cita el origen de las tres que
gobiernan sus resultados.

Sobre aprender política de control desde episodios propios hacia un artefacto ejecutable (§6.3):
Voyager (Wang et al., 2023, arXiv:2305.16291) consolida habilidades como código ejecutable
desde la experiencia propia; Agent Workflow Memory (Wang et al., 2024, arXiv:2409.07429) induce
flujos reutilizables desde trayectorias. Los dos son vecinos de la conjunción de l.448-451 y no
están en §2.6.

Lo que queda de verdad:

- La medición. Doce estructuras de control bajo condiciones idénticas, sin juez, con réplicas,
  piso de ruido por sesgo del máximo, corrección por selección y held-out con el mismo código.
  Ese registro y su disciplina son la contribución, y no dependen de que ninguna idea sea nueva.
- El resultado negativo con mecanismo: la interacción tarea × paradigma es grande y vive entre
  brazos dominados; entre los que compiten no hay premio de calidad. Enunciado así, con el piso
  de ruido delante, es útil y no lo vi publicado en esa forma.
- La distinción `COMPUTED` / `ELICITED` aplicada a la clave de la política (§5.7, §7.3.6), con la
  medición de que el eje elicitado cambia en 27% de las tareas entre modelos. Es una observación
  simple con consecuencia de diseño clara. Sigue en pie aunque la Proposición 5.7 sea una
  tautología.
- El consenso entre estructuras heterogéneas como curva de calibración que se reproduce en otra
  familia con criterio registrado antes, y la decisión de que mueva credencia y no procedencia.
  La idea es Self-Consistency; la disciplina epistémica alrededor es del paper.
- El catálogo de capacidades declaradas desde el código con leave-one-arm-out. La idea está
  cerca de las affordances de SayCan y de las tarjetas A2A; la auditoría contra el código y la
  predicción del hueco (ausencia sin brazo capaz) es lo propio. Hoy es una hipótesis con
  `p = 0,065`.

---

## 5. Claridad y estructura

Orden que confunde:

- El paper tiene dos tesis y no elige. El título habla de policy-as-code y gobernanza
  determinista; el subtítulo de confinamiento de varianza; el prefacio (l.15-22) dice que la
  "columna vertebral" es un sistema que aprende; §7.3 dice que el resultado que "reordenó el
  programa" es un negativo sobre ruteo. Un lector externo llega a §7 sin saber qué se le va a
  demostrar. La sección "Cómo se decide un request" (l.151-172), sin número, aparece entre el
  resumen y la introducción y repite la Figura 1 con otras palabras.
- §5 contiene siete subsecciones con rótulo de teorema para lo que el propio texto llama
  "identidades, construcciones y monotonías" (l.764-767). Teorema 1 es una descomposición
  contable exacta. Teorema 2 es correcto por construcción de una función de tres guardas.
  Proposición 4 es que una secuencia monótona en un conjunto finito cambia finitas veces.
  Proposición 6 ("`max` es la única composición") no tiene prueba y no es cierta sin más
  hipótesis. Proposición 5.7 es composición de funciones. Presentarlos como teoría le quita
  espacio a lo que sí necesita formalización (O2) y le da al lector la sensación de que se
  demostró algo que no se demostró. Reducir §5 a dos páginas con las definiciones y la
  Proposición 5.7 sería una mejora, y mover el Teorema 1 a un apéndice.
- §7 pone la varianza (§7.2) antes que el negativo de ruteo (§7.3) que "reordenó el programa",
  y el ciclo (§7.8) después del held-out (§7.7) aunque §7.8 sea anterior en el tiempo y corra
  sobre otro modelo. El "Puente" de l.2760-2764 lo intenta arreglar en prosa. El orden
  cronológico y por modelo (primero `nano`: §7.8, §7.9.1; después `luna`: el resto) sería más
  honesto y más fácil de seguir.

Redundancias:

- §7.1 y §7.1.1 son la misma tabla dos veces (l.1540-1553 y l.1599-1612), con el mismo texto
  sobre `direct` (l.1570-1573 y l.1616-1620).
- §6.2 (l.1285-1349) y §5.4/§5.5 dicen tres veces lo mismo sobre el ratchet: monótono, tope en
  ACCOUNTABLE, nunca baja solo.
- §6.3, §6.3.1 y §6.3.2 repiten "offline, firmado, versionado, ejecutado como código" en cada
  párrafo.
- §7.5.4 y §7.5.5 repiten el argumento de por qué se compara sobre el mismo plantel.
- El recuadro sobre el piso de ruido (l.2095-2113) y §7.7.1 (l.2723-2731) explican el mismo
  estimador con explicaciones incompatibles (ver O3).
- La frase "una clave de política tiene que ser `COMPUTED`" aparece en l.127-128, l.529-531,
  l.2218-2220, l.3221-3222, y en §5.7. Cuatro veces alcanza; cinco no agregan.

Longitud: 3.389 líneas para cuatro contribuciones de las cuales una está sostenida (la
medición), una es sugestiva (capacidades), una está sobreenunciada (ciclo) y una tiene el número
de otro modelo (C3). Con las redundancias de arriba y §5 comprimido, el paper baja a la mitad
sin perder un dato.

Lo que le falta a un lector que no conoce el laboratorio:

- Qué es una "tarea" con ejemplo. Hay uno solo (l.3131-3132, la de escalación). Una tabla con
  una pregunta por modo, su oráculo y su tamaño de material valdría más que §1.3.1 entero.
- Qué hace cada paradigma. Doce nombres, una tabla de ley de costo (l.618-622) y una frase por
  cada uno de los siete "que entran contra un modo de falla" (l.623-629). `gist_reader`,
  `pointer_chase`, `graph_traverse`, `streaming_scan`, `extract_compute` no tienen descripción
  operativa ni cita.
- Cómo se ajusta la política θ. §6.3 describe propiedades (offline, copy-on-write, orden de
  sorpresa) y ninguna ecuación ni pseudocódigo. "Consolidación" nunca se define operacionalmente.
  Se sabe que es una tabla; no se sabe cómo se llena una fila.
- Cómo se calcula el modelo de capacidades de §7.4.1 (ver O4).
- Qué es la "sonda" (l.1232, l.2858-2860). Aparece como acción de la política y como mecanismo
  de P17 sin haberse definido.
- El glosario de `COMPUTED` / `OBSERVED` / `ELICITED` / `ASSUMED` llega en l.1299-1301, después de
  usarse en el resumen, §2, §5.5 y §5.7.
- Los identificadores arXiv de 2026 no se pueden verificar desde acá. Están fechados, que es lo
  correcto. Uno (2606.31422) tiene un número de secuencia alto para un mes; conviene chequearlo.

---

## 6. Diez preguntas para la rebuttal

1. Los números de C3 (`0,89` de `dag_strategy` y de `pointer_chase`, "12 correctas, 3
   abstenciones") ¿sobre qué modelo se midieron? El archivo de `luna` da `0,667` y `0,167`
   sobre 6 celdas; el de `terra` da `0,889` y `0,889` sobre 9. Si son `terra` o un pool, ¿por qué
   §8.1 afirma que ninguna estadística mezcla modelos?
2. Los backups de `terra` muestran `pointer_chase` en C3 con `0,333`, `0,000`, `0,000` y `0,889` en
   cuatro estados sucesivos del mismo día. ¿Cuántas iteraciones de la corrección se probaron
   sobre esas 9 celdas antes de fijar la que se reporta, y cuál fue el criterio de parada?
3. Por la Definición 5.2, la línea 12 del Algoritmo 1 hace que el nodo siguiente sea función de
   la salida del sensor. ¿Cuál es el `d(T)` de `pointer_chase` corregido, y si es `n`, qué
   proposición cubre la afirmación de que el motor "confina" su varianza?
4. ¿Cómo puede ser `0,065` el piso de ruido del panel de tres contendientes y también el del
   panel de ocho brazos, si §7.7.1 afirma que el piso crece con cuántos compiten? ¿Cuál de las dos
   descripciones del estimador es la que corre en `app/metrics.py`?
5. ¿Qué snapshot del registro produjo el rectángulo 59 × 8 y cuál el 41 × 7? Sobre el archivo
   actual la regla de `panel.py` da 64 × 8. ¿Se puede publicar un hash por panel?
6. El modelo de capacidades de §7.4.1: ¿qué forma funcional, con qué regularización, y cómo se
   ajustan 10 booleanos más α sobre 7 brazos de entrenamiento? ¿Cuál es el MAE de `α +
   identidad`, el baseline que falta?
7. En §7.4.3, ¿por qué la ganancia por segmento se normaliza por `n` y no por `n − 1`, y por qué
   la fila "ontología por celda" no tiene ganancia si con la misma fórmula da `0,084`, por debajo
   de la región estructural?
8. La tabla de §7.8.4 dice que P16 produjo una corrección de valuación y P17 un corpus, que el
   literal no salió de una refutación, y que la ontología es mayormente `ELICITED`. ¿Cómo se
   sostiene entonces "cada una produjo un sensor nuevo, computado y sin modelo: horizonte,
   literal, ontología" en el resumen?
9. El neto de P17 (`−1,04` a λ = 0,05, `−0,146` a λ = 0 contra el mejor fijo, según
   `p17_verdict.json`) no está en §7.8.2. ¿Por qué es el único episodio sin su número?
10. La tabla del dial (5 brazos, `u 0,6101 → 0,4221`) sale de `_analyze_ratchet_cost.py` sobre
    `results/nano`. ¿Sobre qué corpus, con qué 5 brazos, y por qué el resumen y la conclusión lo
    reportan como costo de la máquina sin declarar que es `nano` sobre otro catálogo?

---

## 7. Puntaje

| dimensión | puntaje | fundamento en una línea |
|---|---:|---|
| Contribución (25%) | 3 | el registro y el negativo con mecanismo valen; los cuatro titulares tienen cada uno un defecto de sustento (O1, O3, O4, O5) |
| Teoría (20%) | 2 | identidades y construcciones rotuladas como teoremas; la única definición con contenido (5.3) no cubre el caso que ilustra (O2); Prop. 6 sin prueba; Def. 5.5 no es un enunciado |
| Literatura (15%) | 3 | linaje clásico bien hecho y cesiones honestas; faltan SayCan, LLM+P, CoALA, Adaptive-RAG, Self-Route, la literatura de no-determinismo, El-Yaniv, los papers de los propios paradigmas; `pass^k` mal atribuido |
| Metodología (20%) | 2 | preregistro y piso de ruido son un mérito real; modelos mezclados sin declarar, corrección iterada sobre sus celdas de prueba, piso que no depende del número de brazos, rectángulos no reproducibles, modelo de capacidades sin especificar |
| Argumentación (10%) | 3 | el argumento central (interacción grande entre dominados, sin premio entre contendientes) está bien construido; el resumen elige el panel que da negativo y omite el que da positivo |
| Reflexión crítica (10%) | 4 | §8.3 sobre la agencia del ciclo, §7.4.2 sobre el nulo, §5.2 sobre la conflación gold/detector y §7.3.6 son autocríticas genuinas; le resta que §8.1 y §8.2 tengan texto heredado que contradice a §7 |

Promedio ponderado: `0,25 × 3 + 0,20 × 2 + 0,15 × 3 + 0,20 × 2 + 0,10 × 3 + 0,10 × 4 = 2,70`
sobre 5.

Revisión mayor. Lo que exige medir: O1 (`pointer_chase` corregido sobre `luna`, y celdas C3
nuevas), O3 (piso por panel con nulo emparejado por número de brazos), O4 (más brazos, ya
declarado en §9.1). Lo que se arregla con redacción: O2 (redefinir o restringir el
confinamiento), O5 (reescribir la contribución 3 contra su tabla), las 33 inconsistencias de §3,
y los párrafos heredados de §8. Si se hace lo segundo y se declara con claridad lo que hoy es
`terra`, `nano` y `luna` en cada número, el paper queda como un estudio de medición sólido con
un resultado negativo bien sostenido y tres hipótesis registradas. Eso es publicable. Lo que
está escrito hoy en el resumen no lo es.
