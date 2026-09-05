import { fireEvent, render, screen } from '@testing-library/react'
import { vi } from 'vitest'
import PianoRoll from '@/components/workspace/representations/PianoRoll'

const mockNotes = [
  { id: 'c4', pitch: 60, start: 0, end: 0.5, velocity: 80 },
  { id: 'e4', pitch: 64, start: 0.5, end: 1.0, velocity: 80 },
  { id: 'g4', pitch: 67, start: 1.0, end: 1.5, velocity: 80 },
]

const harmonySpans = [
  {
    id: 'chord-c',
    versionId: 'midi-v1',
    start: 0,
    end: 1,
    chord: 'C major',
    romanNumeral: 'I',
    harmonicFunction: 'Tonic',
    provenance: { engine: 'lv-chordia' },
  },
]

describe('PianoRoll', () => {
  it('renders without crashing with notes', () => {
    render(<PianoRoll notes={mockNotes} />)
    expect(screen.getByText(/3 notes/)).toBeInTheDocument()
  })

  it('renders empty state when no notes', () => {
    render(<PianoRoll notes={[]} />)
    expect(screen.getByText('No notes to display.')).toBeInTheDocument()
  })

  it('renders note labels on SVG', () => {
    render(<PianoRoll notes={mockNotes} bpm={120} />)
    expect(screen.getAllByText(/C4/).length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText(/E4/).length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText(/G4/).length).toBeGreaterThanOrEqual(1)
  })

  it('does not invent a beat grid when no observed pulse exists', () => {
    const { container } = render(<PianoRoll notes={mockNotes} bpm={120} />)

    expect(container.querySelector('[data-grid-kind="tempo-beat"]')).not.toBeInTheDocument()
    expect(container.querySelector('[data-grid-kind="observed-beat"]')).not.toBeInTheDocument()
    expect(container.querySelector('[data-grid-kind="observed-downbeat"]')).not.toBeInTheDocument()
    expect(container.querySelector('[data-grid-kind="subdivision"]')).not.toBeInTheDocument()
    expect(container.querySelector('[data-grid-kind="measure"]')).not.toBeInTheDocument()
    expect(container.querySelector('[data-pitch-lane="octave-anchor"]')).toBeInTheDocument()
    expect(container.querySelector('[data-ruler-kind="elapsed-time"]')).toBeInTheDocument()
  })

  it('uses exact non-uniform observed beats and downbeats instead of a BPM scaffold', () => {
    const { container } = render(
      <PianoRoll
        notes={mockNotes}
        bpm={120}
        beatTimes={[0.12, 0.71, 1.42]}
        downbeatTimes={[0.12]}
      />,
    )

    const beats = [...container.querySelectorAll('[data-grid-kind="observed-beat"]')]
    expect(beats).toHaveLength(3)
    expect(container.querySelectorAll('[data-grid-kind="observed-downbeat"]')).toHaveLength(1)
    expect(container.querySelector('[data-grid-kind="tempo-beat"]')).not.toBeInTheDocument()
    expect(container.querySelector('[data-grid-kind="subdivision"]')).not.toBeInTheDocument()
    expect(container.querySelector('[data-grid-kind="measure"]')).not.toBeInTheDocument()

    const x = beats.map((line) => Number(line.getAttribute('x1')))
    expect(x[1] - x[0]).not.toBeCloseTo(x[2] - x[1], 5)
  })

  it('fails closed without a beat grid for malformed observed pulse coordinates', () => {
    const { container } = render(
      <PianoRoll notes={mockNotes} bpm={120} beatTimes={[0.7, 0.2, 1.4]} />,
    )

    expect(container.querySelector('[data-grid-kind="observed-beat"]')).not.toBeInTheDocument()
    expect(container.querySelector('[data-grid-kind="observed-downbeat"]')).not.toBeInTheDocument()
    expect(container.querySelector('[data-grid-kind="tempo-beat"]')).not.toBeInTheDocument()
  })

  it('keeps active time visually distinct from selected notes', () => {
    const { container } = render(
      <PianoRoll
        notes={mockNotes}
        bpm={120}
        playheadTime={0.25}
        selectedNoteIds={['e4']}
      />,
    )

    expect(container.querySelectorAll('[data-note-state="active"]')).toHaveLength(1)
    expect(container.querySelectorAll('[data-note-state="selected"]')).toHaveLength(1)
    expect(container.querySelector('[data-playhead="true"]')).toBeInTheDocument()
  })

  it('renders literal harmony spans with optional theory context on the same timeline', () => {
    const { container } = render(
      <PianoRoll notes={mockNotes} bpm={120} harmonySpans={harmonySpans} playheadTime={0.25} />,
    )

    expect(screen.getByTestId('piano-roll-harmony')).toBeInTheDocument()
    expect(screen.getByText('C major')).toBeInTheDocument()
    expect(screen.getByText('I')).toBeInTheDocument()
    expect(container.querySelector('[data-harmony-playhead="true"]')).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: /C major, I, Tonic, 0\.00 to 1\.00 seconds/ }),
    ).toBeInTheDocument()
  })

  it('activates a harmony span by pointer or keyboard without inventing another interaction model', () => {
    const onHarmonySpanSelect = vi.fn()
    render(
      <PianoRoll
        notes={mockNotes}
        bpm={120}
        harmonySpans={harmonySpans}
        onHarmonySpanSelect={onHarmonySpanSelect}
      />,
    )
    const chord = screen.getByRole('button', { name: /C major, I, Tonic/ })

    fireEvent.click(chord)
    fireEvent.keyDown(chord, { key: 'Enter' })

    expect(onHarmonySpanSelect).toHaveBeenCalledTimes(2)
    expect(onHarmonySpanSelect).toHaveBeenLastCalledWith(harmonySpans[0])
  })

  it('uses shared selected time as temporal note context for a harmony span', () => {
    const { container } = render(
      <PianoRoll
        notes={mockNotes}
        bpm={120}
        harmonySpans={harmonySpans}
        selectionTimeRange={{ start: 0, end: 1 }}
      />,
    )

    expect(container.querySelector('[data-harmony-selected="true"]')).toBeInTheDocument()
    expect(container.querySelectorAll('[data-note-state="selected"]')).toHaveLength(2)
  })

  it('fails closed instead of drawing malformed harmony geometry', () => {
    render(
      <PianoRoll
        notes={mockNotes}
        bpm={120}
        harmonySpans={[{ ...harmonySpans[0], start: 2, end: 1 }]}
      />,
    )

    expect(screen.queryByTestId('piano-roll-harmony')).not.toBeInTheDocument()
  })
})
