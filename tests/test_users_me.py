"""GET / PATCH /api/v1/users/me のテスト"""

import pytest


@pytest.mark.asyncio
async def test_get_me_returns_user(app_client, authed_user) -> None:
    user, token = authed_user
    response = await app_client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    data = response.json()
    assert data["firebase_uid"] == user.firebase_uid
    assert data["email"] == user.email
    assert data["terms_agreed_at"] is None
    assert data["terms_version"] is None


@pytest.mark.asyncio
async def test_get_me_returns_404_for_unregistered_user(app_client) -> None:
    """ID Token は有効だが users に未登録のケース"""
    token = "mock:unregistered_uid:unregistered@example.com"
    response = await app_client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 404
    body = response.json()
    assert body["detail"]["code"] == "ERR_USER_NOT_FOUND"


@pytest.mark.asyncio
async def test_patch_me_updates_specified_fields(app_client, authed_user) -> None:
    user, token = authed_user
    response = await app_client.patch(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {token}"},
        json={"display_name": "新しい名前", "locale": "en", "timezone": "America/New_York"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["display_name"] == "新しい名前"
    assert data["locale"] == "en"
    assert data["timezone"] == "America/New_York"


@pytest.mark.asyncio
async def test_patch_me_partial_update_preserves_other_fields(app_client, authed_user) -> None:
    """一部項目のみ指定した場合、他の項目は変更されない"""
    user, token = authed_user
    headers = {"Authorization": f"Bearer {token}"}

    # 事前に複数フィールドを更新しておく
    r1 = await app_client.patch(
        "/api/v1/users/me",
        headers=headers,
        json={"display_name": "元の名前", "locale": "en", "timezone": "America/New_York"},
    )
    assert r1.status_code == 200

    # display_name のみ更新
    r2 = await app_client.patch(
        "/api/v1/users/me",
        headers=headers,
        json={"display_name": "更新後の名前"},
    )
    assert r2.status_code == 200
    data = r2.json()
    assert data["display_name"] == "更新後の名前"
    # 指定していない項目は変更されない
    assert data["locale"] == "en"
    assert data["timezone"] == "America/New_York"


@pytest.mark.asyncio
async def test_patch_me_requires_authentication(app_client) -> None:
    response = await app_client.patch("/api/v1/users/me", json={"display_name": "誰か"})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_patch_me_rejects_explicit_null_locale(app_client, authed_user) -> None:
    """locale/timezone は DB が NOT NULL のため null 明示指定は 422 で拒否する"""
    user, token = authed_user
    response = await app_client.patch(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {token}"},
        json={"locale": None},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_patch_me_no_fields_does_not_update(app_client, authed_user) -> None:
    """全項目未指定なら UPDATE を発行せず現ユーザーをそのまま返す"""
    user, token = authed_user
    response = await app_client.patch(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {token}"},
        json={},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["display_name"] == user.display_name
    assert data["locale"] == user.locale
    assert data["timezone"] == user.timezone
