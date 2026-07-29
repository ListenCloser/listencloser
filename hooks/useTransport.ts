"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import { useSharedAudio } from "@/lib/audio-context";
import { synthAudio } from "@/lib/music";

export type PlaybackSource = "original" | "midi" | "synth";

export type TransportState = {
  source: PlaybackSource;
  currentTime: number;
  duration: number;
  isPlaying: boolean;
  isPaused: boolean;
  isLoading: boolean;
  midiWavUrl: string | null;
  setSource: (src: PlaybackSource) => void;
  play: () => void;
  pause: () => void;
  resume: () => void;
  stop: () => void;
  toggle: () => void;
  seek: (time: number) => void;
};

export function useTransport(trackId: string | null, midiBase64?: string): TransportState {
  const { play: sharedPlay, pause: sharedPause, resume: sharedResume, stop: sharedStop, toggle: sharedToggle, playing, currentTime, duration, paused, audioRef } = useSharedAudio();
  const [source, setSourceState] = useState<PlaybackSource>("original");
  const [midiWavUrl, setMidiWavUrl] = useState<string | null>(null);
  const [synthLoading, setSynthLoading] = useState(false);
  const [midiTime, setMidiTime] = useState(0);
  const midiIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const midiStartRef = useRef<number>(0);
  const midiOffsetRef = useRef<number>(0);
  const switchingRef = useRef(false);

  // Synthesize MIDI to WAV when source switches to midi/synth
  useEffect(() => {
    if ((source === "midi" || source === "synth") && midiBase64 && !midiWavUrl && !synthLoading) {
      setSynthLoading(true);
      synthAudio(midiBase64)
        .then((res) => {
          const bytes = Uint8Array.from(atob(res.wav_base64), (c) => c.charCodeAt(0));
          const blob = new Blob([bytes], { type: "audio/wav" });
          setMidiWavUrl(URL.createObjectURL(blob));
        })
        .catch(() => {})
        .finally(() => setSynthLoading(false));
    }
  }, [source, midiBase64, midiWavUrl, synthLoading]);

  // Cleanup MIDI interval
  useEffect(() => {
    return () => {
      if (midiIntervalRef.current) clearInterval(midiIntervalRef.current);
    };
  }, []);

  const stopMidiTimer = useCallback(() => {
    if (midiIntervalRef.current) {
      clearInterval(midiIntervalRef.current);
      midiIntervalRef.current = null;
    }
  }, []);

  const startMidiTimer = useCallback((offset: number) => {
    stopMidiTimer();
    midiStartRef.current = performance.now();
    midiOffsetRef.current = offset;
    midiIntervalRef.current = setInterval(() => {
      const elapsed = (performance.now() - midiStartRef.current) / 1000 + midiOffsetRef.current;
      setMidiTime(elapsed);
    }, 50);
  }, [stopMidiTimer]);

  const effectiveTime = source === "original" ? currentTime : midiTime;
  const effectiveDuration = source === "original" ? duration : (midiWavUrl ? duration : 0);
  const isPlaying = source === "original" ? (playing === trackId && !paused) : (midiIntervalRef.current !== null && !paused);
  const isPaused = source === "original" ? (playing === trackId && paused) : (paused && midiIntervalRef.current === null);

  const playOriginal = useCallback(() => {
    if (!trackId) return;
    stopMidiTimer();
    sharedPlay(trackId, trackId);
  }, [trackId, sharedPlay, stopMidiTimer]);

  const playMidi = useCallback(() => {
    if (!midiWavUrl || !trackId) return;
    sharedStop();
    sharedPlay(`${trackId}-midi`, midiWavUrl);
    const seekTo = midiOffsetRef.current || 0;
    if (audioRef.current) {
      audioRef.current.currentTime = seekTo;
    }
    setMidiTime(seekTo);
    startMidiTimer(seekTo);
  }, [midiWavUrl, trackId, sharedPlay, sharedStop, audioRef, startMidiTimer]);

  const setSource = useCallback((newSource: PlaybackSource) => {
    if (newSource === source || switchingRef.current) return;
    switchingRef.current = true;

    const currentTimeSnapshot = effectiveTime;
    const wasPlaying = isPlaying;

    // Stop everything
    sharedStop();
    stopMidiTimer();
    setMidiTime(0);

    setSourceState(newSource);

    // After state update, play the new source
    setTimeout(() => {
      if (wasPlaying) {
        if (newSource === "original") {
          playOriginal();
          // Seek to the previous position
          if (audioRef.current) {
            audioRef.current.currentTime = currentTimeSnapshot;
          }
        } else if (newSource === "midi" || newSource === "synth") {
          midiOffsetRef.current = currentTimeSnapshot;
          playMidi();
        }
      }
      switchingRef.current = false;
    }, 50);
  }, [source, effectiveTime, isPlaying, sharedStop, stopMidiTimer, playOriginal, playMidi, audioRef]);

  const play = useCallback(() => {
    if (source === "original") {
      playOriginal();
    } else {
      if (!midiWavUrl) return;
      playMidi();
    }
  }, [source, playOriginal, playMidi, midiWavUrl]);

  const pause = useCallback(() => {
    sharedPause();
    stopMidiTimer();
  }, [sharedPause, stopMidiTimer]);

  const resume = useCallback(() => {
    if (source === "original") {
      sharedResume();
    } else if (midiWavUrl) {
      playMidi();
    }
  }, [source, sharedResume, playMidi, midiWavUrl]);

  const stop = useCallback(() => {
    sharedStop();
    stopMidiTimer();
    setMidiTime(0);
    midiOffsetRef.current = 0;
  }, [sharedStop, stopMidiTimer]);

  const toggle = useCallback(() => {
    if (isPlaying) {
      pause();
    } else if (isPaused) {
      resume();
    } else {
      play();
    }
  }, [isPlaying, isPaused, pause, resume, play]);

  const seek = useCallback((time: number) => {
    if (source === "original" && audioRef.current) {
      audioRef.current.currentTime = time;
    } else {
      midiOffsetRef.current = time;
      setMidiTime(time);
    }
  }, [source, audioRef]);

  // Reset state when trackId changes
  useEffect(() => {
    setSourceState("original");
    setMidiWavUrl(null);
    setMidiTime(0);
    midiOffsetRef.current = 0;
    stopMidiTimer();
  }, [trackId, stopMidiTimer]);

  return {
    source,
    currentTime: effectiveTime,
    duration: effectiveDuration,
    isPlaying,
    isPaused,
    isLoading: synthLoading,
    midiWavUrl,
    setSource,
    play,
    pause,
    resume,
    stop,
    toggle,
    seek,
  };
}
