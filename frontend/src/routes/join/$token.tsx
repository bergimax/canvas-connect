import { useState, type FormEvent } from "react";
import { createFileRoute, useRouter } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { api, ApiError } from "@/lib/api";
import { setParticipantId, setToken } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export const Route = createFileRoute("/join/$token")({
  component: JoinLobby,
});

function JoinLobby() {
  const { token: joinToken } = Route.useParams();
  const router = useRouter();
  const [displayName, setDisplayName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  const previewQuery = useQuery({
    queryKey: ["join-preview", joinToken],
    queryFn: () => api.previewJoin(joinToken),
  });

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setPending(true);
    try {
      const { session, participant, collaboration_token } = await api.join(joinToken, {
        display_name: displayName,
      });
      setToken(collaboration_token);
      setParticipantId(participant.id);
      await router.navigate({ to: "/sessions/$id", params: { id: session.id } });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't join this session");
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle>Join interview</CardTitle>
          {previewQuery.data ? (
            <CardDescription>{previewQuery.data.session_title}</CardDescription>
          ) : null}
        </CardHeader>
        <CardContent>
          {previewQuery.isLoading ? (
            <p className="text-sm text-muted-foreground">Checking link…</p>
          ) : null}
          {previewQuery.data && !previewQuery.data.joinable ? (
            <p className="text-sm text-destructive">
              {previewQuery.data.reason ?? "This link is not valid."}
            </p>
          ) : null}
          {previewQuery.data?.joinable ? (
            <form onSubmit={onSubmit} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="display_name">Your name</Label>
                <Input
                  id="display_name"
                  required
                  autoFocus
                  value={displayName}
                  onChange={(e) => setDisplayName(e.target.value)}
                />
              </div>
              {error ? <p className="text-sm text-destructive">{error}</p> : null}
              <Button type="submit" className="w-full" disabled={pending}>
                {pending ? "Joining…" : "Join"}
              </Button>
            </form>
          ) : null}
        </CardContent>
      </Card>
    </div>
  );
}
