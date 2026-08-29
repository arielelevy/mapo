# Revisión de §5.1 — el Teorema 1 y sus tres corolarios

> **Qué es esto.** Una revisión adversarial de la parte formal del paper, con
> contraejemplos ejecutables. **Propuestas, no ediciones**: nada de acá entró todavía a
> `paper-en.md` ni a `paper-es.md`.
>
> **Cómo se leyó.** Cada enunciado se verificó por álgebra y después se lo atacó
> numéricamente. Lo que sobrevive se dice que sobrevive; lo que se cae viene con el
> contraejemplo al lado, porque un defecto sin contraejemplo es una opinión.
>
> **El veredicto corto.** El **Teorema 1 es correcto** —y su corrección es más fuerte de
> lo que el paper reclama—. **El Corolario 2 es falso como está enunciado**, y el arreglo
> lo convierte en algo publicable en vez de en una salvedad. Los Corolarios 1 y 3 necesitan
> hipótesis que hoy no están escritas.

---

## 0. Lo que sí se sostiene, y conviene decirlo primero

**El Teorema 1 es una identidad exacta.** Verificado sobre **2.000 distribuciones al azar**
con ruteos arbitrarios: la discrepancia máxima entre `V(r) − V(p⋆)` y
`π·α·G_α − (1−π)·β·L_β` fue **1,67 × 10⁻¹⁶** — error de punto flotante y nada más.

Y la decisión de diseño que lo hace exacto está bien tomada y bien explicada: **condicionar
`G` y `L` a los subconjuntos RUTEADOS**, no a `S`. Eso elimina toda hipótesis de
independencia entre «dónde se gana» y «dónde el router elige ir», que es exactamente donde
un resultado así se rompe en la práctica.

> **Y el paper ya se autolimita bien.** El párrafo «What Theorem 1 is, and what it is not»
> —identidad, no falsable, lo empírico es sólo si sus términos satisfacen la desigualdad— es
> la clase de honestidad que casi nadie escribe, y **no habría que suavizarlo**. Lo que sigue
> refuerza esa disciplina, no la contradice.

---

## 1. `Corolario 2 es falso como está enunciado` · **contraejemplo**

**Lo que dice hoy:**

> **Corollary 2 (impossibility threshold).** `β_max = π·α·G_α / ((1−π)·L)`. Any router above
> it loses to always-fallback however good its specialists are.

**El contraejemplo**, con tres tareas:

| | prob | `u(p_s)` | `u(p⋆)` | Δ | ¿la rutea? |
|---|---:|---:|---:|---:|---|
| en `S` | 0,10 | 0,60 | 0,50 | **+0,10** | sí |
| fuera de `S`, pérdida ínfima | 0,45 | 0,499 | 0,50 | −0,001 | **sí** |
| fuera de `S`, pérdida enorme | 0,45 | 0,00 | 1,00 | **−1,00** | no |

```
π = 0,10   α = 1,00   G_α = 0,100
β = 0,500        L_β = 0,0010        L (distribucional) = 0,5005
β_max = 0,0222

β  supera  β_max  por  22×
V(r) − V(p⋆) = +0,00955      ->  el router GANA
```

**Por qué pasa, y no es un caso patológico.** El teorema opera con `L_β` —la pérdida sobre
lo **efectivamente ruteado**— y el corolario define su umbral con `L` **distribucional**.
Cuando el router **evita las pérdidas grandes**, `L_β ≪ L` y el umbral deja de ser una
imposibilidad. Un router que se equivoca *seguido pero barato* es exactamente el objeto que
un ruteo selectivo bien construido produce.

### Y el paper no puede simplemente cambiar `L` por `L_β`

`app/metrics.py` ya sabe por qué, y lo tiene escrito:

> *«`beta_max` must be computed from `loss_potential`. Using the realised loss makes the
> threshold circular, and a perfect router (which misroutes nothing, so realises no loss)
> would report `beta_max = infinity` and appear to face no constraint at all.»*

**Las dos objeciones son ciertas a la vez**, y ésa es la parte interesante:

| con | qué se rompe |
|---|---|
| `L` distribucional | deja de ser umbral: el contraejemplo lo supera 22× y gana |
| `L_β` realizada | se vuelve circular: un router perfecto reporta `β_max = ∞` |

### La propuesta: parametrizar por selectividad de pérdida

Definir

```
ρ  =  L_β / L          la SELECTIVIDAD DE PÉRDIDA del router
```

y enunciar

```
β_max(ρ)  =  π·α·G_α / ((1−π)·ρ·L)
```

Entonces:

| ρ | qué router es | qué dice el umbral |
|---|---|---|
| **ρ = 1** | **ciego a la magnitud de la pérdida** — se equivoca de forma representativa | **el corolario actual, y ahí SÍ es exacto** |
| ρ < 1 | evita las pérdidas grandes | el umbral se **afloja**: puede tener β alto y ganar |
| ρ > 1 | anti-calibrado: se equivoca justo donde más duele | el umbral se **endurece** |

**Esto convierte un universal falso en una familia con el enunciado original adentro**, y
gana tres cosas:

1. **Deja de ser falsable por un contraejemplo de tres tareas.**
2. **`ρ` es medible desde el registro** — `metrics.py` ya calcula `loss_potential` y
   `loss_realised`, que son exactamente `L` y `L_β`. El cociente está a una división.
3. **`ρ` es una propiedad interpretable del router**, no un artefacto: dice si su
   confianza correlaciona con el **tamaño** del error o sólo con su existencia. Un router
   con ρ < 1 «sabe dónde no arriesgarse», y eso es una capacidad distinta de la precisión.

**Y hay un corolario nuevo, gratis, que le sirve al argumento central del paper:**

> **Un router obligado a elegir no controla ni `β` ni `ρ`.** Uno selectivo controla los dos,
> y **`ρ` es la palanca más barata**: bajar `β` exige acertar más, bajar `ρ` sólo exige
> abstenerse donde la apuesta es cara. Eso refuerza el Corolario 1 —precisión sobre
> cobertura— con un mecanismo, y no sólo con una desigualdad.

---

## 2. Los empates inflan `β` sin causar daño · **medido**

`S` se define con desigualdad **estricta**: `S = {t : u(t,p_s) > u(t,p⋆)}`. Así que los
**empates** (`Δ = 0`) caen fuera de `S`, y rutear sobre un empate cuenta como
«rutear fuera de `S`».

```
router que rutea SOLO donde gana y donde EMPATA (nunca donde pierde):

   β = 0,714          <- no cometió un solo error dañino
   L_β = 0,000        <- la pérdida es exactamente cero
   V(r) − V(p⋆) = +0,120
```

**El producto `β·L_β` sigue correcto** —`L_β` absorbe el cero— así que **el Teorema 1 no se
toca**. Pero en el **Corolario 2**, que usa `β` y `L` por separado, ese `β` inflado mueve el
umbral.

**Y no es un caso de laboratorio.** Este registro está lleno de empates: la auditoría de
catálogo reporta a `rewoo` como *«el más barato al empatar en 46 celdas»*. Un corpus donde
varios paradigmas resuelven la misma tarea produce empates por construcción.

**Propuesta:** partir el complemento en tres y decirlo en el enunciado.

```
S₊ = {Δ > 0}     ganancia
S₀ = {Δ = 0}     empate      -> contribuye EXACTAMENTE cero, en los dos sentidos
S₋ = {Δ < 0}     pérdida
```

Con `β` definida sobre `S₋` en vez de sobre el complemento, `β` pasa a ser **la tasa de
misruteo dañino** y el Corolario 2 se vuelve ajustado en vez de conservador. La identidad
del Teorema 1 no cambia: `S₀` aporta cero a los dos lados.

> Y hay un beneficio de exposición: hoy `β` se lee como «tasa de falso positivo» y no lo es.
> Un lector que la interprete así va a subestimar sistemáticamente al router.

---

## 3. `Corolario 3` afirma unimodalidad sin hipótesis · **hueco, no error**

> **Corollary 3 (optimal coverage).** With a calibrated confidence and a variable threshold,
> captured value is unimodal in coverage and the optimum generally has coverage ≪ 1.

La conclusión es casi seguramente correcta y **la unimodalidad no se sigue de la
calibración sola**. Calibración dice que la confianza declarada coincide con la frecuencia
de acierto; no dice nada sobre cómo se **ordenan las magnitudes** `Δ` al bajar el umbral.

Un contraejemplo se construye con una distribución de `Δ` bimodal: ganancias grandes con
confianza media y ganancias chicas con confianza alta hacen que el valor capturado suba,
baje y vuelva a subir.

**Propuesta — una de las dos, no las dos:**

- **(a)** agregar la hipótesis que sí lo da: si `E[Δ | κ = c]` es **monótona no creciente**
  en el umbral `c`, el valor capturado es unimodal. Es la condición natural y se puede
  chequear sobre el registro.
- **(b)** bajar el enunciado a lo que el paper de verdad necesita, que es **más débil y
  suficiente**: *el óptimo tiene cobertura < 1 siempre que exista algún `t` con `Δ < 0` que
  el router rutearía*. Eso se prueba en una línea y sostiene el argumento igual.

**La (b) es la que yo elegiría.** El paper no necesita unimodalidad para nada — la usa sólo
para decir «el óptimo está bastante abajo de 1», y eso sale de (b) sin pedir nada.

---

## 4. El teorema es de DOS brazos y el banco tiene DOCE · **el hueco que más caro sale**

Éste no es un error: es un **hueco de alcance**, y es el que un revisor ataca primero.

El Teorema 1 se enuncia con **un** especialista: *«Let `p⋆` be the fallback and `p_s` a
specialist»*. `S`, `α`, `β`, `G` y `L` están todos definidos respecto de ese par. La campaña
mide **doce paradigmas**.

**Con `k` especialistas nada de eso sobrevive tal cual:**

- **`S` deja de estar bien definido.** ¿`S` es «algún paradigma le gana al fallback»? Entonces
  `G` no es la ganancia de *ninguno* en particular, y `π·G` deja de ser la brecha de oráculo.
- **`β` deja de ser un escalar.** Rutear mal tiene ahora un *destino*: mandar a un brazo
  apenas peor no es lo mismo que mandar al peor de los doce.
- **La brecha de oráculo real es `E[max_p u(t,p)] − E[u(t,p⋆)]`**, que **no** es igual a
  `π·G` para ningún par fijo. El párrafo «Identity» —del que cuelga la lectura de los 17,1pp
  publicados— vale para el caso de dos brazos.

**Propuesta — la honesta y la barata:**

**Declarar el alcance donde está el teorema**, con una frase: *«Theorem 1 is stated for one
specialist against the fallback. The multi-arm case is the same identity applied per arm,
and the oracle gap over `k` arms is not `π·G` for any single pair.»*

Y **después** —o en un apéndice— la extensión, que es corta y vale la pena porque ordena
todo el resto:

```
V(r) − V(p⋆) = Σ_j  Pr[r → p_j] · E[ u(t,p_j) − u(t,p⋆) | r → p_j ]
```

Ésta **sí** es exacta con `k` brazos, es la misma descomposición, y **el Teorema 1 es su
caso `k = 1`**. Cada término es un par (destino, ganancia media condicionada al destino), y
la lectura «precisión sobre cobertura» sobrevive sumando términos.

> **Por qué esto le conviene al paper y no le cuesta nada.** La versión de `k` brazos es la
> que el banco de verdad mide, así que enunciarla convierte una limitación en una
> generalización — y deja el caso de dos brazos como el corolario legible que hoy es la
> versión principal.

---

## 5. Lo que NO hay que tocar

Tres cosas que están bien y que una revisión apurada rompería:

**El párrafo de la degeneración.** *«the router's decision margin was 0 on every task, so the
risk–coverage curve collapses to a single point... the identity holds vacuously»*. Reportar
que el instrumento principal **no midió nada** es lo que casi ningún paper hace. **No
suavizarlo.**

**«The work a reader might credit to §5.1 is done by §5.2.»** Es una cesión voluntaria de
crédito y es correcta: lo falsable que este registro cerró es sobre cascada y sensibilidad
del detector, no sobre selección.

**La corrección de la cascada.** *«An earlier statement gave the cost term as `cost(p_1)`.
That is false.»* — con el 4,4× y el −5,98 al lado. Un error propio corregido con el número
que lo delató vale más que el enunciado original.

---

## Resumen para decidir

| # | qué | gravedad | qué cuesta arreglarlo |
|---|---|---|---|
| 1 | **Corolario 2 falso** — contraejemplo lo supera 22× y gana | **alta** | una definición (`ρ`) y dos filas de tabla; `metrics.py` ya calcula las dos pérdidas |
| 4 | teorema de 2 brazos, banco de 12 | **alta** (es lo que ataca un revisor) | una frase de alcance; la extensión es una línea de álgebra |
| 2 | empates inflan `β` | media | partir el complemento en tres |
| 3 | unimodalidad sin hipótesis | baja | bajar el enunciado a lo que el paper necesita |

**Los cuatro arreglos suman.** El 1 y el 4 juntos convierten §5.1 de «una identidad con una
salvedad» en **una descomposición de `k` brazos parametrizada por selectividad de pérdida**,
que es un enunciado más fuerte, más general y —esto es lo que importa— **medible con lo que
el registro ya tiene**.

**Verificación:** `teorema.py` (scratchpad de la sesión) — identidad sobre 2.000
distribuciones al azar, más los dos contraejemplos. Python puro, sin dependencias del lab.
Conviene moverlo a `lab/bench/audits/` cuando la campaña termine.
