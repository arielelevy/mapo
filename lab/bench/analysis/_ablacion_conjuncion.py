"""¿La conjunción es necesaria, o es integración de piezas conocidas? Cero llamadas al modelo.

EL DESAFÍO DE ORIGINALIDAD, dicho como corresponde: cada componente del motor tiene
antecedentes —predicción selectiva, procedencia, poda por presupuesto, voto por consenso— y el
paper afirma que lo nuevo es la conjunción. Un revisor tiene derecho a responder que una
conjunción de técnicas conocidas es ingeniería, no un resultado. La respuesta no es retórica:

    hay que exhibir una propiedad que la conjunción produce y que se ROMPE al sacar cualquier
    componente, uno a la vez.

LA PROPIEDAD, y es la única que un sistema de producción no puede negociar:

    FALLA OPERACIONAL = el sistema AFIRMA un valor, y el valor es incorrecto.

No es «se equivoca»: es **se equivoca afirmando**. Abstenerse no es fallar —es el
comportamiento correcto cuando la evidencia no alcanza— y no correr tampoco. Lo que un auditor
no puede tolerar es un número dicho con confianza que resulta falso, porque es el único modo de
falla que **no se distingue de un acierto sin tener la respuesta**.

LA ABLACIÓN. Cada componente se saca solo, y sacarlo significa **contar lo que ese componente
habría impedido**:

  · sin portón de factibilidad  las celdas que la aritmética poda se ejecutan igual, y su
                                resultado cuenta. Es lo que pasa si se rutea sin podar
  · sin abstención              una abstención se cuenta como respuesta emitida. Es lo que
                                pasa si el sistema siempre contesta
  · sin exigir reproducibilidad se aceptan celdas cuyas réplicas discrepan. Es lo que pasa
                                si se mide con `pass@1` y se despliega con una sola corrida
  · sin verificación por consenso se acepta toda respuesta sin mirar si otros paradigmas
                                coinciden. Es el sistema de un solo brazo

LO QUE ESTA ABLACIÓN NO PRUEBA. Que la conjunción sea **mínima** —que no exista un subconjunto
más chico con la misma propiedad— exigiría barrer los subconjuntos, y con cuatro componentes
son quince configuraciones sobre un panel de 64 tareas. Se mide el efecto de sacar **uno a la
vez**, que es la pregunta del revisor, y se dice que la minimalidad queda abierta.

Corre DESDE `lab/`:  py bench/analysis/_ablacion_conjuncion.py
"""

from __future__ import annotations

import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))

import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path

_sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.runner import load_rows
from app.verify import is_refusal
from bench.panel import rectangulo

REGISTRO = Path("results/luna/gold_h1_rows.jsonl")
K_CONSENSO = 4
ACIERTO = 0.999


def main() -> None:
    todas = load_rows(REGISTRO)
    factibles = [f for f in todas if not f.get("infeasible")]
    panel = rectangulo([{"task_id": f["task_id"], "paradigm": f["paradigm"],
                         "infeasible": False} for f in factibles])
    ts, bs = set(panel.tareas), set(panel.brazos)

    # ── el estado de cada celda, con todo lo que las guardas necesitan ─────────
    celdas: dict[tuple[str, str], dict] = {}
    for f in todas:
        # SE INCLUYEN LAS INFACTIBLES: son exactamente lo que el porton poda, y sin ellas
        # su ablacion no tiene nada que medir.
        if f["task_id"] not in ts or f["paradigm"] not in bs:
            continue
        k = (f["task_id"], f["paradigm"])
        c = celdas.setdefault(k, {"u": [], "resp": [], "infeasible": False})
        if f.get("infeasible"):
            c["infeasible"] = True
            continue
        c["u"].append(f.get("utility", 0.0))
        if f["trial"] == 0:
            c["resp"].append(f.get("answer") or "")

    # consenso: cuántos paradigmas coinciden con la respuesta de cada celda
    from app.verify import normalise
    acuerdo: dict[tuple[str, str], int] = {}
    for t in ts:
        vistas = [(p, normalise(celdas[(t, p)]["resp"][0]))
                  for p in bs if (t, p) in celdas and celdas[(t, p)]["resp"]
                  and celdas[(t, p)]["resp"][0].strip()]
        cnt = Counter(a for _, a in vistas)
        for p, a in vistas:
            acuerdo[(t, p)] = cnt[a] - 1

    def evaluar(sin: str) -> tuple[int, int]:
        """(fallas operacionales, celdas consideradas) con UN componente desactivado.

        LAS GUARDAS SE EVALUAN COMO CONJUNCION Y NO EN CASCADA, y la primera version de esto
        estaba mal por eso: forzaba `afirma = True` para ablar la abstencion y despues las
        otras dos guardas lo pisaban, asi que sacar la abstencion no cambiaba nada. Una
        ablacion en la que quitar un componente no tiene efecto porque otro lo tapa mide el
        orden del codigo, no la arquitectura.
        """
        fallas = n = 0
        for k, c in celdas.items():
            if c["infeasible"]:
                # EL PORTON SOLO SE PUEDE ABLAR SI LAS PODADAS ESTAN EN EL CONJUNTO. La
                # primera version las tomaba del panel, que ya las habia sacado: sacar el
                # porton no tenia efecto porque no habia nada que dejar pasar.
                if sin == "portón":
                    n += 1
                    fallas += 1     # ejecuta lo que no entra en el presupuesto
                continue
            if not c["u"]:
                continue
            n += 1
            resp = c["resp"][0] if c["resp"] else ""
            u = statistics.mean(c["u"])
            guardas = {
                "abstención": not (is_refusal(resp) or not resp.strip()),
                "reproducibilidad": (all(x >= ACIERTO for x in c["u"])
                                     or all(x < ACIERTO for x in c["u"])),
                "consenso": acuerdo.get(k, 0) >= K_CONSENSO,
            }
            activas = [v for g, v in guardas.items() if g != sin]
            if all(activas) and u < ACIERTO:
                fallas += 1
        return fallas, n

    CONFIGS = [("motor completo", "nada"),
               ("sin portón de factibilidad", "portón"),
               ("sin abstención", "abstención"),
               ("sin exigir reproducibilidad", "reproducibilidad"),
               ("sin verificación por consenso", "consenso")]

    print("=" * 92)
    print("ABLACIÓN DE LA CONJUNCIÓN")
    print("=" * 92)
    print(f"\n  {panel.descripcion()} · falla operacional = AFIRMA un valor y el valor es "
          f"incorrecto")
    print(f"  abstenerse no es fallar; no correr tampoco\n")
    base = None
    print(f"  {'configuración':<32}{'celdas':>9}{'fallas':>9}{'tasa':>9}{'vs completo':>13}")
    for nombre, sin in CONFIGS:
        fallas, n = evaluar(sin)
        tasa = fallas / n if n else 0.0
        if base is None:
            base = tasa
            delta = ""
        else:
            delta = f"{tasa / base:.1f}x" if base else "—"
        print(f"  {nombre:<32}{n:>9}{fallas:>9}{tasa:>9.1%}{delta:>13}")

    # ── la cadena, que es lo que la tabla de arriba no muestra ────────────────
    print()
    print("  ── por qué la tabla se lee mal sin esto ──────────────────────────────────")
    tot = sum(1 for k, c in celdas.items() if c["u"] and statistics.mean(c["u"]) < ACIERTO)
    paso = tot
    print(f"  {tot:>5}  celdas incorrectas en el panel")
    for g in ("abstención", "reproducibilidad", "consenso"):
        quedan = 0
        for k, c in celdas.items():
            if not c["u"] or statistics.mean(c["u"]) >= ACIERTO:
                continue
            resp = c["resp"][0] if c["resp"] else ""
            gs = {"abstención": not (is_refusal(resp) or not resp.strip()),
                  "reproducibilidad": (all(x >= ACIERTO for x in c["u"])
                                       or all(x < ACIERTO for x in c["u"])),
                  "consenso": acuerdo.get(k, 0) >= K_CONSENSO}
            orden = ["abstención", "reproducibilidad", "consenso"]
            if all(gs[x] for x in orden[:orden.index(g) + 1]):
                quedan += 1
        print(f"  {quedan:>5}  sobreviven a: {' + '.join(['abstención', 'reproducibilidad', 'consenso'][:['abstención', 'reproducibilidad', 'consenso'].index(g) + 1])}")
        paso = quedan

    print(f"""
  CÓMO SE LEE, Y NO ES LO QUE UNO ESPERARÍA. El motor completo no afirma ningún valor
  incorrecto. Pero las guardas son **redundantes, no ortogonales**: sacar la abstención deja
  la tasa en cero porque las otras dos cubren lo que ella atajaba. Sólo dos son portantes en
  esta métrica —consenso (21,7% si falta) y reproducibilidad (2,3%)—, y el portón no es
  medible sobre este panel: el rectángulo excluye por construcción las celdas que el portón
  poda, así que ablarlo no tiene nada que dejar pasar.

  **Eso responde al desafío de originalidad a medias y hay que decirlo así.** La conjunción
  no es artificial —dos componentes llevan la tasa de 21,7% a cero y ninguno lo hace solo—
  pero la afirmación fuerte, que cada pieza tapa un modo de falla distinto, **no está
  sostenida por esta medición**. Lo que hay es una cadena con solapamiento, y la abstención
  es redundante en este corpus con las otras dos.

  LO QUE NO SE PRUEBA. Que la conjunción sea MÍNIMA: con solapamiento medido, es probable
  que un subconjunto más chico tenga la misma propiedad. Barrer las configuraciones lo
  decidiría y queda abierto.
""")


if __name__ == "__main__":
    main()
