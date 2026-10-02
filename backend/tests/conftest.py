"""Test isolation.

Two fixtures call ``Base.metadata.drop_all(bind=engine)``. The engine is built
at import time from ``DATABASE_URL``, which points at the real application
database, so running the suite destroyed the live SerpApi response cache and
the api_usage history.

Setting DATABASE_URL here -- before any ``app.*`` module is imported -- routes
the whole suite at a throwaway database. An environment variable takes
precedence over the value in .env, so this wins.
"""
import os
import pathlib

_TEST_DB = pathlib.Path(__file__).resolve().parent / "_test_market_radar.db"
os.environ["DATABASE_URL"] = "sqlite:///" + _TEST_DB.as_posix()

import pytest  # noqa: E402  (must follow the env var assignment)


@pytest.fixture(scope="session", autouse=True)
def guard_against_production_database():
    """Fail loudly rather than drop tables in the application database."""
    from app.database.connection import engine

    url = str(engine.url)
    assert "_test_" in url, (
        "Refusing to run: tests are pointed at " + url +
        ", not an isolated test database."
    )
    yield
    # SQLite keeps the file open through the connection pool, and Windows
    # refuses to unlink an open file, so the pool is disposed first. Without
    # this the throwaway database survived every run.
    engine.dispose()
    try:
        _TEST_DB.unlink()
    except OSError:
        pass
