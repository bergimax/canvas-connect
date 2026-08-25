import type { ComponentType } from "./types";

export interface PaletteItem {
  type: ComponentType;
  label: string;
  icon: string; // lucide icon name key used by ComponentIcon
  width: number;
  height: number;
}

export interface PaletteCategory {
  name: string;
  items: PaletteItem[];
}

const box = (
  type: ComponentType,
  label: string,
  icon: string,
  width = 168,
  height = 84,
): PaletteItem => ({
  type,
  label,
  icon,
  width,
  height,
});

export const PALETTE: PaletteCategory[] = [
  {
    name: "General",
    items: [
      box("service", "Service", "Box"),
      box("rounded", "Process", "Squircle"),
      box("boundary", "Boundary", "SquareDashed", 320, 220),
      box("generic", "Generic", "Shapes"),
    ],
  },
  {
    name: "Data",
    items: [
      box("sql-db", "SQL Database", "Database"),
      box("nosql-db", "NoSQL Store", "Layers"),
      box("cache", "Cache", "Zap"),
      box("object-storage", "Object Storage", "HardDrive"),
      box("warehouse", "Data Warehouse", "Warehouse"),
    ],
  },
  {
    name: "Messaging",
    items: [
      box("queue", "Queue", "ListOrdered"),
      box("stream", "Event Stream", "Waves"),
      box("pubsub", "Pub/Sub Broker", "Radio"),
    ],
  },
  {
    name: "Network",
    items: [
      box("client", "Client", "Monitor"),
      box("mobile-client", "Mobile Client", "Smartphone"),
      box("api-gateway", "API Gateway", "DoorOpen"),
      box("load-balancer", "Load Balancer", "Scale"),
      box("cdn", "CDN", "Globe"),
      box("external-api", "External API", "PlugZap"),
    ],
  },
  {
    name: "Compute",
    items: [
      box("server", "Server", "Server"),
      box("worker", "Worker", "Cog"),
      box("function", "Function", "FunctionSquare"),
      box("container", "Container/Cluster", "Container"),
    ],
  },
  {
    name: "AI",
    items: [
      box("llm", "LLM / Model", "Brain"),
      box("embedding", "Embedding Model", "Sparkles"),
      box("vector-db", "Vector Database", "Grid3x3"),
      box("agent", "Agent / Tool", "Bot"),
    ],
  },
];

export const PALETTE_INDEX: Record<string, PaletteItem> = Object.fromEntries(
  PALETTE.flatMap((c) => c.items).map((i) => [i.type, i]),
);

export const PARTICIPANT_COLORS = [
  "#3dd6c4",
  "#f5a524",
  "#7aa2f7",
  "#e5637d",
  "#9ece6a",
  "#c58af9",
  "#ff9e64",
  "#5ac8fa",
];
