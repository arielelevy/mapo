# Pedido de opinión y aval — plantilla

Tres huecos por destinatario: `{NOMBRE}`, `{SU LÍNEA}` y `{SECCIÓN}`. El tercero es el que
importa: **pedir que validen UNA sección**, no el paper, baja el costo de contestar de una hora
a diez minutos.

## Asunto (elegir uno)

- `Your opinion on a measured result about paradigm selection in LLM agents`
- `A systems-side result that touches {SU LÍNEA} — asking your read`
- `Deterministic control planes over LLM sensors: your opinion, and an arXiv endorsement`

## Cuerpo

> Dear {NOMBRE},
>
> I am writing to ask your opinion on a result I believe speaks directly to {SU LÍNEA}, and
> which I think the community can build on.
>
> The work began inside a production project on **forensic document analysis** — the kind of
> system that answers what account is held by whom, who reports to whom N levels up, whether a
> transfer was ever recorded. Building it, one problem kept recurring: a harness over an LLM
> inherits the probabilistic character of the component it wraps, and so do the guards built to
> contain it. A hallucination checker that is itself a model call has the same property it was
> meant to remove. That pushed the design toward putting the control plane in code and leaving
> the model as a typed sensor, and then toward measuring whether that actually buys anything.
>
> Three things came out of the measurements, on 78 tasks × 12 paradigms × 3 replicates, 121M
> tokens, no LLM judge:
>
> - **Choosing the paradigm per task does not pay on this corpus, and there is a mechanism.**
>   The task×paradigm interaction is large — 48% of explained variance, signal-to-noise 5.30 —
>   and the net prize is −0.008 in sample and −0.034 held-out. `var(γ)` is large because the
>   weak paradigms are weak in *different places*; restricted to the arms that would actually
>   compete, it vanishes.
> - **Agreement between paradigms is a verifier with no oracle and no judge.** Precision 1.000
>   from four matches, over 180 of 180 cells, and it replicates on a second model family
>   against a criterion registered before the run.
> - **17–34% of cells return a different answer at temperature zero** with the same prompt and
>   seed — not from misreading, but because the harness consumed generated text as a control
>   signal, and one different choice at step one changes which document is read at step two.
>
> **What I would value from you.** If you have ten minutes, I would rather you look at
> **{SECCIÓN}** than at the whole paper — that is the part closest to your work and the one
> where an outside read would change what I publish. And if the result seems sound to you, I
> would be grateful if you would consider **endorsing the submission for cs.LG** (cs.AI
> cross-list).
>
> Both versions are attached: a 16-page conference-length paper, and the full 70-page record
> with the per-cell data. Scope, stated plainly: the design comes from production work, the
> measurements are on a synthetic corpus whose ground truth is exact and independently
> re-derived, and the limitations section says what that does and does not license. The
> architecture is inspired by MINERVA/HADD (Jaime & Errecalde, 2026), and §2 declares that debt
> piece by piece.
>
> Either way, thank you for reading this far. If the work is useful to you or to someone in
> your group, please use it — that is the point of putting it out.
>
> With appreciation,
>
> **Ariel Edgardo Levy**
> Principal Engineer — Systems Architecture & AI · 20+ years
> {LINK AL DOI DE ZENODO} · {LINK AL REPO SI SE ABRE}

## Qué sección pedirle a quién

| si su línea es | pedile que lea | porque |
|---|---|---|
| andamiajes estructurados, DSPy, optimización de programas con LLM | **§5.3** — el premio neto de rutear y su mecanismo | contradice el supuesto sobre el que se construyen los ruteadores |
| verificación, autoconsistencia, jueces LLM | **§5.4** — el consenso como verificador, con sus tres controles | es un verificador sin oráculo ni juez, replicado |
| reproducibilidad y evaluación de agentes | **§5.2** — `pass^k` y la varianza de trayectoria | es una corrección barata a cómo se reportan los bancos |
| razonamiento simbólico, creencias, procedencia | **§4.1** y **§3** — las definiciones y el retículo de procedencia | es el aparato formal, y es donde una lectura externa más rinde |
| gobernanza, cumplimiento, IA de alto riesgo | **§1.1** y **§6** — la instrucción contra la restricción, y las amenazas | es el argumento normativo y su alcance declarado |

## Notas prácticas

- **El aval de arXiv es por archivo.** El endorser tiene que haber publicado en **ese** archivo
  hace poco. Si alguien publica en `cs.CL` y no en `cs.LG`, no puede avalar aunque quiera —
  conviene revisar el archivo de cada destinatario antes de escribir.
- **Adjuntar los dos PDF, no ofrecerlos.** «Happy to share the manuscript» agrega un paso, y el
  que decide en diez minutos no pide un archivo.
- **Un asunto sin la palabra «endorsement» al principio** se lee como conversación y no como
  trámite. El pedido de aval va en el cuerpo, después del resultado.
- **Zenodo con DOI antes de la próxima ronda.** Nadie avala lo que todavía no puede leer sin
  pedirlo, y un DOI convierte el mail en «acá está el preprint» en vez de «te cuento que tengo
  uno».
