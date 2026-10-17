import json
from collections.abc import Callable
from typing import Any

import pytest

from boabem import undefined


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        pytest.param("/missing/.exec('text')", None, id="no-match"),
        pytest.param(
            r"Array.from(/(a)?(b)/.exec('b'))",
            ["b", undefined, "b"],
            id="unmatched-capture",
        ),
        pytest.param(
            r"'한글 abc 123'.match(/\p{L}+/gu)",
            ["한글", "abc"],
            id="unicode-property-escapes",
        ),
        pytest.param(
            "['😊'.match(/./g).length, '😊'.match(/./gu).length]",
            [2, 1],
            id="unicode-code-points",
        ),
        pytest.param(
            r"'a1한B'.match(/[\p{ASCII}&&\p{Letter}]/gv)",
            ["a", "B"],
            id="unicode-set-intersection",
        ),
        pytest.param(
            r"/(?<=price=)\d+(?=;)/.exec('price=42;')[0]",
            "42",
            id="lookbehind-and-lookahead",
        ),
        pytest.param(
            r"[/^b$/m.test('a\nb\nc'), /^b$/.test('a\nb\nc'), /a.b/s.test('a\nb'), /a.b/.test('a\nb')]",
            [True, False, True, False],
            id="multiline-and-dotall",
        ),
        pytest.param(
            r"'Ada Lovelace'.replace(/(?<first>\w+) (?<last>\w+)/, '$<last>, $<first>')",
            "Lovelace, Ada",
            id="named-capture-replacement",
        ),
        pytest.param(
            r"'a1b22'.replace(/\d+/g, match => String(Number(match) * 2))",
            "a2b44",
            id="replacement-callback",
        ),
        pytest.param(
            r"'a1b22c'.split(/(\d+)/)",
            ["a", "1", "b", "22", "c"],
            id="split-keeps-captures",
        ),
    ],
)
def test_regexp_matching_and_string_methods(
    evaluate: Callable[[str], Any], source: str, expected: Any
):
    assert evaluate(source) == expected


def test_regexp_named_captures_and_indices(evaluate: Callable[[str], Any]):
    source = r"""
        const match = /(?<word>[A-Za-z]+)-(\d+)/d.exec('!item-42?');
        ({captures: Array.from(match), index: match.index, input: match.input,
          groups: match.groups, indices: Array.from(match.indices),
          groupIndices: match.indices.groups});
    """

    assert evaluate(source) == {
        "captures": ["item-42", "item", "42"],
        "index": 1,
        "input": "!item-42?",
        "groups": {"word": "item"},
        "indices": [[1, 8], [1, 5], [6, 8]],
        "groupIndices": {"word": [1, 5]},
    }


def test_regexp_global_last_index_persists_and_resets(
    evaluate: Callable[[str], Any],
):
    evaluate("const regexp = /a/g")

    assert evaluate("[regexp.exec('aba').index, regexp.lastIndex]") == [0, 1]
    assert evaluate("[regexp.exec('aba').index, regexp.lastIndex]") == [2, 3]
    assert evaluate("[regexp.exec('aba'), regexp.lastIndex]") == [None, 0]
    assert evaluate("[regexp.test('aba'), regexp.lastIndex]") == [True, 1]


def test_regexp_sticky_does_not_search_ahead(evaluate: Callable[[str], Any]):
    evaluate("const regexp = /a/y; regexp.lastIndex = 1")

    assert evaluate("[regexp.exec('aba'), regexp.lastIndex]") == [None, 0]
    evaluate("regexp.lastIndex = 2")
    assert evaluate("[regexp.exec('aba').index, regexp.lastIndex]") == [2, 3]


def test_regexp_match_all_preserves_original_last_index(
    evaluate: Callable[[str], Any],
):
    source = r"""
        const regexp = /\d+/g;
        regexp.lastIndex = 2;
        const matches = Array.from('a1b22c333'.matchAll(regexp),
            match => ({value: match[0], index: match.index}));
        ({matches, lastIndex: regexp.lastIndex});
    """

    assert evaluate(source) == {
        "matches": [{"value": "22", "index": 3}, {"value": "333", "index": 6}],
        "lastIndex": 2,
    }


def test_regexp_match_all_advances_empty_unicode_matches(
    evaluate: Callable[[str], Any],
):
    assert evaluate("Array.from('😊'.matchAll(/(?:)/gu), match => match.index)") == [
        0,
        2,
    ]


@pytest.mark.parametrize(
    "text",
    ["foo-bar", "(a+b)*[0-9]?", "a/b\\c", "line\nnext\t", "한글😊", "", "1"],
)
def test_regexp_escape_round_trips_literal_input(
    evaluate: Callable[[str], Any], text: str
):
    # JSON quoting keeps the input literal, including backslashes and line breaks.
    source = f"""
        const text = {json.dumps(text, ensure_ascii=False)};
        const regexp = new RegExp('^(?:' + RegExp.escape(text) + ')$', 'u');
        [regexp.test(text), regexp.test(text + '!')];
    """

    assert evaluate(source) == [True, False]


@pytest.mark.parametrize(
    ("source", "error"),
    [
        ("new RegExp('[')", "SyntaxError"),
        ("/[/", "SyntaxError"),
        ("new RegExp('a', 'gg')", "SyntaxError"),
        ("new RegExp('a', 'z')", "SyntaxError"),
        ("new RegExp('a', 'uv')", "SyntaxError"),
        ("'a'.matchAll(/a/)", "TypeError"),
        ("RegExp.escape(123)", "TypeError"),
    ],
)
def test_regexp_invalid_input_raises_and_context_recovers(
    evaluate: Callable[[str], Any], source: str, error: str
):
    with pytest.raises(RuntimeError, match=error):
        evaluate(source)

    assert evaluate("/ok/.test('ok')") is True
