# Revisión de narrativa, 2026-09-01

Sobre `paper-es.md` (borrador 3.0, 3.849 líneas) y `paper-corto-es.md` (v2, 999 líneas).
Leídos completos, primero el corto y después el largo. Ninguna cifra se verificó contra
scripts. Esto es lectura, no auditoría.

Las referencias a líneas son del archivo largo salvo que diga "corto".

---

## 1. La oración

Si tengo que decir en una oración qué aporta este trabajo, digo esto. En un catálogo de doce
arneses de agente medidos en condiciones idénticas, elegir el paradigma por su nombre no tiene
premio de calidad separable del ruido entre los brazos que competirían, porque esos brazos
comparten capacidades; lo que sí se puede aprender con una clave determinista es qué exige la
pregunta y qué puede hacer cada brazo, y eso compra costo, no calidad.

El paper la dice. La dice bien en §1.1.2 (líneas 256 a 277), que es el mejor tramo de prosa del
documento, y la vuelve a decir en §7.3 y en el párrafo de "dos mitades" de §9 (3629 a 3636). El
problema es que no la pone primero. El resumen abre con otra oración, la del arnés que hereda
las propiedades probabilísticas del componente y la garantía que tiene que venir de un
componente de otra clase (51 a 92). Esa es la oración del título. La del banco como fuente de
episodios llega en el cuarto párrafo (94 a 101) y con la forma de una relectura ("el banco se
lee de otra forma"), no de un hallazgo.

Hay al menos cuatro oraciones compitiendo por ser la tesis, y las cuatro están en el resumen:

La del aforismo, "apilar instancias puede subir una probabilidad, no puede producir una
propiedad" (64). Es la premisa, y es memorable, pero es una premisa de diseño, no un resultado.

La del motor, "decisión = f(creencias), f determinista y plástica" (79 a 92). Es la máquina. El
párrafo termina con "ahí está la novedad: las garantías vienen del envoltorio y no de lo
envuelto", y ese cierre promete que el motor aprende. Lo que sigue en §7 no muestra al motor
aprendiendo algo que pague fuera de muestra (ver §3 de esta revisión).

La del banco como fuente de episodios (94 a 101). Es la tesis v2 según el propio changelog
(15 a 22).

La de la condición que une todo, "una clave de política tiene que ser COMPUTED; determinismo y
aprendizaje no compiten" (151 a 155). Es la que el paper elige como cierre de resumen y de
conclusión. Formalmente es la Proposición 5.7, que el propio §5 rotula como composición de
funciones (1404 a 1411) y cuya dificultad el paper mismo desestima (889 a 891). Es una condición
necesaria e informativa, pero es una condición, no un aporte que el campo no tenía. Sobre esa
condición se apoya la parte positiva del paper, y la parte positiva es la más floja.

El resultado de esa competencia es que el lector termina el resumen sabiendo que hay una
máquina, que hay una epistemología, que hay una relectura del banco y que hay una condición, y
no sabiendo cuál de las cuatro es la que se le pide creer. El título se queda con la primera, el
cuerpo trabaja para la tercera, y la conclusión firma con la cuarta. El changelog lo confiesa
literalmente: "el título y la máquina son los mismos, cambia qué se pone como columna
vertebral" (15 a 17). Cambiar la columna vertebral sin cambiar el título es la raíz de casi todo
lo que sigue.

¿La sostiene hasta el final? La tercera oración sí, con una salvedad. §9 vuelve a ella en el
párrafo de las dos mitades, pero la tabla de conclusión (3614 a 3619) ordena por contribución
y pone primero "la máquina", cuya evidencia es la más débil del paper (un ajuste en muestra
sobre tres tareas, y un dial medido sobre un registro anterior con otro modelo). El lector que
lea la tabla y no el párrafo se lleva la oración equivocada.

## 2. El hilo

El lector sabe qué se está probando en tres tramos: §1.1.2, §7.2 a §7.4, y §9. En el resto se
pierde, y los cortes tienen lugar preciso.

El changelog de la portada (11 a 46). Treinta y seis líneas de historia de revisiones antes del
resumen. Un lector que no vio el borrador 2.0 no tiene con qué leerlo, y un lector que sí lo
vio ya lo sabe. Además arruina el efecto de §1.1.2. Ahí el paper cuenta que el registro
"reordenó el programa", que es el momento dramático de una investigación honesta. El changelog
ya lo contó cuarenta líneas antes, en tono de bitácora, y lo convirtió en un pivote editorial.

"Cómo se decide un request" (175 a 197). Una sección sin número entre el resumen y §1, con la
Figura 2 y la tabla "lo que decide el código / lo que emite el modelo". Es el mejor dispositivo
didáctico del paper. Está huérfano. El lector recién entra a §1 con una figura del motor que
todavía no le presentaron.

§1.2, "Cuatro afirmaciones que preceden al problema de aprendizaje" (279 a 309). La tercera
afirmación dice que "el punto de operación óptimo generalmente implica abstenerse en la mayoría
de las solicitudes" (297 a 301). Esa afirmación no se entrega nunca. §5.1.5 (1107 a 1112)
admite que el margen del ruteador fue cero en todas las tareas y que la curva riesgo-cobertura
colapsó al origen, AURC 0,000. Es una promesa de la tesis v1 (ruteo selectivo con abstención)
que quedó en la introducción de un paper v2. La cuarta afirmación (303 a 309) repite lo que
§7.1.5 y §7.1.6 y §7.9.3 van a decir tres veces más.

§2 (379 a 669). Once subsecciones, casi 300 líneas, dos tablas de posicionamiento y una tabla de
linaje. El contenido es bueno, en particular §2.9 (el supuesto que cada línea clásica hace sobre
su fuente y que un LLM viola) y §2.10 (los tres mecanismos ocupados). El problema es de
ubicación y de dosis. El lector todavía no vio el motor, salvo por la Figura 2, y se le explica
durante 300 líneas qué no es. La tabla de §2.4 (457 a 462) tiene celdas de ocho líneas; eso no
es una tabla, es prosa con bordes.

§3 y el glosario (704 a 711). El glosario define COMPUTED, OBSERVED, ELICITED, ASSUMED, sonda,
episodio. Llega después de que §2 los usó veinte veces (por ejemplo 423, 436, 466, 507, 540).

§4, "La factibilidad es aritmética" (763 a 876). Un capítulo entero sobre cinco corpus
(gold_v2, v3, wide, deep, xl) que no son el de medición, con paradigmas (Map-Reduce, CoT) que
"se retiraron antes de la campaña" (736 a 738). El paper lo sabe y lo declara en la nota de 793
a 799. El lector recibe 110 líneas sobre un experimento de otra época del proyecto entre los
preliminares y la teoría. El punto que importa, que la aritmética poda antes del primer token y
que declinar no es degradación, entra en una subsección del motor con el par gold_wide contra
gold_deep como único ejemplo.

§5, la teoría (880 a 1423). El párrafo de apertura (882 a 891) es honesto: §5.1 y §5.2 son
"el instrumento con el que §7.3 y §7.8 midieron que el ruteo por identidad no tiene premio", y
los enunciados "se rotulan como teoremas por consistencia con los tests". Lo que ese párrafo
dice, leído de frente, es que de las siete piezas del capítulo (5.0 a 5.7) una sola es teoría de
la tesis v2, la 5.7, y está última. El Teorema 1 con sus corolarios 1, 2, 2b, 3 y las
subsecciones 5.1.1 a 5.1.5 ocupan 160 líneas para un ruteador que nunca se abstuvo. El Teorema
2 (soundness del ensamblador, 1172 a 1220) no se usa en ningún resultado de §7. Las Proposiciones
4, 5 y 6 (ratchet y dial) son propiedades del motor medidas sobre el registro nano de cinco
brazos; son diseño, no teoría, y van mejor al lado de §6.2. El capítulo de teoría es andamiaje
de v1 con una viga de v2 al final.

§6.3.4 (1614 a 1639) cuenta P15 como "refutación medida" de la afirmación de transferencia.
§7.8.1 (3165 a 3198) cuenta P15 otra vez, como primer episodio del ciclo. Es el mismo episodio,
con los mismos números, en dos capítulos.

§7, el orden. §7.0 dice que las preguntas "van ordenadas por la contribución a la que
responden" (1665). Pero PI2 y PI3 están rotuladas como "el ciclo" (1674, 1675) y viven en §7.3,
que trata del premio de ruteo; y el orden de lectura de §7 no sigue el de las contribuciones:
la máquina es §7.2, la interfaz es §7.4, el ciclo es §7.8, y lo que compra está repartido en
§7.3.5, §7.5 y §7.9. §7.6 (la ventana frontera, 2955 a 3027) aparece entre el consenso y el
held-out sin que nada la anuncie, y el propio texto dice que "nada de esto está medido" (2996).
§7.7 (held-out) es la continuación natural de §7.3.3 y está cinco secciones después.

§7.1 (1721 a 1956). Seis subsecciones descriptivas del plantel. §7.1.1 (1786 a 1799) repite la
tabla de §7.1 (1727 a 1740) con menos columnas y los mismos números. §7.1.5, §7.1.6 y §7.9.3
dicen tres veces que el costo es reenvío de entrada.

Los modelos. El paper corre sobre `gpt-5.4-nano`, `gpt-5.6-luna`, `gpt-5.6-terra` y, en §8.2
(3468 a 3479), `gpt-5-chat`. Cuatro modelos. La tabla de §7.0 (1669 a 1678) los mapea para §7,
pero el lector ya vio nano en §5.1.1 (1021 a 1022), §5.4 (1262 a 1265), §6.3.5 (1648 a 1651) y
§7.3.6 sin mapa. Hace falta una sola tabla temprana: qué corpus, qué modelo, qué panel, qué
sección, y qué transfiere.

El hilo se corta, en síntesis, por tres causas. Hay material de la tesis v1 que quedó donde
estaba (§1.2 tercera afirmación, §5.1 a §5.6, §4). Hay material de diseño que está antes de que
el lector tenga el problema (§2 largo, §4, §6.2 denso). Y hay resultados que el argumento
necesita juntos y el índice separa (§7.3.3 con §7.7; §7.1.4 con §7.4; §6.3.4 con §7.8.1).

## 3. La tesis contra los resultados

La tesis, tal como la enuncia el paper: un arnés con decisión determinista sobre creencias
tipadas puede aprender sin perder la garantía, y lo que aprende es qué exige la pregunta y qué
puede hacer cada brazo.

Hay que partirla en cuatro afirmaciones y mirar cada una contra lo que §7 trae.

"Sin perder la garantía". Demostrado, y casi por definición. La garantía es "misma base de
creencias, misma decisión", la política es una tabla, y 26 de 26 decisiones se reproducen en
tres mundos. Es correcto, y el lector lo cree. También es lo que uno esperaría de una tabla
indexada por una función pura, así que el peso probatorio es bajo. La Proposición 5.7 le da
forma, y su caso (2) tiene el dato de los 27% (2483 a 2499), que es lo más interesante de esa
línea y viene "sin script publicado".

"Puede aprender". Aquí está el hueco. El paper tiene un mecanismo de consolidación descrito en
cinco pasos (1540 a 1553) y verificado sobre un sintético nulo ("ninguna partición sobrevive",
1522 a 1523). No tiene un caso en el que θ, aprendida por la consolidación desde episodios
sobre una clave COMPUTED, le gane al mejor fijo fuera de muestra en ningún eje. Lo más cerca
que llega es §7.3.5 (2461 a 2479), y ahí θ sobre la clave computada pierde −0,104 con 31% de
ahorro, mientras una señal elegida a mano ahorra 58% sin perder. El texto lo reconoce con
franqueza ("la política que hoy la consume no la aprende", 2478). Los tres episodios de §7.8
son tres derrotas de θ. El 58% de la contribución 4 no es θ; es una agrupación leave-one-task-out
por una señal que, además, se construyó después de descubrir el eje literal midiendo (2317 a
2320). Entonces "puede aprender" está demostrado como capacidad arquitectónica (hay un lazo,
está codificado, no rompe nada) y no como resultado (el lazo todavía no produjo una política
mejor que la constante).

"Lo que aprende es qué exige la pregunta y qué puede hacer cada brazo". Sugerido. Las
capacidades predicen un brazo no visto mejor que la dificultad sola (0,233 contra 0,257), peor
que la identidad aditiva (0,225), sin cruzar su nulo (p exacto 0,080). La ontología separa más
por segmento que la región, medido sobre la etiqueta de diseño, que no se conoce al decidir. El
paper usa la palabra correcta, "sugestivo", y la usa varias veces. Un resultado sugestivo puede
ser el corazón de un paper si el paper lo presenta como la hipótesis que ordena lo demás. Este
paper lo presenta como contribución 2, al lado de "la máquina" y "el ciclo", como si fuera del
mismo peso.

"El ciclo que reparó el vocabulario". Ejecutado por personas. El paper lo dice cuatro veces
(133 a 137, 3136 a 3142, 3265 a 3279, 3542 a 3554). Lo que queda como contribución es un método
de desarrollo con preregistro, mundo nuevo, mecanismo y sensor COMPUTED. Es un buen método. No
es una propiedad del sistema, y el paper lo sabe.

Lo que sí demuestran los resultados, y con solidez, es otra cosa. Que rutear por identidad de
paradigma no tiene premio de calidad entre brazos capaces, con piso de ruido corregido, en
muestra y en held-out, y con un mecanismo (mismas capacidades, γ que vive entre brazos
dominados, clave elicitada que cambia con el modelo). Que la varianza de trayectoria a
temperatura cero es del 12 al 28% de las celdas y que sacar una decisión del sensor la elimina
en el caso medido (con la salvedad de muestra). Que el acuerdo de cuatro brazos heterogéneos
predice corrección 180 de 180 y se replica sobre otra familia contra criterio preregistrado.
Que ofrecer una herramienta cambia la conducta sin usarla, preregistrado y refutado al revés.
Que a λ igual a 0,02 la selección por nombre ya no compra nada (3205 a 3213). Estos cinco son
los resultados del paper. Ninguno de los cinco es "un motor que aprende". Cuatro de los cinco
son diagnósticos de por qué la pregunta que motivó el programa estaba mal hecha, y el quinto
(el consenso) es un verificador.

Lo que le falta a la historia para que la tesis quede probada y no declarada, en orden de
importancia. Primero, una θ producida por la consolidación, sobre clave COMPUTED, que en
held-out le gane a la constante en costo a utilidad igual. El propio §7.3.5 dice que la señal
existe y que el sistema no la aprende; cerrar esa brecha es la medición que convierte
"sugestivo" en "establecido". Segundo, el control que nunca corre: un selector elicitado (preguntarle
al modelo qué paradigma usar) sobre el mismo rectángulo, con tres réplicas, para mostrar que
sus decisiones cambian entre réplicas y las de la clave computada no. Es la Proposición 5.7 (2)
medida contra su alternativa real, en vez de contra un 27% sin script. Tercero, el brazo de
ausencia construido desde la tabla y corrido, porque es la única predicción que la interfaz
hace sobre algo que no existe todavía, y una predicción cumplida vale más que tres refutaciones.
El paper tiene las tres en §9.1. Sin la primera, la tesis es una arquitectura con evidencia de
que su alternativa no funciona.

## 4. La honestidad como narrativa

Conté las intervenciones del tipo "un borrador anterior decía", "una versión anterior", "la
revisión externa señaló", "se retiró". En el cuerpo del largo hay unas veinticinco. Lugares:
portada (11 a 46), §1.3, §5.1.1 (1009 a 1011), §5.2 (1136 a 1139), §5.4 (1224 a 1228), §7.0.1
(1712 a 1713), §7.1 (1777 a 1782), §7.2.2 (2028 a 2032), §7.2.4 (2086 a 2090), §7.3.1 (2275 a
2277), §7.3.3 (2374 a 2381), §7.3.5 (2462 a 2464), §7.3.6 (2486 a 2487), §7.4.1 (2645 a 2651),
§7.4.3 (2752 a 2755), §7.5.4 (2898 a 2900), §7.7.1 (3078 a 3080), §7.8.1 (3170 a 3171), §7.8.2
(3214 a 3217), §7.8.3 (3239 a 3241), §7.8.4 (3269 a 3270), §7.9.1 (3306 a 3307, 3323 a 3324),
§7.9.2 (3356 a 3357), §8.1 (3420 a 3422). El corto hereda unas diez (corto 429 a 430, 489 a 490,
573 a 574, 600 a 601, 656, 667 a 668, 695 a 699, 734 a 735, 801 a 805, 830 a 831), y el corto es
una "versión de conferencia", donde por definición el lector nunca vio el borrador.

Se lee como las dos cosas a la vez, y hay que separarlas.

Se lee como rigor cuando la corrección tiene contenido científico propio y el lector aprende
algo del error. Cuatro casos cumplen. El piso de ruido de §7.3.3 (2374 a 2381): el bootstrap del
propio estadístico da piso igual o mayor que la brecha con cualquier dato, y eso invirtió el
veredicto del held-out. Un lector que evalúa ruteadores necesita saberlo, y es un aporte
metodológico en sí. El empate de §5.1.1: un empate no es un misruteo, y β definida sobre el
complemento de S+ cobra un acto gratis. Es una idea, no una errata. La definición de
inestabilidad de §7.2.2: contar como inestable una celda con tres réplicas iguales y parciales
es lo contrario de lo que se quiere medir. Y el ratchet de §5.4: acotar varianza de una
secuencia monótona es vacuo, lo que hay que acotar es el conteo. Ese es un error de categoría
que otros van a cometer. Estas cuatro se quedan, pero enunciadas como hallazgos ("un piso
computado así es ciego por construcción, y así se ve") y no como confesiones ("hasta el
borrador anterior este paper lo hacía mal").

Se lee como debilidad en el resto. "El borrador anterior traía 0,540" (3356). "La frase 'seis
veces más' comparaba dos R² crudos y se retiró" (3323). "Una tabla de 41 × 7 que ningún script
reproduce y se retiró" (2462, y otra vez en 3239). "Dos párrafos describían un corpus de 16k y
celdas marcadas † que ya no existen" (3420). "El rótulo P29 lo usa la bitácora también para otra
predicción" (2898). Ninguna de éstas le enseña nada al lector sobre agentes. Le enseñan que el
borrador anterior tenía errores, y cada una le sube la prior de que este borrador también los
tiene. A la sexta o séptima el efecto se acumula: el lector deja de leer resultados y empieza a
leer un texto que se corrige en voz alta. Además introducen un personaje, "la revisión externa",
que actúa dentro del paper (2086, 2275, 2463, 2486, 2645, 2923, 3214, 3312, 3421). Un revisor
como actor en el cuerpo es la marca de un preprint a mitad de revisión, no de un paper.

El corte que propongo. Un Apéndice C, "Erratas respecto del borrador 2.0", con una tabla de tres
columnas: qué decía, qué dice, por qué cambió. Ahí van las veinte que no tienen contenido
propio, y el changelog de la portada entero. En el cuerpo quedan las cuatro con contenido,
reescritas en positivo, y una sola frase en §1.3 o en la nota de §7.0.1 que diga "este borrador
corrige al anterior en los puntos del Apéndice C; los que cambian un veredicto se señalan en
su sección". La palabra "retiró" desaparece del cuerpo. La frase "la revisión externa" también.

Un caso aparte es la agencia del ciclo. Decir que lo ejecutaron personas es indispensable y el
paper lo hace bien. Decirlo cuatro veces (resumen, §7.8 apertura, §7.8.4, §8.3) más una quinta
en la tabla de §9 hace que el lector escuche más el descargo que el resultado. Tres lugares
alcanzan: una frase en la contribución del resumen, el párrafo de apertura de §7.8, y la amenaza
de constructo en §8.3. §7.8.4 y §9 pueden remitir.

## 5. Lo que un lector se lleva

Tres cosas que yo recordaría una semana después, en este orden.

Que cuatro paradigmas distintos de acuerdo dieron 180 de 180 correctas, y que se replicó en otra
familia de modelo con criterio escrito antes. Es el número más limpio del paper y el más fácil
de contar en un pasillo.

Que rutear entre arneses por su nombre no paga, porque los que competirían tienen las mismas
capacidades y la interacción grande vive entre los que nadie elegiría. Con la frase de §7.3.3,
"nadie va a elegir el brazo que pierde por poco en vez del que pierde por mucho" (2326 a 2327).
Y su versión con λ: la selección por nombre compra calidad sólo cuando los tokens son gratis.

Que a temperatura cero y semilla fija entre el 12 y el 28% de las celdas cambian de resultado,
que "la varianza no se promedia, se ramifica", y que un banco que reporta pass@1 sin pass^k no
distingue un sistema que acierta de uno con el que se puede contar. Con la imagen de las tres
réplicas del ancla, 1,000 / 0,000 / 0,000.

Probablemente también el aforismo de la probabilidad y la propiedad, porque está bien escrito.

Las contribuciones que el autor lista son la máquina, la interfaz aprendible, el ciclo, y lo que
la política compra. De las tres que un lector recuerda, la primera (consenso) está escondida en
una cláusula de la contribución 4 del largo (145 a 146) y en el corto no tiene casa en la lista
de contribuciones (corto 61 a 90) aunque tiene sección propia (corto §5.7). La segunda (no hay
premio por nombre) no es una contribución numerada en ninguna de las dos versiones; es el
"mecanismo" que motiva la contribución 2. La tercera (pass^k, ramificación) está dentro de la
contribución 1 pero detrás del 0,33 a 0,89, que es un ajuste en muestra sobre tres tareas.

La brecha es ésta. El autor vende la máquina y la interfaz. El lector compra el diagnóstico y la
métrica. Las contribuciones 2 y 3 tal como están numeradas (capacidades con p de 0,080 y un
ciclo ejecutado por personas) son las que el paper más matiza y las que el lector menos va a
retener, porque cada vez que las lee le llega una salvedad pegada. Los resultados que el lector
sí retiene están todos medidos con más fuerza que los que el autor puso en la vitrina.

La corrección es de vitrina, no de contenido. Numerar como contribuciones lo que está
establecido (el diagnóstico del ruteo con su mecanismo, el consenso replicado, pass^k y la
intervención del ancla), y presentar la interfaz aprendible como la hipótesis que ese
diagnóstico deja en pie, con su evidencia sugestiva y su predicción registrada. La máquina pasa
a ser el instrumento con el que se midió todo eso, que es lo que en realidad fue.

## 6. Lo que sobra y lo que falta

Lo que diluye, con líneas. El changelog (11 a 46). "Cómo se decide un request" como sección
suelta (175 a 197); el contenido vale, el lugar no. La tercera y cuarta afirmación de §1.2 (297
a 309). §2.1, §2.3, §2.8 (381 a 387, 439 a 446, 571 a 581); §2.4 y §2.6 a la mitad. §4 entero
salvo el par gold_wide contra gold_deep (837 a 843) y el párrafo de las cuatro celdas de
gold_deep (870 a 876). §5.1.2 a §5.1.5 (1024 a 1121). §5.2 (1123 a 1168), cuyo resultado empírico
vive en §7.8.2 sobre nano. §5.3 (1172 a 1220), un teorema que §7 no usa. §5.4 y §5.5 como teoría;
como diseño valen. §6.3.4 (1614 a 1639), duplicado de §7.8.1. §7.1.1 (1784 a 1813), duplicado de
§7.1. Uno de §7.1.5, §7.1.6 o §7.9.3. §7.6 (2955 a 3027), que se declara no medido; un párrafo en
la discusión alcanza. Los tres bloques de citas de §7.3.3 (2353 a 2387) y su gemelo en el corto
(corto 793 a 805), que son método y van una sola vez en la sección de método. Las repeticiones de
quién ejecutó el ciclo. El "sesenta por ciento del catálogo y treinta y uno de la utilidad" del
dial aparece en el resumen, en §5.4 y en la conclusión, siempre sobre nano y cinco brazos; con
una vez alcanza y con la salvedad pegada.

Lo que falta, en orden de valor para el lector.

Un ejemplo concreto de punta a punta. El paper tiene la Figura 2, la tabla de "lo que decide el
código", el Algoritmo 1 de pointer_chase y el Algoritmo 3 de la compuerta. No tiene nunca un
request real atravesando el motor con valores. Tomar una tarea del corpus, digamos "¿quién le
reporta a X subiendo tres escalones?" sobre 60 unidades, y mostrar: qué declara el caller
(unidades, presupuesto, banderas), qué poda la compuerta y con qué desigualdad (direct fuera
porque C supera A, con los números), qué creencias entran COMPUTED (cardinalidad singular,
literal en k unidades, continuidad presente), qué dice el dial y por qué, qué exige la pregunta
(RESOLVER_REFERENCIA, LARGO_GOBERNADO_POR_CODIGO, ADAPTA), qué brazos quedan capaces, cuál es el
más barato, qué escribe EXPLAIN, y qué pasa en la réplica dos. Dos páginas. Después de eso §5 y
§6 se leen solos, y el lector tiene un objeto en la cabeza al que colgarle cada resultado.

Una figura de la máquina decidiendo sobre el registro. La consola del proyecto tiene una
"escalera de decisión" en la que el plantel se tacha por factibilidad, garantía y política antes
del primer token. El paper no la tiene. Sobre las 64 tareas del rectángulo: cuántos brazos
sobreviven la compuerta, cuántos son capaces, cuál elige el costo, y contra eso el oráculo y el
mejor fijo. Una figura así mostraría a la vez la poda gratis, el conjunto de capaces (y su
hueco en ausencia) y por qué el oráculo tiene premio que la política no cobra. Hoy eso está
repartido en cinco tablas y dos capítulos.

Una comparación con cómo se hace hoy, corrida. El paper cita que Select-then-Solve recupera un
cuarto de la brecha con un ruteador sobre embeddings, y que el auto-ruteo zero-shot recupera
valor negativo (250 a 254). No corre ninguno de los dos sobre su propio rectángulo. Un selector
elicitado ("modelo, ¿cuál de estos ocho usás?") con tres réplicas es una corrida chica, y es el
único control que vuelve empírica la Proposición 5.7 (2). Sin él, "la clave elicitada hereda la
varianza del sensor" se apoya en un 27% sin script.

Una tabla de mapa de modelos y corpus antes de §2. Qué corrió sobre qué, con qué panel, en qué
sección, y qué transfiere. §7.0 y §7.8.0 lo hacen para §7; el lector lo necesita desde §1.

El resultado positivo de aprendizaje, ya dicho en §3. Sin él, el título miente por omisión.

## 7. El título

"Hardness Over Hope: Policy-as-Code and Deterministic Governance in LLM Agent Orchestration",
con el subtítulo "Confinamiento de varianza en agentes LLM mediante un plano de control
determinista y plástico".

Lo primero que un lector nota es que el título está en inglés y el paper en español, y que la
única versión mantenida es la española (11 a 13). No es un problema de fondo, pero es lo primero
que se ve.

Lo que promete de más. "Policy-as-Code" trae al lector que conoce OPA y Rego, y el paper le dice
en un recuadro (1533 a 1538) que ningún motor de policy-as-code corre, que el término nombra una
tabla de condiciones firmada, y que la capa de decisión no depende de ningún motor externo. Ese
lector se va con la sensación de que le vendieron una palabra. "Deterministic Governance" está
entregado en el dial, el max, los pisos y la guarda, pero la superficie de gobierno que la
palabra evoca (acciones, lo irreversible, quién responde) está "diseñada y sin ejercitar" según
§8.3 (3515 a 3540). "Agent Orchestration" promete orquestación de agentes en general y el paper
mide selección de arnés sobre RAG forense, y lo dice (356 a 359). El subtítulo promete
"confinamiento de varianza" y "plástico": el confinamiento está definido y su consecuencia
observable medida, pero el único algoritmo corregido queda con d igual a n ramificaciones
tipadas, no con d igual a cero (918 a 926); y "plástico" es, en el registro, un ciclo ejecutado
por personas. El título es el de un paper de arquitectura. El cuerpo es un paper de medición
que refuta una hipótesis de ruteo y deja otra en pie.

Lo que no promete y el texto tiene. Que la selección de paradigma por identidad no tiene premio
de calidad entre brazos capaces. Que la interacción tarea por paradigma no es evidencia de que
rutear convenga. Que el acuerdo entre arneses heterogéneos calibra corrección. Que pass^k es la
métrica que le falta a la evaluación de agentes. Que las capacidades declaradas desde el código
son una interfaz sobre la que se puede predecir un brazo que no existe. Nadie que busque
cualquiera de esas cinco cosas encuentra este paper por su título.

Dos alternativas, para que se vea el rango. Una conservadora, que mantiene el eslogan y cambia
lo que sigue: "Hardness Over Hope: los paradigmas de agente no compiten. Capacidades, no
nombres, como clave determinista de una política que aprende". Una directa, sin eslogan: "No hay
premio por elegir el paradigma: qué aprende un arnés determinista de doce arquitecturas de
agente medidas bajo las mismas condiciones". Cualquiera de las dos le dice al lector qué va a
encontrar, y ninguna promete gobierno de acciones ni plasticidad autónoma.

## 8. Corto contra largo

Cuentan la misma historia. El resumen del corto es el del largo con las oraciones partidas, la
lista de contribuciones es la misma, y §5 del corto sigue el orden de las PI del largo. No hay
una tesis distinta escondida en el corto.

Lo interesante es que el corto se lee mejor, y el motivo es estructural. El corto va §3 motor,
§4 teoría con tres piezas (confinamiento, identidad contable, clave), §5 resultados. El largo va
§3 preliminares, §4 factibilidad, §5 teoría con siete piezas, §6 diseño, §7 resultados. Al cortar,
el autor dejó afuera §4, §5.1.2 a §5.6, §6 y §7.1.1 a §7.1.6 del largo, y el argumento no perdió
nada. Eso es un dato sobre el largo. El corto es el esqueleto que el largo tendría que adoptar.

Lo que no se sostiene solo en el corto. Hereda las diez autocorrecciones, y en una versión de
conferencia el lector nunca vio el borrador; ahí no aportan nada y cuestan lo mismo. El
segundo episodio de §5.4 (corto 641 a 661) usa "cascada", "escalera", "sonda", "detector
declarado por tarea" y "la cascada precede a la selección en 20 de 22" sin que el corto haya
definido ninguno de esos términos (el largo los define en §5.2 y §3, que el corto cortó). El
lector del corto llega a "la sonda disparó en 14 y no resolvió ninguna, así que la decisión
honesta fue diferir" (corto 655 a 656) sin saber qué es la sonda. "Región" se usa desde corto
311 y se define en ninguna parte. La Definición 5 del corto (522 a 528) llega bien pero
"exigencia" y "brazo capaz" se usan en el resumen del corto (69 a 77) cien líneas antes. Y el
resumen del corto tiene el mismo problema de cuatro oraciones compitiendo, con menos espacio
para que el lector las ordene.

También hay que decir que 1.000 líneas no son una versión de conferencia. Una versión de ocho o
nueve páginas de esta densidad son unas 400 o 500 líneas de este markdown. El corto es una
versión intermedia. Si va a un venue con límite de páginas, hay que cortarlo otra vez, y el
lugar natural para cortar es §2 (75 líneas de trabajo relacionado en un corto), §5.4 (el ciclo,
que puede quedar en la tabla de episodios y dos párrafos) y §6 (amenazas, que puede ir a un
párrafo por tipo de validez).

Una diferencia menor a favor del corto: limpió el resumen del largo en el punto donde el
aforismo llevaba adentro su propia nota al pie ("§7.5 mide las dos mitades de esa frase", largo
65 a 68). En el corto el aforismo queda solo (corto 27 a 28), y así funciona.

---

## Propuesta de reestructuración del largo

El principio es uno: el orden de las secciones tiene que ser el orden del argumento, y el
argumento es "creíamos que había un selector que construir; el registro dice que ese selector no
puede existir por nombre y dice qué sí es aprendible; acá está la máquina con la que lo medimos
y la condición bajo la cual puede aprender sin perder la garantía".

Portada. Título nuevo (§7 de esta revisión). Resumen reescrito con tres contribuciones (abajo).
Palabras clave. Sin changelog. Una línea que remita al Apéndice C para las diferencias con el
borrador anterior.

§1 Introducción. El problema, con el aforismo (del resumen actual, 51 a 68). La expectativa de
la literatura y lo que este registro dice (§1.1.2 actual, casi sin tocar). La tesis en una
oración. Las tres contribuciones. Una tabla de mapa: corpus, modelo, panel, sección, qué
transfiere. Alcance (§1.3 y §1.3.1 actuales, recortados). Organización. Se funden acá las
propiedades de §1.1 y la norma de §1.1.1 en un párrafo cada una. §1.2 desaparece: la primera
afirmación va al resumen, la segunda al motor, la tercera se borra, la cuarta ya está en §7.1.5.

§2 Trabajo relacionado, en unas 120 líneas. Tres partes. El linaje clásico y el supuesto que
cada línea hace sobre su fuente (§2.9 actual, tabla incluida, es lo mejor de §2). Los vecinos de
ruteo y qué agrega este trabajo (§2.2 y §2.11 fundidas; la cascada de §2.2 en un párrafo). Los
mecanismos ocupados y la conjunción que queda libre (§2.10 recortada a la tabla y el párrafo de
la conjunción). §2.7 sobre jueces va a la sección de método. La tabla grande de §2.4 y la de
posicionamiento §2.8 van al Apéndice D. §2.1, §2.3, §2.5 y §2.6 se reducen a las citas que el
cuerpo necesita.

§3 El motor. Se abre con el ejemplo de punta a punta que hoy no existe (§6 de esta revisión),
usando la Figura 2 y la tabla "lo que decide el código / lo que emite el modelo" (175 a 197
actuales). Después los cuatro pasos (§3 del corto, 272 a 292, que ya está bien). La compuerta
aritmética como subsección, con el Algoritmo 3 y el par gold_wide contra gold_deep (de §4
actual). Creencias, procedencia y dial (§6.2 actual, aligerado; §5.5 actual con la Proposición
6 como una frase; la tabla del ratchet de §5.4 con su salvedad de nano). Qué es plástico y cómo
se consolida (§6.3, §6.3.1, §6.3.2 actuales, con los cinco pasos). El glosario de §3 actual (704
a 711) va al principio de esta sección. §6.3.4 y §6.3.5 se borran; P15 vive en el ciclo.

§4 Teoría mínima. Confinamiento (§5.0 actual entero: Definiciones 5.1 a 5.3b, Proposición 5.4,
Observación 5.5). La clave de la política (§5.7 actual entero). El Teorema 1 en su enunciado y
la observación del empate (§5.1 hasta 1022, más 5.1.1), porque §7.3 usa el vocabulario de
oráculo y mejor fijo; los corolarios, la cascada, el Teorema 2 y las Proposiciones 4 y 5 van al
Apéndice B con una frase en el cuerpo que diga que existen y para qué. El párrafo de alcance de
§5.6 (la misma máquina sobre cuatro superficies, con su tabla) queda como cierre de §4.

§5 Banco y método de medición. Corpus y modos (§1.3.1 actual). Plantel en una sola tabla (§7.1
actual fundida con §7.1.1, más la ley de costo de §7.1.3). Medir sin juez y el corrector (§6.1 y
§7.0.1 actuales). Los dos paneles y la regla del rectángulo (el recuadro de §7.2, 1965 a 1976).
El piso de ruido por pseudo-brazos, explicado una sola vez (el recuadro de §7.3.3, sin su
historia). La corrección por selección con maxT (de §7.3.2). La etiqueta de diseño como techo
(de §7.0). Las preguntas PI con su tabla (§7.0), ahora con la columna de contribución
corregida. Aquí es donde vive la disciplina, dicha una vez y citada después.

§6 Resultados, en el orden del argumento.

6.1 La varianza de trayectoria. pass^k (§7.2.2), la conjetura refutada (§7.2.6), el modo de
cadenas acopladas y la intervención del ancla (§7.2.3 y §7.2.4 con el Algoritmo 1), y el embudo
(§7.2.1) como mecanismo de por qué gana el simple. PI1.

6.2 Por qué rutear por nombre no tiene premio. Interacción grande (§7.3.1), la señal que
sobrevive (§7.3.2), el premio entre contendientes y entre ocho (§7.3.3 sin el recuadro de
método), las familias (§7.3.4), el held-out (§7.7 entero, movido acá porque es el mismo
resultado fuera de muestra), y la clave elicitada (§7.3.6). PI2 y PI3. Éste es el pivote del
paper y tiene que leerse de corrido.

6.3 La interfaz: capacidades y ontología. El espacio de capacidades (§7.1.4, movido acá porque
es la primera vez que los tres contendientes caen en el mismo punto), las definiciones (§7.4.0),
leave-one-arm-out con el nulo (§7.4.1 y §7.4.2 fundidas, con un solo p, el exacto), la ontología
(§7.4.3). PI5 y PI6. Se presenta como la hipótesis que 6.2 deja en pie, con su evidencia
sugestiva y su predicción registrada del brazo de ausencia.

6.4 Lo que sí paga. El desempate por costo y lo que θ hoy no aprende (§7.3.5). El consenso
(§7.5, con el Algoritmo 2 y la réplica en terra). Los predictores (§7.9 entero, con el
paradigma y el recall, la oferta de herramienta, el reenvío). PI8 y PI4.

6.5 El ciclo. §7.8 entero, con la agencia dicha en el párrafo de apertura y en la tabla, y no
más. La disciplina que lo separa del ajuste post hoc remite a §5. PI7.

§7 Discusión. Qué cambia para cómo se evalúan agentes (pass^k, var(γ) no es premio, el banco
como fuente de episodios y no torneo; hoy esto está en el último párrafo de §9 y merece más).
La ventana frontera en un párrafo (de §7.6). Impacto más amplio (§8.5 actual).

§8 Amenazas a la validez. §8.1 a §8.4 actuales, recortadas: el confundente del stack de
servicio, los dos modelos, la rama v igual a cero, la etiqueta de diseño, los ocho puntos, la
superficie de acciones, el ciclo ejecutado por personas. Sin los párrafos que hablan del
borrador anterior.

§9 Conclusión y lo que sigue. La tabla de §9 actual reordenada con las tres contribuciones
nuevas. §9.1 actual, con la θ que aprende el desempate por costo como primera prioridad y no
quinta, porque es la medición que decide la tesis.

Apéndice A, artefactos (el actual). Apéndice B, resultados formales auxiliares: Teorema 1 con
corolarios 1, 2, 2b, 3 y §5.1.2 a §5.1.5; la cascada y su partición (§5.2); el Teorema 2 (§5.3);
las Proposiciones 4 y 5 (§5.4). Apéndice C, erratas respecto del borrador 2.0, en tabla. Apéndice
D, trabajo relacionado extendido: la tabla de §2.4, la de §2.8, los párrafos de §2.5 y §2.6 que
se sacaron del cuerpo.

Con eso el largo queda en el orden del corto, con el corto como esqueleto y el material de
diseño y teoría v1 donde no interrumpe. Estimo que baja de 3.850 a unas 2.600 líneas sin perder
un número.

## Las tres frases del resumen

Sobre 78 tareas de análisis forense y doce paradigmas de agente medidos bajo condiciones
idénticas, sin juez y con piso de ruido corregido por sesgo del máximo, la selección de
paradigma por su identidad no tiene premio de calidad separable del ruido entre los brazos que
competirían, porque comparten capacidades y la interacción tarea por paradigma vive entre los
brazos dominados; el premio que el oráculo sí muestra sobre el catálogo entero, +0,07 en muestra
y +0,10 a +0,15 en held-out, no lo captura ninguna política construida con lo que la clave ve
al decidir, y a un costo de tokens mayor que cero desaparece.

Lo que sí es aprendible con una clave determinista es qué exige la pregunta y qué puede hacer
cada brazo: diez capacidades declaradas desde el código predicen la utilidad de un brazo que
nunca corrió mejor que la dificultad de la tarea sola y encuentran un hueco del catálogo antes
de gastar un token, una señal computada elige el más barato entre los capaces con 58% de ahorro
a utilidad igual fuera de muestra, y el acuerdo de cuatro brazos heterogéneos predice
corrección en 180 de 180 celdas, replicado sobre una segunda familia de modelo contra criterio
preregistrado.

La condición que hace compatibles determinismo y aprendizaje es que la clave de la política sea
función pura del request y del material: con ella la decisión se reproduce 26 de 26 en tres
mundos nuevos mientras el vocabulario se repara, y sin ella la tabla de decisión hereda la
varianza del sensor, que a temperatura cero y semilla fija cambia el resultado de entre el 12 y
el 28% de las celdas y mueve un eje elicitado en el 27% de las tareas según el modelo que lo
sensó.
