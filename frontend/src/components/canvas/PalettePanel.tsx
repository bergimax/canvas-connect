import { PALETTE, type PaletteItem } from "@/lib/palette";
import { ComponentIcon } from "./ComponentIcon";
import { ScrollArea } from "@/components/ui/scroll-area";

export function PalettePanel({
  disabled,
  onPick,
}: {
  disabled: boolean;
  onPick: (item: PaletteItem) => void;
}) {
  return (
    <ScrollArea className="h-full">
      <div className="space-y-5 p-3">
        {PALETTE.map((cat) => (
          <section key={cat.name}>
            <h3 className="mb-2 px-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-muted-foreground">
              {cat.name}
            </h3>
            <div className="grid grid-cols-2 gap-2">
              {cat.items.map((item) => (
                <button
                  key={item.type}
                  type="button"
                  disabled={disabled}
                  onClick={() => onPick(item)}
                  draggable={!disabled}
                  onDragStart={(e) =>
                    e.dataTransfer.setData("application/x-sdi-component", item.type)
                  }
                  title={`Add ${item.label}`}
                  className="flex flex-col items-start gap-1.5 rounded-md border border-border bg-elevated px-2.5 py-2 text-left text-xs transition-colors hover:border-primary/60 hover:bg-secondary disabled:cursor-not-allowed disabled:opacity-40"
                >
                  <ComponentIcon name={item.icon} className="size-4 text-primary" />
                  <span className="leading-tight text-surface-foreground">{item.label}</span>
                </button>
              ))}
            </div>
          </section>
        ))}
      </div>
    </ScrollArea>
  );
}
