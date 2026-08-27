import { Plus, History } from "lucide-react";

export function AIHistoryPanel({ 
  isBn, 
  streaming, 
  startNewConversation, 
  conversations, 
  conversationId, 
  openConversation, 
  loadingConversation, 
  cardBorder, 
  textColor, 
  textMuted 
}) {
  return (
    <div className={`flex items-center gap-2 overflow-x-auto border-b p-3 ${cardBorder}`} role="region" aria-label="Conversation History">
      <button 
        onClick={startNewConversation} 
        disabled={streaming} 
        aria-label={isBn ? "নতুন চ্যাট শুরু করুন" : "Start new chat"}
        className="flex shrink-0 items-center gap-2 rounded-xl bg-indigo-600 px-3 py-2 text-xs font-bold text-white disabled:opacity-50 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2"
      >
        <Plus size={15} aria-hidden="true" />{isBn ? "নতুন চ্যাট" : "New chat"}
      </button>
      <History size={16} className={`ml-1 shrink-0 ${textMuted}`} aria-hidden="true" />
      <div role="listbox" aria-label="Previous conversations" className="flex items-center gap-2">
        {conversations.map((conversation) => (
          <button 
            key={conversation.id} 
            role="option"
            aria-selected={conversationId === conversation.id}
            onClick={() => openConversation(conversation.id)} 
            disabled={streaming || loadingConversation} 
            title={conversation.preview || conversation.title} 
            className={`max-w-52 shrink-0 truncate rounded-xl border px-3 py-2 text-left text-xs font-semibold transition focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 ${conversationId === conversation.id ? "border-indigo-500 bg-indigo-500/10 text-indigo-500" : `${cardBorder} ${textColor} hover:bg-slate-500/10`}`}
          >
            {conversation.title}
          </button>
        ))}
      </div>
      {conversations.length === 0 && <span className={`text-xs ${textMuted}`}>{isBn ? "কোনো পুরোনো চ্যাট নেই" : "No previous conversations"}</span>}
    </div>
  );
}
