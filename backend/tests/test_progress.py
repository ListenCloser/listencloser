import pytest

from domain.progress import ProgressReporter


def test_progress_reporter_clamps_and_preserves_message():
    events: list[tuple[float, str | None]] = []
    reporter = ProgressReporter(lambda value, message: events.append((value, message)))

    reporter.report(-0.5, "starting")
    reporter.report(1.5, "finished")

    assert events == [(0.0, "starting"), (1.0, "finished")]


def test_progress_span_maps_child_progress_into_parent_interval():
    events: list[tuple[float, str | None]] = []
    reporter = ProgressReporter(lambda value, message: events.append((value, message)))
    child = reporter.span(0.2, 0.6)

    child.report(0.0, "child")
    child.report(0.5, "child")
    child.report(1.0, "child")

    values = [value for value, _message in events]
    assert values == pytest.approx([0.2, 0.4, 0.6])
    assert [message for _value, message in events] == ["child", "child", "child"]


def test_progress_spans_compose_without_knowing_persistence():
    values: list[float] = []
    reporter = ProgressReporter(lambda value, _message: values.append(value))
    nested = reporter.span(0.2, 0.8).span(0.25, 0.75)

    nested.report(0.0)
    nested.report(0.5)
    nested.report(1.0)

    assert values == pytest.approx([0.35, 0.5, 0.65])


@pytest.mark.parametrize(
    ("start", "end"),
    [(-0.1, 0.5), (0.6, 0.5), (0.5, 1.1)],
)
def test_progress_span_rejects_invalid_intervals(start: float, end: float):
    reporter = ProgressReporter(lambda _value, _message: None)

    with pytest.raises(ValueError, match="progress span"):
        reporter.span(start, end)
