# Ontología de la pregunta: qué exige un request, y quién puede saberlo

> **Estado: PIZARRA.** Nada de acá está implementado ni medido. Se escribe porque S-3 dejó
> demostrado que **el acoplamiento es propiedad de (pregunta × material)** y que todos los
> ejes computables del sistema son función del material solo. Esta es la mitad que falta,
> desarmada en ejes.
>
> **La regla que ordena todo el documento**: cada eje se tipa con **vocabulario cerrado**,
> nunca con prosa libre. Un eje que exija interpretar texto no entra.
>
> Contexto: `PENDIENTES.es.md` §1a (U-1..U-5), `CONTRATOS.es.md` (qué se puede verificar
> después), `LECCIONES.es.md` §8.5 (el primer eje, ya establecido).

---

## Cómo leer cada eje

| columna | qué dice |
|---|---|
| **forma** | cómo se manifiesta en el lenguaje — es lo que hace que sea *tipable* |
| **falla** | qué sale mal si el sistema lo lee al revés. Si un eje no tiene modo de falla propio, no es un eje |
| **procedencia** | el techo alcanzable. Casi todos son `ELICITED`: **el modelo lee la pregunta y eso no puede superarse** |
| **¿medible acá?** | si los corpus actuales pueden falsar algo sobre este eje, o si lo vuelven trivial por construcción |

Esa última columna es la más importante. Tres veces ya el corpus decidió en silencio qué
hipótesis podían ponerse a prueba —el detector heredado del gold, las entidades sin
ambigüedad, el turno único— y este documento existe en parte para que la cuarta no pase
desapercibida.

---

## A. Sobre la forma de la respuesta

### A1 · Cardinalidad de la respuesta · **establecido**

| | |
|---|---|
| **forma** | singular («cuál fue el arma») · enumerativa («listame los nombres») · agregada («cuántos X») |
| **falla** | singular: ambigüedad, varias candidatas · enumerativa: **incompleta** · agregada: mal contada sobre cobertura parcial |
| **procedencia** | `ELICITED`, y **verificable después** por `C-COMPLETE` |
| **¿medible acá?** | **sí** — C1 es singular, C2 enumerativa, C4 agregada |

Único eje ya establecido (`LECCIONES.es.md` §8.5). La demanda es **implícita**: nadie
escribe «listame *todas* las direcciones». Y confundir dos valores tiene consecuencias
opuestas — forzar cobertura sobre una singular paga de más por nada; no forzarla sobre una
enumerativa entrega algo incompleto que parece correcto.

### A2 · Precisión exigida

| | |
|---|---|
| **forma** | «exactamente cuántos» · «aproximadamente» · «del orden de» |
| **falla** | gastar cobertura completa donde una estimación bastaba, o dar una estimación donde se exigía exactitud |
| **procedencia** | `ELICITED` |
| **¿medible acá?** | **no** — todo el gold es de coincidencia exacta, así que la exactitud es el único valor presente |

Interactúa fuerte con λ: es el eje que dice **cuánta cobertura se puede comprar barata**.

### A3 · Grano

| | |
|---|---|
| **forma** | «ventas» — ¿por transacción, por mes, por cliente? |
| **falla** | una respuesta correcta al grano equivocado, que es indistinguible de una correcta si nadie declaró el grano |
| **procedencia** | `ELICITED`; a veces `COMPUTED` si el esquema lo declara |
| **¿medible acá?** | **no** — las unidades son memos sin dimensión |

`CLAUDE.md` ya lo nombra para la superficie de datos («análisis dimensional/grano»).

---

## B. Sobre qué hay que hacer con el material

### B1 · Acoplamiento requerido · **medido, y con límite conocido**

| | |
|---|---|
| **forma** | «seguí la línea de reporte un paso hacia arriba» contra «cuántos X hay» |
| **falla** | contestar desde una unidad cuando la respuesta vive dos unidades más allá |
| **procedencia** | **`ELICITED` como techo** — S-3 lo demostró: ningún eje del material lo determina |
| **¿medible acá?** | **sí**, y ya se midió: la sonda acierta 9/14 |

El caso testigo del documento entero: los mismos documentos sostienen una pregunta que
exige encadenar y otra que no.

### B2 · Ausencia y negación

| | |
|---|---|
| **forma** | «qué clientes **no** tienen dirección» · «¿hay algún X sin Y?» |
| **falla** | afirmar una ausencia desde una muestra — **el error más caro del catálogo**, porque parece una respuesta normal |
| **procedencia** | `COMPUTED` sólo con cobertura total demostrada; si no, **no se puede afirmar** |
| **¿medible acá?** | **parcialmente** — hay tareas de oráculo vacío, pero no preguntas negativas explícitas |

Es el lado-pregunta de una asimetría que la sonda ya implementa: *una unidad de silencio no
es una medición de las otras 47*. Probar una ausencia exige haber mirado todo; probar una
presencia exige un solo documento. **El mismo sistema no puede tratarlas igual.**

### B3 · Resolución de entidad requerida

| | |
|---|---|
| **forma** | que la respuesta dependa de decidir que «J. Pérez», «Juan Pérez» y «el titular» son el mismo |
| **falla** | contar dos veces, o perder el vínculo y declarar que no existe |
| **procedencia** | `OBSERVED` si se verifica contra el texto; `ELICITED` si la decide el modelo |
| **¿medible acá?** | **NO, y ya está demostrado** — cero abreviaturas, cero anáfora, una forma canónica por entidad |

Es el agujero que mandó `graph_traverse` a standby: el corpus **hace gratis la parte
difícil**, así que ningún patrón de grafo puede medirse donde tiene sentido (K-6).

### B4 · Temporalidad y vigencia

| | |
|---|---|
| **forma** | «el domicilio de X» (⇒ el **vigente**) contra «el domicilio de X en 2019» |
| **falla** | devolver un valor superado como si fuera actual — con procedencia impecable |
| **procedencia** | `COMPUTED` si las fechas están declaradas; `ELICITED` si hay que inferir cuál gana |
| **¿medible acá?** | **sí, y está sin explotar** — el corpus tiene **enmiendas** que supersiguen memos |

`corpus/verify.py` cuenta «6 amendments», y **la supersesión está escrita, no inferida**.
Textual de `amend-002-w004`:

> «The domicile of record associated with settlement account AR2936541590 is Rosario. **This
> filing supersedes any earlier domicile on record for that account.** No other engagement
> details are restated.»

O sea que hay un verbo de precedencia declarado, un alcance declarado («for that account»)
y un límite declarado («no other details»). El material para medir vigencia **ya existe, es
verificable por código, y ninguna predicción registrada lo usa.** Es el eje más barato de
todo este documento.

Y trae de regalo una pregunta que el corpus puede hacer y nadie hizo: **¿qué paradigma
respeta la supersesión?** Un memo viejo y su enmienda dicen cosas distintas sobre el mismo
hecho, así que un paradigma que lee ambos y devuelve el viejo está fallando de una manera
que el F1 castiga sin explicar.

**Verificado el 2026-08-28 (`_analyze_supersession.py`), y el resultado es más fuerte que
la propuesta.** Las enmiendas parsean limpio —cinco cuentas con su domicilio vigente,
`Rosario` y `Mendoza`— y sin embargo:

| | |
|---|---|
| preguntas que mencionan domicilio o residencia | **0** |
| golds que son un valor enmendado | **0** |

> **La supersesión está en el material y ninguna pregunta la interroga.** Las enmiendas
> existen sólo como distractor: cuestan tokens, ensucian la recuperación, y **no miden
> nada.**

Peor que no medir: pueden estar **deprimiendo** utilidades sin que nadie sepa qué prueban.
Un paradigma que lee la enmienda y se confunde pierde puntos por un eje que el registro no
declara estar midiendo.

**Y por eso es el pendiente más barato del proyecto entero**: el generador ya produce el
material, la precedencia ya está escrita en forma fija, y el gold de una pregunta de
vigencia es el valor de la enmienda. Falta la pregunta.

### B5 · Autoridad de fuente

| | |
|---|---|
| **forma** | dos documentos que se contradicen, y la pregunta no dice cuál manda |
| **falla** | elegir en silencio, sin registrar que hubo conflicto |
| **procedencia** | `COMPUTED` si hay una regla de precedencia declarada |
| **¿medible acá?** | **sí, junto con B4** — una enmienda *es* una regla de autoridad |

---

## C. Sobre la relación con el pedido anterior

### C1 · Relación conversacional

| | |
|---|---|
| **forma** | independiente · drill-down · comparación · expansiva |
| **falla** | un drill-down tratado como independiente **pierde el alcance heredado** y contesta sobre el corpus entero |
| **procedencia** | `ELICITED` |
| **¿medible acá?** | **NO** — el corpus es de turno único y el `Request` del producto **no tiene campo** para turnos previos |

Tercer caso confirmado del mismo agujero estructural. Y no es sólo del banco: sin campo en
el `Request`, ni siquiera habría de dónde sacar la entrada.

Importa porque **la relación conversacional determina el alcance heredado**, y el alcance
determina la cardinalidad, que determina la región, que determina el ruteo.

---

## D. Sobre si la pregunta es contestable

### D1 · Presuposición

| | |
|---|---|
| **forma** | «¿cuándo dejó de operar en Salta?» cuando nunca operó en Salta |
| **falla** | contestar *cualquier cosa* valida la premisa falsa. **No hay respuesta correcta** |
| **procedencia** | la presuposición **es una proposición**: se chequea contra la base como cualquier otra |
| **¿medible acá?** | **no**, pero sería barato de generar |

El eje más limpio de todos para este producto: una presuposición **ya tiene la forma de una
creencia**, así que el mecanismo para verificarla existe entero. Lo único que falta es
extraerla.

### D2 · Subjetividad

| | |
|---|---|
| **forma** | «cuál es el **mejor** proveedor» · «¿es razonable este monto?» |
| **falla** | producir una respuesta con apariencia de hecho sobre algo que no tiene valor de verdad |
| **procedencia** | ninguna: **no hay evidencia posible** |
| **¿medible acá?** | **no**, y por diseño — el corpus es de extracción de respuesta exacta |

Es el borde de lo que este producto puede prometer. Lo correcto es **rechazar o reformular**,
no contestar bien.

### D3 · Condicionalidad e hipotético

| | |
|---|---|
| **forma** | «si se aprueba la ampliación, ¿cuánto sería?» |
| **falla** | contestar con el valor del mundo **actual** como si fuera el del hipotético |
| **procedencia** | `COMPUTED` sobre el mundo actual, y el salto al hipotético **no tiene procedencia** |
| **¿medible acá?** | **no** |

**Ya apareció medido desde el otro lado**: es una de las cinco familias que sobrevivieron
al red-team de mis-binding (`CONTRATOS.es.md` §3). Que aparezca en los dos lados —como
demanda de la pregunta y como residuo del contrato— sugiere que es el mismo fenómeno visto
desde sus dos puntas.

---

## E. Sobre quién pregunta

### E1 · Alcance por permisos

| | |
|---|---|
| **forma** | la misma pregunta, distinto alcance visible según quién la hace |
| **falla** | filtrar lo que no correspondía, o declarar una ausencia que sólo es una ausencia *para ese usuario* |
| **procedencia** | `COMPUTED` — es aritmética sobre el alcance |
| **¿medible acá?** | **no** — el alcance es la tarea entera y no hay identidad |

La capa congelada **sí lo resolvía** (`legacy/README.md`: scoping por permisos). Y combina
peligrosamente con **B2**: «no hay ningún X» y «no hay ningún X *que vos puedas ver*» son
afirmaciones distintas, y confundirlas es una falla de seguridad y no de calidad.

---

## Qué sale de mirar la tabla entera

**1. Casi todo tope en `ELICITED`, y eso es estructural, no una debilidad del diseño.** El
modelo es lo único que lee la pregunta. Por eso ninguna demanda del request puede gatear una
acción irreversible por sí sola — correcto — y por eso la ruta a subir de rango es siempre
la misma: **verificar después contra el material o contra la respuesta.**

**2. Tres ejes son medibles hoy y sólo uno se está midiendo.**

| eje | estado |
|---|---|
| **A1** cardinalidad de respuesta | medible; **no medido** |
| **B1** acoplamiento | **medido** (9/14) |
| **B4/B5** vigencia y autoridad | medible con las **enmiendas que ya existen**; **no medido** |

**B4 es el más barato de todos los pendientes de este documento**: el material está, el
verificador sería aritmético sobre fechas declaradas, y ninguna predicción registrada lo usa.

**3. Cuatro ejes están bloqueados por el generador, no por el diseño.** B3 (entidades), C1
(conversación), A2 (precisión) y D2 (subjetividad) son estructuralmente inmedibles con los
corpus actuales. **Es el mismo patrón que ya se pagó tres veces**, y ahora está enumerado
antes de pagarlo una cuarta.

**4. El eje con peor relación daño/atención es B2.** Afirmar una ausencia desde una muestra
produce una respuesta que *parece normal*, no hay señal de que algo falló, y el sistema ya
tiene la asimetría correcta implementada en la sonda — pero sólo del lado del material,
nunca del lado de la pregunta.

**5. D1 es el más fácil y no está.** Una presuposición ya tiene forma de proposición: el
mecanismo para verificarla existe completo. Falta únicamente extraerla.
