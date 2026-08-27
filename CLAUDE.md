# CLAUDE.md — mapo (raíz del monorepo)

Este repo es **MAPO**: capa de decisión determinística para agentes LLM. Dos
subproyectos, en orden de prioridad:

1. **`engine/`** — EL PRODUCTO. Instrucciones autoritativas en `engine/CLAUDE.md`
   (invariantes, fila de paradigmas, modelo de medición, protocolo antes de gastar
   un token). Todo trabajo de código/corridas/corpus pasa por ahí.
2. **`paper/`** — el whitepaper que valida el producto. Va SEGUNDO. Empieza DE CERO:
   sin ninguna referencia a marcas o productos anteriores. Nada entra al paper sin
   implementación que lo corra en `engine/`.

El whitepaper viejo (marca anterior) vive FUERA de este repo, en
`D:\Apps\chat\whitepaper` (repo git aparte); es insumo histórico ya cosechado
(`engine/notes/`), no se cita ni se copia acá.

Git: remote `origin` = github.com/arielelevy/mapo (PRIVADO), rama `main`.
Nunca push sin confirmación del autor. `.env`/`cache/`/`results/` viven bajo
`engine/` y están gitignoreados.
