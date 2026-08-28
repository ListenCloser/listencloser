"use client";

import { useRef, type KeyboardEvent } from "react";

type TabItem<T extends string> = {
  id: T;
  label: string;
  disabled?: boolean;
};

export default function TabStrip<T extends string>({
  label,
  items,
  value,
  onChange,
  className = "",
}: {
  label: string;
  items: TabItem<T>[];
  value: T | null;
  onChange: (value: T) => void;
  className?: string;
}) {
  const refs = useRef<Array<HTMLButtonElement | null>>([]);

  const moveTo = (index: number, direction: 1 | -1) => {
    if (items.length === 0) return;
    let next = index;
    for (let attempts = 0; attempts < items.length; attempts += 1) {
      if (next < 0) next = items.length - 1;
      if (next >= items.length) next = 0;
      const item = items[next];
      if (!item.disabled) {
        // Tabs are all mounted, so move focus immediately. Deferring this with
        // requestAnimationFrame makes keyboard navigation lag behind selection
        // and can leave assistive-technology focus on the previous tab.
        refs.current[next]?.focus();
        onChange(item.id);
        return;
      }
      next += direction;
    }
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLButtonElement>, index: number) => {
    switch (event.key) {
      case "ArrowRight":
        event.preventDefault();
        moveTo(index + 1, 1);
        break;
      case "ArrowLeft":
        event.preventDefault();
        moveTo(index - 1, -1);
        break;
      case "Home":
        event.preventDefault();
        moveTo(0, 1);
        break;
      case "End":
        event.preventDefault();
        moveTo(items.length - 1, -1);
        break;
      default:
        break;
    }
  };

  return (
    <div className={`ui-tab-strip ${className}`.trim()} role="tablist" aria-label={label}>
      {items.map((item, index) => {
        const selected = item.id === value;
        return (
          <button
            key={item.id}
            ref={(node) => {
              refs.current[index] = node;
            }}
            type="button"
            role="tab"
            aria-selected={selected}
            aria-disabled={item.disabled || undefined}
            tabIndex={selected ? 0 : -1}
            disabled={item.disabled}
            data-state={selected ? "active" : "inactive"}
            className={`ui-tab${selected ? " active" : ""}`}
            onClick={() => onChange(item.id)}
            onKeyDown={(event) => handleKeyDown(event, index)}
          >
            {item.label}
          </button>
        );
      })}
    </div>
  );
}
