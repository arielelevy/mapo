"""The learned policy bundle (theta), its plasticity, and the determinism ladder.

Three ideas live here, and they are the contribution of the lab.

1. PLASTICITY. Statistics about how each paradigm performs in each feature region are
   updated from outcomes with the Hebbian rule of MAP:

       W <- (1 - lambda) * W + eta * delta

   That is Definition 11.2 of the v1 whitepaper, applied to (region, paradigm) pairs
   instead of (agent, agent) edges. The weights stay bounded and interpretable, which
   is precisely why this substrate was chosen over an embedding: a number in [0,1]
   attached to a named region can be read, audited, argued with and edited by hand.
   An embedding cannot.

2. SELF-OPTIMISATION WITHOUT DRIFT. Learning never happens inside a request. A run
   accumulates episodes; an offline promotion step builds a candidate bundle and
   installs it only if it does not regress against the incumbent on held-out
   episodes. This is Oracle's SQL Plan Management discipline, and it is what keeps
   "self-improving" from meaning "silently different tomorrow".

3. ASSURANCE IS NOT HERE ANY MORE. This module used to define a system-wide
   determinism ladder (D0-D3). That was the wrong shape: it made every request pay for
   the strictest one. Assurance is now a property OF THE REQUEST and lives in
   `assurance.py`; provenance and the belief substrate live in `beliefs.py`. What
   remains here is theta itself and how it learns.
"""

from __future__ import annotations

import hashlib
import json
import random
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Any, Iterable

# Hebbian hyperparameters. Kept at the v1 whitepaper's recommended values so the
# lab and the paper cannot silently disagree: eta = 0.1 sits inside the stability
# bound of Corollary 11.1 with margin.
# --- la guarda que vuelve exigible al dial ------------------------------------------
#
# `theta_may_learn_online` estaba DECLARADO en el perfil de garantia (`assurance.py`) y no
# lo leia nadie. La invariante «nada aprende adentro de un request» se cumplia por
# casualidad —`apply` solo se llama desde el camino offline— y una invariante que se
# cumple por casualidad no es una invariante: es una coincidencia que el proximo cambio
# rompe sin que nada avise.
#
# Ahora se impone. `no_online_learning()` marca el tramo que corre ADENTRO de un request,
# y `apply` levanta si alguien intenta acumular ahi. Por defecto esta permitido, porque el
# camino offline —consolidacion, promocion, los scripts del banco— es donde el aprendizaje
# DEBE ocurrir.
_ONLINE_LEARNING_BLOCKED = ContextVar("mapo_online_learning_blocked", default=False)


class OnlineLearningRefused(RuntimeError):
    """Se intento acumular un episodio adentro de un request."""


@contextmanager
def no_online_learning() -> Iterator[None]:
    """Bloquea el aprendizaje mientras dure el bloque. Reentrante y seguro entre hilos."""
    token = _ONLINE_LEARNING_BLOCKED.set(True)
    try:
        yield
    finally:
        _ONLINE_LEARNING_BLOCKED.reset(token)


# Los pesos se guardan y se firman con esta precision, asi que se APLICAN con ella: lo
# que esta firmado tiene que ser lo que decide.
WEIGHT_PRECISION = 5

# La guarda de promocion decide sobre un INTERVALO, no sobre un punto. Fijos y con
# semilla: la decision de promover tiene que ser tan reproducible como la de rutear.
PROMOTION_RESAMPLES = 1000
PROMOTION_CONFIDENCE = 0.95
PROMOTION_SEED = 11

LEARNING_RATE = 0.1
DECAY = 0.05
WEIGHT_MIN = 0.01
WEIGHT_MAX = 1.0
PRIOR_WEIGHT = 0.5

# A region needs this many episodes before its statistics are allowed to drive a
# specialised route. Below it, confidence is capped and the router abstains.
MIN_EPISODES_FOR_CONFIDENCE = 8



@dataclass
class Stat:
    """Learned statistics for one (region, paradigm) pair."""

    weight: float = PRIOR_WEIGHT
    episodes: int = 0
    utility_sum: float = 0.0
    cost_sum: float = 0.0
    wins: int = 0

    @property
    def mean_utility(self) -> float:
        return self.utility_sum / self.episodes if self.episodes else 0.0

    @property
    def mean_cost(self) -> float:
        return self.cost_sum / self.episodes if self.episodes else 0.0

    @property
    def win_rate(self) -> float:
        return self.wins / self.episodes if self.episodes else 0.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "weight": round(self.weight, WEIGHT_PRECISION),
            "episodes": self.episodes,
            "mean_utility": round(self.mean_utility, 5),
            "mean_cost": round(self.mean_cost, 2),
            "win_rate": round(self.win_rate, 5),
            "utility_sum": self.utility_sum,
            "cost_sum": self.cost_sum,
            "wins": self.wins,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "Stat":
        return cls(
            weight=float(raw["weight"]),
            episodes=int(raw["episodes"]),
            utility_sum=float(raw["utility_sum"]),
            cost_sum=float(raw["cost_sum"]),
            wins=int(raw["wins"]),
        )


@dataclass
class Episode:
    """One observed execution. The unit of learning and of audit."""

    task_id: str
    region: str
    paradigm: str
    utility: float
    cost_tokens: int
    was_best: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "region": self.region,
            "paradigm": self.paradigm,
            "utility": self.utility,
            "cost_tokens": self.cost_tokens,
            "was_best": self.was_best,
        }


@dataclass
class PolicyBundle:
    """theta: an immutable, versioned, signed, human-readable policy.

    Immutability is enforced by convention plus the signature: any in-place edit
    invalidates `signature`, and `verify()` will say so.
    """

    version: int
    created_at: str
    fallback: str
    tau: float
    stats: dict[str, dict[str, Stat]] = field(default_factory=dict)
    # Learned assurance floors per region (paper §6.2), as the Assurance level's int.
    # Stored here rather than beside the policy because it IS policy: it changes what a
    # request is allowed to act on, it must be versioned and signed like theta, and it
    # must not be installable except through the same promotion path.
    #
    # Kept as int so this module stays free of the assurance layer: policy carries the
    # value, the router interprets it. The alternative -- importing Assurance here --
    # would make the thing that is signed depend on the thing that reads it.
    floors: dict[str, int] = field(default_factory=dict)
    # LA SEGUNDA POLITICA: que MODELO conviene para cada paradigma. `P27g`.
    #
    # POR QUE NO VA ADENTRO DE `stats`. `stats` esta indexado por REGION, y `P27e` midio
    # que la region **no explica nada** de la ventaja del modelo: dispersion +0,1667
    # contra una sd interna de 0,5046. Partir por region para elegir modelo pagaria la
    # multiplicacion de bins —que es el mecanismo por el que `P15` fracaso— sin comprar
    # discriminacion. Contado sobre el registro: `modelo x paradigma` son 13 bins con el
    # 100% de los episodios visibles, contra 134 bins con el 90% si se agrega la region.
    #
    # POR QUE ES POLITICA Y NO UN CAMPO MAS. Cambia que se ejecuta, asi que tiene que
    # estar versionada, firmada, y no ser instalable por fuera del camino de promocion —
    # la misma razon que `floors` y `trusts_elicited`.
    #
    # Indexada `paradigma -> modelo -> Stat`, y en ese orden a proposito: la pregunta que
    # el router hace es «para ESTE paradigma, que modelo», no al reves.
    model_stats: dict[str, dict[str, Stat]] = field(default_factory=dict)
    # LA VERSION DE LA SEGUNDA POLITICA, separada de `version`. Dos politicas que se
    # promueven y revierten juntas son una sola con dos nombres: si la de modelo regresa,
    # revertirla no puede obligar a revertir tambien la de paradigmas, que puede estar
    # perfectamente bien. Son promociones independientes o no son dos politicas.
    model_version: int = 0
    # SI LA CREDENCIA ELICITADA SE GANO EL DERECHO A DECIDIR.
    #
    # Va acá por la MISMA razón que `floors`, y no al lado: **cambia lo que un request
    # puede hacer** —con confianza ganada, A2 opera con piso ELICITED; sin ella el piso
    # sube a OBSERVED— así que es política, tiene que estar versionada y firmada, y no
    # debe poder instalarse por fuera del camino de promoción.
    #
    # Antes era un parámetro del router que NINGUNO de los cinco sitios pasaba, así que
    # valía False siempre y **A2 con piso ELICITED era inalcanzable por construcción**: la
    # evidencia para ganarlo se computaba, se persistía, y se tiraba. Como parámetro,
    # además, cada sitio podía olvidarlo; adentro del bundle no hay dónde olvidarlo.
    trusts_elicited: bool = False
    # Promoted acquisition clauses (REC F4), as recorded dicts. Inside the SIGNED
    # payload on purpose: production reads clauses from here and nowhere else, and the
    # only path that appends is certify.install_clause, which refuses drafts, refuses
    # rejected certificates, and refuses certificates that name a different clause.
    clauses: list[dict] = field(default_factory=list)
    # QUE EPISODIOS YA ESTAN ADENTRO. Sin esto, correr la consolidacion dos veces sobre
    # el mismo registro cuenta cada episodio DOS VECES: `candidate` parte de una copia de
    # las estadisticas del incumbente y le reaplica la lista entera, sin saber cuales ya
    # estaban. El peso se mueve el doble hacia su punto fijo, `episodes` se duplica, y la
    # cuenta de evidencia —que es la que decide si una region tiene con que decidir—
    # queda inflada por repetir un proceso, no por haber medido mas.
    #
    # Va ADENTRO del payload firmado: es parte de lo que el bundle afirma sobre si mismo,
    # y un bundle que mintiera sobre que absorbio no seria auditable.
    absorbed: list[str] = field(default_factory=list)
    signature: str = ""
    notes: str = ""

    # -- access ------------------------------------------------------------

    def stat(self, region: str, paradigm: str) -> Stat:
        return self.stats.get(region, {}).get(paradigm, Stat())

    def model_stat(self, paradigm: str, model: str) -> Stat:
        """Lo aprendido sobre ese modelo PARA ese paradigma. `Stat()` vacio si nada."""
        return self.model_stats.get(paradigm, {}).get(model, Stat())

    def best_model(self, paradigm: str, tau: float) -> tuple[str | None, float]:
        """El modelo que conviene para ese paradigma, y por cuanto. `None` si no se sabe.

        DEVUELVE `None` EN TRES CASOS DISTINTOS y ninguno se puede confundir con «el
        barato»: sin datos, con un solo modelo visto, o con margen por debajo de `tau`.
        En los tres, quien llama cae a su regla —el dial y el presupuesto— y el registro
        dice que theta no opino, que es distinto de que haya opinado a favor del barato.

        SOLO CUENTAN LOS MODELOS QUE CRUZAN EL PISO DE EVIDENCIA. Un bin por debajo no es
        menos confiable: es invisible, y promediarlo con uno que si cruza le presta
        confianza que no tiene.
        """
        vistos = {
            m: st for m, st in self.model_stats.get(paradigm, {}).items()
            if st.episodes >= MIN_EPISODES_FOR_CONFIDENCE
        }
        if len(vistos) < 2:
            return None, 0.0
        orden = sorted(vistos.items(), key=lambda kv: -kv[1].mean_utility)
        margen = orden[0][1].mean_utility - orden[1][1].mean_utility
        if margen < tau:
            return None, margen
        return orden[0][0], margen

    def paradigms_for(self, region: str) -> dict[str, Stat]:
        return self.stats.get(region, {})

    def regions(self) -> Iterable[str]:
        return self.stats.keys()

    # -- signature ---------------------------------------------------------

    def _payload(self) -> str:
        body = {
            "version": self.version,
            "created_at": self.created_at,
            "fallback": self.fallback,
            "tau": self.tau,
            "trusts_elicited": self.trusts_elicited,
            "stats": {
                region: {p: s.as_dict() for p, s in sorted(paradigms.items())}
                for region, paradigms in sorted(self.stats.items())
            },
            "floors": dict(sorted(self.floors.items())),
            "model_version": self.model_version,
            "model_stats": {
                par: {m: st.as_dict() for m, st in sorted(modelos.items())}
                for par, modelos in sorted(self.model_stats.items())
            },
            "clauses": sorted(
                (json.dumps(c, sort_keys=True, ensure_ascii=False) for c in self.clauses)
            ),
        }
        return json.dumps(body, sort_keys=True, ensure_ascii=False)

    def sign(self) -> "PolicyBundle":
        self.signature = hashlib.sha256(self._payload().encode("utf-8")).hexdigest()
        return self

    def verify(self) -> bool:
        expected = hashlib.sha256(self._payload().encode("utf-8")).hexdigest()
        return bool(self.signature) and expected == self.signature

    # -- persistence -------------------------------------------------------

    def as_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "created_at": self.created_at,
            "fallback": self.fallback,
            "tau": self.tau,
            "trusts_elicited": self.trusts_elicited,
            "signature": self.signature,
            "notes": self.notes,
            "stats": {
                region: {p: s.as_dict() for p, s in sorted(paradigms.items())}
                for region, paradigms in sorted(self.stats.items())
            },
            "floors": dict(sorted(self.floors.items())),
            "model_version": self.model_version,
            "model_stats": {
                par: {m: st.as_dict() for m, st in sorted(modelos.items())}
                for par, modelos in sorted(self.model_stats.items())
            },
            "model_version": self.model_version,
            "model_stats": {
                par: {m: st.as_dict() for m, st in sorted(modelos.items())}
                for par, modelos in sorted(self.model_stats.items())
            },
            "clauses": list(self.clauses),
        }

    def save(self, directory: Path) -> Path:
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"theta_v{self.version:04d}.json"
        path.write_text(
            json.dumps(self.as_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return path

    @classmethod
    def load(cls, path: Path) -> "PolicyBundle":
        raw = json.loads(path.read_text(encoding="utf-8"))
        bundle = cls(
            version=int(raw["version"]),
            created_at=raw["created_at"],
            fallback=raw["fallback"],
            tau=float(raw["tau"]),
            trusts_elicited=bool(raw.get("trusts_elicited", False)),
            stats={
                region: {p: Stat.from_dict(s) for p, s in paradigms.items()}
                for region, paradigms in raw["stats"].items()
            },
            floors={k: int(v) for k, v in (raw.get("floors") or {}).items()},
            model_version=int(raw.get("model_version") or 0),
            model_stats={
                par: {m: Stat.from_dict(d) for m, d in (modelos or {}).items()}
                for par, modelos in (raw.get("model_stats") or {}).items()
            },
            clauses=list(raw.get("clauses") or []),
            signature=raw.get("signature", ""),
            notes=raw.get("notes", ""),
        )
        if not bundle.verify():
            raise ValueError(
                f"Policy bundle at {path} fails signature verification. "
                "It was edited after signing; refusing to load it silently."
            )
        return bundle

    @classmethod
    def cold_start(cls, fallback: str, tau: float) -> "PolicyBundle":
        """Version 0: no statistics at all.

        A cold bundle routes everything to the fallback, because every region has
        zero episodes and therefore zero confidence. That is the correct behaviour
        for a system that has not learned anything yet, and it means the system is
        never worse than its fallback on day one.
        """
        return cls(
            version=0,
            created_at=datetime.now(timezone.utc).isoformat(),
            fallback=fallback,
            tau=tau,
            stats={},
            notes="cold start: no episodes, abstains everywhere",
        ).sign()

    # -- readability -------------------------------------------------------

    def explain_text(self) -> str:
        """Render theta as something a human (or an auditor) can read."""
        lines = [
            f"theta version {self.version}  signed {self.signature[:16]}",
            f"fallback = {self.fallback}   tau = {self.tau}",
            "",
        ]
        for region in sorted(self.stats):
            lines.append(f"region {region}")
            ranked = sorted(
                self.stats[region].items(),
                key=lambda kv: kv[1].mean_utility,
                reverse=True,
            )
            for paradigm, stat in ranked:
                confident = stat.episodes >= MIN_EPISODES_FOR_CONFIDENCE
                flag = "" if confident else "  (below episode floor -> abstain)"
                lines.append(
                    f"    {paradigm:<14} u={stat.mean_utility:6.3f} "
                    f"w={stat.weight:5.3f} n={stat.episodes:<4d} "
                    f"cost={stat.mean_cost:8.1f}{flag}"
                )
            lines.append("")
        return "\n".join(lines)


class Plasticity:
    """Applies the Hebbian update and builds promoted bundles."""

    @staticmethod
    def delta(episode: Episode) -> float:
        """Reinforcement signal.

        Positive when the paradigm was the best available choice for the task,
        negative otherwise. Being merely adequate is not reinforced: the quantity
        the router needs to estimate is "is this the right paradigm here", not
        "did this paradigm produce something".
        """
        return 0.5 if episode.was_best else -0.3

    @classmethod
    def apply(
        cls, stats: dict[str, dict[str, Stat]], episode: Episode,
        hierarchical: bool = False,
    ) -> None:
        """Accumulate one episode. With `hierarchical`, into its ANCESTOR regions too.

        A region label is a path — `many/oracle/loose/chain` — and its prefixes are
        real, coarser questions about the same request. Indexing only the leaf is what
        made the fourth segment cost all of theta's confidence: every episode landed in
        a bin too small to clear the evidence floor, and the bins that DID have evidence
        (the 3-segment ones) stopped existing the moment the vocabulary grew.

        Off by default. Turning it on changes what a bundle asserts, so it belongs to a
        prediction registered under it — not to a router already being measured.
        """
        if _ONLINE_LEARNING_BLOCKED.get():
            raise OnlineLearningRefused(
                "Se intento acumular un episodio adentro de un request. El aprendizaje es "
                "offline y copy-on-write: aprender en linea haria que dos requests "
                "identicos decidieran distinto, que es exactamente lo que la garantia "
                "«misma base de creencias => misma decision» promete que no pasa."
            )
        for level in cls._levels(episode.region, hierarchical):
            cls._apply_at(stats, level, episode)

    @staticmethod
    def _levels(region: str, hierarchical: bool) -> list[str]:
        if not hierarchical:
            return [region]
        parts = region.split("/")
        return ["/".join(parts[:k]) for k in range(len(parts), 0, -1)]

    @classmethod
    def _apply_at(
        cls, stats: dict[str, dict[str, Stat]], region_key: str, episode: Episode
    ) -> None:
        region = stats.setdefault(region_key, {})
        stat = region.setdefault(episode.paradigm, Stat())

        updated = (1.0 - DECAY) * stat.weight + LEARNING_RATE * cls.delta(episode)
        # SE REDONDEA AL APLICAR, no solo al serializar, y esa es la diferencia que
        # importa: `as_dict` redondeaba a 5 decimales para firmar y para ser legible,
        # mientras la copia en memoria seguia con el float entero. Entonces lo que se
        # FIRMA no era lo que DECIDE, y un bundle recargado desde disco resolvia con un
        # peso distinto del que tenia en el proceso que lo escribio.
        #
        # Ademas `candidate` copia via `from_dict(as_dict())`, asi que cada ciclo de
        # consolidacion perdia precision: dos ciclos sobre el mismo registro daban
        # 0,5713125 y 0,57131. Un desvio chico, pero acumulativo y silencioso, y basta
        # con que cruce un umbral de comparacion para cambiar una decision.
        stat.weight = round(max(WEIGHT_MIN, min(WEIGHT_MAX, updated)), WEIGHT_PRECISION)
        stat.episodes += 1
        stat.utility_sum += episode.utility
        stat.cost_sum += episode.cost_tokens
        stat.wins += 1 if episode.was_best else 0

    @staticmethod
    def episode_key(episode: Episode) -> str:
        """Identidad estable de un episodio, para no absorberlo dos veces.

        `(task_id, region, paradigm)` — la celda. Dos replicas de la misma celda YA
        vienen promediadas en un solo `Episode` antes de llegar aca (`runner.episodes`
        promedia por celda), asi que la celda ES la unidad de evidencia y repetirla es
        siempre doble conteo, nunca dato nuevo.
        """
        return f"{episode.task_id}|{episode.region}|{episode.paradigm}"

    @classmethod
    def candidate(
        cls,
        incumbent: PolicyBundle,
        episodes: list[Episode],
        tau: float,
        notes: str = "",
        hierarchical: bool = False,
    ) -> PolicyBundle:
        """Build the next bundle by replaying episodes onto a copy of the incumbent."""
        stats = {
            region: {p: Stat.from_dict(s.as_dict()) for p, s in paradigms.items()}
            for region, paradigms in incumbent.stats.items()
        }
        # Lo ya absorbido NO se reaplica. Un episodio repetido no es evidencia nueva: es
        # el mismo hecho contado dos veces, y contarlo dos veces mueve el peso y la cuenta
        # de evidencia por repetir un proceso.
        already = set(incumbent.absorbed)
        fresh = [e for e in episodes if cls.episode_key(e) not in already]
        skipped = len(episodes) - len(fresh)
        for episode in fresh:
            cls.apply(stats, episode, hierarchical=hierarchical)
        absorbed = sorted(already | {cls.episode_key(e) for e in fresh})

        return PolicyBundle(
            version=incumbent.version + 1,
            created_at=datetime.now(timezone.utc).isoformat(),
            fallback=incumbent.fallback,
            tau=tau,
            stats=stats,
            # Carried forward untouched: replaying episodes teaches theta about utility,
            # not about which regions refuse elicited evidence. The floors are learned
            # from the belief log, in their own stage, under their own guard.
            floors=dict(incumbent.floors),
            # Misma razón que floors: replayar episodios enseña sobre utilidad, nunca
            # sobre si la credencia elicitada es confiable. Eso se aprende del log de
            # creencias, en su propia etapa y bajo su propia guarda.
            trusts_elicited=incumbent.trusts_elicited,
            # Same reason as floors: replaying episodes teaches theta about utility,
            # never about which acquisitions are authorised. Clauses only change
            # through certify.install_clause.
            clauses=[dict(c) for c in incumbent.clauses],
            absorbed=absorbed,
            notes=notes or (
                f"promoted from v{incumbent.version} on {len(fresh)} new episodes"
                + (f" ({skipped} already absorbed, skipped)" if skipped else "")
            ),
        ).sign()


@dataclass
class PromotionVerdict:
    accepted: bool
    incumbent_value: float
    candidate_value: float
    reason: str
    # El intervalo de la DIFERENCIA, no de cada valor por separado: lo que decide la
    # promocion es si el candidato mejora, y esa es una cantidad pareada. Un intervalo
    # por brazo se solaparia casi siempre y no diria nada sobre la diferencia.
    #
    # `None` significa que no se estimo (bootstrap desactivado), y se distingue de un
    # intervalo que dio cero: son cosas distintas.
    gain_low: float | None = None
    gain_high: float | None = None
    resamples: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "accepted": self.accepted,
            "incumbent_value": round(self.incumbent_value, 5),
            "candidate_value": round(self.candidate_value, 5),
            "delta": round(self.candidate_value - self.incumbent_value, 5),
            "reason": self.reason,
        }


def promote(
    incumbent: PolicyBundle,
    candidate: PolicyBundle,
    holdout: list[Episode],
    router_value_fn,
    min_gain: float = 0.0,
    resamples: int = PROMOTION_RESAMPLES,
    confidence: float = PROMOTION_CONFIDENCE,
    seed: int = PROMOTION_SEED,
) -> PromotionVerdict:
    """Install `candidate` only if it does not regress on held-out episodes.

    `router_value_fn(bundle, holdout) -> float` is injected rather than imported so
    the promotion rule cannot quietly depend on the routing implementation. The
    guard is the reason "self-optimising" is safe to say here: a bundle that would
    make things worse never reaches production, and the verdict is recorded.

    LA GUARDA COMPARABA DOS PUNTOS, y eso no es una guarda: es una moneda con sesgo.
    Sobre un holdout chico, un candidato que gana por 0,001 gana por RUIDO la mitad de
    las veces, y una vez promovido queda como incumbente que el siguiente ciclo tiene que
    superar. El error se hereda.

    Ahora la decision es sobre un INTERVALO de la diferencia, estimado por bootstrap
    pareado sobre los episodios de holdout: se remuestrea el holdout con reposicion, se
    evalua a los dos bundles sobre CADA remuestra —asi el par comparte la muestra, que es
    lo que hace pareada a la comparacion— y se exige que el borde inferior supere
    `min_gain`. Es la misma disciplina que el banco ya aplica a sus propios veredictos.

    Deterministico: semilla fija. Dos corridas sobre el mismo holdout promueven o no
    promueven igual, que es lo que la garantia del producto exige de cualquier decision.
    """
    if not holdout:
        return PromotionVerdict(
            accepted=False,
            incumbent_value=0.0,
            candidate_value=0.0,
            reason="no holdout episodes: refusing to promote unverified policy",
        )

    incumbent_value = router_value_fn(incumbent, holdout)
    candidate_value = router_value_fn(candidate, holdout)
    observed = candidate_value - incumbent_value

    low = high = None
    if resamples > 0 and len(holdout) > 1:
        rng = random.Random(seed)
        n = len(holdout)
        diffs = []
        for _ in range(resamples):
            sample = [holdout[rng.randrange(n)] for _ in range(n)]
            diffs.append(router_value_fn(candidate, sample)
                         - router_value_fn(incumbent, sample))
        diffs.sort()
        alpha = (1.0 - confidence) / 2.0
        low = diffs[min(len(diffs) - 1, int(alpha * len(diffs)))]
        high = diffs[min(len(diffs) - 1, int((1.0 - alpha) * len(diffs)))]

    # El criterio es el BORDE INFERIOR, no el punto. Si no se estimo intervalo —holdout
    # de un solo episodio, o bootstrap apagado— se cae al punto y se DICE en la razon,
    # para que nadie lea una promocion sin intervalo como si lo tuviera.
    decisive = low if low is not None else observed
    if decisive >= min_gain:
        return PromotionVerdict(
            accepted=True,
            incumbent_value=incumbent_value,
            candidate_value=candidate_value,
            gain_low=low, gain_high=high, resamples=resamples if low is not None else 0,
            reason=(
                f"candidate v{candidate.version} gains {observed:+.5f} "
                + (f"[{low:+.5f}, {high:+.5f}] al {confidence:.0%} sobre {resamples} "
                   f"remuestras" if low is not None
                   else "SIN INTERVALO (holdout de 1 episodio o bootstrap apagado)")
            ),
        )

    return PromotionVerdict(
        accepted=False,
        incumbent_value=incumbent_value,
        candidate_value=candidate_value,
        gain_low=low, gain_high=high, resamples=resamples if low is not None else 0,
        reason=(
            f"candidate v{candidate.version} no supera el piso: gana {observed:+.5f} "
            + (f"pero el borde inferior es {low:+.5f} al {confidence:.0%} — la mejora "
               f"no se distingue del ruido del holdout" if low is not None
               else f"y {observed:+.5f} < {min_gain}")
            + f"; se mantiene v{incumbent.version}"
        ),
    )
