"use client";

import { useState, useEffect } from "react";
import { use } from "react";
import Link from "next/link";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface QueryLog {
  id: string;
  sql_text: string;
  row_count: number;
  execution_ms: number;
  estimated_cost: number | null;
  status: string;
  created_at: string;
}

const statusColors: Record<string, string> = {
  success: "text-success bg-success/10",
  error: "text-error bg-error/10",
  retried: "text-warning bg-warning/10",
  blocked: "text-error bg-error/10",
};

export default function LogsPage({ params }: { params: Promise<{ workspaceId: string }> }) {
  const { workspaceId } = use(params);
  const [logs, setLogs] = useState<QueryLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const token = localStorage.getItem("zenai_token");
    fetch(`${API_BASE}/workspaces/${workspaceId}/logs`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((res) => res.json())
      .then((data) => { setLogs(data.logs || []); setLoading(false); })
      .catch(() => { setError("Failed to load logs"); setLoading(false); });
  }, [workspaceId]);

  return (
    <div className="min-h-screen bg-background">
      <aside className="fixed left-0 top-0 h-full w-64 border-r border-border bg-surface flex flex-col">
        <div className="p-4 border-b border-border">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-primary flex items-center justify-center">
              <span className="text-white font-bold text-sm">Z</span>
            </div>
            <span className="text-lg font-semibold text-text-primary">ZenAI</span>
          </div>
        </div>
        <nav className="flex-1 p-4 space-y-1">
          <Link href="/dashboard" className="flex items-center gap-2 px-3 py-2 text-sm text-text-secondary hover:bg-muted rounded-lg">← Workspaces</Link>
          <Link href={`/dashboard/${workspaceId}`} className="flex items-center gap-2 px-3 py-2 text-sm text-text-secondary hover:bg-muted rounded-lg">Chat</Link>
          <Link href={`/dashboard/${workspaceId}/schema`} className="flex items-center gap-2 px-3 py-2 text-sm text-text-secondary hover:bg-muted rounded-lg">Schema</Link>
          <Link href={`/dashboard/${workspaceId}/logs`} className="flex items-center gap-2 px-3 py-2 text-sm font-medium text-primary bg-primary/5 rounded-lg">Audit Log</Link>
          <Link href={`/dashboard/${workspaceId}/members`} className="flex items-center gap-2 px-3 py-2 text-sm text-text-secondary hover:bg-muted rounded-lg">Members</Link>
          <Link href={`/dashboard/${workspaceId}/settings`} className="flex items-center gap-2 px-3 py-2 text-sm text-text-secondary hover:bg-muted rounded-lg">Settings</Link>
        </nav>
      </aside>

      <main className="ml-64 p-8">
        <div className="max-w-5xl">
          <h1 className="text-2xl font-bold text-text-primary mb-2">Audit Log</h1>
          <p className="text-sm text-text-secondary mb-6">All queries executed against your database</p>

          {error && <div className="p-3 mb-4 text-sm text-error bg-error/10 border border-error/20 rounded-lg">{error}</div>}

          {loading ? (
            <p className="text-text-secondary">Loading...</p>
          ) : logs.length === 0 ? (
            <p className="text-text-secondary">No queries logged yet.</p>
          ) : (
            <div className="bg-surface rounded-xl border border-border overflow-hidden">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-muted/50 border-b border-border">
                    <th className="px-4 py-3 text-left text-xs font-medium text-text-secondary">Time</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-text-secondary">SQL</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-text-secondary">Rows</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-text-secondary">Time (ms)</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-text-secondary">Cost</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-text-secondary">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {logs.map((log) => (
                    <tr key={log.id} className="border-t border-border/50 hover:bg-muted/30">
                      <td className="px-4 py-3 text-xs text-text-secondary whitespace-nowrap">
                        {new Date(log.created_at).toLocaleString()}
                      </td>
                      <td className="px-4 py-3 max-w-xs">
                        <code className="text-xs font-mono text-text-primary break-all line-clamp-2">{log.sql_text}</code>
                      </td>
                      <td className="px-4 py-3 text-xs text-text-secondary">{log.row_count}</td>
                      <td className="px-4 py-3 text-xs text-text-secondary">{log.execution_ms}</td>
                      <td className="px-4 py-3 text-xs text-text-secondary">{log.estimated_cost?.toFixed(0) ?? "—"}</td>
                      <td className="px-4 py-3">
                        <span className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium ${statusColors[log.status] || "text-text-secondary bg-muted"}`}>
                          {log.status}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
