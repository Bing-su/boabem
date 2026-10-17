from collections.abc import Callable
from typing import Any

import pytest


def test_promise_jobs_run_before_eval_returns(evaluate: Callable[[str], Any]):
    source = """
        globalThis.result = 0;
        Promise.resolve(42).then(value => {
            result = value;
        });
        123;
    """

    assert evaluate(source) == 123
    assert evaluate("result") == 42


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        pytest.param("Promise.resolve(42)", 42, id="number"),
        pytest.param("Promise.resolve({a: [1, 2]})", {"a": [1, 2]}, id="object"),
        pytest.param("Promise.resolve(null)", None, id="null"),
        pytest.param("(async () => 42)()", 42, id="async-function"),
        pytest.param("({a: Promise.resolve(42)})", {"a": 42}, id="nested-promise"),
    ],
)
def test_fulfilled_promise_returns_python_value(
    evaluate: Callable[[str], Any], source: str, expected: Any
):
    assert evaluate(source) == expected


@pytest.mark.parametrize(
    "source",
    [
        pytest.param("Promise.reject(new Error('boom'))", id="error"),
        pytest.param("Promise.reject('boom')", id="string"),
        pytest.param(
            """
            Promise.resolve().then(() => {
                throw new Error('boom');
            });
            """,
            id="throw-in-callback",
        ),
        pytest.param(
            """
            Promise.reject(new Error('boom'));
            123;
            """,
            id="ordinary-return-value",
        ),
        pytest.param(
            """
            Promise.reject(new Error('boom'));
            Promise.resolve(42);
            """,
            id="fulfilled-return-value",
        ),
        pytest.param(
            """
            Promise.reject(new Error('boom'));
            Promise.reject(new Error('second'));
            123;
            """,
            id="multiple-rejections",
        ),
        pytest.param(
            """
            const promise = Promise.reject(new Error('boom'));
            promise.catch(() => 42);
            promise;
            """,
            id="return-original-rejected-promise",
        ),
    ],
)
def test_promise_rejection_raises_and_context_recovers(
    evaluate: Callable[[str], Any], source: str
):
    with pytest.raises(RuntimeError, match="boom"):
        evaluate(source)

    assert evaluate("1 + 1") == 2


@pytest.mark.parametrize(
    "source",
    [
        pytest.param(
            "Promise.reject(new Error('handled')).catch(() => 42)",
            id="immediate-catch",
        ),
        pytest.param(
            """
            const promise = Promise.reject(new Error('handled'));
            Promise.resolve().then(() => promise.catch(() => 42));
            42;
            """,
            id="catch-in-later-job",
        ),
        pytest.param(
            "Promise.allSettled([Promise.reject(new Error('handled'))]).then(() => 42)",
            id="all-settled",
        ),
    ],
)
def test_handled_rejection_is_not_reported(evaluate: Callable[[str], Any], source: str):
    assert evaluate(source) == 42


def test_pending_promise_can_be_resolved_in_later_eval(
    evaluate: Callable[[str], Any],
):
    source = """
        let resolvePromise;
        const pending = new Promise(resolve => {
            resolvePromise = resolve;
        });
        pending;
    """

    with pytest.raises(RuntimeError, match="Promise is still pending"):
        evaluate(source)

    assert evaluate("resolvePromise(42); pending") == 42


def test_throw_drains_jobs_and_rejections(evaluate: Callable[[str], Any]):
    source = """
        globalThis.result = 0;
        Promise.resolve().then(() => {
            result = 42;
        });
        Promise.reject(new Error('discarded'));
        throw new Error('synchronous');
    """

    with pytest.raises(RuntimeError, match="synchronous"):
        evaluate(source)

    assert evaluate("result") == 42
    assert evaluate("1 + 1") == 2


@pytest.mark.parametrize(
    ("value", "message"),
    [
        pytest.param("Symbol('value')", "cannot convert Symbol", id="symbol"),
        pytest.param(
            "new Promise(() => {})", "Promise is still pending", id="pending-promise"
        ),
    ],
)
def test_conversion_error_clears_rejections(
    evaluate: Callable[[str], Any], value: str, message: str
):
    source = f"Promise.reject(new Error('discarded')); {value};"

    with pytest.raises(RuntimeError, match=message):
        evaluate(source)

    assert evaluate("1 + 1") == 2


def test_throwing_getter_drains_jobs_and_rejections(
    evaluate: Callable[[str], Any],
):
    source = """
        globalThis.result = 0;
        ({
            get value() {
                Promise.resolve().then(() => {
                    result = 42;
                    throw new Error('discarded');
                });
                throw new Error('getter');
            }
        });
    """

    with pytest.raises(RuntimeError, match="getter"):
        evaluate(source)

    assert evaluate("result") == 42
    assert evaluate("1 + 1") == 2


def test_getter_rejection_is_reported_in_same_eval(
    evaluate: Callable[[str], Any],
):
    source = """
        ({
            get value() {
                Promise.reject(new Error('getter'));
                return 1;
            }
        });
    """

    with pytest.raises(RuntimeError, match="getter"):
        evaluate(source)

    assert evaluate("1 + 1") == 2


def test_getter_jobs_run_before_returning(evaluate: Callable[[str], Any]):
    source = """
        globalThis.result = 0;
        ({
            get value() {
                Promise.resolve().then(() => {
                    result = 42;
                });
                return 1;
            }
        });
    """

    assert evaluate(source) == {"value": 1}
    assert evaluate("result") == 42


def test_promise_created_by_getter_is_resolved(evaluate: Callable[[str], Any]):
    source = """
        ({
            get value() {
                return Promise.resolve().then(() => 42);
            }
        });
    """

    assert evaluate(source) == {"value": 42}


@pytest.mark.parametrize(
    "source",
    [
        pytest.param("function f() {", id="function-body"),
        pytest.param("'unfinished", id="string-literal"),
        pytest.param("'escape\\", id="escape-sequence"),
    ],
)
def test_unexpected_eof_raises_without_poisoning_context(
    evaluate: Callable[[str], Any], source: str
):
    with pytest.raises(RuntimeError):
        evaluate(source)

    assert evaluate("1 + 1") == 2
