# Quién fija el dial — `T-5`

La pregunta parece de gobernanza y es de diseño: si el dial de garantía lo elige el
llamador, un llamador apurado lo baja; si lo elige el sistema, el llamador no puede pedir
más rigor del que el sistema cree necesario. **Ninguna de las dos.**

---

## Tres fuentes, y una regla de composición

```
nivel efectivo = max( pedido , piso_de_creencias , piso_aprendido )
```

| fuente | quién la produce | qué puede hacer |
|---|---|---|
| **pedido** | el llamador, en el request | **subir**, nunca bajar |
| **piso de creencias** | `required_floor(base)` sobre creencias `COMPUTED` del request | **subir**, y no se puede desactivar |
| **piso aprendido** | `θ.floors[region]`, dentro del bundle firmado | **subir**, y sólo si está promovido |

`max` no es una elección de conveniencia: es la única composición que hace que **cada
fuente sólo pueda endurecer**. Con `min` o con un promedio, agregar una fuente podría
ablandar el resultado, y entonces una fuente nueva sería un riesgo en vez de una garantía.

---

## Por qué el llamador puede subir pero no bajar

Un llamador conoce cosas que el sistema no: que este request va a un informe regulatorio,
que el resultado se publica, que hay un auditor mirando. Nada de eso está en el material.
Así que puede pedir más.

Lo que no puede es pedir menos, porque el piso sale de propiedades **del request mismo**:
`irreversible` eleva a A3, `shared_writes` a A2, y las dos entran como creencias `COMPUTED`
declaradas por el caller —nunca inferidas del texto—. Un llamador que pudiera bajar el piso
podría declarar una acción irreversible y después pedir tratarla como exploratoria, que es
exactamente la combinación que el piso existe para impedir.

> **Y el piso aprendido viaja firmado, a propósito.** `θ.floors` va dentro del payload del
> bundle. Un request no se puede endurecer por nada que no haya pasado la guarda de
> promoción — si el piso llegara por fuera de la firma, cualquier estadística de rechazo
> podría subir el nivel de una región sin que nadie lo revisara.

---

## La cuarta fuente, que no es un nivel sino una degradación

Hay un caso que no se resuelve con `max` y por eso está aparte: **A2 admite creencias
`ELICITED`, pero sólo una vez que la calibración se ganó.** Admitirlas mientras su confianza
declarada no está verificada anula el propósito del nivel — el nivel diría que rinde cuentas
y estaría aceptando opiniones sin contrastar.

Así que `resolve()` no baja el nivel: **endurece el piso de procedencia dentro del nivel**.
A2 sin calibración exige `OBSERVED`. Es la misma idea que el `max`, aplicada al otro eje.

---

## Cómo se evalúa: marginalizando, no fijando una posición

Reportar métricas a un dial fijo es reportar una política, no un sistema. El dial es un
parámetro del despliegue, y un número medido en A1 no dice nada de lo que pasa en A3.

`_analyze_ratchet_cost.py` recorre las cuatro posiciones sobre el mismo registro y reporta
cobertura y utilidad en cada una. Lo que salió (lección 5.12):

| nivel | brazos | cobertura | u(mejor fijo) |
|---|---:|---:|---:|
| A0 | 5 | 100% | 0,6101 |
| A1 | 5 | 100% | 0,6101 |
| A2 | 5 | 100% | 0,6101 |
| **A3** | **2** | **40%** | **0,4221** |

**Tres de las cuatro posiciones son indistinguibles.** A0/A1/A2 declaran
`admissible_patterns=None`, así que el dial no restringe nada hasta A3. Eso es un hallazgo
sobre el dial, no sobre el corpus: **dos de sus tres transiciones no hacen nada al catálogo
de paradigmas**, y toda la diferencia se paga en un solo escalón.

Lo que sí distingue a A1 de A2 vive en otros ejes —`require_signed_theta`,
`log_belief_base`, `max_composition_depth`, y el piso de procedencia—, así que el dial no es
inerte ahí; es inerte **en la dimensión que esta tabla mide**. Decir cuál es cuál es el
punto de marginalizar.

---

## El resumen en una línea

**El llamador pide, el request impone, lo aprendido impone, y el máximo gana.** Nadie fija
el dial solo, y ninguna fuente puede ablandarlo — que es la propiedad que hace que agregar
una fuente nueva sea seguro por construcción.

Verificado en `tests/test_science.py` §47.
