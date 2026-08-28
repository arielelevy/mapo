"""T-4b: cuanto se deja de RESPONDER por subir el piso. La otra mitad del ratchet.

LA MITAD QUE YA ESTABA. `COTA_RATCHET.es.md` acota el DAÑO: como el piso solo sube y hay
cuatro niveles, una region no puede subir mas de dos veces para siempre, asi que el
perjuicio de un endurecimiento equivocado esta acotado por construccion.

LA MITAD QUE FALTABA, Y ES LA QUE SE PAGA. Una cota sobre el dano no dice nada sobre el
COSTO DE OPORTUNIDAD. Subir una region de A1 a A3 no arruina nada —esa es la cota— pero
A3 restringe los patrones admisibles (`CERTIFIED_PATTERNS`) y, desde hoy, tambien los
modelos (`min_capability`). Cada restriccion es una pregunta que se deja de responder o
que se responde mas caro, y eso nunca se midio.

QUE MIDE ESTE ANALISIS, sobre el registro que ya existe y sin gastar un token:

  cobertura      que fraccion de las tareas conserva al menos un paradigma admisible
                 cuando se sube el piso de su region
  utilidad       cuanto pierde la utilidad del mejor fijo al quedarse con menos brazos
  quien paga     que regiones concentran la perdida — porque si la concentra una sola,
                 el ratchet es barato en promedio y caro donde importa, que no es lo
                 mismo que barato

EL BARRIDO ES CONTRAFACTUAL Y NO NECESITA CORRER NADA. El registro tiene la grilla
completa: para cada nivel se calcula que habria pasado restringiendo a los brazos que ese
nivel admite. Eso es aritmetica sobre lo ya pagado, que es la unica forma honesta de
contestar una pregunta de este tamano sin encargar una corrida.
"""

# Corre DESDE `lab/`: las rutas de datos son relativas al CWD. El prologo solo
# resuelve los imports, que es lo que se rompe al salir de la raiz.
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))

import sys
from collections import defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from bench._sanity import bounded, share
from app.assurance import Assurance, PROFILES
from app.metrics import Observation, Study
from app.runner import load_rows


def observaciones(rows: list[dict]) -> list[Observation]:
    por = defaultdict(list)
    for r in rows:
        por[(r["task_id"], r["paradigm"])].append(r)
    out = []
    for (task, paradigm), rs in sorted(por.items()):
        if any(r.get("error") for r in rs):
            continue
        n = len(rs)
        out.append(Observation(
            task_id=task, region=rs[0]["region"], paradigm=paradigm,
            utility=sum(r["utility"] for r in rs) / n,
            cost_tokens=round(sum(r["cost_tokens"] for r in rs) / n),
        ))
    return out


def main() -> None:
    raiz = Path("results/nano")
    if not raiz.exists():
        print("No hay registro nano. Nada que contrafactualizar — se dice, no se inventa.")
        return

    corpora = sorted({p.parent.name for p in raiz.rglob("*.jsonl")})
    evaluados = 0
    for corpus in corpora:
        rows: list[dict] = []
        for f in sorted((raiz / corpus).glob("*.jsonl")):
            rows.extend(load_rows(f))
        if not rows:
            continue
        obs = observaciones(rows)
        if len(obs) < 4:
            print(f"\n{corpus}: {len(obs)} celdas — SIN N")
            continue
        estudio = Study(obs)
        if not estudio.complete_tasks:
            print(f"\n{corpus}: ninguna tarea con fila completa — SIN N")
            continue

        catalogo = set(estudio.paradigms)
        print(f"\n=== {corpus} — {len(estudio.complete_tasks)} tareas, "
              f"{len(catalogo)} brazos: {sorted(catalogo)}")

        # LA LINEA BASE es el nivel mas laxo, no el mejor imaginable: lo que el ratchet
        # cuesta es la diferencia contra lo que habia ANTES de subir, no contra un ideal.
        base_level = Assurance.EXPLORATORY
        base_arms = _admisibles(catalogo, base_level)
        base_util = _utilidad(estudio, base_arms)

        print(f"  {'nivel':<16} {'brazos':<8} {'cobertura':>10} {'u(mejor fijo)':>14} "
              f"{'perdida':>9}")
        por_nivel = {}
        for nivel in Assurance:
            arms = _admisibles(catalogo, nivel)
            cobertura = share(len(arms), len(catalogo), f"{corpus}/{nivel.label}")
            util = _utilidad(estudio, arms)
            perdida = None if util is None or base_util is None else base_util - util
            por_nivel[nivel] = (arms, util)
            bounded(cobertura, 0.0, 1.0, f"cobertura {corpus}/{nivel.label}")
            print(f"  {nivel.label:<16} {len(arms):<8} {cobertura:>9.1%} "
                  f"{'—' if util is None else f'{util:>14.4f}'} "
                  f"{'—' if perdida is None else f'{perdida:>9.4f}'}")

        # QUIEN PAGA. Un promedio barato con una region cara no es barato: es barato en
        # promedio y caro donde importa, y las dos cosas se reportan por separado.
        peor = _por_region(estudio, por_nivel[Assurance.EXPLORATORY][0],
                           por_nivel[Assurance.CERTIFIED][0])
        if peor:
            print("  perdida por region al endurecer A0 -> A3 (peores 5):")
            for region, delta, n in peor[:5]:
                # UNA TAREA NO ES UNA REGION. Un delta sobre n=1 es un sorteo, no una
                # propiedad de la region, y sin la marca el numero mas grande de la tabla
                # —que casi siempre es el de n mas chico— se lee como el hallazgo.
                marca = "  <- n=1, un sorteo, no la region" if n == 1 else ""
                print(f"    {region:<34} {delta:+.4f}  ({n} tareas){marca}")
            solidas = [x for x in peor if x[2] >= 3]
            if solidas:
                r, d, n = solidas[0]
                print(f"    peor con n>=3: {r} {d:+.4f} ({n} tareas)")
        evaluados += 1

    if not evaluados:
        print("\nNingun corpus evaluable — SIN N, y eso no es un resultado negativo.")


def _admisibles(catalogo: set[str], nivel: Assurance) -> list[str]:
    perfil = PROFILES[nivel]
    return sorted(p for p in catalogo if perfil.permits(p))


def _utilidad(estudio: Study, arms: list[str]) -> float | None:
    """Utilidad del mejor fijo entre `arms`. `None` cuando el nivel no deja ninguno.

    `None` NO es cero. Un nivel que no admite ningun brazo no responde con utilidad cero:
    **no responde**, y eso es lo que la columna tiene que decir. Un cero se promediaria
    con los demas y haria parecer que el endurecimiento cuesta poco.
    """
    if not arms:
        return None
    return max(estudio.mean_utility(p) for p in arms)


def _por_region(
    estudio: Study, laxos: list[str], estrictos: list[str]
) -> list[tuple[str, float, int]]:
    """Cuanta utilidad pierde cada region al pasar del nivel mas laxo al mas estricto."""
    if not laxos:
        return []
    por_region: dict[str, list[str]] = defaultdict(list)
    for o in estudio._obs:  # noqa: SLF001
        if o.task_id in estudio.complete_tasks:
            por_region[o.region].append(o.task_id)

    out = []
    for region, tareas in sorted(por_region.items()):
        unicas = sorted(set(tareas))
        antes = _mejor_en(estudio, unicas, laxos)
        despues = _mejor_en(estudio, unicas, estrictos)
        if antes is None:
            continue
        # Sin brazos admisibles la region deja de responderse. Se reporta como la perdida
        # entera de lo que se conseguia, que es exactamente lo que pasa.
        delta = -antes if despues is None else despues - antes
        out.append((region, delta, len(unicas)))
    return sorted(out, key=lambda x: x[1])


def _mejor_en(estudio: Study, tareas: list[str], arms: list[str]) -> float | None:
    if not arms:
        return None
    medias = []
    for p in arms:
        vals = [estudio.utility(t, p) for t in tareas if p in estudio._by_task[t]]  # noqa: SLF001
        if vals:
            medias.append(sum(vals) / len(vals))
    return max(medias) if medias else None


if __name__ == "__main__":
    main()
