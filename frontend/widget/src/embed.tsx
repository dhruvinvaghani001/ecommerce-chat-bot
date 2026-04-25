import React from "react";
import ReactDOM from "react-dom/client";
import { ChatWidget } from "./components/ChatWidget";
import type { WidgetConfig } from "./types";

interface EcomChatInit {
  containerId?: string;
  apiUrl?: string;
  title?: string;
  subtitle?: string;
  position?: "bottom-right" | "bottom-left";
}

function initEcomChat(options: EcomChatInit = {}) {
  const config: WidgetConfig = {
    apiUrl: options.apiUrl || "http://localhost:8000/api/chat",
    title: options.title || "Store Assistant",
    subtitle: options.subtitle || "Online - Ask about products and prices",
    position: options.position || "bottom-right",
  };

  let container: HTMLElement;
  if (options.containerId) {
    container = document.getElementById(options.containerId)!;
  } else {
    container = document.createElement("div");
    container.id = "ecom-chat-widget-root";
    document.body.appendChild(container);
  }

  const root = ReactDOM.createRoot(container);
  root.render(
    <React.StrictMode>
      <ChatWidget config={config} />
    </React.StrictMode>
  );

  return {
    destroy: () => root.unmount(),
  };
}

(window as any).EcomChat = { init: initEcomChat };
