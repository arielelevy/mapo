# `bench/` — el banco de medición

**Esto no es el producto.** El producto es la capa de decisión en `app/`; esto es lo que la
mide. La regla que evita que se vuelvan a mezclar: **el banco importa al producto, y el
producto no sabe que el banco existe.** Estaba escrita en `CLAUDE.md` y no se veía en el
árbol — 72 scripts sueltos en la raíz de `lab/`, al lado de `app/`.

| | | |
|---|---:|---|
| `analysis/` | 35 | interrogan el registro ya pagado. **Cero llamadas al modelo** |
| `runs/` | 27 | gastan cuota. Cada uno declara su estimación antes de correr |
| `audits/` | 10 | barridos sobre el código y sobre el cruce código × corpus |
| `oneoff/` | 13 | migraciones y arreglos que ya corrieron. Arqueología, no herramientas |
| `_sanity.py` | | cotas que un número derivado tiene que pasar **antes** de reportarse |
| `_estimate.py` | | qué va a costar una corrida, **contado del corpus**. Se corre solo: `py bench/_estimate.py` |
| `_listo.py` | | **las ocho condiciones para lanzar, de una.** Falla si alguna no se cumple |

> **Los conteos se cuentan.** Decían 27/22/9 y eran 35/27/10 — se habían escrito a mano.
> Se recuentan con `ls bench/<carpeta>/*.py | grep -v __init__ | wc -l`.

---

## Cómo se corren

**Desde `lab/`, siempre:**

```
cd lab
py bench/analysis/_analyze_money.py
py bench/audits/_audit_inerte.py
```

Las rutas de datos (`results/nano`, `corpus/…`) son **relativas al CWD** y quedaron así a
propósito. Cada script lleva un prólogo de tres líneas que resuelve los **imports** —eso es
lo que se rompe al salir de la raíz— y nada más. Reescribir setenta archivos de rutas de
datos arriesgaba romper en silencio a cambio de nada hoy, y el silencio es justo lo que este
repo no acepta.

---

## Los tres barridos, que buscan la misma falla por caminos distintos

Aparecen juntos porque cada vez que volví a cometer la falla, el barrido anterior **no
podía verla**. Son tres capas: el nombre, el dato, y el camino.

**`_audit_declarado.py` — léxico.** Nombres que se definen y cuyo único uso es su propia
serialización o un `print`. Encontró `REGION_VOCABULARY`, que llevaba escrito al lado *«un θ
ajustado bajo un vocabulario nunca debe consumir regiones de otro»* y **nada lo estampaba**.

**`_audit_inerte.py` — de ejecución.** Guardas cuyo disparador **no lo satisface ningún
corpus del repo**. El barrido léxico no las ve porque el nombre **sí** se lee y **sí**
gobierna: lo que falta es el *dato* que hace verdadera la condición, y eso es una propiedad
del cruce entre el código y los corpus.

> Encontró cuatro de siete disparadores que **nunca dispararon** — uno de ellos una
> precondición que yo había cerrado como hecha el mismo día.

**`_diagnose_managed.py` — de camino** (2026-08-29). El tercero de la familia, y contesta
lo que los otros dos no pueden: *¿se ejecutó el código, o solamente no dio error?* Un
factor que no llega al modelo y uno que llega y decide no hacer nada producen filas
**idénticas**, y la diferencia importa porque una bloquea la campaña y la otra no. Envuelve
la función del factor y cuenta llamadas y efectos por separado. Veredicto medido sobre
`managed`: **61 llamadas, 0 demociones** — el camino se recorre, la condición no se cumple,
`w4` no tiene historia que compactar.

**Y una falla que estos tres comparten y hay que vigilar: un auditor desactualizado es peor
que no tenerlo, porque informa con la autoridad de una medida.** `_audit_catalog.py`
imprimió *«DOMINADOS: ninguno»* sobre **cero tareas** —el registro se había archivado y un
`except FileNotFoundError: continue` se lo tragó—, y «ninguno dominado» es justo el
resultado tranquilizador que uno espera leer. Ahora levanta.

Ninguna de las tres listas **es un veredicto**. Cada caso se decide leyendo: un campo que sólo
se serializa puede estar bien, y una guarda para un corpus que todavía no existe es
legítima. Lo que no puede pasar es que sea una **sorpresa**.

---

## Antes de gastar un token

**Una sola cosa:**

```
py bench/_listo.py
```

Las ocho condiciones del protocolo, y **falla si alguna no se cumple**. Estaban repartidas
en cinco comandos y tres documentos; acordarse de correrlas no es una garantía. Lo que no
gasta va primero, por la misma razón que la poda aritmética corre antes de inferir.

Las piezas, si hace falta correr una sola:

```
py tests/test_science.py           # completo
py tests/test_consolidation.py     # completo
py corpus/verify.py --corpus corpus/<nombre>
py bench/audits/_audit_documentos.py    # los .md vivos contra el catalogo
py bench/audits/_audit_afirmaciones.py  # lo afirmado, re-derivado del registro
```

Y **la corrida light, que no es opcional**:

```
py bench/runs/_run_homogenea_light.py
```

Ejercita la matriz entera —el plantel de `campaign_roster()` × 7 factores— sobre las 4
tareas más baratas. No
mide nada: prueba que la matriz **corre**, y desde el 2026-08-29 prueba algo más difícil,
que **cada factor llega al modelo**. Un factor desconectado no da error: da exactamente la
base, y eso ya pasó cuatro veces. Ahora cada factor reporta cuántas filas movió respecto de
la base, y cero es un bloqueante. Se corre **de a una**: dos procesos a la vez appendean al
mismo `.jsonl` y el resumen sale con más filas que celdas.

Más: predicciones falsables **registradas con fecha en
`historico/BITACORA-PREDICCIONES.es.md` antes de correr**, `repeat >= 3`, piso de ruido
**por celda**, decisiones sobre la brecha **neta**.

**Y estimar contra el corpus, nunca contra el registro.** Un archivo de resultados **no
declara si está completo**: estimé una corrida en 362k tokens leyendo un `.jsonl` de 90
filas que cubría 6 de 32 tareas, y gastó **12,2 millones** — 34× de error. La aritmética
correcta es `len(tasks.json) × brazos × repeat`, cuesta lo mismo, y no se puede equivocar
así.

---

## Los ejes que este banco cubre, y los que no (relevado 2026-08-30)

Se contrastó contra lo que la literatura de agentes 2024-2026 exige. La tabla está acá y no
en un documento aparte porque **un checklist que vive lejos del código no se corre**.

| eje | estado | dónde |
|---|---|---|
| grading sin juez LLM | **cubierto** — no hay juez, y por eso el sesgo de posición/verbosidad no existe | `app/verify.py` |
| sin pases gratis | **cubierto** — `''`, `'   '` y una cortesía dan `0,0`. Es el fallo que τ-bench tiene | `verify.score` |
| validez de tarea | **cubierto** — el portón **declara** las irresolubles en vez de puntuarlas | `app/feasibility.py` |
| contaminación | **cubierto** — corpus generado, filtración estructuralmente imposible. Y se declara la contaminación **del analista** | `corpus/`, `CONTAMINADAS` |
| costo como eje | **cubierto** — prompt/completion separados, aranceles con fuente y fecha, acantilado de contexto largo, Pareto | `config/tariffs.json` |
| barras de error | **cubierto**, y de más: nulos por permutación **con corrección por selección** | `_predictores.py` |
| atribución de falla | **cubierto** — embudo ver/usar, taxonomía de modos, `ToolFailure` tipado | `_eda_react.py`, `_c3_cadena.py` |
| **`pass^k`** | **cubierto desde 2026-08-30** — y va en el marcador | `bench/fiabilidad.py` |
| **adecuación del oráculo** | **cubierto desde 2026-08-30** | `audits/_audit_oraculo.py` |
| **holdout** | **corriendo** — no existía como medición válida; todo lo publicado hasta hoy es en muestra | `--corpus gold_holdout` |
| modelo vs harness | **falta** — tres modelos declarados, `gold_h1` es esencialmente `luna` | |
| eje de seguridad | **falta** — el gate de irreversibilidad está; las tareas adversariales no | |
| latencia en la decisión | **falta** — medida en el 100% de las filas, **ninguna decisión la mira** | `first_ttft_ms` |

> **El que más duele es el holdout**, porque es el criterio de éxito escrito del producto y
> su única corrida estaba en el archivo pre-K6, sin estampar y no replayable. Por eso
> `_run_homogenea.py` toma `--corpus`: un holdout medido con otro harness no mide
> generalización, mide dos harnesses.

## Dónde vive cada cosa

```
lab/
  app/        el PRODUCTO — capa de decisión y paradigmas
  bench/      esto
  corpus/     generación y verificación del mundo
  tests/      test_science.py, test_consolidation.py
  historico/  snapshots fechados: valían el día que se escribieron
  results/    MEDICIÓN — evidencia de lo que se corrió        (fuera de git)
  state/      ESTADO — lo que el sistema aprendió             (fuera de git)
  cache/      completions content-addressed                   (fuera de git)
```

`results/` y `state/` son **dos árboles y no se mezclan**: un `rglob("*.jsonl")` sobre
resultados levantaba el ledger de creencias como si fueran filas medidas. La distinción es
de **vida útil** — una medición sin su ledger sigue siendo una medición; el ledger se
reconstruye entero volviendo a consolidar. Los tres están fuera de git por tamaño, no por
importancia: la integridad del ledger la sostiene su **cadena de hashes**
(`store.verify_chain`), no el control de versiones.
