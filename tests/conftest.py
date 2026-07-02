"""pytest 共通フィクスチャ"""

from collections.abc import AsyncGenerator
from typing import Any
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import get_session
from app.main import app
from app.models.user import User
from app.settings import settings


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    return "asyncio"


@pytest_asyncio.fixture
async def db_engine() -> AsyncGenerator:
    """テストごとに作成する async engine。

    Docker PostgreSQL を前提とする（DATABASE_URL）。
    pytest-asyncio v1 では各テストが独自の event loop を持つため、
    session スコープの engine は別ループに紐づき "attached to a different loop"
    エラーになる。これを回避するため engine も関数スコープで作る。
    """
    engine = create_async_engine(settings.database_url, echo=False, pool_pre_ping=True)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    """各テストごとに SAVEPOINT を張り、終了時にロールバック。

    既存 DB へのコミット汚染を防ぐ。
    """
    connection = await db_engine.connect()
    transaction = await connection.begin()
    session_maker = async_sessionmaker(bind=connection, class_=AsyncSession, expire_on_commit=False, autoflush=False)
    session = session_maker()
    try:
        yield session
    finally:
        await session.close()
        await transaction.rollback()
        await connection.close()


@pytest_asyncio.fixture
async def app_client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """テスト用 AsyncClient。get_session を db_session で上書きして全 API がトランザクション内で動作する。"""

    async def _override_session() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_session] = _override_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def mock_firebase_verify(monkeypatch: pytest.MonkeyPatch) -> None:
    """全テストで Firebase 実呼び出しを抑止し、mock:<uid>:<email> 形式を解釈させる。

    Settings.use_auth_mock を True にせず、verify_id_token を直接モック化する方式。
    test_auth_firebase.py は本フィクスチャを使わないので影響なし（autouse でも個別 monkeypatch で上書き可能）。
    """
    from app.auth import mock as mock_mod

    def _mock_verify(token: str) -> dict[str, Any]:
        return mock_mod.verify_mock_token(token)

    monkeypatch.setattr("app.auth.firebase.verify_id_token", _mock_verify)
    # ディスパッチャも実 Firebase を呼ばないように差し替え
    monkeypatch.setattr("app.api.deps.verify_id_token_or_mock", _mock_verify)


@pytest_asyncio.fixture
async def authed_user(db_session: AsyncSession) -> tuple[User, str]:
    """DB に test user を INSERT し、(User, Bearer Token) を返す。"""
    firebase_uid = f"test_uid_{uuid4().hex[:8]}"
    email = f"{firebase_uid}@example.com"
    user = User(
        firebase_uid=firebase_uid,
        email=email,
        display_name="Test User",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    token = f"mock:{firebase_uid}:{email}"
    return user, token
