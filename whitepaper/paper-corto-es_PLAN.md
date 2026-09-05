# Revisión del corto: decisiones deterministas que mejoran el sistema

Fecha: 2026-09-04. Documento leído: `paper-corto-es.md`, v2.1, completo.
Alcance: revisar la idea del autor, su sustento y la vía para demostrarla. Este archivo es
un diagnóstico y una propuesta de evaluación; no modifica el paper ni declara capacidades
nuevas como implementadas. No se ejecutaron llamadas a modelos ni se reestimaron los resultados.

## 1. Diagnóstico

La idea original sigue abierta: una capa determinista puede usar evidencia para tomar decisiones
que mejoren el sistema. El corto demuestra una propiedad distinta y necesaria pero insuficiente:
la reproducibilidad de la decisión bajo un estado dado. Una decisión reproducible puede estar
equivocada. Falta cerrar la cadena **señal disponible → decisión → cambio de ejecución → mejora
medida contra un control → transferencia**.

Hay dos señales positivas: la intervención de `pointer_chase` y el ahorro de θ. La primera
mezcla cuatro cambios diseñados sobre tres tareas; la segunda es una evaluación por tarea
retenida dentro del corpus usado para desarrollar las señales. Ninguna establece todavía la
mejora general del motor sobre tareas nuevas.

El corto además quedó detrás del laboratorio: no incorpora P39 ni P40. La bitácora dice que
P39 entró a ambos papers, pero no aparece en el corto leído. Hay que reconciliar los documentos.

## 2. Inventario de contribuciones y evidencia

| sección / pieza | qué aporta | qué no prueba |
|---|---|---|
| resumen, §1, figura 1 | tesis sensor–controlador; tres determinismos; contrato graduado | mejora de utilidad del sistema |
| §2 y referencias | posicionamiento frente a control, ruteo, procedencia y abstención | esta revisión no revalida las fuentes externas ni la novedad |
| §3, figura 2 y ejemplo `d1-002-w48` | factibilidad, creencias, dial, θ, EXPLAIN y consolidación ejecutables | que toda la campaña use control de trayectoria independiente del LLM |
| §4.1, definiciones 1–3, proposición 1 | condición suficiente para invariancia de trayectoria | mejor calidad; invariancia de las salidas |
| §4.2, teorema 1 | contabilidad de ganancias y pérdidas del ruteo | existencia de una política que gane |
| §4.3, definición 4, proposición 2 | dependencia de la política respecto de sus entradas | necesidad universal de una clave enteramente COMPUTED |
| §5.1, tabla 1 | catálogo, cobertura, utilidad, costos, consistencia | comparación completa de todos los brazos sobre las mismas tareas |
| §5.2, figura 3 | intervención 0,33 → 0,89; pass^3 0,33 → 0,67 | efecto aislado del ancla; transferencia |
| §5.3, definición 5, figura 4 | capacidades, exigencias, LOAO y segmentación | selector validado; necesidad de cada exigencia |
| §5.4, tabla de ciclos y episodios | aprendizaje de tablas, guardas y reparación humana del vocabulario | descubrimiento autónomo de sensores; ganancia de calidad general |
| §5.5, figura 5 | costo/calidad de políticas, recall y oferta de herramienta | no inferioridad estadística de θ; causalidad del recall |
| §5.6, tablas de varianza y oráculo | oportunidad de selección sobre ocho brazos y transferencia del premio oráculo | que una señal disponible permita capturarlo |
| §5.7, figura 6 | consenso asociado a éxito y réplica entre modelos | garantía universal; permiso para omitir verificación |
| §6 | amenazas internas, externas y de constructo | cierre de las amenazas declaradas |
| §7, P31–P38 | conclusiones y pruebas pendientes | resultado positivo por estar preregistrado |

## 3. Qué pasó con el resultado buscado

1. **El determinismo tiene una prueba, la mejora necesita una intervención.** §4.1 incluso
   dice explícitamente que el confinamiento no mejora la calidad. El salto a la utilidad tiene
   que venir de señales informativas y decisiones correctas, no del adjetivo determinista.
2. **La intervención positiva es local.** §5.2 prueba un paquete de cuatro correcciones en
   muestra. P32 prueba transferencia del paquete; para atribuir el efecto al ancla hay que
   compararla separadamente manteniendo los otros tres cambios constantes.
3. **El selector no logró cobrar la oportunidad.** P39, verificado contra su JSON, deja 63/64
   tareas sin candidato con los ejes de diseño y 25/64 con los computables. Ninguna política
   supera al mejor fijo. No es evidencia de que toda selección por capacidades sea imposible;
   sí refuta estas políticas y esta tabla.
4. **La tabla confunde necesidad con una implementación particular.** Exigir largo gobernado
   por código para una cadena excluye `dag_strategy`, que puede resolverla por otro camino.
   Exigir costo independiente del alcance porque el corpus no cabe en una ventana excluye
   recuperación iterativa que sí puede funcionar. Son rutas o propiedades de costo, no
   condiciones necesarias universales del resultado.
5. **Parte de la ontología sabe demasiado.** P40 documenta que `ausencia` sale de
   `relevant_units == []`. El sistema puede recibir una pregunta sobre la existencia de un
   hecho; no puede recibir como feature que el hecho efectivamente está ausente. La distinción
   separa intención de consulta y respuesta correcta.
6. **El ahorro es prometedor, pero su comparación debe quedar explícita.** P34 registra
   71.070 tokens frente a 120.976 de su constante: 41,25%; utilidad 0,875 frente a 0,8165;
   Δ=0,0585, IC95 [−0,0144, +0,1323]. La constante de P34 no es la fila del mejor fijo de §5.5.
   Un intervalo que incluye cero no demuestra equivalencia ni conservación de calidad.
7. **La adaptación de las tablas no es toda la adaptación deseada.** Aumentar cobertura de θ
   demuestra acumulación útil para decidir; no demuestra mejora de resultado. P36 no descubrió
   y retuvo el eje que faltaba. Los nuevos medidores fueron trabajo humano.

Fuentes verificadas: `../lab/results/luna/p34_verdicto.json`,
`../lab/results/luna/p39_ruteo_capacidades.json`,
`../lab/results/luna/eda_ruteo_profunda.json`,
`../lab/app/capacidades.py`, `../lab/bench/analysis/_p34_costo.py`,
`../lab/bench/analysis/_eda_ruteo_profunda.py` y la bitácora P39–P40.

## 4. Dirección propuesta: requisitos del resultado y contratos de ejecución

Hipótesis para implementar y medir, no resultado para incorporar como conseguido:

> El motor puede mejorar la relación entre calidad, costo y errores al decidir, desde señales
> verificables, qué evidencia debe obtener, qué ejecución puede obtenerla y cuándo la evidencia
> reunida alcanza para responder.

La decisión no tiene por qué limitarse al nombre de un paradigma. Puede ser cuánto leer, qué
relación seguir, cuándo ampliar el alcance, cuándo verificar y cuándo diferir. El catálogo
actual puede seguir siendo el ejecutor; cambia qué propiedad se le exige y se comprueba.

| requisito de respuesta | señales admisibles antes o durante la ejecución | contrato deseado | contraste que lo prueba |
|---|---|---|---|
| seguir n relaciones | n declarado, entidad y relaciones con referencia al material | aceptar sólo una cadena comprobada de n enlaces o diferir | mismo ejecutor con y sin guarda del contrato |
| enumerar un alcance completo | alcance declarado y registro de unidades procesadas | no presentar una enumeración parcial como completa | lecturas, omisiones, utilidad y costo con/sin guarda |
| contestar existencia o ausencia | pregunta de existencia, alcance y resultados de inspección | distinguir «no encontré» de «inspeccioné el alcance requerido» | casos positivos, negativos y evidencia difícil de recuperar |
| resolver vigencia | fecha solicitada y evidencia de fechas/versiones | no confundir vigente hoy con vigente a la fecha | pares de consultas con fechas distintas y material fijo |

Leer todo sólo acredita cobertura de lectura. No garantiza que la extracción haya entendido
todo ni demuestra por sí mismo ausencia semántica. El contrato debe declarar ese límite.

Conviene separar en el diseño tres objetos: requisitos del resultado, rutas alternativas que
pueden satisfacerlos y preferencias de costo. Sólo una precondición justificada debe podar
como imposibilidad; una hipótesis de rendimiento debe puntuar o pedir evidencia. Las
capacidades actuales pueden orientar esta separación, pero no validarla por declaración.

## 5. Experimento mínimo que cerraría la tesis de mejora

### Hallazgo de implementación: un diagnóstico que no gobierna la ejecución

La inspección posterior de `../lab/app/runner.py:1145` encontró un punto específico donde
falta cerrar el ciclo. Primero puntúa `result.answer`; luego ejecuta `verify_coverage()` y
`verify_obligations()` y los guarda en la fila. En esa ruta, un `emitted=False` del contrato
no retiene la respuesta evaluada, no cambia su utilidad y no dispara reparación.
`../lab/app/contracts.py:838` implementa `retention()`, que devuelve faltantes y propone
reintento, pero la búsqueda de referencias en `lab/app` no encontró un consumidor que ejecute
esa propuesta. Los usos de `note_retention` son otra cosa: contabilidad de contexto.

Conteo directo del JSONL `gold_h1_rows.jsonl`, sin llamadas ni modificación del registro:

| medida | valor |
|---|---:|
| filas totales | 2.511 |
| filas sin infactibilidad ni error de infraestructura | 1.838 |
| ejecuciones con contrato de completitud evaluado | 225 |
| veredictos de rechazo | 10, sobre 6 tareas |
| utilidad media de las 10 rechazadas | 0,12381 |
| rechazadas con utilidad 1 | 0 |
| utilidad media de las 215 admitidas | 0,75173 |

Son ejecuciones, no tareas independientes ni un panel pareado. El conteo indica que existe
una señal de déficit; no mide mejora por aplicarla ni ausencia general de falsos positivos.
El contrato de prosa detecta menciones faltantes en un dominio declarado: mencionar cada
persona tampoco garantiza que sus datos sean correctos. No usar `relevant_units` para armar
ese dominio; debe venir del request.

**Candidato concreto recomendado:** ante una enumeración con dominio explícito, el código
identifica qué elementos no fueron atendidos, dirige una única reparación a esos elementos,
reverifica y emite o difiere. Comparar base, sólo retención, reparación dirigida por déficit y
un reintento genérico de presupuesto comparable. Ese último control separa el valor del
diagnóstico del beneficio de simplemente gastar una llamada más. Medir también regresiones
en lo ya correcto. El lazo de reparación no está ejecutado en la ruta revisada; implementarlo
y medirlo sería trabajo nuevo, no evidencia ya adquirida.

### Otras pruebas que conservan su lugar

Primero elegir una decisión que ya exista y congelar su implementación. La ruta más cercana
es P32, complementada por una ablación del ancla. Para demostrar una decisión del motor durante
la ejecución, elegir un contrato anterior e implementarlo antes de describirlo como método.

Comparar sobre tareas nuevas, con el mismo modelo, recuperación, presupuesto y configuración:

- ejecutor base;
- ejecutor con la decisión concreta bajo código;
- cuando corresponda, la misma intervención aplicada siempre, para separar el beneficio del
  mecanismo del beneficio de decidir cuándo usarlo;
- mejor fijo del catálogo, para conservar el objetivo original del producto.

Registrar decisiones y secuencias de nodos, además de utilidad, costo, respuestas incorrectas,
abstenciones y cobertura. Si se cobra el diferimiento, fijar su costo antes de medir. No contar
como mejora una reducción de errores obtenida simplemente dejando de responder todo.

Para ahorro con calidad conservada, fijar un margen de no inferioridad δ antes de los datos y
exigir que el límite inferior del IC de Δu sea mayor que −δ. Para mejora de calidad, exigir
evidencia de Δu positiva bajo el protocolo del repo. Una prueba por tarea retenida ayuda al
desarrollo; el veredicto final requiere datos no usados para elegir señales, umbrales o reglas.
El held-out ya explorado en P40 no debe convertirse en el nuevo conjunto de ajuste y seguir
llamándose evaluación final intacta.

No bajar el piso de ocho episodios ni reformar EXIGE usando el resultado como criterio de éxito.
Registrar la nueva hipótesis y evaluar después. Estas propuestas no sustituyen P31–P38 ni
cambian retroactivamente sus criterios.

## 6. Correcciones de rigor antes de reforzar el relato

- **§4.3, proposición 2:** una clave ELICITED no obliga a que cambie la acción. Contraejemplo:
  κ varía entre a y b y θ(a)=θ(b). Debe decir que puede introducir variación, salvo invariancia
  de θ sobre todos los valores alcanzables. Una clave COMPUTED sólo conserva la trayectoria
  completa si los brazos también cumplen las premisas de la proposición 1.
- **§3:** «Jamás maneja flujo de control» requiere acotar a las compuertas del controlador.
  §4.1 admite ramas delegadas tipadas en los brazos. El código que aplica una decisión y el
  origen de la información que determina esa decisión son cosas distintas.
- **§5.3:** EXIGE se define como necesidad, pero tiene contraejemplos conocidos. Identificarlo
  como hipótesis de requisitos por ruta y actualizar el estado con P39.
- **§1.1 y §5.6:** «no hay premio» es demasiado tajante frente a una brecha neta pequeña pero
  positiva con el estimador calibrado. Declarar tamaño y sensibilidad al estimador. Compartir
  capacidades declaradas tampoco prueba que esa sea la causa de un premio pequeño.
- **§5.7:** retirar la inferencia «dice cuándo no hace falta verificar». El acuerdo observado
  apoya calibración de credencia; el mismo paper aclara que no eleva procedencia.
- **P40, si se incorpora:** `ΣπG/ΣνL` usa márgenes de todos los brazos, incluidos destinos
  mutuamente excluyentes para una misma tarea. No es sin más una tasa universal máxima de
  error de cualquier selector. El teorema usa G y L condicionados a lo efectivamente ruteado;
  el script calcula promedios no condicionados a una política. Conservar la asimetría medida,
  formalizar supuestos adicionales antes de llamar cota universal al 16%.
- **P40 y abstención:** a utilidad de acierto, abstenerse puede puntuar igual que equivocarse.
  Para afirmar que baja la pérdida hay que medir la utilidad del diferimiento o el riesgo
  separado; no alcanza con cambiarle el nombre al cero.

## 7. Plan editorial, sin reescritura aplicada

| ubicación | cambio propuesto | evidencia que se conserva |
|---|---|---|
| resumen e introducción | separar garantía estructural, mejora local y objetivo aún abierto | todos los números, alcances y tesis sensor–controlador |
| §3 | explicitar entradas, decisiones y contratos que realmente ejecuta el motor | arquitectura, ejemplo y figuras 1–2 |
| §4 | corregir condiciones de proposición 2 y conectar la identidad con una política real | definiciones, teorema y demostraciones |
| §5.2 | distinguir paquete, ablación y transferencia | datos y figura 3 |
| §5.3 | distinguir capacidades de requisitos necesarios; incluir P39 y fuga del gold | LOAO, nulo, ontología y figura 4 |
| §5.4–5.5 | diferenciar maduración, mejora y no inferioridad | episodios, costos, figura 5 |
| §5.6–5.7 | ajustar afirmaciones de premio y verificación | todos los resultados y figura 6 |
| §6–7 | formular la prueba pendiente de mejora y su condición de fracaso | amenazas y apuestas preregistradas |

No agregar una lista de capacidades deseadas como si fueran resultados. Lo deseado puede orientar
el experimento en este plan; lo que entre al método del paper debe existir y haberse ejecutado.

## 8. Evaluación editorial orientativa

Escala 1–5, juicio de esta revisión y no puntuación objetiva de publicabilidad.

| dimensión | puntuación | motivo |
|---|---:|---|
| contribución respecto del objetivo del autor | 3 | mecanismo valioso; mejora general pendiente |
| formalización | 3 | separación útil de determinismos; proposición 2 requiere corrección |
| literatura | no puntuada | fuentes externas fuera del alcance de esta lectura |
| metodología | 3 | réplicas, negativos y controles; ajuste en muestra y selección de señales |
| argumentación | 2,5 | salta de invariancia a mejora y de capacidades a necesidad |
| reflexión crítica | 4 | límites explícitos y fallos conservados, con conclusiones aún excesivas |

No se calcula nota global sin revisar la literatura.

## 9. Verificación de esta revisión

- [x] Corto leído completo; largo no usado como sustituto de esa lectura.
- [x] P34 y P39 contrastados con resultados guardados; P40 con script, JSON y bitácora.
- [x] Propuestas identificadas como hipótesis y separadas del estado ejecutado.
- [x] Ningún resultado, figura, definición ni referencia del paper eliminado o modificado.
- [ ] Implementar y evaluar la decisión elegida sobre tareas nuevas.
- [ ] Aplicar cambios editoriales una vez acordado el alcance de la reescritura.
