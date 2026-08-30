"use client";

import {
  Listbox,
  ListboxButton,
  ListboxOption,
  ListboxOptions,
} from "@headlessui/react";

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
      <div className={`piece-source-select${compact ? " compact" : ""}`}>
        <ListboxButton className="piece-source-trigger" aria-label={triggerAria}>
          <span>{triggerLabel}</span>
          <svg width="11" height="11" viewBox="0 0 11 11" fill="none" stroke="currentColor" strokeWidth="1.3" aria-hidden="true">
            <path d="m2.75 4 2.75 2.75L8.25 4" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </ListboxButton>
        <ListboxOptions
          className="piece-source-menu"
          aria-label={triggerAria}
          modal={false}
        >
          {options.map((option) => (
            <ListboxOption
              key={option.id}
              as="button"
              type="button"
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
