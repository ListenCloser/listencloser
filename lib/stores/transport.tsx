"use client";

import { createContext, useContext, useState, useCallback, useRef, useEffect, type ReactNode } from "react";

export type PlaybackSource = {
  id: string;
  label: string;
  url: string;
  kind: "audio" | "midi" | "score";
  role: "original" | "transcription" | "derived" | "score";
};

export type CompareSide = "A" | "B";

type TransportState = {
  position: number;
  isPlaying: boolean;
  duration: number;
  loopStart: number | null;
  loopEnd: number | null;
  loopEnabled: boolean;
  activeSource: PlaybackSource | null;
  sources: PlaybackSource[];
  compareEnabled: boolean;
  compareA: PlaybackSource | null;
  compareB: PlaybackSource | null;
  activeSide: CompareSide;
};

type TransportContextValue = {
  transport: TransportState;
  setActiveSource: (source: PlaybackSource) => void;
  replaceSources: (sources: PlaybackSource[], activeId?: string, preservePosition?: boolean) => void;
  clearActiveSource: () => void;
  play: () => void;
  pause: () => void;
  stop: () => void;
  toggle: () => void;
  seek: (time: number) => void;
  setLoop: (start: number | null, end: number | null) => void;
  toggleLoop: () => void;
  startCompare: (a: PlaybackSource, b: PlaybackSource) => void;
  setCompareSide: (side: CompareSide) => void;
  setCompareSource: (side: CompareSide, source: PlaybackSource) => void;
  exitCompare: () => void;
  positionRef: React.RefObject<number>;
  audioRef: React.RefObject<HTMLAudioElement | null>;
};

const TransportContext = createContext<TransportContextValue | null>(null);

export function useTransport(): TransportContextValue {
  const ctx = useContext(TransportContext);
  if (!ctx) throw new Error("useTransport must be used within TransportProvider");
  return ctx;
}

export function TransportProvider({ children }: { children: ReactNode }) {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const positionRef = useRef(0);
  const activeSourceIdRef = useRef<string | null>(null);
  const sourcesRef = useRef<PlaybackSource[]>([]);
  const compareRef = useRef<{ aId: string | null; bId: string | null; side: CompareSide }>({ aId: null, bId: null, side: "A" });
  const [transport, setTransport] = useState<TransportState>({
    position: 0,
    isPlaying: false,
    duration: 0,
    loopStart: null,
    loopEnd: null,
    loopEnabled: false,
    activeSource: null,
    sources: [],
    compareEnabled: false,
    compareA: null,
    compareB: null,
    activeSide: "A",
  });

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;

    const onTime = () => {
      const t = audio.currentTime;
      positionRef.current = t;
      setTransport((prev) => {
        if (prev.loopEnabled && prev.loopEnd !== null && t >= prev.loopEnd) {
          audio.currentTime = prev.loopStart ?? 0;
          return { ...prev, position: prev.loopStart ?? 0 };
        }
        return { ...prev, position: t };
      });
    };

    const onEnd = () => {
      setTransport((prev) => ({ ...prev, isPlaying: false }));
    };
    const onMetadata = () => {
      const duration = Number.isFinite(audio.duration) ? audio.duration : 0;
      setTransport((prev) => ({ ...prev, duration }));
    };

    audio.addEventListener("timeupdate", onTime);
    audio.addEventListener("ended", onEnd);
    audio.addEventListener("loadedmetadata", onMetadata);
    return () => {
      audio.removeEventListener("timeupdate", onTime);
      audio.removeEventListener("ended", onEnd);
      audio.removeEventListener("loadedmetadata", onMetadata);
    };
  }, [transport.loopEnabled, transport.loopEnd, transport.loopStart]);

  const setActiveSource = useCallback((source: PlaybackSource) => {
    if (!audioRef.current) return;
    const audio = audioRef.current;
    const currentPosition = audio.currentTime;
    const shouldResume = !audio.paused && !audio.ended;
    audio.pause();
    audio.src = source.url;
    audio.load();
    audio.addEventListener("loadedmetadata", () => {
      audio.currentTime = Math.min(currentPosition, audio.duration || currentPosition);
      if (shouldResume) {
        void audio.play()
          .then(() => setTransport((prev) => ({ ...prev, isPlaying: true })))
          .catch(() => setTransport((prev) => ({ ...prev, isPlaying: false })));
      }
    }, { once: true });
    activeSourceIdRef.current = source.id;
    setTransport((prev) => ({
      ...prev,
      activeSource: source,
      sources: prev.sources.some((item) => item.id === source.id)
        ? prev.sources
        : [...prev.sources, source],
      position: Math.min(currentPosition, audio.duration || currentPosition),
      isPlaying: shouldResume,
    }));
  }, []);

  const replaceSources = useCallback((sources: PlaybackSource[], activeId?: string, preservePosition = false) => {
    sourcesRef.current = sources;
    const fallbackActive = sources.find((item) => item.id === activeId) ?? sources[0] ?? null;
    const active = preservePosition
      ? (sources.find((item) => item.id === activeSourceIdRef.current) ?? fallbackActive)
      : fallbackActive;
    const audio = audioRef.current;
    const previousPosition = positionRef.current;
    const wasPlaying = audio ? !audio.paused && !audio.ended : false;
    if (audio) {
      audio.pause();
      audio.src = active?.url ?? "";
      if (active) audio.load();
    }
    const compareStillValid =
      compareRef.current.aId !== null &&
      compareRef.current.bId !== null &&
      sources.some((item) => item.id === compareRef.current.aId) &&
      sources.some((item) => item.id === compareRef.current.bId);
    const keepCompare = preservePosition && compareStillValid;
    if (!keepCompare) {
      compareRef.current = { aId: null, bId: null, side: "A" };
    }
    if (preservePosition && audio && active) {
      audio.addEventListener("loadedmetadata", () => {
        audio.currentTime = Math.min(previousPosition, audio.duration || previousPosition);
        if (wasPlaying) {
          void audio.play()
            .then(() => setTransport((prev) => ({ ...prev, isPlaying: true })))
            .catch(() => setTransport((prev) => ({ ...prev, isPlaying: false })));
        }
      }, { once: true });
    }
    activeSourceIdRef.current = active?.id ?? null;
    positionRef.current = preservePosition ? previousPosition : 0;
    setTransport((prev) => ({
      ...prev,
      sources,
      activeSource: active,
      position: preservePosition ? previousPosition : 0,
      isPlaying: preservePosition ? wasPlaying : false,
      compareEnabled: keepCompare ? prev.compareEnabled : false,
      ...(keepCompare
        ? {}
        : { compareA: null, compareB: null }),
      ...(preservePosition
        ? {}
        : { duration: 0, loopStart: null, loopEnd: null, loopEnabled: false }),
    }));
  }, []);

  const clearActiveSource = useCallback(() => {
    const audio = audioRef.current;
    if (audio) {
      audio.pause();
      audio.src = "";
    }
    sourcesRef.current = [];
    positionRef.current = 0;
    activeSourceIdRef.current = null;
    compareRef.current = { aId: null, bId: null, side: "A" };
    setTransport((prev) => ({
      ...prev,
      activeSource: null,
      sources: [],
      position: 0,
      isPlaying: false,
      duration: 0,
      loopStart: null,
      loopEnd: null,
      loopEnabled: false,
      compareEnabled: false,
      compareA: null,
      compareB: null,
      activeSide: "A",
    }));
  }, []);

  const play = useCallback(() => {
    const audio = audioRef.current;
    if (!audio || !audio.src) return;
    void audio.play()
      .then(() => setTransport((prev) => ({ ...prev, isPlaying: true })))
      .catch(() => setTransport((prev) => ({ ...prev, isPlaying: false })));
  }, []);

  const pause = useCallback(() => {
    audioRef.current?.pause();
    setTransport((prev) => ({ ...prev, isPlaying: false }));
  }, []);

  const stop = useCallback(() => {
    const audio = audioRef.current;
    if (audio) {
      audio.pause();
      audio.currentTime = 0;
    }
    positionRef.current = 0;
    setTransport((prev) => ({ ...prev, isPlaying: false, position: 0 }));
  }, []);

  const toggle = useCallback(() => {
    if (transport.isPlaying) pause();
    else play();
  }, [transport.isPlaying, play, pause]);

  const seek = useCallback((time: number) => {
    const audio = audioRef.current;
    if (audio) {
      audio.currentTime = time;
      positionRef.current = time;
    }
    setTransport((prev) => ({ ...prev, position: time }));
  }, []);

  const setLoop = useCallback((start: number | null, end: number | null) => {
    setTransport((prev) => ({ ...prev, loopStart: start, loopEnd: end }));
  }, []);

  const toggleLoop = useCallback(() => {
    setTransport((prev) => ({ ...prev, loopEnabled: !prev.loopEnabled }));
  }, []);

  const startCompare = useCallback((a: PlaybackSource, b: PlaybackSource) => {
    if (a.id === b.id) return;
    compareRef.current = { aId: a.id, bId: b.id, side: "A" };
    setTransport((prev) => ({
      ...prev,
      compareEnabled: true,
      compareA: a,
      compareB: b,
      activeSide: "A",
      activeSource: prev.activeSource ?? a,
    }));
  }, []);

  const setCompareSide = useCallback((side: CompareSide) => {
    const compare = compareRef.current;
    if (!compare.aId || !compare.bId) return;
    const targetId = side === "A" ? compare.aId : compare.bId;
    const target = sourcesRef.current.find((item) => item.id === targetId);
    if (!target) return;
    compareRef.current = { ...compare, side };
    if (targetId !== activeSourceIdRef.current) {
      setActiveSource(target);
    }
    setTransport((prev) => ({
      ...prev,
      activeSide: side,
      activeSource: target,
    }));
  }, [setActiveSource]);

  const setCompareSource = useCallback((side: CompareSide, source: PlaybackSource) => {
    const compare = compareRef.current;
    if (!compare.aId || !compare.bId) return;
    const next = side === "A"
      ? { ...compare, aId: source.id }
      : { ...compare, bId: source.id };
    compareRef.current = next;
    const sideBecameActiveTarget = side === next.side && source.id === (next.side === "A" ? next.aId : next.bId);
    if (sideBecameActiveTarget && source.id !== activeSourceIdRef.current) {
      setActiveSource(source);
    }
    setTransport((prev) => ({
      ...prev,
      compareA: side === "A" ? source : prev.compareA,
      compareB: side === "B" ? source : prev.compareB,
      ...(sideBecameActiveTarget ? { activeSource: source } : {}),
    }));
  }, [setActiveSource]);

  const exitCompare = useCallback(() => {
    compareRef.current = { aId: null, bId: null, side: "A" };
    setTransport((prev) => ({
      ...prev,
      compareEnabled: false,
      compareA: null,
      compareB: null,
      activeSide: "A",
    }));
  }, []);

  return (
    <TransportContext.Provider
      value={{
        transport,
        setActiveSource,
        replaceSources,
        clearActiveSource,
        play,
        pause,
        stop,
        toggle,
        seek,
        setLoop,
        toggleLoop,
        startCompare,
        setCompareSide,
        setCompareSource,
        exitCompare,
        positionRef,
        audioRef,
      }}
    >
      <audio ref={audioRef} crossOrigin="anonymous" style={{ display: "none" }} />
      {children}
    </TransportContext.Provider>
  );
}
