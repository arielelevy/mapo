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
  `paper-es.md` espejo; **toda edición va a los dos, en la misma posición**). `GATE.md`
  manda sobre qué se puede afirmar. Nada entra al paper sin implementación que lo corra en
  `lab/`. [`whitepaper/artefactos/`](whitepaper/artefactos/README.md) versiona los
  documentos visuales.
- **[`legacy/`](legacy/README.md)** — una capa de ejecución anterior, **CONGELADA**. No es
  el producto y no se evoluciona: se conserva como referencia de las partes que un
  despliegue real necesita y el banco nunca tuvo que modelar — búsqueda sobre índice real,
  scoping por permisos, citas verificadas contra ese índice, streaming a un cliente. Se
  revisó y reparó el 2026-08-27 (ver su README) para que lo que vale leer valga leerse.
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

## Dónde está el registro (2026-08-27)

**P15 — la afirmación del producto, refutada, y el mecanismo ES el hallazgo.** Sobre un
mundo que θ nunca había visto (seed 47, 390 celdas, cero errores de infraestructura), el
ruteo por request perdió contra el mejor paradigma fijo por **−0,087**, más allá del piso
de ruido — mientras reproducía cada decisión 26/26 desde su base de creencias registrada.

Mecanismo verificado: **el vocabulario de región no tiene eje de horizonte**, así que las
tareas que castigan una elección fija eran indistinguibles de las que la premian, y θ ruteó
contra su propio veredicto registrado (P6b) porque ninguna etiqueta le dijo nunca que
estaba en ese caso.

Titular honesto: **seleccionar sin sensar pierde contra un default fijo fuerte.**

Chequeo de sensibilidad: reparar la validez del aprendizaje (agregación por episodio,
holdout limpio) deja el número idéntico — la refutación no es un artefacto.

**La dirección que sigue: REC (Reparación Epistémica Contrafactual).** Una decisión
registrada más una traza determinista pueden decir qué creencia mínima, a qué fuerza de
evidencia, habría cambiado el plan — y qué observación acotada podría resolverla.
Implementado hasta acá: el solucionador contrafactual (replay puro; las hipótesis nunca
tocan el registro fáctico), cláusulas de adquisición que son borrador hasta certificarse, y
el ciclo de certificación — tres mundos que no se solapan, un **mundo final de un solo uso**
impuesto por un ledger, e instalación fail-closed sobre el bundle firmado de la política.
Diseño: `lab/PATRON_REC.es.md`. Estado vivo: `whitepaper/artefactos/`.

---

## El orden del trabajo

**El producto se construye desde lo que el banco prueba, no al revés.** `lab/` sigue
midiendo patrones y validándolos; el motor del producto arranca cuando ese registro esté
lo bastante maduro como para construir desde ahí. Hasta entonces no se porta nada.

La arquitectura física, cuando arranque, ya está decidida y es reversible:
`lab/ARQUITECTURA.es.md`.
