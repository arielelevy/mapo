# Semántica de los contratos de afirmación

> **T-1.** Bloquea a F6 y al anti-RAG (AR-1). Es trabajo de **pizarra**: nada de acá entra
> al paper hasta que exista implementación que lo corra. Se escribe primero porque sin él
> F6 mide algo indefinido y «qué falta» no está definido.
>
> **Lo que existe hoy no es esto.** `ANSWER_CONTRACT` restringe el **formato** de la salida
> —una línea `ANSWER: <x>`, ítems separados por `; `— y se corrige por F1 de conjuntos. Eso
> no dice nada sobre las **proposiciones** que la salida afirma.

---

## 1. La forma que puede tener una garantía, y la que no

Una garantía sobre la salida de un LLM no puede ser «lo que dice es verdadero»: nadie tiene
acceso al mundo para chequearlo, y prometerlo es exactamente el reclamo que este proyecto
rechaza. La que **sí** se puede dar tiene otra forma:

> **La salida está IMPLICADA por la base de creencias, a la procedencia exigida.**

Es la misma mudanza que ya se hizo en la capa de decisión: no «mismo prompt, misma
respuesta» sino «misma base de creencias, misma decisión». Verdad se reemplaza por
**derivabilidad desde lo que se registró**, que sí es chequeable y sí es auditable.

Formalmente. Sea `B` la base de creencias del request y `o` la salida. Sea `⟦o⟧` el
conjunto de proposiciones que `o` afirma. Un contrato `C` define:

- un **proyector** `π_C`, que extrae de `o` un subconjunto de afirmaciones *decidible por
  código*, y
- un **piso** `φ_C`, la procedencia mínima exigida.

**Soundness de `C`:** para toda `p ∈ π_C(o)`, vale `B ⊨ p` con procedencia `≥ φ_C`.

Y acá está lo que hay que decir en voz alta, porque es donde vive el ataque:

> **`π_C(o) ⊆ ⟦o⟧`, y la inclusión es propia.** El contrato acota una **proyección
> sintáctica** de lo que la salida afirma, no todo lo que afirma. Lo que queda afuera es el
> **residuo**, y ahí es donde vive el mis-binding.

---

## 2. Las tres clases, con su proposición exacta

### C-NUM — números con procedencia

El modelo emite una **plantilla con ranuras**; el código sustituye desde la base.

- `π_NUM(o)` = las ranuras numéricas y el valor que ocupa cada una.
- `φ_NUM` = `COMPUTED`.
- **Garantiza**: todo numeral de `o` es el renderizado de un valor sostenido en `B` a
  procedencia `COMPUTED`. **Ningún número inventado puede aparecer**, porque el modelo
  nunca escribe dígitos — escribe nombres de ranura.
- **NO garantiza**: que el número esté en la ranura **correcta**. La asociación
  ranura → proposición la elige el modelo.

> El total de 2024 puesto en una oración sobre 2025 es una afirmación falsa con procedencia
> impecable. Cada término de `π_NUM` pasa; la proposición compuesta es falsa.

### C-CITE — citado o callado

- `π_CITE(o)` = los pares (afirmación, puntero) y la resolución de cada puntero.
- `φ_CITE` = `OBSERVED`.
- **Garantiza**: toda afirmación de `o` lleva un puntero a una unidad **en alcance**, y el
  puntero **resuelve** — el span literal existe en esa unidad. Una afirmación sin puntero
  resoluble no se emite: se calla.
- **NO garantiza**: que el span **sostenga** la afirmación. Resolver es sintáctico; sostener
  es semántico.

> Es la misma asimetría que la sonda ya tiene medida: un puntero que resuelve vale
> `OBSERVED`; uno inventado, `ELICITED` bajo. Resolver acota la alucinación de
> referencias, no la de inferencias.

### C-COMPLETE — completitud sobre un dominio declarado

- `π_COMPLETE(o)` = el conjunto de ítems enumerados y el dominio contra el que se enumeran.
- `φ_COMPLETE` = `COMPUTED` sobre el dominio (cardinalidad y pertenencia son aritmética
  sobre lo que la tarea declara).
- **Garantiza**: los ítems de `o` cubren el dominio **declarado y enumerable** — típicamente
  las unidades en alcance. Es la generalización de la herramienta `coverage`, que hoy hace
  esto sobre unidades y no sobre proposiciones.
- **NO garantiza** dos cosas distintas, y conviene separarlas: que cada ítem sea correcto
  (eso es C-CITE), y que el **alcance** coincida con el mundo. Completitud sobre lo
  recuperado no es completitud sobre lo que existe.

---

## 3. El residuo, que es el ataque y hay que buscarlo nosotros

**Mis-binding** es, en esta notación, exactamente: existe `p ∈ ⟦o⟧ \ π_C(o)` con `B ⊭ p`,
mientras **todo** `π_C(o)` verifica. El contrato no falla; el contrato **no mira ahí**.

Tres familias donde buscarlo, y las tres son composicionales — surgen de combinar términos
que individualmente pasan:

**MEDIDO el 2026-08-27** (`_redteam_binding.py`, contra la implementación de C-NUM en
`app/contracts.py`): **cinco familias construidas, cinco sobreviven. Residuo 100%.** El
control positivo emite, así que el contrato tampoco rechaza de más.

| familia | contraejemplo | ¿pasa el contrato? |
|---|---|---|
| **Referente** | «El total de **2025** fue 1200», con 1200 = `total_2024` | **sí** |
| **Alcance de agregación** | «**Excluyendo devoluciones**, el total fue 1850», con 1850 = incluyéndolas | **sí** |
| **Negación** | «**Ningún** mes superó los 430», con 430 = el máximo mensual | **sí** |
| **Comparación** | «Las ventas **cayeron** a 1400», con 1400 > el trimestre anterior | **sí** |
| **Condicional** | «**Si se aprueba** la ampliación, la capacidad llega a 500», con 500 = la actual | **sí** |

**Y las cinco comparten una sola forma**, que es el hallazgo y no la lista:

> Lo que hace falsa a la oración vive en la **prosa conectiva** —el referente, el
> modificador, la negación, el verbo, el condicional— y **la prosa conectiva no ocupa
> ninguna ranura**, así que ninguna ranura puede contradecirla.

Eso convierte el residuo de una preocupación en una **cantidad con dirección**: C-NUM
detiene por completo el número inventado y **no detiene nada** del binding. No es que el
contrato sea débil — es que su proyector y el residuo son complementarios por
construcción.

**Consecuencia sobre lo que se puede afirmar.** Mientras el binding lo medie el modelo,
«imposible de producir» es **falso**. La afirmación honesta es:

> **verificado por construcción sobre `π_C`, con residuo de binding declarado y medido.**

Y el residuo se mide: es la tasa de contraejemplos que sobreviven al contrato, buscados
adversarialmente. Un residuo sin número no es una salvedad, es una excusa.

---

## 4. Cómo se cierra el residuo, si se cierra

La única forma de achicar `⟦o⟧ \ π_C(o)` es **agrandar `π_C`**: que más de lo que la salida
afirma sea decidible por código. El límite de esa dirección es un **ensamblador** donde el
modelo propone plantilla y el código instancia y verifica el binding — o sea, mover la
prosa conectiva de «lo que el modelo escribe» a «lo que el contrato genera».

Eso no elimina el residuo, lo **relocaliza**: pasa a ser la distancia entre la plantilla que
el modelo eligió y la que correspondía. Más chico, y sobre todo **enumerable** — hay una
cantidad finita de plantillas y se puede medir cuál se elige mal.

---

## 5. Qué habilita para el anti-RAG

Con `π_C` y `φ_C` definidos, «qué falta» deja de ser una intuición y pasa a ser una resta:

```
déficit(o) = { p ∈ π_C(requerido) : B ⊭ p a procedencia φ_C }
```

Eso es un **rechazo tipado**, que es exactamente lo que `beliefs.py` ya produce y lo que
`rec.py` ya consume. La cadena cierra sin ninguna pieza nueva — y sin esto, cualquier
generador de preguntas tendría que inferir de la prosa qué debería contener la respuesta,
que es parseo de texto libre y está prohibido por regla.

---

## 6. Qué falta antes de que esto valga

- [ ] **Implementar `π_C` para al menos una clase** — sin eso, todo lo de arriba es diseño.
- [ ] **El red-team de mis-binding, hecho por nosotros** (T-2), con su tasa de residuo.
- [ ] **El teorema de soundness del ensamblador** (T-3), que es la Sección 1 hecha
      demostración y no definición.
- [ ] **Comparar contra los baselines directos** (F6): conformal factuality y un detector
      post-hoc, en la misma curva. Si el constructivo no domina al detectivo a igual
      cobertura, la tesis se cae con honestidad, que es como debe caerse.
