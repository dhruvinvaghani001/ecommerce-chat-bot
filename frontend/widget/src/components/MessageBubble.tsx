import type { ChatMessage, CardListData, CardDetailData } from "../types";
import { ProductCardList } from "./ProductCardList";
import { ProductDetail } from "./ProductDetail";

interface Props {
  message: ChatMessage;
  onQuickReply: (message: string, value: string) => void;
}

function formatTime(date: Date): string {
  return date.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
}

function renderMarkdown(text: string): string {
  let html = text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");

  html = html.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  html = html.replace(/\*(.+?)\*/g, "<em>$1</em>");
  html = html.replace(
    /\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g,
    '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>'
  );
  html = html.replace(/\n/g, "<br/>");

  return html;
}

export function MessageBubble({ message, onQuickReply }: Props) {
  return (
    <div className={`ecw-msg ecw-msg--${message.role}`}>
      {message.content && (
        <div
          className="ecw-msg-bubble"
          dangerouslySetInnerHTML={{ __html: renderMarkdown(message.content) }}
        />
      )}

      {message.components?.map((comp, idx) => {
        if (comp.type === "card-list") {
          return (
            <ProductCardList
              key={idx}
              data={comp.data as CardListData}
              onQuickReply={onQuickReply}
            />
          );
        }
        if (comp.type === "card-detail") {
          return (
            <ProductDetail
              key={idx}
              data={comp.data as CardDetailData}
              onQuickReply={onQuickReply}
            />
          );
        }
        return null;
      })}

      <span className="ecw-msg-time">{formatTime(message.timestamp)}</span>
    </div>
  );
}
