import nox


@nox.session(python=["3.9", "3.13"], venv_backend="uv")
def test(session: nox.Session) -> None:
    session.install(".[test]")
    session.run("pytest")
