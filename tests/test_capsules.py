"""capsules API（POST/GET/PATCH）のテスト"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select, update

from app.models.capsule import Capsule
from app.models.capsule_member import CapsuleMember
from app.models.user import User


def _future_iso(days: int = 365) -> str:
    return (datetime.now(UTC) + timedelta(days=days)).isoformat()


def _past_iso(days: int = 1) -> str:
    return (datetime.now(UTC) - timedelta(days=days)).isoformat()


async def _agree_terms(app_client, token: str) -> None:
    response = await app_client.post(
        "/api/v1/users/me/terms-agreement",
        headers={"Authorization": f"Bearer {token}"},
        json={"terms_version": "v1.0"},
    )
    assert response.status_code == 200


async def _create_user(db_session) -> tuple[User, str]:
    """authed_user フィクスチャと同様に DB へユーザーを INSERT し (User, token) を返す。"""
    firebase_uid = f"test_uid_{uuid4().hex[:8]}"
    email = f"{firebase_uid}@example.com"
    user = User(firebase_uid=firebase_uid, email=email, display_name="Another User")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    token = f"mock:{firebase_uid}:{email}"
    return user, token


# --- POST /capsules ---------------------------------------------------------


@pytest.mark.asyncio
async def test_create_capsule_success(app_client, authed_user, db_session) -> None:
    user, token = authed_user
    await _agree_terms(app_client, token)
    headers = {"Authorization": f"Bearer {token}"}

    response = await app_client.post(
        "/api/v1/capsules",
        headers=headers,
        json={"name": "テストカプセル", "open_at": _future_iso()},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "テストカプセル"
    assert data["created_by"] == str(user.id)
    assert data["member_count"] == 1
    assert data["is_frozen"] is False
    assert data["my_membership"]["status"] == "active"

    # 作成者が active メンバーとして DB に登録されていること
    result = await db_session.execute(select(CapsuleMember).where(CapsuleMember.capsule_id == data["id"]))
    members = result.scalars().all()
    assert len(members) == 1
    assert members[0].status == "active"
    assert members[0].user_id == user.id
    assert members[0].joined_at is not None


@pytest.mark.asyncio
async def test_create_capsule_requires_terms_agreement(app_client, authed_user) -> None:
    """terms_agreed_at 未設定のユーザーは 403 ERR_TERMS_NOT_AGREED"""
    _, token = authed_user
    response = await app_client.post(
        "/api/v1/capsules",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "テストカプセル", "open_at": _future_iso()},
    )
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "ERR_TERMS_NOT_AGREED"


@pytest.mark.asyncio
async def test_create_capsule_rejects_past_open_at(app_client, authed_user) -> None:
    _, token = authed_user
    await _agree_terms(app_client, token)
    response = await app_client.post(
        "/api/v1/capsules",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "テストカプセル", "open_at": _past_iso()},
    )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "ERR_OPEN_AT_IN_PAST"


@pytest.mark.asyncio
async def test_create_capsule_requires_authentication(app_client) -> None:
    response = await app_client.post(
        "/api/v1/capsules",
        json={"name": "テストカプセル", "open_at": _future_iso()},
    )
    assert response.status_code == 401


# --- GET /capsules -----------------------------------------------------------


@pytest.mark.asyncio
async def test_list_capsules_returns_only_own_active_capsules(app_client, authed_user, db_session) -> None:
    user, token = authed_user
    await _agree_terms(app_client, token)
    headers = {"Authorization": f"Bearer {token}"}

    _, other_token = await _create_user(db_session)
    await _agree_terms(app_client, other_token)

    r1 = await app_client.post(
        "/api/v1/capsules", headers=headers, json={"name": "自分のカプセル", "open_at": _future_iso()}
    )
    assert r1.status_code == 201

    r2 = await app_client.post(
        "/api/v1/capsules",
        headers={"Authorization": f"Bearer {other_token}"},
        json={"name": "他人のカプセル", "open_at": _future_iso()},
    )
    assert r2.status_code == 201

    response = await app_client.get("/api/v1/capsules", headers=headers)
    assert response.status_code == 200
    data = response.json()
    names = [item["name"] for item in data["items"]]
    assert "自分のカプセル" in names
    assert "他人のカプセル" not in names
    assert data["total"] == len(data["items"])


@pytest.mark.asyncio
async def test_list_capsules_state_filter(app_client, authed_user) -> None:
    """state=sealed/unsealed の絞り込み（未開封しか作れないため sealed に含まれ unsealed には含まれない）"""
    user, token = authed_user
    await _agree_terms(app_client, token)
    headers = {"Authorization": f"Bearer {token}"}
    r = await app_client.post(
        "/api/v1/capsules", headers=headers, json={"name": "封印中カプセル", "open_at": _future_iso()}
    )
    assert r.status_code == 201

    sealed_response = await app_client.get("/api/v1/capsules", headers=headers, params={"state": "sealed"})
    assert sealed_response.status_code == 200
    assert any(item["name"] == "封印中カプセル" for item in sealed_response.json()["items"])

    unsealed_response = await app_client.get("/api/v1/capsules", headers=headers, params={"state": "unsealed"})
    assert unsealed_response.status_code == 200
    assert all(item["name"] != "封印中カプセル" for item in unsealed_response.json()["items"])


# --- GET /capsules/{capsuleId} -----------------------------------------------


@pytest.mark.asyncio
async def test_get_capsule_detail_for_member(app_client, authed_user) -> None:
    user, token = authed_user
    await _agree_terms(app_client, token)
    headers = {"Authorization": f"Bearer {token}"}
    r = await app_client.post(
        "/api/v1/capsules", headers=headers, json={"name": "詳細テスト", "open_at": _future_iso()}
    )
    capsule_id = r.json()["id"]

    response = await app_client.get(f"/api/v1/capsules/{capsule_id}", headers=headers)
    assert response.status_code == 200
    assert response.json()["id"] == capsule_id


@pytest.mark.asyncio
async def test_get_capsule_detail_404_for_non_member(app_client, authed_user, db_session) -> None:
    user, token = authed_user
    await _agree_terms(app_client, token)
    headers = {"Authorization": f"Bearer {token}"}
    r = await app_client.post(
        "/api/v1/capsules", headers=headers, json={"name": "非参加者テスト", "open_at": _future_iso()}
    )
    capsule_id = r.json()["id"]

    _, other_token = await _create_user(db_session)
    response = await app_client.get(
        f"/api/v1/capsules/{capsule_id}", headers={"Authorization": f"Bearer {other_token}"}
    )
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "ERR_CAPSULE_NOT_FOUND"


@pytest.mark.asyncio
async def test_get_capsule_detail_404_for_nonexistent_capsule(app_client, authed_user) -> None:
    _, token = authed_user
    response = await app_client.get(f"/api/v1/capsules/{uuid4()}", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "ERR_CAPSULE_NOT_FOUND"


# --- PATCH /capsules/{capsuleId}/open-date -----------------------------------


@pytest.mark.asyncio
async def test_update_open_date_success(app_client, authed_user) -> None:
    user, token = authed_user
    await _agree_terms(app_client, token)
    headers = {"Authorization": f"Bearer {token}"}
    r = await app_client.post(
        "/api/v1/capsules", headers=headers, json={"name": "開封日変更テスト", "open_at": _future_iso(days=30)}
    )
    capsule_id = r.json()["id"]

    new_open_at = _future_iso(days=90)
    response = await app_client.patch(
        f"/api/v1/capsules/{capsule_id}/open-date", headers=headers, json={"open_at": new_open_at}
    )
    assert response.status_code == 200
    data = response.json()
    assert datetime.fromisoformat(data["open_at"]) == datetime.fromisoformat(new_open_at)


@pytest.mark.asyncio
async def test_update_open_date_forbidden_for_non_member(app_client, authed_user, db_session) -> None:
    user, token = authed_user
    await _agree_terms(app_client, token)
    headers = {"Authorization": f"Bearer {token}"}
    r = await app_client.post(
        "/api/v1/capsules", headers=headers, json={"name": "非参加者拒否テスト", "open_at": _future_iso()}
    )
    capsule_id = r.json()["id"]

    _, other_token = await _create_user(db_session)
    response = await app_client.patch(
        f"/api/v1/capsules/{capsule_id}/open-date",
        headers={"Authorization": f"Bearer {other_token}"},
        json={"open_at": _future_iso(days=100)},
    )
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "ERR_NOT_CAPSULE_MEMBER"


@pytest.mark.asyncio
async def test_update_open_date_rejects_past_date(app_client, authed_user) -> None:
    user, token = authed_user
    await _agree_terms(app_client, token)
    headers = {"Authorization": f"Bearer {token}"}
    r = await app_client.post(
        "/api/v1/capsules", headers=headers, json={"name": "過去日拒否テスト", "open_at": _future_iso()}
    )
    capsule_id = r.json()["id"]

    response = await app_client.patch(
        f"/api/v1/capsules/{capsule_id}/open-date", headers=headers, json={"open_at": _past_iso()}
    )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "ERR_OPEN_AT_IN_PAST"


@pytest.mark.asyncio
async def test_update_open_date_conflict_when_already_unsealed(app_client, authed_user, db_session) -> None:
    user, token = authed_user
    await _agree_terms(app_client, token)
    headers = {"Authorization": f"Bearer {token}"}
    r = await app_client.post(
        "/api/v1/capsules", headers=headers, json={"name": "開封済みテスト", "open_at": _future_iso()}
    )
    capsule_id = r.json()["id"]

    # 開封済み状態へ直接更新（unseal API は B-Slice のスコープ外のため DB を直接操作）
    await db_session.execute(
        update(Capsule).where(Capsule.id == capsule_id).values(unsealed_at=datetime.now(UTC), unseal_trigger="manual")
    )
    await db_session.commit()

    response = await app_client.patch(
        f"/api/v1/capsules/{capsule_id}/open-date", headers=headers, json={"open_at": _future_iso(days=100)}
    )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "ERR_CAPSULE_ALREADY_UNSEALED"


@pytest.mark.asyncio
async def test_update_open_date_requires_authentication(app_client) -> None:
    response = await app_client.patch(f"/api/v1/capsules/{uuid4()}/open-date", json={"open_at": _future_iso()})
    assert response.status_code == 401
