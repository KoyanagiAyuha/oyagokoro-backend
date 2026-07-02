"""app/auth/ の単体テスト"""

from unittest.mock import patch

import pytest

from app.auth.exceptions import (
    FirebaseNotConfiguredError,
    MockTokenError,
)
from app.auth.mock import verify_mock_token


class TestMockToken:
    def test_valid_mock_token(self) -> None:
        payload = verify_mock_token("mock:uid123:user@example.com")
        assert payload["uid"] == "uid123"
        assert payload["email"] == "user@example.com"
        assert payload["email_verified"] is True

    def test_invalid_prefix(self) -> None:
        with pytest.raises(MockTokenError):
            verify_mock_token("invalid:uid:email")

    def test_missing_email(self) -> None:
        with pytest.raises(MockTokenError):
            verify_mock_token("mock:uid:")

    def test_too_few_parts(self) -> None:
        with pytest.raises(MockTokenError):
            verify_mock_token("mock:uid")


class TestVerifyDispatcher:
    """verify_id_token_or_mock の分岐テスト"""

    def test_mock_path_in_local(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """ローカル + USE_AUTH_MOCK=true ならモック検証パス"""
        from app.auth import verify_id_token_or_mock
        from app.settings import settings

        monkeypatch.setattr(settings, "use_auth_mock", True)
        monkeypatch.setattr(settings, "app_env", "local")

        payload = verify_id_token_or_mock("mock:testuid:test@example.com")
        assert payload["uid"] == "testuid"

    def test_production_forces_real_verify(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """APP_ENV=production では USE_AUTH_MOCK=true でも実検証に行く"""
        from app.auth import verify_id_token_or_mock
        from app.settings import settings

        monkeypatch.setattr(settings, "use_auth_mock", True)
        monkeypatch.setattr(settings, "app_env", "production")

        # 実 Firebase は呼ばずに verify_id_token をパッチして呼ばれることを確認
        with patch("app.auth.verify_id_token") as mock_verify:
            mock_verify.return_value = {"uid": "real_uid"}
            payload = verify_id_token_or_mock("mock:testuid:test@example.com")
            mock_verify.assert_called_once_with("mock:testuid:test@example.com")
            assert payload["uid"] == "real_uid"


class TestFirebaseInit:
    """Firebase 初期化エラーパス"""

    def test_no_credentials_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """設定なしの場合は FirebaseNotConfiguredError"""
        from app.auth import firebase as fb_module
        from app.settings import settings

        # シングルトンをリセット
        monkeypatch.setattr(fb_module, "_app", None)
        monkeypatch.setattr(settings, "firebase_credentials_file", None)
        monkeypatch.setattr(settings, "firebase_project_id", None)
        monkeypatch.setattr(settings, "firebase_private_key", None)
        monkeypatch.setattr(settings, "firebase_client_email", None)

        with pytest.raises(FirebaseNotConfiguredError):
            fb_module._build_credentials()
