"use client";

import { useState, useEffect } from "react";
import { use } from "react";
import Link from "next/link";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface Member {
  user_id: string;
  email: string;
  role: string;
  invited_at: string;
}

const roleColors: Record<string, string> = {
  owner: "text-primary bg-primary/10",
  admin: "text-accent bg-accent/10",
  viewer: "text-text-secondary bg-muted",
};

export default function MembersPage({ params }: { params: Promise<{ workspaceId: string }> }) {
  const { workspaceId } = use(params);
  const [members, setMembers] = useState<Member[]>([]);
  const [loading, setLoading] = useState(true);
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("viewer");
  const [inviting, setInviting] = useState(false);
  const [error, setError] = useState("");

  const fetchMembers = async () => {
    const token = localStorage.getItem("zenai_token");
    const res = await fetch(`${API_BASE}/workspaces/${workspaceId}/members`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    const data = await res.json();
    setMembers(data.members || []);
    setLoading(false);
  };

  useEffect(() => { fetchMembers(); }, [workspaceId]);

  const handleInvite = async (e: React.FormEvent) => {
    e.preventDefault();
    setInviting(true);
    setError("");
    try {
      const token = localStorage.getItem("zenai_token");
      const res = await fetch(`${API_BASE}/workspaces/${workspaceId}/members`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ email, role }),
      });
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || "Invite failed");
      }
      setEmail("");
      await fetchMembers();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Invite failed");
    } finally {
      setInviting(false);
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
          <Link href={`/dashboard/${workspaceId}/members`} className="flex items-center gap-2 px-3 py-2 text-sm font-medium text-primary bg-primary/5 rounded-lg">Members</Link>
          <Link href={`/dashboard/${workspaceId}/settings`} className="flex items-center gap-2 px-3 py-2 text-sm text-text-secondary hover:bg-muted rounded-lg">Settings</Link>
        </nav>
      </aside>

      <main className="ml-64 p-8">
        <div className="max-w-3xl">
          <h1 className="text-2xl font-bold text-text-primary mb-2">Members</h1>
          <p className="text-sm text-text-secondary mb-6">Manage who can access this workspace</p>

          {error && <div className="p-3 mb-4 text-sm text-error bg-error/10 border border-error/20 rounded-lg">{error}</div>}

          {/* Invite form */}
          <form onSubmit={handleInvite} className="flex gap-2 mb-6">
            <input
              type="email"
              suppressHydrationWarning
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="teammate@company.com"
              className="flex-1 px-3 py-2 text-sm border border-border rounded-lg bg-surface focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary"
              required
            />
            <select
              value={role}
              onChange={(e) => setRole(e.target.value)}
              className="px-3 py-2 text-sm border border-border rounded-lg bg-surface focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary"
            >
              <option value="viewer">Viewer</option>
              <option value="admin">Admin</option>
            </select>
            <button
              type="submit"
              disabled={inviting}
              className="px-4 py-2 text-sm font-medium text-white bg-primary rounded-lg hover:bg-primary-hover transition-colors disabled:opacity-50"
            >
              {inviting ? "Inviting..." : "Invite"}
            </button>
          </form>

          {loading ? (
            <p className="text-text-secondary">Loading...</p>
          ) : (
            <div className="bg-surface rounded-xl border border-border overflow-hidden">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-muted/50 border-b border-border">
                    <th className="px-4 py-3 text-left text-xs font-medium text-text-secondary">User</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-text-secondary">Role</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-text-secondary">Joined</th>
                  </tr>
                </thead>
                <tbody>
                  {members.map((m) => (
                    <tr key={m.user_id} className="border-t border-border/50">
                      <td className="px-4 py-3">
                        <p className="text-sm font-medium text-text-primary">{m.email}</p>
                      </td>
                      <td className="px-4 py-3">
                        <span className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium ${roleColors[m.role] || ""}`}>
                          {m.role}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-xs text-text-secondary">
                        {new Date(m.invited_at).toLocaleDateString()}
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
