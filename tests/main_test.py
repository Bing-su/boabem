import json
import sys
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from pathlib import Path
from typing import Any

import pytest

from boabem import Context, Undefined


def test_banana():
    ctx = Context()
    assert ctx.eval('"b" + "a" + +"a" + "a"') == "baNaNa"


@pytest.mark.parametrize(
    ("code", "expect"),
    [
        (
            "(![] + [])[+[]] + (![] + [])[+!+[]] + ([![]] + [][[]])[+!+[] + [+[]]] + (![] + [])[!+[] + !+[]]",
            "fail",
        ),
        ("10n ** 100n", 10**100),
        ("-(10n ** 100n)", -(10**100)),
        ('parseInt("f*ck", 16)', 15),
        ('parseInt("Infinity", 35)', 1201203301724),
        ("parseInt(null, 24)", 23),
        ("(true + true) * (true + true) - true", 3),
        ("10000000000000000 + 1.1", 10000000000000002),
        ("'3' + 1", "31"),
        ("{} + []", 0),
        ("({ [{}]: { [{}]: {} } }[{}][{}])", {}),
        ("[...[...'...']].length", 3),
        ("[10, 1, 3].sort()", [1, 10, 3]),
    ],
)
def test_equal(code: str, expect: Any):
    ctx = Context()
    assert ctx.eval(code) == expect


@pytest.mark.parametrize(
    ("code", "expect"),
    [
        ("true == []", False),
        ("true == ![]", False),
        ("false == []", True),
        ("false == ![]", True),
        ("![]", False),
        ('!!"false" == !!"true"', True),
        ('!!"false" === !!"true"', True),
        ("Object.is(NaN, NaN)", True),
        ("NaN === NaN", False),
        ("Object.is(-0, 0)", False),
        ("-0 === 0", True),
        ("[[[[[[]]]]]] == ''", True),
        ("[[[[[[ undefined ]]]]]] == 0", True),
        ("1 < 2 < 3", True),
        ("3 > 2 > 1", False),
        ("(1).__proto__.__proto__.__proto__", None),
    ],
)
def test_is(code: str, expect: Any):
    ctx = Context()
    assert ctx.eval(code) is expect


def test_boolean_logic():
    ctx = Context()
    assert ctx.eval("true && false") is False
    assert ctx.eval("true || false") is True
    assert ctx.eval("!false") is True


def test_string_concat_unicode():
    ctx = Context()
    result = ctx.eval("'한글' + '😊'")
    assert result == "한글😊"


def test_null_and_undefined_are_distinct():
    ctx = Context()
    js_null = ctx.eval("null")
    js_undef = ctx.eval("undefined")

    assert js_null is None
    assert js_undef != js_null
    assert isinstance(js_undef, Undefined)


def test_exception_propagation():
    ctx = Context()
    with pytest.raises(RuntimeError, match="boom"):
        ctx.eval("throw new Error('boom')")


def test_context_state_persists_between_evals():
    ctx = Context()
    ctx.eval("var x = 41")
    assert ctx.eval("x + 1") == 42


def test_eval_from_filepath(tmp_path: Path):
    p = tmp_path / "script.js"
    p.write_text("1 + 2", encoding="utf-8")

    ctx = Context()
    result = ctx.eval_from_filepath(p)
    assert result == 3

    p.write_text("3 + 4", encoding="utf-8")

    ctx = Context()
    result = ctx.eval_from_filepath(str(p))
    assert result == 7


def test_nan_and_infinity():
    ctx = Context()
    assert ctx.eval("typeof NaN") == "number"
    assert ctx.eval("typeof Infinity") == "number"
    assert ctx.eval("Number.isNaN(NaN)") is True
    assert ctx.eval("isNaN(0/0)") is True
    assert ctx.eval("isFinite(Infinity)") is False
    assert ctx.eval("isFinite(1/0)") is False


def test_syntax_error_raises():
    ctx = Context()
    with pytest.raises(RuntimeError, match="SyntaxError"):
        ctx.eval("function(")


def test_bigint_number_mixing_raises():
    ctx = Context()
    with pytest.raises(RuntimeError, match="BigInt"):
        ctx.eval("1n + 1")


def test_template_literals():
    ctx = Context()
    result = ctx.eval("`Hello ${21 + 21}`")
    assert result == "Hello 42"


def test_function_definition_and_call_across_evals():
    ctx = Context()
    ctx.eval("function inc(x) { return x + 1 }")
    assert ctx.eval("inc(41)") == 42
    assert ctx.eval('inc("41")') == "411"


def test_try_catch_returns_message():
    ctx = Context()
    result = ctx.eval("try { throw new Error('boom') } catch (e) { e.message }")
    assert result == "boom"


def test_eval_from_bytes_supports_utf8():
    ctx = Context()
    code_str = "'A' + 'B'"
    res = ctx.eval_from_bytes(code_str)
    assert res == "AB"


def test_multiline_script():
    ctx = Context()
    result = ctx.eval("const a = 5;\nconst b = 7;\na * b")
    assert result == 35


def test_array_length():
    ctx = Context()
    assert ctx.eval("[1,2,3,4].length") == 4


def test_json_stringify_roundtrip():
    ctx = Context()
    js = ctx.eval("JSON.stringify({a:1, b:[2,3], c:'x'})")
    assert js == '{"a":1,"b":[2,3],"c":"x"}'
    obj = json.loads(js)
    assert obj == {"a": 1, "b": [2, 3], "c": "x"}


def test_bigint_loose_and_strict_equality():
    ctx = Context()
    # 느슨한 동등 비교는 true, 엄격한 동등 비교는 false
    assert ctx.eval("1n == 1") is True
    assert ctx.eval("1n === 1") is False


def test_truthiness():
    ctx = Context()
    assert ctx.eval("Boolean({})") is True
    assert ctx.eval("Boolean([])") is True
    assert ctx.eval("Boolean(0)") is False
    assert ctx.eval("Boolean('')") is False


def test_reference_error_for_undefined_identifier():
    ctx = Context()
    # 선언되지 않은 식별자 접근은 ReferenceError
    with pytest.raises(RuntimeError, match="ReferenceError"):
        ctx.eval("notDeclared + 1")


def test_typeof_undeclared_identifier():
    ctx = Context()
    # typeof undeclared 는 예외가 아니라 'undefined'
    assert ctx.eval("typeof notDeclared") == "undefined"


def test_strict_mode_assignment_error():
    ctx = Context()
    with pytest.raises(RuntimeError):
        ctx.eval("'use strict'; x = 3.14")  # 선언 없이 할당 금지


def test_regexp_test_and_exec():
    ctx = Context()
    assert ctx.eval("/foo/.test('foobar')") is True
    assert ctx.eval("/bar/.test('baz')") is False


def test_date_to_string_typeof():
    ctx = Context()
    # Date 객체의 typeof는 'object'이고 toString이 존재
    assert ctx.eval("typeof new Date()") == "object"
    assert ctx.eval("new Date(0).toString()") == "Thu Jan 01 1970 09:00:00 GMT+0900"


def test_destructuring_and_spread():
    ctx = Context()
    assert ctx.eval("let {a,b} = {a:1,b:2}; a+b") == 3
    assert ctx.eval("let arr = [1,2,3]; Math.max(...arr)") == 3


def test_parse_int_float_and_math():
    ctx = Context()
    assert ctx.eval("parseInt('10', 10)") == 10
    assert ctx.eval("parseFloat('3.14')") == 3.14
    assert ctx.eval("Math.min(5, -1, 3)") == -1


def test_bitwise_operations():
    ctx = Context()
    assert ctx.eval("5 & 3") == (5 & 3)
    assert ctx.eval("5 | 2") == (5 | 2)
    assert ctx.eval("5 ^ 1") == (5 ^ 1)
    assert ctx.eval("~0") == (~0)
    assert ctx.eval("1 << 5") == (1 << 5)
    assert ctx.eval("(32 >> 2)") == (32 >> 2)
    assert ctx.eval("(-1 >>> 1) >= 0") is True  # JS 무부호 시프트 결과는 32-bit 양수


def test_short_circuiting():
    ctx = Context()
    assert ctx.eval("false && (x=1)") is False
    assert ctx.eval("true || (x=1)") is True


def test_json_parse_roundtrip():
    ctx = Context()
    code = """JSON.parse('{"a":1}').a"""
    assert ctx.eval(code) == 1


def test_unicode_escape_in_string():
    ctx = Context()
    assert ctx.eval("'\ud55c\uae00' + '!' ") == "한글!"


def test_remainder_negative():
    ctx = Context()
    # JS의 나머지 연산은 피제수의 부호를 따름(-5 % 2 == -1)
    assert ctx.eval("-5 % 2") == -1


def test_bigint_division_truncates():
    ctx = Context()
    # BigInt 나눗셈은 소수 버림
    assert ctx.eval("5n / 2n") == 2


def test_delete_property():
    ctx = Context()
    assert ctx.eval("let o={a:1,b:2}; delete o.a; 'a' in o") is False


def test_typeof_null_and_function_length():
    ctx = Context()
    assert ctx.eval("typeof null") == "object"
    assert ctx.eval("(function(a,b){}).length === 2") is True


def test_arrow_function_call():
    ctx = Context()
    assert ctx.eval("(() => 42)()") == 42


def test_const_reassignment_throws():
    ctx = Context()
    with pytest.raises(RuntimeError):
        ctx.eval("const a=1; a=2")


def test_bigint_unary_plus_throws_and_to_string_radix():
    ctx = Context()
    with pytest.raises(RuntimeError):
        ctx.eval("+1n")
    assert ctx.eval("(255n).toString(16)") == "ff"


def test_map_and_set_size():
    ctx = Context()
    assert ctx.eval("new Map([[1,2],[3,4]]).size") == 2
    assert ctx.eval("new Set([1,1,2]).size") == 2


def test_date_utc_epoch():
    ctx = Context()
    assert ctx.eval("Date.UTC(1970,0,1)") == 0


def test_encode_decode_uri_component():
    ctx = Context()
    assert ctx.eval("decodeURIComponent(encodeURIComponent('한글'))") == "한글"


def test_switch_and_for_sum_via_iife():
    ctx = Context()
    assert (
        ctx.eval(
            "(() => { const x=2; switch(x){case 1: return 'foo'; case 2: return 'bar'; default: return 'baz'; } })()"
        )
        == "bar"
    )
    assert (
        ctx.eval("(() => { let s=0; for(let i=1;i<=5;i++){ s+=i } return s })()") == 15
    )


def test_number_coercion_and_parse_int():
    ctx = Context()
    assert ctx.eval("Number('  10  ')") == 10
    assert ctx.eval("parseInt('08', 10)") == 8


def test_delete_non_configurable_property_returns_false():
    ctx = Context()
    assert ctx.eval("delete Math.PI") is False


def test_weird_equality_cases():
    ctx = Context()
    assert ctx.eval("[] == ![]") is True
    assert ctx.eval("0 == false") is True
    assert ctx.eval("0 === false") is False


def test_number_is_integer():
    ctx = Context()
    assert ctx.eval("Number.isInteger(3.0)") is True
    assert ctx.eval("Number.isInteger(3.1)") is False


def test_cannot_convert_symbol():
    ctx = Context()
    with pytest.raises(RuntimeError, match="TypeError: cannot convert Symbol"):
        ctx.eval("Symbol('a')")


def test_undefined_is_same():
    ctx = Context()
    undefined1 = ctx.eval("undefined")
    undefined2 = ctx.eval("")
    assert isinstance(undefined1, Undefined)
    assert isinstance(undefined2, Undefined)

    assert ctx.eval("undefined == undefined") is True
    assert ctx.eval("undefined === undefined") is True
    assert undefined1 == undefined2

    assert ctx.eval("Object.is(undefined, undefined)") is True
    assert undefined1 is not undefined2


def test_thread_pool():
    ctx = Context()
    with ThreadPoolExecutor() as executor:
        future = executor.submit(ctx.eval, "1 + 1")

    # pyo3_runtime.PanicException
    with pytest.raises(BaseException, match="unsendable"):
        future.result()


def test_process_pool():
    ctx = Context()
    with ProcessPoolExecutor() as executor:
        future = executor.submit(ctx.eval, "1 + 1")

    with pytest.raises(TypeError, match="cannot pickle"):
        future.result()


@pytest.mark.skipif(
    sys.version_info < (3, 11),
    reason="https://docs.python.org/3.13/library/stdtypes.html#integer-string-conversion-length-limitation",
)
def test_integer_string_conversion_length_limitation():
    ctx = Context()
    code = "10n ** 4300n"
    with pytest.raises(ValueError, match="Exceeds the limit"):
        ctx.eval(code)
