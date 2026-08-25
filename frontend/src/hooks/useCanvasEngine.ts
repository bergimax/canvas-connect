import { useCallback, useRef, useState } from "react";
import type { CanvasElement, CanvasOperation } from "@/lib/types";

export interface CanvasEngine {
  elements: CanvasElement[];
  selection: string[];
  setSelection: (ids: string[]) => void;
  add: (el: CanvasElement) => void;
  update: (id: string, patch: Partial<CanvasElement>, options?: { transient?: boolean }) => void;
  remove: (ids: string[]) => void;
  clear: () => void;
  replaceAll: (els: CanvasElement[]) => void;
  applyRemoteOps: (ops: CanvasOperation[]) => void;
  undo: () => void;
  redo: () => void;
  canUndo: boolean;
  canRedo: boolean;
  bringToFront: (ids: string[]) => void;
  sendToBack: (ids: string[]) => void;
  duplicate: (ids: string[]) => void;
}

export function useCanvasEngine(
  emit: (ops: CanvasOperation[]) => void,
  readOnly: () => boolean,
): CanvasEngine {
  const [elements, setElements] = useState<CanvasElement[]>([]);
  const [selection, setSelection] = useState<string[]>([]);
  const past = useRef<CanvasElement[][]>([]);
  const future = useRef<CanvasElement[][]>([]);
  const [, force] = useState(0);

  const pushHistory = useCallback((prev: CanvasElement[]) => {
    past.current.push(prev);
    if (past.current.length > 100) past.current.shift();
    future.current = [];
    force((n) => n + 1);
  }, []);

  const add = useCallback(
    (el: CanvasElement) => {
      if (readOnly()) return;
      setElements((prev) => {
        pushHistory(prev);
        return [...prev, el];
      });
      emit([{ op: "add", element: el }]);
    },
    [emit, pushHistory, readOnly],
  );

  const update = useCallback(
    (id: string, patch: Partial<CanvasElement>, options?: { transient?: boolean }) => {
      if (readOnly()) return;
      setElements((prev) => {
        if (!options?.transient) pushHistory(prev);
        return prev.map((e) =>
          e.id === id
            ? ({ ...e, ...patch, updated_at: new Date().toISOString() } as CanvasElement)
            : e,
        );
      });
      emit([{ op: "update", id, patch }]);
    },
    [emit, pushHistory, readOnly],
  );

  const remove = useCallback(
    (ids: string[]) => {
      if (readOnly() || ids.length === 0) return;
      setElements((prev) => {
        pushHistory(prev);
        return prev.filter(
          (e) =>
            !ids.includes(e.id) &&
            !(
              e.kind === "connector" &&
              (ids.includes(e.from.elementId ?? "") || ids.includes(e.to.elementId ?? ""))
            ),
        );
      });
      setSelection([]);
      emit(ids.map((id) => ({ op: "delete", id }) as CanvasOperation));
    },
    [emit, pushHistory, readOnly],
  );

  const clear = useCallback(() => {
    setElements((prev) => {
      pushHistory(prev);
      return [];
    });
    setSelection([]);
    emit([{ op: "clear" }]);
  }, [emit, pushHistory]);

  const replaceAll = useCallback((els: CanvasElement[]) => {
    setElements(els);
  }, []);

  const applyRemoteOps = useCallback((ops: CanvasOperation[]) => {
    setElements((prev) => {
      let next = prev;
      for (const op of ops) {
        if (op.op === "add")
          next = next.some((e) => e.id === op.element.id) ? next : [...next, op.element];
        else if (op.op === "update")
          next = next.map((e) => (e.id === op.id ? ({ ...e, ...op.patch } as CanvasElement) : e));
        else if (op.op === "delete") next = next.filter((e) => e.id !== op.id);
        else next = [];
      }
      return next;
    });
  }, []);

  const undo = useCallback(() => {
    setElements((prev) => {
      const last = past.current.pop();
      if (!last) return prev;
      future.current.push(prev);
      force((n) => n + 1);
      return last;
    });
  }, []);

  const redo = useCallback(() => {
    setElements((prev) => {
      const next = future.current.pop();
      if (!next) return prev;
      past.current.push(prev);
      force((n) => n + 1);
      return next;
    });
  }, []);

  const reorder = useCallback(
    (ids: string[], toFront: boolean) => {
      setElements((prev) => {
        pushHistory(prev);
        const max = Math.max(0, ...prev.map((e) => e.z));
        const min = Math.min(0, ...prev.map((e) => e.z));
        return prev.map((e) => (ids.includes(e.id) ? { ...e, z: toFront ? max + 1 : min - 1 } : e));
      });
    },
    [pushHistory],
  );

  const duplicate = useCallback(
    (ids: string[]) => {
      if (readOnly()) return;
      setElements((prev) => {
        pushHistory(prev);
        const copies = prev
          .filter((e) => ids.includes(e.id))
          .map(
            (e) => ({ ...e, id: crypto.randomUUID(), x: e.x + 24, y: e.y + 24 }) as CanvasElement,
          );
        emit(copies.map((element) => ({ op: "add", element }) as CanvasOperation));
        return [...prev, ...copies];
      });
    },
    [emit, pushHistory, readOnly],
  );

  return {
    elements,
    selection,
    setSelection,
    add,
    update,
    remove,
    clear,
    replaceAll,
    applyRemoteOps,
    undo,
    redo,
    canUndo: past.current.length > 0,
    canRedo: future.current.length > 0,
    bringToFront: (ids) => reorder(ids, true),
    sendToBack: (ids) => reorder(ids, false),
    duplicate,
  };
}
