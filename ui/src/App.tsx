import { useEffect, useRef, useState } from "react";
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
import ExplainDrawer from "./components/ExplainDrawer";
import ErrorBoundary from "./components/ErrorBoundary";
import { useMapo } from "./store";
import s from "./App.module.css";

export default function App() {
  const exchanges = useMapo((st) => st.exchanges);
  const units = useMapo((st) => st.units);
  const addToContext = useMapo((st) => st.addToContext);
  const [dragging, setDragging] = useState<string | null>(null);

  // Los tokens llegan abajo del fold y no se ven. Se sigue el final del stream
  // mientras haya algo streameando, pero SIN pelearle al usuario: si scrolleó para
  // arriba a leer una decisión anterior, se lo respeta.
  const streamRef = useRef<HTMLDivElement>(null);
  const streaming = useMapo((st) => st.exchanges.some((x) => x.streaming));
  const answerChars = useMapo((st) =>
    st.exchanges.reduce((n, x) => n + x.answer.length, 0),
  );
  const pinned = useRef(true);

  useEffect(() => {
    const el = streamRef.current;
    if (!el) return;
    const onScroll = () => {
      pinned.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
    };
    el.addEventListener("scroll", onScroll, { passive: true });
    return () => el.removeEventListener("scroll", onScroll);
  }, []);

  useEffect(() => {
    const el = streamRef.current;
    if (el && streaming && pinned.current) el.scrollTop = el.scrollHeight;
  }, [streaming, answerChars]);

  // Una pregunta nueva arranca arriba: lo primero que hay que ver es la decisión.
  const count = exchanges.length;
  useEffect(() => {
    if (!count) return;
    pinned.current = true;
    streamRef.current?.querySelector("article:last-of-type")?.scrollIntoView({
      block: "start",
      behavior: "smooth",
    });
  }, [count]);

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
            <div className={s.stream} ref={streamRef}>
              <ErrorBoundary>
                {exchanges.length === 0 ? (
                  <Blank />
                ) : (
                  exchanges.map((x) => <ExchangeView key={x.id} exchange={x} />)
                )}
              </ErrorBoundary>
            </div>
            <Composer />
          </main>

          <ContextTray />
        </div>
      </div>

      <ExplainDrawer />

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
