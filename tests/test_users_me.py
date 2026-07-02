"""GET /api/v1/users/me のテスト"""

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
