"use client";

import { useEffect, useId, useRef, useState, type KeyboardEvent } from "react";

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
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement | null>(null);
  const triggerRef = useRef<HTMLButtonElement | null>(null);
  const optionRefs = useRef<Array<HTMLButtonElement | null>>([]);
  const menuId = useId();

  const focusOption = (index: number) => {
    if (options.length === 0) return;
    let next = index;
    for (let attempts = 0; attempts < options.length; attempts += 1) {
      if (next < 0) next = options.length - 1;
      if (next >= options.length) next = 0;
      if (!options[next]?.disabled) {
        optionRefs.current[next]?.focus();
        return;
      }
      next += 1;
    }
  };

  const openMenu = (preferred: "selected" | "first" | "last" = "selected") => {
    setOpen(true);
    requestAnimationFrame(() => {
      const selectedIndex = options.findIndex((option) => option.id === selectedId && !option.disabled);
      const index = preferred === "last"
        ? options.length - 1
        : preferred === "first"
          ? 0
          : Math.max(0, selectedIndex);
      focusOption(index);
    });
  };

  const closeMenu = (returnFocus = false) => {
    setOpen(false);
    if (returnFocus) requestAnimationFrame(() => triggerRef.current?.focus());
  };

  useEffect(() => {
    if (!open) return;
    const onDown = (event: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(event.target as Node)) closeMenu(false);
    };
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [open]);

  const onTriggerKeyDown = (event: KeyboardEvent<HTMLButtonElement>) => {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      openMenu("selected");
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      openMenu("last");
    } else if (event.key === "Escape" && open) {
      event.preventDefault();
      closeMenu(true);
    }
  };

  const onOptionKeyDown = (event: KeyboardEvent<HTMLButtonElement>, index: number) => {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      focusOption(index + 1);
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      focusOption(index - 1);
    } else if (event.key === "Home") {
      event.preventDefault();
      focusOption(0);
    } else if (event.key === "End") {
      event.preventDefault();
      focusOption(options.length - 1);
    } else if (event.key === "Escape") {
      event.preventDefault();
      closeMenu(true);
    } else if (event.key === "Tab") {
      closeMenu(false);
    }
  };

  return (
    <div className={`piece-source-select${compact ? " compact" : ""}`} ref={rootRef}>
      <button
        ref={triggerRef}
        type="button"
        className="piece-source-trigger"
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={open ? menuId : undefined}
        aria-label={triggerAria}
        onClick={() => (open ? closeMenu(false) : openMenu("selected"))}
        onKeyDown={onTriggerKeyDown}
      >
        <span>{triggerLabel}</span>
        <svg width="11" height="11" viewBox="0 0 11 11" fill="none" stroke="currentColor" strokeWidth="1.3" aria-hidden="true">
          <path d="m2.75 4 2.75 2.75L8.25 4" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </button>
      {open && (
        <div id={menuId} className="piece-source-menu" role="listbox" aria-label={triggerAria}>
          {options.map((option, index) => (
            <button
              key={option.id}
              ref={(node) => {
                optionRefs.current[index] = node;
              }}
              type="button"
              role="option"
              aria-selected={selectedId === option.id}
              disabled={option.disabled}
              onKeyDown={(event) => onOptionKeyDown(event, index)}
              onClick={() => {
                onSelect(option.id);
                closeMenu(true);
              }}
            >
              {option.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
