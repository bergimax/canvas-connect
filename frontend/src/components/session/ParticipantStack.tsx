import type { Participant } from "@/lib/types";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

export function ParticipantStack({ participants }: { participants: Participant[] }) {
  return (
    <div className="flex -space-x-2" aria-label={`${participants.length} participants`}>
      {participants.slice(0, 6).map((p) => (
        <Tooltip key={p.id}>
          <TooltipTrigger asChild>
            <span
              className="flex size-8 items-center justify-center rounded-full border-2 border-surface text-xs font-semibold text-[#10161f]"
              style={{ backgroundColor: p.color }}
            >
              {p.display_name
                .split(" ")
                .map((w) => w[0])
                .slice(0, 2)
                .join("")
                .toUpperCase()}
            </span>
          </TooltipTrigger>
          <TooltipContent>
            {p.display_name} · {p.role}
            {p.connection_state === "reconnecting" ? " · reconnecting" : ""}
          </TooltipContent>
        </Tooltip>
      ))}
      {participants.length > 6 ? (
        <span className="flex size-8 items-center justify-center rounded-full border-2 border-surface bg-elevated text-xs">
          +{participants.length - 6}
        </span>
      ) : null}
    </div>
  );
}
