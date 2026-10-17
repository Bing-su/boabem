from collections.abc import Callable, Iterator
from concurrent.futures import ProcessPoolExecutor
from functools import partial
from multiprocessing import get_context
from pathlib import Path
from socket import SHUT_RDWR
from typing import Any

import pytest
from pytest_httpserver import HTTPServer
from werkzeug import Request, Response

from boabem import Context

EVALUATION_METHODS = ("eval", "eval_from_bytes", "eval_from_filepath")


def _evaluate_source(ctx: Context, method: str, path: Path, source: str) -> Any:
    if method == "eval_from_filepath":
        path.write_text(source, encoding="utf-8")
        return ctx.eval_from_filepath(path)
    return getattr(ctx, method)(source)


def _evaluate_with_recovery_check(method: str, path: Path, source: str) -> Any:
    ctx = Context()
    try:
        return _evaluate_source(ctx, method, path, source)
    finally:
        # Verify recovery in the same context even when a network operation fails.
        assert ctx.eval("1 + 1") == 2


@pytest.fixture(params=EVALUATION_METHODS)
def evaluate(request: pytest.FixtureRequest, tmp_path: Path) -> Callable[[str], Any]:
    return partial(_evaluate_source, Context(), request.param, tmp_path / "script.js")


@pytest.fixture(params=EVALUATION_METHODS)
def network_evaluate(
    request: pytest.FixtureRequest, tmp_path: Path, httpserver: HTTPServer
) -> Iterator[Callable[[str], Any]]:
    evaluate_in_worker = partial(
        _evaluate_with_recovery_check, request.param, tmp_path / "script.js"
    )
    # Keep Rust's blocking eval in another process so the HTTP server can acquire the GIL.
    with ProcessPoolExecutor(
        max_workers=1, mp_context=get_context("spawn")
    ) as executor:

        def run(source: str) -> Any:
            future = executor.submit(evaluate_in_worker, source)
            return future.result(timeout=15)

        yield run

    httpserver.check()
    assert httpserver.log, "The client did not reach the HTTP server"


@pytest.fixture
def raw_http_response(httpserver: HTTPServer) -> Callable[[bytes], str]:
    def respond_with(response: bytes) -> str:
        def handler(request: Request) -> Response:
            # Bypass HTTP framing only to reproduce malformed or truncated responses.
            connection = request.environ["werkzeug.socket"]
            connection.sendall(response)
            connection.shutdown(SHUT_RDWR)
            return Response()

        httpserver.expect_oneshot_request("/", method="GET").respond_with_handler(
            handler
        )
        return httpserver.url_for("/")

    return respond_with
