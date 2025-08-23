import sys
from math import isnan
from typing import Any

import json5
import pytest
from deepdiff import DeepDiff
from hypothesis import given
from hypothesis import strategies as st

from boabem import Context, Undefined


def json(*, finite_only: bool = True):
    """Helper function to describe JSON objects, with optional inf and nan."""
    numbers = st.floats(allow_infinity=not finite_only, allow_nan=not finite_only)
    return st.recursive(
        st.none() | st.booleans() | st.integers() | numbers | st.text(),
        extend=lambda xs: st.lists(xs) | st.dictionaries(st.text(), xs),
    )


def json_array(*, finite_only: bool = True):
    return st.lists(json(finite_only=finite_only))


def json_object(*, finite_only: bool = True):
    return st.dictionaries(st.text(), json(finite_only=finite_only))


@given(value=st.integers(min_value=-(10**9), max_value=10**9))
def test_int(value: int):
    ctx = Context()
    code = str(value)
    assert ctx.eval(code) == value


@given(value=st.floats(allow_infinity=True, allow_nan=True))
def test_float(value: float):
    ctx = Context()
    code = json5.dumps(value).replace("nan", "NaN")
    result = ctx.eval(code)
    assert value == result or (isnan(value) and isnan(result))


@given(value=st.integers(min_value=-(10**100), max_value=10**100))
def test_bigint(value: int):
    ctx = Context()
    code = f"{value}n"
    assert ctx.eval(code) == value


@given(value=json_array(finite_only=False))
def test_json_array(value: list[Any]):
    ctx = Context()
    code = json5.dumps(value).replace("nan", "NaN")
    result = ctx.eval(f"let arr = {code};\narr")
    assert isinstance(result, list)

    diff = DeepDiff(
        value, result, ignore_nan_inequality=True, ignore_numeric_type_changes=True
    )
    assert len(diff.affected_paths) == 0


@given(value=json_object(finite_only=False))
def test_json_object(value: dict[str, Any]):
    ctx = Context()
    code = json5.dumps(value).replace("nan", "NaN")
    result = ctx.eval(f"let obj = {code};\nobj")
    assert isinstance(result, dict)

    diff = DeepDiff(
        value, result, ignore_nan_inequality=True, ignore_numeric_type_changes=True
    )
    assert len(diff.affected_paths) == 0


@given(value=json(finite_only=False))
def test_any_json(value: Any):
    ctx = Context()
    code = json5.dumps(value).replace("nan", "NaN")
    result = ctx.eval(f"let obj = {code};\nobj")
    diff = DeepDiff(
        value, result, ignore_nan_inequality=True, ignore_numeric_type_changes=True
    )
    assert len(diff.affected_paths) == 0


def test_deep_object():
    ctx = Context()
    code = """
let obj = {a:{b:{c:{d:{e:{f:{g:{h:{i:{j:1}}}}}}}}}};
obj
"""
    result = ctx.eval(code)
    diff = DeepDiff(result, json5.loads("{a:{b:{c:{d:{e:{f:{g:{h:{i:{j:1}}}}}}}}}}"))
    assert len(diff.affected_paths) == 0


@pytest.mark.skipif(
    sys.version_info < (3, 11),
    reason="https://docs.python.org/3.13/library/stdtypes.html#integer-string-conversion-length-limitation",
)
def test_integer_string_conversion_length_limitation():
    ctx = Context()
    code = "10n ** 4300n"
    with pytest.raises(ValueError, match="Exceeds the limit"):
        ctx.eval(code)


def test_bigint_in_object():
    ctx = Context()
    assert ctx.eval("({ a: 1n, 1: 2n, 2n: 3n })") == {"a": 1, "1": 2, "2": 3}
    assert ctx.eval("[1, 2, 3n]") == [1, 2, 3]


def test_nan_inf_in_object():
    ctx = Context()
    result = ctx.eval(
        "({ a: NaN, b: Infinity, NaN: NaN, Infinity: Infinity, null: null })"
    )
    assert isinstance(result, dict)
    assert result == pytest.approx(
        {
            "a": float("nan"),
            "b": float("inf"),
            "NaN": float("nan"),
            "Infinity": float("inf"),
            "null": None,
        },
        nan_ok=True,
    )

    result = ctx.eval("[1, 2, NaN, Infinity]")
    assert isinstance(result, list)
    assert result == pytest.approx([1, 2, float("nan"), float("inf")], nan_ok=True)


def test_undefined_in_object():
    ctx = Context()
    assert ctx.eval("({ a: undefined, undefined: undefined })") == {
        "a": Undefined(),
        "undefined": Undefined(),
    }
    assert ctx.eval("[1, 2, undefined]") == [1, 2, Undefined()]
