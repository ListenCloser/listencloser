"use client";

import { createContext, useContext, useState, useCallback, type ReactNode } from "react";

export type TimelineState = {
  bpm: number;
  timeSignatureNumerator: number;
  timeSignatureDenominator: number;
  sampleRate: number;
};

type TimelineContextValue = {
  timeline: TimelineState;
  setBpm: (bpm: number) => void;
  setTimeSignature: (num: number, den: number) => void;
  secondsToBeats: (seconds: number) => number;
  beatsToSeconds: (beats: number) => number;
  secondsToMeasures: (seconds: number) => number;
  totalDuration: number;
  setTotalDuration: (d: number) => void;
};

const DEFAULT: TimelineState = {
  bpm: 120,
  timeSignatureNumerator: 4,
  timeSignatureDenominator: 4,
  sampleRate: 44100,
};

const TimelineContext = createContext<TimelineContextValue | null>(null);

export function useTimeline(): TimelineContextValue {
  const ctx = useContext(TimelineContext);
  if (!ctx) throw new Error("useTimeline must be used within TimelineProvider");
  return ctx;
}

export function TimelineProvider({ children }: { children: ReactNode }) {
  const [timeline, setTimeline] = useState<TimelineState>(DEFAULT);
  const [totalDuration, setTotalDuration] = useState(0);

  const setBpm = useCallback((bpm: number) => {
    setTimeline((prev) => ({ ...prev, bpm }));
  }, []);

  const setTimeSignature = useCallback((num: number, den: number) => {
    setTimeline((prev) => ({ ...prev, timeSignatureNumerator: num, timeSignatureDenominator: den }));
  }, []);

  const secondsToBeats = useCallback(
    (seconds: number) => (seconds / 60) * timeline.bpm,
    [timeline.bpm],
  );

  const beatsToSeconds = useCallback(
    (beats: number) => (beats / timeline.bpm) * 60,
    [timeline.bpm],
  );

  const secondsToMeasures = useCallback(
    (seconds: number) => {
      const beats = secondsToBeats(seconds);
      const beatsPerMeasure = timeline.timeSignatureNumerator;
      return beats / beatsPerMeasure;
    },
    [secondsToBeats, timeline.timeSignatureNumerator],
  );

  return (
    <TimelineContext.Provider
      value={{ timeline, setBpm, setTimeSignature, secondsToBeats, beatsToSeconds, secondsToMeasures, totalDuration, setTotalDuration }}
    >
      {children}
    </TimelineContext.Provider>
  );
}
