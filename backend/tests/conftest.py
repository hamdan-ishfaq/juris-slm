import asyncio
from datetime import datetime, timezone
import os
import sys
from pathlib import Path
import uuid

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.auth import create_access_token, get_password_hash, set_auth_config
from src.db import Base, ChatMessage, User, UserRole, get_db
from src.routers import admin as admin_router
from src.routers import auth as auth_router
from src.routers import chat as chat_router
from src.routers import documents as documents_router


TEST_SECRET = "test-secret-key-for-suite"


class MockIngestionManager:
    def __init__(self):
        self.calls = []

    async def ingest_pdf(self, file_path, user_id, db, access_level):
        self.calls.append(
            {
                "file_path": file_path,
                "user_id": str(user_id),
                "access_level": access_level,
            }
        )
        return {
            "doc_id": "test-doc-id",
            "parent_chunks_created": 2,
            "child_chunks_created": 5,
        }


class MockQueryManager:
    def __init__(self):
        self.next_answer = "Mocked legal answer"
        self.calls = []

    async def query(self, user_query, role, allowed_indices=None, db=None, user_id=None):
        history_len = 0
        if db is not None and user_id is not None:
            from sqlalchemy import desc, select

            stmt = (
                select(ChatMessage)
                .where(ChatMessage.user_id == user_id)
                .order_by(desc(ChatMessage.timestamp))
                .limit(6)
            )
            result = await db.execute(stmt)
            history_len = len(result.scalars().all())

        self.calls.append(
            {
                "query": user_query,
                "role": role,
                "user_id": str(user_id) if user_id else None,
                "history_window_count": history_len,
            }
        )
        return self.next_answer, {"status": "success", "retrieved_chunks": ["src1"]}


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def db_engine():
    database_url = os.getenv("DATABASE_URL", "postgresql+asyncpg://juris:juris_password@db:5432/juris_db")
    schema_name = f"test_{uuid.uuid4().hex[:10]}"

    admin_engine = create_async_engine(database_url, future=True)
    async with admin_engine.begin() as conn:
        await conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema_name}"'))

    engine = create_async_engine(
        database_url,
        future=True,
        connect_args={"server_settings": {"search_path": schema_name}},
        poolclass=NullPool,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    await engine.dispose()
    async with admin_engine.begin() as conn:
        await conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema_name}" CASCADE'))
    await admin_engine.dispose()


@pytest_asyncio.fixture
async def session_maker(db_engine):
    return async_sessionmaker(db_engine, expire_on_commit=False)


@pytest_asyncio.fixture
async def clean_database(session_maker):
    async with session_maker() as session:
        for table in reversed(Base.metadata.sorted_tables):
            await session.execute(table.delete())
        await session.commit()


@pytest_asyncio.fixture
async def db_session(session_maker, clean_database):
    async with session_maker() as session:
        yield session


@pytest_asyncio.fixture(autouse=True)
async def clean_db_per_test(clean_database):
    return None


@pytest_asyncio.fixture
async def app(session_maker):
    async def override_get_db():
        async with session_maker() as session:
            yield session

    set_auth_config(secret_key=TEST_SECRET, algorithm="HS256", expire_minutes=60)

    test_app = FastAPI(title="Backend Test App")
    test_app.include_router(auth_router.router)
    test_app.include_router(admin_router.router)
    test_app.include_router(chat_router.router)
    test_app.include_router(documents_router.router)
    test_app.dependency_overrides[get_db] = override_get_db

    mock_query_manager = MockQueryManager()
    mock_ingestion_manager = MockIngestionManager()
    chat_router.set_managers(mock_query_manager, None, None, asyncio.Semaphore(1))
    documents_router.set_managers(mock_ingestion_manager, None, None)

    import src.db as db_module

    db_module.async_session_maker = session_maker

    test_app.state.mock_query_manager = mock_query_manager
    test_app.state.mock_ingestion_manager = mock_ingestion_manager
    yield test_app


@pytest_asyncio.fixture
async def client(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def create_user(db_session):
    async def _create_user(email: str, role: UserRole = UserRole.USER, password: str = "Secret123!"):
        user = User(
            email=email,
            password_hash=get_password_hash(password),
            role=role,
            created_at=datetime.now(timezone.utc),
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)
        return user

    return _create_user


@pytest_asyncio.fixture
async def auth_headers(create_user):
    async def _auth_headers(role: UserRole = UserRole.USER, email: str | None = None):
        user_email = email or f"{role.value}_{datetime.now().timestamp()}@example.com"
        user = await create_user(user_email, role=role)
        token = create_access_token(data={"sub": str(user.id), "role": user.role.value})
        return {"Authorization": f"Bearer {token}"}, user

    return _auth_headers