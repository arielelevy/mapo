import {
  assuranceStrikes,
  feasibilityStrikes,
  survivorsOf,
} from "./feasibility";
import type {
  Assurance,
  Paradigm,
  Plan,
  Score,
  StreamEvent,
  Terminal,
  Verdict,
} from "../types";

export interface AnswerRequest {
  question: string;
  units: string[];
  contextTokens: number;
  assurance: Assurance;
  budget: number;
  /**
   * Los declara quien pregunta, NUNCA se infieren del texto (`lab/app/serve.py`):
   * se asientan como COMPUTED con credencia 1.0, y adivinarlos desde la redacción
   * pondría una conjetura donde la capa de creencias promete un hecho.
   */
  irreversible: boolean;
  sharedWrites: boolean;
  regulated: boolean;
}

/* ═════════════════════════════════════════════════════════════════════════
   MOTOR REAL — los eventos tipados de ARQUITECTURA.es.md §6
   ═════════════════════════════════════════════════════════════════════════ */

export async function* liveEvents(
  req: AnswerRequest,
  signal: AbortSignal,
): AsyncGenerator<StreamEvent> {
  const res = await fetch("/v1/answer", {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    // snake_case: es el vocabulario de `Request` en `lab/app/serve.py`.
    body: JSON.stringify({
      question: req.question,
      unit_ids: req.units,
      assurance: req.assurance,
      budget_tokens: req.budget,
      irreversible: req.irreversible,
      shared_writes: req.sharedWrites,
      regulated: req.regulated,
    }),
    signal,
  });

  if (!res.ok) throw new Error(`el motor respondió ${res.status}`);
  if (!res.body) throw new Error("la respuesta no trae cuerpo streameable");

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      // Un frame SSE termina en línea en blanco.
      let split: number;
      while ((split = buffer.indexOf("\n\n")) !== -1) {
        const frame = buffer.slice(0, split);
        buffer = buffer.slice(split + 2);

        let event = "message";
        let data = "";
        for (const line of frame.split("\n")) {
          if (line.startsWith("event:")) event = line.slice(6).trim();
          else if (line.startsWith("data:")) data += line.slice(5).trim();
        }
        if (!data) continue;
        yield { type: event, ...JSON.parse(data) } as StreamEvent;
      }
    }
  } finally {
    reader.releaseLock();
  }
}

/* ═════════════════════════════════════════════════════════════════════════
   TRAZAS DE DEMOSTRACIÓN — misma forma de evento, generadas local.
   Sirven para trabajar la interfaz sin motor y sin gastar tokens.
   ═════════════════════════════════════════════════════════════════════════ */

/** Hash estable: la misma región puntúa igual dos veces. θ no es aleatorio. */
function h32(s: string): number {
  let x = 2166136261;
  for (let i = 0; i < s.length; i++) {
    x ^= s.charCodeAt(i);
    x = Math.imul(x, 16777619);
  }
  return (x >>> 0) / 4294967296;
}

export function buildPlan(req: AnswerRequest): Plan {
  const region = "r-" + Math.floor(h32(req.units.join("|") + req.question) * 8999 + 1000);

  const feasibility = feasibilityStrikes({
    contextTokens: req.contextTokens,
    unitCount: req.units.length,
    budget: req.budget,
  });
  const afterFeasibility = survivorsOf(feasibility);
  const assuranceStage = assuranceStrikes(afterFeasibility, req.assurance);
  const admissible = survivorsOf(assuranceStage);

  const scored: Score[] = admissible
    .map((paradigm) => ({
      paradigm,
      utility: +(0.34 + h32(region + "|" + paradigm) * 0.34).toFixed(3),
      n: 12 + Math.floor(h32(paradigm + "|" + region) * 34),
    }))
    .sort((a, b) => b.utility - a.utility);

  const top = scored[0];
  const second = scored[1];
  const margin = top && second ? +(top.utility - second.utility).toFixed(3) : 0.12;

  let terminal: Terminal = "done";
  let verdict: Verdict = "especializar";
  let pick: Paradigm = top?.paradigm ?? "react";

  if (req.irreversible || req.sharedWrites) {
    // Se decide antes de mirar θ: un gate no es un empate, es una competencia ajena.
    terminal = "gated";
    verdict = "gate";
  } else if (!top || margin < 0.03) {
    terminal = "deferred";
    verdict = "abstener";
    // El fallback es `react`, pero abstenerse hacia un paradigma que la aritmética ya
    // descartó sería ejecutar algo infactible. Si react no está admisible, el fallback
    // es el admisible más barato; si no queda ninguno, no hay a dónde abstenerse y la
    // solicitud sube a gate.
    if (admissible.includes("react")) {
      pick = "react";
    } else if (admissible.length > 0) {
      pick = admissible.reduce((cheapest, p) =>
        scored.find((s) => s.paradigm === p)!.utility <
        scored.find((s) => s.paradigm === cheapest)!.utility
          ? p
          : cheapest,
      );
    } else {
      terminal = "gated";
      verdict = "gate";
    }
  } else if (req.assurance === "A3" && req.units.length > 2) {
    verdict = "cascada";
  }

  return {
    region,
    assurance: req.assurance,
    feasibility,
    assuranceStage,
    scored,
    margin,
    verdict,
    terminal,
    pick,
    thetaVersion: "v0031",
    digest: Math.floor(h32(region) * 0xffffffff)
      .toString(16)
      .padStart(8, "0")
      .slice(0, 8),
  };
}

const PROSE =
  "El margen bruto consolidado del ejercicio cerró en 34,2%, contra 31,8% del período " +
  "anterior. La mejora viene casi enteramente de la línea industrial, que pasó de 28,4% " +
  "a 33,1% tras la renegociación de contratos de insumo. La línea de servicios se " +
  "mantuvo plana. El anexo de garantías no modifica el cálculo: las provisiones ya " +
  "estaban imputadas en el resultado operativo.";

const wait = (ms: number) => new Promise((r) => setTimeout(r, ms));

export async function* demoEvents(
  req: AnswerRequest,
  signal: AbortSignal,
): AsyncGenerator<StreamEvent> {
  const plan = buildPlan(req);
  yield { type: "decision", plan };

  if (plan.terminal === "gated") {
    // Un gate no ejecuta NADA. No hay tokens, no hay sonda, no hay respuesta.
    yield { type: "gated", plan };
    return;
  }

  await wait(280);
  if (signal.aborted) return;

  if (plan.assurance !== "A0" && req.units[0]) {
    yield {
      type: "probe",
      unit: req.units[0],
      result: "referencia resuelta contra el índice",
      provenance: "OBSERVED",
    };
    await wait(420);
  }

  if (plan.terminal === "deferred") yield { type: "deferred", plan };

  yield { type: "paradigm.step", label: `${plan.pick} · ejecutando` };

  for (const word of PROSE.split(" ")) {
    if (signal.aborted) return;
    yield { type: "token", text: word + " " };
    await wait(20);
  }

  if (req.units[0]) {
    yield { type: "citation", unit: req.units[0], page: 4, chunk: "c8-0192" };
  }
  yield {
    type: "usage",
    tokens: Math.round(req.contextTokens * 1.9 + 1400),
    probes: plan.assurance !== "A0" ? 1 : 0,
    ms: 1180,
  };
  if (plan.terminal === "done") yield { type: "done", plan };
}
