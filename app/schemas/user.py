"""User 関連の Pydantic スキーマ"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class UserRead(BaseModel):
    """GET /api/v1/users/me 等のレスポンスで返す User 表現"""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    firebase_uid: str
    email: str
    display_name: str | None
    locale: str
    timezone: str
    current_plan: str
    trial_ends_at: datetime | None
    terms_agreed_at: datetime | None
    terms_version: str | None
    created_at: datetime
    updated_at: datetime


class UserCreateRequest(BaseModel):
    """POST /api/v1/auth/register のリクエストボディ。

    firebase_uid と email は ID Token から取得するので、ボディには含めない。
    """

    display_name: str | None = Field(default=None, max_length=120)
    locale: str = Field(default="ja", max_length=10)
    timezone: str = Field(default="Asia/Tokyo", max_length=64)


class UserTermsAgreeRequest(BaseModel):
    """POST /api/v1/users/me/terms-agreement のリクエストボディ"""

    terms_version: str = Field(min_length=1, max_length=32)


class UserUpdateRequest(BaseModel):
    """PATCH /api/v1/users/me のリクエストボディ。

    すべて任意・指定された項目のみ更新する部分更新（exclude_unset で判定）。
    display_name は null 許容（クリア用途）だが、locale/timezone は DB が
    NOT NULL のため null 指定は 422 で拒否する（未指定＝キー省略とは区別）。
    """

    display_name: str | None = Field(default=None, max_length=120)
    locale: str | None = Field(default=None, max_length=10)
    timezone: str | None = Field(default=None, max_length=64)

    @field_validator("locale", "timezone")
    @classmethod
    def _reject_explicit_null(cls, v: str | None) -> str | None:
        if v is None:
            raise ValueError("null is not allowed; omit the field to leave it unchanged")
        return v
