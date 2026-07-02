"""認証 Depends の 401 系テスト"""

import pytest


@pytest.mark.asyncio
async def test_missing_bearer_returns_401(app_client) -> None:
    response = await app_client.get("/api/v1/users/me")
    assert response.status_code == 401
    body = response.json()
    assert body["detail"]["code"] == "ERR_MISSING_TOKEN"


@pytest.mark.asyncio
async def test_invalid_token_returns_401(app_client) -> None:
    response = await app_client.get("/api/v1/users/me", headers={"Authorization": "Bearer invalid:format"})
    assert response.status_code == 401
    body = response.json()
    assert body["detail"]["code"] == "ERR_INVALID_TOKEN"


@pytest.mark.asyncio
async def test_wrong_scheme_returns_401(app_client) -> None:
    response = await app_client.get("/api/v1/users/me", headers={"Authorization": "Basic abc123"})
    assert response.status_code == 401
