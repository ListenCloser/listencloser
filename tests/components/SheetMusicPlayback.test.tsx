import { render, screen } from "@testing-library/react";
import SheetMusic from "@/components/SheetMusic";

const minimalMusicXml = `<?xml version="1.0" encoding="UTF-8"?>
<score-partwise version="3.1">
  <part-list><score-part id="P1"><part-name>Piano</part-name></score-part></part-list>
  <part id="P1">
    <measure number="1"><attributes><divisions>1</divisions><key><fifths>0</fifths></key><time><beats>4</beats><beat-type>4</beat-type></time><clef><sign>G</sign><line>2</line></clef></attributes><note><pitch><step>C</step><octave>4</octave></pitch><duration>4</duration><type>whole</type></note></measure>
    <measure number="2"><note><pitch><step>D</step><octave>4</octave></pitch><duration>4</duration><type>whole</type></note></measure>
  </part>
</score-partwise>`;

describe("SheetMusic", () => {
  it("renders fallback when musicXml is empty", () => {
    render(<SheetMusic musicXml="" />);
    expect(screen.getByText("No sheet music data available.")).toBeInTheDocument();
  });

  it("renders hint for unavailable score playback", () => {
    render(<SheetMusic musicXml={minimalMusicXml} hasScorePlayback={false} />);
    expect(
      screen.getByText("Score playback is not available for this piece yet."),
    ).toBeInTheDocument();
  });

  it("renders hint for active score playback", () => {
    render(
      <SheetMusic
        musicXml={minimalMusicXml}
        hasScorePlayback={true}
        isScoreActive={true}
      />,
    );
    expect(
      screen.getByText(
        "Playing the score rendition in notation time. Click a measure to jump or select it.",
      ),
    ).toBeInTheDocument();
  });

  it("renders hint for inactive score source with available playback", () => {
    render(
      <SheetMusic
        musicXml={minimalMusicXml}
        hasScorePlayback={true}
        isScoreActive={false}
      />,
    );
    expect(
      screen.getByText(
        "Select Score rendition in the transport to hear this notation (notation time).",
      ),
    ).toBeInTheDocument();
  });
});
