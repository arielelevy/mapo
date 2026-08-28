/** Vocabulario compartido con el motor. Los nombres son los de `lab/app/`. */

export type Assurance = "A0" | "A1" | "A2" | "A3";

/** `lab/app/beliefs.py` — la jerarquía completa, en orden. */
export type Provenance = "COMPUTED" | "OBSERVED" | "ELICITED" | "ASSUMED";

/** `lab/app/paradigms/README.es.md`. El orden es el del catálogo, no un ranking. */
export const PARADIGMS = [
  "direct",
  "cot",
  "react",
  "map_reduce",
  "plan_execute",
  "reflection",
  "dag_strategy",
  "rewoo",
  "gist_reader",
  "graph_traverse",
  "extract_compute",
  "streaming_scan",
  "pointer_chase",
] as const;

export type Paradigm = (typeof PARADIGMS)[number];

/**
 * Espejo de `Status` en `lab/app/paradigms/__init__.py`.
 *
 * Los trece siguen en el REGISTRY a propósito: borrar una función volvería
 * irreproducible el registro que la midió. El estado es lo que dice si puede correr.
 *
 * `INFEASIBLE` NO se bloquea: la aritmética lo poda a costo cero y registra la razón,
 * que es más informativo que negarse a correrlo. La infactibilidad ES el resultado.
 */
export type Status = "active" | "retired" | "standby" | "infeasible" | "under_review";

export const RUNNABLE: readonly Status[] = ["active", "infeasible", "under_review"];

/* ── ingesta ────────────────────────────────────────────────────────────── */

/** Los pasos de `lab/ARQUITECTURA.es.md` §3. El sensor decide OCR antes de parsear. */
export const INGEST_STEPS = [
  "en cola",
  "sensor",
  "parseo",
  "chunks",
  "embeddings",
  "indexado",
] as const;

export type IngestStep = number; // índice en INGEST_STEPS

export interface DocumentRecord {
  id: string;
  workspaceId: string;
  name: string;
  bytes: number;
  step: IngestStep;
  /** Veredicto del sensor: es una creencia COMPUTED, no una heurística oculta. */
  sensor: string | null;
  ocr: boolean;
  unitCount: number;
  collection: string;
  failed: string | null;
}

export interface Unit {
  id: string;
  documentId: string;
  workspaceId: string;
  title: string;
  page: number;
  tokens: number;
}

export interface Workspace {
  id: string;
  name: string;
  /** Versión de índice viva. Fija embedder, parser, chunker y manifiesto. */
  collection: string;
}

/* ── contexto curado ────────────────────────────────────────────────────── */

/**
 * Una unidad puesta en el contexto de la próxima pregunta. `included` existe porque
 * sacar algo del contexto no es lo mismo que quitarlo de la bandeja: querés poder
 * apagar una unidad, ver cómo cambia la factibilidad, y volver a prenderla.
 */
export interface ContextEntry {
  unitId: string;
  included: boolean;
}

/* ── decisión ───────────────────────────────────────────────────────────── */

export type Verdict = "especializar" | "cascada" | "sonda" | "abstener" | "gate";
export type Terminal = "done" | "gated" | "deferred";

export interface Strike {
  paradigm: Paradigm;
  /** Motivo tipado. `null` significa que sobrevivió la etapa. */
  reason: string | null;
}

export interface Score {
  paradigm: Paradigm;
  utility: number;
  n: number;
}

export interface Plan {
  region: string;
  assurance: Assurance;
  feasibility: Strike[];
  assuranceStage: Strike[];
  scored: Score[];
  margin: number;
  verdict: Verdict;
  terminal: Terminal;
  pick: Paradigm;
  thetaVersion: string;
  digest: string;
}

/* ── eventos del stream (ARQUITECTURA.es.md §6) ─────────────────────────── */

export type StreamEvent =
  | { type: "decision"; plan: Plan }
  | { type: "probe"; unit: string; result: string; provenance: Provenance }
  | { type: "paradigm.step"; label: string }
  | { type: "token"; text: string }
  | { type: "citation"; unit: string; page: number; chunk: string }
  | { type: "usage"; tokens: number; probes: number; ms: number }
  | { type: "done"; plan: Plan }
  | { type: "gated"; plan: Plan }
  | { type: "deferred"; plan: Plan };

export interface Citation {
  unit: string;
  page: number;
  chunk: string;
  offset: number;
}

export interface Exchange {
  id: string;
  question: string;
  unitIds: string[];
  assurance: Assurance;
  budget: number;
  /** Lo que el caller declaró. Queda en el registro junto a la decisión. */
  declared: string[];
  /** Los tokens de contexto con que se decidió. Hace falta para replay. */
  contextTokens: number;
  /**
   * Si una persona autorizó un gate. No borra el gate: el registro tiene que mostrar
   * que hubo gate Y que alguien lo aprobó, porque son dos hechos distintos.
   */
  approvedAt: string | null;
  plan: Plan | null;
  probe: { unit: string; result: string; provenance: Provenance } | null;
  answer: string;
  citations: Citation[];
  usage: { tokens: number; probes: number; ms: number } | null;
  error: string | null;
  streaming: boolean;
}
