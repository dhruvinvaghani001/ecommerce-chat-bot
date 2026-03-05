import { useState, useCallback } from "react";
import type { ChatMessage, ChatResponse, ComponentData } from "../types";

function generateId(): string {
  return Date.now().toString(36) + Math.random().toString(36).slice(2);
}

export function useChat(apiUrl: string) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [threadId, setThreadId] = useState<string>("");

  const sendMessage = useCallback(
    async (content: string) => {
      const userMsg: ChatMessage = {
        id: generateId(),
        role: "user",
        content,
        components: [],
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, userMsg]);
      setIsLoading(true);

      try {
        const res = await fetch(apiUrl, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            content,
            thread_id: threadId || undefined,
          }),
        });

        const data: ChatResponse = await res.json();

        if (data.thread_id) {
          setThreadId(data.thread_id);
        }

        const assistantMsg: ChatMessage = {
          id: generateId(),
          role: "assistant",
          content: data.content || "",
          components: (data.components || []) as ComponentData[],
          timestamp: new Date(),
        };

        setMessages((prev) => [...prev, assistantMsg]);
      } catch (e) {
        console.error("[EcomChat] Request failed:", e);
        setMessages((prev) => [
          ...prev,
          {
            id: generateId(),
            role: "assistant",
            content: "Sorry, something went wrong. Please try again.",
            components: [],
            timestamp: new Date(),
          },
        ]);
      } finally {
        setIsLoading(false);
      }
    },
    [apiUrl, threadId]
  );

  return { messages, isLoading, sendMessage, threadId };
}
