import enum
from sqlalchemy import Column, String, Integer, Enum, Text, ForeignKey, DateTime, func
from sqlalchemy.orm import relationship
from app.db.base import Base
from typing import Optional
from datetime import datetime

class Role(str, enum.Enum):
    viewer = "viewer"
    editor = "editor"
    reviewer = "reviewer"
    admin = "admin"

class ReviewStatus(str, enum.Enum):
    draft = "draft"
    pending_review = "pending_review"
    approved = "approved"
    rejected = "rejected"
    deleted = "deleted"

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    avatar_url = Column(String, nullable=True)
    hashed_password = Column(String, nullable=False)
    role = Column(Enum(Role), default=Role.viewer, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_login = Column(DateTime(timezone=True), onupdate=func.now())

    documents = relationship("Document", back_populates="author", foreign_keys="Document.author_id")

    # Pydantic schema expectations: camelCase props
    @property
    def avatarUrl(self) -> Optional[str]:
        return self.avatar_url

    @property
    def createdAt(self) -> datetime:
        return self.created_at

class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    image_url = Column(String, nullable=True)
    version = Column(Integer, default=1, nullable=False)
    status = Column(Enum(ReviewStatus), default=ReviewStatus.draft, nullable=False)

    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    author = relationship("User", back_populates="documents", foreign_keys=[author_id])
    author_name = Column(String, nullable=False)

    reviewer_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    reviewer = relationship("User", foreign_keys=[reviewer_id])
    reviewer_name = Column(String, nullable=True)

    rejection_reason = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    submitted_at = Column(DateTime(timezone=True), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)

    history = relationship("DocumentHistory", back_populates="document")

    # Pydantic schema expectations: camelCase props
    @property
    def authorId(self) -> int:
        return self.author_id

    @property
    def authorName(self) -> str:
        return self.author_name

    @property
    def reviewerId(self) -> Optional[int]:
        return self.reviewer_id

    @property
    def reviewerName(self) -> Optional[str]:
        return self.reviewer_name

    @property
    def rejectionReason(self) -> Optional[str]:
        return self.rejection_reason

    @property
    def createdAt(self) -> datetime:
        return self.created_at

    @property
    def updatedAt(self) -> Optional[datetime]:
        return self.updated_at

    @property
    def submittedAt(self) -> Optional[datetime]:
        return self.submitted_at

    @property
    def reviewedAt(self) -> Optional[datetime]:
        return self.reviewed_at

class DocumentHistory(Base):
    __tablename__ = "document_history"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    document = relationship("Document", back_populates="history")

    action = Column(String, nullable=False)

    actor_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    actor = relationship("User")

    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    details = Column(Text, nullable=True)

    # Pydantic schema expectations: camelCase props
    @property
    def userId(self) -> int:
        return self.actor_id

    @property
    def userName(self) -> str:
        return self.actor.name
