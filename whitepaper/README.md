# v2 — activa (agosto 2026)

## Orden de lectura

1. **`GATE.md`** — antes que nada. Ocho criterios binarios y el veredicto actual. Dice
   qué falta y, sobre todo, qué **no** se puede afirmar todavía.
2. **`paper-en.md`** — el paper. Canónico, en inglés, destino arXiv cs.LG.
   `paper-es.md` es la traducción para leer.
3. **`PATTERNS.md`** — el catálogo. Es el producto separable: sirve sin el paper.
4. **`ANALYSIS.md`** — dónde falla cada paradigma y por qué, con la traza.
5. **`PLAN.md`** — sólo si interesa por qué la tesis cambió dos veces.

## Estado

**El gate no tiene bloqueantes** desde el 2026-08-23 (G1 cerrado; §8ter de `GATE.md`).
**G2 cerrado el 2026-08-26** (§8quater): Select-then-Solve y SCL leídos completos, 6/6
números verificados, cesiones correctas, los dos claims pendientes verificados libres
*como conjunción*, y la abstención en ruteo de paradigmas re-verificada libre — con la
ventana cerrándose (2608.00106 nombra el confidence gate como trabajo futuro). Queda **un
solo condicional: G3** (la medición fuera-de-ventana).

Todo número empírico es **n=1 por celda**, sobre un corpus sintético, con un modelo. La
varianza entre réplicas medida sobre la topología más elaborada llegó a 3,93× en costo,
así que las magnitudes son indicativas. Los **mecanismos** son más firmes que las
magnitudes, porque descansan en trazas de uso de herramientas y no en tamaños de efecto.

**La amenaza de validez más grande está en curso de cierre** (2026-08-26): predicciones
P1-P5 registradas antes de correr (README del harness), barrido de factibilidad a costo
cero completado sobre los 4 corpus (`results/feasibility_sweep.json` en el harness), y el
estudio pagado gold_v2 ↔ gold_deep (emparejado, `repeat=3`, piso de ruido por celda) en
ejecución.

## Figuras

Las 6 de `diagrams/` están sólo en inglés (`_en`). Las dos de resultados llevan una banda
roja **PRELIMINARY** con la n adentro del SVG, para que la advertencia no se pueda separar
de la figura al copiarla.
