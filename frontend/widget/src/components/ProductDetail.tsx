import { useRef } from "react";
import type { CardDetailData } from "../types";
import { ActionButton } from "./ActionButton";

interface Props {
  data: CardDetailData;
  onQuickReply: (message: string, value: string) => void;
}

export function ProductDetail({ data, onQuickReply }: Props) {
  const imgScrollRef = useRef<HTMLDivElement>(null);

  const scrollImages = (dir: "left" | "right") => {
    const el = imgScrollRef.current;
    if (!el) return;
    const amount = el.clientWidth * 0.45;
    el.scrollBy({ left: dir === "left" ? -amount : amount, behavior: "smooth" });
  };

  const hasMultipleImages = (data.images?.length || 0) > 2;

  return (
    <div className="ecw-detail">
      <div className="ecw-detail-images">
        <div className="ecw-detail-img-scroll" ref={imgScrollRef}>
          {data.images?.map((img, i) => (
            <div key={i} className="ecw-detail-img-wrap">
              {i === 0 && data.badge && (
                <span className="ecw-detail-badge">{data.type || data.badge}</span>
              )}
              <img className="ecw-detail-img" src={img} alt={`${data.title} ${i + 1}`} loading="lazy" />
            </div>
          ))}
        </div>

        {hasMultipleImages && (
          <button
            className="ecw-detail-img-nav ecw-detail-img-nav--right"
            onClick={() => scrollImages("right")}
            aria-label="Next image"
          >
            <svg viewBox="0 0 24 24"><path d="M8.59 16.59L10 18l6-6-6-6-1.41 1.41L13.17 12z" /></svg>
          </button>
        )}
      </div>

      <div className="ecw-detail-body">
        {data.subText && <div className="ecw-detail-location">{data.subText}</div>}
        <div className="ecw-detail-title">{data.title}</div>
        <div className="ecw-detail-desc">{data.description}</div>
        <div className="ecw-detail-price">{data.highlight}</div>
      </div>

      {data.actions && data.actions.length > 0 && (
        <div className="ecw-detail-actions">
          {data.actions.map((action, i) => (
            <ActionButton
              key={i}
              action={action}
              onQuickReply={onQuickReply}
              variant="detail"
            />
          ))}
        </div>
      )}

    </div>
  );
}
