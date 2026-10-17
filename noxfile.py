import nox


@nox.session(python=["3.11", "3.15", "3.15t", "pypy3.12"], venv_backend="uv")
def test(session: nox.Session) -> None:
    session.install(".[test]")
    session.run("pytest")
