import type { BoxElement, CanvasElement, ConnectorElement, StrokeElement } from "@/lib/types";
import type { CanvasEngine } from "@/hooks/useCanvasEngine";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { ArrowLeftRight, BringToFront, Copy, SendToBack, Trash2 } from "lucide-react";

const SWATCHES = ["#3dd6c4", "#f5a524", "#7aa2f7", "#e5637d", "#9ece6a", "#8fa3bf"];

export function PropertiesPanel({
  engine,
  prompt,
  readOnly,
}: {
  engine: CanvasEngine;
  prompt: string;
  readOnly: boolean;
}) {
  const selected = engine.elements.filter((e) => engine.selection.includes(e.id));

  if (selected.length === 0) {
    return (
      <div className="flex h-full flex-col gap-3 p-4">
        <h2 className="text-sm font-semibold uppercase tracking-[0.14em] text-muted-foreground">Interview prompt</h2>
        <p className="whitespace-pre-wrap text-sm leading-relaxed text-surface-foreground">
          {prompt || "No prompt provided for this interview."}
        </p>
        <Separator className="my-2" />
        <p className="text-xs text-muted-foreground">
          Select an element to edit its properties. Canvas activity is saved automatically.
        </p>
      </div>
    );
  }

  const single = selected.length === 1 ? selected[0]! : null;
  const set = (patch: Partial<CanvasElement>) => single && engine.update(single.id, patch);

  return (
    <div className="flex h-full flex-col gap-4 overflow-y-auto p-4">
      <h2 className="text-sm font-semibold uppercase tracking-[0.14em] text-muted-foreground">
        {selected.length > 1 ? `${selected.length} elements` : "Element"}
      </h2>

      {single && single.kind !== "stroke" && single.kind !== "connector" ? (
        <BoxProps el={single as BoxElement} set={set} readOnly={readOnly} />
      ) : null}

      {single && single.kind === "connector" ? <ConnectorProps el={single} set={set} readOnly={readOnly} /> : null}

      {single && single.kind === "stroke" ? <StrokeProps el={single} set={set} readOnly={readOnly} /> : null}

      <Separator />
      <div className="grid grid-cols-2 gap-2">
        <Button variant="secondary" size="sm" disabled={readOnly} onClick={() => engine.duplicate(engine.selection)}>
          <Copy /> Duplicate
        </Button>
        <Button variant="secondary" size="sm" disabled={readOnly} onClick={() => engine.bringToFront(engine.selection)}>
          <BringToFront /> Front
        </Button>
        <Button variant="secondary" size="sm" disabled={readOnly} onClick={() => engine.sendToBack(engine.selection)}>
          <SendToBack /> Back
        </Button>
        <Button variant="destructive" size="sm" disabled={readOnly} onClick={() => engine.remove(engine.selection)}>
          <Trash2 /> Delete
        </Button>
      </div>
    </div>
  );
}

function BoxProps({ el, set, readOnly }: { el: BoxElement; set: (p: Partial<CanvasElement>) => void; readOnly: boolean }) {
  return (
    <div className="space-y-3">
      <div className="space-y-1.5">
        <Label htmlFor="label">Label</Label>
        <Input id="label" disabled={readOnly} defaultValue={el.label} onBlur={(e) => set({ label: e.target.value } as Partial<CanvasElement>)} />
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="desc">Description</Label>
        <Textarea id="desc" rows={2} disabled={readOnly} defaultValue={el.description ?? ""} onBlur={(e) => set({ description: e.target.value } as Partial<CanvasElement>)} />
      </div>
      <div className="grid grid-cols-2 gap-2">
        <div className="space-y-1.5">
          <Label htmlFor="w">Width</Label>
          <Input id="w" type="number" disabled={readOnly} value={Math.round(el.width)} onChange={(e) => set({ width: Math.max(60, Number(e.target.value)) } as Partial<CanvasElement>)} />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="h">Height</Label>
          <Input id="h" type="number" disabled={readOnly} value={Math.round(el.height)} onChange={(e) => set({ height: Math.max(32, Number(e.target.value)) } as Partial<CanvasElement>)} />
        </div>
      </div>
      {el.kind === "sticky" ? <Swatches value={el.color ?? "#f5a524"} onChange={(c) => set({ color: c } as Partial<CanvasElement>)} disabled={readOnly} /> : null}
    </div>
  );
}

function ConnectorProps({ el, set, readOnly }: { el: ConnectorElement; set: (p: Partial<CanvasElement>) => void; readOnly: boolean }) {
  return (
    <div className="space-y-3">
      <div className="space-y-1.5">
        <Label htmlFor="clabel">Label</Label>
        <Input id="clabel" disabled={readOnly} defaultValue={el.label ?? ""} placeholder="HTTPS, events, read/write" onBlur={(e) => set({ label: e.target.value } as Partial<CanvasElement>)} />
      </div>
      <div className="space-y-1.5">
        <Label>Style</Label>
        <div className="grid grid-cols-3 gap-1.5">
          {(["straight", "elbow", "curved"] as const).map((s) => (
            <Button key={s} size="sm" disabled={readOnly} variant={el.style === s ? "default" : "secondary"} onClick={() => set({ style: s } as Partial<CanvasElement>)}>
              {s}
            </Button>
          ))}
        </div>
      </div>
      <div className="grid grid-cols-3 gap-1.5">
        <Button size="sm" disabled={readOnly} variant={el.dashed ? "default" : "secondary"} onClick={() => set({ dashed: !el.dashed } as Partial<CanvasElement>)}>
          Dashed
        </Button>
        <Button size="sm" disabled={readOnly} variant={el.arrowStart ? "default" : "secondary"} onClick={() => set({ arrowStart: !el.arrowStart } as Partial<CanvasElement>)}>
          <ArrowLeftRight /> Start
        </Button>
        <Button size="sm" disabled={readOnly} variant={el.arrowEnd ? "default" : "secondary"} onClick={() => set({ arrowEnd: !el.arrowEnd } as Partial<CanvasElement>)}>
          End
        </Button>
      </div>
      <WidthPicker value={el.strokeWidth} onChange={(w) => set({ strokeWidth: w } as Partial<CanvasElement>)} disabled={readOnly} />
      <Swatches value={el.color} onChange={(c) => set({ color: c } as Partial<CanvasElement>)} disabled={readOnly} />
    </div>
  );
}

function StrokeProps({ el, set, readOnly }: { el: StrokeElement; set: (p: Partial<CanvasElement>) => void; readOnly: boolean }) {
  return (
    <div className="space-y-3">
      <p className="text-xs text-muted-foreground">Freehand {el.tool} stroke — {el.points.length / 2} points</p>
      <WidthPicker value={el.width} onChange={(w) => set({ width: w } as Partial<CanvasElement>)} disabled={readOnly} />
      <Swatches value={el.color} onChange={(c) => set({ color: c } as Partial<CanvasElement>)} disabled={readOnly} />
    </div>
  );
}

function Swatches({ value, onChange, disabled }: { value: string; onChange: (c: string) => void; disabled: boolean }) {
  return (
    <div className="space-y-1.5">
      <Label>Color</Label>
      <div className="flex gap-1.5">
        {SWATCHES.map((c) => (
          <button
            key={c}
            type="button"
            disabled={disabled}
            aria-label={`Color ${c}`}
            aria-pressed={value === c}
            onClick={() => onChange(c)}
            style={{ backgroundColor: c }}
            className={`size-6 rounded-full border-2 ${value === c ? "border-foreground" : "border-transparent"}`}
          />
        ))}
      </div>
    </div>
  );
}

function WidthPicker({ value, onChange, disabled }: { value: number; onChange: (w: number) => void; disabled: boolean }) {
  return (
    <div className="space-y-1.5">
      <Label>Line width</Label>
      <div className="grid grid-cols-3 gap-1.5">
        {[2, 4, 8].map((w) => (
          <Button key={w} size="sm" disabled={disabled} variant={value === w ? "default" : "secondary"} onClick={() => onChange(w)}>
            {w}px
          </Button>
        ))}
      </div>
    </div>
  );
}
