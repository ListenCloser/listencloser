"use client";

import { createContext, useContext, useState, useCallback, useRef, useEffect, type ReactNode } from "react";
import { useTimeline } from "./timeline";

export type PlaybackSource = {
  id: string;
  label: string;
  url: string;
  kind: "audio" | "midi" | "score";
};

type TransportState = {
  position: number;
  isPlaying: boolean;
  loopStart: number | null;
  loopEnd: number | null;
  loopEnabled: boolean;
  activeSource: PlaybackSource | null;
  sources: PlaybackSource[];
};

type TransportContextValue = {
  transport: TransportState;
  setActiveSource: (source: PlaybackSource) => void;
  replaceSources: (sources: PlaybackSource[], activeId?: string) => void;
  clearActiveSource: () => void;
  play: () => void;
  pause: () => void;
  stop: () => void;
  toggle: () => void;
  seek: (time: number) => void;
  setLoop: (start: number | null, end: number | null) => void;
  toggleLoop: () => void;
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
  const { setTotalDuration } = useTimeline();
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const positionRef = useRef(0);
  const [transport, setTransport] = useState<TransportState>({
    position: 0,
    isPlaying: false,
    loopStart: null,
    loopEnd: null,
    loopEnabled: false,
    activeSource: null,
    sources: [],
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
    const onMetadata = () => setTotalDuration(Number.isFinite(audio.duration) ? audio.duration : 0);

    audio.addEventListener("timeupdate", onTime);
    audio.addEventListener("ended", onEnd);
    audio.addEventListener("loadedmetadata", onMetadata);
    return () => {
      audio.removeEventListener("timeupdate", onTime);
      audio.removeEventListener("ended", onEnd);
      audio.removeEventListener("loadedmetadata", onMetadata);
    };
  }, [setTotalDuration, transport.loopEnabled, transport.loopEnd, transport.loopStart]);

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

  const replaceSources = useCallback((sources: PlaybackSource[], activeId?: string) => {
    const active = sources.find((item) => item.id === activeId) ?? sources[0] ?? null;
    const audio = audioRef.current;
    if (audio) {
      audio.pause();
      audio.src = active?.url ?? "";
      if (active) audio.load();
    }
    positionRef.current = 0;
    setTransport((prev) => ({
      ...prev,
      sources,
      activeSource: active,
      position: 0,
      isPlaying: false,
      loopStart: null,
      loopEnd: null,
      loopEnabled: false,
    }));
  }, []);

  const clearActiveSource = useCallback(() => {
    const audio = audioRef.current;
    if (audio) {
      audio.pause();
      audio.src = "";
    }
    positionRef.current = 0;
    setTransport((prev) => ({
      ...prev,
      activeSource: null,
      sources: [],
      position: 0,
      isPlaying: false,
      loopStart: null,
      loopEnd: null,
      loopEnabled: false,
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
        positionRef,
        audioRef,
      }}
    >
      <audio ref={audioRef} crossOrigin="anonymous" style={{ display: "none" }} />
      {children}
    </TransportContext.Provider>
  );
}
