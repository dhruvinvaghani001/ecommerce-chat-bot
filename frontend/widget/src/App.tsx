import { ChatWidget } from "./components/ChatWidget";
import type { WidgetConfig } from "./types";

const config: WidgetConfig = {
  apiUrl: "http://localhost:8000/api/chat",
  title: "Property Assistant",
  subtitle: "Online - Ask me anything",
  position: "bottom-right",
};

export default function App() {
  return <ChatWidget config={config} />;
}
