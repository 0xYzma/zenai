"use client";

import { Database, Wifi, WifiOff, Clock } from "lucide-react";

interface ConnectionStatusCardProps {
  status: "connected" | "disconnected" | "error";
  host?: string;
  port?: number;
  dbName?: string;
  lastSynced?: string;
  tableCount?: number;
  columnCount?: number;
}

const statusConfig = {
  connected: {
    color: "text-success",
    bg: "bg-success/10",
    border: "border-success/20",
    icon: Wifi,
    label: "Connected",
  },
  disconnected: {
    color: "text-text-secondary",
    bg: "bg-muted",
    border: "border-border",
    icon: WifiOff,
    label: "Disconnected",
  },
  error: {
    color: "text-error",
    bg: "bg-error/10",
    border: "border-error/20",
    icon: WifiOff,
    label: "Error",
  },
};

export function ConnectionStatusCard({
  status,
  host,
  port,
  dbName,
  lastSynced,
  tableCount,
  columnCount,
}: ConnectionStatusCardProps) {
  const config = statusConfig[status];
  const Icon = config.icon;

  return (
    <div className={`flex items-center gap-4 p-4 rounded-xl border ${config.border} ${config.bg}`}>
      <div className={`w-10 h-10 rounded-lg ${config.bg} flex items-center justify-center`}>
        <Icon size={18} className={config.color} />
      </div>
      <div className="flex-1">
        <div className="flex items-center gap-2">
          <span className={`text-sm font-semibold ${config.color}`}>{config.label}</span>
          <div className={`w-2 h-2 rounded-full ${status === "connected" ? "bg-success" : status === "error" ? "bg-error" : "bg-text-secondary"}`} />
        </div>
        {host && (
          <p className="text-xs text-text-secondary mt-0.5">
            {host}:{port}/{dbName}
          </p>
        )}
      </div>
      <div className="text-right text-xs text-text-secondary space-y-0.5">
        {tableCount !== undefined && (
          <div className="flex items-center gap-1 justify-end">
            <Database size={10} />
            <span>{tableCount} tables</span>
          </div>
        )}
        {lastSynced && (
          <div className="flex items-center gap-1 justify-end">
            <Clock size={10} />
            <span>{lastSynced}</span>
          </div>
        )}
      </div>
    </div>
  );
}
