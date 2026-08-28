"""X-5a: la escala de costo en PLATA, y si eso cambia alguna decision.

La pregunta no es «cuanto sale». Es si el orden cambia: `lambda_cost` barre sobre la
escala de costo y elige el mejor fijo, asi que si la escala pasa de tokens a plata y el
ganador es otro, entonces todo lo publicado sobre el mejor fijo estaba medido en la
unidad equivocada. Si el ganador es el mismo, la conversion es cosmetica y se dice.
"""

import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from _sanity import bounded
from app.metrics import Observation, Study, Tariff
from app.runner import load_rows
from app.tariffs import NANO

LAMBDAS = [0.0, 0.05, 0.1, 0.2, 0.5, 1.0]


def observaciones(rows):
    por = defaultdict(list)
    for r in rows:
        por[(r["task_id"], r["paradigm"])].append(r)
    out, sin_split = [], 0
    for (task, paradigm), rs in sorted(por.items()):
        if any(r.get("error") for r in rs):
            continue
        # El split es lo que la conversion necesita. Una celda que no lo tiene no se
        # convierte y NO se cuenta como gratis: se cuenta aparte y se declara.
        if not all(r.get("prompt_tokens") or r.get("completion_tokens") for r in rs):
            sin_split += 1
            continue
        n = len(rs)
        out.append(Observation(
            task_id=task, region=rs[0]["region"], paradigm=paradigm,
            utility=sum(r["utility"] for r in rs) / n,
            cost_tokens=round(sum(r["cost_tokens"] for r in rs) / n),
            prompt_tokens=round(sum(r["prompt_tokens"] for r in rs) / n),
            completion_tokens=round(sum(r["completion_tokens"] for r in rs) / n),
        ))
    return out, sin_split


def main() -> None:
    raiz = Path("results/nano")
    corpora = sorted({p.parent.name for p in raiz.rglob("*.jsonl")}) if raiz.exists() else []
    if not corpora:
        print("No hay registro nano. Nada que convertir — se dice, no se inventa.")
        return

    veredictos = []
    for corpus in corpora:
        # Un `.jsonl` bajo `results/` ES un archivo de filas: lo garantiza el layout
        # —`state/` guarda el ledger— y lo impone `load_rows`, que levanta si no lo es.
        # Antes esto lo esquivaba aca, y esquivarlo en el analizador deja el problema en
        # pie para el analizador siguiente.
        rows = []
        for f in sorted((raiz / corpus).glob("*.jsonl")):
            rows.extend(load_rows(f))
        if not rows:
            continue
        obs, sin_split = observaciones(rows)
        if len(obs) < 4:
            print(f"\n{corpus}: {len(obs)} celdas convertibles, {sin_split} sin split — SIN N")
            continue

        tok, plata = Study(obs), Study(obs, tariff=NANO)
        if not tok.complete_tasks:
            print(f"\n{corpus}: ninguna tarea con fila completa — SIN N")
            continue

        print(f"\n=== {corpus} — {len(tok.complete_tasks)} tareas completas"
              f"{f', {sin_split} celdas sin split excluidas' if sin_split else ''}")
        st, sp = tok.cost_spread(), plata.cost_spread()
        # El mas barato es 1,0 por construccion, asi que nadie puede quedar debajo. Es la
        # invariante que delato el clamp `max(1.0, cheapest)`, que daba 0,0 para todos.
        for u, tabla in (("tokens", st), ("plata", sp)):
            for brazo, fila in tabla.items():
                bounded(fila["cost_multiple"], 1.0, None, f"{corpus}/{brazo} en {u}")
        print(f"  {'brazo':<14} {'xtokens':>8} {'xplata':>8} {'%salida':>8}")
        for p in sorted(st, key=lambda k: st[k]["cost_multiple"]):
            o = [x for x in obs if x.paradigm == p]
            tot = sum(x.prompt_tokens + x.completion_tokens for x in o)
            frac = sum(x.completion_tokens for x in o) / tot if tot else 0.0
            print(f"  {p:<14} {st[p]['cost_multiple']:>8.2f} {sp[p]['cost_multiple']:>8.2f}"
                  f" {frac:>7.1%}")

        # LA PREGUNTA. Mismo lambda, dos unidades: cambia el mejor fijo?
        cambios = []
        for lam in LAMBDAS:
            a = Study(obs, lambda_cost=lam).best_fixed()
            b = Study(obs, lambda_cost=lam, tariff=NANO).best_fixed()
            if a != b:
                cambios.append((lam, a, b))
        if cambios:
            print("  EL ORDEN CAMBIA:")
            for lam, a, b in cambios:
                print(f"    lambda={lam}: en tokens gana {a}, en plata gana {b}")
        else:
            print("  El mejor fijo es el MISMO en las dos unidades, en todo lambda.")
        # INVARIANCIA A LA REFERENCIA. El arancel es un numero puesto a mano, asi que
        # cualquier conclusion que dependa de su valor no vale. Se barre la unica
        # propiedad que un arancel tiene —cuanto mas cara es la salida que la entrada— y
        # se mira si el orden aguanta. Si aguanta en todo el barrido, el resultado es del
        # REGISTRO y no del precio; si se da vuelta en algun lado, el precio decide y hay
        # que declararlo en vez de elegir uno.
        base = tok.cost_spread()
        orden_tok = sorted(base, key=lambda k: base[k]["cost_multiple"])
        print("  invariancia (salida/entrada):", end="")
        rotos, compresiones = [], []
        for r in (1, 2, 4, 8, 16, 32):
            t = Tariff(name=f"ref/x{r}", prompt_per_mtok=1.0, completion_per_mtok=float(r))
            sp_r = Study(obs, tariff=t).cost_spread()
            if sorted(sp_r, key=lambda k: sp_r[k]["cost_multiple"]) != orden_tok:
                rotos.append(r)
            peor = max(sp_r.values(), key=lambda f: f["cost_multiple"])["cost_multiple"]
            compresiones.append((r, peor / base[orden_tok[-1]]["cost_multiple"]))
        print(" " + "  ".join(f"x{r}:{c:.2f}" for r, c in compresiones))
        if rotos:
            print(f"    EL PRECIO DECIDE: el orden se da vuelta en {rotos}. "
                  f"No se puede publicar un orden sin declarar el arancel.")
        else:
            print("    El orden aguanta en todo el barrido: es del REGISTRO, no del precio.")

        veredictos.append((corpus, bool(cambios)))

    if not veredictos:
        print("\nNingun corpus evaluable — SIN N, y eso no es un resultado negativo.")
        return
    cambian = [c for c, v in veredictos if v]
    print(f"\n{'='*60}\n{len(cambian)}/{len(veredictos)} corpus cambian de mejor fijo "
          f"al pasar de tokens a plata"
          + (f": {', '.join(cambian)}" if cambian else "."))


if __name__ == "__main__":
    main()
