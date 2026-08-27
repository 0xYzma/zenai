"use client";

import { useState, useEffect } from "react";
import { use } from "react";
import Link from "next/link";
import { ConnectionStatusCard } from "@/components/ui/ConnectionStatusCard";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const TIMEZONES = [
  "UTC", "US/Eastern", "US/Central", "US/Mountain", "US/Pacific",
  "Europe/London", "Europe/Paris", "Europe/Berlin",
  "Asia/Tokyo", "Asia/Shanghai", "Asia/Kolkata",
  "Australia/Sydney", "Pacific/Auckland",
];

export default function SettingsPage({ params }: { params: Promise<{ workspaceId: string }> }) {
  const { workspaceId } = use(params);
  const [connected, setConnected] = useState(false);
  const [loading, setLoading] = useState(true);
  const [deleting, setDeleting] = useState(false);
  const [tz, setTz] = useState("UTC");
  const [tzSaving, setTzSaving] = useState(false);

  useEffect(() => {
    const token = localStorage.getItem("zenai_token");
    fetch(`${API_BASE}/workspaces/${workspaceId}/schema`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((res) => { if (res.ok) { setConnected(true); } return res.json(); })
      .then((data) => { if (data.timezone) setTz(data.timezone); setLoading(false); })
      .catch(() => { setConnected(false); setLoading(false); });
  }, [workspaceId]);

  const handleDelete = async () => {
    if (!confirm("This will remove the database connection and all embeddings. Continue?")) return;
    setDeleting(true);
    try {
      const token = localStorage.getItem("zenai_token");
      await fetch(`${API_BASE}/workspaces/${workspaceId}/connection`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      });
      setConnected(false);
    } finally {
      setDeleting(false);
    }
  };

  const handleTimezoneSave = async () => {
    setTzSaving(true);
    try {
      const token = localStorage.getItem("zenai_token");
      await fetch(`${API_BASE}/workspaces/${workspaceId}/timezone`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ timezone: tz }),
      });
    } finally {
      setTzSaving(false);
    }
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
          <Link href="/dashboard" className="flex items-center gap-2 px-3 py-2 text-sm text-text-secondary hover:bg-muted rounded-lg">← Workspaces</Link>
          <Link href={`/dashboard/${workspaceId}`} className="flex items-center gap-2 px-3 py-2 text-sm text-text-secondary hover:bg-muted rounded-lg">Chat</Link>
          <Link href={`/dashboard/${workspaceId}/schema`} className="flex items-center gap-2 px-3 py-2 text-sm text-text-secondary hover:bg-muted rounded-lg">Schema</Link>
          <Link href={`/dashboard/${workspaceId}/logs`} className="flex items-center gap-2 px-3 py-2 text-sm text-text-secondary hover:bg-muted rounded-lg">Audit Log</Link>
          <Link href={`/dashboard/${workspaceId}/members`} className="flex items-center gap-2 px-3 py-2 text-sm text-text-secondary hover:bg-muted rounded-lg">Members</Link>
          <Link href={`/dashboard/${workspaceId}/settings`} className="flex items-center gap-2 px-3 py-2 text-sm font-medium text-primary bg-primary/5 rounded-lg">Settings</Link>
        </nav>
      </aside>

      <main className="ml-64 p-8">
        <div className="max-w-2xl">
          <h1 className="text-2xl font-bold text-text-primary mb-2">Settings</h1>
          <p className="text-sm text-text-secondary mb-8">Connection and workspace configuration</p>

          {/* §14.4: Connection Status Card */}
          <div className="mb-6">
            <h2 className="text-sm font-semibold text-text-primary mb-3">Database Connection</h2>
            <ConnectionStatusCard
              status={connected ? "connected" : "disconnected"}
              tableCount={connected ? undefined : 0}
            />
          </div>

          {connected && (
            <div className="bg-surface rounded-xl border border-border p-6 mb-6">
              <button onClick={handleDelete} disabled={deleting}
                className="px-4 py-2 text-sm font-medium text-error border border-error/20 rounded-lg hover:bg-error/5 transition-colors disabled:opacity-50">
                {deleting ? "Removing..." : "Disconnect & Remove"}
              </button>
            </div>
          )}

          {/* §21: Timezone Config */}
          <div className="bg-surface rounded-xl border border-border p-6 mb-6">
            <h2 className="text-sm font-semibold text-text-primary mb-4">Workspace Timezone</h2>
            <p className="text-xs text-text-secondary mb-3">Used for date-sensitive queries (e.g. &ldquo;today&rsquo;s revenue&rdquo;)</p>
            <div className="flex items-center gap-3">
              <select value={tz} onChange={(e) => setTz(e.target.value)}
                className="flex-1 px-3 py-2 text-sm border border-border rounded-lg bg-surface focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary">
                {TIMEZONES.map((tz) => (
                  <option key={tz} value={tz}>{tz}</option>
                ))}
              </select>
              <button onClick={handleTimezoneSave} disabled={tzSaving}
                className="px-4 py-2 text-sm font-medium text-white bg-primary rounded-lg hover:bg-primary-hover transition-colors disabled:opacity-50">
                {tzSaving ? "Saving..." : "Save"}
              </button>
            </div>
          </div>

          {/* Workspace Info */}
          <div className="bg-surface rounded-xl border border-border p-6">
            <h2 className="text-sm font-semibold text-text-primary mb-4">Workspace</h2>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-text-secondary">Workspace ID</span>
                <code className="font-mono text-xs text-text-primary">{workspaceId}</code>
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
