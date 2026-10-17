from collections.abc import Callable
from typing import Any

import pytest

from boabem import Context


def test_intl_number_format_basic_grouping():
    ctx = Context()
    formatted = ctx.eval("new Intl.NumberFormat('en-US').format(1234567.89)")
    assert formatted == "1,234,567.89"


def test_intl_collator_compare_and_sort_sign():
    ctx = Context()
    cmp_ab = ctx.eval("new Intl.Collator('en').compare('a','b')")
    cmp_ba = ctx.eval("new Intl.Collator('en').compare('b','a')")
    cmp_aa = ctx.eval("new Intl.Collator('en').compare('a','a')")
    assert cmp_ab < 0
    assert cmp_ba > 0
    assert cmp_aa == 0


def test_intl_plural_rules_en_basic():
    ctx = Context()
    one = ctx.eval("new Intl.PluralRules('en-US').select(1)")
    other = ctx.eval("new Intl.PluralRules('en-US').select(2)")
    zero = ctx.eval("new Intl.PluralRules('en-US').select(0)")
    assert one == "one"
    assert other == "other"
    assert zero == "other"


def test_intl_listformat_conjunction_en():
    ctx = Context()
    formatted = ctx.eval(
        "new Intl.ListFormat('en', { style: 'long', type: 'conjunction' }).format(['A','B','C'])",
    )
    assert formatted == "A, B, and C"


def test_intl_get_canonical_locales_and_supported_locales():
    ctx = Context()
    canon = ctx.eval("Intl.getCanonicalLocales('EN-us')[0]")
    assert canon == "en-US"
    supported_len = ctx.eval("Intl.NumberFormat.supportedLocalesOf(['en-US']).length")
    assert supported_len == 1


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        pytest.param(
            "new Intl.NumberFormat('de-DE').format(1234567.89)",
            "1.234.567,89",
            id="decimal-comma",
        ),
        pytest.param(
            "new Intl.NumberFormat('en-US', {style: 'currency', currency: 'USD'}).format(12.5)",
            "$12.50",
            id="currency",
            marks=pytest.mark.xfail(
                strict=True,
                raises=RuntimeError,
                reason="Boa 0.22 does not implement currency formatting",
            ),
        ),
        pytest.param(
            "new Intl.NumberFormat('en-US', {style: 'percent', maximumFractionDigits: 1}).format(0.125)",
            "12.5%",
            id="percent",
            marks=pytest.mark.xfail(
                strict=True,
                raises=AssertionError,
                reason="Boa 0.22 formats percent values as decimals",
            ),
        ),
        pytest.param(
            "new Intl.NumberFormat('en-US').formatToParts(12.5)",
            [
                {"type": "integer", "value": "12"},
                {"type": "decimal", "value": "."},
                {"type": "fraction", "value": "5"},
            ],
            id="number-parts",
            marks=pytest.mark.xfail(
                strict=True,
                raises=RuntimeError,
                reason="Boa 0.22 does not implement NumberFormat.formatToParts",
            ),
        ),
        pytest.param(
            """
            new Intl.DateTimeFormat('en-US', {
                timeZone: 'UTC', year: 'numeric', month: '2-digit', day: '2-digit'
            }).format(new Date('2024-02-29T23:30:00Z'));
            """,
            "02/29/2024",
            id="utc-leap-day",
            marks=pytest.mark.xfail(
                strict=True,
                raises=AssertionError,
                reason="Boa 0.22 ignores individual date field widths",
            ),
        ),
        pytest.param(
            """
            new Intl.DateTimeFormat('en-US', {
                timeZone: 'Asia/Seoul', year: 'numeric', month: '2-digit', day: '2-digit'
            }).format(new Date('2024-02-29T23:30:00Z'));
            """,
            "03/01/2024",
            id="time-zone-date-rollover",
            marks=pytest.mark.xfail(
                strict=True,
                raises=AssertionError,
                reason="Boa 0.22 ignores individual date field widths",
            ),
        ),
        pytest.param(
            "['10', '2', '1'].sort(new Intl.Collator('en', {numeric: true}).compare)",
            ["1", "2", "10"],
            id="numeric-collation",
        ),
        pytest.param(
            "new Intl.Collator('en', {sensitivity: 'base'}).compare('é', 'E')",
            0,
            id="base-sensitivity",
        ),
        pytest.param(
            "[1, 2, 3, 4, 11, 21].map(n => new Intl.PluralRules('en', {type: 'ordinal'}).select(n))",
            ["one", "two", "few", "other", "other", "one"],
            id="ordinal-plurals",
        ),
        pytest.param(
            "[-1, 0, 1].map(n => new Intl.RelativeTimeFormat('en', {numeric: 'auto'}).format(n, 'day'))",
            ["yesterday", "today", "tomorrow"],
            id="relative-time",
            marks=pytest.mark.xfail(
                strict=True,
                raises=RuntimeError,
                reason="Boa 0.22 does not expose Intl.RelativeTimeFormat",
            ),
        ),
        pytest.param(
            "new Intl.ListFormat('en', {type: 'disjunction'}).format(['A', 'B', 'C'])",
            "A, B, or C",
            id="disjunction",
        ),
        pytest.param("new Intl.ListFormat('en').format([])", "", id="empty-list"),
        pytest.param(
            "new Intl.DisplayNames(['en'], {type: 'region'}).of('KR')",
            "South Korea",
            id="display-names",
            marks=pytest.mark.xfail(
                strict=True,
                raises=RuntimeError,
                reason="Boa 0.22 does not expose Intl.DisplayNames",
            ),
        ),
        pytest.param(
            "Array.from(new Intl.Segmenter('en', {granularity: 'grapheme'}).segment('e\\u0301👨‍👩‍👧‍👦'), part => part.segment)",
            ["é", "👨‍👩‍👧‍👦"],
            id="grapheme-clusters",
        ),
        pytest.param(
            "Intl.getCanonicalLocales(['EN-us', 'en-US', 'ko-kr'])",
            ["en-US", "ko-KR"],
            id="canonical-locale-deduplication",
        ),
    ],
)
def test_intl_formats_and_locales(
    evaluate: Callable[[str], Any], source: str, expected: Any
):
    assert evaluate(source) == expected


@pytest.mark.parametrize(
    ("time_zone", "expected"),
    [("UTC", "2/29/24"), ("Asia/Seoul", "3/1/24")],
)
def test_intl_date_style_and_time_zone(
    evaluate: Callable[[str], Any], time_zone: str, expected: str
):
    source = f"""
        new Intl.DateTimeFormat('en-US', {{
            timeZone: '{time_zone}', dateStyle: 'short'
        }}).format(new Date('2024-02-29T23:30:00Z'));
    """

    assert evaluate(source) == expected


@pytest.mark.parametrize(
    ("source", "error"),
    [
        ("Intl.getCanonicalLocales('en_US')", "RangeError"),
        ("new Intl.NumberFormat('en', {style: 'currency'})", "TypeError"),
        ("new Intl.NumberFormat('en', {minimumFractionDigits: 101})", "RangeError"),
        ("new Intl.DateTimeFormat('en', {timeZone: 'Invalid/Zone'})", "RangeError"),
        ("new Intl.PluralRules('en', {type: 'invalid'})", "RangeError"),
        ("new Intl.ListFormat('en').format(['A', 1])", "TypeError"),
    ],
)
def test_intl_invalid_input_raises_and_context_recovers(
    evaluate: Callable[[str], Any], source: str, error: str
):
    with pytest.raises(RuntimeError, match=error):
        evaluate(source)

    assert evaluate("new Intl.NumberFormat('en-US').format(1234)") == "1,234"
