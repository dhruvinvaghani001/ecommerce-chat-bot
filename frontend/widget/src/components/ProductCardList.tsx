import { useRef, useState, useEffect, useCallback } from "react";
import type { CardListData } from "../types";
import { ProductCard } from "./ProductCard";

interface Props {
  data: CardListData;
  onQuickReply: (message: string, value: string) => void;
}

export function ProductCardList({ data, onQuickReply }: Props) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [canScrollLeft, setCanScrollLeft] = useState(false);
  const [canScrollRight, setCanScrollRight] = useState(false);

  const checkScroll = useCallback(() => {
    const el = scrollRef.current;
    if (!el) return;
    setCanScrollLeft(el.scrollLeft > 4);
    setCanScrollRight(el.scrollLeft + el.clientWidth < el.scrollWidth - 4);
  }, []);

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    checkScroll();
    el.addEventListener("scroll", checkScroll, { passive: true });
    return () => el.removeEventListener("scroll", checkScroll);
  }, [checkScroll]);

  const scroll = (dir: "left" | "right") => {
    const el = scrollRef.current;
    if (!el) return;
    el.scrollBy({ left: dir === "left" ? -164 : 164, behavior: "smooth" });
  };

  if (!data.items || data.items.length === 0) return null;

  const { pageNo, totalPages, totalItems } = data.pagination;
  const paginationCommands = data.paginationCommands || {};

  return (
    <div className="ecw-card-list">
      <div className="ecw-card-scroll-area">
        {canScrollLeft && (
          <button
            className="ecw-scroll-btn ecw-scroll-btn--left"
            onClick={() => scroll("left")}
            aria-label="Scroll left"
          >
            <svg viewBox="0 0 24 24"><path d="M15.41 7.41L14 6l-6 6 6 6 1.41-1.41L10.83 12z" /></svg>
          </button>
        )}

        <div className="ecw-card-carousel" ref={scrollRef}>
          {data.items.map((item) => (
            <ProductCard key={item.itemId} item={item} onQuickReply={onQuickReply} />
          ))}
        </div>

        {canScrollRight && (
          <button
            className="ecw-scroll-btn ecw-scroll-btn--right"
            onClick={() => scroll("right")}
            aria-label="Scroll right"
          >
            <svg viewBox="0 0 24 24"><path d="M8.59 16.59L10 18l6-6-6-6-1.41 1.41L13.17 12z" /></svg>
          </button>
        )}
      </div>

      {totalPages > 1 && (
        <div className="ecw-pagination">
          <button
            className="ecw-pagination-btn"
            onClick={() =>
              paginationCommands.previous &&
              onQuickReply("Previous page", paginationCommands.previous)
            }
            disabled={!paginationCommands.previous}
          >
            Previous
          </button>

          <div className="ecw-pagination-meta">
            Page {pageNo} of {totalPages}
            <span className="ecw-pagination-total">{totalItems} products</span>
          </div>

          <button
            className="ecw-pagination-btn"
            onClick={() =>
              paginationCommands.next &&
              onQuickReply("Next page", paginationCommands.next)
            }
            disabled={!paginationCommands.next}
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}
