"""POST /api/v1/auth/register の冪等 upsert テスト"""

import asyncio
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.models.user import User


@pytest.mark.asyncio
async def test_post_auth_register_creates_new_user(app_client, db_session) -> None:
    uid = f"new_uid_{uuid4().hex[:8]}"
    email = f"{uid}@example.com"
    token = f"mock:{uid}:{email}"

    response = await app_client.post(
        "/api/v1/auth/register",
        headers={"Authorization": f"Bearer {token}"},
        json={"display_name": "New User"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["firebase_uid"] == uid
    assert data["email"] == email
    assert data["display_name"] == "New User"
    assert data["locale"] == "ja"
    assert data["current_plan"] == "free"

    # DB 確認
    result = await db_session.execute(select(User).where(User.firebase_uid == uid))
    db_user = result.scalar_one_or_none()
    assert db_user is not None


@pytest.mark.asyncio
async def test_post_auth_register_is_idempotent(app_client, authed_user) -> None:
    """既存ユーザーで POST しても重複作成されない（同じユーザーを 201 で返す）"""
    user, token = authed_user
    response = await app_client.post(
        "/api/v1/auth/register",
        headers={"Authorization": f"Bearer {token}"},
        json={"display_name": "Should Not Override"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["firebase_uid"] == user.firebase_uid
    # 既存ユーザーが返るので display_name は body で上書きされない
    assert data["display_name"] == "Test User"


@pytest.mark.asyncio
async def test_post_auth_register_race_condition(app_client) -> None:
    """同時 2 リクエストで重複 INSERT が起きず、両方 201 を返す"""
    uid = f"race_uid_{uuid4().hex[:8]}"
    email = f"{uid}@example.com"
    token = f"mock:{uid}:{email}"
    headers = {"Authorization": f"Bearer {token}"}

    # 2 リクエストを並列実行
    r1, r2 = await asyncio.gather(
        app_client.post("/api/v1/auth/register", headers=headers, json={"display_name": "U1"}),
        app_client.post("/api/v1/auth/register", headers=headers, json={"display_name": "U2"}),
    )
    assert r1.status_code == 201
    assert r2.status_code == 201
    # 同じ firebase_uid の user が両方とも返る
    assert r1.json()["firebase_uid"] == uid
    assert r2.json()["firebase_uid"] == uid


@pytest.mark.asyncio
async def test_post_auth_register_rejects_missing_email(app_client) -> None:
    """payload に email がない場合 400 を返す"""
    from unittest.mock import patch

    async def _send():
        return await app_client.post(
            "/api/v1/auth/register",
            headers={"Authorization": "Bearer fake_token"},
            json={"display_name": "X"},
        )

    with patch(
        "app.api.deps.verify_id_token_or_mock",
        return_value={"uid": "no_email_uid", "email": None},
    ):
        response = await _send()

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "ERR_INVALID_TOKEN"


@pytest.mark.asyncio
async def test_user_read_excludes_internal_fields(app_client, authed_user) -> None:
    """UserRead レスポンスに内部情報（stripe_customer_id 等）が含まれない"""
    user, token = authed_user
    response = await app_client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    data = response.json()
    # 露出しないフィールド
    assert "stripe_customer_id" not in data
    assert "is_deleted" not in data
    assert "deleted_at" not in data
    assert "anonymize_scheduled_at" not in data
