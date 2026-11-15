import pytest
from pydantic import SecretStr

from app.api import ApiConfig
from app.transport import MissingSecret


def test_tokens_are_read_from_the_environment() -> None:
    config = ApiConfig.from_environ({"DEMO_TOKENS": " a , b ,", "ADMIN_TOKEN": "z"})
    assert [token.get_secret_value() for token in config.demo_tokens] == ["a", "b"]
    assert config.admin_token == SecretStr("z")


def test_the_admin_token_is_optional() -> None:
    assert ApiConfig.from_environ({"DEMO_TOKENS": "a"}).admin_token is None


def test_without_demo_tokens_there_is_no_config() -> None:
    with pytest.raises(MissingSecret):
        ApiConfig.from_environ({})


def test_the_config_never_shows_a_token() -> None:
    config = ApiConfig.from_environ({"DEMO_TOKENS": "s3cret", "ADMIN_TOKEN": "adm1n"})
    assert "s3cret" not in repr(config)
    assert "adm1n" not in repr(config)
