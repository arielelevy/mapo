# Plan de revisión doctoral — `paper-es.md`, borrador 3.0 (v2)

> Estado 2026-09-01, fase 2 ejecutada. Todas las acciones marcadas EDITORIAL de §6 se
> aplicaron sobre `paper-es.md` y su espejo en `paper-corto-es.md`: resumen graduado y con
> agencia corregida, §1.4 Organización, literatura de cascadas, self-consistency, DSPy, Kautz,
> optimizer's curse y skills, tabla §2.8 ampliada, §2.11 nueva, definiciones de γ y región en
> §3, entrada a §5 y Proposición 5.7 nueva, episodio y política definidos en §6.3, PI
> reordenadas con columna de modelo, tablas §7.1 y §7.1.1 reconciliadas contra el registro
> (recomputadas el 2026-09-01: `handoff` 0,604 y 120.500 tokens, `graph_traverse` 52%), §7.4.0
> con Definiciones 7.1 a 7.4 y tabla TIENE, MAE por pliegue, §7.4.3 con la salvedad adelante,
> posicionamiento de §7.5, puente §7.7 → §7.8, §7.8.0 régimen de los episodios (modelo nano
> declarado), bootstrap y Benjamini-Hochberg de P15, agencia del ciclo corregida en §7.8, §8.1
> mezcla de modelos, §8.2 ontología y n=8, §8.3 amenaza de constructo del ciclo, §8.5 impacto
> amplio, §9 y §9.1 alineados con dos pasos nuevos, y dos figuras (interfaz aprendible, ciclo).
> Las acciones CORRIDA siguen pendientes y están en §9.1 del paper. Lo que no se hizo: el
> identificador del estudio del 59,4% en §7.0.1 (no se pudo verificar y no se inventó) y la
> relectura completa de las citas nuevas, que quedan marcadas «citadas por sus afirmaciones de
> portada». Los dos puntos de revelación del texto heredado siguen sin revisar uno por uno.

Fecha: 2026-09-01. Fase 1: análisis y plan. No se tocó el paper.
El plan anterior (borrador 2.0, puntaje autodeclarado 4,76) quedó en
`historico/paper-es_PLAN-borrador-2.0.md`. Este plan no parte de ese puntaje. Parte de leer
el borrador 3.0 entero, la bitácora de predicciones, el código de capacidades y los archivos
de veredicto, y de preguntarse qué diría un revisor que no conoce al autor.

Regla del repo que este plan respeta: nada entra al paper sin implementación que lo corra.
Cada acción de abajo está marcada como EDITORIAL (se puede hacer ya, con lo que existe) o
CORRIDA (exige medir antes; hasta entonces sólo puede aparecer como pendiente en §9.1).

---

## 1. Veredicto en una página

El paper tiene una tesis clara y defendible: un harness cuya decisión es determinista sobre
creencias tipadas, que aprende con los pesos del sensor congelados, y cuya interfaz de
aprendizaje son capacidades declaradas y ejes de la pregunta en vez de nombres de paradigma.
La disciplina de medición (preregistro, piso de ruido por sesgo del máximo, sin juez,
réplicas, held-out) está por encima de lo habitual en la literatura de agentes.

Lo que hoy lo hunde ante un revisor doctoral son cinco cosas, en orden de gravedad:

1. Sobreatribución de agencia en la contribución 3. El paper dice que "el sistema aprendió
   qué sensar". Lo que el registro muestra es que el autor y su asistente leyeron tres
   refutaciones y agregaron ejes al vocabulario a mano. El sistema consume el sensor nuevo,
   no lo descubre. Un revisor lo llama development loop, no plasticidad, y tiene razón.
   Se arregla con redacción honesta, y la contribución sigue siendo valiosa como método.
2. Mezcla de modelos sin declarar. Los tres episodios de §7.8 (P15, P16, P17) corrieron con
   `gpt-5.4-nano` (`results/nano/p1{5,6,7}_verdict.json`). Toda la campaña de §7 corre con
   `gpt-5.6-luna`. El paper no lo dice en ningún lado. Es un defecto de reporte, no de
   medición, pero es exactamente el tipo de omisión que el propio paper audita en otros.
3. Dos tablas del mismo plantel con números distintos. §7.1 y §7.1.1 reportan `reflection`
   0,808 y 0,803; `rewoo` 0,678 y 0,669; `supervisor` 0,591 y 0,581; `graph_traverse` 56% y
   52% de `aplica`. Sin denominador que explique la diferencia. Un revisor deja de confiar
   en el resto de los números.
4. La contribución 2 descansa en ocho puntos. El leave-one-arm-out da `p = 0,065` y el paper
   lo dice. Pero el resumen la enuncia como resultado, y las dos frases más fuertes ("mejor
   que la identidad incluso cuando ve la respuesta", "el catálogo predice un brazo que no
   existe") son una comparación sugestiva y una predicción sin correr. Hay que graduar el
   enunciado o correr el brazo de ausencia.
5. Los teoremas. Proposición 5.4 es inducción trivial, Teorema 1 es una identidad,
   Teorema 2 es soundness por construcción, Proposiciones 4 a 6 son monotonía sobre un
   conjunto finito. El paper es honesto sobre eso. Pero llamarlos teoremas e ir a cs.LG
   invita a la pregunta de por qué están. Y falta el único enunciado formal que la tesis v2
   necesita: la relación entre procedencia de la clave y determinismo de la política.

Puntaje: 3,1 sobre 5. Aceptable, requiere revisión mayor. Con las acciones EDITORIAL de
este plan llega a 3,6. Para pasar de 4 hacen falta las dos CORRIDAS marcadas como
decisivas (brazo de ausencia, ontología desde el request).

---

## 2. Evaluación multidimensional

### D1. Contribución original (25%) — 3,2

| criterio | puntaje | notas |
|---|---:|---|
| Avanza el estado del arte | 3 | La interfaz de capacidades declaradas desde código, con leave-one-arm-out, no tiene antecedente directo. El estimador de piso de ruido y "gradeabilidad implica detector" son aportes metodológicos reales. La máquina es heredada y el paper lo reconoce |
| Genuinamente original | 3 | Como conjunción. Cada pieza tiene vecino publicado (§2.10). La ontología de la pregunta como clave de política es lo más propio, y está medida sobre etiquetas de diseño, no sobre requests |
| Resuelve un problema abierto | 3 | Reformula uno: "qué paradigma gana" pasa a "qué capacidad falta". Es una reformulación buena, con evidencia de que la pregunta anterior no tenía premio |
| Impacto potencial claro | 4 | Cualquier banco de agentes puede adoptar `pass^k`, el piso de ruido y la lectura por capacidades mañana |
| Se distingue de trabajo previo | 3 | Sí en §2.4 y §2.10, pero por conjunción. Y la distinción con HADD está mejor ahora, pero sigue pareciendo defensiva |

Qué sabe el campo después que no sabía antes: que la brecha de oráculo publicada en ruteo
de paradigmas contiene sesgo del máximo y hay un estimador directo; que la interacción
tarea×paradigma vive entre brazos dominados; que las capacidades declaradas predicen un
brazo no visto mejor que su identidad, sobre ocho brazos; que ofrecer una herramienta cambia
la conducta sin usarla. Eso es un paper sólido de conferencia. No es todavía un capítulo
central de tesis, porque la afirmación que haría la diferencia (la ontología se recupera
desde el request y la política aprende sobre ella) está declarada y no medida.

### D2. Marco teórico y formalización (20%) — 2,8

| criterio | puntaje | notas |
|---|---:|---|
| Definiciones formales | 3 | Def. 5.1 a 5.5 bien. Faltan: capacidad, EXIGE, TIENE, capaces (están en código, no en el paper como definiciones); región; clave de política; episodio |
| Teoremas correctamente enunciados | 3 | Correctos. Débiles. T1 y T2 se declaran instrumentos, bien, pero el rótulo "Teorema" sobra |
| Demostraciones | 4 | Completas y verificadas por máquina |
| Notación consistente | 2 | `u` se usa con λ=0 en §7 y con λ en §3; `p⋆` y "mejor fijo" alternan; `γ` es interacción en §7.3 y no se define antes; PI1 a PI8 numeradas por orden de aparición y no por orden lógico |
| Conexión con teoría establecida | 4 | §2.9 es muy bueno. Chow, AGM, Doyle, BDI, Soar, con el supuesto que cada uno rompe |
| Supuestos declarados | 3 | Sí en §5.1.5 y §5.6. Falta el supuesto central de v2: que las capacidades son booleanas y que EXIGE es conjunción, con el contraejemplo ya anotado |

Lo que falta y es barato: una Proposición 5.7 que diga formalmente lo que §7.3.6 mide.
Si la clave de la política es función de `(q, M)` (COMPUTED), la decisión es función de
`(q, M)` y hereda la Proposición 5.4. Si algún eje de la clave es salida del sensor, la
decisión es una variable aleatoria aun con `d(T) = 0`. Es una línea de demostración y es el
puente que la tesis v2 promete en el resumen ("una clave de política tiene que ser
COMPUTED") y nunca formaliza. Y una Definición de capacidad y de "brazo capaz" con la
semántica de conjuntos que ya está en `capacidades.py`.

### D3. Dominio de la literatura (15%) — 3,0

| criterio | puntaje | notas |
|---|---:|---|
| Conocimiento del campo | 3 | Muy bueno en ruteo de paradigmas y gobernanza simbólica. Con huecos abajo |
| Fundacionales clásicos | 4 | §2.9 los cubre con criterio |
| Recientes | 3 | Sí, con búsquedas fechadas. Faltan líneas enteras |
| Análisis crítico | 4 | Las cesiones y las lecturas completas son ejemplares |
| Gaps genuinos | 3 | Sí, pero el gap principal (ruteo sobre capacidades) no está contrastado contra la literatura de skills/tool routing |
| Posicionamiento honesto | 3 | HADD ahora sí. La tabla §2.8 sigue en marco v1: compara cobertura, abstención y factibilidad, no la interfaz de aprendizaje |

Huecos que un experto nota de inmediato:

| falta | dónde pega | por qué importa |
|---|---|---|
| FrugalGPT (Chen, Zaharia, Zou, 2023) y la línea de cascadas de LLM (HybridLLM, RouterBench, RouteLLM) | §5.2 dominancia de la cascada, §2.2 | §5.2 reinventa la cascada con detector sin citar al trabajo que la fundó. Un revisor de cs.LG lo marca en la primera página |
| Self-consistency (Wang et al., 2022) y Universal Self-Consistency (Chen et al., 2023) | §7.5 consenso | El consenso entre paradigmas es self-consistency con muestreadores heterogéneos. Hay que decirlo y decir qué agrega: heterogeneidad de control de flujo, réplica entre familias, credencia sin procedencia |
| Sesgo del máximo / winner's curse en selección de modelos (Jensen, "optimizer's curse", Smith y Winkler 2006) | §7.3.3 piso de ruido | El estimador es propio; el fenómeno tiene nombre y literatura. Citarla fortalece, no debilita |
| DSPy y la línea "LM como módulo dentro de un programa" (Khattab et al., 2023) | §2, §6.2 sensor | Es el antecedente de ingeniería más cercano a "el flujo de control vive en el código" |
| Kautz, taxonomía neurosimbólica | §2.4 | Se nombra Type-2 vía HADD; hay que citar la fuente |
| Ruteo por habilidades/skills y agent cards (A2A, "skill-based routing") | §7.4 | Es el vecino de "capacidades declaradas"; distinguir: acá son booleanos verificables contra código, no descripciones en texto |
| Literatura de tool-use y efecto de la especificación de herramientas | §7.9.2 | El efecto de oferta parece nuevo. Hay que buscar antes de reclamarlo (búsqueda fechada, como el resto) |

Conteo actual: 56 identificadores citados. Suficiente en número, desbalanceado en cobertura.

### D4. Rigor metodológico (20%) — 3,4

| criterio | puntaje | notas |
|---|---:|---|
| Diseño apropiado para las afirmaciones | 3 | Para contribuciones 1 y 4, sí. Para 2, ocho brazos. Para 3, episodios sobre otro modelo que la campaña |
| Baselines | 4 | Doce paradigmas, mejor fijo, siempre-react, nulos por permutación, nulo de capacidades barajadas |
| Métricas formales | 4 | `u`, `pass^k`, brecha neta, piso de ruido, todas definidas |
| Estadística | 3 | Piso de ruido y permutaciones sí. Intervalos de confianza casi no aparecen en §7 (la bitácora tiene bootstraps pareados de P15 que el paper no usa). Wilson en §7.5 sí |
| Reproducibilidad | 4 | Caché content-addressed, huella de decodificación, manifiestos, verificador independiente |
| Ablaciones | 3 | Las cuatro correcciones de `pointer_chase` son una intervención, no una ablación una a una. §7.2.6 lo admite |
| Casos de fallo | 4 | §7.2.3 modos de falla; el contraejemplo de EXIGE escrito |

Defectos concretos a corregir:

- Modelo por episodio. §7.8 no declara que P15, P16 y P17 corrieron con `nano`. Debe
  declararlo en cada tabla y en §8.1, y decir qué transfiere: el mecanismo (eje faltante) sí,
  las magnitudes no.
- Dos rectángulos, dos vocabularios, un titular. El "42% de ahorro" del resumen sale de una
  señal suelta sobre 59×8 con `λ` implícito; el "0,951 y 46%" sale de la política entera
  sobre 41×7 con otro vocabulario. Los dos se reportan, bien, pero el resumen cita uno como si
  fuera la política. Declarar cuál es la política y cuál la señal.
- §7.9.1 condiciona sobre una variable post-tratamiento y lo dice. Bien. Pero la tabla de
  participaciones de varianza sobre grupos desbalanceados no debería ir con dos decimales.
- §7.4.1 compara MAE de cuatro modelos sobre ocho pliegues sin intervalo. Con `n = 8` hay
  que reportar el rango por pliegue, no sólo la media.
- La corrección por comparaciones múltiples (Benjamini-Hochberg) que la bitácora aplicó a
  P15 no está en el paper. Debe estar, porque es la que dice que "no sobrevive ningún
  contraste".

### D5. Argumentación y coherencia (10%) — 3,0

| criterio | puntaje | notas |
|---|---:|---|
| Flujo lógico | 3 | v2 arregló el resumen y la conclusión. El cuerpo sigue en orden v1: §7.3 (negativo) antes de §7.4 (interfaz), y §7.7 (held-out del ruteo por identidad) después del consenso, sin puente |
| Afirmaciones soportadas | 3 | Casi todas. Las de agencia ("el sistema aprendió") no |
| Sin gaps | 3 | §5.1 y §5.2 (teoría del ruteo) no se conectan con la tesis v2. Son el instrumento que mostró que el premio era cero; hay que decirlo al entrar a §5 |
| Transiciones | 2 | Las secciones nuevas (§7.8, §7.9) están pegadas al final de §7 sin una oración que las anuncie en §7.0 más allá de la tabla de PI |
| Tesis coherente | 4 | Sí, y es una sola |
| Sin contradicciones | 2 | Las tablas de §7.1 y §7.1.1. "Éste es el resultado que reordenó el programa" en §7.3 y "la interfaz aprendible es la contribución principal" en el resumen conviven, pero el lector llega primero al negativo |

### D6. Reflexión crítica (10%) — 3,3

| criterio | puntaje | notas |
|---|---:|---|
| Limitaciones honestas | 4 | §8 es de lo mejor del paper |
| Amenazas a la validez | 4 | Interna, externa, constructo, reproducibilidad |
| Implicaciones prácticas | 3 | §7.6 las da; falta enunciar qué cambia para quien construye un harness hoy |
| Implicaciones teóricas | 3 | La condición "clave COMPUTED" es una implicación teórica y no está enunciada como tal |
| Trabajo futuro fundamentado | 4 | §9.1 en orden y atado a limitaciones |
| Impacto amplio / ética | 1 | Ausente. El paper invoca el Reglamento de IA y el RGPD en §1.1.1 y nunca vuelve: qué significa que un sistema se abstenga ante un auditor, quién responde por un piso aprendido, qué pasa si la ontología clasifica mal una pregunta regulada |

Y la amenaza que falta, la más importante: la contribución 3 la ejecutaron personas. Debe ir
en §8.3 como amenaza de constructo, con el nombre correcto: lo que se midió es un ciclo de
desarrollo dirigido por refutaciones preregistradas, y lo que el sistema hace hoy es
consumir sensores COMPUTED que ese ciclo produjo. La automatización del ciclo (que la
consolidación proponga el eje) está en §6.3 como diseño y no corrió.

### Puntaje

```
D1 3,2 × 0,25 = 0,80
D2 2,8 × 0,20 = 0,56
D3 3,0 × 0,15 = 0,45
D4 3,4 × 0,20 = 0,68
D5 3,0 × 0,10 = 0,30
D6 3,3 × 0,10 = 0,33
              = 3,12   Aceptable, revisión mayor
```

---

## 3. Inventario de contenido

Todo lo de abajo se preserva. Nada se borra.

### A. Conceptos y definiciones

| # | concepto | ubicación | estado |
|---|---|---|---|
| 1 | arnés / harness | Resumen, §1.1 | informal, suficiente |
| 2 | sensor estocástico | Resumen, §6.2 | informal |
| 3 | base de creencias, procedencia, credencia | §6.2, §7.5.3 | informal; el retículo se enuncia, no se define |
| 4 | trayectoria, punto de ramificación delegado, confinamiento, `pass^k` | §5.0 Def. 5.1 a 5.5 | formal |
| 5 | tarea, paradigma, calidad, costo, utilidad, mejor fijo, oráculo, brecha | §3 | formal |
| 6 | ley de costo (estructural, vueltas, alcance) | §3, §7.1.3 | informal, medida |
| 7 | factibilidad (Algoritmo 3) | §4 | formal en pseudocódigo |
| 8 | S₊, S₀, S₋, π, α, β, G, L, ρ, L̄ | §5.1 | formal |
| 9 | cascada, detector, sensibilidad `s`, partición `v` | §5.2 | semiformal |
| 10 | plantilla, ranura, `fill`, piso `φ` | §5.3 | formal |
| 11 | niveles de garantía, ratchet, `max` | §5.4, §5.5 | formal |
| 12 | región, vocabulario de región, eje | §6.3.4, §7.3.6, §7.8 | informal; nunca definida |
| 13 | capacidad, TIENE, EXIGE, capaces | §7.4 | informal en el paper; formal en código |
| 14 | ontología de la pregunta, eje ontológico, etiqueta de diseño | §7.0, §7.4.3 | informal |
| 15 | episodio, consolidación, política, bundle firmado | §6.3 | informal |
| 16 | recall de evidencia, releído, racha estéril | §7.9 | informal, medidos |
| 17 | consenso, `k`, credencia calibrada | §7.5, Algoritmo 2 | semiformal |

### B. Afirmaciones y soporte

| # | afirmación | ubicación | soporte |
|---|---|---|---|
| 1 | 17 a 34% de celdas inestables a t=0 | §7.2.2 | medido, 59×8, tres réplicas |
| 2 | `pointer_chase` 0,33 → 0,89 por cuatro correcciones de flujo | §7.2.4 | medido, una celda, tres réplicas |
| 3 | varianza no crece con número de ramificaciones, r = −0,24 | §7.2.6 | medido, n = 8, declarado débil |
| 4 | dial gratis hasta A2, A3 cuesta 60% del catálogo y 31% de utilidad | §5.4 | medido |
| 5 | interacción 48% explicada / 39% total, premio neto −0,008 | §7.3 | medido, 59×8 |
| 6 | sólo `cardinalidad × término` sobrevive la corrección por selección | §7.3.2 | medido, permutaciones |
| 7 | desempate por costo 42% a −0,017 LOTO | §7.3.5 | medido, 59×8 |
| 8 | política con literal 0,951 / 46% vs 0,928 / 37% LOO | §7.3.5, §7.8.3 | medido, 41×7, otro vocabulario |
| 9 | eje elicitado cambia en 27% de tareas entre modelos | §7.3.6 | medido, 26 tareas |
| 10 | capacidades MAE 0,233 vs identidad 0,339, 6/8 pliegues, p = 0,065 | §7.4.1, §7.4.2 | medido, n = 8, no establecido |
| 11 | ningún brazo junta cobertura garantizada con abstención sin prueba | §7.4 | derivado del catálogo, no corrido |
| 12 | ontología separa 40% más por segmento; contradicción S/R 1,82 con partición binaria | §7.4.3 | medido sobre etiqueta de diseño |
| 13 | C5 y C8 idénticos en seis campos computables | §7.4.3 | medido |
| 14 | consenso k ≥ 4 → 180/180; réplica en segunda familia 1,000 | §7.5 | medido, preregistrado |
| 15 | consenso no abarata: 56 cascadas suben costo | §7.5.2 | medido |
| 16 | 211× de precio contra ventana frontera | §7.6.1 | inferido de aranceles, no medido |
| 17 | held-out: brecha neta negativa en tres estratos | §7.7.1 | medido, 26×12×3 |
| 18 | no hay mejor fijo estable | §7.7.2 | medido |
| 19 | P15 −0,087, mecanismo eje de horizonte, 26/26 | §6.3.4, §7.8.1 | medido, nano, preregistrado |
| 20 | continuidad separa C5 6/6 sin falsos positivos | §7.8.1 | medido, tres corpus |
| 21 | fragmentación 12/26 → 0/26; jerárquico 16/26 | §7.8.1 | medido |
| 22 | barrido λ: +0,121 a λ=0, −0,404 a λ=0,02 | §7.8.2 | medido, nano, preregistrado |
| 23 | cascada 22 → 2 con detectores honestos; sonda 14 dispara, 0 resuelve | §7.8.2 | medido, nano |
| 24 | recall completo vs parcial +0,533, 4,2× la brecha entre paradigmas | §7.9.1 | medido, gold_transfer |
| 25 | participación en varianza del recall: región 5,2%, paradigma 62,2%, tarea 10,5% | §7.9.1 | medido, grupos desbalanceados |
| 26 | efecto de oferta: 1,57× más barato, u idéntica, 3/63 llamadas, releído 8,8× menos | §7.9.2 | medido, luna, preregistrado |
| 27 | reenvío 99% de la entrada; turno 8 = 110,8× turno 0 | §7.9.3 | medido, traza |
| 28 | 33% de tokens evitables; racha 1,17 vs 2,28 | §7.9.3 | medido; regla P20 no corrió |
| 29 | Trace2Policy: la versión de la regla explica más varianza que el modelo | §2.10 | citado |
| 30 | 59,4% de fallos de un benchmark de código eran del arnés | §7.0.1 | citado sin identificador |
| 31 | el sistema aprendió qué sensar | Resumen, §7.8.4, §9 | no soportada como enunciada |

### C. Contenido técnico

| # | tipo | descripción | ubicación | completo |
|---|---|---|---|---|
| 1 | Algoritmo 3 | compuerta de factibilidad | §4 | sí |
| 2 | Algoritmo 1 | caminata determinista sobre cadena de referencias | §7.2.4 | sí |
| 3 | Algoritmo 2 | verificación por consenso | §7.5.2 | sí |
| 4 | Proposición 5.4 | localización | §5.0 | sí |
| 5 | Teorema 1 y corolarios 1, 2, 2b, 3 | valor de selección | §5.1 | sí |
| 6 | Teorema 2 | soundness del ensamblador | §5.3 | sí |
| 7 | Proposiciones 4, 5, 6 | ratchet, replicación, `max` | §5.4, §5.5 | sí |
| 8 | catálogo de capacidades, tabla EXIGE | §7.4 | parcial: TIENE no se muestra |
| 9 | arquitectura del motor (cuatro pasos) | Resumen, §6 | prosa |
| 10 | consolidación en tres pasos, seis superficies | §6.3 | prosa |
| 11 | plantel de doce paradigmas por ley de costo | §3 | tabla |

### D. Figuras y tablas

| # | tipo | descripción | ubicación | referenciada |
|---|---|---|---|---|
| 1 | Figura 1 | contrato de garantía | Resumen | sí |
| 2 | Figura | método determinista | "Cómo se decide un request" | sí |
| 3 | Figura | aplica contra aporta | §7.1.1 | sí |
| 4 | Figura | degradación por ancho | §7.1.2 | sí |
| 5 | Figura | espacio de capacidades | §7.1.4 | sí |
| 6 | Figura | utilidad contra costo | §7.1.5 | sí |
| 7 | Figura | ley de costo | §7.1.6 | sí |
| 8 | Figura | embudo ver contra usar | §7.2.1 | sí |
| 9 | Figura | modos de falla C3 | §7.2.3 | sí |
| 10 | Figura | sensor determinista | §7.2.4 | sí |
| 11 | Figura | flujo del Algoritmo 1 | §7.2.4 | sí |
| 12 | Figura | latencia serial | §7.2.5 | sí |
| 13 | Figura | predictores de la interacción | §7.3.2 | sí |
| 14 | Figura | EDA de capacidades | §7.4.1 | sí |
| 15 a 40 | tablas | 26 tablas, todas referenciadas en su párrafo | varias | sí |

Sin figura: §7.8 (el ciclo), §7.9 (predictores), §5.5 (el `max`). Ver §5 de este plan.

### E. Ejemplos

| # | ejemplo | ubicación | propósito claro |
|---|---|---|---|
| 1 | `'M. Arrieta settlement account'` tipado antes de usar | "Cómo se decide", §7.2.4 | sí |
| 2 | `Ramiro Herrera` y `M. Arrieta` en índice híbrido vs léxico | §7.2.4 | sí |
| 3 | tres tareas que rompen el umbral clásico de β | §5.1.2 | sí |
| 4 | tres grupos que rompen unimodalidad | §5.1.3 | sí |
| 5 | «el saldo NO supera {x}» sound y falso | §5.3 | sí |
| 6 | `dag_strategy` resuelve C3 por otra ruta | §7.4.2 | sí |
| 7 | tarea de una unidad infactible para Direct | §4.2 | sí |

### F. Datos y resultados

Campaña 78×12×3 (121,4M tokens, luna); held-out 26×12×3 (48,5M); réplica terra 23×8×1
(209 celdas); episodios nano P15 (390 celdas), P16 (390 filas), P17 (390 filas); P30 63
celdas; barrido de factibilidad 168 tareas × 5 corpus; 567 ceros auditados; 573 aserciones.

Total inventariado: 17 conceptos, 31 afirmaciones, 11 piezas técnicas, 14 figuras, 26
tablas, 7 ejemplos, 8 conjuntos de datos.

---

## 4. Análisis de gaps

### Estructurales

- [x] Resumen con problema, gap, enfoque, contribuciones, resultados
- [x] Contribuciones enumeradas
- [ ] Organización del paper (párrafo de mapa). Falta
- [ ] Formalización de la interfaz aprendible (capacidad, EXIGE, capaces, clave). Falta
- [x] Tabla comparativa de trabajo relacionado (§2.8). Está en marco v1, hay que actualizarla
- [x] Preguntas de investigación (PI1 a PI8). Numeradas por aparición, hay que reordenar
- [x] Diseño experimental (§7.0). Falta la columna "modelo" por sección
- [x] Limitaciones y amenazas (§8)
- [ ] Impacto más amplio. Falta
- [x] Trabajo futuro (§9.1)
- [x] Referencias. Faltan líneas (ver D3)

### Elementos formales faltantes

| elemento | tipo | dónde | prioridad |
|---|---|---|---|
| capacidad, TIENE, EXIGE, capaces(e) = {p : EXIGE(e) ⊆ TIENE(p)} | Definición | nueva §5.6 o §7.4.0 | alta |
| región y clave de política como función de (q, M) | Definición | §6.3 | alta |
| "clave COMPUTED ⇒ decisión determinista; clave ELICITED ⇒ variable aleatoria" | Proposición con demostración de una línea | nueva §5.7, apoyada en Prop. 5.4 | alta |
| episodio y política consolidada | Definición | §6.3 | media |
| protocolo leave-one-arm-out y nulo de capacidades barajadas | Definición del procedimiento | §7.4.1 | media |
| piso de ruido por sesgo del máximo | Definición (hoy es una caja de texto) | §6.1 o §7.3.3 | media |
| ontología por eje: qué es un eje, vocabulario cerrado | Definición | §7.4.3 | media |
| `γ` interacción | Definición antes de §7.3.1 | §3 | baja |

### Transiciones faltantes

| de | a | transición |
|---|---|---|
| §5 (teoría del ruteo) | tesis v2 | una entrada a §5 que diga que T1 y §5.2 son el instrumento que mostró que el premio por identidad era cero, y que §5.7 es el puente hacia la interfaz aprendible |
| §7.3 | §7.4 | cerrar §7.3 con la oración que abre §7.4: los contendientes empatan porque tienen las mismas capacidades |
| §7.7 | §7.8 | §7.7 es el held-out del ruteo por identidad; hoy queda huérfano después del consenso. Debe presentarse como el episodio cero del ciclo, o moverse antes de §7.8 con un puente |
| §7.0 | §7.8, §7.9 | una oración en el régimen de medición que anuncie que dos secciones usan otro modelo y otro registro |
| §8 | §9 | el impacto amplio faltante |

### Contexto faltante

| contenido | falta | sugerencia |
|---|---|---|
| §7.8 | quién ejecutó el ciclo, con qué modelo, cuánto costó cada episodio | tabla de episodios con columnas modelo, tokens, fecha de registro |
| §7.4.2 | por qué ocho brazos y no doce en el leave-one-arm-out | declarar el criterio de rectángulo |
| §7.9.1 | qué corpus (gold_transfer, nano) | declarar |
| §7.0.1 | identificador del estudio del 59,4% | citar |
| §2.4 fila HADD | que la afirmación "no está disponible" se verificó en fecha | ya está; agregar la fecha a la fila |

---

## 5. Plan de reorganización

Principio: mismo contenido, orden que sigue la tesis v2. Ningún párrafo se elimina.

### Mapa de movimientos

| origen | contenido | destino | acción |
|---|---|---|---|
| §7.3 entero | premio de calidad cero entre brazos capaces | §7.3, sin mover | agregar cierre que remite a §7.4 |
| §7.4 | capacidades | §7.4, sin mover | anteponer §7.4.0 con las definiciones formales nuevas |
| §7.7 held-out | ruteo por identidad fuera de muestra | nuevo §7.8.0 "Episodio cero: el held-out por identidad" o dejar en §7.7 con puente | mover completo o puentear; recomendación: puentear, no mover, para no romper referencias cruzadas |
| §6.3.4 | P15 refutación | queda; agregar referencia cruzada a §7.8.1 | ninguna |
| §5.1.5 último bloque | "los términos nunca se separaron", AURC 0 | queda; referenciar desde §7.8.2 | ninguna |
| §7.9.4 tabla de predictores | resumen de predictores | queda; referenciar desde §6.3.2 (superficies) | ninguna |
| §1.1.1 normativa | RGPD, Reglamento de IA | queda; nuevo §8.5 impacto amplio la retoma | ninguna |

### Secciones nuevas

| sección | título | fuentes | propósito |
|---|---|---|---|
| §1.4 | Organización del paper | todas | mapa; elemento requerido |
| §5.6bis o §5.7 | La clave de la política y su procedencia | §7.3.6, Prop. 5.4 | el único enunciado formal que la tesis v2 necesita |
| §7.4.0 | Definiciones: capacidad, exigencia, brazo capaz | `capacidades.py`, §7.4 | formalizar lo que hoy es prosa |
| §7.8.0 | Régimen de los episodios | bitácora, `results/nano` | declarar modelo, fechas, costo por episodio |
| §8.3bis | Amenaza de constructo: quién ejecutó el ciclo | §7.8 | la más importante que falta |
| §8.5 | Impacto más amplio | §1.1.1, §5.5, §7.5.3 | abstención ante auditores, pisos aprendidos, clasificación errada en dominio regulado |

### Contenido a mejorar sin eliminar

| contenido | estado | mejora |
|---|---|---|
| §7.1 y §7.1.1 | dos tablas, números distintos | conservar ambas, declarar el rectángulo de cada una, o reconciliar contra el registro y explicar la diferencia en una nota. Verificar contra `results/luna` antes de tocar un número |
| Resumen, contribución 3 | "el sistema aprendió" | reescribir: "el ciclo de desarrollo, dirigido por refutaciones preregistradas, produjo tres sensores COMPUTED que el sistema consume; la automatización del paso está diseñada en §6.3 y no medida" |
| Resumen, contribución 2 | enunciada como resultado | graduar: "predicen mejor que la identidad sobre ocho brazos, sin cruzar su nulo (p = 0,065)"; el hueco predicho como predicción registrada |
| Resumen, contribución 4 | "42% de costo" | decir de qué panel y que es una señal, no la política; o citar 46% de la política sobre 41×7 |
| §2.8 tabla de posicionamiento | marco v1 | agregar columnas "aprende sobre" y "clave de la política" |
| §5 encabezado | sin entrada | agregar párrafo de entrada que ubique T1, T2 y la nueva §5.7 respecto a la tesis |
| §7.0 tabla PI | orden de aparición | reordenar PI por contribución: máquina (PI1), interfaz (PI5, PI6), ciclo (PI7, PI2, PI3), lo que compra (PI8, PI4). Conservar los ocho |
| §7.4.1 tabla MAE | medias | agregar rango por pliegue |
| §7.5 | sin antecedente de self-consistency | agregar párrafo de posicionamiento |
| §5.2 | sin FrugalGPT | agregar cita y una oración de qué agrega la partición por verificabilidad |
| §7.9.1 tabla de participaciones | dos decimales | un decimal, con la advertencia ya escrita |
| Referencias | 56, desbalanceadas | agregar las siete líneas de D3 con búsqueda fechada |

### Adiciones estructurales

| adición | ubicación | propósito |
|---|---|---|
| párrafo de entrada | §5, §7.8, §7.9 | señalizar |
| oración puente | fin de §7.3, fin de §7.7 | flujo hacia la tesis |
| figura del ciclo | §7.8.4 | los tres episodios como lazo: refutación → eje faltante → sensor COMPUTED → nuevo mundo. Es la figura que la contribución 3 no tiene |
| figura de la interfaz | §7.4.0 | pregunta → ejes → capacidades → brazos capaces → costo. Existe en prosa tres veces y en imagen ninguna |

---

## 6. Plan detallado por sección

### Resumen
Estado: v2, cuatro contribuciones. Objetivo: mismas cuatro, enunciadas con su soporte real.
Acciones (EDITORIAL):
1. Contribución 2: agregar "sobre ocho brazos, sin cruzar su nulo" y "predicción registrada" para el hueco.
2. Contribución 3: reemplazar agencia del sistema por agencia del ciclo. Conservar los números.
3. Contribución 4: declarar panel del 42% o usar 46% de la política. Conservar ambos en el cuerpo.
4. Agregar una oración con el modelo de la campaña y el de los episodios.

### §1 Introducción
Estado: 1.1, 1.1.1, 1.1.2, 1.2, 1.3. Objetivo: agregar 1.4 Organización.
Acciones (EDITORIAL):
1. §1.4 nuevo, un párrafo.
2. §1.1.2: la frase "42% de ahorro" con su panel.
3. §1.3.1: declarar que §7.8 corre sobre otro modelo.

### §2 Trabajo relacionado
Acciones (EDITORIAL, con búsqueda fechada para cada cita nueva):
1. §2.2: FrugalGPT, HybridLLM, RouterBench, RouteLLM. Una oración cada uno y qué no tienen (abstención, detector declarado, capacidades).
2. §2.4: agregar Kautz como fuente. Fecha de verificación en la fila de HADD.
3. §2.5 o nueva §2.5bis: Self-Consistency y Universal Self-Consistency; qué agrega §7.5.
4. §2.6: DSPy como antecedente de "LM como módulo".
5. Nueva §2.11: ruteo por habilidades y agent cards; qué distingue a las capacidades declaradas.
6. §2.8 tabla: dos columnas nuevas.
7. Nota en §7.3.3 con la literatura del sesgo del máximo.

### §3 Preliminares
Acciones (EDITORIAL):
1. Definir `γ` y el modelo aditivo antes de §7.3.
2. Aclarar que `u` en §7 es con `λ = 0` salvo indicación, una sola vez y al principio.

### §4 Factibilidad
Sin cambios de contenido. Acción: ninguna.

### §5 Teoría
Acciones (EDITORIAL):
1. Párrafo de entrada: T1 y §5.2 son el instrumento; §5.3 a §5.5 la máquina; §5.7 el puente.
2. Nueva §5.7: Definición de clave de política; Proposición: si la clave es función de (q, M), la decisión hereda 5.4; si depende del sensor, la decisión es variable aleatoria aun con d(T) = 0. Demostración por composición de funciones. Referencia a §7.3.6 como la medición.
3. Considerar rebajar "Teorema" a "Proposición" en T1 y T2. Es decisión del autor; el plan lo recomienda y no lo impone.

### §6 Diseño
Acciones (EDITORIAL):
1. §6.3: definir episodio y política consolidada.
2. §6.3.2: referencia cruzada a §7.9.4 (predictores medidos por superficie).
3. §6.3.4: referencia cruzada a §7.8.1 y declarar modelo nano.

### §7 Resultados
Acciones:
1. §7.0 (EDITORIAL): reordenar PI por contribución conservando los ocho; agregar columna "modelo y registro" a la tabla; una oración que anuncie §7.8 y §7.9.
2. §7.1 y §7.1.1 (EDITORIAL con verificación contra el registro): reconciliar las dos tablas o declarar por qué difieren. No inventar un número: correr el script de la tabla y copiar.
3. §7.3 (EDITORIAL): oración de cierre hacia §7.4. Literatura del sesgo del máximo en la caja.
4. §7.4.0 (EDITORIAL): definiciones formales de capacidad, TIENE, EXIGE, capaces. Mostrar la tabla TIENE completa (hoy sólo EXIGE). Figura de la interfaz.
5. §7.4.1 (EDITORIAL): rango por pliegue.
6. §7.4.3 (EDITORIAL): definir eje y vocabulario cerrado; decir que la medición usa la etiqueta de diseño en la primera oración, no al final.
7. §7.5 (EDITORIAL): posicionamiento frente a self-consistency.
8. §7.7 (EDITORIAL): párrafo puente hacia §7.8.
9. §7.8.0 (EDITORIAL): régimen de los episodios: modelo `gpt-5.4-nano`, fechas, tokens (14,07M; 13,95M; 12,69M), scripts de veredicto congelados. Tabla.
10. §7.8.4 (EDITORIAL): reescribir "lo que aprendió el sistema" como "lo que produjo el ciclo"; figura del lazo.
11. §7.8 (EDITORIAL): agregar el bootstrap pareado y Benjamini-Hochberg de P15 que la bitácora tiene y el paper no.
12. §7.9.1 (EDITORIAL): declarar corpus y modelo; un decimal en participaciones.
13. §7.4 (CORRIDA, decisiva): construir y correr el brazo de ausencia. Hasta entonces, el hueco es predicción registrada.
14. §7.4.3 (CORRIDA, decisiva): clasificador de ejes desde el request (ONT-1). Hasta entonces, la ontología es resultado sobre etiquetas de diseño.
15. §7.9.3 (CORRIDA): regla de parada P20. Hasta entonces, señal medida y regla pendiente, como está.
16. §7.6 (CORRIDA, barata): ventana frontera sobre 18 tareas anchas.

### §8 Limitaciones
Acciones (EDITORIAL):
1. §8.1: agregar la mezcla de modelos entre campaña y episodios, y qué transfiere.
2. §8.3: nueva amenaza de constructo: el ciclo lo ejecutaron personas. Nombrar qué parte está automatizada (consumo del sensor, consolidación con guarda) y cuál no (proponer el eje).
3. §8.3: la ontología se midió sobre etiquetas de diseño.
4. Nueva §8.5 Impacto más amplio: abstención ante un auditor, responsabilidad sobre pisos aprendidos, clasificación errada de una pregunta regulada, uso del sistema para justificar decisiones con procedencia impecable y valor superado (C8).

### §9 Conclusión
Acciones (EDITORIAL):
1. Alinear la fila "El ciclo" de la tabla con la redacción honesta de agencia.
2. §9.1: agregar al orden "automatizar la propuesta de eje en la consolidación" como el paso que convertiría el ciclo en plasticidad del sistema.

### Referencias
Acciones (EDITORIAL): agregar las siete líneas de D3 con fecha de búsqueda; identificador del estudio del 59,4%.

---

## 7. Checklist final

Preservación
- [ ] 17 conceptos presentes
- [ ] 31 afirmaciones presentes, con la 31 reescrita y no borrada
- [ ] 14 figuras y 26 tablas presentes; las dos tablas de §7.1 conservadas y reconciliadas
- [ ] 7 ejemplos presentes
- [ ] Algoritmos 1 a 3, Proposición 5.4, Teoremas 1 y 2, Proposiciones 4 a 6 intactos

Cumplimiento
- [ ] §1.4 Organización
- [ ] §5.7 clave de la política, con demostración
- [ ] §7.4.0 definiciones de capacidad
- [ ] §7.8.0 régimen de los episodios con modelo declarado
- [ ] §8.3 amenaza de constructo del ciclo
- [ ] §8.5 impacto más amplio
- [ ] Siete líneas de literatura agregadas con fecha
- [ ] Tabla §2.8 actualizada
- [ ] PI reordenadas y conservadas

Estilo (estilo-ariel.md)
- [ ] sin guión largo en prosa
- [ ] negrita sólo en rótulos
- [ ] sin "no es X, sino Y"
- [ ] los dos puntos de revelación del texto heredado, revisados uno por uno

Regla del repo
- [ ] ninguna CORRIDA aparece en el cuerpo como resultado hasta que corra
- [ ] el paper corto recibe los mismos cambios EDITORIAL, en la misma posición

Puntaje esperado tras EDITORIAL: 3,6. Tras las dos CORRIDAS decisivas, si salen como se
predijo: 4,1 a 4,3.
