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

## Dónde está el registro (2026-08-29)

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
py tests\test_science.py            # 52 chequeos, 524 aserciones
py tests\test_consolidation.py
py corpus\verify.py --corpus corpus\<nombre>
py bench\_listo.py                  # las ocho condiciones de lanzamiento
```

Y tres reglas que no son de estilo: **predicciones falsables registradas con fecha antes de
correr**, **`repeat ≥ 3` con piso de ruido por celda**, y **estimar contra el corpus, nunca
contra el registro** — estimar desde una corrida parcial costó una vez un error de 34×.
