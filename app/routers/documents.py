from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import File, UploadFile
from sqlalchemy.orm import Session
from typing import List, Optional
from math import ceil
from app.db.session import get_db
from app.db.models import Document, DocumentHistory, ReviewStatus, User, Role
from app.schemas.document import DocumentCreate, DocumentRead, DocumentUpdate
from app.schemas.history import HistoryEntry
from app.core.security import get_current_user, require_role
from app.services.s3 import upload_image
from app.core.config import settings
from datetime import datetime, timezone

router = APIRouter(prefix="/api/documents", tags=["documents"])

# Helper for pagination

def paginate(query, page:int, limit:int):
    total = query.count()
    pages = ceil(total/limit if limit else 1)
    items = query.offset((page-1)*limit).limit(limit).all()
    return items, pages

@router.post("/", response_model=DocumentRead)
def create_document(data: DocumentCreate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    # create draft or submit
    doc = Document(
        title=data.title, content=data.content, image_url=data.imageUrl,
        author_id=user.id, author_name=user.name,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    if data.action == 'submit_for_review':
        if not data.reviewerId:
            raise HTTPException(400, "reviewerId required for submit")
        rev = db.query(User).get(data.reviewerId)
        if not rev or rev.role not in [Role.reviewer, Role.admin]:
            raise HTTPException(400, "Invalid reviewer")
        doc.status = ReviewStatus.pending_review
        doc.reviewer_id = rev.id
        doc.reviewer_name = rev.name
        doc.submitted_at = datetime.now(timezone.utc)
    db.add(doc)
    db.commit()
    db.refresh(doc)
    # history
    action = 'submitted' if data.action=='submit_for_review' else 'created'
    hist = DocumentHistory(document_id=doc.id, action=action, actor_id=user.id)
    db.add(hist)
    db.commit()
    return doc

@router.get("/", response_model=dict)
def list_documents(
    authorId: Optional[int] = None,
    reviewerId: Optional[int] = None,
    status: Optional[ReviewStatus] = None,
    view: Optional[str] = None,
    searchTerm: Optional[str] = None,
    sortBy: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1),
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    query = db.query(Document)
    # RBAC filtering
    if user.role == Role.viewer:
        query = query.filter(Document.status==ReviewStatus.approved)
    if authorId:
        query = query.filter(Document.author_id==authorId)
    if reviewerId:
        query = query.filter(Document.reviewer_id==reviewerId)
    if status:
        query = query.filter(Document.status==status)
    if view=='pending_my_review':
        query = query.filter(Document.reviewer_id==user.id, Document.status==ReviewStatus.pending_review)
    if searchTerm:
        query = query.filter(Document.title.ilike(f"%{searchTerm}%")|Document.content.ilike(f"%{searchTerm}%"))
    # sorting
    if sortBy:
        field, order = sortBy.split('_')
        col = getattr(Document, 'updated_at' if field=='updatedAt' else field)
        query = query.order_by(col.desc() if order=='desc' else col.asc())
    items, pages = paginate(query, page, limit)
    return {"documents": items, "totalPages": pages, "currentPage": page}

@router.get("/{document_id}", response_model=DocumentRead)
def get_document(document_id: int, db: Session=Depends(get_db), user=Depends(get_current_user)):
    doc = db.query(Document).get(document_id)
    if not doc:
        raise HTTPException(404,"Not found")
    if doc.status!=ReviewStatus.approved and user.id not in [doc.author_id, doc.reviewer_id] and user.role!=Role.admin:
        raise HTTPException(403)
    return doc

@router.put("/{document_id}", response_model=DocumentRead)
def update_document(document_id: int, data: DocumentUpdate, db: Session=Depends(get_db), user=Depends(get_current_user)):
    doc = db.query(Document).get(document_id)
    if not doc:
        raise HTTPException(404)
    if doc.author_id!=user.id and user.role!=Role.admin:
        raise HTTPException(403)
    # version bump if editing approved
    if doc.status==ReviewStatus.approved:
        doc.version += 1
        doc.status=ReviewStatus.draft
    if data.title: doc.title = data.title
    if data.content: doc.content = data.content
    if data.imageUrl: doc.image_url = data.imageUrl
    doc.updated_at = datetime.now(timezone.utc)
    if data.action=='resubmit_for_review':
        if not data.reviewerId: raise HTTPException(400)
        rev=db.query(User).get(data.reviewerId)
        doc.reviewer_id=rev.id; doc.reviewer_name=rev.name; doc.status=ReviewStatus.pending_review; doc.submitted_at=datetime.utcnow()
    db.commit(); db.refresh(doc)
    hist=DocumentHistory(document_id=doc.id, action='edited' if data.action=='save_draft' else 'resubmitted', actor_id=user.id)
    db.add(hist); db.commit()
    return doc

@router.delete("/{document_id}")
def delete_document(document_id:int, db:Session=Depends(get_db), user=Depends(get_current_user)):
    doc=db.query(Document).get(document_id)
    if not doc: raise HTTPException(404)
    if doc.status!=ReviewStatus.draft or (doc.author_id!=user.id and user.role!=Role.admin):
        raise HTTPException(403)
    db.delete(doc); db.commit()
    return {"message":"Deleted"}

@router.post("/{document_id}/approve", response_model=DocumentRead)
def approve(document_id:int, db:Session=Depends(get_db), user=Depends(require_role(Role.reviewer, Role.admin))):
    doc=db.query(Document).get(document_id)
    if not doc or doc.reviewer_id!=user.id and user.role!=Role.admin: raise HTTPException(404)
    doc.status=ReviewStatus.approved; doc.reviewed_at=datetime.utcnow()
    db.commit(); db.refresh(doc)
    hist=DocumentHistory(document_id=doc.id, action='approved', actor_id=user.id)
    db.add(hist); db.commit()
    return doc

@router.post("/{document_id}/reject", response_model=DocumentRead)
def reject(document_id:int, payload:dict, db:Session=Depends(get_db), user=Depends(require_role(Role.reviewer, Role.admin))):
    reason=payload.get('reason')
    doc=db.query(Document).get(document_id)
    if not doc or doc.reviewer_id!=user.id and user.role!=Role.admin: raise HTTPException(404)
    doc.status=ReviewStatus.rejected; doc.rejection_reason=reason; doc.reviewed_at=datetime.utcnow()
    db.commit(); db.refresh(doc)
    hist=DocumentHistory(document_id=doc.id, action='rejected', actor_id=user.id, details=reason)
    db.add(hist); db.commit()
    return doc

@router.post("/{document_id}/reassign", response_model=DocumentRead)
def reassign(document_id:int, payload:dict, db:Session=Depends(get_db), user=Depends(require_role(Role.admin))):
    new_id=payload.get('newReviewerId')
    rev=db.query(User).get(new_id); doc=db.query(Document).get(document_id)
    if not doc or not rev: raise HTTPException(404)
    doc.reviewer_id=new_id; doc.reviewer_name=rev.name; doc.status=ReviewStatus.pending_review
    db.commit(); db.refresh(doc)
    hist=DocumentHistory(document_id=doc.id, action='reassigned', actor_id=user.id, details=str({'newReviewerId':new_id}))
    db.add(hist); db.commit()
    return doc

# History endpoint
@router.get("/{document_id}/history", response_model=List[HistoryEntry])
def history(document_id:int, db:Session=Depends(get_db), user=Depends(get_current_user)):
    return db.query(DocumentHistory).filter(DocumentHistory.document_id==document_id).order_by(DocumentHistory.timestamp.desc()).all()

# Image upload
from fastapi import APIRouter
upload_router = APIRouter(prefix="/api", tags=["images"])

@upload_router.post("/upload")
async def upload_endpoint(file: UploadFile = File(...)):
    url = await upload_image(file)
    return {"imageUrl": url}
