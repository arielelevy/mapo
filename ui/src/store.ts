import { create } from "zustand";
import { estimateTokens } from "./lib/tokens";
import { demoEvents, liveEvents, type AnswerRequest } from "./lib/transport";
import type {
  Assurance,
  ContextEntry,
  DocumentRecord,
  Exchange,
  Unit,
  Workspace,
} from "./types";

export interface RequestFlags {
  irreversible: boolean;
  sharedWrites: boolean;
  regulated: boolean;
}

const wait = (ms: number) => new Promise((r) => setTimeout(r, ms));
let counter = 0;
const nextId = (p: string) => `${p}${++counter}`;

const UNIT_TITLES = [
  "márgenes por línea de producto",
  "condiciones de rescisión",
  "tabla de amortización",
  "supuestos macro del ejercicio",
  "anexo de garantías",
  "cronograma de entregas",
  "penalidades por incumplimiento",
  "estructura de costos fijos",
  "proyección de caja",
  "cuadro de resultados comparativo",
  "detalle de provisiones",
  "notas a los estados contables",
];

interface State {
  workspaces: Workspace[];
  activeWorkspaceId: string;
  documents: DocumentRecord[];
  units: Unit[];
  /** El contexto es por workspace: cambiar de corpus no arrastra evidencia ajena. */
  context: ContextEntry[];
  exchanges: Exchange[];
  assurance: Assurance;
  budget: number;
  live: boolean;
  running: boolean;
  /** Declarados por quien pregunta. El motor los asienta como COMPUTED. */
  flags: RequestFlags;

  setFlag: (key: keyof RequestFlags, value: boolean) => void;
  setWorkspace: (id: string) => void;
  createWorkspace: (name: string) => void;
  setAssurance: (a: Assurance) => void;
  setBudget: (n: number) => void;
  toggleLive: () => void;

  ingestFiles: (files: File[]) => void;
  removeDocument: (id: string) => void;

  addToContext: (unitId: string) => void;
  removeFromContext: (unitId: string) => void;
  toggleIncluded: (unitId: string) => void;
  setAllIncluded: (included: boolean) => void;
  clearContext: () => void;

  ask: (question: string) => Promise<void>;
  cancel: () => void;
}

let inflight: AbortController | null = null;

export const useMapo = create<State>((set, get) => ({
  workspaces: [
    { id: "ws1", name: "corpus-tecnico", collection: "Chunk_v8" },
    { id: "ws2", name: "contratos-2026", collection: "Chunk_v8" },
  ],
  activeWorkspaceId: "ws1",
  documents: [],
  units: [],
  context: [],
  exchanges: [],
  assurance: "A2",
  budget: 24_000,
  live: false,
  running: false,
  flags: { irreversible: false, sharedWrites: false, regulated: false },

  setFlag: (key, value) => set((s) => ({ flags: { ...s.flags, [key]: value } })),

  setWorkspace: (id) => set({ activeWorkspaceId: id, context: [] }),

  createWorkspace: (name) => {
    const ws: Workspace = { id: nextId("ws"), name, collection: "Chunk_v1" };
    set((s) => ({
      workspaces: [...s.workspaces, ws],
      activeWorkspaceId: ws.id,
      context: [],
    }));
  },

  setAssurance: (assurance) => set({ assurance }),
  setBudget: (budget) => set({ budget }),
  toggleLive: () => set((s) => ({ live: !s.live })),

  /* ── ingesta asincrónica ───────────────────────────────────────────────
     Cada documento avanza por su cuenta. Subir cinco no serializa nada: el
     motor los toma en paralelo y el panel refleja ese paralelismo.        */
  ingestFiles: (files) => {
    const workspaceId = get().activeWorkspaceId;
    const collection =
      get().workspaces.find((w) => w.id === workspaceId)?.collection ?? "Chunk_v1";

    for (const file of files) {
      const doc: DocumentRecord = {
        id: nextId("d"),
        workspaceId,
        name: file.name,
        bytes: file.size,
        step: 0,
        sensor: null,
        ocr: false,
        unitCount: 0,
        collection,
        failed: null,
      };
      set((s) => ({ documents: [doc, ...s.documents] }));
      void runIngest(doc, set, get);
    }
  },

  removeDocument: (id) =>
    set((s) => {
      const gone = s.units.filter((u) => u.documentId === id).map((u) => u.id);
      return {
        documents: s.documents.filter((d) => d.id !== id),
        units: s.units.filter((u) => u.documentId !== id),
        context: s.context.filter((c) => !gone.includes(c.unitId)),
      };
    }),

  /* ── contexto curado ───────────────────────────────────────────────────
     Poner algo en la bandeja y encenderlo son dos gestos distintos: podés
     apagar una unidad, mirar cómo cambia la factibilidad, y volver a
     prenderla sin haberla perdido de vista.                               */
  addToContext: (unitId) =>
    set((s) =>
      s.context.some((c) => c.unitId === unitId)
        ? s
        : { context: [...s.context, { unitId, included: true }] },
    ),

  removeFromContext: (unitId) =>
    set((s) => ({ context: s.context.filter((c) => c.unitId !== unitId) })),

  toggleIncluded: (unitId) =>
    set((s) => ({
      context: s.context.map((c) =>
        c.unitId === unitId ? { ...c, included: !c.included } : c,
      ),
    })),

  setAllIncluded: (included) =>
    set((s) => ({ context: s.context.map((c) => ({ ...c, included })) })),

  clearContext: () => set({ context: [] }),

  /* ── una pregunta ──────────────────────────────────────────────────── */
  ask: async (question) => {
    const s = get();
    const unitIds = s.context.filter((c) => c.included).map((c) => c.unitId);
    const chosen = s.units.filter((u) => unitIds.includes(u.id));
    const contextTokens = chosen.reduce((n, u) => n + u.tokens, 0);

    const exchange: Exchange = {
      id: nextId("x"),
      question,
      unitIds,
      assurance: s.assurance,
      budget: s.budget,
      declared: (
        [
          ["irreversible", s.flags.irreversible],
          ["escrituras compartidas", s.flags.sharedWrites],
          ["regulado", s.flags.regulated],
        ] as const
      )
        .filter(([, on]) => on)
        .map(([label]) => label),
      plan: null,
      probe: null,
      answer: "",
      citations: [],
      usage: null,
      error: null,
      streaming: true,
    };
    set((st) => ({ exchanges: [...st.exchanges, exchange], running: true }));

    const patch = (fn: (x: Exchange) => Exchange) =>
      set((st) => ({
        exchanges: st.exchanges.map((x) => (x.id === exchange.id ? fn(x) : x)),
      }));

    const req: AnswerRequest = {
      question,
      units: unitIds,
      contextTokens,
      assurance: s.assurance,
      budget: s.budget,
      ...s.flags,
    };

    inflight = new AbortController();
    const { signal } = inflight;

    try {
      const source = s.live ? liveEvents(req, signal) : demoEvents(req, signal);
      for await (const ev of source) {
        if (signal.aborted) break;
        switch (ev.type) {
          case "decision":
            patch((x) => ({ ...x, plan: ev.plan }));
            break;
          case "probe":
            patch((x) => ({
              ...x,
              probe: { unit: ev.unit, result: ev.result, provenance: ev.provenance },
            }));
            break;
          case "token":
            patch((x) => ({ ...x, answer: x.answer + ev.text }));
            break;
          case "citation":
            patch((x) => ({
              ...x,
              citations: [
                ...x.citations,
                { unit: ev.unit, page: ev.page, chunk: ev.chunk, offset: x.answer.length },
              ],
            }));
            break;
          case "usage":
            patch((x) => ({
              ...x,
              usage: { tokens: ev.tokens, probes: ev.probes, ms: ev.ms },
            }));
            break;
          case "done":
          case "gated":
          case "deferred":
            patch((x) => ({ ...x, plan: ev.plan }));
            break;
          case "paradigm.step":
            break;
        }
      }
    } catch (err) {
      if ((err as Error).name !== "AbortError") {
        patch((x) => ({ ...x, error: (err as Error).message }));
      }
    } finally {
      patch((x) => ({ ...x, streaming: false }));
      set({ running: false });
      inflight = null;
    }
  },

  cancel: () => {
    inflight?.abort();
    set({ running: false });
  },
}));

/* ── el pipeline de ingesta ───────────────────────────────────────────────
   Los pasos son los de ARQUITECTURA.es.md §3. El sensor decide OCR ANTES de
   parsear, así un PDF escaneado no se parsea dos veces.                    */
async function runIngest(
  doc: DocumentRecord,
  set: (fn: (s: State) => Partial<State>) => void,
  get: () => State,
) {
  const step = (patch: Partial<DocumentRecord>) =>
    set((s) => ({
      documents: s.documents.map((d) => (d.id === doc.id ? { ...d, ...patch } : d)),
    }));

  await wait(400 + Math.random() * 500);
  step({ step: 1 });

  // 01 sensor — cobertura de la capa de texto, en chars por página
  await wait(700);
  const charsPerPage = Math.round(Math.random() ** 2 * 1800);
  const ocr = charsPerPage < 120;
  step({
    step: 2,
    ocr,
    sensor: ocr
      ? `capa de texto ausente · ${charsPerPage} chars/pág → con OCR`
      : `capa de texto sana · ${charsPerPage} chars/pág → sin OCR`,
  });

  // 02 parseo — Docling, con procedencia página + bbox
  await wait(ocr ? 2400 : 1100);
  step({ step: 3 });

  // 03 chunks
  await wait(850);
  step({ step: 4 });

  // 04 embeddings
  await wait(1300);

  // 05 indexado
  const n = 3 + Math.floor(Math.random() * 4);
  const existing = get().units.length;
  const units: Unit[] = Array.from({ length: n }, (_, i) => ({
    id: `u-${String(existing + i + 1).padStart(2, "0")}`,
    documentId: doc.id,
    workspaceId: doc.workspaceId,
    title: UNIT_TITLES[(existing + i) % UNIT_TITLES.length]!,
    page: 1 + i * 3,
    tokens: estimateTokens(2200 + Math.random() * 6000),
  }));

  set((s) => ({
    documents: s.documents.map((d) =>
      d.id === doc.id ? { ...d, step: 5, unitCount: n } : d,
    ),
    units: [...s.units, ...units],
  }));
}

/* ── derivaciones ────────────────────────────────────────────────────────
   NO son selectores de zustand. Un selector que construye un array nuevo en
   cada llamada le devuelve a `useSyncExternalStore` un snapshot distinto
   siempre, y eso es un render infinito. Estas funciones se usan dentro de un
   `useMemo` sobre las referencias crudas del store, que sí son estables.   */

export function activeUnits(units: Unit[], workspaceId: string): Unit[] {
  return units.filter((u) => u.workspaceId === workspaceId);
}

export function activeDocuments(
  documents: DocumentRecord[],
  workspaceId: string,
): DocumentRecord[] {
  return documents.filter((d) => d.workspaceId === workspaceId);
}

export type ContextUnit = Unit & { included: boolean };

export function contextUnits(context: ContextEntry[], units: Unit[]): ContextUnit[] {
  return context.flatMap((c) => {
    const unit = units.find((u) => u.id === c.unitId);
    return unit ? [{ ...unit, included: c.included }] : [];
  });
}
