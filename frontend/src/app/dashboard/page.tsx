"use client";

import Link from "next/link";
import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { deleteWorkspace } from "@/lib/api";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface Workspace {
  id: string;
  name: string;
  owner_id: string;
  schema_version: number;
  created_at: string;
  role: string;
}

export default function DashboardPage() {
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [loading, setLoading] = useState(true);
  const router = useRouter();

  useEffect(() => {
    const token = localStorage.getItem("zenai_token");
    if (!token) {
      router.push("/login");
      return;
    }

    fetch(`${API_BASE}/workspaces`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((res) => res.json())
      .then((data) => {
        setWorkspaces(data.workspaces || []);
        setLoading(false);
      })
      .catch(() => {
        setLoading(false);
      });
  }, [router]);

  const handleDelete = async (e: React.MouseEvent, workspaceId: string, role: string) => {
    e.preventDefault();
    e.stopPropagation();
    if (role !== "owner") {
      alert("Only the owner can delete this workspace.");
      return;
    }
    if (!confirm("Are you sure you want to completely delete this workspace? This action cannot be undone.")) return;

    try {
      await deleteWorkspace(workspaceId);
      // Remove from state without reloading
      setWorkspaces(workspaces.filter(w => w.id !== workspaceId));
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to delete workspace");
    }
  };

  return (
    <div className="min-h-screen bg-background">
      {/* Sidebar */}
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
          <Link
            href="/dashboard"
            className="flex items-center gap-2 px-3 py-2 text-sm font-medium text-primary bg-primary/5 rounded-lg"
          >
            Workspaces
          </Link>
        </nav>
        <div className="p-4 border-t border-border">
          <button
            onClick={() => {
              localStorage.removeItem("zenai_token");
              localStorage.removeItem("zenai_user");
              router.push("/login");
            }}
            className="text-xs text-text-secondary hover:text-error transition-colors"
          >
            Sign out
          </button>
        </div>
      </aside>

      {/* Main content */}
      <main className="ml-64 p-8">
        <div className="max-w-4xl">
          <div className="flex items-center justify-between mb-8">
            <div>
              <h1 className="text-2xl font-bold text-text-primary">Workspaces</h1>
              <p className="text-sm text-text-secondary mt-1">Manage your database connections</p>
            </div>
            <Link
              href="/dashboard/new"
              className="px-4 py-2 text-sm font-medium text-white bg-primary rounded-lg hover:bg-primary-hover transition-colors"
            >
              + New Workspace
            </Link>
          </div>

          {loading ? (
            <div className="text-center py-20 text-text-secondary">Loading...</div>
          ) : workspaces.length === 0 ? (
            <div className="text-center py-20">
              <p className="text-text-secondary mb-4">No workspaces yet</p>
              <Link
                href="/dashboard/new"
                className="px-4 py-2 text-sm font-medium text-white bg-primary rounded-lg hover:bg-primary-hover transition-colors"
              >
                Create your first workspace
              </Link>
            </div>
          ) : (
            <div className="grid gap-4">
              {workspaces.map((ws) => (
                <Link
                  key={ws.id}
                  href={`/dashboard/${ws.id}`}
                  className="flex items-center justify-between p-4 rounded-xl border border-border bg-surface hover:shadow-md transition-shadow"
                >
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center">
                      <span className="text-primary font-semibold text-sm">
                        {ws.name.charAt(0).toUpperCase()}
                      </span>
                    </div>
                    <div>
                      <h3 className="text-sm font-semibold text-text-primary">{ws.name}</h3>
                      <p className="text-xs text-text-secondary">
                        v{ws.schema_version} · {ws.role}
                      </p>
                    </div>
                  </div>
                  {ws.role === "owner" && (
                    <button
                      onClick={(e) => handleDelete(e, ws.id, ws.role)}
                      className="text-xs text-error/80 hover:text-error bg-error/10 hover:bg-error/20 px-3 py-1.5 rounded transition-colors"
                      title="Delete Workspace"
                    >
                      Delete
                    </button>
                  )}
                </Link>
              ))}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
