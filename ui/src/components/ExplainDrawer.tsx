import { useEffect, useState } from "react";
import { useMapo, type ReplayResult } from "../store";
import { formatTokens } from "../lib/tokens";
import s from "./ExplainDrawer.module.css";

/**
 * El certificado de una decisión.
 *
 * Muestra lo que EXPLAIN tiene hoy (`lab/DISENO.es.md` §4.7) y, al pie, lo que
 * todavía le falta para un replay integral. Esa segunda lista no es un TODO: es la
 * diferencia entre "puedo explicar la decisión" y "puedo reconstruirla completa", y
 * esconderla convertiría una propuesta en una capacidad.
 */
export default function ExplainDrawer() {
  const id = useMapo((st) => st.explainFor);
  const close = useMapo((st) => st.closeExplain);
  const replay = useMapo((st) => st.replay);
  const exchange = useMapo((st) => st.exchanges.find((e) => e.id === st.explainFor));
  const units = useMapo((st) => st.units);
  const [result, setResult] = useState<ReplayResult | null>(null);
  const [copied, setCopied] = useState(false);

  // Cambiar de intercambio invalida el replay anterior: el resultado es de ESA decisión.
  useEffect(() => {
    setResult(null);
    setCopied(false);
  }, [id]);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") close();
    }
    if (id) document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [id, close]);

  if (!id || !exchange?.plan) return null;
  const { plan } = exchange;

  const certificate = {
    request: {
      question: exchange.question,
      unit_ids: exchange.unitIds,
      context_tokens: exchange.contextTokens,
      assurance: exchange.assurance,
      budget_tokens: exchange.budget,
      declared: exchange.declared,
    },
    decision: {
      region: plan.region,
      verdict: plan.verdict,
      terminal: plan.terminal,
      paradigm: plan.pick,
      margin: plan.margin,
      theta_version: plan.thetaVersion,
      theta_digest: plan.digest,
    },
    feasibility: plan.feasibility.map((f) => ({ paradigm: f.paradigm, rejected: f.reason })),
    assurance_stage: plan.assuranceStage.map((f) => ({
      paradigm: f.paradigm,
      rejected: f.reason,
    })),
    theta: plan.scored,
    probe: exchange.probe,
    approved_at: exchange.approvedAt,
    usage: exchange.usage,
  };

  async function copy() {
    await navigator.clipboard.writeText(JSON.stringify(certificate, null, 2));
    setCopied(true);
  }

  return (
    <>
      <div className={s.scrim} onClick={close} aria-hidden />
      <aside className={s.drawer} role="dialog" aria-modal="true" aria-label="EXPLAIN">
        <header className={s.head}>
          <span className="eyebrow">EXPLAIN</span>
          <button type="button" className={s.close} onClick={close} aria-label="Cerrar">
            ×
          </button>
        </header>

        <div className={s.body}>
          <h3 className={s.q}>{exchange.question}</h3>

          {/* ── replay: el claim, ejercitable ───────────────────────────── */}
          <section className={s.block}>
            <span className="eyebrow">Replay sin red</span>
            <p className={s.lead}>
              Rederiva el plan desde las entradas fijadas y compara. No invoca al modelo.
              La garantía es <b>misma base de creencias ⟹ misma decisión</b>, nunca mismo
              prompt ⟹ misma respuesta: el texto puede variar y no integra la garantía.
            </p>
            <button type="button" className={s.action} onClick={() => setResult(replay(id))}>
              Rederivar el plan
            </button>

            {result && (
              <div className={result.ok ? s.replayOk : s.replayBad}>
                <b>{result.ok ? "Reproduce" : "No reproduce"}</b>
                <dl className={s.kv}>
                  <dt>digest original</dt>
                  <dd>{result.original}</dd>
                  <dt>digest rederivado</dt>
                  <dd>{result.rebuilt}</dd>
                </dl>
                {!result.ok && <p>Difieren: {result.differs.join(", ")}.</p>}
              </div>
            )}
          </section>

          {/* ── entradas fijadas ────────────────────────────────────────── */}
          <section className={s.block}>
            <span className="eyebrow">Entradas fijadas</span>
            <dl className={s.kv}>
              <dt>dial</dt>
              <dd>{exchange.assurance}</dd>
              <dt>presupuesto</dt>
              <dd>{formatTokens(exchange.budget)}</dd>
              <dt>contexto</dt>
              <dd>{formatTokens(exchange.contextTokens)}</dd>
              <dt>declarado</dt>
              <dd>{exchange.declared.length ? exchange.declared.join(", ") : "nada"}</dd>
              <dt>región</dt>
              <dd>{plan.region}</dd>
              <dt>θ</dt>
              <dd>
                {plan.thetaVersion} · {plan.digest}
              </dd>
            </dl>
            <ul className={s.units}>
              {exchange.unitIds.map((uid) => {
                const u = units.find((x) => x.id === uid);
                return (
                  <li key={uid}>
                    <span className={s.uid}>{uid}</span>
                    <span>{u?.title ?? "unidad no cargada"}</span>
                    <span className={s.utok}>{u ? formatTokens(u.tokens) : "—"}</span>
                  </li>
                );
              })}
            </ul>
          </section>

          {/* ── la sonda, si corrió ─────────────────────────────────────── */}
          {exchange.probe && (
            <section className={s.block}>
              <span className="eyebrow">Sonda</span>
              <dl className={s.kv}>
                <dt>unidad</dt>
                <dd>{exchange.probe.unit}</dd>
                <dt>resultado</dt>
                <dd>{exchange.probe.result}</dd>
                <dt>procedencia</dt>
                <dd>{exchange.probe.provenance}</dd>
              </dl>
              <p className={s.note}>
                Sólo una referencia verificada eleva a <code>OBSERVED</code>. Una lectura
                negativa queda en <code>ELICITED</code>: una unidad callada no demuestra
                nada sobre las otras.
              </p>
            </section>
          )}

          {exchange.approvedAt && (
            <section className={s.block}>
              <span className="eyebrow">Autorización</span>
              <p className={s.lead}>
                Una persona autorizó este gate el{" "}
                {new Date(exchange.approvedAt).toLocaleString("es-AR")}. El gate sigue en
                el registro: hubo gate <em>y</em> hubo aprobación, y son dos hechos
                distintos.
              </p>
            </section>
          )}

          {/* ── lo que falta, dicho ─────────────────────────────────────── */}
          <section className={s.block}>
            <span className="eyebrow">Falta para replay integral</span>
            <p className={s.lead}>
              Lo de arriba explica la decisión. Para reconstruirla completa, según{" "}
              <code>DISENO.es.md</code> §4.7, todavía faltan:
            </p>
            <ul className={s.gaps}>
              <li>el vector y la región completos, no sólo su etiqueta</li>
              <li>factibilidad estructurada y el conjunto de candidatos</li>
              <li>digest de reglas y de perfiles de garantía</li>
              <li>identidad de contenido de las unidades</li>
              <li>historia de creencias pre y post sonda</li>
              <li>certificado de promoción de θ</li>
            </ul>
          </section>

          <button type="button" className={s.action} onClick={copy}>
            {copied ? "Copiado" : "Copiar certificado (JSON)"}
          </button>
        </div>
      </aside>
    </>
  );
}
