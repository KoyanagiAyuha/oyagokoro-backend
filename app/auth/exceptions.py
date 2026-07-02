"""認証関連の例外定義"""


class InvalidTokenError(Exception):
    """ID Token の検証に失敗したとき"""


class FirebaseNotConfiguredError(RuntimeError):
    """Firebase の認証情報が設定されていないとき"""


class MockTokenError(Exception):
    """モックトークンの形式が不正なとき"""
