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

- [x] **W-5** · **un título que producía una creencia falsa, corregido** (2026-08-29).

  `ANALYSIS.md` titulaba **«`reflection`: retirado»** y `GATE.md` repetía **«+0,250 →
  retirado»**, mientras el catálogo lo tiene **activo** — *«único mejor en 1 de 14: delgado,
  no dominado»* (`_audit_catalog.py`, 2026-08-28).

  **Los dos hechos eran ciertos y el título los confundía.** Lo que no sobrevivió al test de
  atribución fue **el efecto** —+0,250 salió íntegro de `c3-002-h3`, la celda que se da
  vuelta sola—, no el brazo. Retirar un efecto no atribuible y retirar un brazo dominado son
  criterios distintos, y sólo se cumplió el primero. Un número mal medido se puede chequear;
  un título se cree.

  Los dos archivos dicen ahora las dos cosas y por qué no se contradicen. `_audit_documentos.py`
  ya no las señala.

  > **Y lo encontró una guarda, no una lectura.** Vale anotarlo porque la guarda es nueva y
  > su primera corrida encontró algo que cuatro pasadas de lectura no habían visto.


- [ ] W-3 · integrar el hallazgo de nano (P13)

- [x] **F5** · **teoría nativa: los tres teoremas que estaban construidos entraron al paper**
  (2026-08-29). `PENDIENTES.es.md` lo describía como *pizarra*, y contado contra el
  ejecutable eso ya era falso: **T-3** (soundness del ensamblador, `test_science.py` §46),
  **T-4** (cota nativa del ratchet, §22) con su **precio medido**, y **T-5** (quién fija el
  dial, §47) estaban escritos, verificados con test y dos de ellos medidos. El paper los
  ignoraba — «soundness», «ratchet» y «assurance dial» aparecían **cero veces** en
  `paper-en.md`.

  Entraron como **§5.3, §5.4 y §5.5** en los dos archivos, en la misma posición. Son
  **resultados estructurales**: no dependen del corpus ni del modelo, así que son lo único
  del paper que no queda condicionado a una corrida. La sección empírica está condicionada;
  ésta no.

  Lo que sigue abierto de la familia es **T-1** (semántica del contrato): dos de sus tres
  clases están en `app/contracts.py`, y es lo que bloquea a `F6`.

- [x] **W-6** · **§6.5: el banco leído como procedimiento de ajuste** (2026-08-29). Tesis del
  autor, y encaja con lo que el ejecutable hace: el modelo está congelado, lo que se ajusta
  es la capa de decisión, y se ajusta sobre el registro del producto cruzado — cero llamadas
  nuevas. El paper describía la maquinaria (§6.3) sin nombrar lo que era.

  Entró con el **inventario exacto** de qué se ajusta y en qué estado —incluidas las dos
  filas donde el aprendizaje existe como medición y **no** como mecanismo: las asociaciones
  de orden (`p = 0,0078`, ningún consumidor las lee) y el reparto del handoff (fijo)— y con
  su **refutación medida**: `P15`, −0,087 sobre un mundo nuevo, causada por un vocabulario de
  región sin eje de horizonte. De ahí sale la condición que el paper ahora enuncia y que
  antes no tenía: **la representatividad hay que declararla sobre los ejes que el vocabulario
  de región distingue**, y eso se chequea sobre un corpus antes de correrlo.

- [ ] F6 · contratos contra baselines directos

- [ ] F7 · validez externa

- [ ] W-4 · endorser de arXiv, o Zenodo con DOI
