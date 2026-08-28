import { PARADIGMS, type Assurance, type Paradigm, type Strike } from "../types";

/**
 * Espejo LOCAL de la poda aritmética de `lab/app/feasibility.py`.
 *
 * Existe por una razón de producto: la factibilidad no consume inferencia, así que la
 * podés calcular mientras el usuario arma el contexto. Agregar una unidad mata a
 * `direct` por ventana; agregar la quinta mata a `map_reduce` por cardinalidad. Eso se
 * ve ANTES de gastar un token, que es exactamente lo que el motor promete.
 *
 * No es la autoridad. El veredicto que vale es el que devuelve el motor en el evento
 * `decision`; esto es una vista previa y la interfaz lo dice así.
 */

/** Ventana efectiva para "toda la evidencia entra de una". */
const WINDOW_TOKENS = 32_000;

/** Overhead de prompt por llamada: instrucciones, esquema, andamiaje. */
const CALL_OVERHEAD = 900;

/**
 * Multiplicadores sobre los tokens de contexto. Son priors de costo, no mediciones:
 * el banco tiene los números reales en `lab/results/`.
 */
const COST_PRIOR: Record<Paradigm, (ctx: number, units: number) => number> = {
  direct: (c) => c + CALL_OVERHEAD,
  cot: (c) => c * 1.3 + CALL_OVERHEAD,
  react: (c) => c * 4.5 + CALL_OVERHEAD * 6,
  map_reduce: (c, u) => c + CALL_OVERHEAD * (u + 1),
  plan_execute: (c) => c * 3.2 + CALL_OVERHEAD * 4,
  reflection: (c) => c * 2.6 + CALL_OVERHEAD * 3,
  dag_strategy: (c) => c * 6.0 + CALL_OVERHEAD * 9,
  rewoo: (c) => c * 2.2 + CALL_OVERHEAD * 3,
  gist_reader: (c) => c * 2.0 + CALL_OVERHEAD * 4,
  graph_traverse: (c) => c * 3.0 + CALL_OVERHEAD * 5,
  extract_compute: (c, u) => c * 1.4 + CALL_OVERHEAD * (u + 2),
  streaming_scan: (c, u) => c * 1.2 + CALL_OVERHEAD * (u + 3),
  pointer_chase: (c) => c * 2.4 + CALL_OVERHEAD * 5,
};

/**
 * Veredictos ya cerrados del banco. No son poda por request: son catálogo, y por eso
 * el motivo cita la predicción que los cerró (`lab/README.md` §Findings).
 */
const CLOSED: Partial<Record<Paradigm, string>> = {
  cot: "retirado · control nulo",
  gist_reader: "falsificado P13",
  graph_traverse: "falsificado P10a",
  pointer_chase: "falsificado P14a",
};

export interface FeasibilityInput {
  contextTokens: number;
  unitCount: number;
  budget: number;
}

export function feasibilityStrikes({
  contextTokens,
  unitCount,
  budget,
}: FeasibilityInput): Strike[] {
  return PARADIGMS.map((paradigm): Strike => {
    const closed = CLOSED[paradigm];
    if (closed) return { paradigm, reason: closed };

    // `direct` es el caso degenerado: sólo existe cuando TODA la evidencia entra en
    // ventana. Con un corpus real eso deja de pasar, y no es un candidato del catálogo.
    if (paradigm === "direct" && contextTokens + CALL_OVERHEAD > WINDOW_TOKENS * 0.75) {
      return { paradigm, reason: "contexto" };
    }

    // Un map por unidad: pasado cierto número de unidades el fan-out ya no cabe.
    if (paradigm === "map_reduce" && unitCount > 12) {
      return { paradigm, reason: "cardinalidad" };
    }

    const cost = COST_PRIOR[paradigm](contextTokens, unitCount);
    if (cost > budget) return { paradigm, reason: "presupuesto" };

    return { paradigm, reason: null };
  });
}

/** El dial no ordena paradigmas: recorta el espacio admisible. */
export function assuranceStrikes(survivors: Paradigm[], dial: Assurance): Strike[] {
  const excluded: Partial<Record<Paradigm, string>> = {};
  if (dial === "A2" || dial === "A3") excluded.dag_strategy = "flujo no acotado";
  if (dial === "A3") {
    excluded.react = "flujo no acotado";
    excluded.reflection = "procedencia insuficiente";
  }
  return survivors.map((paradigm) => ({
    paradigm,
    reason: excluded[paradigm] ?? null,
  }));
}

export function survivorsOf(strikes: Strike[]): Paradigm[] {
  return strikes.filter((s) => s.reason === null).map((s) => s.paradigm);
}

/** Estimación del costo del más caro que todavía está en juego. Sirve al medidor. */
export function worstCaseCost(
  admissible: Paradigm[],
  contextTokens: number,
  unitCount: number,
): number {
  if (admissible.length === 0) return 0;
  return Math.max(...admissible.map((p) => COST_PRIOR[p](contextTokens, unitCount)));
}

export { WINDOW_TOKENS };
