import { useCallback, useEffect, useRef, useState } from 'react'
import { PlaybackEngine } from '../audio/engine'
import type { MidiTrack } from '../midi/parseSmf'

/**
 * Owns one PlaybackEngine for the app's lifetime and mirrors the parts React
 * needs to render. The playhead is polled on rAF rather than pushed from the
 * scheduler — the audio clock runs at its own rate and we only need it at frame
 * rate, so polling keeps the two decoupled.
 */
export function usePlayback() {
  const engineRef = useRef<PlaybackEngine | null>(null)
  if (!engineRef.current) engineRef.current = new PlaybackEngine()
  const engine = engineRef.current

  const [playing, setPlaying] = useState(false)
  const [position, setPosition] = useState(0)
  const [mixVersion, setMixVersion] = useState(0) // bumps when mute/solo change

  useEffect(() => {
    engine.onStateChange = (s) => {
      setPlaying(s.playing)
      setPosition(s.positionBeats)
      setMixVersion((v) => v + 1)
    }
    return () => { engine.dispose() }
  }, [engine])

  useEffect(() => {
    if (!playing) return
    let raf = 0
    const tick = () => {
      setPosition(engine.positionBeats())
      raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [playing, engine])

  const load = useCallback((tracks: MidiTrack[], tempoBpm: number, endBeat: number) => {
    engine.load(tracks, tempoBpm, endBeat)
    setPosition(0)
  }, [engine])

  const toggle = useCallback((fromBeat?: number) => { void engine.toggle(fromBeat) }, [engine])
  const play = useCallback((fromBeat?: number) => { void engine.play(fromBeat) }, [engine])
  const stop = useCallback(() => engine.stop(), [engine])
  const seek = useCallback((beat: number) => {
    engine.seek(beat)
    setPosition(engine.positionBeats())
  }, [engine])

  const setMuted = useCallback((role: string, v: boolean) => engine.setMuted(role, v), [engine])
  const setSoloed = useCallback((role: string, v: boolean) => engine.setSoloed(role, v), [engine])
  const setLoop = useCallback(
    (r: { start: number; end: number } | null) => engine.setLoop(r), [engine])

  return {
    engine, playing, position, mixVersion,
    load, toggle, play, stop, seek, setMuted, setSoloed, setLoop,
  }
}
