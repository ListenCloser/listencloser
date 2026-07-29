"use client";

import { createContext, useContext, useState, useCallback, useRef, useEffect, type ReactNode } from "react";

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
};

type TransportContextValue = {
  transport: TransportState;
  setActiveSource: (source: PlaybackSource) => void;
  clearActiveSource: () => void;
  play: () => void;
  pause: () => void;
  stop: () => void;
  toggle: () => void;
  seek: (time: number) => void;
  setLoop: (start: number | null, end: number | null) => void;
  toggleLoop: () => void;
  positionRef: React.RefObject<number>;
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
  const [transport, setTransport] = useState<TransportState>({
    position: 0,
    isPlaying: false,
    loopStart: null,
    loopEnd: null,
    loopEnabled: false,
    activeSource: null,
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

    audio.addEventListener("timeupdate", onTime);
    audio.addEventListener("ended", onEnd);
    return () => {
      audio.removeEventListener("timeupdate", onTime);
      audio.removeEventListener("ended", onEnd);
    };
  }, [transport.loopEnabled, transport.loopEnd, transport.loopStart]);

  const setActiveSource = useCallback((source: PlaybackSource) => {
    if (!audioRef.current) return;
    const audio = audioRef.current;
    audio.src = source.url;
    audio.load();
    setTransport((prev) => ({ ...prev, activeSource: source, position: 0, isPlaying: false }));
  }, []);

  const clearActiveSource = useCallback(() => {
    const audio = audioRef.current;
    if (audio) {
      audio.pause();
      audio.src = "";
    }
    setTransport((prev) => ({
      ...prev,
      activeSource: null,
      position: 0,
      isPlaying: false,
    }));
  }, []);

  const play = useCallback(() => {
    const audio = audioRef.current;
    if (!audio || !transport.activeSource?.url) return;
    audio.play().catch(() => {});
    setTransport((prev) => ({ ...prev, isPlaying: true }));
  }, [transport.activeSource]);

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
        clearActiveSource,
        play,
        pause,
        stop,
        toggle,
        seek,
        setLoop,
        toggleLoop,
        positionRef,
      }}
    >
      <audio ref={audioRef} crossOrigin="anonymous" style={{ display: "none" }} />
      {children}
    </TransportContext.Provider>
  );
}
