"use client";

import * as Tabs from "@radix-ui/react-tabs";

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
      value={value ?? ""}
      onValueChange={(nextValue) => onChange(nextValue as T)}
      activationMode="automatic"
      style={{ display: "contents" }}
    >
      <Tabs.List
        className={`ui-tab-strip ${className}`.trim()}
        aria-label={label}
        loop
      >
        {items.map((item) => {
          const selected = item.id === value;
          return (
            <Tabs.Trigger
              key={item.id}
              value={item.id}
              disabled={item.disabled}
              aria-controls={undefined}
              className={`ui-tab${selected ? " active" : ""}`}
            >
              {item.label}
            </Tabs.Trigger>
          );
        })}
      </Tabs.List>
    </Tabs.Root>
  );
}
