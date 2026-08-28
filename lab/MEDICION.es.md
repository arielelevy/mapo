# Un mecanismo de medición definido por lo que se niega a hacer

> **De dónde sale.** No es un diseño nuevo: es lo que este banco terminó siendo después de
> medir con él. Cada sección de acá enuncia una restricción y **qué deja de ser medible si
> se la afloja** — no una recomendación de estilo.
>
> **Lo que NO es.** No es una alternativa general a los frameworks de evaluación de RAG:
> **acepta menos tareas** —hace falta una respuesta verificable— y sobre las que acepta
> **mide estrictamente más**. Las dos cosas se detallan abajo, porque confundirlas fue un
> error de una versión anterior de este documento.

---

## La diferencia no es tener más métricas

Un framework de evaluación típico reporta un vector de puntajes —fidelidad, relevancia,
precisión de contexto— producidos por un **juez LLM**. La tentación es agregar métricas.
El problema no está ahí.

> **Un número que no puede separar dos fallas distintas no está midiendo: está
> resumiendo.**

Ese es el criterio que ordena todo lo que sigue, y no es retórico — se puede aplicar.
«Fidelidad 0,82» no dice si el sistema no encontró el documento, lo encontró y leyó el
párrafo equivocado, o lo leyó bien y afirmó de más. Son tres arreglos distintos y un
número que los promedia le da al equipo la sensación de saber en qué está.

---

## 1. Sin juez, porque el juez es más ruidoso que el efecto

El efecto bajo estudio son **unos pocos puntos porcentuales**. El ruido de un juez LLM es
del mismo orden, así que un juez vuelve **infalsificables** exactamente las mejoras chicas
que esta literatura reporta.

La corrección se paga con alcance: sin juez hay que poder corregir por coincidencia exacta,
y eso obliga a tareas con respuesta verificable. **Es una restricción real y se declara**,
en vez de comprarse generalidad con un instrumento que no distingue lo que mide.

**La asimetría no es simétrica.** Un juez puede evaluar cualquier cosa y no puede falsar
nada; un corrector exacto falsa todo lo que alcanza y no alcanza a todo.

---

## 2. El costo es un eje, no una nota al pie

Toda comparación se reporta **barriendo λ**, la preferencia de costo. Nunca un solo punto.

Medido dos veces, en dos corpus held-out independientes:

| λ | P16: neto contra el mejor fijo |
|---:|---:|
| **0,00** | **+0,1211** |
| 0,02 | −0,4043 |
| 0,05 | −1,2888 |

> **Sin cobrar el costo, el ruteo captura. Cobrar cualquier precio realista lo borra.**

Y de ahí sale la lectura que conviene aplicarle a cualquier resultado ajeno:

> Un resultado de orquestación reportado **sin cobrar el costo** es el punto **λ=0** de una
> curva que nadie mostró.

---

## 3. La abstención se mide, no se evita

Un sistema que puede **negarse** necesita que se le mida el negarse: curva riesgo-cobertura
y su área. Reportar sólo la utilidad de lo que contestó es elegir la muestra después de
verla.

**Medido**: acá esa curva salió **degenerada** — un solo punto en el origen, AURC 0,000,
porque el margen del ruteador era 0 en las 26 tareas. **La ausencia de la curva era el
resultado**, y sin la curva se habría reportado la utilidad de lo contestado como si fuera
el desempeño del selector.

---

## 4. Cada celda tiene que separar dos fallas, o no es una celda

No alcanza con que una tarea sea difícil: tiene que **fallar de una manera que informe**.

El caso más limpio es la celda de vigencia. El corpus tiene enmiendas con la precedencia
escrita, así que el valor viejo **y** el nuevo viven en el material. Entonces una respuesta
incorrecta dice cuál falla ocurrió:

| respuesta | qué falló |
|---|---|
| otra ciudad cualquiera | nunca encontró la enmienda: **recuperación** |
| el domicilio original | encontró las dos y eligió la superada: **vigencia** |

El F1 castiga las dos igual. La segunda se comete **con procedencia impecable** —el memo
viejo dice lo que dice— y es la que un sistema de gobierno existe para impedir.

**El verificador se niega** a aceptar una tarea cuyo valor superado no esté en el material:
sin los dos valores presentes, un error sólo diría «no lo encontró», que es lo que las otras
celdas ya miden.

---

## 5. La verdad se re-deriva, y el verificador puede negarse

El gold **no se declara**: se vuelve a derivar desde los documentos con un verificador
independiente del generador. Y cuando se agregó una celda nueva, el verificador **la
rechazó** —«no verifier for cell C8_currency»— hasta que se le escribió el chequeo.

Esa negativa es la propiedad, no un inconveniente. Una celda cuya verdad nadie puede
reconstruir es una celda que mide lo que el generador quiso, no lo que el documento dice.

---

## 6. El veredicto se congela antes que el dato

Preregistrar en prosa deja margen: una predicción se lee de varias maneras después de ver
los números. Acá se congela **el código que juzga**, y entra a git antes de que exista una
sola fila.

**Demostrado sobre las mismas filas**: cambiar la regla de detectores mueve el número
prerregistrado de −1,2888 a −1,6931 y cambia las acciones. **Nada en la salida habría dicho
que la regla cambió por debajo.**

Corolarios que salieron caros:

- **Lo que es función de un registro se recomputa; sólo lo irreducible se guarda.** La
  región y la utilidad estaban congeladas dentro de cada fila, así que arreglar el
  vocabulario o el corrector partía el registro en dos épocas en silencio.
- **Un test que no puede rechazar no está midiendo.** Antes de leer un no-significativo hay
  que chequear la **potencia**: con `n` filas de las que `k` salieron bien, el `p` mínimo
  alcanzable es `1/C(n,k)`, y si ese piso ya supera 0,05 el estrato no puede dar
  significativo **aunque la señal sea perfecta**.
- **Un null que rompe la estructura de correlación produce números publicables sobre una
  hipótesis que nadie puso a prueba.** El resultado es de la fila, no de la transición:
  permutar por transición le regala al azar variación que no existe.

---

## 7. Y el corpus decide qué se puede preguntar — hay que enumerarlo

Lo más caro que se aprendió, y tres veces:

| lo que el corpus hacía gratis | qué volvió inmedible |
|---|---|
| ser corregible **implicaba** tener detector barato | la rama del ruteo: la cascada pre-empataba siempre |
| una forma canónica por entidad, cero anáfora | todo patrón de grafo — su parte difícil no existía |
| turno único | toda demanda sobre relación conversacional |

> **Un generador que vuelve trivial una dependencia no puede falsificar el patrón que existe
> para esa dependencia.** La falsación vale para el régimen en el que corrió.

Por eso el mecanismo incluye una pieza que no es una métrica: **la lista explícita de qué
ejes el corpus actual puede falsar y cuáles vuelve triviales** (`ONTOLOGIA_PREGUNTAS.es.md`).
Enumerarlos antes es la única defensa contra el cuarto caso.

---

## 8. El catálogo también se mide, con la misma vara

A un candidato nuevo se le exige predicción registrada y falsación. A los que ya están,
históricamente, no se les exigió nada. Se cerró: **dominado** = nunca único mejor y, al
empatar, nunca el más barato. Sobre 96 tareas de seis corpus eso retiró un brazo y dejó a
dos «apenas».

Y cada estado vive en el ejecutable con su **razón** y su **condición de revival** — no en
un documento aparte, porque una decisión que vive en prosa se deriva sola.

---

## «Más angosto» estaba mal dicho, y la exhaustividad lo muestra

Una versión anterior de este documento decía que el mecanismo es «más angosto» que un
framework de evaluación por juez. Eso mezcla dos cosas y le regala a la otra parte una
generalidad que no entrega.

| | |
|---|---|
| **angosto en qué ACEPTA** | cierto: hace falta una respuesta verificable |
| **angosto en qué MIDE** | **falso**: mide estrictamente más sobre las tareas que acepta |

**El caso testigo es la exhaustividad.** Preguntale a un juez si una enumeración incompleta
es *fiel*: dice que sí, y **tiene razón** — cada ítem presente está sostenido por un
documento. La incompletitud **no es un problema de anclaje**, así que ninguna métrica de
anclaje puede verla. No la mide con menos precisión: **no la mide.**

Y es la misma forma que la vigencia. Un valor superado también está perfectamente anclado:
el memo viejo dice lo que dice.

> **Las métricas basadas en anclaje son ciegas a toda falla en la que la respuesta
> equivocada está anclada.** Y esa es exactamente la clase de falla que una capa de
> gobierno existe para impedir.

| falla | ¿la ve una métrica de anclaje? | ¿la ve este mecanismo? |
|---|---|---|
| inventó un dato | **sí** | sí |
| enumeración **incompleta** | **no** — cada ítem citado es real | sí (C2, C4, `C-COMPLETE`) |
| devolvió el valor **superado** | **no** — el memo viejo lo sostiene | sí (C8) |
| lo resolvió pero **carísimo** | **no** — no hay eje de costo | sí (barrido de λ) |
| **contestó cuando debía abstenerse** | **no** — no hay abstención que medir | sí (riesgo-cobertura) |
| **encontró vs. eligió mal** | **no** — un puntaje, dos causas | sí (atribución por celda) |

**Y la angostura es el precio de la falsabilidad, no un defecto colateral.** Ya está dicho
en §1 y conviene decirlo entero: un método que puede evaluar cualquier cosa **no puede
falsar nada**. La amplitud del otro lado es en buena medida **amplitud infalsificable** —
produce un número también donde ningún número está garantizado.

---

## Lo que este mecanismo NO hace

Se dice acá para que no haya que descubrirlo:

- **Sólo acepta tareas con respuesta verificable.** Generación abierta queda afuera por
  construcción. Pero conviene no confundir eso con que el otro enfoque *sí* la evalúe: le
  pone número, que es distinto.
- **Corpus sintético de un solo autor.** El verificador es independiente del generador; el
  generador no es independiente de la hipótesis.
- **Una sola familia de modelos.** Parte de lo aprendido puede ser del modelo y no de la
  tarea, y eso está sin medir.
- **Sin resultados en benchmarks públicos.**
- **Cuatro ejes de la ontología son estructuralmente inmedibles acá** — entidades,
  conversación, precisión exigida, subjetividad.

---

## En una frase

No es mejor por sofisticado. Es mejor por lo que **se niega a hacer**: sin juez, sin costo
regalado, sin celda que no separe dos fallas, sin gold que no se pueda re-derivar, sin
veredicto elegido después del número — y **con la lista de sus propios puntos ciegos
escrita**, que es la parte que casi nadie publica.
