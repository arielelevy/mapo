"""La factibilidad tiene DOS ejes y yo chequeaba uno.

EL DEFECTO, EN UNA LINEA. `check()` calculaba `projected_tokens` y no lo comparaba con
nada. Sobre gold_deep c2-000-w48 devolvio `feasible=True, projected_tokens=486.404` con un
presupuesto declarado de 60.000. Tenia el numero en la mano y no lo uso. map_reduce salio a
correr y gasto 343.682 tokens, 5,7x el presupuesto.

EL DIAGNOSTICO. Estaba chequeando CONTEXTO -- entra en un prompt -- y llamando a eso
factibilidad. Pero hay un segundo limite igual de duro:

    CONTEXTO   cabe una llamada?          direct/cot fallan aca
    PRESUPUESTO cabe el gasto TOTAL?      map_reduce falla aca

map_reduce pasa contexto por construccion (nunca junta las unidades) y por eso parecia
escalar. Falla presupuesto, que es el eje que nunca mire. Y es el eje que mas importa,
porque es justamente el costo lo que el paper dice que esta capa acota.

GASTO GARANTIZADO vs GASTO EN EL PEOR CASO. La distincion que hace util al chequeo:

    garantizado    el patron lee cada unidad POR DEFINICION. direct, cot, map_reduce.
                   Si excede el presupuesto es INFACTIBLE, punto.
    peor caso      el patron PUEDE leer todo pero lee a demanda. react, reflection,
                   plan_execute, dag. Sigue factible, y necesita un tope en ejecucion.

Sin esa distincion o se poda a los selectivos en todas partes (y se pierde su unica
ventaja) o no se poda a map_reduce en ninguna (y se gastan 343k tokens en descubrirlo).
"""

# Corre DESDE `lab/`: las rutas de datos son relativas al CWD. El prologo solo
# resuelve los imports, que es lo que se rompe al salir de la raiz.
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))

import pathlib
import sys

ROOT = pathlib.Path(__file__).parent


def patch(path, pairs):
    p = ROOT / path
    s = p.read_text(encoding="utf-8")
    for label, old, new in pairs:
        if old not in s:
            sys.exit(f"FAIL {path}/{label}: ancla ausente")
        s = s.replace(old, new, 1)
    p.write_text(s, encoding="utf-8")
    print(f"  {path}: {len(pairs)} bloques")


patch("app/feasibility.py", [
    # 1. Verdict lleva el eje que fallo, para que el motivo sea legible.
    (
        "verdict-axis",
        """@dataclass(frozen=True)
class Verdict:
    feasible: bool
    reason: str = ""
    projected_calls: int = 0
    projected_tokens: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "feasible": self.feasible,
            "reason": self.reason,
            "projected_calls": self.projected_calls,
            "projected_tokens": self.projected_tokens,
        }""",
        '''@dataclass(frozen=True)
class Verdict:
    feasible: bool
    reason: str = ""
    projected_calls: int = 0
    projected_tokens: int = 0
    # Which limit was hit. Two paradigms can both be infeasible for opposite reasons and
    # conflating them is what made map_reduce look like it scaled: it passes CONTEXT by
    # construction, because it never holds the units together, and fails BUDGET, because
    # it still pays for every one of them.
    axis: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "feasible": self.feasible,
            "reason": self.reason,
            "projected_calls": self.projected_calls,
            "projected_tokens": self.projected_tokens,
            "axis": self.axis,
        }''',
    ),
    # 2. Constantes del eje presupuesto.
    (
        "budget-consts",
        "# Worst-case call count for the DAG: sub-questions x sub-agent iterations x replans,\n"
        "# plus plan, verify and synthesise per round.\n"
        "MAX_ORCHESTRATION_CALLS = 200",
        '''# Worst-case call count for the DAG: sub-questions x sub-agent iterations x replans,
# plus plan, verify and synthesise per round.
MAX_ORCHESTRATION_CALLS = 200

# A paradigm whose GUARANTEED spend exceeds the declared budget by more than this is
# infeasible. Slightly above 1.0 because the projection is an estimate and refusing a
# paradigm that would have come in at 1.01x would be the check being wrong in the other
# direction. Overshoot beyond this is not an estimate error, it is a different plan.
BUDGET_OVERSHOOT_TOLERANCE = 1.15

# Paradigms that read every unit BY DEFINITION, so their spend is a guarantee and not a
# worst case. The distinction is what lets the check prune map_reduce without also
# pruning the selective paradigms, whose only advantage is that they may read less.
GUARANTEED_FULL_READ = frozenset({"direct", "cot", "map_reduce"})''',
    ),
    # 3. El chequeo de presupuesto para map_reduce, que es el que faltaba.
    (
        "map-budget",
        """        return Verdict(
            True,
            projected_calls=units + 1,
            projected_tokens=content + reduce_tokens,
        )""",
        """        # THE CHECK THAT WAS MISSING. Mapping never holds the units together, so it
        # passes the context axis at any size -- which is exactly why it looked like it
        # scaled. But it reads every one of them, so its spend is `content`, guaranteed,
        # and that has to be tested against the budget. Without this line the layer
        # computed 486,404 projected tokens against a 60,000 budget and returned
        # feasible; the paradigm then spent 5.7x the budget proving the point.
        projected = content + reduce_tokens
        if projected > budget * BUDGET_OVERSHOOT_TOLERANCE:
            return Verdict(
                False,
                f"maps over every unit, so it pays for all {units}: about {projected} "
                f"tokens against a declared budget of {budget}. Per-unit mapping keeps "
                f"the CONTEXT bounded and leaves the COST unbounded",
                projected_calls=units + 1,
                projected_tokens=projected,
                axis="budget",
            )
        return Verdict(
            True,
            projected_calls=units + 1,
            projected_tokens=projected,
        )""",
    ),
    # 4. Etiquetar el eje en los rechazos existentes.
    (
        "axis-direct",
        """                f"needs all {units} units in one prompt: about {content} tokens "
                f"against an allowance of {allowance}",
                projected_calls=1,
                projected_tokens=content,
            )""",
        """                f"needs all {units} units in one prompt: about {content} tokens "
                f"against an allowance of {allowance}",
                projected_calls=1,
                projected_tokens=content,
                axis="context",
            )""",
    ),
    (
        "axis-mapcalls",
        """                f"one call per unit over {units} units exceeds the {MAX_MAP_CALLS}-call "
                f"cap; at this cardinality it is a batch job, not a strategy",
                projected_calls=units + 1,
                projected_tokens=content + units * EST_FINDING_CHARS // CHARS_PER_TOKEN,
            )""",
        """                f"one call per unit over {units} units exceeds the {MAX_MAP_CALLS}-call "
                f"cap; at this cardinality it is a batch job, not a strategy",
                projected_calls=units + 1,
                projected_tokens=content + units * EST_FINDING_CHARS // CHARS_PER_TOKEN,
                axis="cardinality",
            )""",
    ),
    (
        "axis-reduce",
        """                f"the reduce step would concatenate {units} findings, about "
                f"{reduce_tokens} tokens against an allowance of {allowance}. "
                f"Per-unit mapping scales; the reduce does not",
                projected_calls=units + 1,
                projected_tokens=content + reduce_tokens,
            )""",
        """                f"the reduce step would concatenate {units} findings, about "
                f"{reduce_tokens} tokens against an allowance of {allowance}. "
                f"Per-unit mapping scales; the reduce does not",
                projected_calls=units + 1,
                projected_tokens=content + reduce_tokens,
                axis="context",
            )""",
    ),
    (
        "axis-dag",
        """                f"worst-case orchestration is {projected} calls, above the "
                f"{MAX_ORCHESTRATION_CALLS} cap",
                projected_calls=projected,
            )""",
        """                f"worst-case orchestration is {projected} calls, above the "
                f"{MAX_ORCHESTRATION_CALLS} cap",
                projected_calls=projected,
                axis="cardinality",
            )""",
    ),
    # 5. Los selectivos: honestos sobre que su cota es peor-caso y no garantia.
    (
        "selective",
        """    # react and reflection are bounded by their own iteration caps and read
    # selectively, so they remain feasible at any corpus size. That is a real property
    # of those topologies, not an omission.
    return FEASIBLE""",
        '''    # react and reflection read selectively and cap their own iterations, so `content`
    # is their WORST case and not a guarantee -- they may well answer after two units.
    # Pruning them on a worst case would discard their only advantage, so they stay
    # feasible and the budget has to be enforced at RUNTIME instead, by the tool surface
    # degrading a bulk read it cannot afford.
    #
    # Saying that plainly is the point. This layer bounds the paradigms whose spend is a
    # guarantee; it does not bound the ones whose spend is a decision, and a check that
    # claimed otherwise would be lying about which risk it retires.
    return Verdict(
        True,
        projected_tokens=content,
        axis="worst_case_only",
    )''',
    ),
])

print()
print("=== el mismo caso, ahora ===")
sys.path.insert(0, str(ROOT))
import importlib
import json
from app import feasibility as F
importlib.reload(F)
docs = json.loads((ROOT / "corpus/gold_deep/documents.json").read_text(encoding="utf-8"))
tasks = json.loads((ROOT / "corpus/gold_deep/tasks.json").read_text(encoding="utf-8"))
for tid in ("c2-000-w48", "c2-000-w16", "c2-000-w4"):
    t = [x for x in tasks if x["task_id"] == tid][0]
    v = F.check("map_reduce", docs, t)
    content = sum(len(docs[u]) for u in t["unit_ids"]) // 4
    print(f"  {tid:12s} {len(t['unit_ids']):3d} unid  {content:7,d} tok  budget={t['budget_tokens']:,}  "
          f"-> feasible={v.feasible} axis={v.axis or '-'}")
    if not v.feasible:
        print(f"       {v.reason}")
