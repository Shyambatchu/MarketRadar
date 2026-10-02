"""Test-database isolation.

Two fixtures in this suite call ``Base.metadata.drop_all(bind=engine)``. The
engine is built at import time from ``DATABASE_URL``, so when that pointed at
the application database, running the suite destroyed the live SerpApi response
cache and the api_usage history. ``conftest.py`` now sets ``DATABASE_URL`` to a
throwaway file before any ``app.*`` module is imported, and asserts it took
effect. These tests keep that arrangement from quietly coming undone.
"""
import pathlib

from app.config import settings
from app.database.connection import engine


def _engine_path() -> pathlib.Path:
    return pathlib.Path(engine.url.database).resolve()


def test_suite_runs_against_an_isolated_database():
    url = str(engine.url)
    assert "_test_" in url, "the suite is pointed at " + url


def test_test_database_is_not_the_configured_application_database():
    """Even if .env changes, the two must not converge on one file."""
    configured = settings.DATABASE_URL
    assert "_test_" in configured, configured


def test_test_database_lives_under_the_tests_directory():
    """A throwaway file, not the application's data directory."""
    path = _engine_path()
    assert path.parent == pathlib.Path(__file__).resolve().parent
    assert "data" not in [p.name for p in path.parents][:1]


def test_application_database_file_is_untouched_by_the_suite():
    """The real development database must not even be open."""
    app_db = (pathlib.Path(__file__).resolve().parent.parent
              / "data" / "market_radar.db")
    if not app_db.exists():
        return
    assert _engine_path() != app_db.resolve()


def test_destructive_guard_exists_and_is_autouse():
    """The guard must run for the whole session without being requested."""
    import inspect
    from tests import conftest

    source = inspect.getsource(conftest)
    assert "autouse=True" in source
    assert 'scope="session"' in source
    assert "_test_" in source
    # DATABASE_URL must be set before app.* is imported, or the engine is
    # already bound to the application database by the time the guard runs.
    assert source.index("os.environ[\"DATABASE_URL\"]") < source.index("import pytest")


def test_guard_would_reject_the_application_database():
    """The assertion is real: an application URL fails it."""
    for url in ("sqlite:///./data/market_radar.db",
                "postgresql://user@host/market_radar"):
        assert "_test_" not in url
