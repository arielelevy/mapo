import { PARADIGMS, type Exchange, type Plan, type Strike } from "../types";
import { formatTokens } from "../lib/tokens";
import s from "./ExchangeView.module.css";

/* Las etapas son una secuencia real: el orden carga información. */
const STAGES = [
  { n: "01", name: "Factibilidad", note: "aritmética · sin inferencia" },
  { n: "02", name: "Garantía", note: "piso de procedencia y espacio admisible" },
  { n: "03", name: "θ", note: "utilidad media · evidencia · margen" },
] as const;

export default function ExchangeView({ exchange }: { exchange: Exchange }) {
  const { plan } = exchange;

  return (
    <article className={s.xch} data-terminal={plan?.terminal ?? "pending"}>
      <div className={s.wrap}>
        <h2 className={s.ask}>{exchange.question}</h2>
        <div className={s.askUnits}>
          {exchange.unitIds.map((id) => (
            <span key={id} className={s.askUnit}>
              {id}
            </span>
          ))}
          <span className={s.askDial}>dial {exchange.assurance}</span>
          {exchange.declared.map((d) => (
            <span key={d} className={s.askDeclared}>
              {d}
            </span>
          ))}
        </div>

        {plan ? <Ladder plan={plan} /> : <p className={s.waiting}>decidiendo…</p>}
        {plan && <Verdict plan={plan} exchange={exchange} />}

        {exchange.probe && (
          <p className={s.probe}>
            sonda · {exchange.probe.unit} · {exchange.probe.result} →{" "}
            <b>{exchange.probe.provenance}</b>
          </p>
        )}

        {plan?.terminal !== "gated" && (exchange.answer || exchange.streaming) && (
          <section className={s.answer}>
            <span className="eyebrow">Respuesta</span>
            <div className={s.answerText}>
              {exchange.answer}
              {exchange.streaming && <i className={s.cursor} />}
            </div>
            {exchange.citations.length > 0 && (
              <div className={s.cites}>
                {exchange.citations.map((c, i) => (
                  <span
                    key={i}
                    className={s.cite}
                    title={`chunk ${c.chunk} · verificado contra el índice vivo`}
                  >
                    {c.unit} · p.{c.page}
                  </span>
                ))}
              </div>
            )}
            {exchange.usage && (
              <div className={s.usage}>
                <span>{formatTokens(exchange.usage.tokens)} tokens</span>
                <span>
                  {exchange.usage.probes} sonda{exchange.usage.probes === 1 ? "" : "s"}
                </span>
                <span>{exchange.usage.ms} ms</span>
              </div>
            )}
          </section>
        )}

        {exchange.error && (
          <div className={`${s.notice} ${s.noticeHalt}`}>
            <b>El motor no respondió</b>
            {exchange.error}. Comprobá que la API esté en pie, o volvé a demo desde el
            control de arriba a la derecha.
          </div>
        )}
      </div>
    </article>
  );
}

/* ── la escalera: trece paradigmas tachándose antes de que exista un token ── */
function Ladder({ plan }: { plan: Plan }) {
  const admissible = plan.assuranceStage.filter((x) => !x.reason).length;
  const maxUtility = plan.scored[0]?.utility ?? 1;

  return (
    <div className={s.ladder}>
      <Stage
        stage={STAGES[0]}
        note={`${plan.feasibility.filter((x) => !x.reason).length} de ${PARADIGMS.length} caben`}
      >
        {plan.feasibility.map((x, i) => (
          <StrikeRow key={x.paradigm} strike={x} index={i} />
        ))}
      </Stage>

      <Stage
        stage={STAGES[1]}
        note={`dial ${plan.assurance} · ${plan.assuranceStage.filter((x) => x.reason).length} excluidos`}
      >
        {plan.assuranceStage.map((x, i) => (
          <StrikeRow key={x.paradigm} strike={x} index={i} />
        ))}
      </Stage>

      <Stage
        stage={STAGES[2]}
        note={`región ${plan.region} · margen ${plan.margin.toFixed(3)} · ${admissible} admisibles`}
      >
        {plan.scored.length === 0 ? (
          <p className={s.none}>Ningún paradigma sobrevivió a las dos etapas.</p>
        ) : (
          plan.scored.map((sc, i) => (
            <div
              key={sc.paradigm}
              className={`${s.row} ${s.rowTheta} ${
                i === 0 && plan.terminal !== "deferred" ? s.rowPick : s.rowIn
              }`}
            >
              <span className={s.rowName}>{sc.paradigm}</span>
              <span className={s.bar}>
                <i style={{ width: `${(sc.utility / maxUtility) * 100}%` }} />
              </span>
              <span className={s.rowVal}>
                {sc.utility.toFixed(3)} · n={sc.n}
              </span>
            </div>
          ))
        )}
      </Stage>
    </div>
  );
}

function Stage({
  stage,
  note,
  children,
}: {
  stage: (typeof STAGES)[number];
  note: string;
  children: React.ReactNode;
}) {
  return (
    <section className={s.stage}>
      <header className={s.stageHead}>
        <span className={s.stageN}>{stage.n}</span>
        <span className={s.stageName}>{stage.name}</span>
        <span className={s.stageNote}>{note}</span>
      </header>
      <div className={s.rows}>{children}</div>
    </section>
  );
}

function StrikeRow({ strike, index }: { strike: Strike; index: number }) {
  const out = strike.reason !== null;
  return (
    <div
      className={`${s.row} ${out ? s.rowOut : s.rowIn}`}
      style={{ animationDelay: `${index * 26}ms` }}
    >
      <span className={s.rowName}>{strike.paradigm}</span>
      <span className={s.rowWhy}>{strike.reason ?? ""}</span>
      <span className={s.rowVal}>{out ? "" : "✓"}</span>
    </div>
  );
}

/* ── veredicto: los tres terminales son estructuralmente distintos ───────── */
function Verdict({ plan, exchange }: { plan: Plan; exchange: Exchange }) {
  return (
    <div className={s.verdict}>
      <div className={s.verdictLine}>
        <span className={s.verdictTag}>04 {plan.verdict}</span>
        <span className={s.verdictWhat}>
          {plan.terminal === "gated" ? "nada se ejecutó" : plan.pick}
        </span>
        <span className={s.verdictMeta}>
          θ {plan.thetaVersion} · {plan.digest}
          <br />
          plan {plan.region} · replay sin red
        </span>
      </div>

      {plan.terminal === "gated" && (
        <div className={`${s.notice} ${s.noticeHalt}`}>
          <b>Requiere revisión humana</b>
          La solicitud declara una acción irreversible o de escritura compartida. El plan
          quedó registrado y ningún paradigma corrió. Un gate no es una respuesta segura:
          es una decisión que le corresponde a una persona.
          <div className={s.noticeActs}>
            <button type="button" className={s.btn}>
              Aprobar y ejecutar
            </button>
            <button type="button" className={s.btn}>
              Ver EXPLAIN
            </button>
          </div>
        </div>
      )}

      {plan.terminal === "deferred" && (
        <div className={`${s.notice} ${s.noticeAbstain}`}>
          <b>Abstención registrada</b>
          θ no encontró margen que sostenga una especialización en la región {plan.region}:
          la diferencia con el segundo fue {plan.margin.toFixed(3)}, bajo el umbral. Corrió
          el fallback <code>{plan.pick}</code> con {exchange.unitIds.length} unidades.
          Queda anotado como abstención, no como elección.
        </div>
      )}
    </div>
  );
}
