# lab

**La capa de decisión de MAPO, y el banco que la mide.**

Este README describe **lo que hay hoy**. La cronología de predicciones y veredictos
—1.400 líneas que vivían acá adentro— se mudó a
[`historico/BITACORA-PREDICCIONES.es.md`](historico/BITACORA-PREDICCIONES.es.md), que
sigue siendo canónica: es la prueba de que cada predicción se escribió **antes** de ver
el número.

---

## Qué problema resuelve

Hay trabajo publicado que mide una **brecha de oráculo de 17,1 puntos** entre elegir el
paradigma de orquestación por tarea y quedarse con el mejor paradigma fijo
(Select-then-Solve, arXiv 2604.06753). El ruteador de ese trabajo recupera apenas el
**26%** de esa brecha, y cuando se le pide al LLM que se rutee solo el resultado es
**peor que no elegir**: Qwen3-30B cae a 27,5%, abajo de su propia línea base.

O sea: el premio es grande, nadie lo está agarrando, y elegir mal es peor que no elegir.

Este banco mide por qué, y prueba dos afirmaciones.

**Afirmación 1 — Teorema del valor de la selección.** Elegir le gana al mejor fijo sólo si

```
π · α · G  >  (1 − π) · β · L
```

Un ruteador **obligado a elegir siempre** no tiene control sobre `β` y paga cada falso
positivo. Uno **selectivo** —que se abstiene y cae a un fallback seguro cuando está fuera
de su región de confianza— sí lo tiene. La cobertura óptima suele estar bastante abajo de 1.

**Afirmación 2 — Dominancia de la cascada.** Donde existe un detector barato de fallas,
no predigas: probá lo barato, verificá, escalá. Un ruteador que se equivoca paga en
*calidad*; una cascada paga en *costo*. De ahí la partición:

```
v = 1 (hay oráculo)   →  CASCADA, no hace falta ruteador
v = 0 (no hay)        →  rutear, con la disciplina de abstención de la Afirmación 1
```

Si la Afirmación 2 se sostiene, buena parte de la literatura de ruteo está resolviendo el
problema equivocado en el régimen verificable.

---

## Cómo se decide un request

El LLM **nunca maneja el control de flujo**. Participa como **sensor**: emite
proposiciones tipadas sobre la tarea, con una credencia y una procedencia. Una capa
simbólica determinista decide sobre esa base de creencias.

```
                          request
                             │
   ┌─────────────────────────▼─────────────────────────┐
   │ 1. RASGOS            φ(request)                   │  features.py
   │    estructurales, baratos de extraer:             │
   │    cardinalidad · acoplamiento · hay oráculo ·     │
   │    horizonte · reversibilidad · escrituras ·      │
   │    presupuesto                                    │
   └─────────────────────────┬─────────────────────────┘
                             │
   ┌─────────────────────────▼─────────────────────────┐
   │ 2. FACTIBILIDAD      aritmética pura              │  feasibility.py
   │    SIN llamar al modelo. «Necesita 386k tokens    │
   │    en un solo prompt contra un permiso de 24k»    │
   │    → paradigma marcado infactible, costo CERO     │
   └─────────────────────────┬─────────────────────────┘
                             │
   ┌─────────────────────────▼─────────────────────────┐
   │ 3. CREENCIAS         el LLM como sensor           │  beliefs.py
   │    proposiciones tipadas + credencia + PROCEDENCIA│  rules.py
   │                                                   │
   │      COMPUTED > OBSERVED > ELICITED > ASSUMED     │
   │                                                   │
   │    una regla puede exigir un piso de procedencia: │
   │    una acción irreversible NO acepta la opinión   │
   │    del modelo como evidencia                      │
   └─────────────────────────┬─────────────────────────┘
                             │
   ┌─────────────────────────▼─────────────────────────┐
   │ 4. GARANTÍA          el dial A0–A3 por request    │  assurance.py
   │    el piso sale de las creencias sobre el request │
   │    mismo. El caller puede pedir MÁS, nunca menos  │
   └─────────────────────────┬─────────────────────────┘
                             │
   ┌─────────────────────────▼─────────────────────────┐
   │ 5. RUTEO SELECTIVO   Π(φ, θ) con ABSTENCIÓN       │  router.py
   │    emite un paradigma especializado sólo adentro  │  policy.py
   │    de la región de confianza (κ > τ); si no,      │
   │    difiere al fallback general.                   │
   │    θ es una lista de decisión versionada, firmada │
   │    y LEGIBLE — no son pesos.                      │
   │    Mismo φ y mismo θ ⟹ mismo plan.                │
   └─────────────────────────┬─────────────────────────┘
                             │
   ┌─────────────────────────▼─────────────────────────┐
   │ 6. EJECUCIÓN         el paradigma elegido corre   │  paradigms/
   │    contra la superficie de herramientas, que      │  tools.py
   │    lleva señales de contabilidad determinista     │
   │    (estancamiento, cobertura, contabilidad de     │
   │    ids) actuando como CORTACIRCUITOS: el loop no  │
   │    puede replanificar para siempre por intuición  │
   └─────────────────────────┬─────────────────────────┘
                             │
   ┌─────────────────────────▼─────────────────────────┐
   │ 7. EXPLAIN           el artefacto que queda       │  router.py
   │    φ, creencias con procedencia, nivel de         │
   │    garantía, veredictos, plan elegido, resultado. │
   │    Un auditor inspecciona lo que se afirmó y      │
   │    RE-EJECUTA LAS REGLAS — nunca el modelo.       │
   └───────────────────────────────────────────────────┘
```

### La garantía es propiedad del request, no del sistema

El determinismo total no existe con un LLM, así que prometerlo sería mentir. Perseguirlo
sacando al modelo de la decisión es peor: tira información que el modelo genuinamente
tiene y encima promete una garantía imposible. La garantía que **sí** se puede dar cambia
de forma:

```
NO    «el mismo prompt da la misma respuesta»           (falso, siempre)
SINO  «la misma base de creencias da la misma decisión»  (verdadero, y auditable)
```

El default está en el extremo flexible; la estrictez es una escalada que se paga. Un
nivel restringe el espacio de patrones admisibles; la plasticidad permuta libremente
adentro de ese espacio.

Los cuatro niveles son `Assurance.EXPLORATORY` … `CERTIFIED` (un `IntEnum`, 0 a 3). En los
documentos se los abrevia **A0–A3**; `A0_EXPLORATORY` no es un identificador y no existe en
el código.

| Nivel | Piso de procedencia | θ aprende online | Profundidad máx. | Patrones |
|---|---|---|---|---|
| **A0** `EXPLORATORY` | `ASSUMED` | **sí** | 8 | álgebra completa |
| **A1** `STANDARD` | `ELICITED` | no | 5 | catálogo |
| **A2** `ACCOUNTABLE` | `ELICITED`\* | no | 3 | catálogo |
| **A3** `CERTIFIED` | `OBSERVED` | no | 2 | subconjunto certificado |

\* admisible **sólo una vez calibrada**; sube a `OBSERVED` mientras la calibración no esté
ganada.

**Qué de ese perfil se impone de verdad, y qué sólo se declara** — la distinción importa
porque una garantía declarada y no impuesta es peor que ninguna:

| campo | quién lo impone |
|---|---|
| `theta_may_learn_online` | **`serve.py`**, alrededor del request entero. Antes vivía en el perfil y **no lo leía nadie**: la invariante «nada aprende adentro de un request» se cumplía **por casualidad**, porque `Plasticity.apply` sólo se llama offline. Una invariante que se cumple por casualidad la rompe el próximo cambio sin que nada avise |
| `require_signed_theta` · `log_belief_base` · `max_composition_depth` · `admissible_patterns` · `min_capability` | leídos y aplicados |
| `seal_replay` | **no lo lee nadie.** El sellado que sí existe (`LLMClient._sealed`, `embeddings.py`) es un mecanismo aparte que **no lo activa el dial**. O sea: A3 declara replay sellado y el dial no lo impone |

Un caller que pide `A0` sobre una tarea irreversible **obtiene `A3` igual**. Y eso achica
el espacio de planes: se excluyen los paradigmas de control no acotado, no porque sean
peores —seguido son mejores— sino porque sus modos de falla no se pueden enumerar. Por eso
`A3` es una escalada y no el default.

Y hay una decisión registrada en el código que conviene no perder: **A2 no exige piso de
capacidad, y no exigirlo es la decisión.** Poner `DEEP` ahí por el argumento de «rinde
cuentas» sería una política sin una sola medición detrás, y obligaría a pagar 25× en cada
request contable. Si el modelo barato alcanza a ese nivel de procedencia es una pregunta
**empírica**, y está registrada (`X-5g`). En A3 el argumento sí es estructural y no hace
falta medirlo: `decide_level` ya eleva a A3 toda acción irreversible, así que ese piso es el
que impide rutear lo irreversible al modelo más barato porque salga la cuenta.


---

## Cómo aprende sin volverse inauditable

El aprendizaje es **offline y copy-on-write**, nunca adentro de un request. Los episodios
se consolidan en una política **candidata** θ' —que sigue siendo una lista de decisión
legible sobre φ— y la promoción está guardada: θ' reemplaza a θ sólo si no regresa sobre
episodios held-out.

El registro se parte en tres por tarea, y esa partición es lo que le da sentido:

```
   search    →  propone la regla
   validate  →  la puntúa
   final     →  lo toca ÚNICAMENTE la guarda de promoción
```

Así una regla descubierta **nunca puede ser puntuada por los datos que la propusieron**.
Una θ promovida recibe versión; dos versiones se diffean como código, y volver atrás es
trivial porque las políticas viejas son artefactos inmutables.

Dos deudas que este README declaraba ya están cerradas, y vale decir por qué eran deudas:
la candidata se ajusta **sin** el bloque final (antes se ajustaba con todo y después se le
daba ese mismo bloque a la guarda, que es corregirse el propio examen), y un episodio es
una celda `(tarea, paradigma)` con utilidad media, **no** un trial (antes tres réplicas de
una tarea contaban como tres evidencias, y una réplica con suerte cobraba un refuerzo que
la media de su paradigma nunca ganó).

**Sigue abierta una:** el peso Hebbiano se almacena pero **no participa en la decisión** —
`policy.py` lo actualiza, `router.py` no lo lee ni una vez. Es la herencia de v1 y hoy es
un número que se guarda, no una señal que decide. Está en `DISENO.es.md` con su orden de
reparación.

---

## Qué garantiza, y qué no

| Garantizado | No garantizado |
|---|---|
| Misma base, reglas, bundle, candidatos y configuración ⟹ misma decisión, replayable desde el EXPLAIN | Mismo prompt ⟹ misma respuesta (imposible con un LLM, y nunca se reclama) |
| Un plan infactible nunca se intenta, y su exclusión queda registrada con la razón | Que el paradigma elegido tenga éxito — la selección acota el *regret*, no los resultados |
| Las acciones irreversibles se gatean sólo con evidencia computada u observada | Nada sobre tareas fuera de extracción de respuesta exacta sobre documentos |
| El incumbente se conserva cuando la guarda rechaza una candidata | Que la guarda actual esté libre de leakage estadístico |

---

## Cómo está partido el repo

La regla que evita que se vuelvan a mezclar: **el banco importa al producto; el producto
no sabe que el banco existe.**

```
   ┌──────────────── PRODUCTO ────────────────┐   ┌──────── BANCO ─────────┐
   │                                          │   │                        │
   │  la capa de decisión                     │   │  runner.py             │
   │    features · feasibility · beliefs      │◄──┤  grading · metrics     │
   │    rules · assurance · router · policy   │   │  corpus/ · tests/      │
   │    rec · certify · consolidation         │   │  bench/                │
   │                                          │   │                        │
   │  + los paradigmas de `paradigms/`        │   │  mide EXACTAMENTE lo   │
   │  + la superficie de tools                │   │  que producción corre  │
   └──────────────────────────────────────────┘   └────────────────────────┘
                        ▲
                        │  no depende de ningún orquestador,
                        │  y los paradigmas son funciones async planas
```

El banco es **sin framework, por diseño**. Si el ejecutor necesitara un runtime para
correr, dejaría de medir lo que producción ejecuta.

---

## Estructura

```
app/                  EL PRODUCTO (capa de decisión) + el ejecutor del banco
  config.py           validación de entorno, settings congelados, huella de decodificación
  llm.py              HTTP directo a Azure OpenAI, cache direccionado por contenido
  features.py         el vector φ; separación COMPUTABLE vs DERIVADO
  feasibility.py      la poda aritmética, antes de gastar un token
  beliefs.py          Belief/Provenance/BeliefBase + gobernanza determinista + calibración
  rules.py            el conjunto de reglas COMO DATO, y los sensores que pueblan una base
  assurance.py        el dial de garantía por request, y qué admite cada nivel
  router.py           partición → sonda → deferral, y el artefacto EXPLAIN
  policy.py           θ: versionada, firmada, legible. Plasticidad Hebbiana.
  consolidation.py    episodios → candidata, con la guarda de promoción
  rec.py              diagnóstico contrafactual: qué creencia mínima habría cambiado el plan
  certify.py          certificación de cláusulas, con el mundo final de un solo uso
  probe.py            la sonda: convierte una opinión en una observación
  tools.py            la superficie de herramientas y sus cortacircuitos
  retrieval.py        los brazos de recuperación (léxico, semántico, híbrido, HyDE)
  ingest.py           ingesta y su contabilidad, separada del gasto del paradigma
  grading.py          F1 de conjuntos, determinista
  metrics.py          π/α/β/G/L, β_max, brecha de oráculo, riesgo-cobertura, cascada
  runner.py           ejecutor del producto cruzado, guardas de mezcla y reporte
  serve.py            superficie HTTP con eventos tipados (la que consume `ui/`)
  paradigms/          las estructuras de control ejecutables (ver su README)

corpus/               generación y verificación del gold
  generate.py         construcción determinista desde seed
  verify.py           re-derivación INDEPENDIENTE de cada oráculo — es un gate obligatorio
  gold_h1/            el corpus de la campaña homogénea (78 tareas)

bench/                el banco: nada de acá es producto
  runs/               las corridas
  analysis/           los análisis reproducibles
  audits/             barridos de costo cero (código declarado y no leído, guardas inertes)
  _sanity.py          cotas sobre números derivados; LEVANTA, no avisa al lado

tests/
  test_science.py         valida la capa de medición contra respuestas conocidas
  test_consolidation.py   valida el aprendizaje y la guarda de promoción

historico/            snapshots fechados: valían el día que se escribieron
```

---

## El catálogo hoy

Son **15 registrados**, **12 que corren la campaña** y **8 activos**. El plantel no se
escribe a mano: sale de `campaign_roster()`, que lo deriva del catálogo y exige
**nombrar** cada excepción. Los que quedan afuera están afuera por
decisión escrita, no por olvido:

| fuera del ruteo | por qué |
|---|---|
| `cot` | **la ingeniería de prompts no es un patrón.** Dominado por `direct` en toda celda medida: misma utilidad, nunca más barato. Se conserva sólo como control nulo — es la evidencia de que el andamiaje por prompt no compra nada |
| `plan_execute` | retirado por dominado (2026-08-29) |
| `map_reduce` | **retirado 2026-08-29 por decisión del autor**: su nicho está vacío. Donde el material entra lo domina `direct`; donde no entra, la aritmética lo poda (180 filas de 270). Gana 1 celda de 33 |
| `pointer_chase` | **P14a falsificado** — nunca tocó una unidad relevante. Sus frenos (P14b) sí se confirmaron, y el mecanismo sobrevive a la muerte del patrón |

Y uno en **`standby`**, que es distinto de retirado: `graph_traverse` (falsificado en `P10a`,
con dos condiciones de revival escritas en el ejecutable — `gold_h1` ya cumple una).

**El dato histórico de todos ellos se replaya igual.** Un brazo que no se corre sigue en el
`REGISTRY`: las filas ya pagadas hay que poder leerlas, y borrar la función volvería
irreproducible el registro que la midió.

Los patrones se distinguen por **estructura de control de flujo**, jamás por fraseo. Lo que
cambia lo que el modelo recibe sin cambiar quién decide la próxima acción es un **factor**,
no un patrón — la prueba está en `PATRON_O_FACTOR.es.md`.

El estado de cada uno: [`app/paradigms/README.es.md`](app/paradigms/README.es.md).

---

## Cómo se corre

Desde `lab/`. El intérprete es Python 3.14 (`py`).

```powershell
py -m pip install -e .          # los pines reales están en pyproject.toml
copy .env.example .env          # y después completar las claves

# 1. Validar la capa de medición. No hace falta API key. Tiene que pasar PRIMERO.
py tests\test_science.py
py tests\test_consolidation.py

# 2. Construir y verificar el corpus. La verificación es un gate, no un chequeo.
py corpus\generate.py --seed 101 --people 60 --per-cell 3 --widths 4,16,48 `
   --unit-tokens 8000 --hard --honest-detectors --out corpus\gold_h1
py corpus\verify.py --corpus corpus\gold_h1

# 3. Estimar el gasto ANTES de gastarlo.
py bench\_estimate.py

# 4. La corrida LIGHT: ejercita la matriz entera sobre lo más barato que existe.
#    No mide nada — prueba que la matriz corre, y que cada factor llega al modelo.
py bench\runs\_run_homogenea_light.py

# 5. Recién ahí, la campaña.
```

**O todo de una, que es lo que conviene:**

```powershell
py bench\_listo.py
```

Corre las **ocho condiciones** —los dos tests, la verificación del corpus, las tres
auditorías, la estimación y la corrida light— y **falla si alguna no se cumple**. El
protocolo estaba repartido en cinco comandos y tres documentos, y «me acordé de correr
todo» no es una garantía: es una intención. Lo barato va primero, así una falla barata no
obliga a haber pagado la cara.

**El paso 4 no es opcional.** La campaña completa son decenas de millones de tokens y
horas de reloj; un paradigma que explota o un factor que no llega al modelo se descubriría
a las horas y con los tokens ya gastados. La corrida light lo encuentra en minutos.

Las corridas **resumen**: los resultados se appendean a `results/<corpus>_rows.jsonl` y los
pares `(tarea, paradigma)` ya hechos se saltean. El cache del LLM hace que una segunda
pasada sea gratis e idéntica.

### Las guardas que impiden promediar dos experimentos

Un archivo de resultados es una condición experimental, no una bolsa de filas. `load_rows`
**levanta** —no avisa— cuando un archivo mezcla:

| se mezcla | por qué importa |
|---|---|
| decodificaciones | promediar entre modelos no mide un paradigma: mide el modelo |
| brazos de recuperación | la recuperación es un factor cruzado, no una constante |
| analizadores léxicos | el tokenizador decide QUÉ encuentra BM25, y no deja rastro en ningún otro campo |
| vocabularios de región | una etiqueta cuyo significado lo fija el vocabulario que la produjo |

La tercera es la más silenciosa: el brazo está en el nombre del archivo, el modelo en la
huella, el vocabulario en su campo — el tokenizador no dejaba rastro en ninguno.

---

## Reglas de trabajo que están en el código, no en la buena voluntad

- **Un 429 no es parte de la evaluación.** Los fallos de infraestructura quedan como
  `infra_error` y afuera de toda estadística.
- **Estimar tokens ANTES de correr**, y decidir sobre la brecha **neta**.
- **Piso de ruido POR CELDA**, `repeat ≥ 3`, y predicciones falsables registradas con fecha
  antes de ver el número.
- **Un número derivado se verifica en la granularidad donde vive, no en el agregado.** Un
  promedio puede ser posible mientras cada uno de sus términos es imposible: agregar es
  exactamente la operación que borra la contradicción.
- **Un defecto de construcción no es un hallazgo.** Un bug, un lock roto, un límite de
  tasa: se arreglan y se registran como trabajo. No entran a `LECCIONES.es.md` ni al paper,
  y no son premisa de ninguna conclusión.

---

## Dónde está cada cosa

El índice completo de los documentos —cuál abrir para qué pregunta— está en
[`CLAUDE.md`](CLAUDE.md) §«Qué documento es cada cosa».

Los tres que más se usan:

| documento | responde |
|---|---|
| [`PENDIENTES.es.md`](PENDIENTES.es.md) | qué falta, y qué corrida lo cierra |
| [`DISENO.es.md`](DISENO.es.md) | el ejecutable actual y sus deudas comprobadas |
| [`LECCIONES.es.md`](LECCIONES.es.md) | los errores propios, con el número que los delató |

Y la cronología medida:
[`historico/BITACORA-PREDICCIONES.es.md`](historico/BITACORA-PREDICCIONES.es.md) —
predicciones registradas antes de correr, con sus veredictos.
