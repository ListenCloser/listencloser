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
    const currentPosition = positionRef.current;
    const shouldResume = !audio.paused && !audio.ended;

    const restorePosition = () => {
      const duration = Number.isFinite(audio.duration) ? audio.duration : 0;
      const restoredPosition = Math.min(currentPosition, duration || currentPosition);
      audio.currentTime = restoredPosition;
      positionRef.current = restoredPosition;
      setTransport((prev) => ({ ...prev, position: restoredPosition, duration }));
      if (shouldResume) {
        void audio.play()
          .then(() => setTransport((prev) => ({ ...prev, isPlaying: true })))
          .catch(() => setTransport((prev) => ({ ...prev, isPlaying: false })));
      }
    };

    // Install the restore listener before assigning/loading the new source.
    // Cached/data media can emit loadedmetadata during load(), and registering
    // afterward loses the exact position we promised to preserve.
    audio.addEventListener("loadedmetadata", restorePosition, { once: true });
    audio.pause();
    activeSourceIdRef.current = source.id;
    positionRef.current = currentPosition;
    setTransport((prev) => ({
      ...prev,
      activeSource: source,
      sources: prev.sources.some((item) => item.id === source.id)
        ? prev.sources
        : [...prev.sources, source],
      position: currentPosition,
      isPlaying: shouldResume,
    }));
    audio.src = source.url;
    audio.load();
  }, []);

  const replaceSources = useCallback((sources: PlaybackSource[], activeId?: string, preservePosition = false) => {
    const previousSources = sourcesRef.current;
    // Same-Work bundle refreshes may mint a fresh signed URL for the same
    // immutable Version. Keep the already-loaded URL while that Version ID is
    // unchanged so background processing polls do not look like source changes.
    const stableSources = preservePosition
      ? sources.map((source) => {
          const previous = previousSources.find((item) => item.id === source.id);
          return previous ? { ...source, url: previous.url } : source;
        })
      : sources;
    sourcesRef.current = stableSources;

    const fallbackActive = stableSources.find((item) => item.id === activeId) ?? stableSources[0] ?? null;
    const active = preservePosition
      ? (stableSources.find((item) => item.id === activeSourceIdRef.current) ?? fallbackActive)
      : fallbackActive;
    const previousActiveId = activeSourceIdRef.current;
    const sameActiveVersion = preservePosition && previousActiveId !== null && active?.id === previousActiveId;
    const audio = audioRef.current;
    const previousPosition = positionRef.current;
    const wasPlaying = audio ? !audio.paused && !audio.ended : false;

    // Polling the same Work must be a state reconciliation, not a media reload.
    // Only touch the audio element when the immutable active Version actually
    // changes (or when opening a different Work with preservePosition=false).
    if (audio && !sameActiveVersion) {
      audio.pause();
      audio.src = active?.url ?? "";
      if (active) audio.load();
    }
    const compareStillValid =
      compareRef.current.aId !== null &&
      compareRef.current.bId !== null &&
      stableSources.some((item) => item.id === compareRef.current.aId) &&
      stableSources.some((item) => item.id === compareRef.current.bId);
    const keepCompare = preservePosition && compareStillValid;
    if (!keepCompare) {
      compareRef.current = { aId: null, bId: null, side: "A" };
    }
    if (preservePosition && audio && active && !sameActiveVersion) {
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
      sources: stableSources,
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
