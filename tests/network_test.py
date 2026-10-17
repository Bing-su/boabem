from collections.abc import Callable
from typing import Any

import pytest
from pytest_httpserver import HTTPServer


def test_fetch_basic(network_evaluate: Callable[[str], Any], httpserver: HTTPServer):
    httpserver.expect_oneshot_request("/", method="GET").respond_with_data("ok")
    url = httpserver.url_for("/")
    source = f"""
        const textPromise = fetch('{url}').then(response => response.text());
        textPromise.then(text => [text, textPromise instanceof Promise]);
    """

    assert network_evaluate(source) == ["ok", True]


@pytest.mark.parametrize(
    "response",
    [
        pytest.param(
            b"HTTP/1.1 200 OK\r\nContent-Length:",
            id="headers",
        ),
        pytest.param(
            b"HTTP/1.1 200 OK\r\nContent-Length: 10\r\nConnection: close\r\n\r\nabc",
            id="fixed-length-body",
        ),
        pytest.param(
            b"HTTP/1.1 200 OK\r\n"
            b"Transfer-Encoding: chunked\r\n"
            b"Connection: close\r\n"
            b"\r\n"
            b"5\r\nab",
            id="chunked-body",
        ),
    ],
)
def test_fetch_eof_rejection_raises(
    network_evaluate: Callable[[str], Any],
    raw_http_response: Callable[[bytes], str],
    response: bytes,
):
    url = raw_http_response(response)
    source = f"""
        fetch('{url}');
        123;
    """

    with pytest.raises(RuntimeError, match=r"^Error:"):
        network_evaluate(source)


def test_fetch_error_can_be_caught(
    network_evaluate: Callable[[str], Any], raw_http_response: Callable[[bytes], str]
):
    url = raw_http_response(b"HTTP/1.1 200 OK\r\nContent-Length:")
    source = f"fetch('{url}').catch(() => 'handled')"

    assert network_evaluate(source) == "handled"
