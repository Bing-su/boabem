from collections.abc import Callable
from typing import Any

import pytest


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        pytest.param(
            "Temporal.PlainDate.from('2024-02-29').add({days: 1}).toString()",
            "2024-03-01",
            id="leap-day",
        ),
        pytest.param(
            "Temporal.PlainDate.from('2023-01-31').add({months: 1}).toString()",
            "2023-02-28",
            id="month-overflow-constrains",
        ),
        pytest.param(
            "Temporal.PlainDate.from({year: 2023, month: 2, day: 29}).toString()",
            "2023-02-28",
            id="field-overflow-constrains",
        ),
        pytest.param(
            "Temporal.PlainDate.from('2024-02-28').until('2024-03-01').days",
            2,
            id="date-difference",
        ),
        pytest.param(
            "Temporal.PlainTime.from('23:59:59.999999999').add({nanoseconds: 1}).toString()",
            "00:00:00",
            id="time-wraps-at-midnight",
        ),
        pytest.param(
            "Temporal.PlainDateTime.from('2024-12-31T23:30').add({minutes: 90}).toString()",
            "2025-01-01T01:00:00",
            id="date-time-year-rollover",
        ),
        pytest.param(
            "Temporal.PlainYearMonth.from('2024-12').add({months: 1}).toString()",
            "2025-01",
            id="year-month",
        ),
        pytest.param(
            "Temporal.PlainMonthDay.from('02-29').toPlainDate({year: 2024}).toString()",
            "2024-02-29",
            id="month-day",
        ),
        pytest.param(
            "Temporal.Instant.from('2024-01-01T09:00:00+09:00').toString()",
            "2024-01-01T00:00:00Z",
            id="instant-offset",
        ),
        pytest.param(
            "Temporal.Instant.fromEpochNanoseconds(1700000000123456789n).epochNanoseconds",
            1700000000123456789,
            id="nanosecond-bigint-precision",
        ),
        pytest.param(
            "Temporal.Instant.fromEpochNanoseconds(-1n).toString()",
            "1969-12-31T23:59:59.999999999Z",
            id="before-epoch",
        ),
        pytest.param(
            "Temporal.Duration.from('PT1H30M').total({unit: 'minutes'})",
            90,
            id="duration-total",
        ),
        pytest.param(
            "Temporal.Duration.from({months: 1}).total({unit: 'days', relativeTo: '2024-02-01'})",
            29,
            id="calendar-relative-duration",
        ),
    ],
)
def test_temporal_arithmetic_and_precision(
    evaluate: Callable[[str], Any], source: str, expected: str | int
):
    assert evaluate(source) == expected


def test_temporal_operations_do_not_mutate_original(
    evaluate: Callable[[str], Any],
):
    evaluate("const date = Temporal.PlainDate.from('2024-02-29')")

    assert evaluate("date.with({year: 2023}).toString()") == "2023-02-28"
    assert evaluate("date.add({years: 1}).toString()") == "2025-02-28"
    assert evaluate("date.toString()") == "2024-02-29"


@pytest.mark.parametrize(
    ("date", "elapsed_hours", "offset"),
    [
        ("2024-03-09", 23, "-04:00"),
        ("2024-11-02", 25, "-05:00"),
    ],
)
def test_temporal_calendar_day_across_dst(
    evaluate: Callable[[str], Any], date: str, elapsed_hours: int, offset: str
):
    # Compare a calendar day with 24 hours to catch DST arithmetic regressions.
    source = f"""
        const start = Temporal.ZonedDateTime.from('{date}T12:00[America/New_York]');
        const nextDay = start.add({{days: 1}});
        [nextDay.hour, nextDay.offset, start.until(nextDay, {{largestUnit: 'hours'}}).hours,
         start.until(start.add({{hours: 24}}), {{largestUnit: 'hours'}}).hours];
    """

    assert evaluate(source) == [12, offset, elapsed_hours, 24]


@pytest.mark.parametrize(
    ("disambiguation", "expected"),
    [
        ("earlier", "2024-11-03T05:30:00Z"),
        ("later", "2024-11-03T06:30:00Z"),
    ],
)
def test_temporal_repeated_dst_hour(
    evaluate: Callable[[str], Any], disambiguation: str, expected: str
):
    source = f"""
        Temporal.ZonedDateTime.from('2024-11-03T01:30[America/New_York]',
            {{disambiguation: '{disambiguation}'}}).toInstant().toString();
    """

    assert evaluate(source) == expected


@pytest.mark.parametrize(
    ("source", "error"),
    [
        ("Temporal.PlainDate.from('2023-02-29')", "RangeError"),
        (
            "Temporal.PlainDate.from({year: 2023, month: 2, day: 29}, {overflow: 'reject'})",
            "RangeError",
        ),
        (
            "Temporal.PlainDate.from('2023-01-31').add({months: 1}, {overflow: 'reject'})",
            "RangeError",
        ),
        ("Temporal.Instant.from('2024-01-01T00:00:00')", "RangeError"),
        ("Temporal.Instant.fromEpochNanoseconds(1)", "TypeError"),
        ("Temporal.Duration.from({hours: 1, minutes: -1})", "RangeError"),
        ("Temporal.Duration.from({months: 1}).total({unit: 'days'})", "RangeError"),
        (
            "Temporal.ZonedDateTime.from('2024-03-10T02:30[America/New_York]', {disambiguation: 'reject'})",
            "RangeError",
        ),
        (
            "Temporal.ZonedDateTime.from('2024-11-03T01:30[America/New_York]', {disambiguation: 'reject'})",
            "RangeError",
        ),
    ],
)
def test_temporal_invalid_input_raises_and_context_recovers(
    evaluate: Callable[[str], Any], source: str, error: str
):
    with pytest.raises(RuntimeError, match=error):
        evaluate(source)

    assert evaluate("Temporal.PlainDate.from('2024-02-29').day") == 29
