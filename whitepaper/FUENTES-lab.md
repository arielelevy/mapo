# paper — el whitepaper de MAPO

Empieza de cero (decisión del autor, 2026-08-27): sin ninguna referencia a marcas
o productos anteriores. Se escribe SEGUNDO, desde el registro medido del engine.

Fuentes canónicas, todas en `../engine/`:

- `README.md` §"The deliverable" — el diseño del producto que el paper valida.
- `README.md` §"Registered predictions" (P1–P14) y §"Findings so far" — las
  predicciones falsables con fecha y sus veredictos. La regla: nada entra al
  paper sin implementación que lo corra.
- `notes/2026-08-26-scouting-patrones.md` — literatura leída (DocTrace, PRISM,
  BAGEN, ContextBudget), falsificaciones de candidatos, veredicto P13
  (estructura vs juicio en el segundo modelo) y el titular de ruteo
  (cobertura → nano; acoplamiento profundo → prohibido el downgrade).
- `results/` (no versionado) — filas crudas por (task, paradigm, trial),
  grillas gpt-5-chat (congelada) y gpt-5.4-nano.
- `_analyze_p13.py` — el análisis reproducible de la comparación entre modelos.

Pendiente: estructura del paper (a definir por el autor).
