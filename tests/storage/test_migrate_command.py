import psycopg
import pytest

from app.storage.__main__ import main
from app.transport import MissingSecret


def applied(dsn: str) -> list[str]:
    with psycopg.connect(dsn) as conn:
        return [row[0] for row in conn.execute("SELECT name FROM schema_migrations ORDER BY name")]


def test_the_command_applies_the_migrations_and_a_second_run_changes_nothing(
    postgres_dsn: str, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main({"DATABASE_URL": postgres_dsn}) == 0
    first = applied(postgres_dsn)
    assert first and first[0] == "0001_init.sql"
    assert f"{len(first)} migrations" in capsys.readouterr().out

    assert main({"DATABASE_URL": postgres_dsn}) == 0
    assert applied(postgres_dsn) == first


def test_the_command_names_the_missing_variable_and_never_prints_a_value(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(MissingSecret) as raised:
        main({})
    assert "DATABASE_URL" in str(raised.value)
    assert capsys.readouterr().out == ""
