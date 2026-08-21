/**
 * Bearer-token storage. A browser tab is either signed in as an interviewer
 * (`user` token, from POST /v1/auth/login) or joined as a guest (`participant`
 * token, from POST /v1/join/{token}) — never both, so a single active token
 * is enough. Guests also need their participant id to identify "self" among
 * `session.participants` (they have no `User` record to match against).
 */
const TOKEN_KEY = "sdi.token";
const PARTICIPANT_ID_KEY = "sdi.participantId";

export function getToken(): string | null {
  if (typeof localStorage === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function getParticipantId(): string | null {
  if (typeof localStorage === "undefined") return null;
  return localStorage.getItem(PARTICIPANT_ID_KEY);
}

export function setParticipantId(id: string): void {
  localStorage.setItem(PARTICIPANT_ID_KEY, id);
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(PARTICIPANT_ID_KEY);
}
