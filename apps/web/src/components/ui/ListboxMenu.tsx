"use client";

import {
  Listbox,
  ListboxButton,
  ListboxOption,
  ListboxOptions,
} from "@headlessui/react";
import styles from "./ListboxMenu.module.css";

type MenuOption = { id: string; label: string; disabled?: boolean };

export default function ListboxMenu({
  triggerLabel,
  triggerAria,
  options,
  selectedId,
  onSelect,
  compact = false,
}: {
  triggerLabel: string;
  triggerAria: string;
  options: MenuOption[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  compact?: boolean;
}) {
  return (
    <Listbox
      value={selectedId}
      onChange={(nextId) => {
        if (nextId !== null) onSelect(nextId);
      }}
    >
      <div className={`${styles.root}${compact ? ` ${styles.compact}` : ""}`}>
        <ListboxButton className={styles.trigger} aria-label={triggerAria}>
          <span className={styles.triggerLabel}>{triggerLabel}</span>
          <svg
            className={styles.chevron}
            viewBox="0 0 12 12"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.3"
            aria-hidden="true"
          >
            <path d="m3 4.25 3 3 3-3" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </ListboxButton>
        <ListboxOptions
          className={styles.menu}
          aria-label={triggerAria}
          modal={false}
        >
          {options.map((option) => (
            <ListboxOption
              key={option.id}
              as="button"
              type="button"
              className={styles.option}
              value={option.id}
              disabled={option.disabled}
            >
              {option.label}
            </ListboxOption>
          ))}
        </ListboxOptions>
      </div>
    </Listbox>
  );
}
