"use client";

export function ThinkingIndicator() {
  return (
    <div className="flex items-center gap-2 px-4 py-3">
      <div className="flex gap-1">
        <span className="thinking-dot w-2 h-2 rounded-full bg-primary inline-block" />
        <span className="thinking-dot w-2 h-2 rounded-full bg-primary inline-block" />
        <span className="thinking-dot w-2 h-2 rounded-full bg-primary inline-block" />
      </div>
      <span className="text-text-secondary text-sm">Thinking...</span>
    </div>
  );
}
