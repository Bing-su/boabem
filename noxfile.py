import nox


@nox.session(python=["3.10", "3.14", "3.14t", "pypy3.11"], venv_backend="uv")
def test(session: nox.Session) -> None:
    session.install(".[test]")
    session.run("pytest")
