"use client";

import { createContext, useContext, useState, useCallback, type ReactNode } from "react";

export type SelectionRange = {
  timeStart: number | null;
  timeEnd: number | null;
  beatStart: number | null;
  beatEnd: number | null;
  measureStart: number | null;
  measureEnd: number | null;
  noteIndices: number[];
};

const EMPTY: SelectionRange = {
  timeStart: null,
  timeEnd: null,
  beatStart: null,
  beatEnd: null,
  measureStart: null,
  measureEnd: null,
  noteIndices: [],
};

type SelectionState = {
  selection: SelectionRange;
  setTimeSelection: (start: number | null, end: number | null) => void;
  setBeatSelection: (start: number | null, end: number | null) => void;
  setMeasureSelection: (start: number | null, end: number | null) => void;
  clearSelection: () => void;
  hasSelection: () => boolean;
};

const SelectionContext = createContext<SelectionState | null>(null);

export function useSelection(): SelectionState {
  const ctx = useContext(SelectionContext);
  if (!ctx) throw new Error("useSelection must be used within SelectionProvider");
  return ctx;
}

export function SelectionProvider({ children }: { children: ReactNode }) {
  const [selection, setSelection] = useState<SelectionRange>(EMPTY);

  const setTimeSelection = useCallback((start: number | null, end: number | null) => {
    setSelection({ ...EMPTY, timeStart: start, timeEnd: end });
  }, []);

  const setBeatSelection = useCallback((start: number | null, end: number | null) => {
    setSelection({ ...EMPTY, beatStart: start, beatEnd: end });
  }, []);

  const setMeasureSelection = useCallback((start: number | null, end: number | null) => {
    setSelection({ ...EMPTY, measureStart: start, measureEnd: end });
  }, []);

  const clearSelection = useCallback(() => {
    setSelection(EMPTY);
  }, []);

  const hasSelection = useCallback(() => {
    return (
      selection.timeStart !== null ||
      selection.beatStart !== null ||
      selection.measureStart !== null
    );
  }, [selection]);

  return (
    <SelectionContext.Provider
      value={{ selection, setTimeSelection, setBeatSelection, setMeasureSelection, clearSelection, hasSelection }}
    >
      {children}
    </SelectionContext.Provider>
  );
}
