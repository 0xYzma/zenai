import { useTranslation } from "react-i18next";
import {
  AlertTriangle, Bot, BrainCircuit, Building2, CalendarDays, ChartNoAxesCombined, Download, RefreshCw, Send, Sparkles,
  Square, ThumbsDown, ThumbsUp, TrendingUp, PackageSearch, Users, WalletCards,
} from "lucide-react";
import DOMPurify from "dompurify";

import { useThemeClasses } from "../utils/themeClasses";
import { useAiChat } from "./hooks/useAiChat";
import { AIHistoryPanel } from "./components/AIHistoryPanel";
import { InsightChart, DataTable } from "./components/AIChartRenderer";


const PROMPTS = {
  en: [
    "Summarize sales and profit for this month",
    "Which products may run out soon?",
    "How much money is locked in dead stock?",
    "Show customer retention and repeat sales",
  ],
  bn: [
    "এই মাসের বিক্রয় ও লাভের সারাংশ দেখান",
    "কোন পণ্যের স্টক শীঘ্রই শেষ হতে পারে?",
    "ডেড স্টকে কত টাকা আটকে আছে?",
    "রিটার্নিং কাস্টমার ও রিপিট সেলস দেখান",
  ],
};

const iconFor = [TrendingUp, PackageSearch, WalletCards, Users];
const PROACTIVE_ICONS = {
  sales: TrendingUp,
  profit: WalletCards,
  inventory: PackageSearch,
  orders: AlertTriangle,
  product: Sparkles,
};

export default function AIInsightsPage() {
  const { i18n } = useTranslation();
  const isBn = i18n.language?.startsWith("bn");
  const { isDark, cardBg, cardBorder, textColor, textMuted, inputBg, inputBorder } = useThemeClasses();
  
  const chat = useAiChat(isBn);
  const prompts = isBn ? PROMPTS.bn : PROMPTS.en;

  const formatCardValue = (card) => {
    if (card.value_type === "currency") {
      return new Intl.NumberFormat("en-BD", {
        style: "currency", currency: "BDT", maximumFractionDigits: 0,
      }).format(Number(card.value || 0));
    }
    if (card.value_type === "percent") return `${card.value}%`;
    if (card.value_type === "number") return new Intl.NumberFormat("en-BD").format(Number(card.value || 0));
    return String(card.value ?? "—");
  };

  return (
    <div className={`min-h-screen p-4 md:p-8 ${isDark ? "bg-slate-950" : "bg-slate-50"}`}>
      <div className="mx-auto max-w-6xl">
        <header className="mb-6 flex items-start gap-4">
          <div className="rounded-2xl bg-gradient-to-br from-indigo-600 to-cyan-500 p-3 text-white shadow-lg shadow-indigo-500/20" aria-hidden="true">
            <BrainCircuit size={26} />
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <h1 className={`text-2xl font-black ${textColor}`}>
                {isBn ? "AI বিজনেস ইনসাইটস" : "AI Business Insights"}
              </h1>
              <span className="rounded-full border border-indigo-500/20 bg-indigo-500/10 px-2 py-0.5 text-[10px] font-black uppercase tracking-wider text-indigo-500" aria-label="Beta version">Beta</span>
            </div>
            <p className={`mt-1 text-sm ${textMuted}`}>
              {isBn ? "আপনার ব্যবসার তথ্য থেকে উত্তর, প্রবণতা এবং করণীয় জানুন" : "Ask questions and discover trends and actions from your business data"}
            </p>
          </div>
          {chat.usage && (
            <div className={`ml-auto shrink-0 rounded-xl border px-3 py-2 text-right ${cardBorder} ${cardBg}`} role="status" aria-label="AI usage quota">
              <div className={`text-[10px] font-bold uppercase tracking-wide ${textMuted}`}>
                {isBn ? "মাসিক ব্যবহার" : "Monthly usage"}
              </div>
              <div className={`text-sm font-black ${textColor}`}>
                {chat.usage.used} / {chat.usage.limit < 0 ? "∞" : chat.usage.limit}
              </div>
            </div>
          )}
        </header>

        <section className="mb-5" aria-label={isBn ? "ব্যবসার গুরুত্বপূর্ণ ইনসাইট" : "Proactive business insights"}>
          <div className="mb-2 flex items-center justify-between">
            <h2 className={`text-sm font-black ${textColor}`}>{isBn ? "আজকের গুরুত্বপূর্ণ ইনসাইট" : "Proactive insights"}</h2>
            {chat.proactiveLoading && <RefreshCw size={14} className="animate-spin text-indigo-500" aria-label="Loading insights" />}
          </div>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
            {(chat.proactiveLoading && chat.proactive.length === 0 ? Array.from({ length: 5 }) : chat.proactive).map((card, index) => {
              if (!card) return <div key={index} className={`h-32 animate-pulse rounded-2xl border ${cardBg} ${cardBorder}`} aria-hidden="true" />;
              const Icon = PROACTIVE_ICONS[card.kind] || Sparkles;
              const tone = card.severity === "critical" ? "text-red-500 bg-red-500/10"
                : card.severity === "warning" ? "text-amber-500 bg-amber-500/10"
                : card.severity === "positive" ? "text-emerald-500 bg-emerald-500/10"
                : "text-indigo-500 bg-indigo-500/10";
              return (
                <article key={card.id} className={`rounded-2xl border p-4 ${cardBg} ${cardBorder}`}>
                  <div className="flex items-start justify-between gap-2">
                    <div className={`rounded-xl p-2 ${tone}`} aria-hidden="true"><Icon size={17} /></div>
                    {card.action_url && <a href={card.action_url} className="text-[10px] font-bold text-indigo-500 hover:underline focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2">{isBn ? "খুলুন" : "Open"}</a>}
                  </div>
                  <div className={`mt-3 truncate text-lg font-black ${textColor}`} title={formatCardValue(card)}>{formatCardValue(card)}</div>
                  <h3 className={`text-xs font-bold ${textColor}`}>{card.title}</h3>
                  <div className={`mt-1 line-clamp-2 text-[11px] leading-4 ${textMuted}`}>{card.detail}</div>
                  <button onClick={() => chat.send(card.prompt)} disabled={chat.streaming || Boolean(chat.accessError)} className="mt-2 text-[10px] font-bold text-indigo-500 hover:underline disabled:opacity-40 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2">{isBn ? "বিশ্লেষণ করুন" : "Analyze"}</button>
                </article>
              );
            })}
          </div>
        </section>

        <main className={`overflow-hidden rounded-3xl border ${cardBg} ${cardBorder}`}>
          <AIHistoryPanel 
            isBn={isBn} 
            streaming={chat.streaming} 
            startNewConversation={chat.startNewConversation} 
            conversations={chat.conversations} 
            conversationId={chat.conversationId} 
            openConversation={chat.openConversation} 
            loadingConversation={chat.loadingConversation} 
            cardBorder={cardBorder} 
            textColor={textColor} 
            textMuted={textMuted} 
          />
          
          <div className={`flex flex-wrap items-center gap-3 border-b px-4 py-3 ${cardBorder}`} role="search" aria-label="Data filters">
            <label className={`flex items-center gap-2 rounded-xl border px-3 py-2 text-xs ${inputBg} ${inputBorder}`}>
              <Building2 size={15} className="text-indigo-500" aria-hidden="true" />
              <span className="sr-only">{isBn ? "শাখা" : "Branch"}</span>
              <select value={chat.selectedLocation} onChange={(event) => chat.setSelectedLocation(event.target.value)} disabled={chat.streaming || !chat.scope} className={`bg-transparent font-semibold outline-none focus:ring-2 focus:ring-indigo-500 ${textColor}`}>
                {chat.scope?.all_branches_allowed && <option value="">{isBn ? "সব শাখা" : "All branches"}</option>}
                {(chat.scope?.locations || []).map((location) => <option key={location.id} value={location.id}>{location.name}</option>)}
              </select>
            </label>
            <fieldset className={`flex items-center gap-2 rounded-xl border px-3 py-2 ${inputBg} ${inputBorder}`}>
              <legend className="sr-only">Date Range</legend>
              <CalendarDays size={15} className="text-indigo-500" aria-hidden="true" />
              <input type="date" value={chat.fromDate} max={chat.toDate || undefined} onChange={(event) => chat.setFromDate(event.target.value)} disabled={chat.streaming} className={`bg-transparent text-xs font-semibold outline-none focus:ring-2 focus:ring-indigo-500 ${textColor}`} aria-label="From date" />
              <span className={textMuted} aria-hidden="true">–</span>
              <input type="date" value={chat.toDate} min={chat.fromDate || undefined} onChange={(event) => chat.setToDate(event.target.value)} disabled={chat.streaming} className={`bg-transparent text-xs font-semibold outline-none focus:ring-2 focus:ring-indigo-500 ${textColor}`} aria-label="To date" />
              {(chat.fromDate || chat.toDate) && <button onClick={() => { chat.setFromDate(""); chat.setToDate(""); }} disabled={chat.streaming} className={`text-xs font-bold ${textMuted} hover:text-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500`} aria-label="Clear dates">{isBn ? "মুছুন" : "Clear"}</button>}
            </fieldset>
          </div>
          
          <section className="min-h-[560px] p-4 md:p-6" aria-live="polite" aria-label="Chat messages">
            {chat.messages.length === 0 ? (
              <div className="flex min-h-[480px] flex-col items-center justify-center text-center">
                <div className="mb-4 rounded-3xl bg-indigo-500/10 p-5 text-indigo-500" aria-hidden="true"><Sparkles size={34} /></div>
                <h2 className={`text-xl font-bold ${textColor}`}>{isBn ? "আজ কী জানতে চান?" : "What would you like to know?"}</h2>
                <p className={`mt-2 max-w-xl text-sm ${textMuted}`}>{isBn ? "একটি সাজেস্টেড প্রশ্ন বেছে নিন অথবা নিজের প্রশ্ন লিখুন।" : "Choose a suggested question or ask your own in plain language."}</p>
                <div className="mt-7 grid w-full max-w-3xl gap-3 sm:grid-cols-2" role="group" aria-label="Suggested prompts">
                  {prompts.map((prompt, index) => {
                    const Icon = iconFor[index];
                    return (
                      <button key={prompt} onClick={() => chat.send(prompt)} disabled={Boolean(chat.accessError)} className={`flex items-center gap-3 rounded-2xl border p-4 text-left text-sm font-semibold transition hover:border-indigo-500/50 focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:cursor-not-allowed disabled:opacity-40 ${cardBorder} ${textColor}`}>
                        <Icon className="shrink-0 text-indigo-500" size={19} aria-hidden="true" />{prompt}
                      </button>
                    );
                  })}
                </div>
              </div>
            ) : (
              <div className="space-y-5 pb-5">
                {chat.messages.map((message, index) => (
                  <article key={`${message.role}-${index}`} className={`flex gap-3 ${message.role === "user" ? "justify-end" : "justify-start"}`}>
                    {message.role === "assistant" && <div className="h-9 w-9 shrink-0 rounded-xl bg-indigo-500/10 p-2 text-indigo-500" aria-hidden="true"><Bot size={20} /></div>}
                    <div className={`max-w-3xl rounded-2xl px-4 py-3 text-sm leading-6 ${message.role === "user" ? "bg-indigo-600 text-white" : `${inputBg} ${textColor}`}`}>
                      <div className="whitespace-pre-wrap" dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(message.content) }} />
                      {message.insights?.length > 0 && <ul className="mt-3 list-disc space-y-1 pl-5" aria-label="Insights">{message.insights.map((item) => <li key={item} dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(item) }} />)}</ul>}
                      <InsightChart rows={message.chartData} chartType={message.chartType} isDark={isDark} />
                      <DataTable rows={message.chartData} isDark={isDark} />
                      {message.source && <div className={`mt-3 text-xs ${textMuted}`}>{isBn ? "উৎস" : "Source"}: {message.source.replaceAll("_", " ")}</div>}
                      {message.confidence && <div className={`mt-3 text-xs font-bold uppercase tracking-wide ${textMuted}`}>{isBn ? "বিশ্বাসযোগ্যতা" : "Confidence"}: {message.confidence}</div>}
                      {message.role === "assistant" && message.messageId && (
                        <div className="mt-3 flex items-center gap-1" role="group" aria-label="Message actions">
                          <button onClick={() => chat.rateMessage(index, message.messageId, "up")} aria-label="Helpful" aria-pressed={message.feedback === "up"} className={`rounded-lg p-1.5 transition hover:bg-emerald-500/10 focus:outline-none focus:ring-2 focus:ring-emerald-500 ${message.feedback === "up" ? "text-emerald-500" : textMuted}`}><ThumbsUp size={14} /></button>
                          <button onClick={() => chat.rateMessage(index, message.messageId, "down")} aria-label="Not helpful" aria-pressed={message.feedback === "down"} className={`rounded-lg p-1.5 transition hover:bg-red-500/10 focus:outline-none focus:ring-2 focus:ring-red-500 ${message.feedback === "down" ? "text-red-500" : textMuted}`}><ThumbsDown size={14} /></button>
                          <button onClick={() => chat.exportMessage(message.messageId)} disabled={chat.exportingMessageId === message.messageId} aria-label={isBn ? "CSV ডাউনলোড" : "Download CSV"} title={isBn ? "CSV ডাউনলোড" : "Download CSV"} className={`ml-1 rounded-lg p-1.5 transition hover:bg-indigo-500/10 focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:opacity-40 ${textMuted}`}><Download size={14} /></button>
                        </div>
                      )}
                    </div>
                  </article>
                ))}
                {chat.streaming && <div className={`flex items-center gap-3 text-sm ${textMuted}`} aria-live="polite"><Sparkles className="animate-pulse text-indigo-500" size={18} aria-hidden="true" />{chat.status}</div>}
              </div>
            )}
          </section>

          {chat.accessError && <div role="alert" className="mx-4 mb-3 rounded-xl border border-amber-500/20 bg-amber-500/10 px-4 py-3 text-sm text-amber-600 md:mx-6">{chat.accessError}</div>}
          {chat.error && <div role="alert" className="mx-4 mb-3 flex items-center justify-between gap-3 rounded-xl border border-red-500/20 bg-red-500/10 px-4 py-3 text-sm text-red-500 md:mx-6"><span>{chat.error}</span>{chat.lastQuestion && !chat.streaming && <button type="button" onClick={() => chat.send(chat.lastQuestion, { retry: true })} className="shrink-0 rounded-lg border border-red-500/30 px-3 py-1 font-bold hover:bg-red-500/10 focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-2 bg-red-500/20">{isBn ? "আবার চেষ্টা" : "Retry"}</button>}</div>}

          <div className={`border-t p-4 md:p-5 ${cardBorder}`}>
            <form onSubmit={(e) => { e.preventDefault(); if(!chat.streaming) chat.send(); }} className={`flex items-end gap-2 rounded-2xl border p-2 focus-within:border-indigo-500 focus-within:ring-1 focus-within:ring-indigo-500 ${inputBg} ${inputBorder}`}>
              <label htmlFor="ai-chat-input" className="sr-only">Your message</label>
              <textarea id="ai-chat-input" value={chat.input} onChange={(event) => chat.setInput(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); chat.send(); } }} rows={1} maxLength={2000} disabled={Boolean(chat.accessError)} placeholder={isBn ? "আপনার ব্যবসা সম্পর্কে প্রশ্ন করুন..." : "Ask about your business..."} className={`max-h-32 min-h-10 flex-1 resize-none bg-transparent px-3 py-2 text-sm outline-none disabled:cursor-not-allowed disabled:opacity-50 ${textColor}`} />
              <button type="button" onClick={chat.streaming ? chat.stop : () => chat.send()} disabled={!chat.streaming && (!chat.input.trim() || Boolean(chat.accessError))} className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-indigo-600 text-white transition hover:bg-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 focus:ring-offset-slate-950 disabled:cursor-not-allowed disabled:opacity-40" aria-label={chat.streaming ? "Stop" : "Send"}>
                {chat.streaming ? <Square size={16} /> : <Send size={17} />}
              </button>
            </form>
            <p className={`mt-2 flex items-center justify-center gap-1 text-center text-xs ${textMuted}`}><ChartNoAxesCombined size={13} aria-hidden="true" />{isBn ? "গুরুত্বপূর্ণ সিদ্ধান্তের আগে তথ্য যাচাই করুন।" : "Verify important numbers before making critical decisions."}</p>
          </div>
        </main>
      </div>
    </div>
  );
}
