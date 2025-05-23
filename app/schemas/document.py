from pydantic import BaseModel
from typing import Optional
from app.db.models import ReviewStatus
from datetime import datetime

class DocumentBase(BaseModel):
    title: str
    content: str
    imageUrl: Optional[str]

class DocumentCreate(DocumentBase):
    reviewerId: Optional[int]
    action: str  # 'save_draft' | 'submit_for_review'

class DocumentRead(DocumentBase):
    id: int
    authorId: int
    authorName: str
    reviewerId: Optional[int]
    reviewerName: Optional[str]
    status: ReviewStatus
    createdAt: datetime
    updatedAt: Optional[datetime]
    submittedAt: Optional[datetime]
    reviewedAt: Optional[datetime]
    rejectionReason: Optional[str]
    version: int
    class Config:
        orm_mode = True

class DocumentUpdate(BaseModel):
    title: Optional[str]
    content: Optional[str]
    imageUrl: Optional[str]
    reviewerId: Optional[int]
    action: str  # 'save_draft' | 'resubmit_for_review'
