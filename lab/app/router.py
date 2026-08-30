"""The control plane: theta as a sensor, beliefs as the substrate, rules as the decider.

This module is the integration point. It owns none of the logic:

    rules.sense        turns a task plus whatever is known into a belief base
    assurance.resolve  picks the operating level, floored by beliefs about the request
    beliefs.Governance evaluates the rule set over the belief base, deterministically
    assurance.restrict narrows the pattern space to what the level admits

and this file only wires them together and turns the resulting action into a concrete
plan. Keeping the policy out of here is the point: an if/elif chain cannot be
serialised, diffed, signed or read by someone who does not read Python.

theta's role has also changed shape. It no longer decides; it ASSERTS. `best_paradigm`
and `theta_margin` enter the belief base as COMPUTED beliefs — facts about the bundle,
each with credence 1.0 — and a rule decides whether the margin is large enough to act
on. That separation is what stopped the earlier confusion between a credence (how sure
we are) and an effect size (how big the thing is).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Sequence

from .assurance import (
    Assurance,
    AssuranceDecision,
    AssuranceProfile,
    resolve,
    restrict,
)
from . import feasibility
from .beliefs import BeliefBase, Provenance, Verdict
from .policy import MIN_EPISODES_FOR_CONFIDENCE, PolicyBundle
from .paradigms import traverses_scope
from .rules import (
    BULK_THRESHOLD,
    ACTION_CASCADE,
    ACTION_DEFER,
    ACTION_GATE,
    ACTION_PROBE,
    ACTION_SPECIALISE,
    BeliefPolicy,
    sense,
    standard_rules,
)



if TYPE_CHECKING:  # el catalogo importa metrics; el router no depende del analisis
    from .models import Model

@dataclass
class Plan:
    """A concrete plan plus the full derivation that produced it."""

    action: str
    paradigm: str
    # EL MODELO ES PARTE DE LA ACCION, no del contexto. Elegir `react` sin decir en que
    # modelo no es una decision completa: el registro no la puede reproducir y el EXPLAIN
    # no la puede defender. Vacio significa «catalogo de un solo modelo», que es el
    # regimen en el que se midio todo hasta hoy — y decirlo vacio es distinto de mentir
    # un nombre por omision.
    model: str = ""
    ladder: list[str] = field(default_factory=list)
    gated: bool = False
    needs_probe: bool = False
    excluded_patterns: list[str] = field(default_factory=list)
    assurance: dict[str, Any] = field(default_factory=dict)
    verdict: dict[str, Any] = field(default_factory=dict)
    theta_version: int = -1
    theta_signature: str = ""
    notes: list[str] = field(default_factory=list)

    def explain(self) -> dict[str, Any]:
        """The audit artifact: everything needed to replay this decision."""
        body = {
            "action": self.action,
            "paradigm": self.paradigm,
            "model": self.model,
            "ladder": self.ladder,
            "gated": self.gated,
            "needs_probe": self.needs_probe,
            "excluded_patterns": self.excluded_patterns,
            "assurance": self.assurance,
            "verdict": self.verdict,
            "theta_version": self.theta_version,
            "theta_signature": self.theta_signature,
            "notes": self.notes,
        }
        body["plan_digest"] = hashlib.sha256(
            json.dumps(body, sort_keys=True, ensure_ascii=False).encode("utf-8")
        ).hexdigest()
        return body


class Router:
    """LA DECISIÓN: qué paradigma corre este request, o si no corre ninguno.

    ES EL PRODUCTO. Todo lo demás de este repo existe para que esta clase pueda decidir con
    evidencia en vez de con una corazonada, y para que la decisión se pueda defender
    después.

    EL ORDEN NO ES ARBITRARIO — cada paso es más barato que el siguiente:

      1. **factibilidad**, que es aritmética y gratis: qué brazos ni siquiera pueden correr
         bajo el presupuesto declarado. Se poda antes de que exista un token
      2. **el dial de garantía**, `max(pedido, piso de creencias, piso aprendido)`: qué
         brazos son admisibles a este nivel de rigor. Sólo puede subir
      3. **θ**, la política aprendida: entre los que quedan, cuál gana en esta región —
         y **sólo si tiene evidencia suficiente**, que es un piso de episodios, no una
         preferencia
      4. **abstención**: si el margen entre el mejor y el segundo no supera `tau`, no se
         elige. Diferir al fallback es una decisión, no una falla

    ABSTENERSE ES LA MITAD DEL PUNTO. Un router obligado a elegir siempre no controla ni
    cuántas veces se equivoca ni cuánto cuesta cada error, y paga por cada desvío. El
    Teorema 1 dice cuándo la selección conviene, y su corolario que la cobertura óptima
    está por debajo de 1 en cuanto alguna pérdida se rutee.

    EL LLM NO DECIDE ACÁ, y es un invariante del producto: emite proposiciones, y esta
    clase las lee como sensor. Jamás maneja flujo de control ni decide un gate. Un router
    que le preguntara al modelo qué hacer sería el zero-shot self-routing que la literatura
    midió en **valor negativo**.

    Y DEVUELVE UN `EXPLAIN`, no sólo un nombre: qué se podó y por qué, qué nivel se exigió y
    cuál de las tres fuentes lo fijó, con qué evidencia se eligió, y si se abstuvo. La
    garantía tiene UNA forma —«misma base de creencias ⟹ misma decisión»— y sin el registro
    de esa base no se puede sostener.
    """

    def __init__(
        self,
        bundle: PolicyBundle,
        paradigm_costs: dict[str, float],
        fallback: str,
        region_backoff: bool = False,
    ) -> None:
        if not bundle.verify():
            raise ValueError("Refusing to route with an unverified policy bundle.")
        self._theta = bundle
        # OFF by default, and deliberately: P16 is running against a frozen verdict
        # script, and changing what the router asserts mid-run would dissolve the one
        # guarantee that makes a preregistration worth anything. It is opt-in until a
        # prediction registered under it says otherwise.
        self._region_backoff = region_backoff
        # Relative priors only: they order a cascade ladder cheapest-first before any
        # episodes exist, and measured mean_cost supersedes them once theta has data.
        self._costs = paradigm_costs
        self._fallback = fallback
        # SI LA CREDENCIA ELICITADA SE GANO EL DERECHO A DECIDIR — un booleano, no un
        # objeto. El router recibia un `Calibration` que NADIE construia: cinco sitios lo
        # instancian y ninguno pasaba el parametro, asi que `trustworthy` era False
        # siempre.
        #
        # Y el efecto no era neutro: sin calibracion el piso sube a OBSERVED en A2+, o sea
        # que **A2 con piso ELICITED era inalcanzable por construccion**. La evidencia para
        # ganarlo se computaba, se persistia, y se tiraba.
        #
        # El booleano y no el objeto porque quien SABE calcularlo es la capa de creencias
        # (`Calibration.is_trustworthy`) y quien lo TIENE guardado es el store. El router
        # no deberia saber como se computa: recibir el objeto lo ataba a una de las dos
        # fuentes y dejaba a la otra sin camino.
        # Se lee del bundle FIRMADO, no de un parametro: un parametro se puede
        # olvidar en un sitio de construccion, y se olvido en los cinco.

    # -- theta as a sensor -------------------------------------------------

    def theta_assertions(
        self, region: str, candidates: list[str]
    ) -> tuple[str | None, float]:
        """What theta asserts about this region: the best paradigm and its margin."""
        best, margin, _ = self.theta_assertions_at(region, candidates)
        return best, margin

    def theta_assertions_at(
        self, region: str, candidates: list[str]
    ) -> tuple[str | None, float, str]:
        """As above, plus WHICH region level actually answered.

        The margin saturates on evidence, so eight episodes is not eighty. A region
        below the episode floor asserts a name with no confidence, which leaves the
        rules no reason to specialise and drops the request to the fallback.

        With `region_backoff`, a region too thin to clear the floor defers to its
        parent — `many/oracle/loose/chain` to `many/oracle/loose`, and so on up — and
        the level that answered is RETURNED rather than hidden. An assertion drawn
        from a coarser bin is a weaker claim than one drawn from the exact bin, and a
        belief that does not say which bin it came from is claiming a specificity it
        does not have.

        Why it exists, measured: adding a fourth segment to the vocabulary split the
        regions below MIN_EPISODES_FOR_CONFIDENCE and theta went from asserting on 12
        of 26 held-out tasks to asserting on none. A more expressive vocabulary costs
        statistical power; backoff keeps the axis where the evidence supports it and
        keeps the power where it does not.
        """
        thin: tuple[str | None, float, str] | None = None

        for level in self._region_levels(region):
            peers = {
                p: s for p, s in self._theta.paradigms_for(level).items()
                if p in candidates
            }
            if len(peers) < 2:
                continue

            best = max(peers, key=lambda p: peers[p].mean_utility)
            stat = peers[best]
            if stat.episodes < MIN_EPISODES_FOR_CONFIDENCE:
                # Remember the most specific thin answer: if no ancestor has enough
                # evidence either, this is still what theta believes — just without
                # the confidence to act on it.
                if thin is None:
                    thin = (best, 0.0, level)
                continue

            runner_up = max(
                (s.mean_utility for p, s in peers.items() if p != best), default=0.0
            )
            gap = stat.mean_utility - runner_up
            if gap <= 0.0:
                if thin is None:
                    thin = (best, 0.0, level)
                continue

            evidence = min(1.0, stat.episodes / (4.0 * MIN_EPISODES_FOR_CONFIDENCE))
            margin = stat.win_rate * evidence * min(1.0, gap * 4.0)
            return best, max(0.0, min(1.0, margin)), level

        return thin if thin is not None else (None, 0.0, "")

    def _region_levels(self, region: str) -> list[str]:
        """The exact region, then its ancestors, most specific first."""
        if not self._region_backoff:
            return [region]
        parts = region.split("/")
        return ["/".join(parts[:k]) for k in range(len(parts), 0, -1)]

    # -- the decision ------------------------------------------------------

    def plan(
        self,
        task: dict[str, Any],
        candidates: list[str],
        region: str,
        documents: dict[str, str] | None = None,
        requested: Assurance = Assurance.STANDARD,
        coupling: float | None = None,
        coupling_provenance: Provenance = Provenance.ELICITED,
        coupling_credence: float = 0.0,
        horizon_unknown: bool | None = None,
        # EL LITERAL, COMO CREENCIA (EP-4). Llega hasta `sense` o no existe: una creencia
        # que el router no propaga es una que ninguna regla puede ver, y este repo ya pagó
        # tres veces por un factor que no llega.
        literal: str | None = None,
        horizon_provenance: Provenance = Provenance.ELICITED,
        horizon_credence: float = 0.0,
        prior_beliefs: list[dict[str, Any]] | None = None,
        models: "Sequence[Model] | None" = None,
    ) -> Plan:
        """`prior_beliefs` continues a recorded history (a first plan's base) so that a
        post-probe replan supersedes rather than forgets: one base, one digest lineage,
        with the ELICITED estimate still on the record under the OBSERVED reading."""
        if not candidates:
            raise ValueError("No candidate paradigms were supplied.")

        # Feasibility prunes first, and for free. A learned policy that spends episodes
        # discovering that map_reduce loses on 500-unit tasks is learning arithmetic the
        # hard way: the cap was computable from the task before any token was spent.
        infeasible: dict[str, str] = {}
        # El espacio de pares que sobrevivio la poda, por paradigma. Vacio cuando el
        # catalogo es de un solo modelo, que es como se midio todo hasta hoy.
        modelos_por_paradigma: dict[str, list[str]] = {}
        if documents is not None:
            if models:
                pares, vp = feasibility.admissible_pairs(
                    models, candidates, documents, task
                )
                for nombre, par in pares:
                    modelos_por_paradigma.setdefault(par, []).append(nombre)
                runnable = [p for p in candidates if p in modelos_por_paradigma]
                # UN PARADIGMA MUERE SOLO SI MUERE EN TODOS LOS MODELOS. Reportar el
                # motivo de uno solo diria «infactible» de algo que corria en el otro,
                # que es narrar la poda al reves.
                infeasible = {
                    p: "; ".join(
                        f"{m}: {v.reason}"
                        for (m, q), v in sorted(vp.items())
                        if q == p and not v.feasible
                    )
                    for p in candidates
                    if p not in modelos_por_paradigma
                }
            else:
                runnable, verdicts = feasibility.admissible(candidates, documents, task)
                infeasible = {
                    p: v.reason for p, v in verdicts.items() if not v.feasible
                }
            if not runnable:
                raise ValueError(
                    "No candidate can run this task: "
                    + "; ".join(f"{p}: {r}" for p, r in sorted(infeasible.items()))
                )
            candidates = runnable

        trustworthy = self._theta.trusts_elicited

        # First pass: a provisional base, only to derive the assurance floor. The
        # floor depends on COMPUTED beliefs about the request, so a cheap policy is
        # sufficient here and the level it yields cannot be gamed by an estimate.
        floor_policy = BeliefPolicy.from_trust(trustworthy, self._theta.tau)
        provisional = sense(task, floor_policy)
        decision: AssuranceDecision = resolve(
            provisional,
            requested=requested,
            calibration_trustworthy=trustworthy,
            # The learned floor rides on the signed bundle, so a request cannot be
            # raised to a stricter level by anything that has not been promoted.
            learned={
                r: Assurance(level) for r, level in self._theta.floors.items()
            },
            region=region,
        )
        profile: AssuranceProfile = decision.profile

        # PRECONDICION DE COBERTURA: demanda x material, y NO es un eje del selector.
        #
        # `O-4b` midio que la demanda **no reordena paradigmas**, asi que usarla como
        # feature de ruteo agregaria bins sin poder de discriminacion — el mecanismo por
        # el que `P15` le costo a theta toda su confianza. Aca no ordena: PODA.
        #
        # La conjuncion es la regla, y ninguna mitad sola dice nada: exigir exhaustividad
        # sobre tres unidades se cumple solo, y material masivo sin demanda de cobertura
        # es el caso normal. Juntas, una respuesta armada desde una muestra no es una
        # respuesta peor — es una afirmacion sobre un dominio que nadie recorrio.
        #
        # Y NO GATEA, que fue el primer intento y estaba mal: gatear ahi mata a `C2`
        # entera, que es exhaustiva y masiva y es justo el caso que los paradigmas existen
        # para resolver. Ademas la regla corre ANTES de ejecutar, asi que no puede saber
        # que se cubrio; lo unico que puede saber de antemano es la ESTRUCTURA.
        cobertura_excluidos: list[str] = []
        cobertura_no_impuesta: str = ""
        if task.get("coverage_demanded") == "exhaustive" and len(
            task.get("unit_ids") or []
        ) > BULK_THRESHOLD:
            recorren = [p for p in candidates if traverses_scope(p)]
            if recorren:
                cobertura_excluidos = [p for p in candidates if p not in recorren]
                candidates = recorren
            else:
                # NINGUNO RECORRE, y lo que se hace con eso DEPENDE DEL DIAL — no es una
                # sola respuesta. Podar a cero seria una abstencion universal; seguir y
                # anotarlo seria contestar igual con una nota que nadie lee.
                #
                # A0/A1: se sigue. Una respuesta desde una muestra es aceptable ahi, y el
                #        registro dice que la precondicion no se pudo imponer.
                # A2/A3: se GATEA. No se puede sostener una afirmacion sobre un dominio
                #        entero sin ninguna topologia capaz de recorrerlo, y a esos
                #        niveles lo que se afirma hay que poder defenderlo. Abstenerse ES
                #        el producto: la curva riesgo-cobertura se reporta, no se esconde.
                cobertura_no_impuesta = (
                    "cobertura exhaustiva exigida sobre material masivo y ningun "
                    "candidato recorre el alcance por construccion: la precondicion NO "
                    "se pudo imponer y la respuesta se arma desde una muestra"
                )

        admissible, excluded = restrict(candidates, profile)
        if not admissible:
            raise ValueError(
                f"Assurance level {decision.level.label} admits none of {candidates}."
            )

        # Second pass: the real base, built under the resolved profile so the sensors
        # and the rules agree on what provenance counts as known.
        # The profile's floor is carried through as-is. Projecting it onto a boolean
        # lost A0: its ASSUMED floor is looser than elicited, and the projection turned
        # it into OBSERVED -- the strictest floor of the four, at the least strict level.
        policy = BeliefPolicy(derived_floor=profile.derived_floor, tau=self._theta.tau)
        best, margin = self.theta_assertions(region, admissible)
        history = (
            BeliefBase.from_dicts(prior_beliefs) if prior_beliefs else None
        )
        base: BeliefBase = sense(
            task,
            policy,
            theta_best=best,
            theta_confidence=margin,
            coupling=coupling,
            coupling_provenance=coupling_provenance,
            coupling_credence=coupling_credence,
            horizon_unknown=horizon_unknown,
            horizon_provenance=horizon_provenance,
            horizon_credence=horizon_credence,
            literal=literal,
            base=history,
        )

        verdict: Verdict = standard_rules(policy).decide(base)
        avisos = []
        if cobertura_excluidos:
            avisos.append(
                f"precondicion de cobertura: {sorted(cobertura_excluidos)} no recorren el "
                f"alcance por construccion y la pregunta exige cobertura total"
            )
        if cobertura_no_impuesta:
            avisos.append(cobertura_no_impuesta)
        return self._materialise(
            verdict, decision, profile, admissible, excluded, best, infeasible,
            region=region, models=models, pairs=modelos_por_paradigma,
            extra_notes=avisos, coverage_unenforceable=bool(cobertura_no_impuesta),
        )

    def _cost_key(self, region: str, paradigm: str) -> float:
        """Lo que ordena la cascada: el costo MEDIDO si hay evidencia, el prior si no.

        Sin evidencia suficiente el prior es lo unico que hay, y se usa. El piso es el
        mismo que gobierna la confianza de theta: por debajo de el, una media es ruido con
        nombre de medicion.
        """
        stat = self._theta.stat(region, paradigm)
        if stat.episodes >= MIN_EPISODES_FOR_CONFIDENCE and stat.mean_cost > 0:
            return stat.mean_cost
        return self._costs.get(paradigm, 1.0)

    def _materialise(
        self,
        verdict: Verdict,
        decision: AssuranceDecision,
        profile: AssuranceProfile,
        admissible: list[str],
        excluded: list[str],
        theta_best: str | None,
        infeasible: dict[str, str] | None = None,
        region: str = "",
        models: "Sequence[Model] | None" = None,
        pairs: dict[str, list[str]] | None = None,
        extra_notes: list[str] | None = None,
        coverage_unenforceable: bool = False,
    ) -> Plan:
        """Turn a rule action into a concrete plan under the assurance profile."""
        notes: list[str] = list(extra_notes or [])
        infeasible = infeasible or {}
        # EL COSTO MEDIDO SUPERSEDE AL PRIOR, y hasta ahora no lo hacia. El comentario del
        # constructor decia «measured mean_cost supersedes them once theta has data» y
        # NADIE lo implementaba: `mean_cost` solo aparecia en `as_dict` y en un formato de
        # impresion. El prior ordenaba la cascada PARA SIEMPRE.
        #
        # Y el prior erra 2-7x (leccion 5.6): `reflection` declara 5,0 y mide 1,6, asi que
        # la cascada nunca lo probaba primero aunque fuera de los mas baratos. La cascada
        # es el mecanismo al que se le acredita el 100% de la brecha, y empezar por el
        # peldaño equivocado es exactamente el costo que la escalera existe para evitar.
        #
        # El costo medido ademas no necesita referencia: son tokens absolutos. El prior
        # esta escalado contra `direct`, que solo es factible donde todo entra en ventana
        # —7 tareas en 1.008 filas— asi que su escala no tiene base en el regimen que el
        # producto apunta.
        cheapest = min(admissible, key=lambda p: self._cost_key(region, p))
        ladder = sorted(admissible, key=lambda p: self._cost_key(region, p))

        fallback = self._fallback
        if fallback not in admissible:
            # The fallback must itself be admissible or there is nothing safe to defer
            # to. Substituting the cheapest is a real narrowing and is recorded.
            notes.append(
                f"fallback {fallback} is not admissible at {decision.level.label}; "
                f"using {cheapest} as the safe default instead"
            )
            fallback = cheapest

        action = verdict.action
        if action == ACTION_CASCADE:
            paradigm, plan_ladder, gated, probe = ladder[0], ladder, False, False
        elif action == ACTION_PROBE:
            paradigm, plan_ladder, gated, probe = cheapest, [cheapest], False, True
        elif action == ACTION_GATE:
            paradigm, plan_ladder, gated, probe = fallback, [fallback], True, False
        elif action == ACTION_SPECIALISE:
            if theta_best and theta_best in admissible:
                paradigm = theta_best
            else:
                paradigm = fallback
                notes.append(
                    "rule chose to specialise but theta named no admissible paradigm; "
                    "deferring to the safe default rather than picking arbitrarily"
                )
            plan_ladder, gated, probe = [paradigm], False, False
        elif action == ACTION_DEFER:
            paradigm, plan_ladder, gated, probe = fallback, [fallback], False, False
        else:
            raise ValueError(f"Unknown rule action: {action}")

        # LA PRECONDICION DE COBERTURA GATEA, y va DESPUES de la regla a proposito: no
        # compite con ella por prioridad, la corrige. Una precondicion que no se puede
        # imponer no cambia CUAL paradigma conviene — cambia si se puede contestar.
        if coverage_unenforceable and decision.level >= Assurance.ACCOUNTABLE:
            gated = True
            notes.append(
                f"GATEADO por {decision.level.label}: la pregunta exige cobertura total "
                f"sobre material masivo y ninguna topologia admisible recorre el alcance "
                f"por construccion. A este nivel lo que se afirma hay que poder "
                f"defenderlo, y una afirmacion sobre un dominio que nadie recorrio no se "
                f"puede. Abstenerse es la respuesta, no un fallo"
            )

        if infeasible:
            notes.append(
                "pruned as infeasible before any selection: "
                + "; ".join(f"{p} ({r})" for p, r in sorted(infeasible.items()))
            )
        if excluded:
            notes.append(
                f"{decision.level.label} excluded {sorted(excluded)} from the plan "
                "space — not because they are worse, but because their control flow "
                "is unbounded or their failure modes are not enumerable"
            )
        if len(plan_ladder) > profile.max_composition_depth:
            plan_ladder = plan_ladder[: profile.max_composition_depth]
            notes.append(
                f"ladder truncated to depth {profile.max_composition_depth} by "
                f"{decision.level.label}"
            )

        # EL MODELO SE ELIGE ULTIMO, y en ese orden por una razon. Primero el dial —una
        # precondicion, no un precio— y despues la plata. Al reves, un descuento
        # suficiente compraria permiso para rutear al mas barato lo que el dial prohibe.
        #
        # Entre los que quedan gana el mas barato, y eso NO es una politica timida: la
        # ventaja del caro depende de la dificultad (X-5e: 0,81x los tokens en `gold_deep`
        # y 1,90x en `gold_v2`), y ese eje es el que la region ya mide. Aprenderlo es de
        # theta, que hoy ordena paradigmas y no pares — asi que el mecanismo esta y el
        # aprendizaje esta registrado, en vez de fingido con una heuristica.
        model_name = ""
        pairs = pairs or {}
        if models and paradigm in pairs:
            permitidos = [
                m for m in models
                if m.name in pairs[paradigm]
                and profile.permits_model(m.capability)
            ]
            if not permitidos:
                raise ValueError(
                    f"{decision.level.label} exige capacidad "
                    f"{profile.min_capability.name if profile.min_capability else 'any'} "
                    f"y ningun modelo factible para {paradigm} la alcanza."
                )
            # LA SEGUNDA POLITICA OPINA ACA, y no antes. El orden es precondicion ->
            # aritmetica -> aprendido, y ninguna de las dos primeras es negociable: theta
            # puede preferir el caro y el dial haberlo prohibido, o el presupuesto haberlo
            # podado, y en los dos casos gana la cota. Un aprendizaje que pudiera levantar
            # una precondicion no seria una preferencia: seria una manera de evadirla.
            #
            # Se consulta por PARADIGMA y no por region, porque ahi vive el efecto (`P27e`:
            # dispersion +0,1667 por region contra +0,7843 por paradigma). Partir por
            # region multiplicaria los bins sin comprar discriminacion — el mecanismo de
            # `P15`, contado en `P27g`.
            aprendido, margen = self._theta.best_model(paradigm, self._theta.tau)
            preferido = next(
                (m for m in permitidos if m.name == aprendido), None
            ) if aprendido else None

            if preferido is not None:
                elegido = preferido
                model_name = elegido.name
                notes.append(
                    f"modelo {elegido.name}: theta lo prefiere para {paradigm} por "
                    f"{margen:.3f} sobre el siguiente, y el dial y el presupuesto lo "
                    f"admiten"
                )
            else:
                elegido = min(permitidos, key=lambda m: (m.capability, m.name))
                model_name = elegido.name
                if aprendido:
                    # THETA OPINO Y NO SE PUDO SEGUIR. Eso no es lo mismo que no haber
                    # opinado, y el registro tiene que distinguirlo: si el caro se poda
                    # sistematicamente por presupuesto, lo aprendido no gobierna nada y
                    # nadie se entera mirando cual corrio.
                    notes.append(
                        f"theta prefiere {aprendido} para {paradigm} (margen {margen:.3f}) "
                        f"y NO es admisible: el dial o el presupuesto lo podaron. Corre "
                        f"{elegido.name}"
                    )
            if preferido is None and len(permitidos) > 1:
                notes.append(
                    f"modelo {elegido.name}: el mas barato de "
                    f"{[m.name for m in permitidos]} que el dial admite"
                )
            elif len(models) > 1:
                notes.append(
                    f"modelo {elegido.name}: unico admisible de "
                    f"{[m.name for m in models]}"
                )

        return Plan(
            action=action,
            paradigm=paradigm,
            model=model_name,
            ladder=plan_ladder,
            gated=gated,
            needs_probe=probe,
            excluded_patterns=sorted(excluded),
            assurance=decision.as_dict(),
            verdict=verdict.as_dict(),
            theta_version=self._theta.version,
            theta_signature=self._theta.signature,
            notes=notes,
        )

    # -- offline valuation -------------------------------------------------

    def value_on(
        self, episodes: list[Any], requested: Assurance = Assurance.STANDARD
    ) -> float:
        """Mean utility this router would have obtained on recorded episodes.

        Used by the promotion guard in `policy.py`. Episodes are grouped by task so the
        chosen paradigm is scored against what it actually achieved on that task rather
        than against a global average.
        """
        by_task: dict[str, dict[str, Any]] = {}
        for episode in episodes:
            by_task.setdefault(episode.task_id, {})[episode.paradigm] = episode

        total = 0.0
        counted = 0
        for observed in by_task.values():
            any_episode = next(iter(observed.values()))
            task = _task_from_region(any_episode.region)
            # The region records what coupling was measured; not passing it made every
            # tight region fall to the probe rule and pick the cheapest candidate, so
            # the guard was valuing a router that is not the one in production.
            coupling, credence = _coupling_from_region(any_episode.region)
            plan = self.plan(
                task=task,
                candidates=sorted(observed),
                region=any_episode.region,
                requested=requested,
                coupling=coupling,
                coupling_provenance=Provenance.OBSERVED,
                coupling_credence=credence,
                # La sonda midio ACOPLAMIENTO. El horizonte no se toca: promoverlo aca
                # seria darle procedencia OBSERVED a algo que nadie observo.
            )
            # An unmeasured pick is still a pick. Skipping the task made `counted`
            # depend on WHICH paradigm each bundle chose, so incumbent and candidate
            # were averaged over different populations and the guard tilted toward
            # whichever bundle picked the rarely-run paradigm. Every task enters the
            # denominator now: an unmeasured pick is scored at what the fallback
            # actually achieved on that task, and at 0.0 when not even that was run.
            if plan.paradigm in observed:
                total += observed[plan.paradigm].utility
            elif self._fallback in observed:
                total += observed[self._fallback].utility
            counted += 1

        return total / counted if counted else 0.0


# Representative mid-bin coupling for each region label. The bins are the router's own
# (features.region), and the midpoint is the honest reconstruction: the label is all the
# episode kept. "unknown" stays unmeasured -- credence 0 -- because inventing a value
# there would assert a belief nothing backs.
_REGION_COUPLING = {"loose": 0.15, "mixed": 0.5, "tight": 0.85}


def _coupling_from_region(region: str) -> tuple[float | None, float]:
    label = region.split("/")[2]
    if label not in _REGION_COUPLING:
        return None, 0.0
    return _REGION_COUPLING[label], 1.0


def _task_from_region(region: str) -> dict[str, Any]:
    """Reconstruct a representative task payload from a region label.

    Lossy by construction: a region is a binning of the feature vector, so this
    recovers a representative point rather than the original task. Adequate for
    offline valuation, which only ever consults the region.
    """
    parts = region.split("/")
    card, oracle = parts[0], parts[1]
    n_units = {"single": 1, "few": 4, "many": 32, "bulk": 128}[card]
    return {
        "unit_ids": [f"u{i}" for i in range(n_units)],
        # La region YA codifica el detector en su segundo segmento, asi que la
        # reconstruccion lo lee de ahi en vez de inferirlo del gold. `oracle` queda por
        # compatibilidad de forma: ningun camino de decision lo consulta.
        "has_oracle": oracle == "oracle",
        "oracle": ["x"] if oracle == "oracle" else [],
        "irreversible": False,
        "shared_writes": False,
        "budget_tokens": 100_000,
    }
