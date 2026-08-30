import { render, screen } from '@testing-library/react'
import PianoRoll from '@/components/PianoRoll'

const mockNotes = [
  { id: 'c4', pitch: 60, start: 0, end: 0.5, velocity: 80 },
  { id: 'e4', pitch: 64, start: 0.5, end: 1.0, velocity: 80 },
  { id: 'g4', pitch: 67, start: 1.0, end: 1.5, velocity: 80 },
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

  it('distinguishes beats from subdivisions without inventing measure lines', () => {
    const { container } = render(<PianoRoll notes={mockNotes} bpm={120} />)

    expect(container.querySelectorAll('[data-grid-kind="beat"]').length).toBeGreaterThan(0)
    expect(container.querySelectorAll('[data-grid-kind="subdivision"]').length).toBeGreaterThan(0)
    expect(container.querySelector('[data-grid-kind="measure"]')).not.toBeInTheDocument()
    expect(container.querySelector('[data-pitch-lane="octave-anchor"]')).toBeInTheDocument()
    expect(container.querySelector('[data-ruler-kind="elapsed-time"]')).toBeInTheDocument()
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
})
