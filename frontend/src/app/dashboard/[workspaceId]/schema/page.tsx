"use client";

import { useState, useEffect } from "react";
import { use, } from "react";
import Link from "next/link";
import { RefreshCw, ChevronDown, ChevronRight, Database } from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface Column {
  name: string;
  data_type: string;
  is_nullable: boolean;
  is_primary_key: boolean;
  is_foreign_key: boolean;
  references_table: string | null;
  references_column: string | null;
  sample_values: string[];
  column_comment: string | null;
}

interface Table {
  name: string;
  columns: Column[];
  row_count: number | null;
  foreign_keys: { column: string; references_table: string; references_column: string }[];
}

export default function SchemaPage({ params }: { params: Promise<{ workspaceId: string }> }) {
  const { workspaceId } = use(params);
  const [tables, setTables] = useState<Table[]>([]);
  const [version, setVersion] = useState(0);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [search, setSearch] = useState("");
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [error, setError] = useState("");

  const fetchSchema = async () => {
    const token = localStorage.getItem("zenai_token");
    try {
      const res = await fetch(`${API_BASE}/workspaces/${workspaceId}/schema`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error("Failed to load schema");
      const data = await res.json();
      setTables(data.tables || []);
      setVersion(data.version || 0);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load schema");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchSchema(); }, [workspaceId]);

  const handleRefresh = async () => {
    setRefreshing(true);
    setError("");
    try {
      const token = localStorage.getItem("zenai_token");
      const res = await fetch(`${API_BASE}/workspaces/${workspaceId}/introspect`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({}),
      });
      if (!res.ok) throw new Error("Refresh failed");
      await fetchSchema();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Refresh failed");
    } finally {
      setRefreshing(false);
    }
  };

  const toggleTable = (name: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      next.has(name) ? next.delete(name) : next.add(name);
      return next;
    });
  };

  const filtered = tables.filter(
    (t) =>
      t.name.toLowerCase().includes(search.toLowerCase()) ||
      t.columns.some((c) => c.name.toLowerCase().includes(search.toLowerCase()))
  );

  if (loading) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <p className="text-text-secondary">Loading schema...</p>
      </div>
    );
  }

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
          <Link href={`/dashboard/${workspaceId}/schema`} className="flex items-center gap-2 px-3 py-2 text-sm font-medium text-primary bg-primary/5 rounded-lg">Schema</Link>
          <Link href={`/dashboard/${workspaceId}/logs`} className="flex items-center gap-2 px-3 py-2 text-sm text-text-secondary hover:bg-muted rounded-lg">Audit Log</Link>
          <Link href={`/dashboard/${workspaceId}/members`} className="flex items-center gap-2 px-3 py-2 text-sm text-text-secondary hover:bg-muted rounded-lg">Members</Link>
          <Link href={`/dashboard/${workspaceId}/settings`} className="flex items-center gap-2 px-3 py-2 text-sm text-text-secondary hover:bg-muted rounded-lg">Settings</Link>
        </nav>
      </aside>

      <main className="ml-64 p-8">
        <div className="max-w-4xl">
          <div className="flex items-center justify-between mb-6">
            <div>
              <h1 className="text-2xl font-bold text-text-primary">Schema</h1>
              <p className="text-sm text-text-secondary mt-1">v{version} · {tables.length} tables · {tables.reduce((a, t) => a + t.columns.length, 0)} columns</p>
            </div>
            <button
              onClick={handleRefresh}
              disabled={refreshing}
              className="flex items-center gap-2 px-3 py-2 text-sm font-medium text-primary border border-primary/20 rounded-lg hover:bg-primary/5 transition-colors disabled:opacity-50"
            >
              <RefreshCw size={14} className={refreshing ? "animate-spin" : ""} />
              {refreshing ? "Refreshing..." : "Refresh Schema"}
            </button>
          </div>

          {error && (
            <div className="p-3 mb-4 text-sm text-error bg-error/10 border border-error/20 rounded-lg">{error}</div>
          )}

          <div className="mb-4">
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search tables or columns..."
              className="w-full px-3 py-2 text-sm border border-border rounded-lg bg-surface focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary"
            />
          </div>

          <div className="space-y-2">
            {filtered.map((table) => (
              <div key={table.name} className="border border-border rounded-lg bg-surface overflow-hidden">
                <button
                  onClick={() => toggleTable(table.name)}
                  className="flex items-center gap-2 w-full px-4 py-3 text-left hover:bg-muted transition-colors"
                >
                  {expanded.has(table.name) ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                  <Database size={14} className="text-primary" />
                  <span className="text-sm font-semibold text-text-primary">{table.name}</span>
                  <span className="text-xs text-text-secondary ml-1">({table.columns.length} cols)</span>
                  {table.row_count !== null && (
                    <span className="text-xs text-text-secondary ml-auto">{table.row_count.toLocaleString()} rows</span>
                  )}
                </button>

                {expanded.has(table.name) && (
                  <div className="border-t border-border">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="bg-muted/50">
                          <th className="px-4 py-2 text-left text-xs font-medium text-text-secondary">Column</th>
                          <th className="px-4 py-2 text-left text-xs font-medium text-text-secondary">Type</th>
                          <th className="px-4 py-2 text-left text-xs font-medium text-text-secondary">Nullable</th>
                          <th className="px-4 py-2 text-left text-xs font-medium text-text-secondary">Key</th>
                          <th className="px-4 py-2 text-left text-xs font-medium text-text-secondary">Sample Values</th>
                        </tr>
                      </thead>
                      <tbody>
                        {table.columns.map((col) => (
                          <tr key={col.name} className="border-t border-border/50">
                            <td className="px-4 py-2 font-mono text-xs text-text-primary">{col.name}</td>
                            <td className="px-4 py-2 text-xs text-text-secondary">{col.data_type}</td>
                            <td className="px-4 py-2 text-xs">{col.is_nullable ? "YES" : "NO"}</td>
                            <td className="px-4 py-2 text-xs">
                              {col.is_primary_key && <span className="text-primary font-medium">PK</span>}
                              {col.is_foreign_key && (
                                <span className="text-accent font-medium">FK → {col.references_table}</span>
                              )}
                            </td>
                            <td className="px-4 py-2 text-xs text-text-secondary">
                              {col.sample_values.length > 0 ? col.sample_values.join(", ") : "—"}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      </main>
    </div>
  );
}
