// Domain types mirroring the MVP v1.0 data model.

export type SessionState = "draft" | "live" | "ended" | "archived";
export type Role = "owner" | "interviewer" | "candidate" | "observer";
export type ConnectionState = "connected" | "reconnecting" | "offline";

export interface User {
  id: string;
  email: string;
  display_name: string;
  organization_id: string | null;
  created_at: string;
}

export interface InterviewSession {
  id: string;
  owner_user_id: string;
  title: string;
  prompt: string;
  state: SessionState;
  candidate_editing_enabled: boolean;
  cursors_visible: boolean;
  scheduled_at: string | null;
  started_at: string | null;
  ended_at: string | null;
  created_at: string;
  updated_at: string;
  participants: Participant[];
}

export interface Participant {
  id: string;
  session_id: string;
  user_id: string | null;
  display_name: string;
  role: Role;
  color: string;
  joined_at: string;
  left_at: string | null;
  connection_state?: ConnectionState;
  cursor?: { x: number; y: number } | null;
  selection?: string[];
}

export interface GuestLink {
  id: string;
  session_id: string;
  url: string;
  role_granted: Role;
  expires_at: string | null;
  max_uses: number | null;
  revoked_at: string | null;
  created_at: string;
}

/* ---------------- Canvas ---------------- */

export type ElementKind = "component" | "shape" | "text" | "sticky" | "stroke" | "connector";

export type ComponentType =
  | "service"
  | "rounded"
  | "boundary"
  | "generic"
  | "sql-db"
  | "nosql-db"
  | "cache"
  | "object-storage"
  | "warehouse"
  | "queue"
  | "stream"
  | "pubsub"
  | "client"
  | "mobile-client"
  | "api-gateway"
  | "load-balancer"
  | "cdn"
  | "external-api"
  | "server"
  | "worker"
  | "function"
  | "container"
  | "llm"
  | "embedding"
  | "vector-db"
  | "agent";

export interface BaseElement {
  id: string;
  kind: ElementKind;
  x: number;
  y: number;
  z: number;
  parent_id: string | null;
  created_by: string;
  created_at: string;
  updated_at: string;
}

export interface BoxElement extends BaseElement {
  kind: "component" | "shape" | "text" | "sticky";
  width: number;
  height: number;
  label: string;
  description?: string;
  componentType?: ComponentType;
  shape?: "rect" | "ellipse";
  color?: string;
}

export interface StrokeElement extends BaseElement {
  kind: "stroke";
  points: number[]; // flat [x,y,x,y...] in canvas space
  color: string;
  width: number;
  tool: "pen" | "highlighter";
}

export interface ConnectorElement extends BaseElement {
  kind: "connector";
  from: { elementId: string | null; x: number; y: number };
  to: { elementId: string | null; x: number; y: number };
  style: "straight" | "elbow" | "curved";
  dashed: boolean;
  color: string;
  strokeWidth: number;
  arrowStart: boolean;
  arrowEnd: boolean;
  label?: string;
}

export type CanvasElement = BoxElement | StrokeElement | ConnectorElement;

export interface CanvasDocument {
  id: string;
  session_id: string;
  schema_version: number;
  latest_operation_cursor: number;
  updated_at: string;
  elements: CanvasElement[];
}

/* ---------------- Realtime protocol ---------------- */

export type ClientMessage =
  | { type: "join_room"; protocol: 1; sessionId: string; token: string }
  | {
      type: "document_update";
      protocol: 1;
      sessionId: string;
      operationId: string;
      ops: CanvasOperation[];
    }
  | {
      type: "presence_update";
      protocol: 1;
      sessionId: string;
      cursor?: { x: number; y: number } | null;
      selection?: string[];
    }
  | { type: "ping"; protocol: 1 };

export type ServerMessage =
  | { type: "room_joined"; participants: Participant[]; document: CanvasDocument }
  | { type: "document_update"; ops: CanvasOperation[]; cursor: number }
  | { type: "presence_snapshot"; participants: Participant[] }
  | { type: "presence_update"; participant: Participant }
  | { type: "permission_changed"; candidate_editing_enabled: boolean }
  | { type: "session_ended"; ended_at: string }
  | { type: "error"; code: string; message: string }
  | { type: "pong" };

export type CanvasOperation =
  | { op: "add"; element: CanvasElement }
  | { op: "update"; id: string; patch: Partial<CanvasElement> }
  | { op: "delete"; id: string }
  | { op: "clear" };
