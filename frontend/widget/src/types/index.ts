export interface ActionInstruction {
  type: "quick_reply" | "navigate";
  options: {
    message?: string;
    value: string;
  };
}

export interface ProductAction {
  text: string;
  icon: string;
  instructions: ActionInstruction[];
}

export interface ProductItem {
  itemId: string;
  slug: string;
  title: string;
  description: string;
  badge: string;
  highlight: string;
  images: string[];
  url: string;
  type?: string;
  actions: ProductAction[];
}

export interface Pagination {
  pageNo: number;
  pageSize: number;
  totalPages: number;
  totalItems: number;
}

export interface CardListData {
  items: ProductItem[];
  pagination: Pagination;
}

export interface CardDetailData {
  itemId: string;
  slug: string;
  badge: string;
  header: string;
  title: string;
  description: string;
  highlight: string;
  subText: string;
  footer: string;
  type?: string;
  images: string[];
  actions: ProductAction[];
}

export interface ComponentData {
  type: "card-list" | "card-detail";
  data: CardListData | CardDetailData;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  components: ComponentData[];
  timestamp: Date;
}

export interface ChatResponse {
  type: "assistant_message" | "error";
  content: string;
  components?: ComponentData[];
  thread_id: string;
}

export interface WidgetConfig {
  apiUrl: string;
  title?: string;
  subtitle?: string;
  primaryColor?: string;
  position?: "bottom-right" | "bottom-left";
}
