"""POST /api/v1/users/me/terms-agreement のテスト"""

import pytest


@pytest.mark.asyncio
async def test_terms_agree_sets_both_fields(app_client, authed_user) -> None:
    user, token = authed_user
    response = await app_client.post(
        "/api/v1/users/me/terms-agreement",
        headers={"Authorization": f"Bearer {token}"},
        json={"terms_version": "v1.0"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["terms_agreed_at"] is not None
    assert data["terms_version"] == "v1.0"


@pytest.mark.asyncio
async def test_terms_agree_requires_version(app_client, authed_user) -> None:
    user, token = authed_user
    response = await app_client.post(
        "/api/v1/users/me/terms-agreement",
        headers={"Authorization": f"Bearer {token}"},
        json={"terms_version": ""},
    )
    assert response.status_code == 422  # Pydantic ValidationError


@pytest.mark.asyncio
async def test_terms_agree_can_be_re_agreed(app_client, authed_user) -> None:
    """既に同意済みのユーザーが再度 POST しても 200 で terms_agreed_at が更新される"""
    user, token = authed_user
    headers = {"Authorization": f"Bearer {token}"}

    # 1回目の同意
    r1 = await app_client.post("/api/v1/users/me/terms-agreement", headers=headers, json={"terms_version": "v1.0"})
    assert r1.status_code == 200
    first_agreed_at = r1.json()["terms_agreed_at"]
    assert first_agreed_at is not None

    # 2回目の同意（バージョンアップ想定）
    r2 = await app_client.post("/api/v1/users/me/terms-agreement", headers=headers, json={"terms_version": "v2.0"})
    assert r2.status_code == 200
    data = r2.json()
    assert data["terms_version"] == "v2.0"
    assert data["terms_agreed_at"] is not None
