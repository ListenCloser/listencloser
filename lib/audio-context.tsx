/**
 * Shared audio playback context.
 *
 * Architecture: A single <audio> element is shared across all components
 * (Library, Transform, Visualize). Only one track can play at a time.
 * Components use useSharedAudio() to get play/pause/stop controls.
 *
 * This avoids the browser limit of ~5 concurrent AudioContext instances
 * and ensures clean transitions between tracks.
 */

"use client";

import { createContext, useContext, useState, useRef, useCallback, useEffect, type ReactNode } from "react";

type SharedAudioState = {
  audioRef: React.RefObject<HTMLAudioElement | null>;
  playing: string | null;
  currentTime: number;
  duration: number;
  paused: boolean;
  play: (id: string, url: string) => void;
  pause: () => void;
  resume: () => void;
  stop: () => void;
  toggle: (id: string, url: string) => void;
};

const SharedAudioContext = createContext<SharedAudioState | null>(null);

export function useSharedAudio(): SharedAudioState {
  const ctx = useContext(SharedAudioContext);
  if (!ctx) throw new Error("useSharedAudio must be used within SharedAudioProvider");
  return ctx;
}

export function SharedAudioProvider({ children }: { children: ReactNode }) {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [playing, setPlaying] = useState<string | null>(null);
  const [paused, setPaused] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const cleanupRef = useRef<(() => void) | null>(null);

  useEffect(() => {
    return () => { cleanupRef.current?.(); };
  }, []);

  const stop = useCallback(() => {
    cleanupRef.current?.();
    cleanupRef.current = null;
    const audio = audioRef.current;
    if (audio) {
      audio.pause();
      audio.currentTime = 0;
    }
    setPlaying(null);
    setPaused(false);
    setCurrentTime(0);
    setDuration(0);
  }, []);

  const play = useCallback((id: string, url: string) => {
    cleanupRef.current?.();
    cleanupRef.current = null;
    const audio = audioRef.current;
    if (!audio) return;

    const onTime = () => setCurrentTime(audio.currentTime);
    const onMeta = () => setDuration(audio.duration);
    const onEnd = () => { stop(); };

    audio.addEventListener("timeupdate", onTime);
    audio.addEventListener("loadedmetadata", onMeta);
    audio.addEventListener("ended", onEnd);

    cleanupRef.current = () => {
      audio.removeEventListener("timeupdate", onTime);
      audio.removeEventListener("loadedmetadata", onMeta);
      audio.removeEventListener("ended", onEnd);
    };

    audio.src = url;
    audio.play().catch(() => {});
    setPlaying(id);
    setPaused(false);
    setCurrentTime(0);
    setDuration(0);
  }, [stop]);

  const pause = useCallback(() => {
    audioRef.current?.pause();
    setPaused(true);
  }, []);

  const resume = useCallback(() => {
    const audio = audioRef.current;
    if (!audio) return;
    audio.play().catch(() => {});
    setPaused(false);
  }, []);

  const toggle = useCallback((id: string, url: string) => {
    if (playing !== id) {
      stop();
      play(id, url);
    } else if (paused) {
      resume();
    } else {
      pause();
    }
  }, [playing, paused, stop, play, pause, resume]);

  return (
    <SharedAudioContext.Provider value={{ audioRef, playing, currentTime, duration, paused, play, pause, resume, stop, toggle }}>
      <audio ref={audioRef} crossOrigin="anonymous" style={{ display: "none" }} />
      {children}
    </SharedAudioContext.Provider>
  );
}
