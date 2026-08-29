"""Feasibility as arithmetic, checked before anything runs.

THE GAP THIS CLOSES. `direct` already refuses when the material does not fit, but the
other paradigms had no cap at all, and two of them need one badly:

    map_reduce      one call per unit plus a reduce over every partial. At 500 units
                    that is 501 calls and a reduce prompt built from 500 findings. It
                    never puts the whole corpus in one context — which is why it looks
                    like it scales — but the REDUCE does, and the call count is a cost
                    ceiling regardless.

    dag_strategy    waves x sub-agents x iterations, with replans on top. The product
                    is knowable in advance and can exceed any budget.

WHY IT IS A SEPARATE LAYER, AND WHY IT MATTERS FOR THE THESIS. Every check here is
arithmetic over quantities the task already declares: how many units, how long they are,
what the budget is. No model call, no statistics, no learning. So the plan space can be
pruned deterministically BEFORE any selection happens, and a paradigm that cannot run is
never a candidate.

That makes feasibility the cheapest routing signal that exists, and it is upstream of
everything else in this harness. A learned policy that spends episodes discovering that
map_reduce loses on 500-unit tasks is learning arithmetic the hard way — the cap was
computable from the task before the first token was spent.

The corollary is the one that matters in production: knowing the length and declining is
not a degradation. It is the difference between a bounded system and a runaway.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Sequence
from .tools import SUMMARY_CHARS

if TYPE_CHECKING:  # el catalogo de modelos importa metrics, y la factibilidad no debe depender del analisis
    from .models import Model

CHARS_PER_TOKEN = 4

# Una linea de gist por unidad. Se DERIVA de la formula que la produce
# (`tools._summarise`: `body[:SUMMARY_CHARS]` mas " … [N chars]") en vez de declararse
# a mano, mas un margen para el sobre de la respuesta de busqueda — id de unidad y JSON.
#
# POR QUE IMPORTABA. Estaba fijo en 400 y el gist real de `gold_transfer` promedia 69,4
# caracteres con un maximo de 126: una sobre-proyeccion de 5,8x. La factibilidad rechaza
# un paradigma cuando su proyeccion no entra en el presupuesto, asi que inflar el gist
# no es conservador — declara INFACTIBLE a un paradigma que entraba, y esa exclusion
# entra al registro como si fuera un hecho aritmetico sobre la tarea.
#
# Sigue siendo una COTA SUPERIOR, no un promedio: la factibilidad no puede sub-proyectar
# sin admitir planes que no entran. Por eso parte de SUMMARY_CHARS —el techo del recorte—
# y no de la media medida.
GIST_ENVELOPE_CHARS = 40  # " … [NNNNN chars]" + id de unidad + sobre JSON
GIST_CHARS = SUMMARY_CHARS + GIST_ENVELOPE_CHARS

# A paradigm may consume this share of the task budget. The remainder is the
# conversation itself, which a paradigm using the entire budget would not leave room for.
BUDGET_SHARE = 0.6

# One model call per unit stops being a strategy and becomes a batch job. The cap is a
# cost ceiling, not a context limit: 500 calls will complete and should not be paid for.
MAX_MAP_CALLS = 80

# Projected size of a reduce prompt: one finding per unit, at roughly this size each.
EST_FINDING_CHARS = 220

# Worst-case call count for the DAG: sub-questions x sub-agent iterations x replans,
# plus plan, verify and synthesise per round.
MAX_ORCHESTRATION_CALLS = 200

# La forma del handoff, DERIVADA del patron y no repetida a mano. Importarlos crearia un
# ciclo —`paradigms` importa `tools`, que importa esto— asi que se declaran aca con el
# nombre del que salen, y `test_science.py` §39 verifica que no se hayan separado.
HANDOFF_SCOPES = 2      # paradigms.handoff.SCOPES
HANDOFF_TURNS = 6       # paradigms.handoff.MAX_TURNS_PER_AGENT

# A paradigm whose GUARANTEED spend exceeds the declared budget by more than this is
# infeasible. Slightly above 1.0 because the projection is an estimate and refusing a
# paradigm that would have come in at 1.01x would be the check being wrong in the other
# direction. Overshoot beyond this is not an estimate error, it is a different plan.
BUDGET_OVERSHOOT_TOLERANCE = 1.15

# Hard ceiling on pointer_chase hops. The effective cap per task is the arithmetic
# min(this, allowance // mean unit): the chase reads ONE unit per hop, so its spend is
# hops x unit, knowable here and enforced identically at runtime.
POINTER_HOP_CAP = 6

# LOS QUE RECORREN EL ALCANCE ENTERO POR CONSTRUCCION viven en `paradigms`, no aca.
#
# Habia una `GUARANTEED_FULL_READ` en este modulo que NADIE consultaba, y una
# `TRAVERSES_SCOPE` en `paradigms` que el router SI consulta: la misma propiedad escrita
# dos veces, una de ellas muerta. Y ya diferian — la de aca incluia `cot`, que esta
# retirado— que es como empiezan a separarse dos listas de lo mismo.
#
# Se elimino la muerta en vez de cablearla: la viva ya gobierna la precondicion de
# cobertura (`U-2`), que es el unico consumidor que la propiedad necesita.



@dataclass(frozen=True)
class Verdict:
    feasible: bool
    reason: str = ""
    # AUSENTE NO ES CERO, y aca costo caro. Cada rama de `check` llenaba SOLO el eje que
    # miraba: `dag_strategy` proyecta llamadas y deja los tokens en 0, `react` al reves.
    # Mientras el numero solo se imprimia no molestaba. Apenas una cota lo consumio —la
    # de plata, `check_pair`— el 0 se leyo como GRATIS y declaro admisible en el modelo
    # caro justo al brazo que mide 59x los tokens de `direct`.
    #
    # `None` es «no proyectado» y ninguna cota puede correr sobre eso: se niega a decidir
    # y lo dice. Un 0 no se puede distinguir de una proyeccion real que dio cero.
    projected_calls: int | None = None
    projected_tokens: int | None = None
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
        }


FEASIBLE = Verdict(feasible=True)


def _content_tokens(documents: dict[str, str], unit_ids: list[str]) -> int:
    return sum(len(documents[u]) for u in unit_ids) // CHARS_PER_TOKEN


# The paradigms whose spend is a DECISION, not a guarantee: they read selectively and
# cap their own iterations, so `content` is a worst case and pruning on it would discard
# their only advantage. They are feasible here and bounded at runtime instead.
WORST_CASE_ONLY = frozenset({"react", "reflection"})

# CUANTAS LLAMADAS PUEDE HACER CADA UNO EN EL PEOR CASO. Su GASTO es una decision del
# modelo, pero su CANTIDAD DE LLAMADAS no: la fija el codigo con `max_iterations`. Que el
# gasto sea indeterminado no vuelve indeterminado al conteo, y confundir las dos cosas es
# lo que dejaba a estos brazos sin proyeccion.
#
# POR QUE IMPORTA AHORA Y NO ANTES. Mientras `projected_calls` solo se imprimia, un `None`
# no molestaba. Desde que `check_pair` cobra plata sobre la proyeccion, un brazo sin
# proyectar no se puede cotizar — y se declara «no evaluado», que es correcto y es peor
# que evaluarlo cuando se puede.
WORST_CASE_CALLS = {
    "react": 20,        # paradigms.__init__: _run_tool_loop(max_iterations=20)
    "reflection": 4 + 8,  # borrador (4) + revision (8)
}

# Every name this layer has arithmetic for. Kept explicit so an unknown one raises
# instead of falling through the last branch as "feasible".
KNOWN_PARADIGMS = frozenset({
    "direct",
    "cot",
    "map_reduce",
    "dag_strategy",
    "plan_execute",
    "gist_reader",
    "rewoo",
    "pointer_chase",
    "graph_traverse",
    "extract_compute",
    "streaming_scan",
}) | WORST_CASE_ONLY


def check(
    paradigm: str, documents: dict[str, str], task: dict[str, Any]
) -> Verdict:
    """Whether `paradigm` can run this task at all. Pure arithmetic."""
    unit_ids = task["unit_ids"]
    units = len(unit_ids)
    budget = int(task["budget_tokens"])
    allowance = int(budget * BUDGET_SHARE)
    content = _content_tokens(documents, unit_ids)

    if paradigm in ("direct", "cot"):
        # One prompt containing every unit.
        if content > allowance:
            return Verdict(
                False,
                f"needs all {units} units in one prompt: about {content} tokens "
                f"against an allowance of {allowance}",
                projected_calls=1,
                projected_tokens=content,
                axis="context",
            )
        return Verdict(True, projected_calls=1, projected_tokens=content)

    if paradigm == "map_reduce":
        # One call per unit, then a reduce over every partial finding.
        if units > MAX_MAP_CALLS:
            return Verdict(
                False,
                f"one call per unit over {units} units exceeds the {MAX_MAP_CALLS}-call "
                f"cap; at this cardinality it is a batch job, not a strategy",
                projected_calls=units + 1,
                projected_tokens=content + units * EST_FINDING_CHARS // CHARS_PER_TOKEN,
                axis="cardinality",
            )
        reduce_tokens = units * EST_FINDING_CHARS // CHARS_PER_TOKEN
        if reduce_tokens > allowance:
            return Verdict(
                False,
                f"the reduce step would concatenate {units} findings, about "
                f"{reduce_tokens} tokens against an allowance of {allowance}. "
                f"Per-unit mapping scales; the reduce does not",
                projected_calls=units + 1,
                projected_tokens=content + reduce_tokens,
                axis="context",
            )
        # THE CHECK THAT WAS MISSING. Mapping never holds the units together, so it
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
        )

    if paradigm == "dag_strategy":
        # 4 sub-questions x 10 iterations x (1 + 3 replans), plus plan/verify/synthesise.
        projected = 4 * 10 * 4 + 4 + 1
        # LOS TOKENS: cada rama puede ver el material entero —nada le impide leerlo— y
        # ademas arrastra el blackboard, que crece con lo que las ramas anteriores
        # encontraron. La cota superior honesta es contenido x ramas, y la medicion la
        # respalda: `dag_strategy` mide 89.834 tokens por celda contra 30.000 de
        # contenido, o sea ~3x. Proyectarlo como `content` a secas seria sub-proyectar,
        # que en una cota de admision es el error caro.
        dag_tokens = content * 4
        if projected > MAX_ORCHESTRATION_CALLS:
            return Verdict(
                False,
                f"worst-case orchestration is {projected} calls, above the "
                f"{MAX_ORCHESTRATION_CALLS} cap",
                projected_calls=projected,
                projected_tokens=dag_tokens,
                axis="cardinality",
            )
        return Verdict(True, projected_calls=projected, projected_tokens=dag_tokens)

    if paradigm == "plan_execute":
        return Verdict(True, projected_calls=5 * 4 + 2)

    if paradigm == "gist_reader":
        # Pays the gist table by construction: one truncated summary per unit in a
        # single prompt. That spend is a guarantee, so it is tested here; the targeted
        # full reads are a decision and are bounded at runtime by the allowance.
        gist_tokens = units * GIST_CHARS // CHARS_PER_TOKEN
        if gist_tokens > allowance:
            return Verdict(
                False,
                f"the gist table alone is about {gist_tokens} tokens for {units} units "
                f"against an allowance of {allowance}",
                projected_calls=2,
                projected_tokens=gist_tokens,
                axis="context",
            )
        return Verdict(True, projected_calls=2, projected_tokens=gist_tokens)

    if paradigm == "rewoo":
        # Two LLM calls plus at most MAX_PLAN_STEPS tool executions, none of which
        # involve the model. Its spend is bounded by construction.
        #
        # LOS TOKENS SON EL CONTENIDO COMO COTA SUPERIOR, y no `None`. La segunda llamada
        # recibe la evidencia que los pasos juntaron, que en el peor caso es todo el
        # material. Es una cota floja —`rewoo` mide 2.549 tokens por celda contra 30.000
        # de contenido— y una cota floja sirve igual: la cota de plata la usa para
        # RECHAZAR, y rechazar de mas es conservador. `None` no permite ni eso.
        return Verdict(True, projected_calls=2, projected_tokens=content)

    if paradigm == "handoff":
        # ALCANCES DISJUNTOS, y de ahi sale la cota entera. `SCOPES` agentes, cada uno con
        # `MAX_TURNS_PER_AGENT` vueltas como maximo, todo fijado por el CODIGO — no hay
        # bucle que el modelo corte. Y la transferencia no agrega vueltas: re-alcanza.
        #
        # POR QUE NO SE COMPARA CONTRA EL CONTENIDO ENTERO. Un agente ve SOLO su alcance,
        # asi que su contexto es una fraccion del material: el reparto es la razon de ser
        # del patron. Compararlo contra el total lo declararia infactible exactamente
        # donde el reparto lo hace posible, que es al reves de lo que la cota tiene que
        # hacer.
        por_alcance = content // max(1, HANDOFF_SCOPES)
        proyectadas = HANDOFF_SCOPES * HANDOFF_TURNS
        if proyectadas > MAX_ORCHESTRATION_CALLS:
            return Verdict(
                False,
                f"{HANDOFF_SCOPES} alcances x {HANDOFF_TURNS} vueltas son {proyectadas} "
                f"llamadas, por encima del tope de {MAX_ORCHESTRATION_CALLS}",
                projected_calls=proyectadas,
                projected_tokens=content,
                axis="cardinality",
            )
        if por_alcance > allowance:
            return Verdict(
                False,
                f"cada alcance carga ~{por_alcance} tokens contra un margen de "
                f"{allowance}: repartir en {HANDOFF_SCOPES} no alcanza para que una "
                f"parte entre",
                projected_calls=proyectadas,
                projected_tokens=content,
                axis="context",
            )
        # UN ALCANCE POR UNIDAD ES EL PISO. Con menos unidades que alcances el reparto
        # deja alcances vacios y el patron degenera en una pasada — corre, y no es un
        # handoff. Se dice en el veredicto en vez de dejarlo pasar como si lo fuera.
        if units < HANDOFF_SCOPES:
            return Verdict(
                False,
                f"{units} unidad(es) para {HANDOFF_SCOPES} alcances: el reparto deja "
                f"alcances vacios y no hay transferencia que autorizar, asi que esto "
                f"correria como una pasada sola con nombre de handoff",
                projected_calls=proyectadas,
                projected_tokens=content,
                axis="cardinality",
            )
        return Verdict(True, projected_calls=proyectadas, projected_tokens=content)

    if paradigm == "pointer_chase":
        # Anchor pick + at most hop_cap sensor calls, ONE unit each, + solve. The hop
        # cap is the same arithmetic the paradigm applies at runtime, so the projection
        # is a guarantee, not a hope. Tested against the BUDGET like the other
        # guaranteed-spend paradigms, not against the conversation allowance: the chase
        # never resends history and solves from a small ledger, so BUDGET_SHARE would
        # reserve room for a conversation this paradigm structurally never holds. Its
        # per-call CONTEXT is one unit, bounded by construction.
        mean_unit = max(1, content // max(1, units))
        hop_cap = min(POINTER_HOP_CAP, max(2, budget // mean_unit))
        if 2 * mean_unit > budget * BUDGET_OVERSHOOT_TOLERANCE:
            return Verdict(
                False,
                f"even two hops of one unit each (~{2 * mean_unit} tokens) exceed the "
                f"declared budget of {budget}; a chain cannot be followed in under "
                f"two hops",
                projected_calls=4,
                projected_tokens=2 * mean_unit,
                axis="budget",
            )
        return Verdict(
            True,
            projected_calls=hop_cap + 2,
            projected_tokens=hop_cap * mean_unit,
        )

    if paradigm == "graph_traverse":
        # Per question: 2 LLM calls + a walk that costs nothing. The index (one short
        # call per unit, `content` read once) is amortised across every question on
        # the corpus and memoised on disk, so it is not charged per task here — the
        # first paying row records it honestly in its own usage.
        return Verdict(True, projected_calls=2)

    if paradigm in ("extract_compute", "streaming_scan"):
        # Both pay the corpus exactly once, in bounded calls; neither has a reduce
        # context bound (extract_compute reduces in code; streaming_scan carries a
        # capped registry). Their guaranteed spend is `content`, tested against budget
        # exactly like map_reduce's.
        if paradigm == "extract_compute" and units > MAX_MAP_CALLS:
            return Verdict(
                False,
                f"one extraction call per unit over {units} units exceeds the "
                f"{MAX_MAP_CALLS}-call cap",
                projected_calls=units + 2,
                axis="cardinality",
            )
        projected = int(content * 1.2)
        calls = (units + 2) if paradigm == "extract_compute" else (units // 3 + 2)
        if projected > budget * BUDGET_OVERSHOOT_TOLERANCE:
            return Verdict(
                False,
                f"scans every unit, so it pays for all {units}: about {projected} "
                f"tokens against a declared budget of {budget}",
                projected_calls=calls,
                projected_tokens=projected,
                axis="budget",
            )
        return Verdict(True, projected_calls=calls, projected_tokens=projected)

    # react and reflection read selectively and cap their own iterations, so `content`
    # is their WORST case and not a guarantee -- they may well answer after two units.
    # Pruning them on a worst case would discard their only advantage, so they stay
    # feasible and the budget has to be enforced at RUNTIME instead, by the tool surface
    # degrading a bulk read it cannot afford.
    #
    # Saying that plainly is the point. This layer bounds the paradigms whose spend is a
    # guarantee; it does not bound the ones whose spend is a decision, and a check that
    # claimed otherwise would be lying about which risk it retires.
    if paradigm not in WORST_CASE_ONLY:
        # A typo used to fall through to "feasible". The whole layer exists to say what
        # can run and why; answering that about a name it does not know is not an
        # answer, it is a guess with the shape of one.
        raise ValueError(
            f"Unknown paradigm {paradigm!r}: feasibility has no arithmetic for it. "
            f"Known: {sorted(KNOWN_PARADIGMS)}."
        )

    return Verdict(
        True,
        projected_calls=WORST_CASE_CALLS[paradigm],
        projected_tokens=content,
        axis="worst_case_only",
    )


def admissible(
    paradigms: list[str], documents: dict[str, str], task: dict[str, Any]
) -> tuple[list[str], dict[str, Verdict]]:
    """Split candidates into those that can run and the verdicts for all of them.

    Excluded paradigms are returned with their reason rather than dropped: a plan space
    that was narrowed has to say so, or a report reads as if the full space had been
    considered.
    """
    verdicts = {p: check(p, documents, task) for p in paradigms}
    return [p for p, v in verdicts.items() if v.feasible], verdicts


# Cuanto de la proyeccion es salida. `metrics` mide la mezcla REAL por brazo (0,3% a
# 9,9%), pero la factibilidad corre ANTES de que exista una fila, asi que no la tiene.
# Se usa una cota alta y no la media: sub-proyectar la salida abarata un par que no
# entraba, y la factibilidad no puede admitir planes que no entran.
PROJECTED_COMPLETION_SHARE = 0.15


# LATENCIA POR LLAMADA, medida y leida de `config/latency.json`. `L-3`.
#
# POR QUE ES UNA COTA DURA Y NO UN TERCER EJE DE LAMBDA. `lambda` expresa una PREFERENCIA
# —cuanta calidad vale una unidad de costo— y el tiempo casi nunca es eso: un request con
# un usuario esperando tiene un techo, no una tasa de cambio. Un brazo que gana 0,030 de
# utilidad y tarda 11,5x (leccion 5.19) no es «caro»: es inservible para quien espera.
#
# Va con la ventana y la plata, que son las otras dos cotas duras, y NO con lambda.
_LATENCY_PATH = Path(__file__).resolve().parent.parent / "config" / "latency.json"


def _load_latency() -> tuple[dict[str, float], float]:
    if not _LATENCY_PATH.exists():
        raise FileNotFoundError(
            f"No existe {_LATENCY_PATH}. La latencia por llamada es un dato MEDIDO y vive "
            f"en un JSON: sin el, cualquier numero que el codigo usara seria inventado."
        )
    raw = json.loads(_LATENCY_PATH.read_text(encoding="utf-8"))
    por_llamada = {k: float(v) for k, v in (raw.get("per_call_seconds") or {}).items()}
    default = raw.get("default")
    if default is None:
        raise ValueError(
            f"{_LATENCY_PATH.name} no declara `default`. Un paradigma sin medicion propia "
            f"necesita con que proyectarse, y elegirlo en el codigo seria inventarlo."
        )
    return por_llamada, float(default)


LATENCY_PER_CALL, LATENCY_DEFAULT = _load_latency()


def projected_seconds(paradigm: str, calls: int | None) -> float | None:
    """Segundos proyectados. `None` si el paradigma no proyecta llamadas.

    AUSENTE NO ES CERO, igual que en la plata: sin proyeccion de llamadas no hay tiempo
    que proyectar, y cobrarle cero lo admitiria en cualquier presupuesto por no saber.
    """
    if calls is None:
        return None
    return calls * LATENCY_PER_CALL.get(paradigm, LATENCY_DEFAULT)


def check_pair(
    model: "Model",
    paradigm: str,
    documents: dict[str, str],
    task: dict[str, Any],
) -> Verdict:
    """Si el par `(modelo, paradigma)` puede correr. Sigue siendo pura aritmetica.

    TRES COTAS, Y SON INDEPENDIENTES. La del paradigma ya existia; las otras dos entran
    con el modelo, y ninguna se deduce de las otras:

      paradigma   lo que `check()` ya decide: llamadas, contexto, cardinalidad
      ventana     techo DURO del modelo. Un presupuesto generoso no agranda una ventana,
                  asi que la cota que manda es la MENOR de las dos
      plata       el presupuesto real. Un par puede entrar en tokens y no en plata, que
                  es justamente lo que el banco no podia ni preguntar

    EL PRESUPUESTO EN PLATA ES OPCIONAL Y AUSENTE NO ES CERO. Sin `budget_usd` declarado
    no se proyecta plata y se dice —el par pasa por las otras dos cotas—. Tratar la
    ausencia como cero declararia infactible a todo, que es la falla opuesta y peor.
    """
    verdict = check(paradigm, documents, task)
    if not verdict.feasible:
        return verdict

    if verdict.projected_tokens is not None and (
        verdict.projected_tokens > model.context_tokens
    ):
        return Verdict(
            False,
            f"{paradigm} proyecta {verdict.projected_tokens} tokens y la ventana de "
            f"{model.name} es {model.context_tokens}: el presupuesto no agranda una "
            f"ventana, asi que manda la cota mas chica",
            projected_calls=verdict.projected_calls,
            projected_tokens=verdict.projected_tokens,
            axis="window",
        )

    # LA COTA DE TIEMPO, y va ANTES que la de plata a proposito: si el request no se
    # puede contestar a tiempo, cuanto sale es una pregunta que ya no importa.
    budget_seconds = task.get("budget_seconds")
    if budget_seconds is not None:
        segundos = projected_seconds(paradigm, verdict.projected_calls)
        if segundos is None:
            return Verdict(
                True,
                f"{paradigm} no proyecta llamadas, asi que la cota de TIEMPO no se evaluo. "
                f"No proyectado no es instantaneo",
                projected_calls=verdict.projected_calls,
                projected_tokens=verdict.projected_tokens,
                axis="latency_unevaluated",
            )
        if segundos > float(budget_seconds):
            return Verdict(
                False,
                f"{paradigm} proyecta ~{segundos:.0f}s ({verdict.projected_calls} "
                f"llamadas) contra un techo de {float(budget_seconds):.0f}s. El tiempo es "
                f"una COTA y no una preferencia: un brazo que gana utilidad y no llega no "
                f"gana",
                projected_calls=verdict.projected_calls,
                projected_tokens=verdict.projected_tokens,
                axis="latency",
            )

    budget_usd = task.get("budget_usd")
    if budget_usd is None:
        return verdict
    if verdict.projected_tokens is None:
        # NO SE PUEDE COBRAR LO QUE NO SE PROYECTO. El par pasa las otras dos cotas y la
        # de plata se declara no evaluada — que no es lo mismo que aprobada, y el motivo
        # queda en el veredicto para que el EXPLAIN no lo lea como un permiso.
        return Verdict(
            True,
            f"{paradigm} no proyecta tokens, asi que la cota de plata NO se evaluo para "
            f"{model.name}. No proyectado no es gratis: el par pasa por las otras dos "
            f"cotas y esta se declara ausente",
            projected_calls=verdict.projected_calls,
            projected_tokens=None,
            axis="money_unevaluated",
        )

    salida = int(verdict.projected_tokens * PROJECTED_COMPLETION_SHARE)
    plata = model.money_for(verdict.projected_tokens - salida, salida)
    if plata > float(budget_usd):
        return Verdict(
            False,
            f"{paradigm} en {model.name} proyecta USD {plata:.4f} contra un presupuesto "
            f"de USD {float(budget_usd):.4f}. Entra en tokens y no en plata: son dos "
            f"cotas distintas y el banco no podia preguntar la segunda",
            projected_calls=verdict.projected_calls,
            projected_tokens=verdict.projected_tokens,
            axis="money",
        )
    return verdict


def admissible_pairs(
    models: "Sequence[Model]",
    paradigms: list[str],
    documents: dict[str, str],
    task: dict[str, Any],
) -> tuple[list[tuple[str, str]], dict[tuple[str, str], Verdict]]:
    """El espacio de decision entero, podado. La accion es el PAR.

    Devuelve `(modelo, paradigma)` porque esa es la accion: elegir `react` sin decir en
    que modelo no es una decision completa, y el registro tiene que poder reproducirla.

    Los pares excluidos vuelven con su motivo, igual que en `admissible()`: un espacio
    que se angosto tiene que decirlo, o el informe se lee como si se hubiera considerado
    entero. Y con dos modelos el espacio es el doble, asi que callar la mitad es peor.
    """
    verdicts = {
        (m.name, p): check_pair(m, p, documents, task)
        for m in models
        for p in paradigms
    }
    return [k for k, v in verdicts.items() if v.feasible], verdicts
