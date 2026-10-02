"""The demo seeder writes only to its own file and produces the intended history."""
import pathlib
import sqlite3
import subprocess
import sys

BACKEND = pathlib.Path(__file__).resolve().parent.parent
SCRIPT = BACKEND / "scripts" / "seed_demo_data.py"


def run(*args):
    return subprocess.run([sys.executable, str(SCRIPT), *args], cwd=BACKEND,
                          capture_output=True, text=True)


def test_refuses_the_application_database():
    result = run("--database", str(BACKEND / "data" / "market_radar.db"))
    assert result.returncode != 0
    assert "Refusing" in (result.stdout + result.stderr)


def test_seeds_a_separate_file_and_will_not_overwrite_it(tmp_path):
    target = tmp_path / "demo.db"
    assert run("--database", str(target)).returncode == 0

    con = sqlite3.connect(target)
    try:
        assert con.execute("select count(*) from merchants").fetchone()[0] == 7
        locations = {r[0] for r in con.execute(
            "select distinct location_resolved from competitor_observations")}
        assert locations == {"Sample City (demo data)"}
        domains = {r[0] for r in con.execute(
            "select normalized_domain from merchants where normalized_domain is not null")}
        assert all(d.endswith(".example") for d in domains)
    finally:
        con.close()

    again = run("--database", str(target))
    assert again.returncode != 0 and "--reset" in (again.stdout + again.stderr)
    assert run("--database", str(target), "--reset").returncode == 0
