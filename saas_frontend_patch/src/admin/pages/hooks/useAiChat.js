import { useState, useRef, useEffect, useCallback } from "react";
import {
  downloadAiMessageCsv, getAiConversation, getAiScope, getAiUsage, getProactiveInsights, listAiConversations,
  sendAiFeedback, streamAiChat,
} from "@/services/aiInsightsService";
import DOMPurify from "dompurify";

export function useAiChat(isBn) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  const [accessError, setAccessError] = useState("");
  const [lastQuestion, setLastQuestion] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [conversationId, setConversationId] = useState(null);
  const [usage, setUsage] = useState(null);
  const [conversations, setConversations] = useState([]);
  const [loadingConversation, setLoadingConversation] = useState(false);
  const [scope, setScope] = useState(null);
  const [selectedLocation, setSelectedLocation] = useState("");
  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState("");
  const [exportingMessageId, setExportingMessageId] = useState(null);
  const [proactive, setProactive] = useState([]);
  const [proactiveLoading, setProactiveLoading] = useState(true);
  const abortRef = useRef(null);

  const refreshUsage = useCallback(() => {
    getAiUsage().then(setUsage).catch(() => undefined);
  }, []);

  const refreshConversations = useCallback(() => {
    listAiConversations().then((result) => setConversations(result?.items || []))
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    refreshUsage();
    refreshConversations();
    getAiScope().then((result) => {
      setScope(result);
      setSelectedLocation(result?.selected_location_id || "");
      setAccessError("");
    }).catch((err) => {
      setAccessError(err.message || (isBn
        ? "AI Insights ব্যবহারের অনুমতি পাওয়া যায়নি"
        : "AI Insights access could not be verified"));
    });
  }, [isBn, refreshUsage, refreshConversations]);

  useEffect(() => {
    if (Boolean(fromDate) !== Boolean(toDate)) return;
    let active = true;
    setProactiveLoading(true);
    getProactiveInsights({
      locationId: selectedLocation || undefined,
      from: fromDate || undefined,
      to: toDate || undefined,
    }).then((result) => {
      if (active) setProactive(result?.cards || []);
    }).catch(() => {
      if (active) setProactive([]);
    }).finally(() => {
      if (active) setProactiveLoading(false);
    });
    return () => { active = false; };
  }, [selectedLocation, fromDate, toDate]);

  const startNewConversation = () => {
    if (streaming) return;
    setConversationId(null);
    setMessages([]);
    setError("");
  };

  const openConversation = async (id) => {
    if (streaming || id === conversationId) return;
    setLoadingConversation(true);
    setError("");
    try {
      const conversation = await getAiConversation(id);
      setConversationId(conversation.id);
      setSelectedLocation(conversation.scope?.location_id || "");
      setFromDate(conversation.scope?.from || "");
      setToDate(conversation.scope?.to || "");
      setMessages((conversation.messages || []).map((message) => ({
        role: message.role,
        content: DOMPurify.sanitize(message.content), // Add Sanitization!
        messageId: message.id,
        insights: message.insights || [],
        confidence: message.confidence,
        chartData: message.chart_data,
        chartType: message.chart_type,
        source: message.sources?.[0]?.tool,
        feedback: message.feedback,
      })));
    } catch (err) {
      setError(err.message);
    } finally {
      setLoadingConversation(false);
    }
  };

  const rateMessage = async (index, messageId, rating) => {
    if (!messageId) return;
    try {
      await sendAiFeedback(messageId, rating);
      setMessages((current) => current.map((message, messageIndex) => (
        messageIndex === index ? { ...message, feedback: rating } : message
      )));
    } catch (err) {
      setError(err.message);
    }
  };

  const exportMessage = async (messageId) => {
    setExportingMessageId(messageId);
    setError("");
    try {
      await downloadAiMessageCsv(messageId);
    } catch (err) {
      setError(err.message);
    } finally {
      setExportingMessageId(null);
    }
  };

  const send = async (question = input, options = {}) => {
    const clean = question.trim();
    if (!clean || streaming || accessError) return;
    if ((fromDate && !toDate) || (!fromDate && toDate) || (fromDate && toDate && fromDate > toDate)) {
      setError(isBn ? "সঠিক শুরু এবং শেষের তারিখ নির্বাচন করুন" : "Select a valid start and end date");
      return;
    }

    if (!options.retry) {
      setMessages((current) => [...current, { role: "user", content: DOMPurify.sanitize(clean) }]);
    }
    setLastQuestion(clean);
    setInput("");
    setError("");
    setStatus(isBn ? "প্রশ্ন বিশ্লেষণ করা হচ্ছে..." : "Analyzing your question...");
    setStreaming(true);
    const controller = new AbortController();
    abortRef.current = controller;

    try {
      await streamAiChat(
        {
          question: clean,
          conversation_id: conversationId || undefined,
          location_id: selectedLocation || undefined,
          ...(fromDate && toDate ? { date_range: { from: fromDate, to: toDate } } : {}),
          locale: isBn ? "bn-BD" : "en-BD",
          timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || "Asia/Dhaka",
        },
        {
          signal: controller.signal,
          onEvent: (event) => {
            if (event.type === "meta" && event.conversation_id) {
              setConversationId(event.conversation_id);
            } else if (event.type === "status") {
              setStatus(event.message || "");
            } else if (event.type === "answer") {
              setMessages((current) => [...current, {
                role: "assistant",
                content: DOMPurify.sanitize(event.answer || event.message || ""), // Sanitization
                insights: event.insights || [],
                confidence: event.confidence,
                chartData: event.chart_data,
                chartType: event.chart_type,
                source: event.sources?.[0]?.tool,
                messageId: event.message_id,
              }]);
            } else if (event.type === "error") {
              setError(event.message || "AI Insights is temporarily unavailable");
            }
          },
        },
      );
    } catch (err) {
      if (err?.name !== "AbortError") setError(err.message);
    } finally {
      abortRef.current = null;
      setStatus("");
      setStreaming(false);
      refreshUsage();
      refreshConversations();
    }
  };

  const stop = () => abortRef.current?.abort();

  return {
    messages, input, setInput, status, error, accessError, lastQuestion, streaming,
    conversationId, usage, conversations, loadingConversation, scope, selectedLocation,
    setSelectedLocation, fromDate, setFromDate, toDate, setToDate, exportingMessageId,
    proactive, proactiveLoading, startNewConversation, openConversation, rateMessage,
    exportMessage, send, stop
  };
}
