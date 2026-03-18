"""
db.py - SQLAlchemy database configuration and ORM models
Async SQLAlchemy setup for PostgreSQL with User model
"""
import uuid
from datetime import datetime
from typing import AsyncGenerator

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Session, relationship
from sqlalchemy import Column, String, Text, Enum, TIMESTAMP, UUID, Integer, ForeignKey, JSON
import enum

# Database URL (will be configured at runtime)
SQLALCHEMY_DATABASE_URL = None

class Base(DeclarativeBase):
    """Base class for all ORM models"""
    pass


class UserRole(str, enum.Enum):
    """User role enumeration"""
    USER = "user"
    ADMIN = "admin"
    OWNER = "owner"


class AccessLevel(str, enum.Enum):
    """Document access level enumeration for hierarchical RBAC"""
    LEVEL_1 = "level_1"  # Public - accessible to all authenticated users
    LEVEL_2 = "level_2"  # Restricted - accessible to admin and owner
    LEVEL_3 = "level_3"  # Confidential - accessible to owner only


class User(Base):
    """User model for authentication and RBAC"""
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(Text, nullable=False)
    role = Column(Enum(UserRole), default=UserRole.USER, nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, default=datetime.utcnow)

    # Relationships
    documents = relationship("Document", back_populates="owner", cascade="all, delete-orphan")
    query_traces = relationship("QueryTrace", back_populates="user", cascade="all, delete-orphan")


class Document(Base):
    """Document model for tracking uploaded files and ownership"""
    __tablename__ = "documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    filename = Column(String(255), nullable=False)
    owner_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    access_level = Column(Enum(AccessLevel), default=AccessLevel.LEVEL_1, nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, default=datetime.utcnow)

    # Relationships
    owner = relationship("User", back_populates="documents")
    parent_chunks = relationship("ParentChunk", back_populates="document", cascade="all, delete-orphan")


class ParentChunk(Base):
    """Parent chunk model for hierarchical retrieval (large context blocks)"""
    __tablename__ = "parent_chunks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    doc_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    content = Column(Text, nullable=False)  # Large 1000-token block
    page_number = Column(Integer, nullable=True)  # PDF page number (nullable for text files)
    char_start = Column(Integer, nullable=False)  # Start position in original document
    char_end = Column(Integer, nullable=False)  # End position in original document

    # Relationships
    document = relationship("Document", back_populates="parent_chunks")


class QueryTrace(Base):
    """Query trace model for audit logging and analytics"""
    __tablename__ = "query_traces"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    query_text = Column(Text, nullable=False)
    response_text = Column(Text, nullable=False)
    retrieved_doc_ids = Column(JSON, nullable=False, default=list)  # List of document UUIDs
    timestamp = Column(TIMESTAMP(timezone=True), nullable=False, default=datetime.utcnow, index=True)

    # Relationships
    user = relationship("User", back_populates="query_traces")


class ChatMessage(Base):
    """Chat message model for conversational memory"""
    __tablename__ = "chat_messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(20), nullable=False)  # "user" or "assistant"
    content = Column(Text, nullable=False)
    timestamp = Column(TIMESTAMP(timezone=True), nullable=False, default=datetime.utcnow, index=True)


# Async engine and session factory (initialized in config)
engine = None
async_session_maker = None


async def init_db(database_url: str) -> None:
    """
    Initialize async database engine and session factory
    
    Args:
        database_url: Async SQLAlchemy database URL (e.g., 'postgresql+asyncpg://user:pass@host/db')
    """
    global engine, async_session_maker
    
    engine = create_async_engine(database_url, echo=False, future=True)
    async_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency to get async database session
    
    Yields:
        AsyncSession for database operations
    """
    if async_session_maker is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()


async def close_db() -> None:
    """Close database engine"""
    global engine
    if engine:
        await engine.dispose()
