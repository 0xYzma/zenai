"use client";

import { motion } from "framer-motion";
import { User, Bot, RotateCcw } from "lucide-react";
import { ConfidenceBadge } from "./ConfidenceBadge";
import { SQLPanel } from "./SQLPanel";
import { ChartRenderer } from "./ChartRenderer";
import type { ChatMessage } from "@/lib/api";

interface MessageBubbleProps {
  message: ChatMessage;
  onRegenerate?: () => void;
}

export function MessageBubble({ message, onRegenerate }: MessageBubbleProps) {
  const isUser = message.role === "user";

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.15, ease: "easeOut" }}
      className={`flex gap-3 ${isUser ? "justify-end" : "justify-start"}`}
    >
      {!isUser && (
        <div className="flex-shrink-0 w-8 h-8 rounded-full bg-primary flex items-center justify-center">
          <Bot size={16} className="text-white" />
        </div>
      )}

      <div className={`max-w-[75%] rounded-2xl px-4 py-3 ${
        isUser ? "bg-primary text-white rounded-br-md" : "bg-surface border border-border shadow-sm rounded-bl-md"
      }`}>
        <div className={`text-sm leading-relaxed whitespace-pre-wrap ${isUser ? "" : "text-text-primary"}`}>
          {message.content}
        </div>

        {!isUser && message.insights && message.insights.length > 0 && (
          <div className="mt-3 space-y-1">
            {message.insights.map((insight, i) => (
              <div key={i} className="flex items-start gap-2 text-sm text-text-secondary">
                <span className="text-primary mt-0.5">•</span>
                <span>{insight}</span>
              </div>
            ))}
          </div>
        )}

        {!isUser && message.chartType && message.chartType !== "none" && message.chartData && (
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.25, ease: "easeOut" }}
            className="mt-3"
          >
            <ChartRenderer chartType={message.chartType} chartData={message.chartData} />
          </motion.div>
        )}

        {!isUser && message.generatedSql && <SQLPanel sql={message.generatedSql} />}

        {!isUser && message.confidence && (
          <div className="flex items-center gap-3 mt-3 pt-2 border-t border-border">
            <ConfidenceBadge confidence={message.confidence} />
            {message.executionMs !== undefined && (
              <span className="text-xs text-text-secondary">{message.executionMs}ms</span>
            )}
            {message.rowCount !== undefined && (
              <span className="text-xs text-text-secondary">{message.rowCount} rows</span>
            )}
            {onRegenerate && (
              <button onClick={onRegenerate}
                className="ml-auto flex items-center gap-1 text-xs text-text-secondary hover:text-primary transition-colors">
                <RotateCcw size={12} /> Regenerate
              </button>
            )}
          </div>
        )}
      </div>

      {isUser && (
        <div className="flex-shrink-0 w-8 h-8 rounded-full bg-zinc-200 flex items-center justify-center">
          <User size={16} className="text-zinc-600" />
        </div>
      )}
    </motion.div>
  );
}
