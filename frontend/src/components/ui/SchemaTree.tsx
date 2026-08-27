"use client";

import { useState } from "react";
import { Search, ChevronDown, ChevronRight, Database, Key, Link } from "lucide-react";

interface Column {
  name: string;
  data_type: string;
  is_primary_key: boolean;
  is_foreign_key: boolean;
  references_table: string | null;
  sample_values: string[];
}

interface Table {
  name: string;
  columns: Column[];
  row_count: number | null;
}

interface SchemaTreeProps {
  tables: Table[];
  onSelectTable?: (tableName: string) => void;
}

export function SchemaTree({ tables, onSelectTable }: SchemaTreeProps) {
  const [search, setSearch] = useState("");
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  const filtered = tables.filter(
    (t) =>
      t.name.toLowerCase().includes(search.toLowerCase()) ||
      t.columns.some((c) => c.name.toLowerCase().includes(search.toLowerCase()))
  );

  const toggle = (name: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      next.has(name) ? next.delete(name) : next.add(name);
      return next;
    });
    onSelectTable?.(name);
  };

  return (
    <div className="space-y-2">
      <div className="relative">
        <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-text-secondary" />
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search tables or columns..."
          className="w-full pl-8 pr-3 py-2 text-sm border border-border rounded-lg bg-surface focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary"
        />
      </div>

      <div className="space-y-1 max-h-96 overflow-y-auto">
        {filtered.map((table) => (
          <div key={table.name} className="border border-border rounded-lg bg-surface overflow-hidden">
            <button
              onClick={() => toggle(table.name)}
              className="flex items-center gap-2 w-full px-3 py-2 text-left hover:bg-muted transition-colors"
            >
              {expanded.has(table.name) ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
              <Database size={12} className="text-primary" />
              <span className="text-sm font-medium text-text-primary">{table.name}</span>
              <span className="text-xs text-text-secondary ml-auto">{table.columns.length} cols</span>
            </button>

            {expanded.has(table.name) && (
              <div className="px-3 pb-2 space-y-0.5">
                {table.columns.map((col) => (
                  <div key={col.name} className="flex items-center gap-2 px-2 py-1 text-xs rounded hover:bg-muted/50">
                    {col.is_primary_key && <Key size={10} className="text-primary" />}
                    {col.is_foreign_key && <Link size={10} className="text-accent" />}
                    {!col.is_primary_key && !col.is_foreign_key && <span className="w-[10px]" />}
                    <span className="font-mono text-text-primary">{col.name}</span>
                    <span className="text-text-secondary">{col.data_type}</span>
                    {col.sample_values.length > 0 && (
                      <span className="text-text-secondary ml-auto truncate max-w-[120px]">
                        {col.sample_values.slice(0, 3).join(", ")}
                      </span>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
