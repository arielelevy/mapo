# Soundness del ensamblador — `T-3`

**Qué se afirma, y qué no.** Lo que sigue es un teorema sobre una función de treinta líneas
(`contracts.fill`), no sobre el sistema. Es corto a propósito: un enunciado de soundness que
abarcara «la respuesta» sería falso, y decir exactamente hasta dónde llega es la mitad del
valor.

---

## El enunciado

> **Teorema (soundness del ensamblador).** Sea `T` una plantilla con ranuras
> `S = {s₁ … sₙ}`, `B` una lista de asignaciones ranura→proposición, `Γ` una base de
> creencias y `φ` un piso de procedencia. Si `fill(T, B, Γ, φ)` emite una cadena `R`,
> entonces para toda ranura `sᵢ ∈ S` existe una creencia `βᵢ ∈ Γ` tal que:
>
> 1. `βᵢ` es la creencia **vigente** sobre la proposición que `B` asigna a `sᵢ`;
> 2. `rank(procedencia(βᵢ)) ≥ rank(φ)`;
> 3. la subcadena que `R` tiene en la posición de `sᵢ` es exactamente `str(valor(βᵢ))`.
>
> Y `R` no contiene ninguna otra subcadena que provenga de otro lado que no sea `T` o esos
> valores.

En una línea: **si el ensamblador emite, todo número que emitió está implicado por la base
de creencias al piso pedido.** No «probablemente». No «salvo alucinación».

---

## La demostración, que es por construcción

`fill` recorre `slots_of(T)` —las ranuras que la plantilla realmente usa, extraídas de la
plantilla y no declaradas aparte— y para cada una hace exactamente tres cosas antes de
aceptarla: busca la proposición asignada, pide la creencia vigente, y compara el rango de
procedencia contra el piso. Cualquier fallo **anota el motivo y sigue**, sin emitir.

Después viene el paso que hace al teorema cierto y no aproximado:

```python
if verdict.refused:
    return verdict
verdict.rendered = SLOT.sub(lambda m: str(values[m.group(1)]), template)
```

**La sustitución ocurre después de que la lista de rechazos se comprobó vacía.** Por lo
tanto `values` tiene una entrada por cada ranura de `T`, todas provenientes de una creencia
vigente que pasó el piso, y `SLOT.sub` no puede introducir nada más: reemplaza ocurrencias
del patrón de ranura y deja intacto el resto de la plantilla, que es texto fijo escrito por
el código.

Las tres condiciones se corresponden una a una con las tres guardas. No hay cuarto camino
por el que un valor llegue a `values`.

---

## Falla cerrada y **entera**, que es una decisión y no una consecuencia

Si una sola ranura no llega al piso, no se emite una versión parcial: **se retiene la salida
completa**. Sería técnicamente posible emitir la oración con el hueco marcado, y sería peor:
dejaría que el lector complete lo que el contrato rechazó, que es la versión tipográfica de
afirmar sin evidencia.

Emitir «El saldo de la cuenta es ___» no es más honesto que emitir un número inventado. Es
el mismo acto con mejor caligrafía.

---

## Los cuatro límites, dichos en el teorema y no en una nota al pie

**1. El alcance es la ranura, no la oración.** El teorema garantiza los valores sustituidos.
No dice nada de la prosa que los envuelve, y la prosa la escribe el código en la plantilla.
Una plantilla que diga *«el saldo NO supera {x}»* con `x` correcto produce una salida sound
y falsa. **Eso no es un defecto de la implementación: es la frontera de la familia entera**,
y `redteam.py` la mide en vez de suponerla.

**2. La procedencia es del registro, no del mundo.** `COMPUTED` significa que alguien la
computó y la asentó, no que sea verdad. El teorema traslada confianza desde el piso hacia la
salida; **no la crea**. Si el sensor que produjo la creencia miente, el ensamblador emite la
mentira con procedencia impecable.

**3. Vigente, no histórica.** `base.current(p)` devuelve la última creencia sobre `p`. Si
una creencia posterior superseded a otra, el teorema habla de la nueva. Eso es lo que se
quiere y conviene decirlo: la garantía es sobre el estado de creencias **en el momento de
ensamblar**, no sobre todo lo que alguna vez se creyó.

**4. `str()` es parte del teorema.** La condición 3 dice `str(valor)`, no «el valor». Un
`float` con más decimales de los que nadie quiere leer se emite con todos. El ensamblador no
formatea, y formatear sería empezar a decidir algo sobre el número — que es justo lo que no
hace.

---

## Por qué esto vale escribirlo

Todo el aparato —procedencia tipada, pisos por acción, base de creencias con historia—
existe para poder terminar en un enunciado de esta forma. Sin él, la procedencia es
contabilidad: se registra, se muestra en el EXPLAIN, y nadie puede decir qué compra.

El teorema es lo que compra: **una condición verificable, sobre una función que se puede
leer entera, que convierte «hay evidencia» en «esta cadena está implicada por ella».** Que
sea corto es la propiedad, no la limitación.

Verificado exhaustivamente en `tests/test_science.py` §46 — no con casos elegidos, sino
recorriendo el producto cartesiano de las cuatro procedencias por las condiciones de
rechazo, que es un espacio chico y por eso se puede recorrer entero.
