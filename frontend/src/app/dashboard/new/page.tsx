"use client";

import Link from "next/link";
import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { connectDatabase, introspectSchema, getSchema } from "@/lib/api";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface SchemaTable {
  name: string;
  columns: { name: string; data_type: string }[];
  row_count: number | null;
}

export default function NewWorkspacePage() {
  const router = useRouter();
  const [step, setStep] = useState<"name" | "connect" | "tables" | "done">("name");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [workspaceName, setWorkspaceName] = useState("");
  const [workspaceId, setWorkspaceId] = useState("");
  const [tableCount, setTableCount] = useState(0);
  const [schemaTables, setSchemaTables] = useState<SchemaTable[]>([]);
  const [selectedTables, setSelectedTables] = useState<Set<string>>(new Set());
  const [selectAll, setSelectAll] = useState(true);
  const [form, setForm] = useState({ host: "localhost", port: 5432, db_name: "", username: "", password: "" });

  useEffect(() => {
    const token = localStorage.getItem("zenai_token");
    if (!token) router.push("/login");
  }, [router]);

  const handleCreateWorkspace = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const token = localStorage.getItem("zenai_token");
      const res = await fetch(`${API_BASE}/workspaces`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ name: workspaceName }),
      });
      if (!res.ok) throw new Error("Failed to create workspace");
      const data = await res.json();
      setWorkspaceId(data.id);
      setStep("connect");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed");
    } finally {
      setLoading(false);
    }
  };

  const handleConnect = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const result = await connectDatabase(workspaceId, form);
      if (result.connected) {
        setTableCount(result.table_count || 0);
        if (result.tables) {
          setSchemaTables(
            result.tables.map((t) => ({
              name: t.name,
              columns: new Array(t.column_count).fill({ name: "", data_type: "" }),
              row_count: null,
            }))
          );
        }
        setStep("tables");
      } else {
        setError(result.detail || "Connection failed");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Connection failed");
    } finally {
      setLoading(false);
    }
  };

  const handleIntrospect = async () => {
    setLoading(true);
    try {
      const tablesToIndex = selectAll ? undefined : Array.from(selectedTables);
      await introspectSchema(workspaceId, tablesToIndex);
      setStep("done");
      router.push(`/dashboard/${workspaceId}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Introspection failed");
    } finally {
      setLoading(false);
    }
  };

  const toggleTable = (name: string) => {
    setSelectedTables((prev) => {
      const next = new Set(prev);
      next.has(name) ? next.delete(name) : next.add(name);
      return next;
    });
  };

  const toggleSelectAll = () => {
    if (selectAll) {
      setSelectedTables(new Set());
    } else {
      setSelectedTables(new Set(schemaTables.map((t) => t.name)));
    }
    setSelectAll(!selectAll);
  };

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
          <Link href="/dashboard" className="flex items-center gap-2 px-3 py-2 text-sm font-medium text-text-secondary hover:bg-muted rounded-lg">← Back to Workspaces</Link>
        </nav>
      </aside>

      <main className="ml-64 p-8">
        <div className="max-w-lg">
          <h1 className="text-2xl font-bold text-text-primary mb-2">New Workspace</h1>
          <p className="text-sm text-text-secondary mb-8">Set up a new workspace for your database</p>

          {error && <div className="p-3 mb-4 text-sm text-error bg-error/10 border border-error/20 rounded-lg">{error}</div>}

          {step === "name" && (
            <form onSubmit={handleCreateWorkspace} className="space-y-4 bg-surface p-6 rounded-xl border border-border">
              <div>
                <label className="block text-sm font-medium text-text-primary mb-1">Workspace Name</label>
                <input type="text" value={workspaceName} onChange={(e) => setWorkspaceName(e.target.value)}
                  className="w-full px-3 py-2 text-sm border border-border rounded-lg bg-surface focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary"
                  placeholder="e.g. NexPOS, My Store" required />
              </div>
              <button type="submit" disabled={loading}
                className="w-full py-2.5 text-sm font-medium text-white bg-primary rounded-lg hover:bg-primary-hover transition-colors disabled:opacity-50">
                {loading ? "Creating..." : "Create Workspace"}
              </button>
            </form>
          )}

          {step === "connect" && (
            <form onSubmit={handleConnect} className="space-y-4 bg-surface p-6 rounded-xl border border-border">
              <h3 className="text-sm font-semibold text-text-primary mb-2">Connect your PostgreSQL database</h3>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-text-primary mb-1">Host</label>
                  <input type="text" value={form.host} onChange={(e) => setForm({ ...form, host: e.target.value })}
                    className="w-full px-3 py-2 text-sm border border-border rounded-lg bg-surface focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary" required />
                </div>
                <div>
                  <label className="block text-sm font-medium text-text-primary mb-1">Port</label>
                  <input type="number" value={form.port} onChange={(e) => setForm({ ...form, port: parseInt(e.target.value) })}
                    className="w-full px-3 py-2 text-sm border border-border rounded-lg bg-surface focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary" required />
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-text-primary mb-1">Database Name</label>
                <input type="text" value={form.db_name} onChange={(e) => setForm({ ...form, db_name: e.target.value })}
                  className="w-full px-3 py-2 text-sm border border-border rounded-lg bg-surface focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary"
                  placeholder="my_database" required />
              </div>
              <div>
                <label className="block text-sm font-medium text-text-primary mb-1">Username</label>
                <input type="text" value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })}
                  className="w-full px-3 py-2 text-sm border border-border rounded-lg bg-surface focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary" required />
              </div>
              <div>
                <label className="block text-sm font-medium text-text-primary mb-1">Password</label>
                <input type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })}
                  className="w-full px-3 py-2 text-sm border border-border rounded-lg bg-surface focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary" required />
              </div>
              <button type="submit" disabled={loading}
                className="w-full py-2.5 text-sm font-medium text-white bg-primary rounded-lg hover:bg-primary-hover transition-colors disabled:opacity-50">
                {loading ? "Testing connection..." : "Test & Connect"}
              </button>
            </form>
          )}

          {step === "tables" && (
            <div className="bg-surface p-6 rounded-xl border border-border">
              <div className="flex items-center gap-3 mb-4">
                <div className="w-10 h-10 rounded-lg bg-success/10 flex items-center justify-center">
                  <span className="text-success text-lg">✓</span>
                </div>
                <div>
                  <h3 className="text-sm font-semibold text-text-primary">Connected!</h3>
                  <p className="text-xs text-text-secondary">Found {tableCount} tables</p>
                </div>
              </div>

              <p className="text-sm text-text-secondary mb-3">Select tables to index for AI queries (§5.3 — table selection for large schemas):</p>

              <div className="flex items-center gap-2 mb-2 pb-2 border-b border-border">
                <input type="checkbox" checked={selectAll} onChange={toggleSelectAll}
                  className="w-4 h-4 rounded border-border text-primary focus:ring-primary/20" />
                <label className="text-sm font-medium text-text-primary">
                  {selectAll ? "All tables selected" : `${selectedTables.size} of ${tableCount} selected`}
                </label>
              </div>

              <div className="max-h-60 overflow-y-auto space-y-1 mb-4">
                {schemaTables.map((t) => (
                  <label key={t.name} className="flex items-center gap-2 px-2 py-1.5 rounded hover:bg-muted cursor-pointer">
                    <input type="checkbox" checked={selectedTables.has(t.name)} onChange={() => toggleTable(t.name)}
                      disabled={selectAll}
                      className="w-4 h-4 rounded border-border text-primary focus:ring-primary/20" />
                    <span className="text-sm text-text-primary">{t.name}</span>
                    <span className="text-xs text-text-secondary ml-auto">{t.columns.length} cols</span>
                  </label>
                ))}
              </div>

              <button onClick={handleIntrospect} disabled={loading || (!selectAll && selectedTables.size === 0)}
                className="w-full py-2.5 text-sm font-medium text-white bg-primary rounded-lg hover:bg-primary-hover transition-colors disabled:opacity-50">
                {loading ? "Scanning schema..." : `Index ${selectAll ? "all" : selectedTables.size} tables`}
              </button>
            </div>
          )}

          {step === "done" && (
            <div className="bg-surface p-6 rounded-xl border border-border text-center">
              <div className="w-12 h-12 rounded-full bg-success/10 flex items-center justify-center mx-auto mb-4">
                <span className="text-success text-xl">✓</span>
              </div>
              <h3 className="text-lg font-semibold text-text-primary mb-2">All Set!</h3>
              <p className="text-sm text-text-secondary">Redirecting to your workspace...</p>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
