"use client";

import Link from "next/link";

export default function Home() {
  return (
    <div className="min-h-screen bg-background flex flex-col">
      {/* Hero */}
      <main className="flex-1 flex items-center justify-center px-4">
        <div className="max-w-2xl text-center">
          <div className="w-20 h-20 rounded-2xl bg-primary flex items-center justify-center mx-auto mb-6">
            <span className="text-white text-3xl font-bold">Z</span>
          </div>
          <h1 className="text-5xl font-bold text-text-primary mb-4 tracking-tight">
            ZenAI
          </h1>
          <p className="text-xl text-text-secondary mb-2">
            Ask your business data anything.
          </p>
          <p className="text-sm text-text-secondary mb-8 max-w-lg mx-auto">
            Connect your PostgreSQL database and get instant, data-backed answers
            to natural language questions — no SQL knowledge required.
          </p>
          <div className="flex items-center justify-center gap-4">
            <Link
              href="/login"
              className="px-6 py-3 text-sm font-medium text-white bg-primary rounded-xl hover:bg-primary-hover transition-colors"
            >
              Get Started
            </Link>
            <Link
              href="/register"
              className="px-6 py-3 text-sm font-medium text-text-primary border border-border rounded-xl hover:bg-muted transition-colors"
            >
              Create Account
            </Link>
          </div>

          {/* Feature cards */}
          <div className="grid grid-cols-3 gap-4 mt-16 text-left">
            <div className="p-4 rounded-xl border border-border bg-surface">
              <div className="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center mb-3">
                <span className="text-primary text-sm">SQL</span>
              </div>
              <h3 className="text-sm font-semibold text-text-primary mb-1">Natural Language → SQL</h3>
              <p className="text-xs text-text-secondary">
                Ask in plain English, get answers grounded in real SQL queries.
              </p>
            </div>
            <div className="p-4 rounded-xl border border-border bg-surface">
              <div className="w-8 h-8 rounded-lg bg-success/10 flex items-center justify-center mb-3">
                <span className="text-success text-sm">Safe</span>
              </div>
              <h3 className="text-sm font-semibold text-text-primary mb-1">Read-Only &amp; Secure</h3>
              <p className="text-xs text-text-secondary">
                Your data is never modified. Hardened SQL validation keeps it safe.
              </p>
            </div>
            <div className="p-4 rounded-xl border border-border bg-surface">
              <div className="w-8 h-8 rounded-lg bg-accent/10 flex items-center justify-center mb-3">
                <span className="text-accent text-sm">Charts</span>
              </div>
              <h3 className="text-sm font-semibold text-text-primary mb-1">Instant Insights</h3>
              <p className="text-xs text-text-secondary">
                Get explanations, charts, and key insights from every answer.
              </p>
            </div>
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="py-6 text-center text-xs text-text-secondary border-t border-border">
        ZenAI — Built for NexPOS &amp; beyond
      </footer>
    </div>
  );
}
