# §5.1 reescrita — el Teorema 1 en `k` brazos, con selectividad de pérdida

> **Propuesta de reemplazo para §5.1.** No es una corrección al margen: es el mismo
> resultado enunciado sobre lo que el banco de verdad mide, con los tres corolarios
> arreglados. Todo lo de acá está verificado numéricamente; los contraejemplos van con su
> número.
>
> **Nada de esto entró todavía a `paper-en.md` ni a `paper-es.md`.** Cuando entre, va a los
> dos, en la misma posición.

---

## El diagnóstico, en una frase

Los cuatro problemas de §5.1 son **el mismo problema**:

> **`π`, `α` y `β` responden *si* el router acierta. `G`, `L` y `ρ` responden *cuánto cuesta
> cuando no*. El enunciado actual trata los dos ejes como uno, y cada corolario se rompe en
> el punto donde esa distinción importaba.**

| corolario | dónde se rompe | qué eje se confundió |
|---|---|---|
| 2 — umbral de imposibilidad | **es falso**: contraejemplo lo supera 23× y el router gana | usa `β` (probabilidad) contra `L` (magnitud) sin decir cómo se relacionan |
| 3 — cobertura óptima | unimodalidad **no se sigue** de la calibración | la calibración ordena por probabilidad; el valor depende de la magnitud |
| — los empates | `β = 0,714` con **cero** daño real | `β` cuenta ruteos, no daños |
| — dos brazos | el banco tiene doce | `S` no está definido con `k > 1` |

Arreglar los cuatro con una sola idea es lo que hace que valga reescribir en vez de parchar.

---

## Teorema 1′ (descomposición por destino, con empates)

Sea `p⋆` el fallback y `p_1 … p_k` los especialistas. Sea `r` el router, y

```
Δ_j(t) = u(t, p_j) − u(t, p⋆)
```

Para cada brazo `j`, partir el espacio de tareas **en tres**, no en dos:

```
S₊ʲ = { Δ_j > 0 }     ganancia estricta      π_j = Pr[S₊ʲ]
S₀ʲ = { Δ_j = 0 }     empate                 τ_j = Pr[S₀ʲ]
S₋ʲ = { Δ_j < 0 }     pérdida estricta       ν_j = Pr[S₋ʲ]
```

y definir, **condicionando a lo efectivamente ruteado**:

```
α_j = Pr[r → p_j | S₊ʲ]        G_j = E[ Δ_j | r → p_j , S₊ʲ ]
β_j = Pr[r → p_j | S₋ʲ]        L_j = E[ −Δ_j | r → p_j , S₋ʲ ]
```

> **`β_j` se define sobre `S₋ʲ` y no sobre el complemento de `S₊ʲ`.** Ésa es la corrección de
> los empates, y no es cosmética: un router que rutea sobre un empate no comete ningún daño
> y el enunciado anterior lo contaba como error.

**Teorema 1′.**

```
V(r) − V(p⋆)  =  Σⱼ ( π_j · α_j · G_j  −  ν_j · β_j · L_j )
```

**exactamente**, para todo `k ≥ 1`, sin ninguna hipótesis de independencia.

**Demostración.** `V(r) − V(p⋆) = E[ Δ_{r(t)}(t) · 1{r(t) ≠ p⋆} ]`. Descomponiendo por
destino, `= Σⱼ Pr[r→p_j] · E[Δ_j | r→p_j]`, y partiendo cada esperanza condicional según el
signo de `Δ_j`: la parte de `S₊ʲ` pesa `Pr[r→p_j ∧ S₊ʲ] = π_j α_j` con media `G_j`, la de
`S₋ʲ` pesa `ν_j β_j` con media `−L_j`, y **`S₀ʲ` aporta exactamente cero** porque `Δ_j = 0`
ahí. ∎

**Verificado:** 4.000 distribuciones al azar con `k` de 1 a 4 —**3.269 de ellas con
empates**— y ruteos arbitrarios. Discrepancia máxima **1,67 × 10⁻¹⁶**.

> **El Teorema 1 original es el caso `k = 1` sin empates.** No se descarta: se generaliza.
> Y la generalización es la que el banco mide, porque el catálogo tiene doce brazos y el
> ruteo elige entre todos.

### Lo que esto arregla, y que no era evidente

**La brecha de oráculo deja de ser `π·G`.** Con `k` brazos la brecha real es
`E[maxⱼ u(t,p_j)] − E[u(t,p⋆)]`, que **no** es `π_j·G_j` de ningún par fijo. El párrafo
«Identity» del paper —del que cuelga la lectura de los 17,1 pp publicados— vale para dos
brazos y hay que decirlo. Con `k` brazos la identidad correcta es

```
brecha de oráculo  =  E[ maxⱼ Δ_j⁺ ]      con  Δ⁺ = max(Δ, 0)
```

que **no se factoriza** en un producto de dos números. Leer un `β` implícito desde un
titular publicado sólo es legítimo si ese trabajo reporta un par, no una grilla.

---

## Corolario 2′ (el umbral, parametrizado por selectividad de pérdida)

**Qué estaba mal.** El enunciado actual —`β_max = π·α·G_α / ((1−π)·L)`, y *«cualquier router
por encima pierde»*— es **falso**. Contraejemplo, tres tareas:

| | prob | `Δ` | ¿ruteada? |
|---|---:|---:|---|
| ganancia | 0,10 | **+0,10** | sí |
| pérdida ínfima | 0,45 | −0,001 | **sí** |
| pérdida enorme | 0,45 | **−1,00** | no |

```
β = 0,500        β_max = 0,0222        β lo supera 23×
V(r) − V(p⋆) = +0,00955   ->  el router GANA
```

El teorema opera con `L_j` —la pérdida sobre lo **ruteado**— y el umbral se define con la
pérdida **distribucional**. Un router que **evita las pérdidas caras** se equivoca seguido y
barato, y eso es exactamente lo que un ruteo selectivo bien hecho produce.

**Y no alcanza con cambiar `L` por `L_j`**, porque `metrics.py` ya tiene escrito por qué:

> *«Using the realised loss makes the threshold circular, and a perfect router (which
> misroutes nothing, so realises no loss) would report `beta_max = infinity` and appear to
> face no constraint at all.»*

**Las dos objeciones son ciertas.** La salida es no elegir entre ellas.

**Definición (selectividad de pérdida).**

```
L̄_j = E[ −Δ_j | S₋ʲ ]        la pérdida media de la TAREA          (no depende del router)
ρ_j = L_j / L̄_j              la SELECTIVIDAD del router            (ρ_j := 1 si β_j = 0)
```

**Corolario 2′.** El router pierde contra siempre-fallback si y sólo si

```
Σⱼ π_j·α_j·G_j   <   Σⱼ ν_j·β_j·ρ_j·L̄_j
```

y con un solo brazo,

```
β_max(ρ) = π·α·G / ( ν · ρ · L̄ )
```

| `ρ` | qué router es | qué hace el umbral |
|---|---|---|
| **ρ = 1** | **ciego a la magnitud**: se equivoca de forma representativa | **el enunciado original, y ahí sí es exacto** |
| ρ < 1 | evita las pérdidas caras | se **afloja** |
| ρ > 1 | anti-calibrado: falla justo donde más duele | se **endurece** |

Sobre el contraejemplo: `ρ = 0,0020`, `β_max(ρ) = 11,1`, y `β = 0,500 < 11,1`. **Coherente
con que el router gane.**

**Y la circularidad se disuelve sola.** Con un router perfecto, `β = 0` y el término de
pérdida `ν·β·ρ·L̄` **vale cero antes de que `ρ` importe**. La división por cero desaparecía
porque el problema nunca fue la pérdida realizada: era ponerla **en el denominador de un
umbral**. Como **factor de la pérdida**, se comporta.

> **Corolario 2′b (y es el que le sirve al argumento del paper).** Un router obligado a
> elegir no controla ni `β` ni `ρ`. Uno selectivo controla los dos — y **`ρ` es la palanca
> barata**: bajar `β` exige *acertar más*; bajar `ρ` sólo exige *abstenerse donde la apuesta
> es cara*. Eso le da al Corolario 1 —precisión sobre cobertura— un **mecanismo**, y no sólo
> una desigualdad.

**`ρ` ya es medible.** `metrics.py` calcula `loss_potential` y `loss_realised`, que son
`L̄` y `L`. El cociente está a una división, y es una propiedad **interpretable** del
router: dice si su confianza correlaciona con el **tamaño** del error o sólo con su
existencia.

---

## Corolario 3′ (cobertura óptima)

**Qué estaba mal.** *«With a calibrated confidence and a variable threshold, captured value
is unimodal in coverage»*. La unimodalidad **no se sigue** de la calibración.

**Contraejemplo con confianza perfectamente calibrada** (`Pr[acertar | κ] = κ` en cada
grupo):

| grupo | prob | κ | Δ si acierta | Δ si falla | `E[Δ]` |
|---|---:|---:|---:|---:|---:|
| A | 0,30 | 0,90 | +0,01 | −0,01 | **+0,0080** |
| B | 0,40 | 0,60 | +0,05 | −0,50 | **−0,1700** |
| C | 0,30 | 0,30 | +2,00 | −0,01 | **+0,5930** |

```
cobertura   0,00      0,30      0,70      1,00
valor       0,0000   +0,0024   −0,0656   +0,1123

cambios:      +         −         +        ->  NO es unimodal
```

**Y el óptimo está en cobertura 1,00**, que es lo contrario de lo que el corolario afirma.

**Por qué.** La calibración ordena por **probabilidad de acertar**; el valor depende de la
**magnitud**. El grupo C acierta poco y, cuando acierta, gana 2,00 — bajar el umbral hasta
incluirlo vuelve a subir el valor después de que B lo hundió.

**Corolario 3′.** Sea `V(c)` el valor capturado a cobertura `c`. Entonces

```
dV/dc  =  E[ Δ | tarea marginal a cobertura c ]
```

y por lo tanto:

**(a)** `V` es unimodal **si y sólo si** `c ↦ E[Δ | marginal a c]` es no creciente — es
decir, **si y sólo si la confianza ordena las tareas por ganancia esperada**, no por
probabilidad de ganar. Eso es una condición sobre la señal, es más fuerte que la
calibración, y **es chequeable sobre el registro**.

**(b)** Sin ninguna hipótesis: **la cobertura óptima es `< 1` siempre que exista alguna
tarea con `Δ_{r(t)}(t) < 0` que el router rutearía a cobertura total.** La demostración es
una línea —sacar un término negativo aumenta la suma— y **es todo lo que el paper necesita**.

> **Recomendación: quedarse con (b) en el cuerpo y (a) en una nota.** El paper usa la
> unimodalidad sólo para decir «el óptimo está bastante abajo de 1», y (b) lo da sin pedir
> nada. Reclamar unimodalidad es reclamar de más y regalar un contraejemplo.

---

## Corolario 1, que sobrevive intacto

*«When `p⋆` is near-optimal over wide regions, `G` is small and `L` large, so the condition
demands `β → 0` even at the cost of `α`. Recall is not the objective.»*

Sigue siendo cierto y ahora tiene **dos** mecanismos en vez de uno: bajar `β` **o** bajar
`ρ`. La versión fuerte:

> **Corolario 1′.** Cuando el fallback es casi óptimo, lo que hay que minimizar no es la
> tasa de misruteo sino el **producto** `β·ρ`. Un router que se equivoca la mitad de las
> veces pero sólo donde no cuesta domina a uno que se equivoca poco y caro.

---

## Qué cambia en el resto del paper

| dónde | qué |
|---|---|
| §5.1 «Identity» | vale para **dos brazos**. Con `k`, la brecha es `E[maxⱼ Δ_j⁺]` y no se factoriza — leer un `β` implícito desde un titular publicado exige que ese trabajo reporte un par |
| §5.1 «verified in `tests/test_science.py`» | el test verifica la identidad, que es cierta. **No** verifica el Corolario 2 como universal, porque no lo es. Hay que reformular la frase |
| §5.2 | **no se toca.** La cascada y la sensibilidad del detector son lo falsable que este registro cerró, y están bien |
| el párrafo de la degeneración | **no se toca.** Reportar que el instrumento no midió nada es lo mejor que tiene la sección |

---

## Por qué esto es más publicable que lo que hay

Lo que hoy es *«una identidad exacta con una salvedad honesta»* pasa a ser:

1. una **descomposición de `k` brazos** — la que el banco de verdad mide;
2. con los **empates separados**, así que `β` significa lo que un lector cree que significa;
3. **parametrizada por selectividad de pérdida**, que convierte un universal falso en una
   familia con el enunciado original como su caso `ρ = 1`;
4. y con `ρ` **medible desde el registro que ya existe**.

Y el hilo que las une —**probabilidad de errar y costo del error son dos ejes**— es un
enunciado corto, defendible, y que el propio registro de este proyecto ilustra: `rewoo`
empata seguido y barato; `dag_strategy` acierta más y cuesta 37×.

**Verificación:** `teorema2.py` (scratchpad de la sesión). 4.000 distribuciones para la
identidad, más los dos contraejemplos. Python puro, sin dependencias del lab. Conviene
moverlo a `lab/bench/audits/` cuando la campaña termine.
