const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

function getHeaders() {
  const token = typeof window !== "undefined" ? localStorage.getItem("zenai_token") : null;
  return {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {})
  };
}
export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  generatedSql?: string;
  chartType?: string;
  chartData?: Record<string, unknown>[];
  confidence?: "high" | "medium" | "low";
  executionMs?: number;
  insights?: string[];
  rowCount?: number;
}

export interface ChatResponse {
  type: "status" | "answer";
  message_id?: string;
  message?: string;
  answer?: string;
  generated_sql?: string;
  chart_type?: string;
  chart_data?: Record<string, unknown>[];
  confidence?: string;
  execution_ms?: number;
  insights?: string[];
  row_count?: number;
  schema_similarity?: number;
  retries?: number;
}

export interface ConnectionResult {
  connected: boolean;
  message: string;
  table_count?: number;
  tables?: { name: string; column_count: number }[];
  detail?: string;
}

export async function connectDatabase(
  workspaceId: string,
  data: { host: string; port: number; db_name: string; username: string; password: string }
): Promise<ConnectionResult> {
  const res = await fetch(`${API_BASE}/workspaces/${workspaceId}/connect`, {
    method: "POST",
    headers: getHeaders(),
    body: JSON.stringify(data),
  });
  return res.json();
}

export async function introspectSchema(workspaceId: string, tables?: string[]) {
  const res = await fetch(`${API_BASE}/workspaces/${workspaceId}/introspect`, {
    method: "POST",
    headers: getHeaders(),
    body: JSON.stringify({ tables }),
  });
  return res.json();
}

export async function getSchema(workspaceId: string) {
  const res = await fetch(`${API_BASE}/workspaces/${workspaceId}/schema`, {
    headers: getHeaders(),
  });
  return res.json();
}

export async function deleteWorkspace(workspaceId: string) {
  const res = await fetch(`${API_BASE}/workspaces/${workspaceId}`, {
    method: "DELETE",
    headers: getHeaders(),
  });
  if (!res.ok) {
    throw new Error(`Failed to delete workspace: ${res.statusText}`);
  }
  return res.json();
}

export async function* streamChat(
  workspaceId: string,
  question: string,
  sessionId?: string
): AsyncGenerator<ChatResponse> {
  const res = await fetch(`${API_BASE}/workspaces/${workspaceId}/chat`, {
    method: "POST",
    headers: getHeaders(),
    body: JSON.stringify({ question, session_id: sessionId }),
  });

  if (!res.ok) {
    throw new Error(`Chat request failed: ${res.status}`);
  }

  const reader = res.body?.getReader();
  if (!reader) throw new Error("No response body");

  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";

    for (const line of lines) {
      if (line.trim()) {
        try {
          yield JSON.parse(line);
        } catch {
          // skip malformed lines
        }
      }
    }
  }
}
