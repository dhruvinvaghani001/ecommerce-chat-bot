import type { ProductItem } from "../types";
import { ActionButton } from "./ActionButton";

interface Props {
  item: ProductItem;
  onQuickReply: (message: string, value: string) => void;
}

export function ProductCard({ item, onQuickReply }: Props) {
  const imgSrc = item.images?.[0] || "https://via.placeholder.com/160x160?text=No+Image";

  return (
    <div className="ecw-card">
      <div className="ecw-card-img-wrap">
        <img className="ecw-card-img" src={imgSrc} alt={item.title} loading="lazy" />
        {item.type && <span className="ecw-card-badge">{item.type}</span>}
      </div>
      <div className="ecw-card-body">
        <div className="ecw-card-title" title={item.title}>{item.title}</div>
        <div className="ecw-card-price">{item.highlight}</div>
      </div>
      <div className="ecw-card-actions">
        {item.actions.map((action, i) => (
          <ActionButton key={i} action={action} onQuickReply={onQuickReply} variant="card" />
        ))}
      </div>
    </div>
  );
}
