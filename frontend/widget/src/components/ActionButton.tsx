import type { ProductAction } from "../types";
import { getActionIcon } from "./Icons";

interface Props {
  action: ProductAction;
  onQuickReply: (message: string, value: string) => void;
  variant?: "card" | "detail";
}

export function ActionButton({ action, onQuickReply, variant = "card" }: Props) {
  const handleClick = () => {
    for (const instruction of action.instructions) {
      if (instruction.type === "quick_reply") {
        onQuickReply(
          instruction.options.message || instruction.options.value,
          instruction.options.value
        );
      } else if (instruction.type === "navigate") {
        window.open(instruction.options.value, "_blank", "noopener");
      }
    }
  };

  const className =
    variant === "detail" ? "ecw-detail-action-btn" : "ecw-action-btn";

  return (
    <button className={className} onClick={handleClick}>
      {getActionIcon(action.icon)}
      <span>{action.text}</span>
    </button>
  );
}
