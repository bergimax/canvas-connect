import { useCallback, useEffect, useRef, useState } from "react";
import type { BoxElement, CanvasElement, ConnectorElement, Participant, StrokeElement } from "@/lib/types";
import type { CanvasEngine } from "@/hooks/useCanvasEngine";
import type { Tool } from "./Toolbar";
import { PALETTE_INDEX } from "@/lib/palette";

export interface Viewport {
  x: number;
  y: number;
  scale: number;
}

const GRID = 24;
const snap = (v: number, on: boolean) => (on ? Math.round(v / GRID) * GRID : v);

export function centerOf(el: CanvasElement): { x: number; y: number } {
  if (el.kind === "connector") return { x: el.from.x, y: el.from.y };
  if (el.kind === "stroke") return { x: el.x, y: el.y };
  return { x: el.x + el.width / 2, y: el.y + el.height / 2 };
}

function anchorPoint(box: BoxElement, toward: { x: number; y: number }) {
  const cx = box.x + box.width / 2;
  const cy = box.y + box.height / 2;
  const dx = toward.x - cx;
  const dy = toward.y - cy;
  if (dx === 0 && dy === 0) return { x: cx, y: cy };
  const sx = box.width / 2 / Math.abs(dx || 1e-6);
  const sy = box.height / 2 / Math.abs(dy || 1e-6);
  const s = Math.min(sx, sy);
  return { x: cx + dx * s, y: cy + dy * s };
}

export function CanvasStage({
  engine,
  tool,
  setTool,
  readOnly,
  participants,
  selfId,
  viewport,
  setViewport,
  onCursor,
  strokeColor,
  strokeWidth,
  snapToGrid,
  showCursors,
}: {
  engine: CanvasEngine;
  tool: Tool;
  setTool: (t: Tool) => void;
  readOnly: boolean;
  participants: Participant[];
  selfId: string;
  viewport: Viewport;
  setViewport: (v: Viewport | ((v: Viewport) => Viewport)) => void;
  onCursor: (p: { x: number; y: number } | null) => void;
  strokeColor: string;
  strokeWidth: number;
  snapToGrid: boolean;
  showCursors: boolean;
}) {
  const svgRef = useRef<SVGSVGElement | null>(null);
  const [draft, setDraft] = useState<StrokeElement | null>(null);
  const [marquee, setMarquee] = useState<{ x: number; y: number; w: number; h: number } | null>(null);
  const [pendingConnector, setPendingConnector] = useState<{ fromId: string; x: number; y: number } | null>(null);
  const [editing, setEditing] = useState<string | null>(null);
  const drag = useRef<{ mode: "move" | "resize" | "pan" | "marquee" | null; start: { x: number; y: number }; origin: Record<string, { x: number; y: number; w?: number; h?: number }>; vp?: Viewport }>({
    mode: null,
    start: { x: 0, y: 0 },
    origin: {},
  });

  const toCanvas = useCallback(
    (clientX: number, clientY: number) => {
      const rect = svgRef.current?.getBoundingClientRect();
      if (!rect) return { x: 0, y: 0 };
      return {
        x: (clientX - rect.left - viewport.x) / viewport.scale,
        y: (clientY - rect.top - viewport.y) / viewport.scale,
      };
    },
    [viewport],
  );

  const boxes = engine.elements.filter((e): e is BoxElement => e.kind !== "stroke" && e.kind !== "connector");
  const connectors = engine.elements.filter((e): e is ConnectorElement => e.kind === "connector");
  const strokes = engine.elements.filter((e): e is StrokeElement => e.kind === "stroke");
  const byId = new Map(boxes.map((b) => [b.id, b]));

  const newBase = (x: number, y: number) => ({
    id: crypto.randomUUID(),
    x,
    y,
    z: engine.elements.length + 1,
    parent_id: null,
    created_by: selfId,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  });

  const createBoxAt = (kind: BoxElement["kind"], x: number, y: number, extra: Partial<BoxElement> = {}) => {
    const el: BoxElement = {
      ...newBase(snap(x, snapToGrid), snap(y, snapToGrid)),
      kind,
      width: extra.width ?? 168,
      height: extra.height ?? 84,
      label: extra.label ?? "",
      ...extra,
    } as BoxElement;
    engine.add(el);
    engine.setSelection([el.id]);
    setEditing(el.id);
    setTool("select");
  };

  /* --------------------------- pointer handling --------------------------- */

  const onPointerDown = (e: React.PointerEvent) => {
    if (e.button === 1 || tool === "pan" || (e.button === 0 && e.altKey)) {
      drag.current = { mode: "pan", start: { x: e.clientX, y: e.clientY }, origin: {}, vp: viewport };
      (e.currentTarget as Element).setPointerCapture(e.pointerId);
      return;
    }
    const p = toCanvas(e.clientX, e.clientY);
    const target = (e.target as Element).closest("[data-el-id]");
    const id = target?.getAttribute("data-el-id") ?? null;

    if (readOnly) {
      if (!id) engine.setSelection([]);
      else engine.setSelection([id]);
      return;
    }

    if (tool === "pen" || tool === "highlighter") {
      const stroke: StrokeElement = {
        ...newBase(0, 0),
        kind: "stroke",
        points: [p.x, p.y],
        color: strokeColor,
        width: tool === "highlighter" ? strokeWidth * 4 : strokeWidth,
        tool,
      };
      setDraft(stroke);
      (e.currentTarget as Element).setPointerCapture(e.pointerId);
      return;
    }

    if (tool === "eraser") {
      if (id) engine.remove([id]);
      return;
    }

    if (tool === "text") return createBoxAt("text", p.x, p.y, { width: 180, height: 40, label: "Text" });
    if (tool === "sticky")
      return createBoxAt("sticky", p.x, p.y, { width: 160, height: 140, label: "Note", color: "#f5a524" });
    if (tool === "rect") return createBoxAt("shape", p.x, p.y, { shape: "rect", label: "" });
    if (tool === "ellipse") return createBoxAt("shape", p.x, p.y, { shape: "ellipse", label: "" });

    if (tool === "connector") {
      if (id && byId.has(id)) {
        if (!pendingConnector) setPendingConnector({ fromId: id, x: p.x, y: p.y });
        else if (pendingConnector.fromId !== id) {
          const conn: ConnectorElement = {
            ...newBase(0, 0),
            kind: "connector",
            from: { elementId: pendingConnector.fromId, x: 0, y: 0 },
            to: { elementId: id, x: 0, y: 0 },
            style: "elbow",
            dashed: false,
            color: "#8fa3bf",
            strokeWidth: 2,
            arrowStart: false,
            arrowEnd: true,
          };
          engine.add(conn);
          setPendingConnector(null);
          setTool("select");
        }
      } else setPendingConnector(null);
      return;
    }

    // select tool
    if (id) {
      const already = engine.selection.includes(id);
      const next = e.shiftKey ? (already ? engine.selection.filter((s) => s !== id) : [...engine.selection, id]) : already ? engine.selection : [id];
      engine.setSelection(next);
      const handle = (e.target as Element).getAttribute("data-handle");
      const origin: Record<string, { x: number; y: number; w?: number; h?: number }> = {};
      for (const el of engine.elements)
        if (next.includes(el.id))
          origin[el.id] = { x: el.x, y: el.y, ...(el.kind !== "stroke" && el.kind !== "connector" ? { w: el.width, h: el.height } : {}) };
      drag.current = { mode: handle ? "resize" : "move", start: p, origin };
      (e.currentTarget as Element).setPointerCapture(e.pointerId);
    } else {
      engine.setSelection([]);
      drag.current = { mode: "marquee", start: p, origin: {} };
      setMarquee({ x: p.x, y: p.y, w: 0, h: 0 });
      (e.currentTarget as Element).setPointerCapture(e.pointerId);
    }
  };

  const onPointerMove = (e: React.PointerEvent) => {
    const p = toCanvas(e.clientX, e.clientY);
    onCursor(p);

    if (drag.current.mode === "pan" && drag.current.vp) {
      const vp = drag.current.vp;
      setViewport({ ...vp, x: vp.x + (e.clientX - drag.current.start.x), y: vp.y + (e.clientY - drag.current.start.y) });
      return;
    }
    if (draft) {
      setDraft({ ...draft, points: [...draft.points, p.x, p.y] });
      return;
    }
    if (pendingConnector) {
      setPendingConnector({ ...pendingConnector, x: p.x, y: p.y });
      return;
    }
    if (drag.current.mode === "marquee") {
      const s = drag.current.start;
      setMarquee({ x: Math.min(s.x, p.x), y: Math.min(s.y, p.y), w: Math.abs(p.x - s.x), h: Math.abs(p.y - s.y) });
      return;
    }
    if (drag.current.mode === "move") {
      const dx = p.x - drag.current.start.x;
      const dy = p.y - drag.current.start.y;
      for (const [id, o] of Object.entries(drag.current.origin))
        engine.update(id, { x: snap(o.x + dx, snapToGrid), y: snap(o.y + dy, snapToGrid) }, { transient: true });
      return;
    }
    if (drag.current.mode === "resize") {
      const dx = p.x - drag.current.start.x;
      const dy = p.y - drag.current.start.y;
      for (const [id, o] of Object.entries(drag.current.origin))
        if (o.w !== undefined && o.h !== undefined)
          engine.update(
            id,
            { width: Math.max(60, snap(o.w + dx, snapToGrid)), height: Math.max(32, snap(o.h + dy, snapToGrid)) } as Partial<CanvasElement>,
            { transient: true },
          );
    }
  };

  const onPointerUp = () => {
    if (draft) {
      if (draft.points.length > 4) engine.add(draft);
      setDraft(null);
    }
    if (marquee) {
      const hits = boxes
        .filter((b) => b.x >= marquee.x && b.y >= marquee.y && b.x + b.width <= marquee.x + marquee.w && b.y + b.height <= marquee.y + marquee.h)
        .map((b) => b.id);
      engine.setSelection(hits);
      setMarquee(null);
    }
    drag.current = { mode: null, start: { x: 0, y: 0 }, origin: {} };
  };

  const onWheel = (e: React.WheelEvent) => {
    if (e.ctrlKey || e.metaKey) {
      e.preventDefault();
      const rect = svgRef.current?.getBoundingClientRect();
      if (!rect) return;
      const factor = Math.exp(-e.deltaY / 300);
      setViewport((vp) => {
        const scale = Math.min(3, Math.max(0.2, vp.scale * factor));
        const mx = e.clientX - rect.left;
        const my = e.clientY - rect.top;
        return { scale, x: mx - ((mx - vp.x) / vp.scale) * scale, y: my - ((my - vp.y) / vp.scale) * scale };
      });
    } else {
      setViewport((vp) => ({ ...vp, x: vp.x - e.deltaX, y: vp.y - e.deltaY }));
    }
  };

  /* ------------------------------ shortcuts ------------------------------- */
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement;
      if (t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.isContentEditable)) return;
      const mod = e.metaKey || e.ctrlKey;
      if (mod && e.key.toLowerCase() === "z") {
        e.preventDefault();
        e.shiftKey ? engine.redo() : engine.undo();
      } else if (mod && e.key.toLowerCase() === "d") {
        e.preventDefault();
        engine.duplicate(engine.selection);
      } else if (e.key === "Delete" || e.key === "Backspace") {
        if (engine.selection.length) {
          e.preventDefault();
          engine.remove(engine.selection);
        }
      } else if (e.key === "Escape") {
        engine.setSelection([]);
        setPendingConnector(null);
      } else if (!mod) {
        const map: Record<string, Tool> = { v: "select", h: "pan", p: "pen", m: "highlighter", e: "eraser", t: "text", n: "sticky", c: "connector", r: "rect", o: "ellipse" };
        const next = map[e.key.toLowerCase()];
        if (next) setTool(next);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [engine, setTool]);

  /* ------------------------------- rendering ------------------------------ */

  const renderConnector = (c: ConnectorElement) => {
    const a = c.from.elementId ? byId.get(c.from.elementId) : undefined;
    const b = c.to.elementId ? byId.get(c.to.elementId) : undefined;
    const pa = a ? anchorPoint(a, b ? centerOf(b) : c.to) : c.from;
    const pb = b ? anchorPoint(b, a ? centerOf(a) : c.from) : c.to;
    let d: string;
    if (c.style === "straight") d = `M ${pa.x} ${pa.y} L ${pb.x} ${pb.y}`;
    else if (c.style === "curved") {
      const mx = (pa.x + pb.x) / 2;
      d = `M ${pa.x} ${pa.y} C ${mx} ${pa.y}, ${mx} ${pb.y}, ${pb.x} ${pb.y}`;
    } else d = `M ${pa.x} ${pa.y} L ${(pa.x + pb.x) / 2} ${pa.y} L ${(pa.x + pb.x) / 2} ${pb.y} L ${pb.x} ${pb.y}`;
    const selected = engine.selection.includes(c.id);
    return (
      <g key={c.id} data-el-id={c.id}>
        <path d={d} fill="none" stroke="transparent" strokeWidth={14} style={{ cursor: "pointer" }} />
        <path
          d={d}
          fill="none"
          stroke={selected ? "var(--color-primary)" : c.color}
          strokeWidth={c.strokeWidth}
          strokeDasharray={c.dashed ? "8 6" : undefined}
          markerEnd={c.arrowEnd ? "url(#arrow)" : undefined}
          markerStart={c.arrowStart ? "url(#arrow-start)" : undefined}
        />
        {c.label ? (
          <text
            x={(pa.x + pb.x) / 2}
            y={(pa.y + pb.y) / 2 - 6}
            textAnchor="middle"
            fontSize={12}
            fill="var(--color-muted-foreground)"
            style={{ paintOrder: "stroke", stroke: "var(--color-canvas)", strokeWidth: 6 }}
          >
            {c.label}
          </text>
        ) : null}
      </g>
    );
  };

  const renderBox = (b: BoxElement) => {
    const selected = engine.selection.includes(b.id);
    const item = b.componentType ? PALETTE_INDEX[b.componentType] : undefined;
    const isSticky = b.kind === "sticky";
    const isText = b.kind === "text";
    const fill = isSticky ? (b.color ?? "#f5a524") : isText ? "transparent" : "var(--color-surface)";
    return (
      <g key={b.id} data-el-id={b.id} style={{ cursor: readOnly ? "default" : "move" }}>
        {b.shape === "ellipse" ? (
          <ellipse
            cx={b.x + b.width / 2}
            cy={b.y + b.height / 2}
            rx={b.width / 2}
            ry={b.height / 2}
            fill={fill}
            stroke={selected ? "var(--color-primary)" : "var(--color-border)"}
            strokeWidth={selected ? 2 : 1.5}
          />
        ) : (
          <rect
            x={b.x}
            y={b.y}
            width={b.width}
            height={b.height}
            rx={b.componentType === "boundary" ? 12 : isSticky ? 4 : 10}
            fill={b.componentType === "boundary" ? "transparent" : fill}
            fillOpacity={isSticky ? 0.9 : 1}
            stroke={selected ? "var(--color-primary)" : b.componentType === "boundary" ? "var(--color-accent)" : "var(--color-border)"}
            strokeDasharray={b.componentType === "boundary" ? "10 6" : undefined}
            strokeWidth={selected ? 2 : 1.5}
          />
        )}
        <foreignObject x={b.x} y={b.y} width={b.width} height={b.height} style={{ pointerEvents: editing === b.id ? "auto" : "none" }}>
          <div
            className={`flex size-full flex-col items-center justify-center gap-1 px-2 text-center ${isSticky ? "text-[#20242c]" : "text-surface-foreground"}`}
          >
            {item ? <IconBadge icon={item.icon} sticky={isSticky} /> : null}
            {editing === b.id ? (
              <input
                autoFocus
                defaultValue={b.label}
                onBlur={(e) => {
                  engine.update(b.id, { label: e.target.value } as Partial<CanvasElement>);
                  setEditing(null);
                }}
                onKeyDown={(e) => {
                  if (e.key === "Enter") (e.target as HTMLInputElement).blur();
                }}
                className="w-full rounded bg-background/70 px-1 text-center text-[13px] outline-none"
              />
            ) : (
              <span className={`text-[13px] font-medium leading-tight ${isText ? "text-base" : ""}`}>{b.label}</span>
            )}
            {b.description ? <span className="text-[11px] text-muted-foreground">{b.description}</span> : null}
          </div>
        </foreignObject>
        {selected && !readOnly ? (
          <rect
            data-handle="se"
            x={b.x + b.width - 5}
            y={b.y + b.height - 5}
            width={10}
            height={10}
            fill="var(--color-primary)"
            style={{ cursor: "nwse-resize" }}
          />
        ) : null}
      </g>
    );
  };

  const strokePath = (s: StrokeElement) => {
    let d = "";
    for (let i = 0; i < s.points.length; i += 2) d += `${i === 0 ? "M" : "L"} ${s.points[i]} ${s.points[i + 1]} `;
    return d;
  };

  return (
    <svg
      ref={svgRef}
      className="size-full touch-none select-none bg-canvas"
      role="application"
      aria-label="Collaborative system design canvas"
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
      onWheel={onWheel}
      onDoubleClick={(e) => {
        const id = (e.target as Element).closest("[data-el-id]")?.getAttribute("data-el-id");
        if (id && !readOnly) setEditing(id);
      }}
      onDragOver={(e) => e.preventDefault()}
      onDrop={(e) => {
        const type = e.dataTransfer.getData("application/x-sdi-component");
        if (!type || readOnly) return;
        const item = PALETTE_INDEX[type];
        const p = toCanvas(e.clientX, e.clientY);
        if (item)
          createBoxAt("component", p.x - item.width / 2, p.y - item.height / 2, {
            componentType: item.type,
            label: item.label,
            width: item.width,
            height: item.height,
          });
      }}
    >
      <defs>
        <pattern id="grid" width={GRID} height={GRID} patternUnits="userSpaceOnUse">
          <path d={`M ${GRID} 0 L 0 0 0 ${GRID}`} fill="none" stroke="var(--color-canvas-grid)" strokeWidth="1" opacity="0.4" />
        </pattern>
        <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
          <path d="M 0 0 L 10 5 L 0 10 z" fill="#8fa3bf" />
        </marker>
        <marker id="arrow-start" viewBox="0 0 10 10" refX="1" refY="5" markerWidth="7" markerHeight="7" orient="auto">
          <path d="M 10 0 L 0 5 L 10 10 z" fill="#8fa3bf" />
        </marker>
      </defs>

      <rect width="100%" height="100%" fill="var(--color-canvas)" />
      <g transform={`translate(${viewport.x} ${viewport.y}) scale(${viewport.scale})`}>
        <rect x={-10000} y={-10000} width={20000} height={20000} fill="url(#grid)" />
        {connectors.map(renderConnector)}
        {[...boxes].sort((a, b) => a.z - b.z).map(renderBox)}
        {strokes.map((s) => (
          <path
            key={s.id}
            data-el-id={s.id}
            d={strokePath(s)}
            fill="none"
            stroke={s.color}
            strokeWidth={s.width}
            strokeOpacity={s.tool === "highlighter" ? 0.35 : 1}
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        ))}
        {draft ? (
          <path
            d={strokePath(draft)}
            fill="none"
            stroke={draft.color}
            strokeWidth={draft.width}
            strokeOpacity={draft.tool === "highlighter" ? 0.35 : 1}
            strokeLinecap="round"
          />
        ) : null}
        {pendingConnector && byId.get(pendingConnector.fromId) ? (
          <line
            x1={centerOf(byId.get(pendingConnector.fromId)!).x}
            y1={centerOf(byId.get(pendingConnector.fromId)!).y}
            x2={pendingConnector.x}
            y2={pendingConnector.y}
            stroke="var(--color-primary)"
            strokeDasharray="6 6"
            strokeWidth={2}
          />
        ) : null}
        {marquee ? (
          <rect
            x={marquee.x}
            y={marquee.y}
            width={marquee.w}
            height={marquee.h}
            fill="var(--color-primary)"
            fillOpacity={0.08}
            stroke="var(--color-primary)"
            strokeDasharray="4 4"
          />
        ) : null}
        {showCursors
          ? participants
              .filter((p) => p.id !== selfId && p.cursor)
              .map((p) => (
                <g key={p.id} transform={`translate(${p.cursor!.x} ${p.cursor!.y})`}>
                  <path d="M 0 0 L 0 14 L 4 11 L 7 17 L 10 15 L 7 9 L 12 9 Z" fill={p.color} />
                  <rect x={12} y={12} width={p.display_name.length * 7 + 12} height={18} rx={4} fill={p.color} />
                  <text x={18} y={25} fontSize={11} fill="#10161f">
                    {p.display_name}
                  </text>
                </g>
              ))
          : null}
      </g>
    </svg>
  );
}

function IconBadge({ icon, sticky }: { icon: string; sticky: boolean }) {
  return <ComponentIcon name={icon} className={`size-4 ${sticky ? "text-[#20242c]" : "text-primary"}`} />;
}
