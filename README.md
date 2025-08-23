# boabem

Boabem (/po.a.bɛm/, 'bo-ah-bem') is a Python binding for the Rust crate [boa](https://github.com/boa-dev/boa) — an embeddable JavaScript engine.

Run small bits of JavaScript from Python, get back plain Python values, and keep state across evaluations.

## Install

Python 3.9+ is required.

- If a prebuilt wheel is available for your platform:
  - pip install boabem
- Otherwise, build from source.

## Quick start

```python
from boabem import Context

ctx = Context()
ctx.eval("var x = 41")
print(ctx.eval("x + 1"))  # 42

print(ctx.eval("'A' + 'B'"))         # 'AB'
print(ctx.eval("[1,2,3].length"))    # 3
print(ctx.eval("JSON.stringify({a:1})"))  # '{"a":1}'
```

Load code from a file:

```python
from pathlib import Path
from boabem import Context

ctx = Context()
result = ctx.eval_from_filepath(Path("script.js"))
```

## API

- boabem.Context
  - eval(source: str) -> Any
  - eval_from_bytes(source: str) -> Any (same behavior as eval)
  - eval_from_filepath(path: str | os.PathLike[str]) -> Any
- boabem.PanicException
  - Exception class exposed for Rust panics (e.g., attempting to use a Context across threads).
- boabem.Undefined
  - Sentinel type representing JavaScript `undefined`.
  - String representation: "Undefined".

State persists within a single Context instance between calls. Each Context is isolated from others.

## Value mapping (JS -> Python)

- undefined -> boabem.Undefined
- null -> None
- boolean -> bool
- number -> float (NaN/Infinity preserved as float("nan")/float("inf"))
- BigInt -> int
- string -> str
- Array -> list
- Object -> dict

Notes:

- Some JS values (e.g., Symbol) cannot be converted and will raise an error.
- Each `undefined` you get back is a distinct Python object, but compares equal to another `Undefined`.

### Object/Array conversion details

When converting composite values (JavaScript Objects and Arrays) to Python `dict`/`list`, elements are converted recursively with a few caveats:

- BigInt inside Objects/Arrays is converted to Python `int`.
  - Examples: `({ a: 1n, 1: 2n, 2n: 3n }) -> {"a": 1, "1": 2, "2": 3}` and `[1, 2, 3n] -> [1, 2, 3]`.
- `NaN` and `±Infinity` inside Objects/Arrays are preserved as Python floats (`float('nan')` / `float('inf')`).
  - Examples: `({ a: NaN, b: Infinity }) -> {"a": nan, "b": inf}` and `[1, 2, NaN, Infinity] -> [1, 2, nan, inf]`.
- `undefined` inside Objects/Arrays is converted to `boabem.Undefined`.

Additional notes:

- JavaScript object property keys are coerced to strings during conversion; for example, a `2n` property name becomes the Python key `"2"`.

Note: Top-level primitives are still mapped as documented above (e.g., `10n` -> `int`, `NaN`/`Infinity` -> `float('nan')`/`float('inf')`). The special rules here apply only to values nested within Objects/Arrays.

## Threading and processes

Context is not thread-sendable or picklable:

- Do not move or use a Context across threads (ThreadPoolExecutor will fail).
- Do not send a Context to another process (cannot pickle).
- Create and use a Context only in the thread where it was created.

If you try to use a Context across threads, you'll get a Rust panic surfaced as `pyo3_runtime.PanicException` (exposed as `boabem.PanicException`).

## Errors

- JavaScript exceptions (e.g., `throw new Error('boom')`) raise RuntimeError with the JS message.
- Syntax/Reference/Type errors surface as RuntimeError messages (e.g., "SyntaxError", "ReferenceError").

## License

Dual-licensed under MIT or Apache-2.0.
