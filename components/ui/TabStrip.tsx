"use client";

import { Tabs } from "@base-ui/react/tabs";

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
  return (
    <Tabs.Root
      value={value}
      onValueChange={(nextValue) => {
        if (typeof nextValue === "string") onChange(nextValue as T);
      }}
      style={{ display: "contents" }}
    >
      <Tabs.List
        className={`ui-tab-strip ${className}`.trim()}
        aria-label={label}
        activateOnFocus
        loopFocus
      >
        {items.map((item) => {
          const selected = item.id === value;
          return (
            <Tabs.Tab
              key={item.id}
              value={item.id}
              disabled={item.disabled}
              data-state={selected ? "active" : "inactive"}
              className={`ui-tab${selected ? " active" : ""}`}
              render={(tabProps) => (
                <button {...tabProps} disabled={item.disabled}>
                  {item.label}
                </button>
              )}
            />
          );
        })}
      </Tabs.List>
    </Tabs.Root>
  );
}
