# boabem

Boabem (/po.a.bɛm/, 'bo-ah-bem') is a Python binding for the Rust crate [Boa](https://github.com/boa-dev/boa) — an embeddable JavaScript engine. The current version uses Boa 0.22.

Run small bits of JavaScript from Python, get back plain Python values, and keep state across evaluations.

## Quick start

```python
from boabem import Context, undefined

ctx = Context()
ctx.eval("var x = 41")
print(ctx.eval("x + 1"))  # 42

print(ctx.eval("'A' + 'B'"))  # 'AB'
print(ctx.eval("[1,2,3].length"))  # 3
print(ctx.eval("JSON.stringify({a:1})"))  # '{"a":1}'
assert ctx.eval("({answer: 42, items: [1, 2, 3]})") == {
    "answer": 42,
    "items": [1, 2, 3],
}
assert ctx.eval("undefined") == undefined
```

Load code from a file:

```python
from pathlib import Path
from boabem import Context

ctx = Context()
result = ctx.eval_from_filepath(Path("script.js"))
```

## API

| API                                                                  | Behavior                                                                 |
| -------------------------------------------------------------------- | ------------------------------------------------------------------------ |
| `Context()`                                                          | Create an isolated JavaScript context                                    |
| `Context.eval(source: str) -> Any`                                   | Evaluate JavaScript source and convert the result to Python              |
| `Context.eval_from_bytes(source: str) -> Any`                        | Same behavior as `eval`; accepts a Python `str`, despite the method name |
| `Context.eval_from_filepath(source: str \| os.PathLike[str]) -> Any` | Read and evaluate a JavaScript file                                      |
| `Undefined()`                                                        | Create a value representing JavaScript `undefined`                       |
| `undefined`                                                          | Exported `Undefined` instance for equality comparisons                   |
| `PanicException`                                                     | Rust panic exception; inherits from `BaseException`                      |
| `__version__`                                                        | Package version string                                                   |

State persists within a single Context instance between calls. Each Context is isolated from others.

## Promises and async functions

All three evaluation methods run queued Promise jobs before returning. For example:

```python
ctx = Context()
assert ctx.eval("Promise.resolve(42).then(value => value + 1)") == 43
assert ctx.eval("Promise.reject(new Error('handled')).catch(() => 'ok')") == "ok"
```

| Promise state after running jobs | Python result                                                        |
| -------------------------------- | -------------------------------------------------------------------- |
| Fulfilled                        | The fulfillment value, converted using the value mapping below       |
| Rejected                         | `RuntimeError` with the rejection reason                             |
| Still pending                    | `RuntimeError`; evaluation does not wait indefinitely for resolution |

Unhandled rejections raise `RuntimeError` even when the script returns an ordinary value.
Rejections handled by `.catch()` before the jobs finish do not raise on their own.
Queued jobs also run when the script throws; the script's exception takes precedence.
Network requests made by `fetch()` run synchronously while the job queue is processed.

## JavaScript runtime

| Feature    | Behavior                                                                                                                    |
| ---------- | --------------------------------------------------------------------------------------------------------------------------- |
| `console`  | Registered in every context through Boa's console extension                                                                 |
| `fetch()`  | Registered with a blocking Reqwest fetcher; consume results with Promises or `async`/`await` inside an async function       |
| `Intl`     | Built with bundled locale data; includes number/date formatting, collation, plural rules, list formatting, and segmentation |
| `Temporal` | Supports date/time arithmetic, nanosecond instants, and time zones                                                          |
| `RegExp`   | Supports Unicode property escapes, `v` sets, lookbehind, named captures, match indices, and `RegExp.escape()`               |

```python
from boabem import Context

ctx = Context()
assert ctx.eval("new Intl.NumberFormat('en-US').format(1234)") == "1,234"
assert (
    ctx.eval("Temporal.PlainDate.from('2024-02-29').add({days: 1}).toString()")
    == "2024-03-01"
)
assert ctx.eval(r"/(?<=price=)\d+/.exec('price=42;')[0]") == "42"
```

JavaScript compatibility follows Boa's implementation. The tests record known Boa 0.22 limitations: currency/percent number formatting, `NumberFormat.formatToParts()`, individual date field widths, `Intl.RelativeTimeFormat`, and `Intl.DisplayNames`.

## Value mapping (JS -> Python)

| JavaScript value               | Python value                                                                |
| ------------------------------ | --------------------------------------------------------------------------- |
| `undefined`                    | `boabem.Undefined` instance                                                 |
| `null`                         | `None`                                                                      |
| Boolean                        | `bool`                                                                      |
| Number                         | `int` or `float`, depending on Boa's internal representation                |
| `NaN`, `Infinity`, `-Infinity` | Corresponding Python `float`                                                |
| BigInt                         | Arbitrary-precision `int`                                                   |
| String                         | `str`                                                                       |
| Array                          | `list`                                                                      |
| Object                         | `dict` with string keys                                                     |
| Promise                        | Converted fulfillment value; pending/rejected Promises raise `RuntimeError` |
| Symbol                         | `RuntimeError`                                                              |

Notes:

- Each JavaScript `undefined` converts to a distinct Python object that compares equal to `undefined` and other `Undefined` instances. Use `==`, rather than `is`, to compare these values.
- `str(undefined)` is `"undefined"`; `repr(undefined)` is `"Undefined"`.

### Object/Array conversion details

When converting composite values (JavaScript Objects and Arrays) to Python `dict`/`list`, elements are converted recursively with a few caveats:

- BigInt inside Objects/Arrays is converted to Python `int`.
  - Examples: `({ a: 1n, 1: 2n, 2n: 3n }) -> {"a": 1, "1": 2, "2": 3}` and `[1, 2, 3n] -> [1, 2, 3]`.
- `NaN` and `±Infinity` inside Objects/Arrays are preserved as Python floats (`float('nan')` / `float('inf')`).
  - Examples: `({ a: NaN, b: Infinity }) -> {"a": nan, "b": inf}` and `[1, 2, NaN, Infinity] -> [1, 2, nan, inf]`.
- `undefined` inside Objects/Arrays is converted to `boabem.Undefined`.

Additional notes:

- JavaScript object property keys are coerced to strings during conversion; for example, a `2n` property name becomes the Python key `"2"`.

These conversions also apply to top-level values. Nested Promises are unwrapped recursively. Returned containers are Python values, rather than live JavaScript object handles.

## Threading and processes

Context is not thread-sendable or picklable:

- Do not move or use a Context across threads (ThreadPoolExecutor will fail).
- Do not send a Context to another process (cannot pickle).
- Create and use a Context only in the thread where it was created.

If you try to use a Context across threads, you'll get a Rust panic surfaced as `pyo3_runtime.PanicException` (exposed as `boabem.PanicException`).

## Errors

| Failure                                                   | Python exception                                                |
| --------------------------------------------------------- | --------------------------------------------------------------- |
| JavaScript exception, syntax error, or conversion failure | `RuntimeError` containing the JavaScript error message          |
| Rejected or still-pending Promise                         | `RuntimeError`                                                  |
| File access failure in `eval_from_filepath`               | Corresponding Python I/O exception, such as `FileNotFoundError` |
| Using a context from another thread                       | `PanicException`                                                |

## Development

From a local checkout, with Rust and `uv` installed:

```sh
uv venv --python 3.11
uv pip install '.[test]'
uv run --no-project pytest
```

Reinstall the package after changing Rust code to rebuild the extension. To run the configured interpreter matrix:

```sh
uvx nox -s test
```

Nox tests Python 3.11, Python 3.15, free-threaded Python 3.15 (`3.15t`), and PyPy 3.12. CI runs this matrix on Linux (x86_64 and ARM64), macOS, and Windows. Tests cover value conversion, context state, threading/process restrictions, Promises, local HTTP fetches, `Intl`, `Temporal`, and regular expressions; known engine limitations are marked as expected failures.

## License

Licensed under the [Blue Oak Model License 1.0.0](LICENSE.md) (`BlueOak-1.0.0`).
