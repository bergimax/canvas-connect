/**
 * In-memory mock backend. Replaced by the real API as soon as
 * VITE_API_BASE_URL is configured. Data lives in localStorage so page
 * reloads restore the latest confirmed state, as the spec requires.
 */
import type {
  CanvasDocument,
  GuestLink,
  InterviewSession,
  Participant,
  Role,
  User,
} from "./types";
import { PARTICIPANT_COLORS } from "./palette";

const KEY = "sdi.mock.v1";

const uid = () => Math.random().toString(36).slice(2, 10) + Date.now().toString(36).slice(-4);
const now = () => new Date().toISOString();

interface Store {
  user: User;
  sessions: InterviewSession[];
  links: GuestLink[];
  canvases: Record<string, CanvasDocument>;
}

const OWNER: User = {
  id: "usr_owner",
  email: "interviewer@example.com",
  display_name: "Alex Moreau",
  organization_id: "org_demo",
  created_at: now(),
};

function seed(): Store {
  const s: InterviewSession = {
    id: "ses_demo",
    owner_user_id: OWNER.id,
    title: "Design a URL shortener",
    prompt:
      "Design a highly available URL shortening service handling 10k writes/s and 500k reads/s. Discuss data model, caching, and failure modes.",
    state: "draft",
    candidate_editing_enabled: true,
    cursors_visible: true,
    scheduled_at: null,
    started_at: null,
    ended_at: null,
    created_at: now(),
    updated_at: now(),
    participants: [
      {
        id: "prt_owner",
        session_id: "ses_demo",
        user_id: OWNER.id,
        display_name: OWNER.display_name,
        role: "owner",
        color: PARTICIPANT_COLORS[0]!,
        joined_at: now(),
        left_at: null,
        connection_state: "connected",
      },
    ],
  };
  return {
    user: OWNER,
    sessions: [s],
    links: [],
    canvases: {
      [s.id]: {
        id: "doc_demo",
        session_id: s.id,
        schema_version: 1,
        latest_operation_cursor: 0,
        updated_at: now(),
        elements: [],
      },
    },
  };
}

function read(): Store {
  if (typeof localStorage === "undefined") return seed();
  const raw = localStorage.getItem(KEY);
  if (!raw) {
    const s = seed();
    localStorage.setItem(KEY, JSON.stringify(s));
    return s;
  }
  try {
    return JSON.parse(raw) as Store;
  } catch {
    return seed();
  }
}

function write(store: Store) {
  if (typeof localStorage !== "undefined") localStorage.setItem(KEY, JSON.stringify(store));
}

function mustSession(store: Store, id: string): InterviewSession {
  const s = store.sessions.find((x) => x.id === id);
  if (!s) throw new Error("Session not found");
  return s;
}

const delay = <T,>(v: T): Promise<T> => new Promise((r) => setTimeout(() => r(v), 90));

export const mockApi = {
  requestMagicLink: (_email: string) => delay({ sent: true }),
  me: () => delay(read().user),

  listSessions: () => delay(read().sessions.filter((s) => s.state !== "archived")),

  getSession: (id: string) => delay(mustSession(read(), id)),

  createSession: (input: { title: string; prompt?: string; scheduled_at?: string | null }) => {
    const store = read();
    const id = "ses_" + uid();
    const session: InterviewSession = {
      id,
      owner_user_id: store.user.id,
      title: input.title,
      prompt: input.prompt ?? "",
      state: "draft",
      candidate_editing_enabled: true,
      cursors_visible: true,
      scheduled_at: input.scheduled_at ?? null,
      started_at: null,
      ended_at: null,
      created_at: now(),
      updated_at: now(),
      participants: [
        {
          id: "prt_" + uid(),
          session_id: id,
          user_id: store.user.id,
          display_name: store.user.display_name,
          role: "owner",
          color: PARTICIPANT_COLORS[0]!,
          joined_at: now(),
          left_at: null,
          connection_state: "connected",
        },
      ],
    };
    store.sessions.unshift(session);
    store.canvases[id] = {
      id: "doc_" + uid(),
      session_id: id,
      schema_version: 1,
      latest_operation_cursor: 0,
      updated_at: now(),
      elements: [],
    };
    write(store);
    return delay(session);
  },

  updateSession: (id: string, patch: Partial<InterviewSession>) => {
    const store = read();
    const s = mustSession(store, id);
    Object.assign(s, patch, { updated_at: now() });
    write(store);
    return delay(s);
  },

  startSession: (id: string) => {
    const store = read();
    const s = mustSession(store, id);
    s.state = "live";
    s.started_at = s.started_at ?? now();
    s.updated_at = now();
    write(store);
    return delay(s);
  },

  endSession: (id: string) => {
    const store = read();
    const s = mustSession(store, id);
    s.state = "ended";
    s.ended_at = now();
    s.candidate_editing_enabled = false;
    s.updated_at = now();
    write(store);
    return delay(s);
  },

  archiveSession: (id: string) => {
    const store = read();
    const s = mustSession(store, id);
    s.state = "archived";
    s.updated_at = now();
    write(store);
    return delay(s);
  },

  duplicateSession: (id: string) => {
    const store = read();
    const src = mustSession(store, id);
    const newId = "ses_" + uid();
    const copy: InterviewSession = {
      ...src,
      id: newId,
      title: `${src.title} (copy)`,
      state: "draft",
      started_at: null,
      ended_at: null,
      created_at: now(),
      updated_at: now(),
      participants: src.participants.filter((p) => p.role === "owner").map((p) => ({ ...p, session_id: newId })),
    };
    store.sessions.unshift(copy);
    const srcDoc = store.canvases[id];
    store.canvases[newId] = {
      id: "doc_" + uid(),
      session_id: newId,
      schema_version: 1,
      latest_operation_cursor: 0,
      updated_at: now(),
      elements: srcDoc ? JSON.parse(JSON.stringify(srcDoc.elements)) : [],
    };
    write(store);
    return delay(copy);
  },

  listGuestLinks: (id: string) => delay(read().links.filter((l) => l.session_id === id && !l.revoked_at)),

  createGuestLink: (id: string, input?: { role_granted?: Role; expires_at?: string | null; max_uses?: number | null }) => {
    const store = read();
    store.links = store.links.map((l) => (l.session_id === id ? { ...l, revoked_at: l.revoked_at ?? now() } : l));
    const token = `${id}.${uid()}${uid()}`;
    const link: GuestLink = {
      id: "lnk_" + uid(),
      session_id: id,
      url: `${typeof location !== "undefined" ? location.origin : ""}/join/${token}`,
      role_granted: input?.role_granted ?? "candidate",
      expires_at: input?.expires_at ?? null,
      max_uses: input?.max_uses ?? 10,
      revoked_at: null,
      created_at: now(),
    };
    store.links.push(link);
    write(store);
    return delay(link);
  },

  revokeGuestLink: (id: string, linkId: string) => {
    const store = read();
    const l = store.links.find((x) => x.id === linkId && x.session_id === id);
    if (l) l.revoked_at = now();
    write(store);
    return delay(undefined as void);
  },

  previewJoin: (token: string) => {
    const store = read();
    const link = store.links.find((l) => l.url.endsWith(token));
    const sessionId = token.split(".")[0]!;
    const session = store.sessions.find((s) => s.id === sessionId);
    if (!session) return delay({ session_title: "", joinable: false, reason: "This link is not valid." });
    if (link?.revoked_at) return delay({ session_title: session.title, joinable: false, reason: "This link was revoked." });
    if (session.state === "archived")
      return delay({ session_title: session.title, joinable: false, reason: "This interview is archived." });
    return delay({ session_title: session.title, joinable: true });
  },

  join: (token: string, input: { display_name: string }) => {
    const store = read();
    const sessionId = token.split(".")[0]!;
    const session = mustSession(store, sessionId);
    const participant: Participant = {
      id: "prt_" + uid(),
      session_id: session.id,
      user_id: null,
      display_name: input.display_name,
      role: "candidate",
      color: PARTICIPANT_COLORS[session.participants.length % PARTICIPANT_COLORS.length]!,
      joined_at: now(),
      left_at: null,
      connection_state: "connected",
    };
    session.participants.push(participant);
    if (session.state === "draft") {
      session.state = "live";
      session.started_at = session.started_at ?? now();
    }
    write(store);
    return delay({ session, participant, collaboration_token: "collab_" + uid() });
  },

  removeParticipant: (id: string, participantId: string) => {
    const store = read();
    const s = mustSession(store, id);
    s.participants = s.participants.filter((p) => p.id !== participantId);
    write(store);
    return delay(undefined as void);
  },

  getCanvas: (id: string) => {
    const store = read();
    const doc =
      store.canvases[id] ??
      ({
        id: "doc_" + uid(),
        session_id: id,
        schema_version: 1,
        latest_operation_cursor: 0,
        updated_at: now(),
        elements: [],
      } satisfies CanvasDocument);
    store.canvases[id] = doc;
    write(store);
    return delay({ document: doc, collaboration_token: "collab_" + uid(), websocket_url: "" });
  },

  saveCanvas: (id: string, document: CanvasDocument) => {
    const store = read();
    store.canvases[id] = { ...document, updated_at: now() };
    const s = store.sessions.find((x) => x.id === id);
    if (s) s.updated_at = now();
    write(store);
    return delay({ saved_at: now() });
  },
};
