import nox


@nox.session(python=["3.9", "3.14", "3.14t"], venv_backend="uv")
def test(session: nox.Session) -> None:
    session.install(".[test]")
    session.run("pytest")
