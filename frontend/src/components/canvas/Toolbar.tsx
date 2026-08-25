import {
  Eraser,
  Hand,
  Highlighter,
  MousePointer2,
  Pen,
  Spline,
  StickyNote,
  Type,
  Circle,
  Square,
} from "lucide-react";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

export type Tool =
  | "select"
  | "pan"
  | "pen"
  | "highlighter"
  | "eraser"
  | "text"
  | "sticky"
  | "connector"
  | "rect"
  | "ellipse";

const TOOLS: { tool: Tool; label: string; icon: typeof Pen; shortcut: string }[] = [
  { tool: "select", label: "Select", icon: MousePointer2, shortcut: "V" },
  { tool: "pan", label: "Pan", icon: Hand, shortcut: "H" },
  { tool: "pen", label: "Pen", icon: Pen, shortcut: "P" },
  { tool: "highlighter", label: "Highlighter", icon: Highlighter, shortcut: "M" },
  { tool: "eraser", label: "Eraser", icon: Eraser, shortcut: "E" },
  { tool: "text", label: "Text", icon: Type, shortcut: "T" },
  { tool: "sticky", label: "Sticky note", icon: StickyNote, shortcut: "N" },
  { tool: "connector", label: "Connector", icon: Spline, shortcut: "C" },
  { tool: "rect", label: "Rectangle", icon: Square, shortcut: "R" },
  { tool: "ellipse", label: "Ellipse", icon: Circle, shortcut: "O" },
];

export function Toolbar({
  tool,
  setTool,
  disabled,
}: {
  tool: Tool;
  setTool: (t: Tool) => void;
  disabled: boolean;
}) {
  return (
    <div
      className="flex w-14 flex-col items-center gap-1 border-r border-border bg-sidebar py-3"
      role="toolbar"
      aria-label="Canvas tools"
    >
      {TOOLS.map(({ tool: t, label, icon: Icon, shortcut }) => (
        <Tooltip key={t}>
          <TooltipTrigger asChild>
            <button
              type="button"
              aria-label={`${label} (${shortcut})`}
              aria-pressed={tool === t}
              disabled={disabled && t !== "select" && t !== "pan"}
              onClick={() => setTool(t)}
              className={cn(
                "flex size-9 items-center justify-center rounded-md border border-transparent text-muted-foreground transition-colors hover:bg-sidebar-accent hover:text-sidebar-foreground disabled:cursor-not-allowed disabled:opacity-35",
                tool === t && "border-primary/50 bg-primary/15 text-primary",
              )}
            >
              <Icon className="size-[18px]" />
            </button>
          </TooltipTrigger>
          <TooltipContent side="right">
            {label} <span className="ml-1 text-muted-foreground">{shortcut}</span>
          </TooltipContent>
        </Tooltip>
      ))}
    </div>
  );
}
