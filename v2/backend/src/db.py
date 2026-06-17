import re
import uuid
from datetime import datetime, timezone

from sqlalchemy import ForeignKey, DateTime, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from config import settings

engine = create_async_engine(settings.database_url, echo=False)
async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()"), default=lambda: datetime.now(timezone.utc)
    )
    settings: Mapped[dict] = mapped_column(JSONB, default=dict, server_default=text("'{}'::jsonb"))


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="member")
    org_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()"), default=lambda: datetime.now(timezone.utc)
    )


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    chunk_index: Mapped[int] = mapped_column(nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)


async def get_db():
    async with async_session_factory() as session:
        yield session


class Matter(Base):
    __tablename__ = "matters"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    org_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()"), default=lambda: datetime.now(timezone.utc)
    )


class MatterMember(Base):
    __tablename__ = "matter_members"

    matter_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("matters.id"), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="viewer")
    invited_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()"), default=lambda: datetime.now(timezone.utc)
    )
    invited_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)


class MatterDocument(Base):
    __tablename__ = "matter_documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    matter_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("matters.id"), nullable=False)
    filename: Mapped[str] = mapped_column(String, nullable=False)
    file_path: Mapped[str] = mapped_column(String, nullable=False)
    confidentiality: Mapped[str] = mapped_column(String(20), nullable=False, default="internal")
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()"), default=lambda: datetime.now(timezone.utc)
    )


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    org_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=True)
    action: Mapped[str] = mapped_column(String, nullable=False)
    resource_type: Mapped[str] = mapped_column(String, nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()"), default=lambda: datetime.now(timezone.utc)
    )
    details: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class GraphNode(Base):
    __tablename__ = "graph_nodes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("matter_documents.id"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    type: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)


class GraphEdge(Base):
    __tablename__ = "graph_edges"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_node_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("graph_nodes.id"), nullable=False)
    target_node_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("graph_nodes.id"), nullable=False)
    relationship: Mapped[str] = mapped_column(String, nullable=False)
    chunk_index: Mapped[int] = mapped_column(nullable=False)


def slugify_org_name(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug[:64] or "org"
