import { useCallback, useMemo } from "react";
import { useDropzone } from "react-dropzone";
import { useDraggable } from "@dnd-kit/core";
import { useMapo, activeDocuments, activeUnits } from "../store";
import { formatBytes, formatTokens } from "../lib/tokens";
import { INGEST_STEPS, type DocumentRecord, type Unit } from "../types";
import s from "./WorkspacePanel.module.css";

export default function WorkspacePanel() {
  const workspaces = useMapo((st) => st.workspaces);
  const activeId = useMapo((st) => st.activeWorkspaceId);
  const setWorkspace = useMapo((st) => st.setWorkspace);
  const createWorkspace = useMapo((st) => st.createWorkspace);
  const ingestFiles = useMapo((st) => st.ingestFiles);
  const allDocuments = useMapo((st) => st.documents);
  const allUnits = useMapo((st) => st.units);

  const documents = useMemo(
    () => activeDocuments(allDocuments, activeId),
    [allDocuments, activeId],
  );
  const units = useMemo(() => activeUnits(allUnits, activeId), [allUnits, activeId]);

  const onDrop = useCallback((accepted: File[]) => ingestFiles(accepted), [ingestFiles]);
  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      "application/pdf": [".pdf"],
      "text/markdown": [".md"],
      "text/plain": [".txt"],
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [".docx"],
    },
  });

  function onSelect(value: string) {
    if (value !== "__new") return setWorkspace(value);
    const name = window.prompt("Nombre del workspace");
    if (name?.trim()) createWorkspace(name.trim());
  }

  const ingesting = documents.filter((d) => d.step < 5).length;

  return (
    <aside className={s.rail}>
      <div className={s.head}>
        <span className="eyebrow">Workspace</span>
        <select value={activeId} onChange={(e) => onSelect(e.target.value)}>
          {workspaces.map((w) => (
            <option key={w.id} value={w.id}>
              {w.name}
            </option>
          ))}
          <option value="__new">— crear workspace —</option>
        </select>
      </div>

      <div
        {...getRootProps({ className: `${s.drop} ${isDragActive ? s.dropOver : ""}` })}
      >
        <input {...getInputProps()} />
        <b>Soltá los documentos acá</b>
        <span>La ingesta arranca sola, en segundo plano</span>
      </div>

      <div className={s.scroll}>
        {documents.length > 0 && (
          <>
            <div className={s.section}>
              <span className="eyebrow">Ingesta</span>
              {ingesting > 0 && <span className={s.count}>{ingesting} en curso</span>}
            </div>
            {documents.map((d) => (
              <DocumentCard key={d.id} doc={d} />
            ))}
          </>
        )}

        <div className={s.section}>
          <span className="eyebrow">Unidades indexadas</span>
          {units.length > 0 && <span className={s.count}>{units.length}</span>}
        </div>

        {units.length === 0 ? (
          <p className={s.empty}>
            Todavía no hay nada indexado. Soltá un documento arriba y vas a ver qué
            decidió el sensor en cada archivo.
          </p>
        ) : (
          units.map((u) => <UnitRow key={u.id} unit={u} />)
        )}
      </div>
    </aside>
  );
}

function DocumentCard({ doc }: { doc: DocumentRecord }) {
  const removeDocument = useMapo((st) => st.removeDocument);
  const indexed = doc.step === 5;

  const line = indexed
    ? `${doc.collection} · ${doc.unitCount} unidades`
    : INGEST_STEPS[doc.step] ?? "en cola";

  return (
    <article className={`${s.doc} ${indexed ? s.docDone : ""}`}>
      <div className={s.docTop}>
        <span className={s.docName}>{doc.name}</span>
        <span className={s.docSize}>{formatBytes(doc.bytes)}</span>
        <button
          type="button"
          className={s.docKill}
          onClick={() => removeDocument(doc.id)}
          aria-label={`Quitar ${doc.name}`}
        >
          ×
        </button>
      </div>

      <div className={s.docState}>
        {line}
        {doc.sensor && <em>{doc.sensor}</em>}
      </div>

      <div className={s.steps} role="progressbar" aria-valuenow={doc.step} aria-valuemin={0} aria-valuemax={5}>
        {INGEST_STEPS.map((name, i) => (
          <i
            key={name}
            className={
              i < doc.step ? s.stepDone : i === doc.step ? s.stepActive : s.step
            }
            title={name}
          />
        ))}
      </div>
    </article>
  );
}

function UnitRow({ unit }: { unit: Unit }) {
  const addToContext = useMapo((st) => st.addToContext);
  const inContext = useMapo((st) => st.context.some((c) => c.unitId === unit.id));
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({ id: unit.id });

  return (
    <div
      ref={setNodeRef}
      className={`${s.unit} ${isDragging ? s.unitDragging : ""} ${inContext ? s.unitUsed : ""}`}
      {...listeners}
      {...attributes}
      onDoubleClick={() => addToContext(unit.id)}
    >
      <span className={s.grip} aria-hidden>
        ⠿
      </span>
      <span className={s.unitId}>{unit.id}</span>
      <span className={s.unitTitle}>{unit.title}</span>
      <span className={s.unitTokens}>{formatTokens(unit.tokens)}</span>
    </div>
  );
}
