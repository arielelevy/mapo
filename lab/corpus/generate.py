"""Generator for a stratified investigative corpus with exact ground truth.

Why synthetic rather than a public benchmark: the study needs tasks whose STRUCTURE is
known, not just whose answer is known. To measure whether a router can detect that a
task has high cardinality, cardinality has to be a dial. No public benchmark exposes
one, so the corpus is generated with the structural parameters as inputs and the answer
derived from the same generative process.

Three properties this buys, all of which the v1 whitepaper's evaluation lacked:

1. EXACT ground truth. Answers are sets of strings computed from the graph, so grading
   is set F1 with no LLM judge. Judge noise would otherwise be confounded with the
   effect being measured, which is exactly what makes a 2.8pp result unfalsifiable.
2. n and coupling as INDEPENDENT dials, so feature cells can be populated on purpose
   instead of hoped for.
3. Redistributable. Nothing here is client data, so the corpus can ship with the paper.

Public benchmarks still matter for external validity and are loaded separately; this
corpus is for identifying WHICH structural property drives WHICH paradigm's advantage.

Deterministic: seeded throughout. Same seed, same corpus, forever.
"""

from __future__ import annotations

import argparse
import json
import random
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

FIRST = [
    "Marta", "Ignacio", "Lucia", "Tomas", "Valeria", "Ramiro", "Sofia", "Damian",
    "Camila", "Nicolas", "Julieta", "Federico", "Agustina", "Emilio", "Renata",
    "Bruno", "Carolina", "Mateo", "Paula", "Gonzalo", "Micaela", "Esteban",
]
LAST = [
    "Arrieta", "Bengochea", "Cavallero", "Duarte", "Elizalde", "Ferreyra",
    "Goitia", "Herrera", "Ibarrola", "Juarez", "Kessler", "Lombardi",
    "Maidana", "Nardelli", "Ochoa", "Peralta", "Quiroga", "Rinaldi",
]
FIRMS = [
    "Andesmar Holdings", "Boreal Trading", "Cardenal Capital", "Delta Sur SA",
    "Elqui Partners", "Farallon Group", "Gaucho Logistics", "Huemul Invest",
    "Ipanema Freight", "Jujuy Minerals", "Kaipo Servicios", "Lanin Assets",
]
CITIES = [
    "Rosario", "Mendoza", "Posadas", "Salta", "Bariloche", "Cordoba",
    "La Plata", "Neuquen", "Ushuaia", "Corrientes",
]
ROLES = ["director", "signatory", "auditor", "beneficial owner", "custodian"]

# ROLES QUE NUNCA SE ASIGNAN, y por eso existe la lista.
#
# La primera version de B2 buscaba un rol de `ROLES` que nadie tuviera EN ALCANCE. Anda a
# width=12 y desaparece a width=40, porque con suficientes personas los cinco roles quedan
# instanciados. O sea que la celda de ausencia existia solo en el regimen chico — justo el
# que el producto NO apunta, y justo donde la falla que mide es menos grave: afirmar una
# ausencia sobre 12 unidades es menos temerario que sobre 400.
#
# Estos son nombres de rol legitimos del mismo vocabulario —la pregunta es sensata, no
# inventada— que el generador nunca le da a nadie. Asi la ausencia es verdadera POR
# CONSTRUCCION y a cualquier ancho, y para saberlo hay que barrer igual.
ABSENT_ROLES = ["trustee", "nominee shareholder", "compliance officer"]

_NOTE_ID = re.compile(r"note-\d{3}")

# Stamped into every manifest. A seed alone does not pin a corpus: when the generation
# ALGORITHM changes, the same seed yields a different world. Name assignment moved from
# rejection sampling to enumeration (the sampler could not exceed 396 people and hung
# instead of failing), so corpora built before that are not reproducible from this file
# and results measured on them must not be pooled with results measured on v2 corpora.
GENERATOR_VERSION = 2

# --- Hardening: surface variation and near-miss distractors -------------------
#
# Five phrasings of the same assertion. A fixed template made every fact findable with
# one keyword search, which neutralised the cardinality dial: 48 units cost the same as
# 4 because nobody had to read them.
ASSERTION_TEMPLATES = (
    "{name}, based in {city}, acts as {role} for {firm}.",
    "{name} serves as {role} at {firm}; domiciled in {city}.",
    "Appointed {role} of {firm}: {name}, resident of {city}.",
    "{name} ({city}) holds the position of {role} within {firm}.",
    "In the capacity of {role} for {firm}, {name} operates from {city}.",
)

# Lines that MATCH the keyword and are the wrong answer. These are the discriminating
# pressure: a search now returns hits that each have to be verified.
NEAR_MISS_TEMPLATES = (
    "{other} reports to the {role} of {firm}.",
    "{other} was formerly {role} of {firm}; the position was vacated.",
    "{other} is not recorded as {role} for any entity.",
    "Correspondence regarding the {role} appointment was filed in {city}.",
    "A prior filing listed no {role} for the {city} branch.",
)

# Padding is the load-bearing hardening, not decoration. Measured on the first corpus:
# 60 units totalled 4.2k tokens, so `direct` stuffed the entire corpus into one prompt
# for 4.3k tokens and answered correctly. While everything fits comfortably in one
# prompt, read-everything is the optimal paradigm and no amount of lexical hardening
# changes that — removing searchability punishes the paradigm that SEARCHES and leaves
# the one that reads untouched.
#
# Target: ~600-900 tokens per unit, so the winner FLIPS across the width dial. At width
# 4 (~3k tokens) reading everything stays cheapest; at width 48 (~40k) it costs an order
# of magnitude more than searching. A dial that does not change the answer is not a dial.
PADDING = (
    "Retention of supporting schedules follows the standard engagement calendar. "
    "Working papers for the period were indexed on receipt and cross-referenced to the "
    "prior-year file, with variances above the reporting threshold annotated in the "
    "margin sheets. The engagement team confirmed that no schedule was carried forward "
    "without a signed reconciliation, and that all supporting evidence was filed under "
    "the general correspondence series rather than the restricted annex.",

    "No deviation from the agreed scope was recorded during the period under review. "
    "Scope confirmations were obtained at the planning meeting and reconfirmed at the "
    "interim review, with the standing instruction that any extension be documented in "
    "writing before fieldwork commenced. The engagement letter remained unamended, and "
    "the fee basis was unchanged from the preceding period.",

    "Correspondence handling followed the routing matrix in force for the period. "
    "Inbound items were logged on the day of receipt, assigned a reference in the "
    "sequential register, and acknowledged within the service standard. Items requiring "
    "specialist review were referred without delay; none of the items referred during "
    "the period resulted in a change to the reported position.",

    "The reconciliation was signed off without exception at period end. Balances were "
    "agreed to the underlying ledgers, with immaterial timing differences carried in the "
    "suspense schedule and cleared in the following period. Sample selections were made "
    "on the standard basis and the results extrapolated in accordance with the firm "
    "methodology, producing no projected misstatement above the threshold.",

    "Ancillary documentation remains on file with the engagement partner. This comprises "
    "the planning memorandum, the risk assessment summary, the independence "
    "confirmations obtained from each team member, and the completion checklist. All "
    "items were dated within the period and none required subsequent amendment or "
    "re-issue after the reporting date.",

    "Periodic monitoring continued in line with the approved plan. Coverage was "
    "maintained across the reporting cycle with no gaps recorded, and the monitoring "
    "log was reviewed at each interval by a person independent of the preparation. "
    "Exceptions identified in earlier periods have been closed, and no new exception "
    "was raised during the period covered by this memorandum.",
)


# Anchored so amendment units (amend-*) can never be mistaken for base memos.
_MEMO_ID = re.compile(r"memo-\d{3}")


@dataclass
class Person:
    name: str
    city: str
    firm: str
    role: str
    account: str
    supervisor: str | None = None


@dataclass
class Task:
    task_id: str
    cell: str
    question: str
    oracle: list[str]
    unit_ids: list[str]
    budget_tokens: int
    # The units that actually bear the answer. Everything else in `unit_ids` is a
    # distractor for this question. Declared so retrieval quality can be simulated at a
    # measured recall and precision rather than asserted.
    relevant_units: list[str] = field(default_factory=list)
    # Whether a cheap RUNTIME detector exists — NOT whether the bench holds gold. The
    # two were the same field carrying the same value (True, always), which made them
    # the same concept, and the conflation is measurable: with a detector on every task
    # the cascade rule fires at priority 90 and the selection rule at 70 is never even
    # evaluated. The bench could not measure selection because being gradeable implied
    # having a detector. `oracle` is untouched: it is the answer key, and it grades.
    has_oracle: bool = True
    irreversible: bool = False
    shared_writes: bool = False
    # Recorded so the study can check the router's inference against the truth. NEVER
    # fed to the router: it is the answer key for the feature extractor itself.
    truth_n_units: int = 0
    truth_coupling: float = 0.0
    truth_horizon_unknown: bool = False
    # Demandas TIPADAS de la pregunta, declaradas por celda (ver REQUEST_DEMANDS). No se
    # infieren de la prosa del enunciado. Son dos porque C5 y C8 son singulares y aun asi
    # exigen cobertura total: la cardinalidad de la respuesta no implica la cobertura.
    # Obligaciones que la pregunta EXIGE, de vocabulario cerrado (`contracts.OBLIGATIONS`).
    # Declaradas por celda, jamas inferidas de la prosa del enunciado: inferir "esta
    # pregunta niega algo" del texto es exactamente el parseo de prosa que este banco no
    # acepta como sensor.
    obligations: list[str] = field(default_factory=list)
    answer_cardinality: str = ""
    coverage_demanded: str = ""
    # De donde sale el dominio contra el que se verificaria la completitud. Decide si
    # `C-COMPLETE` es APLICABLE, que no es lo mismo que si la cobertura se exige.
    completeness_domain: str = ""
    # Las claves del dominio, cuando la pregunta lo enumera. Vacio en toda otra celda —
    # NO se infiere del enunciado: se registra al construir la tarea, que es donde se sabe.
    domain_keys: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class Generator:
    def __init__(self, seed: int) -> None:
        self._rng = random.Random(seed)
        self.people: list[Person] = []
        self.documents: dict[str, str] = {}

    # -- world -------------------------------------------------------------

    def build_world(self, n_people: int) -> None:
        """Enumerate names rather than sample them by rejection.

        The pool is 22 first names by 18 surnames = 396 unique combinations, and the
        previous version drew from it by rejection sampling into a set. Asking for 400
        people therefore did not fail — it spun forever, because the 397th unique name
        does not exist. Enumeration is deterministic, exhausts the pool in order, and
        appends a discriminator past it, so the generator scales to any size and the
        limit is visible in the names instead of being a hang.
        """
        names: list[str] = []
        pool = len(FIRST) * len(LAST)
        for i in range(n_people):
            base = f"{FIRST[i % len(FIRST)]} {LAST[(i // len(FIRST)) % len(LAST)]}"
            names.append(base if i < pool else f"{base} {i // pool + 1}")

        for name in names:
            self.people.append(
                Person(
                    name=name,
                    city=self._rng.choice(CITIES),
                    firm=self._rng.choice(FIRMS),
                    role=self._rng.choice(ROLES),
                    account=f"AR{self._rng.randint(10**9, 10**10 - 1)}",
                )
            )

        # A supervision FOREST, not a single funnel. Drawing every supervisor from a
        # lower index — as an earlier version did — makes every chain flow toward
        # person[0], so following the reporting line upward from anywhere converges to
        # the same terminal and the multi-hop question becomes guessable: three C3
        # tasks all had the identical answer. Blocks give several independent roots.
        block = max(4, n_people // 6)
        for i, person in enumerate(self.people):
            root = (i // block) * block
            if i > root and self._rng.random() < 0.75:
                person.supervisor = self.people[self._rng.randrange(root, i)].name

    def build_documents(self) -> None:
        """One memo per person, plus distractor memos that mention nobody relevant."""
        for i, p in enumerate(self.people):
            unit_id = f"memo-{i:03d}"
            lines = [
                f"INTERNAL MEMORANDUM {unit_id.upper()}",
                f"Subject: engagement review, {p.firm}",
                "",
                f"{p.name}, based in {p.city}, acts as {p.role} for {p.firm}.",
                f"Settlement account on file: {p.account}.",
            ]
            if p.supervisor:
                lines.append(f"Reports to {p.supervisor} for all authorisations.")
            lines.append("")
            lines.append(
                f"Routine correspondence was logged in {self._rng.choice(CITIES)} "
                f"and requires no escalation at this time."
            )
            self.documents[unit_id] = "\n".join(lines)

        for j in range(max(3, len(self.people) // 3)):
            unit_id = f"note-{j:03d}"
            self.documents[unit_id] = "\n".join([
                f"FILE NOTE {unit_id.upper()}",
                "",
                f"Quarterly reconciliation for the {self._rng.choice(CITIES)} branch "
                f"closed without exception. Archived under general correspondence.",
                "No individual engagement is referenced in this note.",
            ])


    def _assert_line(self, p: "Person", index: int) -> str:
        """One assertion, phrased differently per person."""
        template = ASSERTION_TEMPLATES[index % len(ASSERTION_TEMPLATES)]
        return template.format(name=p.name, city=p.city, role=p.role, firm=p.firm)

    def _near_miss_lines(self, p: "Person", count: int) -> list[str]:
        """Lines that keyword-match p's role or city but assert nothing about anyone."""
        lines = []
        for _ in range(count):
            template = self._rng.choice(NEAR_MISS_TEMPLATES)
            other = self._rng.choice(self.people).name
            # A near miss must never name the person it could be confused with, or it
            # stops being a near miss and becomes a contradiction.
            while other == p.name:
                other = self._rng.choice(self.people).name
            lines.append(template.format(
                other=other,
                role=self._rng.choice(ROLES),
                firm=self._rng.choice(FIRMS),
                city=self._rng.choice(CITIES),
            ))
        return lines

    def build_documents_hard(self) -> None:
        """Memos with varied phrasing, embedded near misses and padding."""
        for i, p in enumerate(self.people):
            unit_id = f"memo-{i:03d}"
            lines = [
                f"INTERNAL MEMORANDUM {unit_id.upper()}",
                f"Subject: engagement review, {p.firm}",
                "",
                self._assert_line(p, i),
                f"Settlement account on file: {p.account}.",
            ]
            if p.supervisor:
                lines.append(f"Reports to {p.supervisor} for all authorisations.")
            lines.append("")
            lines.extend(self._near_miss_lines(p, self._rng.randint(1, 2)))
            lines.append("")
            lines.extend(self._rng.sample(PADDING, 2))
            self.documents[unit_id] = "\n".join(lines)

        # Standalone near-miss units: they match a search and contain no valid answer at
        # all. These punish search-and-stop hardest, because the hit is pure cost.
        for j in range(max(4, len(self.people) // 3)):
            unit_id = f"note-{j:03d}"
            decoy = self._rng.choice(self.people)
            lines = [
                f"FILE NOTE {unit_id.upper()}",
                "",
            ]
            lines.extend(self._near_miss_lines(decoy, 2))
            lines.append("")
            lines.extend(self._rng.sample(PADDING, 2))
            self.documents[unit_id] = "\n".join(lines)

    def inflate_units(self, target_tokens: int) -> None:
        """Pad every unit toward a target size, deterministically.

        The padding is filler by construction — it must not change any answer, so it is
        drawn from the same neutral boilerplate and never mentions a person, role, city
        or account. What it changes is whether the corpus fits in a prompt, which is the
        only variable being manipulated here.
        """
        target_chars = target_tokens * 4
        for unit_id, text in list(self.documents.items()):
            if len(text) >= target_chars:
                continue
            filler: list[str] = [text]
            size = len(text)
            index = 0
            while size < target_chars:
                paragraph = PADDING[index % len(PADDING)]
                # A section marker keeps the filler plausible as document structure
                # rather than reading as a repeated block.
                filler.append(f"[continuation {index + 1}] {paragraph}")
                size += len(paragraph) + 20
                index += 1
            self.documents[unit_id] = "\n\n".join(filler)

    # -- tasks -------------------------------------------------------------

    def _memo_ids(self) -> list[str]:
        """Base memos only, in numeric order.

        The regex anchor matters. Amendment units are named `amend-*` precisely so
        they can never enter this set: an earlier version named them `memo-NNN-alt`,
        which made them match this prefix, so every task generated after the first
        C5 task had its unit list shifted out of alignment with `self.people[:width]`
        and its oracle silently became wrong.
        """
        return sorted(
            u for u in self.documents
            if _MEMO_ID.fullmatch(u)
        )

    def _note_ids(self) -> list[str]:
        return sorted(u for u in self.documents if _NOTE_ID.fullmatch(u))

    def _with_distractors(self, memos: list[str], every: int = 4) -> list[str]:
        """Interleave irrelevant units among the relevant ones.

        Without this, no task ever contains a unit that contributes nothing, so
        nothing measures precision against noise — and that is the comparison the
        corpus most needs. A paradigm that processes every unit regardless (map-reduce)
        should pay for the distractors; one that searches first (ReAct) should not.
        """
        notes = self._note_ids()
        if not notes:
            return memos
        mixed: list[str] = []
        n = 0
        for i, memo in enumerate(memos):
            mixed.append(memo)
            if (i + 1) % every == 0 and n < len(notes):
                mixed.append(notes[n])
                n += 1
        return mixed

    def task_c1_single_fact(self, idx: int) -> Task:
        """n=1, oracle, no coupling. Direct/CoT should win; ReAct should overpay."""
        person = self.people[idx % len(self.people)]
        unit_id = f"memo-{idx % len(self.people):03d}"
        return Task(
            task_id=f"c1-{idx:03d}",
            cell="C1_single_verifiable",
            question=f"What is the settlement account on file for {person.name}?",
            oracle=[person.account],
            unit_ids=[unit_id],
            relevant_units=[unit_id],
            budget_tokens=8_000,
            truth_n_units=1,
            truth_coupling=0.0,
        )

    def task_c9_roster(self, idx: int, width: int) -> Task:
        """Dominio ENUNCIADO: las personas que la pregunta nombra.

        POR QUE EXISTE (leccion 8.7). Es la unica celda donde `C-COMPLETE` es aplicable
        sin reemplazar al paradigma. En C2 enumerar el dominio es la extraccion misma; en
        C4/C5/C8 el dominio barato son las unidades, y la fraccion leida no predice
        correccion. Aca el dominio son cinco nombres dados: `COMPUTED`, enumerable, y una
        respuesta a la que le falta uno esta incompleta de una forma que el codigo VE.

        Y la falla es la cara: contestar cuatro de cinco produce una respuesta que parece
        bien formada, cada item citado es real, y ninguna metrica de anclaje la toca.
        """
        # DOS RESTRICCIONES, y las dos cambian lo que la celda mide.
        #
        # (a) El roster sale de `people[:width]`, no del padron entero: si nombrara a
        #     alguien cuyo memo no esta en alcance, la respuesta correcta seria "no esta"
        #     y la celda pasaria a medir ausencia — que es otro eje (O-2), no completitud.
        # (b) Se toman con PASO, no consecutivos. Indices seguidos son memos adyacentes, y
        #     un bloque contiguo vuelve barata la recuperacion por vecindad en vez de por
        #     nombre: la celda mediria localidad del indice y no cobertura del dominio.
        pool = self.people[:width]
        size = min(5, len(pool))
        stride = 7 if len(pool) > 7 else 1
        chosen: list[Person] = []
        k = 0
        while len(chosen) < size and k < len(pool) * 2:
            person = pool[(idx + k * stride) % len(pool)]
            if person.name not in {c.name for c in chosen}:
                chosen.append(person)
            k += 1
        roster = chosen
        names = [p.name for p in roster]
        units = self._with_distractors(self._memo_ids()[:width])
        relevant = [
            f"memo-{i:03d}" for i, p in enumerate(self.people[:width])
            if p.name in set(names)
        ]
        return Task(
            task_id=f"c9-{idx:03d}-w{width}",
            cell="C9_declared_roster",
            question=(
                "For each of the following individuals, report the settlement account "
                "on file: " + ", ".join(names) + ". "
                "Return one account per individual, in any order."
            ),
            # `sorted(set(...))` y no una lista: el corrector es F1 de conjuntos. Si dos
            # del roster compartieran cuenta el dominio y el oraculo tendrian tamanos
            # distintos, y el verificador lo rechaza en vez de dejarlo pasar.
            oracle=sorted({p.account for p in roster}),
            unit_ids=units,
            relevant_units=relevant,
            budget_tokens=40_000,
            truth_n_units=len(units),
            truth_coupling=0.0,
            domain_keys=names,
        )

    def task_b2_absence(self, idx: int, width: int) -> Task:
        """Ausencia: la respuesta correcta es que NO esta. `O-2`.

        POR QUE ESTA CELDA ES LA DE PEOR RELACION DAÑO/ATENCION de todo el banco. Una
        ausencia afirmada desde una muestra produce una respuesta que PARECE NORMAL: «no
        hay ningun memo sobre X» se lee igual de segura leyendo 3 unidades que leyendo 40.
        Un error de presencia se cae solo —el lector busca el dato y no esta— y uno de
        ausencia no deja rastro, porque no hay nada que buscar.

        LA CONSTRUCCION. Se pregunta por un rol de `ABSENT_ROLES`: nombres legitimos del
        mismo vocabulario que el generador NUNCA le asigna a nadie. La pregunta es sensata
        —el rol es real— y la respuesta correcta es vacia A CUALQUIER ANCHO.

        La primera version buscaba un rol de `ROLES` que nadie tuviera en alcance, y eso
        anda a width=12 y desaparece a width=40: con suficientes personas los cinco quedan
        instanciados. O sea que la celda existia solo en el regimen chico, que es el que el
        producto NO apunta y donde la falla es menos grave — afirmar una ausencia sobre 12
        unidades es menos temerario que sobre 400.

        Y EL ORACULO ES LA LISTA VACIA, que no es lo mismo que no tener oraculo. Una tarea
        cuya respuesta correcta es el conjunto vacio SI tiene con que corregirse, y por eso
        `has_oracle` se declara y no se deriva de `bool(oracle)`: derivarlo mal-etiquetaria
        como no verificables justo a estas.
        """
        # El rol sale de `ABSENT_ROLES`, que el generador NUNCA asigna. Asi la ausencia es
        # verdadera a cualquier ancho, y no solo donde el sorteo dejo un rol sin usar.
        ausente = ABSENT_ROLES[idx % len(ABSENT_ROLES)]
        # LA GUARDA IGUAL SE QUEDA, y no es defensiva: si alguien agregara un rol de
        # `ABSENT_ROLES` al pool de asignacion, la celda pasaria a medir presencia bajo la
        # etiqueta de ausencia y NADA lo diria. Es barata y cubre un cambio a dos archivos
        # de distancia.
        instanciados = {p.role for p in self.people}
        if ausente in instanciados:
            raise ValueError(
                f"{ausente!r} esta en ABSENT_ROLES y ademas asignado a alguien. La celda "
                f"B2 mediria presencia con nombre de ausencia, asi que se niega."
            )
        units = self._with_distractors(self._memo_ids()[:width])
        return Task(
            task_id=f"b2-{idx:03d}-w{width}",
            cell="B2_absence",
            question=(
                f"Which individuals hold the role of {ausente}? "
                f"If none do, say so explicitly."
            ),
            oracle=[],
            unit_ids=units,
            # NINGUNA unidad lleva la respuesta, y eso es exacto: la respuesta correcta no
            # esta en ninguna parte. Declarar unidades relevantes seria mentirle al
            # simulador de recuperacion sobre lo que hay que encontrar.
            relevant_units=[],
            budget_tokens=40_000,
            truth_n_units=len(units),
            truth_coupling=0.0,
            has_oracle=True,
            obligations=["absence"],
        )

    def task_d1_presupposition(self, idx: int, width: int) -> Task:
        """La pregunta da algo por sentado que el material no sostiene. `O-3`.

        «Cuando renuncio X?» da por sentado que renuncio. Si no renuncio, TODA respuesta a
        la pregunta como esta formulada es falsa, INCLUIDA «no consta la fecha»: declinar
        el dato ratifica la premisa igual que darlo.

        POR QUE ES EL MAS FACIL DE LA FAMILIA. Una presuposicion ya tiene forma de
        proposicion, asi que el mecanismo para verificarla existe entero —`BeliefBase` con
        su piso de procedencia—. Lo unico que faltaba era extraerla, y extraerla es el
        patron del handoff: el agente la PROPONE tipada y el codigo la AUTORIZA por
        presencia literal en el material.

        EL ORACULO ES EL RECHAZO DE LA PREMISA, no un dato. Por eso la respuesta correcta
        nombra la premisa: lo que se corrige es que la haya identificado, no que conteste.
        """
        persona = self.people[idx % max(1, min(len(self.people), width))]
        units = self._with_distractors(self._memo_ids()[:width])
        return Task(
            task_id=f"d1-{idx:03d}-w{width}",
            cell="D1_presupposition",
            question=(
                f"On what date did {persona.name} transfer the settlement account to "
                f"the successor account? Report the date."
            ),
            # La transferencia NUNCA ocurre en este corpus: el memo declara una cuenta y
            # no registra transferencias. Asi que la premisa es falsa por construccion, no
            # por casualidad de generacion — que es lo que la hace medible.
            oracle=["no transfer is recorded"],
            unit_ids=units,
            relevant_units=[f"memo-{idx % max(1, width):03d}"],
            budget_tokens=40_000,
            truth_n_units=len(units),
            truth_coupling=0.0,
            has_oracle=True,
            obligations=["presupposition"],
        )

    def task_c2_bulk_extraction(self, idx: int, width: int) -> Task:
        """High n, independent, oracle. Map-reduce should win; ReAct should miss items."""
        target_role = ROLES[idx % len(ROLES)]
        answers = sorted({
            p.name
            for i, p in enumerate(self.people[:width])
            if p.role == target_role
        })
        units = self._with_distractors(self._memo_ids()[:width])
        relevant = [
            f"memo-{i:03d}" for i, p in enumerate(self.people[:width])
            if p.role == target_role
        ]
        return Task(
            task_id=f"c2-{idx:03d}-w{width}",
            cell="C2_bulk_independent",
            question=(
                f"Across all supplied units, list every individual whose role is "
                f"'{target_role}'. Return names only."
            ),
            oracle=answers,
            unit_ids=units,
            relevant_units=relevant,
            budget_tokens=60_000,
            truth_n_units=len(units),
            truth_coupling=0.0,
        )

    def task_c3_multi_hop(self, idx: int, hops: int) -> Task:
        """Chained dependency. Plan-execute / SEQ should win over map-reduce."""
        by_name = {p.name: p for p in self.people}

        def walk(start: "Person", steps: int) -> list["Person"]:
            chain = [start]
            current = start
            for _ in range(steps):
                nxt = by_name.get(current.supervisor or "")
                if nxt is None:
                    break
                chain.append(nxt)
                current = nxt
            return chain

        # Only starts that actually admit `hops` steps, and then one start per distinct
        # terminal. Without the distinctness filter the answer repeats across tasks and
        # the cell can be scored by guessing.
        viable = [
            walk(p, hops) for p in self.people
            if p.supervisor and len(walk(p, hops)) == hops + 1
        ]
        if not viable:
            raise ValueError(
                f"No chain of {hops} hop(s) exists; raise --people or the link rate."
            )
        seen: set[str] = set()
        distinct: list[list["Person"]] = []
        for chain in viable:
            terminal = chain[-1].name
            if terminal not in seen:
                seen.add(terminal)
                distinct.append(chain)
        chain = distinct[idx % len(distinct)]
        start = chain[0]

        terminal = chain[-1]
        # The oracle is the terminal person's ACCOUNT, not their city. Cities repeat
        # across the population, and because the supervision graph converges, every
        # city answer collapsed to the same value — three tasks all answering
        # "Cordoba", so guessing once scored 3/3 without reading anything. An account
        # number is unique per person, so the answer can only come from completing the
        # hop.
        return Task(
            task_id=f"c3-{idx:03d}-h{len(chain) - 1}",
            cell="C3_coupled_chain",
            question=(
                f"Starting from {start.name}, follow the reporting line upward "
                f"{len(chain) - 1} step(s). Report the settlement account on file for "
                f"that final person."
            ),
            oracle=[terminal.account],
            unit_ids=self._memo_ids(),
            relevant_units=[
                f"memo-{i:03d}"
                for i, p in enumerate(self.people)
                if p.name in {c.name for c in chain}
            ],
            budget_tokens=40_000,
            truth_n_units=len(self._memo_ids()),
            # Each hop is only discoverable after the previous one, which is coupling
            # in its purest form.
            truth_coupling=min(1.0, 0.4 + 0.2 * (len(chain) - 1)),
        )

    def task_c4_aggregate(self, idx: int, width: int) -> Task:
        """Counting across units. Needs full coverage, so a barrier is justified."""
        city = CITIES[idx % len(CITIES)]
        count = sum(1 for p in self.people[:width] if p.city == city)
        units = self._with_distractors(self._memo_ids()[:width])
        relevant = [
            f"memo-{i:03d}" for i, p in enumerate(self.people[:width]) if p.city == city
        ]
        return Task(
            task_id=f"c4-{idx:03d}-w{width}",
            cell="C4_aggregate_full_coverage",
            question=(
                f"How many individuals across the supplied units are based in {city}? "
                f"Answer with the number only."
            ),
            oracle=[str(count)],
            unit_ids=units,
            relevant_units=relevant,
            budget_tokens=60_000,
            truth_n_units=len(units),
            truth_coupling=0.2,
        )

    def task_c5_contradiction(self, idx: int, width: int) -> Task:
        """Unknown horizon, no cheap oracle in the general case. Reflection/loop territory."""
        units = self._memo_ids()[:width]
        # `(idx * 7 + width) % width` collapses to 0 for every width when idx == 0,
        # so the earlier version planted person[0] in all three widths of c5-000.
        # Offsetting by idx first, then mixing the width, actually varies both.
        planted_index = (idx * 13 + width // 4 + 1) % max(1, width)
        planted = self.people[planted_index]
        conflicting = f"amend-{planted_index:03d}-w{width:03d}"
        alt_city = next(c for c in CITIES if c != planted.city)
        # The amendment names the ACCOUNT, never the person, and avoids the word
        # "Correction". Previously exactly one unit contained that word, so a single
        # keyword search solved the task at any width: the cardinality dial was fake
        # and the "unknown horizon" was one step. Now the horizon is genuinely two —
        # find the restated city, then find who holds that account.
        self.documents[conflicting] = "\n".join([
            f"SUPPLEMENTARY FILING {conflicting.upper()}",
            "",
            f"The domicile of record associated with settlement account "
            f"{planted.account} is {alt_city}.",
            "This filing supersedes any earlier domicile on record for that account.",
            "No other engagement details are restated.",
        ])
        return Task(
            task_id=f"c5-{idx:03d}-w{width}",
            cell="C5_unknown_horizon",
            question=(
                "Exactly one individual has contradictory city information across the "
                "supplied units. Name that individual."
            ),
            oracle=[planted.name],
            unit_ids=units + [conflicting],
            relevant_units=[conflicting, f"memo-{planted_index:03d}"],
            budget_tokens=60_000,
            truth_n_units=len(units) + 1,
            truth_coupling=0.7,
            truth_horizon_unknown=True,
        )

    def task_c8_currency(self, idx: int, width: int) -> Task:
        """Resolver una supersesion declarada. MISMO material que C5, demanda opuesta.

        C5 pregunta QUIEN tiene informacion contradictoria: pone a prueba la DETECCION
        del conflicto. Esta pregunta cual es el domicilio VIGENTE de una cuenta: pone a
        prueba la RESOLUCION del conflicto por precedencia. Los mismos dos documentos
        sostienen las dos preguntas y exigen cosas distintas — que es exactamente lo que
        `ONTOLOGIA_PREGUNTAS.es.md` sostiene sobre la demanda: no la determina el
        material.

        POR QUE ESTA CELDA FALTABA Y POR QUE ES BARATA. Las enmiendas ya existian en el
        corpus desde C5, con la precedencia ESCRITA —«this filing supersedes any earlier
        domicile on record for that account»— y ninguna pregunta las interrogaba.
        Medido el 2026-08-28: cero preguntas sobre domicilio, cero golds en un valor
        enmendado. El material estaba y sobraba como distractor.

        LO QUE SEPARA, Y NINGUNA OTRA CELDA LO HACE. Una respuesta incorrecta aca dice
        CUAL de dos fallas ocurrio, porque los dos valores estan en el corpus:

          - responde otra ciudad cualquiera  -> no encontro nada: falla de recuperacion
          - responde el domicilio ORIGINAL   -> encontro los dos y eligio el superado:
                                                falla de VIGENCIA

        El F1 castiga las dos igual. Un paradigma que devuelve el valor superado esta
        fallando CON PROCEDENCIA IMPECABLE —el memo viejo dice lo que dice— y ese es
        exactamente el modo de falla que la capa de decision existe para impedir.

        NO SE PLANTA NADA NUEVO: reusa la enmienda que C5 ya crea para el mismo
        (idx, width), asi que la celda no agrega un solo token al corpus.
        """
        units = self._memo_ids()[:width]
        planted_index = (idx * 13 + width // 4 + 1) % max(1, width)
        planted = self.people[planted_index]
        conflicting = f"amend-{planted_index:03d}-w{width:03d}"
        alt_city = next(c for c in CITIES if c != planted.city)
        if conflicting not in self.documents:
            self.documents[conflicting] = "\n".join([
                f"SUPPLEMENTARY FILING {conflicting.upper()}",
                "",
                f"The domicile of record associated with settlement account "
                f"{planted.account} is {alt_city}.",
                "This filing supersedes any earlier domicile on record for that account.",
                "No other engagement details are restated.",
            ])
        return Task(
            task_id=f"c8-{idx:03d}-w{width}",
            cell="C8_currency",
            question=(
                f"What is the domicile of record currently on file for settlement "
                f"account {planted.account}? Name the city only."
            ),
            oracle=[alt_city],
            unit_ids=units + [conflicting],
            relevant_units=[conflicting],
            budget_tokens=60_000,
            truth_n_units=len(units) + 1,
            # No exige encadenar: la enmienda sola contesta. Lo que exige es NO quedarse
            # con el primer valor que aparece, que es otra cosa.
            truth_coupling=0.2,
        )

    def task_c7_irreversible(self, idx: int, warranted: bool) -> Task:
        """High risk. A critic gate is mandatory regardless of what costs suggest.

        Half the tasks warrant escalation and half do not. With only negative cases —
        as in the first version — a paradigm that answers "no escalation" unread scores
        perfectly, so the cell could not tell caution from laziness. Both directions
        are needed: inventing grounds for an irreversible action is one failure,
        missing real grounds is the other.
        """
        person = self.people[idx % len(self.people)]
        units = self._memo_ids()[:8]

        if warranted:
            trigger = f"alert-{idx:03d}"
            self.documents[trigger] = "\n".join([
                f"COMPLIANCE ALERT {trigger.upper()}",
                "",
                f"Settlement account {person.account} was flagged for structuring "
                f"activity across three consecutive reporting periods.",
                "This engagement requires escalation for freezing.",
            ])
            units = units + [trigger]

        return Task(
            task_id=f"c7-{idx:03d}-{'pos' if warranted else 'neg'}",
            cell="C7_irreversible",
            question=(
                f"Decide whether the engagement for {person.name} should be escalated "
                f"for freezing, based only on the supplied units. "
                f"Answer 'escalate' or 'no escalation'."
            ),
            oracle=["escalate"] if warranted else ["no escalation"],
            unit_ids=units,
            # A negative case has NO answer-bearing unit. That is the point of it: the
            # correct behaviour is to find nothing and say so, and a retriever cannot
            # help.
            relevant_units=[f"alert-{idx:03d}"] if warranted else [],
            budget_tokens=20_000,
            irreversible=True,
            truth_n_units=len(units),
            truth_coupling=0.1,
        )

    # -- assembly ----------------------------------------------------------

    def build_tasks(self, per_cell: int, widths: tuple[int, ...]) -> list[Task]:
        tasks: list[Task] = []
        for i in range(per_cell):
            tasks.append(self.task_c1_single_fact(i))
            # Both polarities, so the cell can distinguish caution from laziness.
            tasks.append(self.task_c7_irreversible(i, warranted=False))
            tasks.append(self.task_c7_irreversible(i, warranted=True))
            tasks.append(self.task_c3_multi_hop(i, hops=1 + (i % 3)))
            for width in widths:
                tasks.append(self.task_c2_bulk_extraction(i, width))
                tasks.append(self.task_c4_aggregate(i, width))
                tasks.append(self.task_c5_contradiction(i, width))
                # Despues de C5, que es quien planta la enmienda que esta reusa.
                tasks.append(self.task_c8_currency(i, width))
                # La unica celda cuyo dominio de completitud viene ENUNCIADO. Reusa los
                # memos que ya existen: cero documentos nuevos.
                tasks.append(self.task_c9_roster(i, width))
                # LAS DOS CELDAS DE OBLIGACION. Reusan los memos que ya existen: cero
                # documentos nuevos, igual que C9.
                #
                # B2 puede no ser generable —si todo rol esta instanciado no hay ausencia
                # legitima que preguntar— y ahi se DECLARA en vez de degradarla a una
                # tarea de presencia con nombre de ausencia.
                tasks.append(self.task_b2_absence(i, width))
                tasks.append(self.task_d1_presupposition(i, width))
        return tasks


# A runtime detector exists only where VERIFYING is cheaper than SOLVING.
#
#   C1  one fact: look at it and you know.                             detector
#   C7  a trigger is present or it is not.                             detector
#   C2  "list every X": verifying completeness IS the task.            none
#   C3  a chain endpoint: checking it means walking the chain.         none
#   C4  an aggregate: verifying the count requires the count.          none
#   C5  unknown horizon: knowing when to stop is the question.         none
#   C8  currency: verifying a value is current means finding every
#       filing that could supersede it -- which is the task.               none
#   B2  absence: checking "nobody holds R" means scanning the whole
#       domain, which is exactly what solving it costs.                    none
#   D1  presupposition: the correct answer is that the premise is not
#       supported, and verifying THAT is the absence problem again.        none
#
# Y LAS DOS ULTIMAS TIENEN UNA ASIMETRIA QUE VALE DECIR. Verificar la POLARIDAD OPUESTA
# si es barato: un testigo literal confirma una presencia, y confirmar una premisa
# sostenida cuesta una contencion de cadena. Pero el detector se declara para la celda, y
# la celda pregunta el caso caro. Declararlo `True` por el caso barato pondria la cascada
# adelante de cada decision y llamaria a eso una medicion de ruteo.
#
# This is a claim about the WORLD, not a knob. A deployment that can cheaply check a
# list is a deployment with an index nobody has; declaring one anyway puts the cascade
# in front of every decision and calls the result a routing measurement.
HONEST_DETECTORS = {
    "C1": True,
    "C7": True,
    "B2": False,
    "D1": False,
    "C2": False,
    "C3": False,
    "C4": False,
    "C5": False,
    "C8": False,
    # C9 NO tiene detector de correccion: saber que cuenta le toca a cada nombre sigue
    # costando la busqueda. Lo que tiene es un detector de COMPLETITUD, y son cosas
    # distintas — por eso el eje es `completeness_domain` y no un `has_oracle` mas
    # generoso. Colapsarlos volveria a hacer lo que `has_oracle` ya hizo una vez.
    "C9": False,
}


# -- demandas tipadas del request (U-1 / O-4) ------------------------------------------
#
# QUE SE TIPA, Y POR QUE SON DOS EJES Y NO UNO. El eje propuesto era la CARDINALIDAD DE
# LA RESPUESTA: «cual fue el arma homicida» espera exactamente una y no pide exhaustividad;
# «listame los nombres» espera varias y la pide implicita, sin decirla nunca.
#
# Pero el corpus ya contiene los contraejemplos de que ese eje solo no alcanza. C5 pide UN
# individuo —cardinalidad singular— y sin embargo no se puede contestar sin haber barrido
# todo, porque la contradiccion puede estar en cualquier unidad. C8 pide UNA ciudad y
# tampoco: hay que ver el memo base Y la enmienda, o no se sabe cual vale. En las dos, la
# cardinalidad de la respuesta dice «singular» y la lectura correcta es exhaustiva.
#
# Entonces el tipo es un PAR:
#
#   cardinality  cuantos valores tiene la respuesta bien formada
#   coverage     que hace falta haber visto para que sea correcta
#
# `sufficient` significa que parar en el primer acierto ES CORRECTO — no es un atajo que
# el paradigma se toma, es lo que la pregunta permite. `exhaustive` significa que parar
# temprano produce una respuesta que PARECE bien formada y esta mal, que es el modo de
# falla caro.
#
# Ninguna de las dos se infiere del texto de la pregunta: se DECLARAN por celda, con
# vocabulario cerrado y falla si la celda no esta en la tabla. Parsear la prosa del
# enunciado para adivinarlas seria construir el sensor sobre exactamente lo que este
# proyecto no acepta como sensor.

# DE DONDE SALE EL DOMINIO CONTRA EL QUE SE VERIFICA LA COMPLETITUD. Es un tercer eje y
# no un detalle de `coverage_demanded`, porque decide si `C-COMPLETE` es APLICABLE:
#
#   from_question  el dominio esta enunciado en la pregunta (una lista de nombres dados).
#                  Es `COMPUTED`, enumerable, y verificarlo NO cuesta resolver la tarea.
#   from_scope     el dominio son las unidades en alcance. Tambien gratis de enumerar,
#                  pero 8.6 midio que la fraccion leida NO predice correccion en celdas
#                  exhaustivas (+0,018): verifica lo que no importa.
#   semantic       el dominio se descubre resolviendo. Enumerarlo ES la extraccion, asi
#                  que el contrato no verificaria al paradigma: lo reemplazaria.
#   none           la pregunta no enumera nada.
#
# EL HALLAZGO QUE LO HIZO NECESARIO (leccion 8.7). Antes de C9, ninguna celda era
# `from_question`, y las tablas del corpus dejaban a `cobertura exigida` y `detector barato`
# PERFECTAMENTE anti-correlacionadas — la interseccion era vacia. Asi que el contrato que la
# medicion justifico no tenia donde ejercitarse.
COMPLETENESS_DOMAIN = frozenset({"none", "from_question", "from_scope", "semantic"})

CARDINALITY = frozenset({"singular", "enumerative", "aggregate", "boolean"})
COVERAGE = frozenset({"sufficient", "exhaustive"})

REQUEST_DEMANDS: dict[str, tuple[str, str, str]] = {
    # celda    cardinalidad     cobertura       dominio de completitud
    "C1": ("singular", "sufficient", "none"),
    "C2": ("enumerative", "exhaustive", "semantic"),
    "C3": ("singular", "sufficient", "none"),
    "C4": ("aggregate", "exhaustive", "from_scope"),
    "C5": ("singular", "exhaustive", "from_scope"),
    "C7": ("boolean", "sufficient", "none"),
    "C8": ("singular", "exhaustive", "from_scope"),
    # La UNICA celda `from_question`: el dominio son las personas que el enunciado nombra.
    "C9": ("enumerative", "exhaustive", "from_question"),
    # AUSENCIA: enumerativa —pide una lista— y EXHAUSTIVA por la asimetria de C-ABSENCE.
    # Una ausencia se sostiene con el dominio entero o no se sostiene, asi que exigir
    # `sufficient` aca seria dejar pasar exactamente la falla que la celda existe para
    # medir. El dominio es `from_scope`: lo que hay que barrer son las unidades.
    "B2": ("enumerative", "exhaustive", "from_scope"),
    # PRESUPOSICION: singular —pide una fecha— y `sufficient`, porque lo que se verifica
    # NO es cobertura sino la premisa. Un testigo literal la sostiene o no la sostiene, y
    # leer el resto del corpus no cambia ese veredicto.
    "D1": ("singular", "sufficient", "none"),
}


def apply_request_demands(tasks: list[Task]) -> list[Task]:
    """Declarar el par (cardinalidad, cobertura) por celda. Falla si falta la celda."""
    for task in tasks:
        prefix = task.cell.split("_")[0]
        if prefix not in REQUEST_DEMANDS:
            raise ValueError(
                f"La celda {task.cell!r} no declara demandas de request. Una celda sin "
                f"declarar tomaria un default, y el default silencioso es lo que hizo "
                f"inmedible al detector — asi que falla."
            )
        card, cov, dom = REQUEST_DEMANDS[prefix]
        assert card in CARDINALITY and cov in COVERAGE, (card, cov)
        assert dom in COMPLETENESS_DOMAIN, dom
        task.answer_cardinality = card
        task.coverage_demanded = cov
        task.completeness_domain = dom
    return tasks


def apply_honest_detectors(tasks: list[Task]) -> list[Task]:
    """Declare `has_oracle` per cell by whether verifying is cheaper than solving."""
    for task in tasks:
        prefix = task.cell.split("_")[0]
        if prefix not in HONEST_DETECTORS:
            raise ValueError(
                f"Cell {task.cell!r} has no declared detector. A cell whose detector "
                f"nobody decided defaults to True, which is the conflation this flag "
                f"exists to remove — so it fails instead."
            )
        task.has_oracle = HONEST_DETECTORS[prefix]
    return tasks


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate the stratified corpus.")
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--people", type=int, required=True)
    parser.add_argument("--per-cell", type=int, required=True)
    parser.add_argument(
        "--widths", type=str, required=True,
        help="Comma-separated cardinality dials, e.g. 4,16,48",
    )
    parser.add_argument("--out", type=str, required=True)
    parser.add_argument(
        "--unit-tokens", type=int, default=0,
        help="Pad each unit to roughly this many tokens. 0 leaves the natural\n             size. Large values create the regime where reading everything is\n             not an option, which is the regime the comparison is about.",
    )
    parser.add_argument(
        "--honest-detectors", action="store_true",
        help="Declare has_oracle per cell by whether verifying is cheaper than\n"
             "             solving, instead of True everywhere. The gold oracle is\n"
             "             untouched: only what the DECISION is told changes.",
    )
    parser.add_argument(
        "--hard", action="store_true",
        help="Varied phrasing, near-miss distractors and padding. Removes the\n             lexical shortcut that made every fact findable with one search.",
    )
    args = parser.parse_args()

    widths = tuple(int(w) for w in args.widths.split(","))
    generator = Generator(seed=args.seed)
    generator.build_world(n_people=args.people)
    if args.hard:
        generator.build_documents_hard()
    else:
        generator.build_documents()
    if args.unit_tokens:
        generator.inflate_units(args.unit_tokens)
    tasks = generator.build_tasks(per_cell=args.per_cell, widths=widths)
    if args.honest_detectors:
        tasks = apply_honest_detectors(tasks)
    # SIEMPRE, sin flag: las demandas son verdad sobre la celda y NO cambian lo que la
    # capa de decision recibe — se registran como se registra `truth_n_units`, para que
    # el estudio pueda preguntar si el eje importa ANTES de pagar por elicitarlo.
    tasks = apply_request_demands(tasks)

    max_width = max(widths)
    if max_width > args.people:
        raise ValueError(
            f"--widths asks for {max_width} memos but only {args.people} people exist."
        )

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    (out / "documents.json").write_text(
        json.dumps(generator.documents, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out / "tasks.json").write_text(
        json.dumps([t.as_dict() for t in tasks], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    cells: dict[str, int] = {}
    for t in tasks:
        cells[t.cell] = cells.get(t.cell, 0) + 1

    (out / "manifest.json").write_text(
        json.dumps(
            {
                "generator_version": GENERATOR_VERSION,
                "seed": args.seed,
                "hard": args.hard,
                "honest_detectors": args.honest_detectors,
                "unit_tokens": args.unit_tokens,
                "people": args.people,
                "per_cell": args.per_cell,
                "widths": list(widths),
                "documents": len(generator.documents),
                "tasks": len(tasks),
                "cells": cells,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"documents : {len(generator.documents)}")
    print(f"tasks     : {len(tasks)}")
    for cell in sorted(cells):
        print(f"  {cell:<32} {cells[cell]}")
    print(f"written to {out}")


if __name__ == "__main__":
    main()
