import pytest

from app.settings import Settings


def test_default_use_auth_mock_is_false(monkeypatch: pytest.MonkeyPatch) -> None:
    """USE_AUTH_MOCK を設定しない場合、デフォルトで False になることを確認。"""
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test")
    monkeypatch.setenv("APP_ENV", "local")
    monkeypatch.delenv("USE_AUTH_MOCK", raising=False)

    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert s.use_auth_mock is False


def test_use_auth_mock_can_be_true_in_local(monkeypatch: pytest.MonkeyPatch) -> None:
    """APP_ENV=local かつ USE_AUTH_MOCK=true の場合、True になることを確認。"""
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test")
    monkeypatch.setenv("APP_ENV", "local")
    monkeypatch.setenv("USE_AUTH_MOCK", "true")

    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert s.use_auth_mock is True


def test_use_auth_mock_forced_false_in_production(monkeypatch: pytest.MonkeyPatch) -> None:
    """APP_ENV=production の場合、USE_AUTH_MOCK=true でも強制的に False になることを確認（多重防御）。"""
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test")
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("USE_AUTH_MOCK", "true")

    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert s.use_auth_mock is False
