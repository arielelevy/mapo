# Pendientes del PAPER — MAPO

> **El paper documenta y valida el producto, no al revés.** Vive en `../whitepaper/`
> (`paper-en.md` canónico, `paper-es.md` espejo — **toda edición va a los DOS, en la misma
> posición del archivo**). `GATE.md` manda sobre qué se puede afirmar; `PLAN.md` es
> arqueología, no tesis.
>
> **Va segundo**, después de que el lab esté terminado y verificado (orden del autor,
> 2026-08-29), y con un par de iteraciones de ida y vuelta: lo que el paper no pueda
> sostener vuelve al lab como medición, no como redacción.
>
> **Nada entra sin implementación que lo corra**, y nada se afirma sin medida, cita o
> rótulo de hipótesis (G3). Las novedades se enuncian como CONJUNCIÓN, nunca como partes
> (GATE §8quater): lo que es nuevo es que las piezas estén juntas, no cada pieza.
>
> **Dos archivos que dicen lo mismo en distinto lugar empiezan a decir cosas distintas.**
> Ya pasó una vez.

---

## Lo que falta para publicar

- [ ] **W-5** · **el paper dice que `reflection` está retirado y el ejecutable lo tiene
  activo** (encontrado el 2026-08-29 por `bench/audits/_audit_documentos.py`).

  `ANALYSIS.md:310` titula **«`reflection`: retirado»** y `GATE.md:237` repite
  **«`reflection` +0,250 → retirado»**. El cuerpo aclara qué se retiró: *«+0,250 salió
  íntegro de `c3-002-h3`, y esa celda cambia de valor entre dos corridas de la misma
  superficie. No es un efecto.»*

  **Lo retirado es el EFECTO, no el brazo.** Y el título dice lo otro. El catálogo, medido
  cinco días después (`_audit_catalog.py`, 2026-08-28), lo tiene **activo**: *«único mejor
  en 1 de 14: delgado, no dominado»*.

  Un lector del paper concluye que el brazo salió del catálogo, y no salió. No es un número
  mal medido —los dos hechos son ciertos— es un **título que produce una creencia falsa**,
  que es peor: el número se puede chequear y el título se cree.

  Va a los **dos** archivos, en la misma posición.

  > **Y lo encontró una guarda, no una lectura.** Vale anotarlo porque la guarda es nueva y
  > su primera corrida encontró algo que cuatro pasadas de lectura no habían visto.


- [ ] W-3 · integrar el hallazgo de nano (P13)

- [ ] F5 · teoría nativa

- [ ] F6 · contratos contra baselines directos

- [ ] F7 · validez externa

- [ ] W-4 · endorser de arXiv, o Zenodo con DOI
