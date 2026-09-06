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

    assert events == [
        (0.2, "child"),
        (0.4, "child"),
        (0.6, "child"),
    ]


def test_progress_spans_compose_without_knowing_persistence():
    values: list[float] = []
    reporter = ProgressReporter(lambda value, _message: values.append(value))
    nested = reporter.span(0.2, 0.8).span(0.25, 0.75)

    nested.report(0.0)
    nested.report(0.5)
    nested.report(1.0)

    assert values == [0.35, 0.5, 0.65]


def test_progress_span_rejects_invalid_intervals():
    reporter = ProgressReporter(lambda _value, _message: None)

    invalid = [(-0.1, 0.5), (0.6, 0.5), (0.5, 1.1)]
    for start, end in invalid:
        try:
            reporter.span(start, end)
        except ValueError:
            pass
        else:
            raise AssertionError(f"expected invalid progress span: {(start, end)}")
