import { ChatWidget } from "./components/ChatWidget";
import type { WidgetConfig } from "./types";

const config: WidgetConfig = {
  apiUrl: "/api/chat",
  title: "Store Assistant",
  subtitle: "Online - Ask about products and prices",
  position: "bottom-right",
};

export default function App() {
  return <ChatWidget config={config} />;
}
