# Revisión B (metodología y estadística), paper-es.md borrador 3.0

Revisor: metodólogo externo, lectura fresca del paper completo (3.389 líneas) antes de abrir el laboratorio.
Fecha: 2026-09-01.
Material verificado: `lab/results/luna/gold_h1_rows.jsonl` (2.511 filas), `lab/results/luna/gold_holdout_rows.jsonl` (936 filas), `lab/results/terra/gold_h1_rows.jsonl` (350 filas), `lab/results/nano/{p15,p16,p17}_verdict.json`, `retention.json`, `statistics.json`, `lab/app/metrics.py`, `lab/bench/panel.py`, `lab/bench/fiabilidad.py`, y corridas de `_eda_capacidades.py`, `_consenso.py`, `_predictores.py`, `_plasticidad.py` más scripts propios en el scratchpad. No modifiqué nada del repo.

---

## 1. Veredicto en diez líneas

1. El registro es real, está completo, y la mayoría de las tablas descriptivas reproducen al tercer decimal (plantel §7.1, pass^3 de §7.1, curva de consenso §7.5.1 con sus controles, leave-one-arm-out §7.4.1 y su nulo, veredictos P15 a P17, estadísticas de P15). Eso es raro y vale.
2. El resultado central negativo del paper (PI2, "brecha neta negativa" en §7.3.3 y §7.7.1) descansa en un estimador de piso de ruido que no es el que el paper describe. El código computa la distribución bootstrap del propio estadístico de brecha (remuestrea las réplicas de cada celda real y recalcula oráculo menos mejor fijo), no un nulo sin interacción. Ese "piso" iguala o supera a la brecha observada por construcción, con cualquier dato. Lo reproduje: da exactamente 0,065 en §7.3.3 y 0,167 / 0,185 / 0,162 en el held-out.
3. Con el estimador que el paper sí describe en la caja de §7.3.3 (réplicas del mismo paradigma como pseudo-brazos, `metrics.noise_floor`), el piso del held-out es 0,071 a 0,073 y la brecha neta pasa a +0,057 / +0,096 / +0,066 en los tres estratos. El veredicto held-out cambia de signo. En muestra, para los tres contendientes, el neto queda en −0,018 (sigue negativo).
4. En un dataset sintético con premio real de +0,50, el estimador usado por el paper devuelve neto +0,005. Un estimador que no detecta un premio de medio punto no puede sostener un veredicto negativo.
5. La afirmación "capacidades superan a la identidad del paradigma incluso cuando ésta ve la respuesta" (Resumen, §7.4.1, §9) compara un modelo con dificultad de tarea contra uno sin ella. Con la misma dificultad de tarea, la identidad que ve al brazo da MAE 0,225 y las capacidades 0,233. La comparación no es justa y la afirmación cae.
6. El panel "59 × 8, rectángulo con ≥3 réplicas" de §7.2.2 y §7.3 no existe como tal: las 64 tareas del rectángulo tienen tres réplicas en los ocho brazos. Las 59 salen de una lista de cinco tareas excluidas a mano (`CONTAMINADAS` en `_predictores.py`) que el paper no declara.
7. La campaña no es 78 × 12 × 3. Nueve de los doce brazos corrieron 67 tareas. Son 2.511 filas y 123,3M tokens, no 2.808 y 121,4M.
8. Varias tablas quedaron congeladas antes del re-puntuado del 2026-08-30 y ya no corresponden al registro: P30 reporta u = 0,540 y el registro da 0,822 / 0,825; la tabla S/R de §7.4.3 salió de un registro de 46 tareas; la política de 41 × 7 de §7.3.5 no la reproduce ningún script del repo, y el que existe (`_plasticidad.py`) da una pérdida de utilidad significativa para la clave computada (−0,104, IC [−0,181, −0,030]).
9. El "17% a 34% de celdas inestables" usa una definición defectuosa (`0 < media < 1`) que cuenta como inestable una celda con tres réplicas idénticas y parciales. Con la definición correcta, sobre el rectángulo actual, el rango es 12% a 28%.
10. Puntajes: rigor metodológico 3, validez estadística 2, reproducibilidad 3, honestidad de reporte 4. El paper declara sus límites con una franqueza poco común, y a la vez el número que decide su tesis empírica está mal construido. Las dos cosas son ciertas.

---

## 2. Hallazgos por sección

Convención: [R] es corrección de redacción, [M] exige recomputar o medir.

### Resumen y §1

H-01 (líneas 94 a 97, 187 a 189). Dice: "entre el 17% y el 34% de las celdas devuelven resultados distintos a temperatura cero". Verifiqué: `bench/fiabilidad.perfil` define inestable como `0.0 < mean(us) < 1.0`. Sobre el rectángulo 64 × 8 actual, `gist_reader` tiene 27% por esa definición y 12% con réplicas realmente distintas; 14% de sus celdas son tres réplicas idénticas y parciales. Rango correcto sobre 64 × 8: 12% (gist_reader) a 28% (rewoo, supervisor); para los cuatro brazos de la tabla de §7.2.2: 20% a 28%. Corrección [M]: redefinir inestable como `len(set(us)) > 1` y recomputar; el rango del Resumen cambia.

H-02 (líneas 101 a 103, 3217). Dice: las capacidades "predicen un paradigma nunca visto mejor que la identidad del paradigma, incluso cuando a ésta se le permite ver la respuesta". Verifiqué: el baseline "identidad viendo al brazo" es la media global del brazo, sin término de tarea. El modelo de capacidades sí lleva el término de tarea (`dif[t] + efectos`). Computé la identidad aditiva (`dif[t] + efecto del brazo`, también viendo al brazo): MAE 0,225 contra 0,233 de capacidades. Además, el propio script imprime como veredicto "NO TRANSFIEREN en este corpus" (p = 0,065). Corrección [R+M]: retirar la frase del Resumen y de §9; en §7.4.1 reemplazar la cuarta fila por la identidad aditiva y decir que pierde contra ella.

H-03 (líneas 96 a 97, 1939 a 1943, 3216). Dice: la corrección lleva a `pointer_chase` "de 0,33 a 0,89" en C3. Verifiqué: en el registro de campaña hay dos tareas C3 en el rectángulo (`c3-000-h1`, `c3-001-h2`); `pointer_chase` saca 0,167 (1 de 6) y `dag_strategy` 0,667 (4 de 6, con dos ceros). Los "12 correctas, 3 abstenciones, cero equivocadas" (línea 1859) suman 15 celdas y no están en este registro. El 0,89 tampoco. Corrección [R]: declarar de qué corrida sale cada uno de esos números (archivo, fecha, tareas) o bajarlos a "medido en una corrida aparte, no en la campaña".

H-04 (líneas 268 a 271, 1581 a 1583). Dice: "factor 11× de costo" entre `react` y `rewoo`. Verifiqué: 108.137 / 10.840 = 9,98 en tokens; en dólares con la tarifa de `config/tariffs.json`, 21,81 / 2,32 = 9,4. El 11 sale de dividir 22 por 2 ya redondeados. §7.1.5 dice "factor 10" para la misma comparación. Corrección [R]: unificar en 10×.

H-05 (líneas 283 a 284, 1528 a 1531). Dice: "78 tareas × 12 paradigmas × 3 réplicas (121,4M tokens)". Verifiqué: 2.511 filas; `handoff`, `rewoo` y `graph_traverse` corrieron 78 tareas, los otros nueve corrieron 67 (faltan `b2-001-w4`, `b2-002-w4`, `c2-002-w4`, `c3-002-h3`, `c4-002-w4`, `c5-002-w4`, `c8-002-w4`, `c9-002-w4`, `d1-001-w4`, `d1-002-w4`, `w1-002-pos`). Tokens: 123,26M totales, 122,93M en filas factibles. Corrección [R]: "78 tareas, 12 paradigmas, 3 réplicas, 2.511 filas (nueve brazos sobre 67 tareas, tres sobre 78)".

### §5

H-06 (líneas 1099 a 1107). La tabla de la Proposición 5 no declara el modelo. Verifiqué por búsqueda: es Binomial(n = 8, k ≥ 4) para los cuatro valores (0,0050 / 0,1138 / 0,4059 / 0,5230). Corrección [R]: escribir "ocho tareas por split, umbral de cuatro rechazos". Sin eso la tabla no se puede verificar.

H-07 (líneas 1119 a 1129). La tabla A0/A3 (0,6101 → 0,4221) no trae n ni piso. Corrección [R]: n de celdas por fila.

### §7.0 y §7.1

H-08 (líneas 1540 a 1566). Tabla del plantel. Recomputé `aplica`, `u`, `u × aplica`, `tok/celda` para los doce brazos: coinciden al tercer decimal y al token. `pass^3` sobre 64 × 8 también coincide (react 0,734, dag 0,703, reflection 0,688, rewoo 0,531, supervisor 0,406, gist 0,516, handoff 0,438, pointer 0,359). El 101,9% de `graph_traverse` reproduce (1,019). Nada que corregir.

H-09 (líneas 1634 a 1649). Degradación por ancho. Recomputé sobre todas las filas factibles: reflection w48 0,73 (paper 0,71), rewoo w48 0,69 (paper 0,66, así que Δ es +0,09 y no +0,06), handoff w4 0,75 (paper 0,72), supervisor w16 0,61 (paper 0,59). El paper no dice sobre qué panel se calculó. Corrección [R]: declarar panel; si es el rectángulo, decirlo.

H-10 (líneas 1753 a 1756). Bien hecho: renunciar al exponente con n desparejo es la decisión correcta.

### §7.2

H-11 (líneas 1765 a 1778, 2034 a 2040). Dice: §7.2.2 y §7.3 usan "59 × 8 (rectángulo con ≥3 réplicas)". Verifiqué: `bench.panel.rectangulo` sobre el registro da 64 × 8, y las 64 tareas tienen tres réplicas en los ocho brazos. El 59 aparece sólo en `_predictores.py` y `_senales_del_camino.py`, que excluyen a mano `{"b2-000-w4", "b2-001-w16", "b2-002-w16", "c3-000-h1", "c2-001-w4"}` bajo el nombre `CONTAMINADAS`, y además restringen al `campaign_roster()` (73 tareas medidas en vez de 78). La frase de §7.3.1 "el criterio de recorte es mecánico y está en un solo lugar del código" es falsa para ese panel. Corrección [R+M]: declarar las cinco exclusiones y su motivo, o recomputar §7.2.2 y §7.3 sobre 64 × 8.

H-12 (líneas 1821 a 1829). Tabla pass^k de cuatro brazos. No pude reproducirla sobre 64 × 8 (react 0,843 / 0,734 / 23% contra 0,875 / 0,797 / 17% del paper). Es el panel de H-11 con la definición de H-01. Corrección [M]: recomputar con la definición correcta sobre el panel declarado.

H-13 (líneas 1992 a 2006). Iteraciones por brazo reproducen exactas (8,9 / 8,6 / 5,9 / 4,3 / 3,8 / 2,0 / 1,9). r = −0,24 reproduce (−0,237 con 8 brazos, −0,244 con los 7 de la tabla; la tabla omite `handoff` y el texto dice n = 8). El paper ya declara que ocho puntos no deciden nada. Corrección [R]: incluir a `handoff` en la tabla o decir n = 7.

H-14 (líneas 3084 a 3091). El confundente del jitter de servicio está bien declarado. Agrego: con k = 3 réplicas, la probabilidad de detectar una celda cuya réplica se da vuelta con probabilidad q es 1 − q³ − (1 − q)³; para q = 0,10 es 0,27, para q = 0,20 es 0,49. El 17 a 34% (o 12 a 28%) es una cota inferior de la fracción de celdas inestables, y el paper lo presenta como estimación puntual. Corrección [R]: decir "al menos".

### §7.3

H-15 (líneas 2034 a 2058). Descomposición de varianza. Corrí `_predictores.py` hoy: α 0,0648 (42%), β 0,0160 (10%), γ 0,0720 (47%), ε 0,0337, γ limpio 0,0608, S/R 5,41. El paper trae 0,0632 / 0,0160 / 0,0736 / 0,0351 / 0,0619 / 5,30: es el mismo script sobre un registro anterior. Sobre 64 × 8 con varianza insesgada: 0,0748 / 0,0138 / 0,0753 / 0,0563, γ limpio 0,0565, S/R 3,0. Tres observaciones de método: (a) el script usa `pvariance` (ddof = 0) para β sobre 8 valores, lo que sesga β hacia abajo un 12,5%; (b) descuenta ε/3 de γ pero no de α ni de β, aunque la corrección para ellos es chica (ε/24 y ε/177); (c) el "48%" se calcula sobre la γ sin descontar ruido; descontado, γ es 43% de la varianza explicada (39% sobre 64 × 8). El modelo aditivo es apropiado porque el panel es un rectángulo completo, pero eso vale sólo por la exclusión no declarada de H-11. Corrección [M]: ddof = 1 en las tres componentes, descontar ruido antes de reportar porcentajes, declarar el panel.

H-16 (líneas 2064 a 2073). Corrección por selección. Reproduce: 0,308 contra máximo de nulos p95 0,148, p < 1/2000. El diseño (máximo de los nueve nulos) es correcto para la selección entre nueve candidatas. Dos cosas que el paper no dice: la candidata ganadora, `cardinalidad × término literal`, se construyó después de que el eje literal se descubriera midiendo (§7.8.3, 2026-08-30), así que la familia de hipótesis efectivamente explorada es mayor que nueve; y con 2.000 permutaciones "p < 0,001" es lo máximo afirmable. Corrección [R]: declarar que el producto se agregó tras ver el eje literal.

H-17 (líneas 2082 a 2119). El piso de ruido de §7.3.3. El paper describe en la caja (líneas 2101 a 2105) el estimador de `metrics.noise_floor`: réplicas del mismo paradigma tratadas como paradigmas distintos. El número 0,065 no sale de ahí. Sale de `_predictores.py` líneas 358 a 368: para cada (tarea, contendiente) remuestrea con reposición las tres réplicas reales, promedia, y calcula oráculo menos mejor fijo sobre esas medias; el "piso" es la media de 400 corridas. Eso es la distribución bootstrap del estadístico de brecha. Su esperanza es la brecha observada más el sesgo extra que agrega el remuestreo, así que "brecha − piso" es negativa o nula por construcción. Lo verifiqué de tres formas. (1) Reproduje 0,065 y el neto −0,008 con ese procedimiento. (2) Sobre los ocho brazos del mismo panel: brecha +0,080, "piso" 0,089, neto −0,009; y con el estimador de la caja: 0,074, neto +0,006. (3) Sintético, 60 tareas × 3 brazos, premio real +0,50, ruido sd 0,15: brecha observada +0,313, "piso" bootstrap 0,308, neto +0,005; con el estimador de la caja: 0,097, neto +0,216. El estimador usado no puede detectar un premio de medio punto. Con el estimador de la caja sobre los tres contendientes hoy: piso 0,075, neto −0,018. La conclusión de §7.3.3 sobrevive en signo con el estimador correcto, pero por el motivo equivocado y con otro número. Corrección [M]: recomputar con `metrics.noise_floor` y publicar además un IC bootstrap pareado de la brecha misma.

H-18 (líneas 2136 a 2153). Familias reproduce (+0,079; 54 / 6 / 4 contra 54 / 5 / 5 del paper; +0,110 brazos sobre 64). Pero el piso 0,065 se reusa para tres familias y para ocho brazos. El paper mismo dice en §7.7.1 (línea 2726) que el sesgo del máximo "crece con cuántos compiten". Simulé el sesgo con k pseudo-brazos remuestreando las réplicas de `react`: k = 3 da media 0,055 y p95 0,081; k = 8 da media 0,081 y p95 0,109. El "+0,045 neto para brazos" es contra un piso de k = 3. Corrección [M]: piso con k igual al número de brazos comparados.

H-19 (líneas 2168 a 2177). Primera tabla de §7.3.5: `cardinalidad × término` −0,017 / 42% reproduce; `región` da −0,086 / 74% (paper −0,110 / 74%); `n_units` da +0,014 / 0% (paper +0,000 / 1%). Deriva del registro. Corrección [R]: actualizar o fechar.

H-20 (líneas 2179 a 2193). Segunda tabla (41 × 7, 0,951 y 46% contra 0,928 y 37%). No hay script en el repo que la produzca; la fuente es `lab/CLAUDE.md` líneas 95 a 101 y un docstring de `app/features.py` (líneas 366 a 375) con otros números (0,938 / 69%, 0,951 / 48%). El script que sí existe para esta pregunta, `_plasticidad.py`, corrido hoy sobre 64 × 8 con objetivo costo, da: θ región completa −0,063 [−0,139, +0,002] con 68% de ahorro; θ región computada −0,104 [−0,181, −0,030] con 31% de ahorro. La clave reproducible pierde utilidad de forma significativa. La frase "elegir el barato es una decisión aprendible que sobrevive fuera de muestra" no está sostenida por el código vigente. Corrección [M]: publicar el script que produce 0,951 / 46% o retirar la tabla y el "+0,021" del Resumen (línea 120) y §9 (línea 3219).

H-21 (líneas 2195 a 2210). §7.3.6: 7 de 26 tareas cambian de región entre modelos. No pude verificar (no ubiqué el archivo de las 26 con dos familias). Queda sin verificar.

### §7.4

H-22 (líneas 2340 a 2369). Leave-one-arm-out reproduce exacto (0,364 / 0,257 / 0,233 / 0,339; los ocho pliegues). Ver H-02 para la cuarta fila. Además, con ocho pliegues, el MAE promedio lo mueven dos brazos (react y reflection bajan a 0,16); sin ellos capacidades y dificultad de tarea empatan.

H-23 (líneas 2378 a 2385). Nulo barajado reproduce (media 0,2599, p5 0,2299, p = 0,065). El p es unilateral y con 400 barajadas; con 8! = 40.320 permutaciones se puede hacer exacto. El real (0,2327) está por encima del p5 del nulo: el 5% de las asignaciones al azar predicen mejor que la tabla real. El paper lo llama "sugestivo"; el script lo llama "NO TRANSFIEREN". Corrección [R]: alinear el texto con el veredicto del script o justificar la diferencia.

H-24 (líneas 2415 a 2427). Tabla S/R. No hay script en `bench/analysis` que la produzca; la única fuente es `lab/PENDIENTES.es.md` (ONT-1, 2026-08-30), que dice "con 46 tareas". El paper (PI6, línea 1498) dice "registro completo". El control por número de segmentos divide la ganancia por la cantidad de segmentos, que es una penalización lineal ad hoc; el inflado de S/R por segmentación no es lineal en el número de segmentos y depende del tamaño de cada uno. El control válido es el mismo nulo por permutación de §7.3.2 aplicado a cada segmentación. El "40% más" (0,148 / 0,105 = 1,41) es aritméticamente correcto y metodológicamente no sostenido. Corrección [M]: recomputar sobre el registro actual con nulo por permutación por segmentación y publicar el script.

### §7.5

H-25 (líneas 2460 a 2475). Curva reproduce fila por fila (208 / 36 / 24 / 64 / 20 / 42 / 70 / 48 y sus probabilidades). Wilson 0,979 verificado. Agrego: en k = 4 solo hay 20 celdas (Wilson inferior 0,839); el "≥ 0,98" es del agregado k ≥ 4.

H-26 (líneas 2479 a 2503). Los tres controles reproducen (180 / 36, 1,000 / 0,100; las cuatro cardinalidades). El control dentro de la tarea es el correcto y es la parte más sólida del paper.

H-27 (líneas 2568 a 2584). Réplica en terra. El registro actual tiene 26 tareas, 350 filas, 200 celdas factibles de 8 brazos en réplica 0 (paper: 23 tareas, 374 filas, 209 celdas). Recomputado: k ≥ 4 da 104 celdas con P = 1,000 en 15 de 26 tareas (paper 99, 14 de 23); k ≥ 3 da 120 celdas, 1,000, 19 de 26 (paper 115, 18 de 23); fuera del consenso a k ≥ 3: 0,263 con n = 30 (paper 0,272, n = 29). Cualitativamente idéntico. Dos cosas: P29 exigía "reportar la curva entera" y el paper no la muestra; en terra la curva no es monótona en k bajo (k = 0: 0,397; k = 1: 0,500; k = 2: 0,250 con n = 12). Y una réplica de un solo trial no permite estimar el piso de ruido de esa corrida. Corrección [R]: publicar la curva completa de terra y actualizar los conteos.

H-28 (líneas 2586 a 2601). El manejo del tamaño de plantel (restringir a los mismos ocho) es correcto. La lectura "el umbral es del modelo" es post hoc y la guarda de P29 la cubre. Bien.

### §7.6

H-29 (líneas 2624 a 2631). 211× verifica (4,55 / 0,0216 = 210,6). El paper declara que es inferencia y no medición. Correcto.

### §7.7

H-30 (líneas 2694 a 2721). El held-out. Utilidades por brazo reproducen exactas; las tres brechas observadas reproducen exactas (+0,139 / +0,168 / +0,128). Los pisos 0,167 / 0,187 / 0,162 no salen del estimador que el paper describe. Los reproduje como p95 del bootstrap del estadístico (H-17) sobre 400 corridas: 0,167 / 0,185 / 0,162. Con `metrics.noise_floor` (réplicas del mismo brazo como pseudo-brazos, ocho brazos, k = 3): 0,073 / 0,072 / 0,071, y las brechas netas quedan en +0,066 / +0,096 / +0,057. Con un k = 8 simulado el piso sube a alrededor de 0,08 a 0,11 y el neto queda entre +0,02 y +0,08. Ninguna variante legítima da negativo en los tres estratos. La afirmación "el premio neto es negativo en los tres estratos" no se sostiene; lo afirmable es "positivo y chico, sin IC que lo separe de cero con 12 a 24 tareas". Además, el patrón piso ≈ brecha + 0,02 a 0,03 en las tres filas es la firma de este defecto. Corrección [M]: recomputar con el estimador descripto, con k igualado al plantel, y con IC bootstrap pareado de la brecha. Reescribir §7.7.1, §7.7.2, el Resumen (línea 80 a 82), §1.1.2 (línea 229) y §9 (línea 3230).

H-31 (líneas 2723 a 2731). "El piso no decrece al agregar tareas, y eso es una propiedad del estimador". Es cierto para el sesgo del máximo, y es exactamente lo que hace sospechoso que el piso siga a la brecha observada estrato por estrato. Con el estimador correcto el piso es plano en 0,071 a 0,073.

H-32 (líneas 2694, 2749 a 2754). Tres conteos distintos de la misma corrida: 927 filas (§7.7.1), 932 celdas (§7.7.3), 936 en el registro y en `CIERRE-2026-08-30`. El estrato base+w4 dice 500 celdas; son 504 filas. Corrección [R].

### §7.8

H-33 (líneas 2788 a 2802). La tabla de régimen y la declaración de dos modelos son suficientes y están bien ubicadas. `p15_verdict.json`, `p16_verdict.json`, `p17_verdict.json` y `statistics.json` reproducen cada número de §7.8.1 y §7.8.2 (−0,0874, 0,05729, [−0,2284, +0,0367], p 0,19; +0,1116 [+0,0014, +0,2382] p 0,045; barrido λ; 2 de 26; 14 sondas).

H-34 (líneas 2806 a 2809). El piso de P15 (0,057) se estimó sobre 112 tareas de los corpus de entrenamiento (`noise_floor.tasks = 112`), no sobre el mundo held-out de 26. El paper no lo dice. Corrección [R].

H-35 (líneas 2843 a 2852). El barrido λ compara netos a λ = 0,02 y 0,05 (donde la utilidad por celda llega a −3,78 por ratios de costo de 50× a 80×) contra un piso de ruido computado a λ = 0 (0,034). El piso a λ > 0 tiene que incorporar la dispersión de costo entre réplicas, que el propio laboratorio mide en 2× a 5× (PENDIENTES, "99 de 428 celdas"). "A λ = 0,02 ya está dentro del ruido" no está medido contra el ruido de λ = 0,02. Corrección [M].

### §7.9

H-36 (líneas 2916 a 2927). `retention.json` reproduce 0,533, 0,721, 29 de 90. "Mayor diferencia entre paradigmas 0,126, razón 4,2×": el 0,126 es la mayor desviación de un brazo respecto de la media (gist_reader −0,1264). La diferencia entre el mejor y el peor brazo es 0,083 − (−0,126) = 0,209, y la razón es 2,5×. Corrección [R]: "2,5× la diferencia entre el mejor y el peor brazo".

H-37 (líneas 2931 a 2941). Participaciones 5,2% / 62,2% / 10,5% reproducen. Son R² de agrupamiento simple sobre 90 celdas con 5, 5 y 21 grupos. El R² esperado bajo nulo es aproximadamente (g − 1) / (n − 1): 4,5% para región y paradigma, 22,5% para tarea. La "tarea" está por debajo de su propio nulo y la "región" en el suyo; el "seis veces más que la tarea" compara un R² inflado por grados de libertad con uno que no lo está. Con R² ajustado la conclusión cualitativa (el paradigma domina) se mantiene y el 6× desaparece. El archivo también tiene región × paradigma = 82,7% y un MAE fuera de muestra por paradigma 0,205 contra 0,392 por región, que son mejores evidencias y no están en el paper. El condicionamiento post-tratamiento está declarado (línea 2945). Corrección [M]: R² ajustado, y decir modelo `nano` y cinco brazos (incluido `map_reduce`, que no está en el catálogo de la campaña) en el Resumen (línea 124) y §9 (línea 3219), donde hoy no lleva etiqueta.

H-38 (líneas 2952 a 2975). P30: tokens 137.211 / 87.495, llamadas 4,3 / 4,0 y "3 de 63" reproducen exactos sobre los mismos 63 pares. La utilidad no: el paper dice 0,540 / 0,540 y el registro da 0,822 / 0,825. La causa es el re-puntuado del 2026-08-30 (`_regrade_2026_08_30.py`, 252 filas), posterior al veredicto de P30 y no propagado. Y "utilidad exactamente igual" describe la media: 7 de 63 celdas cambian de utilidad (4 suben, 3 bajan), con desvío del delta pareado 0,31. Corrección [M+R]: actualizar a 0,822 / 0,825 y decir "media igual, 7 de 63 celdas cambian".

H-39 (líneas 2979 a 2997). No verifiqué el 33% de tokens evitables ni la racha 1,17 / 2,28.

### §8 y §9

H-40 (líneas 3020 a 3038). El párrafo "Ya existen réplicas, y el ruido es por celda" habla de "primer estudio", "segundo", "celdas en re-corrida" y "marcadas † en §7.4": es texto heredado de un borrador anterior que ya no corresponde a las secciones actuales (§7.4 no tiene †). Corrección [R].

H-41 (líneas 3214 a 3231). La tabla de conclusiones repite H-02, H-03, H-20, H-30 y H-37. "−0,034 held-out" cambia de signo con el estimador descripto.

H-42 (línea 1525). "Sobre 567 ceros, ninguno presenta señal fuerte". El re-puntuado del 2026-08-30 cambió 252 filas (c9 +0,825, d1 +1,000) y PENDIENTES línea 1745 dice que "el registro abarca varias versiones del grader". El paper no declara versión de corrector por fila ni cuándo se corrió la auditoría de los 567. Corrección [R]: fechar la auditoría y declarar que el registro mezcla versiones del corrector, o estampar versión por fila.

---

## 3. Números recomputados

| sección, línea | qué | paper | recomputado | diferencia | cómo |
|---|---|---:|---:|---|---|
| §1.3 l.283 | filas de campaña | 78×12×3 = 2.808 | 2.511 | 9 brazos con 67 tareas | conteo del JSONL |
| §1.3 l.284 | tokens de campaña | 121,4M | 123,26M (122,93M factibles) | +1,9M | suma `cost_tokens` |
| §7.1 l.1542-1553 | aplica, u, u×aplica, tok/celda, 12 brazos | (tabla) | idéntico al 3er decimal | 0 | registro entero, sin infeasible |
| §7.1 l.1542-1549 | pass^3, 8 brazos, 64×8 | 0,734 … 0,359 | idéntico | 0 | `fiabilidad.perfil` y recomputo propio |
| §7.1 l.1582 | costo react/rewoo | 11× | 9,98× tokens, 9,4× USD | redondeo | tarifa luna 0,2 / 1,2 |
| §7.1.2 l.1638-1641 | reflection w48, rewoo w48, handoff w4, supervisor w16 | 0,71 / 0,66 / 0,72 / 0,59 | 0,73 / 0,69 / 0,75 / 0,61 | +0,02 a +0,03 | todas las filas factibles |
| §7.2.2 l.1823-1826 | react pass@1 / pass^3 / inestables | 0,875 / 0,797 / 17% | 0,843 / 0,734 / 23% (64×8) | panel distinto, definición distinta | ver H-11, H-01 |
| §7.2.2 l.1828 | rango de celdas inestables | 17% a 34% | 12% a 28% (8 brazos), 20% a 28% (los 4) | definición | réplicas distintas, 64×8 |
| §7.2.6 l.1994-2000 | iteraciones por brazo | 8,9 / 8,6 / 5,9 / 4,3 / 3,8 / 2,0 / 1,9 | idéntico | 0 | media de `iterations` |
| §7.2.6 l.2002 | r(decisiones, caída) | −0,24 (n=8) | −0,237 (8) / −0,244 (7) | 0 | |
| §7.3.1 l.2047-2050 | α / β / γ / ε | 0,0632 / 0,0160 / 0,0736 / 0,0351 | 0,0648 / 0,0160 / 0,0720 / 0,0337 (`_predictores` hoy) | deriva | 59×8 con exclusiones |
| §7.3.1 | mismo, 64×8, ddof=1 | | 0,0748 / 0,0138 / 0,0753 / 0,0563 | | recomputo propio |
| §7.3.1 l.2057 | γ limpio, S/R | 0,0619, 5,30 | 0,0608, 5,41 (59×8); 0,0565, 3,0 (64×8) | | |
| §7.3.2 l.2070 | señal ganadora | 0,309, p<0,001 | 0,308, p<1/2000 | 0 | 2.000 permutaciones |
| §7.3.3 l.2087-2092 | γ contendientes, S/R | 0,0046, 0,38 | 0,0034, 0,28 | deriva | |
| §7.3.3 l.2088-2091 | oráculo / fijo / premio / piso / neto | 0,932 / 0,875 / +0,058 / 0,065 / −0,008 | idéntico con el bootstrap del estadístico | 0 | H-17 |
| §7.3.3 | piso con `metrics.noise_floor`, 3 contendientes | | 0,075, neto −0,018 | | estimador descripto en la caja |
| §7.3.3 | piso bootstrap del estadístico, 8 brazos | | brecha +0,080, "piso" 0,089, neto −0,009; nulo 0,074, neto +0,006 | | |
| sintético | premio real +0,50 | | observado +0,313, "piso" 0,308, neto +0,005; nulo 0,097, neto +0,216 | | 60×3, sd 0,15 |
| §7.3.4 l.2137-2142 | familias, brazos, victorias | +0,079 / +0,110 / 54-5-5 | +0,079 / +0,110 / 54-6-4 | 1 tarea | 64×8 |
| §7.3.4 | piso simulado k=3 / k=8 | 0,065 para ambos | media 0,055 p95 0,081 / media 0,081 p95 0,109 | crece con k | réplicas de react remuestreadas |
| §7.3.5 l.2170-2172 | cardinalidad×término / región / n_units | −0,017 42% / −0,110 74% / +0,000 1% | −0,017 42% / −0,086 74% / +0,014 0% | deriva | `_predictores` hoy |
| §7.3.5 l.2186-2187 | política 41×7, con / sin literal | 0,951 46% / 0,928 37% | no reproducible; `_plasticidad` 64×8: −0,063 [−0,139, +0,002] 68% / −0,104 [−0,181, −0,030] 31% | sin script | H-20 |
| §7.4.1 l.2342-2345 | MAE cuatro modelos | 0,364 / 0,257 / 0,233 / 0,339 | idéntico | 0 | `_eda_capacidades.py` |
| §7.4.1 | identidad aditiva (tarea + brazo, ve al brazo) | no reportada | 0,225 | gana a capacidades | recomputo propio |
| §7.4.2 l.2379-2381 | nulo barajado | 0,2599 / 0,2299 / p 0,065 | idéntico | 0 | |
| §7.4.3 l.2415-2421 | S/R por segmentación | 1,00 / 1,04 / 1,74 / 1,84 / 1,92 | no reproducible | sin script; fuente 46 tareas | H-24 |
| §7.5.1 l.2460-2469 | curva k = 0..7 | (tabla) | idéntica | 0 | `_consenso.py` |
| §7.5.1 l.2473 | Wilson inferior 180/180 | 0,980 | 0,979 | 0 | |
| §7.5.2 l.2483-2499 | controles | 180 / 36, 1,000 / 0,100; cardinalidades | idénticos | 0 | |
| §7.5.4 l.2570-2579 | terra | 23 tareas, 374 filas, 209 celdas; k≥4 99, 14/23; k≥3 115, 18/23; fuera 0,272 (29) | 26, 350, 200; 104, 15/26; 120, 19/26; 0,263 (30) | registro creció | 8 brazos, trial 0 |
| §7.6.1 l.2631 | ventana / react | 211× | 210,6× | 0 | |
| §7.7.1 l.2697-2706 | u por brazo held-out | (tabla) | idéntica | 0 | 24×8 |
| §7.7.1 l.2713 | brecha observada | +0,139 / +0,168 / +0,128 | idéntica | 0 | |
| §7.7.1 l.2714 | piso p95 | 0,167 / 0,187 / 0,162 | 0,167 / 0,185 / 0,162 con bootstrap del estadístico; 0,073 / 0,072 / 0,071 con `metrics.noise_floor` | estimador | H-30 |
| §7.7.1 l.2715 | brecha neta | −0,028 / −0,019 / −0,034 | +0,066 / +0,096 / +0,057 con el estimador descripto | cambia de signo | |
| §7.7.1, §7.7.3 | filas / celdas held-out | 927 / 932 / 500 (base) | 936 / 936 / 504 | contabilidad | |
| §7.8.1-2 | P15, P16, P17, statistics | (todos) | idénticos | 0 | JSON de `results/nano` |
| §7.9.1 l.2922-2923 | recall completo, brecha, C5 | 29/90, +0,533, +0,721 | idéntico | 0 | `retention.json` |
| §7.9.1 l.2923 | mayor diferencia entre paradigmas, razón | 0,126, 4,2× | rango mejor-peor 0,209, 2,5× | definición | |
| §7.9.1 l.2933-2935 | participaciones | 5,2% / 62,2% / 10,5% | idénticas; nulo esperado ≈ 4,5% / 4,5% / 22,5% | df | H-37 |
| §7.9.2 l.2960-2961 | tokens, llamadas, u | 137.211 / 87.495, 4,3 / 4,0, 0,540 / 0,540 | 137.211 / 87.495, 4,3 / 4,0, 0,822 / 0,825; 7 de 63 celdas cambian | re-puntuado no propagado | |
| §5.4 l.1102-1107 | Proposición 5 | (tabla) | Binomial(8, ≥4) exacta | modelo no declarado | |
| §7.2.3 l.1859 | dag_strategy en C3 | 12 correctas, 3 abstenciones, 0 erradas | en campaña: 4 de 6 correctas, 2 ceros, 2 tareas C3 | fuente no declarada | |
| §7.2.4 l.1939 | pointer_chase en C3 | 0,33 → 0,89 | en campaña: 0,167; el 0,89 no está en el registro | fuente no declarada | |

---

## 4. Riesgos estadísticos que el paper no declara

1. El estimador de piso de ruido usado (bootstrap del estadístico) tiene esperanza igual o mayor que la brecha observada. Toda "brecha neta" calculada con él es no positiva por construcción. Afecta §7.3.3, §7.3.4, §7.7.1, §7.7.2, Resumen, §1.1.2 y §9.
2. Un piso construido con k = 3 pseudo-brazos se compara contra oráculos de 3 y de 8 brazos por igual (§7.3.4, §7.7.1). El sesgo del máximo crece con k.
3. El piso de P15 (0,057) se estimó sobre otros corpus (112 tareas de entrenamiento), no sobre el mundo held-out donde se aplica.
4. Los netos a λ > 0 (§7.8.2) se comparan contra un piso a λ = 0. El costo es 20 veces más disperso entre réplicas que la utilidad, según el propio laboratorio.
5. Panel post hoc: cinco tareas excluidas a mano en §7.2.2 y §7.3 sin declararlo, y roster restringido a 73 tareas medidas.
6. Registro en movimiento: al menos cinco tablas (§7.1.2, §7.3.1, §7.3.5, §7.5.4, §7.9.2) están tomadas de estados distintos del registro, y una (§7.4.3) de un estado de 46 tareas. No hay hash ni fecha de snapshot por tabla. El re-puntuado del 2026-08-30 cambió 252 filas y no se propagó a §7.9.2.
7. Versiones del corrector mezcladas en el registro (PENDIENTES 1745) sin estampa por fila; la auditoría de 567 ceros no está fechada respecto del re-puntuado.
8. Definición defectuosa de "inestable" (cuenta réplicas idénticas parciales). Y con k = 3 la detección de inestabilidad tiene potencia 0,27 para q = 0,10: la fracción es cota inferior.
9. Comparación desigual en §7.4.1 (identidad sin término de tarea contra capacidades con término de tarea).
10. Participaciones de varianza (§7.9.1) sin ajuste por grados de libertad, con 21 grupos sobre 90 celdas.
11. Familia de hipótesis en §7.3.2 mayor que las nueve declaradas: la ganadora se construyó tras descubrir el eje literal midiendo.
12. Múltiples comparaciones a lo largo del paper (nueve señales, tres familias, siete vocabularios, cuatro contrastes de P15, 56 cascadas, ocho pliegues) con corrección sólo en §7.3.2 y en P15.
13. La ontología de §7.4.3 y su "40% más" usan un control lineal por número de segmentos en vez de un nulo por permutación.
14. Los ocho brazos del consenso comparten modelo, corpus, recuperador y semilla; el paper lo declara. Lo que no declara es que el recuperador es el mismo índice con la misma consulta en varios brazos, así que parte del "acuerdo" es identidad de entrada y no convergencia.
15. Held-out con 12, 18 y 24 tareas: cualquier p95 sobre 12 tareas tiene error de muestreo del orden del efecto que se busca.
16. La curva terra completa no se publica aunque P29 lo exigía; en k bajo no es monótona.
17. Los números de C3 (12 / 3 / 0; 0,33 → 0,89) provienen de corridas fuera del registro de campaña y no están fechados ni contados.

---

## 5. Diez preguntas para la rebuttal

1. El piso de ruido de §7.3.3 y §7.7.1, ¿se computó con `metrics.noise_floor` (réplicas del mismo paradigma como pseudo-brazos), como dice la caja de §7.3.3, o con el bootstrap de `_predictores.py` líneas 358 a 368 (remuestreo de réplicas por celda real y recálculo de la brecha)? Si es lo segundo, ¿cómo justifican que "brecha − piso" pueda ser positiva alguna vez?
2. ¿Qué da la brecha neta del held-out en los tres estratos con `metrics.noise_floor`, con k igualado a ocho brazos, y con un IC bootstrap pareado sobre tareas de la brecha misma?
3. ¿Por qué las tareas `b2-000-w4`, `b2-001-w16`, `b2-002-w16`, `c3-000-h1` y `c2-001-w4` están excluidas del panel 59 × 8 y qué las hace "contaminadas"? ¿Cambian las conclusiones de §7.3 sobre 64 × 8?
4. ¿Cuál es el MAE de un modelo de identidad aditivo (dificultad de tarea más efecto del brazo) en el leave-one-arm-out, y sostienen la frase "las capacidades superan a la identidad incluso cuando ésta ve la respuesta" contra ese baseline?
5. ¿Qué script produce la tabla 41 × 7 de §7.3.5 (0,951 / 46%) y sobre qué snapshot? `_plasticidad.py` sobre el registro actual da −0,104 [−0,181, −0,030] para la clave computada. ¿Cuál de los dos describe al sistema?
6. ¿Qué script produce la tabla S/R de §7.4.3, sobre cuántas tareas, y qué da con un nulo por permutación por segmentación en lugar de dividir la ganancia por el número de segmentos?
7. ¿Cuántas de las celdas contadas como "inestables" en §7.2.2 tienen las tres réplicas idénticas y parciales? ¿Cuál es el rango 17 a 34% con la definición `len(set(us)) > 1`?
8. ¿De qué corrida salen "12 correctas, 3 abstenciones, cero equivocadas" (§7.2.3) y "0,33 → 0,89" (§7.2.4), dado que la campaña tiene dos tareas C3 en el rectángulo y `pointer_chase` saca 0,167 ahí?
9. ¿Qué versión del corrector tiene cada fila del registro, y la auditoría de 567 ceros es anterior o posterior al re-puntuado del 2026-08-30 que cambió 252 filas? ¿Por qué P30 sigue con u = 0,540 si el registro da 0,822 / 0,825?
10. En §7.9.1, ¿qué dan las participaciones con R² ajustado por grados de libertad (5, 5 y 21 grupos sobre 90 celdas), y sostienen el "seis veces más que la tarea" cuando el R² esperado bajo nulo para la tarea es 22%?

---

## 6. Puntajes (1 a 5)

| dimensión | puntaje | por qué |
|---|---:|---|
| Rigor metodológico | 3 | Predicciones preregistradas, controles dentro de tarea, factibilidad aritmética, declaración de dos modelos: todo bien hecho. En contra: panel post hoc no declarado, baseline desigual en §7.4.1, control ad hoc en §7.4.3, comparación de λ contra piso de λ = 0. |
| Validez estadística | 2 | El estimador que decide la tesis empírica (piso de ruido) está mal construido y el veredicto del held-out cambia de signo con el estimador que el propio paper describe. Definición defectuosa de inestable. R² sin ajuste. Piso con k fijo. |
| Reproducibilidad | 3 | Registro completo, scripts para la mayoría de las tablas, y once tablas reproducen al tercer decimal. En contra: tres tablas sin script (§7.3.5 segunda, §7.4.3, §7.7.1 piso), registro sin snapshot por tabla, cinco tablas con deriva, y números de C3 sin fuente. |
| Honestidad de reporte | 4 | El paper declara más límites que la mayoría (dos modelos, ontología sobre etiqueta de diseño, ciclo ejecutado por personas, n = 8, jitter de servicio, condicionamiento post-tratamiento). La descripción del piso de ruido no coincide con el código, y varios números están desactualizados, pero nada indica intención: el patrón es de un registro que se movió más rápido que el texto. |

Recomendación: revisión mayor. El trabajo tiene un registro auditable y una disciplina de preregistro que se agradece. Lo que hace falta es recomputar el piso de ruido con el estimador declarado en toda sección que lo use, declarar el panel real, actualizar las tablas al snapshot vigente con hash, y bajar cuatro afirmaciones del Resumen (17 a 34%, identidad vs capacidades, +0,021 fuera de muestra, brecha neta negativa held-out) a lo que el registro sostiene hoy.
