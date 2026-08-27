"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { Send, RotateCcw, Square, Download } from "lucide-react";
import { MessageBubble } from "./MessageBubble";
import { ThinkingIndicator } from "./ThinkingIndicator";
import { streamChat, type ChatMessage, type ChatResponse } from "@/lib/api";

interface ChatInterfaceProps {
  workspaceId: string;
}

export function ChatInterface({ workspaceId }: ChatInterfaceProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [sessionId] = useState(() => crypto.randomUUID());
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSend = useCallback(async (question?: string, retryIndex?: number) => {
    const q = question || input.trim();
    if (!q || isStreaming) return;

    setInput("");
    abortRef.current = new AbortController();

    let userMessage: ChatMessage;
    if (retryIndex !== undefined) {
      // Regenerate: replace the assistant message at retryIndex
      setMessages((prev) => {
        const updated = [...prev];
        updated.splice(retryIndex, 1);
        return updated;
      });
      userMessage = { id: crypto.randomUUID(), role: "user", content: q };
    } else {
      userMessage = { id: crypto.randomUUID(), role: "user", content: q };
      setMessages((prev) => [...prev, userMessage]);
    }

    setIsStreaming(true);
    let assistantMessage: ChatMessage = { id: crypto.randomUUID(), role: "assistant", content: "" };
    setMessages((prev) => [...prev, assistantMessage]);

    try {
      for await (const chunk of streamChat(workspaceId, q, sessionId)) {
        if (abortRef.current?.signal.aborted) break;

        if (chunk.type === "status" && chunk.message) {
          setMessages((prev) => {
            const updated = [...prev];
            const last = updated[updated.length - 1];
            if (last.role === "assistant") last.content = chunk.message!;
            return [...updated];
          });
        }

        if (chunk.type === "answer") {
          assistantMessage = {
            ...assistantMessage,
            id: chunk.message_id || assistantMessage.id,
            content: chunk.answer || "No answer generated.",
            generatedSql: chunk.generated_sql,
            chartType: chunk.chart_type,
            chartData: chunk.chart_data,
            confidence: chunk.confidence as ChatMessage["confidence"],
            executionMs: chunk.execution_ms,
            insights: chunk.insights,
            rowCount: chunk.row_count,
          };
          setMessages((prev) => {
            const updated = [...prev];
            updated[updated.length - 1] = assistantMessage;
            return [...updated];
          });
        }
      }
    } catch (error) {
      if (error instanceof Error && error.name === "AbortError") {
        setMessages((prev) => {
          const updated = [...prev];
          updated[updated.length - 1] = { ...assistantMessage, content: "Generation stopped." };
          return [...updated];
        });
      } else {
        setMessages((prev) => {
          const updated = [...prev];
          updated[updated.length - 1] = {
            ...assistantMessage,
            content: `Error: ${error instanceof Error ? error.message : "Failed to get response"}`,
          };
          return [...updated];
        });
      }
    } finally {
      setIsStreaming(false);
      abortRef.current = null;
    }
  }, [input, isStreaming, workspaceId, sessionId]);

  const handleStop = () => {
    abortRef.current?.abort();
  };

  const handleRegenerate = (index: number) => {
    const userMsg = messages[index - 1];
    if (userMsg?.role === "user") {
      handleSend(userMsg.content, index);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (isStreaming) {
        handleStop();
      } else {
        handleSend();
      }
    }
  };

  const handleDownloadRaw = (msg: ChatMessage) => {
    if (!msg.id) return;
    const token = localStorage.getItem("zenai_token");
    // Since we need to pass auth token, we can fetch the CSV as blob and then save it
    fetch(`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/workspaces/${workspaceId}/chat/${msg.id}/download`, {
      headers: { Authorization: `Bearer ${token}` }
    })
    .then(res => res.blob())
    .then(blob => {
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `results_${msg.id}.csv`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    })
    .catch(console.error);
  };

  return (
    <div className="flex flex-col h-screen bg-background">
      {/* Header */}
      <header className="flex items-center justify-between px-6 py-4 border-b border-border bg-surface">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-primary flex items-center justify-center">
            <span className="text-white font-bold text-sm">Z</span>
          </div>
          <div>
            <h1 className="text-lg font-semibold text-text-primary">ZenAI</h1>
            <p className="text-xs text-text-secondary">Ask your business data anything</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-success" />
          <span className="text-xs text-text-secondary">Connected</span>
        </div>
      </header>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-[800px] mx-auto px-4 py-6 space-y-6">
          {messages.length === 0 && (
            <div className="text-center py-20">
              <div className="w-16 h-16 rounded-2xl bg-primary/10 flex items-center justify-center mx-auto mb-4">
                <span className="text-primary text-2xl font-bold">Z</span>
              </div>
              <h2 className="text-xl font-semibold text-text-primary mb-2">Ask your business data anything</h2>
              <p className="text-text-secondary text-sm max-w-md mx-auto">
                Try: &ldquo;Why did Tuesday&apos;s revenue drop?&rdquo; or &ldquo;Which store had the most refunds this week?&rdquo;
              </p>
              <div className="flex flex-wrap gap-2 justify-center mt-6">
                {[
                  "What were the top 5 products by revenue last month?",
                  "Show me daily revenue for the past week",
                  "Which category has the highest refund rate?",
                ].map((s) => (
                  <button key={s} onClick={() => handleSend(s)}
                    className="px-3 py-1.5 text-xs text-text-secondary border border-border rounded-full hover:bg-muted transition-colors">
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((msg, i) => (
            <div key={msg.id}>
              <MessageBubble
                message={msg}
                onRegenerate={msg.role === "assistant" && i === messages.length - 1 && !isStreaming ? () => handleRegenerate(i) : undefined}
              />
              {msg.role === "assistant" && msg.generatedSql && (
                <div className="ml-11 mt-1">
                  <button onClick={() => handleDownloadRaw(msg)}
                    className="flex items-center gap-1 text-xs text-text-secondary hover:text-primary transition-colors">
                    <Download size={12} /> Download Raw Results (CSV)
                  </button>
                </div>
              )}
            </div>
          ))}

          {isStreaming && messages[messages.length - 1]?.role !== "assistant" && <ThinkingIndicator />}
          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Input bar */}
      <div className="border-t border-border bg-surface">
        <div className="max-w-[800px] mx-auto px-4 py-3">
          <div className="flex items-end gap-2 bg-background rounded-2xl border border-border p-2">
            <textarea
              ref={inputRef} value={input} onChange={(e) => setInput(e.target.value)} onKeyDown={handleKeyDown}
              placeholder="Ask a question about your data..." rows={1}
              className="flex-1 resize-none bg-transparent px-3 py-2 text-sm text-text-primary placeholder:text-text-secondary focus:outline-none"
              style={{ maxHeight: "120px" }}
            />
            {isStreaming ? (
              <button onClick={handleStop}
                className="flex-shrink-0 w-9 h-9 rounded-xl bg-error text-white flex items-center justify-center hover:bg-error/90 transition-colors">
                <Square size={16} />
              </button>
            ) : (
              <button onClick={() => handleSend()} disabled={!input.trim()}
                className="flex-shrink-0 w-9 h-9 rounded-xl bg-primary text-white flex items-center justify-center hover:bg-primary-hover transition-colors disabled:opacity-50 disabled:cursor-not-allowed">
                <Send size={16} />
              </button>
            )}
          </div>
          <p className="text-xs text-text-secondary text-center mt-2">
            ZenAI generates SQL to query your database. Always verify important numbers.
          </p>
        </div>
      </div>
    </div>
  );
}
