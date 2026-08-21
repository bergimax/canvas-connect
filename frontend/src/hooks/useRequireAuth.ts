import { useEffect, useState } from "react";
import { useRouter } from "@tanstack/react-router";
import { getToken } from "@/lib/auth";

/**
 * Reads the token once on mount and redirects to /login if it's missing.
 * Starts `null` on every render (server and client alike) so there's no
 * SSR/hydration mismatch to reconcile — the token lives in localStorage,
 * which only exists client-side, so the real value can only be known after
 * mount anyway.
 */
export function useRequireAuth(): string | null {
  const router = useRouter();
  const [token, setTokenState] = useState<string | null>(null);

  useEffect(() => {
    const t = getToken();
    setTokenState(t);
    if (!t) void router.navigate({ to: "/login" });
  }, [router]);

  return token;
}
