import { useRef, useState } from "react";
import { useMapo, type RequestFlags } from "../store";
import s from "./Composer.module.css";

export default function Composer() {
  const [text, setText] = useState("");
  const ref = useRef<HTMLTextAreaElement>(null);
  // Sólo hace falta el conteo, así que se deriva un número — no un array nuevo.
  const included = useMapo((st) => st.context.filter((c) => c.included).length);
  const running = useMapo((st) => st.running);
  const ask = useMapo((st) => st.ask);
  const cancel = useMapo((st) => st.cancel);

  const ready = text.trim().length > 0 && included > 0 && !running;

  function grow() {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 168) + "px";
  }

  function submit() {
    if (!ready) return;
    const q = text.trim();
    setText("");
    queueMicrotask(grow);
    void ask(q);
  }

  return (
    <div className={s.composer}>
      <div className={s.wrap}>
        <div className={s.box}>
          <textarea
            ref={ref}
            rows={1}
            value={text}
            placeholder="Preguntá sobre las unidades que pusiste en el contexto…"
            onChange={(e) => {
              setText(e.target.value);
              grow();
            }}
            onKeyDown={(e) => {
              if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
                e.preventDefault();
                submit();
              }
            }}
          />
          {/* Lo declara quien pregunta. No se infiere del texto: el motor lo asienta
              como COMPUTED y una conjetura ahí rompe la garantía. */}
          <div className={s.flags}>
            <span className="eyebrow">Declarás</span>
            <Flag k="irreversible" label="irreversible" />
            <Flag k="sharedWrites" label="escrituras compartidas" />
            <Flag k="regulated" label="regulado" />
          </div>

          <div className={s.foot}>
            <span className={s.hint}>
              {included === 0
                ? "El contexto está vacío. Arrastrá al menos una unidad."
                : `${included} unidad${included > 1 ? "es" : ""} en contexto · ⌘↵ para enviar`}
            </span>
            {running ? (
              <button type="button" className={s.cancel} onClick={cancel}>
                Cancelar
              </button>
            ) : (
              <button type="button" className={s.send} disabled={!ready} onClick={submit}>
                Decidir y ejecutar
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function Flag({ k, label }: { k: keyof RequestFlags; label: string }) {
  const on = useMapo((st) => st.flags[k]);
  const setFlag = useMapo((st) => st.setFlag);
  return (
    <label className={`${s.flag} ${on ? s.flagOn : ""}`}>
      <input type="checkbox" checked={on} onChange={(e) => setFlag(k, e.target.checked)} />
      {label}
    </label>
  );
}
