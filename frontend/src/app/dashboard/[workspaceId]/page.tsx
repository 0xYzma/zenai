"use client";

import { ChatInterface } from "@/components/chat/ChatInterface";
import { use } from "react";

export default function WorkspacePage({ params }: { params: Promise<{ workspaceId: string }> }) {
  const { workspaceId } = use(params);
  return <ChatInterface workspaceId={workspaceId} />;
}
