import { useEffect } from "react";
import { createFileRoute, useRouter } from "@tanstack/react-router";
import { getToken } from "@/lib/auth";

export const Route = createFileRoute("/")({
  component: Index,
});

function Index() {
  const router = useRouter();

  useEffect(() => {
    void router.navigate({ to: getToken() ? "/sessions" : "/login" });
  }, [router]);

  return <div className="flex min-h-screen items-center justify-center bg-background" />;
}
