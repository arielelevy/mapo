import { useState } from "react";
import {
  DndContext,
  DragOverlay,
  PointerSensor,
  KeyboardSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
  type DragStartEvent,
} from "@dnd-kit/core";
import TopBar from "./components/TopBar";
import WorkspacePanel from "./components/WorkspacePanel";
import ContextTray from "./components/ContextTray";
import Composer from "./components/Composer";
import ExchangeView from "./components/ExchangeView";
import Blank from "./components/Blank";
import { useMapo } from "./store";
import s from "./App.module.css";

export default function App() {
  const exchanges = useMapo((st) => st.exchanges);
  const units = useMapo((st) => st.units);
  const addToContext = useMapo((st) => st.addToContext);
  const [dragging, setDragging] = useState<string | null>(null);

  // El teclado tiene que poder hacer lo mismo que el puntero: por eso dnd-kit y no
  // el drag-and-drop nativo, que no es operable sin mouse.
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 4 } }),
    useSensor(KeyboardSensor),
  );

  function onDragStart(e: DragStartEvent) {
    setDragging(String(e.active.id));
  }

  function onDragEnd(e: DragEndEvent) {
    setDragging(null);
    if (e.over?.id === "context-tray") addToContext(String(e.active.id));
  }

  const draggedUnit = units.find((u) => u.id === dragging);

  return (
    <DndContext sensors={sensors} onDragStart={onDragStart} onDragEnd={onDragEnd}>
      <div className={s.shell}>
        <TopBar />
        <div className={s.body}>
          <WorkspacePanel />

          <main className={s.main}>
            <div className={s.stream}>
              {exchanges.length === 0 ? (
                <Blank />
              ) : (
                exchanges.map((x) => <ExchangeView key={x.id} exchange={x} />)
              )}
            </div>
            <Composer />
          </main>

          <ContextTray />
        </div>
      </div>

      <DragOverlay dropAnimation={null}>
        {draggedUnit ? (
          <div className={s.ghost}>
            <span className={s.ghostId}>{draggedUnit.id}</span>
            <span className={s.ghostTitle}>{draggedUnit.title}</span>
          </div>
        ) : null}
      </DragOverlay>
    </DndContext>
  );
}
