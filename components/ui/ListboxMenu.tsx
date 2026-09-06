"use client";

import {
  Listbox,
  ListboxButton,
  ListboxOption,
  ListboxOptions,
} from "@headlessui/react";
import { ChevronDownIcon } from "./Icons";
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
          <ChevronDownIcon className={styles.chevron} />
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
