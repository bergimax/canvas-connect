/**
 * HTTP API client for the System Design Interview Platform.
 *
 * Every call in this file matches the documented REST surface (section 12).
 * While the backend is not available, requests transparently fall back to the
 * in-memory mock adapter in `./mock-backend`. Set VITE_API_BASE_URL (and
 * optionally VITE_USE_MOCK_API="false") to point the app at the real backend.
 */
import type { CanvasDocument, GuestLink, InterviewSession, Participant, Role, User } from "./types";
import { mockApi } from "./mock-backend";

const API_BASE = (import.meta.env["VITE_API_BASE_URL"] as string | undefined) ?? "";
const USE_MOCK = (import.meta.env["VITE_USE_MOCK_API"] as string | undefined) !== "false" && !API_BASE;

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
  ) {
    super(message);
  }
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers: { "content-type": "application/json" },
    credentials: "include",
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  });
  if (!res.ok) {
    const payload = (await res.json().catch(() => ({}))) as { code?: string; message?: string };
    throw new ApiError(res.status, payload.code ?? "unknown_error", payload.message ?? res.statusText);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

/* ------------------------- Auth ------------------------- */

export const api = {
  /** POST /v1/auth/magic-link */
  requestMagicLink: (email: string): Promise<{ sent: boolean }> =>
    USE_MOCK ? mockApi.requestMagicLink(email) : request("POST", "/v1/auth/magic-link", { email }),

  /** GET /v1/me */
  me: (): Promise<User> => (USE_MOCK ? mockApi.me() : request("GET", "/v1/me")),

  /* ----------------------- Sessions ----------------------- */

  /** POST /v1/sessions */
  createSession: (input: {
    title: string;
    prompt?: string;
    scheduled_at?: string | null;
    duration_minutes?: number | null;
  }): Promise<InterviewSession> =>
    USE_MOCK ? mockApi.createSession(input) : request("POST", "/v1/sessions", input),

  /** GET /v1/sessions */
  listSessions: (): Promise<InterviewSession[]> =>
    USE_MOCK ? mockApi.listSessions() : request("GET", "/v1/sessions"),

  /** GET /v1/sessions/{id} */
  getSession: (id: string): Promise<InterviewSession> =>
    USE_MOCK ? mockApi.getSession(id) : request("GET", `/v1/sessions/${id}`),

  /** PATCH /v1/sessions/{id} */
  updateSession: (
    id: string,
    patch: Partial<Pick<InterviewSession, "title" | "prompt" | "candidate_editing_enabled" | "cursors_visible" | "state">>,
  ): Promise<InterviewSession> =>
    USE_MOCK ? mockApi.updateSession(id, patch) : request("PATCH", `/v1/sessions/${id}`, patch),

  /** POST /v1/sessions/{id}/start */
  startSession: (id: string): Promise<InterviewSession> =>
    USE_MOCK ? mockApi.startSession(id) : request("POST", `/v1/sessions/${id}/start`),

  /** POST /v1/sessions/{id}/end */
  endSession: (id: string): Promise<InterviewSession> =>
    USE_MOCK ? mockApi.endSession(id) : request("POST", `/v1/sessions/${id}/end`),

  /** POST /v1/sessions/{id}/duplicate */
  duplicateSession: (id: string): Promise<InterviewSession> =>
    USE_MOCK ? mockApi.duplicateSession(id) : request("POST", `/v1/sessions/${id}/duplicate`),

  /** POST /v1/sessions/{id}/archive */
  archiveSession: (id: string): Promise<InterviewSession> =>
    USE_MOCK ? mockApi.archiveSession(id) : request("POST", `/v1/sessions/${id}/archive`),

  /* --------------------- Guest links ---------------------- */

  /** POST /v1/sessions/{id}/guest-links */
  createGuestLink: (
    id: string,
    input?: { role_granted?: Role; expires_at?: string | null; max_uses?: number | null },
  ): Promise<GuestLink> =>
    USE_MOCK ? mockApi.createGuestLink(id, input) : request("POST", `/v1/sessions/${id}/guest-links`, input ?? {}),

  /** DELETE /v1/sessions/{id}/guest-links/{linkId} */
  revokeGuestLink: (id: string, linkId: string): Promise<void> =>
    USE_MOCK ? mockApi.revokeGuestLink(id, linkId) : request("DELETE", `/v1/sessions/${id}/guest-links/${linkId}`),

  /** GET /v1/sessions/{id}/guest-links */
  listGuestLinks: (id: string): Promise<GuestLink[]> =>
    USE_MOCK ? mockApi.listGuestLinks(id) : request("GET", `/v1/sessions/${id}/guest-links`),

  /* ------------------------- Join ------------------------- */

  /** GET /v1/join/{token} — lobby preflight */
  previewJoin: (token: string): Promise<{ session_title: string; joinable: boolean; reason?: string }> =>
    USE_MOCK ? mockApi.previewJoin(token) : request("GET", `/v1/join/${token}`),

  /** POST /v1/join/{token} */
  join: (
    token: string,
    input: { display_name: string },
  ): Promise<{ session: InterviewSession; participant: Participant; collaboration_token: string }> =>
    USE_MOCK ? mockApi.join(token, input) : request("POST", `/v1/join/${token}`, input),

  /* ------------------------ Canvas ------------------------ */

  /** GET /v1/sessions/{id}/canvas */
  getCanvas: (id: string): Promise<{ document: CanvasDocument; collaboration_token: string; websocket_url: string }> =>
    USE_MOCK ? mockApi.getCanvas(id) : request("GET", `/v1/sessions/${id}/canvas`),

  /** PUT /v1/sessions/{id}/canvas — autosave fallback when the socket is down */
  saveCanvas: (id: string, document: CanvasDocument): Promise<{ saved_at: string }> =>
    USE_MOCK ? mockApi.saveCanvas(id, document) : request("PUT", `/v1/sessions/${id}/canvas`, document),

  /* -------------------- Participants ---------------------- */

  /** DELETE /v1/sessions/{id}/participants/{participantId} */
  removeParticipant: (id: string, participantId: string): Promise<void> =>
    USE_MOCK
      ? mockApi.removeParticipant(id, participantId)
      : request("DELETE", `/v1/sessions/${id}/participants/${participantId}`),
};

export const usingMockBackend = USE_MOCK;
