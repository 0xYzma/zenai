"use client";

import { useState } from "react";
import { ChevronDown, ChevronRight, Copy, Check } from "lucide-react";
import clsx from "clsx";

interface SQLPanelProps {
  sql: string;
}

export function SQLPanel({ sql }: SQLPanelProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(sql);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="mt-2 border border-border rounded-lg overflow-hidden">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-2 w-full px-3 py-2 text-sm text-text-secondary hover:bg-muted transition-colors"
      >
        {isOpen ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        <span className="font-mono text-xs">Show SQL</span>
      </button>

      {isOpen && (
        <div className="relative bg-zinc-900 text-zinc-100 p-3 text-sm font-mono">
          <button
            onClick={handleCopy}
            className="absolute top-2 right-2 p-1 rounded hover:bg-zinc-700 transition-colors"
          >
            {copied ? <Check size={14} className="text-success" /> : <Copy size={14} />}
          </button>
          <pre className="whitespace-pre-wrap break-all pr-8">{sql}</pre>
        </div>
      )}
    </div>
  );
}
