import { useState, type FormEvent } from "react";
import { createFileRoute, useRouter } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { api, ApiError } from "@/lib/api";
import { clearToken } from "@/lib/auth";
import { useRequireAuth } from "@/hooks/useRequireAuth";
import type { InterviewSession, SessionState } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";

export const Route = createFileRoute("/sessions/")({
  component: SessionsDashboard,
});

const STATE_VARIANT: Record<SessionState, "default" | "secondary" | "outline" | "destructive"> = {
  draft: "secondary",
  live: "default",
  ended: "outline",
  archived: "destructive",
};

function SessionsDashboard() {
  const token = useRequireAuth();
  const router = useRouter();
  const queryClient = useQueryClient();
  const [createOpen, setCreateOpen] = useState(false);

  const sessionsQuery = useQuery({
    queryKey: ["sessions"],
    queryFn: api.listSessions,
    enabled: !!token,
  });

  const meQuery = useQuery({ queryKey: ["me"], queryFn: api.me, enabled: !!token });

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["sessions"] });

  const startMutation = useMutation({ mutationFn: api.startSession, onSuccess: invalidate });
  const endMutation = useMutation({ mutationFn: api.endSession, onSuccess: invalidate });
  const archiveMutation = useMutation({ mutationFn: api.archiveSession, onSuccess: invalidate });
  const duplicateMutation = useMutation({
    mutationFn: api.duplicateSession,
    onSuccess: invalidate,
  });

  function logout() {
    clearToken();
    void router.navigate({ to: "/login" });
  }

  if (!token) return null;

  const sessions = sessionsQuery.data ?? [];

  return (
    <div className="min-h-screen bg-background px-6 py-8">
      <div className="mx-auto max-w-4xl">
        <div className="mb-6 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-semibold text-foreground">Interview sessions</h1>
            {meQuery.data ? (
              <p className="text-sm text-muted-foreground">
                Signed in as {meQuery.data.display_name}
              </p>
            ) : null}
          </div>
          <div className="flex items-center gap-2">
            <CreateSessionDialog
              open={createOpen}
              onOpenChange={setCreateOpen}
              onCreated={() => {
                setCreateOpen(false);
                void invalidate();
              }}
            />
            <Button variant="outline" onClick={logout}>
              Sign out
            </Button>
          </div>
        </div>

        {sessionsQuery.isLoading ? <p className="text-sm text-muted-foreground">Loading…</p> : null}
        {sessionsQuery.isError ? (
          <p className="text-sm text-destructive">
            Couldn't load sessions. Is the backend running?
          </p>
        ) : null}

        <div className="space-y-3">
          {sessions.map((s) => (
            <SessionRow
              key={s.id}
              session={s}
              onOpen={() => router.navigate({ to: "/sessions/$id", params: { id: s.id } })}
              onStart={() => startMutation.mutate(s.id)}
              onEnd={() => endMutation.mutate(s.id)}
              onArchive={() => archiveMutation.mutate(s.id)}
              onDuplicate={() => duplicateMutation.mutate(s.id)}
            />
          ))}
          {!sessionsQuery.isLoading && sessions.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No sessions yet — create one to get started.
            </p>
          ) : null}
        </div>
      </div>
    </div>
  );
}

function SessionRow({
  session,
  onOpen,
  onStart,
  onEnd,
  onArchive,
  onDuplicate,
}: {
  session: InterviewSession;
  onOpen: () => void;
  onStart: () => void;
  onEnd: () => void;
  onArchive: () => void;
  onDuplicate: () => void;
}) {
  return (
    <Card>
      <CardContent className="flex items-center justify-between gap-4 py-4">
        <button type="button" onClick={onOpen} className="min-w-0 flex-1 text-left">
          <div className="flex items-center gap-2">
            <span className="truncate font-medium text-foreground">{session.title}</span>
            <Badge variant={STATE_VARIANT[session.state]}>{session.state}</Badge>
          </div>
          <p className="mt-0.5 truncate text-sm text-muted-foreground">
            {session.prompt || "No prompt set"}
          </p>
        </button>
        <div className="flex shrink-0 items-center gap-2">
          {session.state === "draft" ? (
            <Button size="sm" variant="secondary" onClick={onStart}>
              Start
            </Button>
          ) : null}
          {session.state === "live" ? (
            <Button size="sm" variant="secondary" onClick={onEnd}>
              End
            </Button>
          ) : null}
          {session.state !== "archived" ? (
            <Button size="sm" variant="outline" onClick={onDuplicate}>
              Duplicate
            </Button>
          ) : null}
          {session.state !== "archived" ? (
            <Button size="sm" variant="ghost" onClick={onArchive}>
              Archive
            </Button>
          ) : null}
        </div>
      </CardContent>
    </Card>
  );
}

function CreateSessionDialog({
  open,
  onOpenChange,
  onCreated,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreated: () => void;
}) {
  const [title, setTitle] = useState("");
  const [prompt, setPrompt] = useState("");
  const [error, setError] = useState<string | null>(null);

  const createMutation = useMutation({
    mutationFn: () => api.createSession(prompt ? { title, prompt } : { title }),
    onSuccess: () => {
      setTitle("");
      setPrompt("");
      onCreated();
    },
    onError: (err) => {
      setError(err instanceof ApiError ? err.message : "Couldn't create session");
      toast.error("Couldn't create session");
    },
  });

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    createMutation.mutate();
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogTrigger asChild>
        <Button>New session</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>New interview session</DialogTitle>
        </DialogHeader>
        <form onSubmit={onSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="title">Title</Label>
            <Input id="title" required value={title} onChange={(e) => setTitle(e.target.value)} />
          </div>
          <div className="space-y-2">
            <Label htmlFor="prompt">Prompt</Label>
            <Textarea
              id="prompt"
              rows={4}
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
            />
          </div>
          {error ? <p className="text-sm text-destructive">{error}</p> : null}
          <DialogFooter>
            <Button type="submit" disabled={createMutation.isPending}>
              {createMutation.isPending ? "Creating…" : "Create"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
