import { useMapo } from "../store";
import type { Assurance } from "../types";
import s from "./TopBar.module.css";

const DIALS: { value: Assurance; label: string }[] = [
  { value: "A0", label: "A0 · sin piso" },
  { value: "A1", label: "A1 · básico" },
  { value: "A2", label: "A2 · observado" },
  { value: "A3", label: "A3 · sellado" },
];

export default function TopBar() {
  const assurance = useMapo((st) => st.assurance);
  const budget = useMapo((st) => st.budget);
  const live = useMapo((st) => st.live);
  const setAssurance = useMapo((st) => st.setAssurance);
  const setBudget = useMapo((st) => st.setBudget);
  const toggleLive = useMapo((st) => st.toggleLive);

  return (
    <header className={s.bar}>
      <div className={s.brand}>
        <b>MAPO</b>
        <span>consola</span>
      </div>

      <label className={s.field}>
        <span className="eyebrow">Garantía</span>
        <select
          value={assurance}
          onChange={(e) => setAssurance(e.target.value as Assurance)}
        >
          {DIALS.map((d) => (
            <option key={d.value} value={d.value}>
              {d.label}
            </option>
          ))}
        </select>
      </label>

      <label className={s.field}>
        <span className="eyebrow">Presupuesto</span>
        <input
          type="number"
          value={budget}
          min={2000}
          step={1000}
          onChange={(e) => setBudget(Math.max(2000, Number(e.target.value) || 2000))}
          style={{ width: 92 }}
        />
      </label>

      <div className={s.spacer} />

      <button
        type="button"
        className={s.mode}
        data-live={live}
        onClick={toggleLive}
        title={
          live
            ? "Apunta a POST /v1/answer, que es una API PROPUESTA: el motor de hoy no streamea y recibe los textos, no ids de unidades"
            : "Trazas generadas local, sin motor y sin gastar tokens"
        }
      >
        <i className={s.dot} />
        {/* No decir "/v1/answer" a secas: implicaría que existe. */}
        {live ? "motor · API propuesta" : "demo · sin motor"}
      </button>
    </header>
  );
}
