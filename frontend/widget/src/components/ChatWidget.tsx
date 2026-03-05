import { useState, useRef, useEffect, useCallback } from "react";
import { useChat } from "../hooks/useChat";
import { MessageBubble } from "./MessageBubble";
import { ChatInput } from "./ChatInput";
import { ChatIcon, CloseIcon, BotIcon } from "./Icons";
import type { WidgetConfig } from "../types";
import "../styles/widget.css";

interface Props {
  config: WidgetConfig;
}

export function ChatWidget({ config }: Props) {
  const [isOpen, setIsOpen] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const { messages, isLoading, sendMessage } = useChat(config.apiUrl);

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading, scrollToBottom]);

  const handleQuickReply = useCallback(
    (displayMessage: string, value: string) => {
      sendMessage(value);
    },
    [sendMessage]
  );

  const isLeft = config.position === "bottom-left";

  return (
    <div className="ecom-chat-widget">
      {isOpen && (
        <div className={`ecw-panel ${isLeft ? "ecw-left" : ""}`}>
          <div className="ecw-header">
            <div className="ecw-header-avatar">
              <BotIcon />
            </div>
            <div className="ecw-header-info">
              <div className="ecw-header-title">
                {config.title || "AI Assistant"}
              </div>
              <div className="ecw-header-subtitle">
                {config.subtitle || "Online - Ask me anything"}
              </div>
            </div>
            <button
              className="ecw-header-close"
              onClick={() => setIsOpen(false)}
              aria-label="Close chat"
            >
              <CloseIcon />
            </button>
          </div>

          <div className="ecw-messages">
            {messages.length === 0 && (
              <div className="ecw-msg ecw-msg--assistant">
                <div className="ecw-msg-bubble">
                  Hello! I'm your AI assistant. I can help you browse
                  properties, find specific listings, get details, and answer
                  questions about our policies. How can I help you today?
                </div>
              </div>
            )}

            {messages.map((msg) => (
              <MessageBubble
                key={msg.id}
                message={msg}
                onQuickReply={handleQuickReply}
              />
            ))}

            {isLoading && (
              <div className="ecw-typing">
                <div className="ecw-typing-dot" />
                <div className="ecw-typing-dot" />
                <div className="ecw-typing-dot" />
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          <ChatInput onSend={sendMessage} disabled={isLoading} />

          <div className="ecw-powered">Powered by Ecom Chat AI</div>
        </div>
      )}

      <button
        className={`ecw-toggle-btn ${isLeft ? "ecw-left" : ""}`}
        onClick={() => setIsOpen(!isOpen)}
        aria-label={isOpen ? "Close chat" : "Open chat"}
      >
        {isOpen ? <CloseIcon /> : <ChatIcon />}
      </button>
    </div>
  );
}
