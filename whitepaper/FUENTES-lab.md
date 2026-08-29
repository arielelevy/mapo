# De dónde sale cada número del paper

MAPO empieza de cero (decisión del autor, 2026-08-27): sin ninguna referencia a marcas o
productos anteriores. El paper se escribe **segundo**, desde el registro medido del lab.

> **Corregido el 2026-08-29.** Esta página decía que las fuentes canónicas estaban «todas
> en `../legacy/`». Es falso y era una herencia: `legacy/` está **congelado** y no es el
> producto ni produce números. Todo lo que el paper cita sale de `../lab/`.

## Fuentes canónicas, todas en `../lab/`

| fuente | qué aporta |
|---|---|
| `README.md` | el diseño del producto que el paper valida: cómo se decide un request, qué garantiza y qué no |
| `historico/BITACORA-PREDICCIONES.es.md` | **las predicciones falsables con fecha, registradas antes de correr, y sus veredictos.** Estuvo hasta el 2026-08-29 adentro de `README.md`; se mudó porque un README describe el estado y esto es una cronología. Sigue siendo canónico y no se edita retroactivamente |
| `PENDIENTES.es.md` | qué falta, y qué corrida lo cierra. Lo que está acá **no** se puede afirmar |
| `LECCIONES.es.md` | los errores propios con el número que los delató — varias amenazas de validez del paper salen de acá |
| `notes/2026-08-26-scouting-patrones.md` | literatura leída (DocTrace, PRISM, BAGEN, ContextBudget), falsificaciones de candidatos, veredicto P13 (estructura vs juicio en el segundo modelo) y el titular de ruteo: cobertura → nano, acoplamiento profundo → prohibido el downgrade |
| `bench/analysis/` | los análisis reproducibles. `_analyze_p13.py` es el de la comparación entre modelos |
| `results/` (no versionado) | filas crudas por (tarea, paradigma, trial). Grilla `gpt-5-chat` **congelada**, y `gpt-5.4-nano` en adelante |

## La regla que manda sobre todo esto

**Nada entra al paper sin implementación que lo corra en `lab/`.** Si algo está hoy en el
paper como «declarado, no medido», es deuda: se implementa o se saca. Y `GATE.md` manda
sobre qué se puede afirmar — las novedades se enuncian como CONJUNCIÓN, nunca por partes.

## Orden de trabajo

El autor lo fijó: **lab primero** (terminado, probado, verificado), **después** el paper
con iteraciones de ida y vuelta, y el producto al final. Lo que falta del paper vive en
`../lab/PAPER.es.md`, separado a propósito de `PENDIENTES.es.md` para que no se cuele.
