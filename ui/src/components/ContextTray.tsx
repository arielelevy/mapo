import { useMemo } from "react";
import { useDroppable } from "@dnd-kit/core";
import { useMapo, contextUnits } from "../store";
import {
  assuranceStrikes,
  feasibilityStrikes,
  survivorsOf,
  worstCaseCost,
} from "../lib/feasibility";
import { formatTokens } from "../lib/tokens";
import { PARADIGMS } from "../types";
import s from "./ContextTray.module.css";

export default function ContextTray() {
  const context = useMapo((st) => st.context);
  const units = useMapo((st) => st.units);
  const entries = useMemo(() => contextUnits(context, units), [context, units]);
  const assurance = useMapo((st) => st.assurance);
  const budget = useMapo((st) => st.budget);
  const toggleIncluded = useMapo((st) => st.toggleIncluded);
  const removeFromContext = useMapo((st) => st.removeFromContext);
  const setAllIncluded = useMapo((st) => st.setAllIncluded);
  const clearContext = useMapo((st) => st.clearContext);

  const { setNodeRef, isOver } = useDroppable({ id: "context-tray" });

  const included = entries.filter((e) => e.included);
  const contextTokens = included.reduce((n, e) => n + e.tokens, 0);

  // La factibilidad es aritmética: se recalcula con cada toggle, sin tocar el modelo.
  const preview = useMemo(() => {
    const feas = feasibilityStrikes({
      contextTokens,
      unitCount: included.length,
      budget,
    });
    const afterFeas = survivorsOf(feas);
    const dial = assuranceStrikes(afterFeas, assurance);
    const admissible = survivorsOf(dial);
    return {
      strikes: [...feas.filter((x) => x.reason), ...dial.filter((x) => x.reason)],
      admissible,
      worst: worstCaseCost(admissible, contextTokens, included.length),
    };
  }, [contextTokens, included.length, budget, assurance]);

  const over = preview.worst > budget;
  const fill = Math.min(100, (preview.worst / budget) * 100);

  return (
    <aside className={s.tray}>
      <div className={s.head}>
        <span className="eyebrow">Contexto</span>
        {entries.length > 0 && (
          <span className={s.count}>
            {included.length} de {entries.length} · {formatTokens(contextTokens)}
          </span>
        )}
      </div>

      <div
        ref={setNodeRef}
        className={`${s.zone} ${isOver ? s.zoneOver : ""} ${entries.length === 0 ? s.zoneEmpty : ""}`}
      >
        {entries.length === 0 ? (
          <p className={s.hint}>
            Arrastrá unidades desde el workspace. Sólo lo que esté acá y encendido entra
            en la pregunta.
          </p>
        ) : (
          entries.map((e) => (
            <div key={e.id} className={`${s.row} ${e.included ? "" : s.rowOff}`}>
              <input
                type="checkbox"
                checked={e.included}
                onChange={() => toggleIncluded(e.id)}
                aria-label={`Incluir ${e.id}`}
              />
              <span className={s.rowId}>{e.id}</span>
              <span className={s.rowTitle}>{e.title}</span>
              <span className={s.rowTokens}>{formatTokens(e.tokens)}</span>
              <button
                type="button"
                className={s.rowKill}
                onClick={() => removeFromContext(e.id)}
                aria-label={`Sacar ${e.id} del contexto`}
              >
                ×
              </button>
            </div>
          ))
        )}
      </div>

      {entries.length > 0 && (
        <div className={s.bulk}>
          <button type="button" onClick={() => setAllIncluded(true)}>
            Encender todo
          </button>
          <button type="button" onClick={() => setAllIncluded(false)}>
            Apagar todo
          </button>
          <button type="button" onClick={clearContext}>
            Vaciar
          </button>
        </div>
      )}

      {/* ── presupuesto ─────────────────────────────────────────────────── */}
      <div className={s.block}>
        <span className="eyebrow">Presupuesto</span>
        <div className={s.meterRow}>
          <span>peor caso admisible</span>
          <b className={over ? s.overBudget : undefined}>
            {formatTokens(Math.round(preview.worst))} / {formatTokens(budget)}
          </b>
        </div>
        <div className={s.meter}>
          <i style={{ width: `${fill}%` }} data-over={over} />
        </div>
      </div>

      {/* ── el pago de curar el contexto ────────────────────────────────── */}
      <div className={s.block}>
        <span className="eyebrow">Qué queda en juego</span>
        <p className={s.lead}>
          <b>{preview.admissible.length}</b> de {PARADIGMS.length} paradigmas admisibles
          con esta selección.
        </p>

        {preview.strikes.length > 0 && (
          <ul className={s.strikes}>
            {preview.strikes.map((x) => (
              <li key={x.paradigm}>
                <span className={s.strikeName}>{x.paradigm}</span>
                <span className={s.strikeWhy}>{x.reason}</span>
              </li>
            ))}
          </ul>
        )}

        <p className={s.footnote}>
          Vista previa aritmética, calculada acá. El veredicto que vale lo devuelve el
          motor.
        </p>
      </div>
    </aside>
  );
}
