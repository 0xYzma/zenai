"use client";

import clsx from "clsx";

interface ConfidenceBadgeProps {
  confidence: "high" | "medium" | "low";
}

const styles: Record<string, string> = {
  high: "bg-success/10 text-success border-success/20",
  medium: "bg-warning/10 text-warning border-warning/20",
  low: "bg-error/10 text-error border-error/20",
};

export function ConfidenceBadge({ confidence }: ConfidenceBadgeProps) {
  return (
    <span
      className={clsx(
        "inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border",
        styles[confidence] || styles.medium
      )}
    >
      {confidence.charAt(0).toUpperCase() + confidence.slice(1)} confidence
    </span>
  );
}
