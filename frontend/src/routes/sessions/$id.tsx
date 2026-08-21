import { useEffect, useMemo, useRef, useState } from "react";
import { createFileRoute, Link } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { ArrowLeft, Copy, Link2, Trash2 } from "lucide-react";
import { api } from "@/lib/api";
import { getParticipantId } from "@/lib/auth";
import { useRequireAuth } from "@/hooks/useRequireAuth";
import { useCanvasEngine } from "@/hooks/useCanvasEngine";
import { CanvasStage, type Viewport } from "@/components/canvas/CanvasStage";
import { Toolbar, type Tool } from "@/components/canvas/Toolbar";
import { PalettePanel } from "@/components/canvas/PalettePanel";
import { PropertiesPanel } from "@/components/canvas/PropertiesPanel";
import { ParticipantStack } from "@/components/session/ParticipantStack";
import { ConnectionBadge } from "@/components/session/ConnectionBadge";
import type { PaletteItem } from "@/lib/palette";
import type { BoxElement, CanvasOperation, ConnectionState, InterviewSession } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";

export const Route = createFileRoute("/sessions/$id")({
  component: SessionWorkspace,
});

const AUTOSAVE_DELAY = 800;
const POLL_INTERVAL = 4000;

function SessionWorkspace() {
  const { id } = Route.useParams();
  const token = useRequireAuth();
  const queryClient = useQueryClient();
  const participantId = getParticipantId();

  const sessionQuery = useQuery({
    queryKey: ["session", id],
    queryFn: () => api.getSession(id),
    enabled: !!token,
  });
  const meQuery = useQuery({
    queryKey: ["me"],
    queryFn: api.me,
    enabled: !!token && !participantId,
  });
  const canvasQuery = useQuery({
    queryKey: ["canvas", id],
    queryFn: () => api.getCanvas(id),
    enabled: !!token,
    refetchInterval: POLL_INTERVAL,
    refetchIntervalInBackground: false,
  });

  const session = sessionQuery.data;
  const self = useMemo(() => {
    if (!session) return null;
    if (participantId) return session.participants.find((p) => p.id === participantId) ?? null;
    if (meQuery.data)
      return session.participants.find((p) => p.user_id === meQuery.data!.id) ?? null;
    return null;
  }, [session, participantId, meQuery.data]);

  const isManager = self?.role === "owner" || self?.role === "interviewer";
  const readOnly =
    !self ||
    self.role === "observer" ||
    (self.role === "candidate" && !session?.candidate_editing_enabled);

  const [tool, setTool] = useState<Tool>("select");
  const [viewport, setViewport] = useState<Viewport>({ x: 0, y: 0, scale: 1 });
  const [connState, setConnState] = useState<ConnectionState>("connected");
  const [savedAt, setSavedAt] = useState<string | null>(null);

  const remoteUpdatedAt = useRef<string | null>(null);
  const pendingSave = useRef(false);
  const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const cursorRef = useRef<number>(0);

  const emit = (_ops: CanvasOperation[]) => {
    pendingSave.current = true;
    setConnState("reconnecting");
    if (saveTimer.current) clearTimeout(saveTimer.current);
    saveTimer.current = setTimeout(saveDocument, AUTOSAVE_DELAY);
  };

  const engine = useCanvasEngine(emit, () => readOnly);

  // setTimeout captures whatever closure was current when it was scheduled,
  // which is stale by the time it fires (React re-renders — with the new
  // element already in `engine.elements` — long before the 800ms elapses).
  // Refs kept in sync on every render give saveDocument the live values.
  const elementsRef = useRef(engine.elements);
  elementsRef.current = engine.elements;
  const docRef = useRef(canvasQuery.data?.document);
  docRef.current = canvasQuery.data?.document;

  async function saveDocument() {
    const doc = docRef.current;
    if (!doc) return;
    cursorRef.current += 1;
    try {
      const { saved_at } = await api.saveCanvas(id, {
        ...doc,
        elements: elementsRef.current,
        latest_operation_cursor: cursorRef.current,
      });
      remoteUpdatedAt.current = saved_at;
      setSavedAt(saved_at);
      setConnState("connected");
    } catch {
      setConnState("offline");
      toast.error("Couldn't save canvas changes");
    } finally {
      pendingSave.current = false;
    }
  }

  // Apply the initial load, and any remote change picked up by polling —
  // skipped while a local save is in flight so we don't clobber unsaved edits.
  useEffect(() => {
    const doc = canvasQuery.data?.document;
    if (!doc || pendingSave.current) return;
    if (doc.updated_at === remoteUpdatedAt.current) return;
    remoteUpdatedAt.current = doc.updated_at;
    setSavedAt(doc.updated_at);
    engine.replaceAll(doc.elements);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [canvasQuery.data?.document]);

  function handlePalettePick(item: PaletteItem) {
    if (readOnly) return;
    const n = engine.elements.length;
    const el: BoxElement = {
      id: crypto.randomUUID(),
      kind: "component",
      x: 320 + (n % 6) * 40,
      y: 220 + (n % 6) * 40,
      z: n,
      parent_id: null,
      created_by: self?.id ?? "unknown",
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      width: item.width,
      height: item.height,
      label: item.label,
      componentType: item.type,
    };
    engine.add(el);
  }

  if (!token) return null;

  if (sessionQuery.isLoading || canvasQuery.isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center text-sm text-muted-foreground">
        Loading…
      </div>
    );
  }

  if (sessionQuery.isError || !session) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-3 text-sm text-muted-foreground">
        <p>Couldn't load this session.</p>
        <Link to="/sessions" className="text-primary underline">
          Back to dashboard
        </Link>
      </div>
    );
  }

  return (
    <div className="flex h-screen flex-col bg-background">
      <header className="flex items-center justify-between gap-4 border-b border-border px-4 py-2.5">
        <div className="flex min-w-0 items-center gap-3">
          <Link to="/sessions" className="text-muted-foreground hover:text-foreground">
            <ArrowLeft className="size-4" />
          </Link>
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <h1 className="truncate text-sm font-semibold text-foreground">{session.title}</h1>
              <Badge variant={session.state === "live" ? "default" : "secondary"}>
                {session.state}
              </Badge>
            </div>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <ParticipantStack participants={session.participants} />
          <ConnectionBadge state={connState} savedAt={savedAt} />
          {isManager ? <ManagerControls session={session} sessionId={id} /> : null}
        </div>
      </header>

      <div className="flex flex-1 overflow-hidden">
        <Toolbar tool={tool} setTool={setTool} disabled={readOnly} />
        <div className="w-56 shrink-0 border-r border-border bg-sidebar">
          <PalettePanel disabled={readOnly} onPick={handlePalettePick} />
        </div>
        <div className="min-w-0 flex-1">
          <CanvasStage
            engine={engine}
            tool={tool}
            setTool={setTool}
            readOnly={readOnly}
            participants={session.participants}
            selfId={self?.id ?? ""}
            viewport={viewport}
            setViewport={setViewport}
            onCursor={() => {}}
            strokeColor="#3dd6c4"
            strokeWidth={2}
            snapToGrid
            showCursors={session.cursors_visible}
          />
        </div>
        <div className="w-72 shrink-0 border-l border-border bg-sidebar">
          <PropertiesPanel engine={engine} prompt={session.prompt} readOnly={readOnly} />
        </div>
      </div>
    </div>
  );
}

function ManagerControls({ session, sessionId }: { session: InterviewSession; sessionId: string }) {
  const queryClient = useQueryClient();
  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["session", sessionId] });

  const startMutation = useMutation({
    mutationFn: () => api.startSession(sessionId),
    onSuccess: invalidate,
  });
  const endMutation = useMutation({
    mutationFn: () => api.endSession(sessionId),
    onSuccess: invalidate,
  });
  const toggleEditing = useMutation({
    mutationFn: (enabled: boolean) =>
      api.updateSession(sessionId, { candidate_editing_enabled: enabled }),
    onSuccess: invalidate,
  });

  return (
    <div className="flex items-center gap-3">
      <div className="flex items-center gap-2">
        <Switch
          id="candidate-editing"
          checked={session.candidate_editing_enabled}
          onCheckedChange={(v) => toggleEditing.mutate(v)}
        />
        <Label htmlFor="candidate-editing" className="text-xs text-muted-foreground">
          Candidate editing
        </Label>
      </div>
      {session.state === "draft" ? (
        <Button size="sm" variant="secondary" onClick={() => startMutation.mutate()}>
          Start
        </Button>
      ) : null}
      {session.state === "live" ? (
        <Button size="sm" variant="secondary" onClick={() => endMutation.mutate()}>
          End
        </Button>
      ) : null}
      <GuestLinkDialog sessionId={session.id} />
    </div>
  );
}

function GuestLinkDialog({ sessionId }: { sessionId: string }) {
  const queryClient = useQueryClient();
  const linksQuery = useQuery({
    queryKey: ["guest-links", sessionId],
    queryFn: () => api.listGuestLinks(sessionId),
  });

  const createMutation = useMutation({
    mutationFn: () => api.createGuestLink(sessionId, { role_granted: "candidate" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["guest-links", sessionId] }),
  });
  const revokeMutation = useMutation({
    mutationFn: (linkId: string) => api.revokeGuestLink(sessionId, linkId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["guest-links", sessionId] }),
  });

  return (
    <Dialog>
      <DialogTrigger asChild>
        <Button size="sm" variant="outline">
          <Link2 className="size-3.5" />
          Guest links
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Candidate links</DialogTitle>
        </DialogHeader>
        <div className="space-y-2">
          {(linksQuery.data ?? []).map((link) => (
            <div
              key={link.id}
              className="flex items-center gap-2 rounded-md border border-border p-2 text-xs"
            >
              <span className="flex-1 truncate font-mono">{link.url}</span>
              <Button
                size="icon"
                variant="ghost"
                className="size-7"
                onClick={() => {
                  void navigator.clipboard.writeText(link.url);
                  toast.success("Link copied");
                }}
              >
                <Copy className="size-3.5" />
              </Button>
              <Button
                size="icon"
                variant="ghost"
                className="size-7"
                onClick={() => revokeMutation.mutate(link.id)}
              >
                <Trash2 className="size-3.5" />
              </Button>
            </div>
          ))}
          {linksQuery.data?.length === 0 ? (
            <p className="text-xs text-muted-foreground">No active links yet.</p>
          ) : null}
        </div>
        <DialogFooter>
          <Button onClick={() => createMutation.mutate()} disabled={createMutation.isPending}>
            {createMutation.isPending ? "Creating…" : "New candidate link"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
