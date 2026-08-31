# mapo

**Una capa de decisión determinista para agentes LLM** — la capa de decisión, el banco que
la mide, y el paper que la valida.

---

## Qué hay acá adentro

```
   ┌─────────────────────────────────────────────────────────────────────┐
   │                              MAPO                                    │
   ├──────────────────────┬──────────────────────┬───────────────────────┤
   │       lab/           │     whitepaper/      │      legacy/          │
   │                      │                      │                       │
   │  la capa de decisión │  el paper que la     │  capa de ejecución    │
   │  + el banco que la   │  valida              │  anterior, CONGELADA  │
   │  mide                │                      │                       │
   │                      │  paper-en.md canónico│  no es el producto y  │
   │  el producto se      │  paper-es.md espejo  │  no se evoluciona     │
   │  construye desde lo  │                      │                       │
   │  que el banco prueba │  GATE.md manda sobre │  se conserva como     │
   │                      │  qué se puede afirmar│  referencia de lo que │
   │                      │                      │  el banco nunca tuvo  │
   │                      │                      │  que modelar          │
   └──────────────────────┴──────────────────────┴───────────────────────┘
              │                      ▲
              │  nada entra al paper │
              └──────────────────────┘
                sin implementación que lo corra
```

- **[`lab/`](lab/README.md)** — la capa de **decisión** y el banco de medición:
  factibilidad aritmética → creencias con procedencia → dial de garantía por request
  (A0–A3, con un piso que **aprende de estadísticas de rechazo tipado**) → ruteo selectivo
  con abstención → una sonda ejecutada que convierte una opinión en observación → el
  artefacto EXPLAIN, reproducible por digest de la base de creencias. Los corpus, las
  predicciones registradas y la dirección REC viven acá.
- **[`whitepaper/`](whitepaper/README.md)** — el paper (`paper-en.md` canónico,
  `paper-es.md` espejo; **toda edición va a los dos, en la misma posición**, y una
  auditoría lo hace cumplir). `GATE.md` manda sobre qué se puede afirmar.
  [`whitepaper/artefactos/`](whitepaper/artefactos/README.md) versiona los documentos
  visuales.
- **[`legacy/`](legacy/README.md)** — una capa de ejecución anterior, **CONGELADA**. No es
  el producto y no se evoluciona: se conserva como referencia de las partes que un
  despliegue real necesita y el banco nunca tuvo que modelar — búsqueda sobre índice real,
  scoping por permisos, citas verificadas contra ese índice, streaming a un cliente.
- **[`ui/`](ui/README.md)** — la consola de prueba (Vite + React 19 + TypeScript). Consume
  los mismos eventos tipados de `/v1/answer` y trae un modo demo para trabajarla sin motor
  y sin gastar tokens.

---

## Los tres que no se pueden mezclar

Dos de ellos son un solo directorio hoy, y por eso hace falta decirlo:

| | |
|---|---|
| **el producto** | la capa de decisión (factibilidad, creencias, garantía, ruteo, sonda, EXPLAIN) y los paradigmas que sobreviven a la medición |
| **el banco** | corpus, runner, grading, metrics, predicciones registradas, tests — **mide** al producto y no es parte de él |
| **`legacy/`** | referencia congelada de recuperación, scoping, citas y streaming |

La regla que los mantiene separados cuando se partan: **el banco importa al producto; el
producto nunca sabe que el banco existe.**

---

## Lo vigente (2026-08-30)

> **Esta sección es sólo el estado de hoy.** La cronología —qué se predijo, qué se refutó y
> cuándo— vive en `lab/historico/`. Un README que acumula historia deja de decir dónde está
> el proyecto y pasa a decir por dónde pasó, que es otra pregunta.

**El registro está completo y el plantel corrió entero.** 78 tareas × 12 paradigmas × 3
réplicas sobre `gold_h1`, 121,4M tokens. `bench/_listo.py` pasa 9/9 y la auditoría de
plomería reporta por primera vez que **todo brazo que llama a una herramienta obtiene su
efecto**.

### Los cuatro resultados que gobiernan

**1. El ruteo por calidad no tiene premio en este corpus, y ahora se sabe por qué.** Hay
interacción real —γ es el 48% de la varianza, con señal/ruido 5,30— y hay una señal que la
explica: `cardinalidad × término literal` captura dos tercios del techo y sobrevive la
corrección por selección. Pero **esa interacción vive entre brazos que nadie elegiría**:
restringida a los tres que compiten, γ real cae a 0,0046 con señal/ruido **0,38**, ninguna
señal los separa (`p > 0,29`), y el premio neto da **−0,008**. `gist_reader` aporta el 20%
de γ; los tres punteros, 6-7% cada uno.

**2. `react` gana por no destruir, no por buscar mejor.** Partida la utilidad en
`P(vio las portadoras) × P(contestó bien | las vio)`, `react` ve el **60%** y `gist_reader`
el **77%** — pero con el material a la vista `react` da 0,970 y `gist_reader` 0,594, *peor
que cuando no lo vio todo*. Cada representación intermedia más chica que el material es una
pérdida que no se recupera aguas abajo. `react` no tiene ninguna.

**3. El promedio escondía la mitad que importa.** `pass^3` —acertar en las tres réplicas—
cae entre **0,078 y 0,196** por brazo, y entre el **17% y el 34%** de las celdas cambian de
resultado con `t=0`, semilla fija y la misma huella. Eso corrige nuestra propia afirmación
de «determinismo casi al token»: es cierto **por llamada** y falso **por trayectoria**.

**4. Un sensor determinista compra utilidad y determinismo a la vez.** `pointer_chase` pasa
de **0,33 a 0,89** en la celda de cadenas acopladas tras cuatro correcciones de flujo de
control, ninguna de fraseo: una regla de creencias (entidad nombrada ⇒ índice léxico, no
híbrido), tipar la salida del sensor antes de usarla, verificar que un salto realmente
nombre a quien se persigue, y resolver el ancla con código en vez de con una llamada. La
última lo prueba sola: **con la misma huella y los mismos resultados de búsqueda**, una
réplica elegía la unidad correcta (u=1,000) y las otras dos otra (u=0,000).

### El harness, contra la literatura

Se contrastó contra lo que exigen [ABC](https://arxiv.org/abs/2507.02825),
[AI Agents That Matter](https://arxiv.org/abs/2407.01502), [HAL](https://arxiv.org/abs/2510.11977),
[Adding Error Bars to Evals](https://arxiv.org/abs/2411.00640) y
[tau2-bench](https://github.com/sierra-research/tau2-bench). Tabla completa en
`lab/bench/README.md`.

**Cubierto, y varias cosas por encima de la práctica publicada:** sin juez LLM (así que el
sesgo del juez no existe), sin pases gratis (una respuesta vacía da `0,0` — el fallo que
τ-bench tiene), contaminación estructuralmente imposible por corpus generado, costo con
prompt/completion separados y aranceles con procedencia, y nulos por permutación **con
corrección por selección**. Cerrado el 2026-08-30: **`pass^k`** (`bench/fiabilidad.py`, y va
en el marcador) y **auditoría de oráculo** (`bench/audits/_audit_oraculo.py` — 0 de 567 ceros
con señal fuerte de defecto del corrector; la auditoría equivalente de OpenAI encontró 59,4%
en SWE-bench Verified).

**Lo que falta, en orden:** el **holdout** —que es el criterio de éxito escrito del producto
y no existía como medición válida; su única corrida estaba en el archivo pre-K6 sin estampar
y no replayable—, desenredar **modelo de harness**, un **eje de seguridad** adversarial, y
usar la **latencia** en alguna decisión: está medida en el 100% de las filas, hay 3,6× de
rango entre brazos, y ninguna decisión la mira.

---

## Cómo se llegó hasta acá (hasta 2026-08-29)

> Se conserva porque **explica los veredictos vigentes**, no porque describa el estado.
> Lo que pasó después está arriba.

### El registro previo


**La afirmación del producto sigue refutada, y el mecanismo ES el hallazgo.** Sobre un
mundo que θ nunca había visto —seed 47, 390 celdas, cero errores de infraestructura— el
ruteo por request perdió contra el mejor paradigma fijo por **−0,087**, más allá del piso
de ruido, mientras reproducía cada decisión 26/26 desde su base de creencias registrada.

Mecanismo verificado: **el vocabulario de región no tiene eje de horizonte**, así que las
tareas que castigan una elección fija eran indistinguibles de las que la premian. Reparar
la validez del aprendizaje —agregación por episodio, holdout limpio— **deja el número
idéntico**: la refutación no es un artefacto del procedimiento.

**Y la campaña homogénea le puso un número a por qué.** Sobre las 21 tareas donde corrieron
los nueve brazos: la brecha de oráculo da **+9,5 pp**, y contra el ruido **de cada tarea**,
**ninguna de las 21 la supera**. En **17 de 21 el mejor fijo YA es el oráculo** — sólo 3
tareas tienen un único mejor brazo.

> **θ no perdió por ser mal router: casi no había premio que capturar en ese estrato.** Es
> el régimen que el paper ya llamaba «casi tautológico», ahora con el número.

**Tres mecanismos medidos que apuntan al mismo lado.** El costo crece como `N²` y la
cobertura como `N` —≤2 llamadas dan 9.779 tokens, ≥8 dan 136.432, por +0,122 de utilidad—
porque la conversación se reenvía entera en cada vuelta — y **el 99% del gasto de entrada
es re-envío**, trazado por llamada: el turno 0 cuesta 607 tokens de prompt y el turno 8
cuesta 67.233. **Alrededor de la mitad de todas las búsquedas no traen nada nuevo** —48,7%,
51,7% y 57,2% por estrato— y lo que escala con el ancho no es la tasa sino la **racha**:
20, 12, **46** búsquedas seguidas sin nada nuevo. El ancho no hace que se busque en vano más
seguido; hace que se **insista mucho más antes de rendirse**.

**La dirección REC tiene veredicto, y es negativo.** Reparación Epistémica Contrafactual
está implementada y corrida —diagnóstico contrafáctico con esquema cerrado y firmado, tres
mundos disjuntos, mundo final de un solo uso, instalación fail-closed— y **la cláusula no
se promueve**: el beneficio neto da `+0,0311` contra un piso de ruido de `0,0655` al `λ`
con que decide el banco. Diseño en `lab/PATRON_REC.es.md`.

**Cierre de la sesión del 2026-08-29**, con todo lo implementado y verificado:
`lab/historico/IMPLEMENTACION-2026-08-29.es.md`.

---

## El orden del trabajo

**El producto se construye desde lo que el banco prueba, no al revés.** `lab/` sigue
midiendo patrones y validándolos; el motor arranca cuando ese registro esté lo bastante
maduro. Hasta entonces no se porta nada.

La arquitectura física, cuando arranque, ya está decidida y es reversible:
`lab/ARQUITECTURA.es.md`. On-prem y Docker, Weaviate, Postgres como ledger, FastAPI con SSE
resumible. **Temporal todavía no** —entra sólo si se cumple uno de tres gatillos escritos—
y **LangGraph nunca**. Observabilidad con Langfuse y su propio SDK, **con el producto y no
antes**: hoy no hay servicio que trazar.

---

## Antes de gastar un token

```powershell
py tests\test_science.py            # 67 chequeos, 670 aserciones
py tests\test_consolidation.py
py corpus\verify.py --corpus corpus\<nombre>
py bench\_listo.py                  # las nueve condiciones de lanzamiento
```

Y tres reglas que no son de estilo: **predicciones falsables registradas con fecha antes de
correr**, **`repeat ≥ 3` con piso de ruido por celda**, y **estimar contra el corpus, nunca
contra el registro** — estimar desde una corrida parcial costó una vez un error de 34×.
