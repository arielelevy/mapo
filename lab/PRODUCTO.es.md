# Pendientes de PRODUCTO — MAPO

> **Esto NO es el banco.** Acá vive lo que hay que **construir** para que MAPO sea un
> producto corriendo, no lo que hay que **medir** para saber si funciona. La medición vive
> en `PENDIENTES.es.md` y el argumento en `PAPER.es.md`.
>
> **Orden fijado por el autor (2026-08-29): el lab va primero.** Terminado, probado,
> afinado, verificado y testeado. Después el paper, con un par de iteraciones de ida y
> vuelta entre paper y lab. **El producto va último, cuando todo lo demás esté perfecto.**
> Nada de este archivo se empieza antes de eso — y tenerlo separado es lo que impide que se
> cuele por el costado.
>
> La arquitectura física ya está **decidida y escrita** en `ARQUITECTURA.es.md`: on-prem
> con Docker, Weaviate con `fusionType: rankedFusion` clavado y no heredado del default,
> Postgres como ledger epistémico y única autoridad sobre qué índice está vivo, FastAPI con
> SSE resumible, Docling con un sensor de OCR barato adelante, y el NER en la etapa de
> ingesta. **Ninguna pieza está ejecutada ni medida** — eso es exactamente `G-2`, y es lo
> que separa una arquitectura de un plan.
>
> **La regla que no se negocia al portar**: el banco importa al producto, el producto no
> sabe que el banco existe. Y la capa de decisión **nunca** depende de un orquestador —
> los paradigmas son funciones async planas, que es lo que hace que el banco mida
> exactamente lo que producción ejecuta.

---

## Lo que hay que construir

- [ ] **A-1** · arrancar el producto — *el motor nuevo no existe*

- [ ] **A-3** · separar producto de banco ANTES de portar

- [ ] **A-2** · decidir qué se porta de `legacy/`

- [ ] **A-2b** · **cosecha de `legacy/`, con la mitad ya resuelta.** `context_guard` **sí**
  (el mecanismo, no sus constantes). El **prompt de suficiencia NO**: es andamiaje por
  prompt, y el banco ya midió que eso no compra nada.
  **`hyde` sale de esta lista: ya está portado al lab y medido** (`H-1`, `H-2`, P26). La
  duda que este renglón registraba —«medirlo acá puede no significar nada»— **se contestó
  midiendo**: `rewoo` gana **+0,0421** global (2,16 ee) y **+0,0845** donde el enunciado y
  el documento se dicen distinto (2,03 ee); `react` no mueve la utilidad pero gasta **1.281
  tokens menos**. Y el mecanismo no es el que se había predicho: `rewoo` gana leyendo las
  MISMAS unidades y haciendo las MISMAS búsquedas, así que lo que HyDE mejora es el
  contexto de búsqueda, no el conjunto recuperado. Lo que queda de `A-2b` es `context_guard`

- [ ] **E-3** · **el stream todavía no sale por HTTP.** `_answer_stream` emite y `Event.as_sse()` serializa, pero el endpoint sigue devolviendo el bloque. Falta el SSE resumible que propone `ARQUITECTURA.es.md` — y con él la guarda que ya está escrita ahí: **A3 buffea la respuesta hasta verificar citas**, así que `token` no puede salir antes de que el contrato lo permita

- [ ] **G-2** · `ARQUITECTURA.es.md` propone la pila entera y **ninguna pieza está
  ejecutada ni medida**. Las seis, que hasta el 2026-08-29 vivían sueltas en
  `PENDIENTES.es.md` contando el mismo trabajo dos veces:

  | pieza | qué decide, y qué NO se eligió |
  |---|---|
  | [ ] Docling + `pypdfium2` | extractor primario con procedencia **página + bbox**, y un sensor barato decidiendo OCR **antes** de la primera pasada. `pypdfium2` y no PyMuPDF, que es AGPL |
  | [ ] Postgres como ledger epistémico | hace **durables** las guardas que `runner.py`, `consolidation.py` y el `FinalLedger` de `certify.py` ya imponen en proceso. **No cierra deudas nuevas** |
  | [ ] Weaviate + `live_pointer` | `hybrid` con `fusionType: rankedFusion` **clavado**, no heredado del default; una colección por versión de índice, y `live_pointer` en Postgres como **único flip atómico** de promoción |
  | [ ] work table → DBOS | work table en Postgres ahora, DBOS después. **Temporal todavía NO** — entra sólo si dispara uno de los gatillos escritos en §2.3. **LangGraph descartado, no pospuesto** |
  | [ ] FastAPI con SSE resumible | eventos tipados, y **A3 buffea la respuesta hasta verificar citas**. Es la otra mitad de `E-3` |
  | [ ] on-prem / Docker | restricción del autor: on-prem, single-tenant |

  Lo que **no cambia** al portar: la capa de decisión nunca depende de un orquestador, y
  los paradigmas siguen siendo funciones async planas.
