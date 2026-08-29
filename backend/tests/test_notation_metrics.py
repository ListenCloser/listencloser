import pytest

from evaluation.notation_metrics import diagnose_musicxml


def _score(body: str) -> bytes:
    return f"""<?xml version=\"1.0\" encoding=\"utf-8\"?>
<score-partwise version=\"4.0\">
  <part-list>
    <score-part id=\"P1\"><part-name>Piano</part-name></score-part>
  </part-list>
  <part id=\"P1\">{body}</part>
</score-partwise>
""".encode()


def test_tie_fragmentation_reconstructs_logical_pitched_notes():
    xml = _score(
        """
    <measure number=\"1\">
      <note><rest/><duration>4</duration><voice>1</voice></note>
      <note>
        <pitch><step>C</step><octave>4</octave></pitch>
        <duration>4</duration><voice>1</voice>
      </note>
      <note>
        <pitch><step>G</step><octave>4</octave></pitch>
        <duration>4</duration><tie type=\"start\"/><voice>1</voice>
      </note>
    </measure>
    <measure number=\"2\">
      <note>
        <pitch><step>G</step><octave>4</octave></pitch>
        <duration>4</duration><tie type=\"stop\"/><voice>1</voice>
      </note>
    </measure>
    """
    )

    diagnostics = diagnose_musicxml(xml)

    assert diagnostics.total_note_count == 4
    assert diagnostics.pitched_note_count == 3
    assert diagnostics.tie_count == 2
    assert diagnostics.tie_start_count == 1
    assert diagnostics.logical_pitched_note_count == 2
    assert diagnostics.tie_fragment_overhead == pytest.approx(0.5)
    assert diagnostics.to_dict()["tie_fragment_overhead"] == 0.5


def test_multi_fragment_tie_chain_counts_each_extra_written_fragment_once():
    xml = _score(
        """
    <measure number=\"1\">
      <note>
        <pitch><step>A</step><octave>3</octave></pitch>
        <duration>4</duration><tie type=\"start\"/><voice>1</voice>
      </note>
    </measure>
    <measure number=\"2\">
      <note>
        <pitch><step>A</step><octave>3</octave></pitch>
        <duration>4</duration><tie type=\"stop\"/><tie type=\"start\"/><voice>1</voice>
      </note>
    </measure>
    <measure number=\"3\">
      <note>
        <pitch><step>A</step><octave>3</octave></pitch>
        <duration>4</duration><tie type=\"stop\"/><voice>1</voice>
      </note>
    </measure>
    """
    )

    diagnostics = diagnose_musicxml(xml)

    assert diagnostics.pitched_note_count == 3
    assert diagnostics.tie_count == 4
    assert diagnostics.tie_start_count == 2
    assert diagnostics.logical_pitched_note_count == 1
    assert diagnostics.tie_fragment_overhead == pytest.approx(2.0)


def test_rest_only_score_has_no_tie_fragmentation_denominator():
    xml = _score(
        """
    <measure number=\"1\">
      <note><rest/><duration>4</duration><voice>1</voice></note>
    </measure>
    """
    )

    diagnostics = diagnose_musicxml(xml)

    assert diagnostics.pitched_note_count == 0
    assert diagnostics.logical_pitched_note_count == 0
    assert diagnostics.tie_start_count == 0
    assert diagnostics.tie_fragment_overhead is None
