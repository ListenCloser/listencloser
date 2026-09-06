"use client";

import * as Tabs from "@radix-ui/react-tabs";
import styles from "./TabStrip.module.css";

export type TabIntentSource = "pointer" | "focus";

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
  onIntentStart,
  onIntentEnd,
  className = "",
}: {
  label: string;
  items: TabItem<T>[];
  value: T | null;
  onChange: (value: T) => void;
  onIntentStart?: (value: T, source: TabIntentSource) => void;
  onIntentEnd?: (value: T, source: TabIntentSource) => void;
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
        className={`${styles.strip} ${className}`.trim()}
        aria-label={label}
        loop
      >
        {items.map((item) => (
          <Tabs.Trigger
            key={item.id}
            value={item.id}
            disabled={item.disabled}
            aria-controls={undefined}
            className={styles.tab}
            onPointerEnter={() => onIntentStart?.(item.id, "pointer")}
            onPointerLeave={() => onIntentEnd?.(item.id, "pointer")}
            onFocus={() => onIntentStart?.(item.id, "focus")}
            onBlur={() => onIntentEnd?.(item.id, "focus")}
          >
            {item.label}
          </Tabs.Trigger>
        ))}
      </Tabs.List>
    </Tabs.Root>
  );
}
