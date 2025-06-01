from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from fastapi import File, UploadFile
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
from typing import List, Optional
from math import ceil
from app.db.session import get_db
from app.db.models import Document, DocumentHistory, ReviewStatus, User, Role
from app.schemas.document import DocumentCreate, DocumentRead, DocumentUpdate
from app.schemas.history import HistoryEntry
from app.core.security import get_current_user, require_role
from app.services.s3 import upload_image
from app.services.ses import queue_review_email
from app.services.cloudfront import generate_signed_url
from app.core.config import settings
from datetime import datetime, timezone
import re

router = APIRouter(prefix="/api/documents", tags=["documents"])

# Helper for pagination

def paginate(query, page:int, limit:int):
    total = query.count()
    pages = ceil(total/limit if limit else 1)
    items = query.offset((page-1)*limit).limit(limit).all()
    return items, pages

@router.post("", response_model=DocumentRead)
def create_document(data: DocumentCreate, background_tasks: BackgroundTasks,db: Session = Depends(get_db), user=Depends(get_current_user)):
    # create draft or submit
    print(f"reviewerId: {data.reviewerId}, action: {data.action}")
    doc = Document(
        title=data.title,
        content=_process_image_urls_in_content(data.content),
        image_url=_process_image_url_to_path(data.imageUrl),
        author_id=user.id,
        author_name=user.name,
        status=ReviewStatus.draft,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    if data.reviewerId:
        rev = db.query(User).get(data.reviewerId)
        if rev and rev.role in [Role.reviewer, Role.admin]:
            doc.reviewer_id = rev.id
            doc.reviewer_name = rev.name
        else:
            if data.action == 'submit_for_review':
                raise HTTPException(400, "Invalid reviewer")

    if data.action == 'submit_for_review':
        if not data.reviewerId:
            raise HTTPException(400, "reviewerId required for submit")
        doc.status = ReviewStatus.pending_review
        doc.submitted_at = datetime.now(timezone.utc)

    db.add(doc)
    db.commit()
    db.refresh(doc)

    hist_action = 'submitted' if data.action == 'submit_for_review' else 'created'
    hist = DocumentHistory(document_id=doc.id, action=hist_action, actor_id=user.id)
    db.add(hist)
    db.commit()

    if doc.status == ReviewStatus.pending_review and doc.reviewer and doc.reviewer.email:
        queue_review_email(
            background_tasks=background_tasks,
            reviewer_email=doc.reviewer.email,
            reviewer_name=doc.reviewer.name,
            author_name=user.name,
            doc_title=doc.title,
            doc_id=doc.id,
            frontend_url=settings.FRONTEND_URL,
        )
    return doc

@router.get("", response_model=dict)
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
    query = query.filter(Document.status != ReviewStatus.deleted)  # Exclude soft-deleted documents
    # RBAC filtering
    if user.role == Role.admin:
        pass

    elif user.role == Role.viewer:
        # viewer can only see approved documents
        query = query.filter(Document.status == ReviewStatus.approved)

    elif user.role == Role.reviewer:
        # reviewer can see: all approved, pending reviews assigned to them,
        # rejected documents they reviewed, and drafts they authored
        query = query.filter(
            or_(
                Document.status == ReviewStatus.approved,
                
                Document.author_id == user.id,
                
                and_(
                    Document.reviewer_id == user.id,
                    Document.status.in_([
                        ReviewStatus.pending_review,
                        ReviewStatus.rejected
                    ])
                )
            )
        )

    else:
        # editor: can see all approved, drafts and pending reviews they authored
        query = query.filter(
            or_(
                Document.status == ReviewStatus.approved,
                and_(
                    Document.author_id == user.id,
                    Document.status.in_([
                        ReviewStatus.draft,
                        ReviewStatus.pending_review,
                        ReviewStatus.rejected
                    ])
                )
            )
        )
    # -- RBAC 過濾結束 --
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
       query = query.filter(
            or_(
                Document.title.ilike(f"%{searchTerm}%"),
                Document.content.ilike(f"%{searchTerm}%"),
                Document.author_name.ilike(f"%{searchTerm}%"),
                Document.reviewer_name.ilike(f"%{searchTerm}%")           
            )
       )
    # sorting
    if sortBy:
        field, order = sortBy.split('_')
        col = getattr(Document, 'updated_at' if field=='updatedAt' else field)
        query = query.order_by(col.desc() if order=='desc' else col.asc())
    items, pages = paginate(query, page, limit)
    # Convert image URLs to signed URLs if needed
    for item in items:
        if item.image_url:
            item.image_url = generate_signed_url(item.image_url, expire_in_seconds=600)
    
    return {"documents": items, "totalPages": pages, "currentPage": page}

@router.get("/{document_id}", response_model=DocumentRead)
def get_document(document_id: int, db: Session=Depends(get_db), user=Depends(get_current_user)):
    doc = db.query(Document).get(document_id)
    if not doc:
        raise HTTPException(404,"Not found")
    if doc.status!=ReviewStatus.approved and user.id not in [doc.author_id, doc.reviewer_id] and user.role!=Role.admin:
        raise HTTPException(403)
    doc.content = _sign_all_urls_in_content(doc.content) if doc.content else None
    doc.image_url = generate_signed_url(doc.image_url, expire_in_seconds=600) if doc.image_url else None
    return doc

@router.put("/{document_id}", response_model=DocumentRead)
def update_document(document_id: int, data: DocumentUpdate, background_tasks: BackgroundTasks, db: Session = Depends(get_db), user=Depends(get_current_user)):
    print(f"reviewerId: {data.reviewerId}, action: {data.action}")
    doc = db.query(Document).get(document_id)
    if not doc:
        raise HTTPException(404)
    if doc.author_id != user.id and user.role != Role.admin:
        raise HTTPException(403)

    if doc.status == ReviewStatus.approved:
        doc.version += 1
        doc.status = ReviewStatus.draft

    if data.title:
        doc.title = data.title
    if data.content is not None:
        doc.content = _process_image_urls_in_content(data.content)
    if data.imageUrl is not None:
        doc.image_url = _process_image_url_to_path(data.imageUrl)
    doc.updated_at = datetime.now(timezone.utc)

    if data.reviewerId:
        rev = db.query(User).get(data.reviewerId)
        if rev and rev.role in [Role.reviewer, Role.admin]:
            doc.reviewer_id = rev.id
            doc.reviewer_name = rev.name
        else:
            if data.action == 'resubmit_for_review':
                raise HTTPException(400, "Invalid reviewer")

    if data.action == 'resubmit_for_review':
        if not data.reviewerId:
            raise HTTPException(400, "reviewerId required for resubmit")
        doc.status = ReviewStatus.pending_review
        doc.submitted_at = datetime.now(timezone.utc)
    else:
        doc.status = ReviewStatus.draft

    db.commit()
    db.refresh(doc)

    hist_action = 'submitted' if data.action == 'resubmit_for_review' else 'edited'
    hist = DocumentHistory(document_id=doc.id, action=hist_action, actor_id=user.id)
    db.add(hist)
    db.commit()

    if doc.status == ReviewStatus.pending_review and doc.reviewer and doc.reviewer.email:
        queue_review_email(
            background_tasks=background_tasks,
            reviewer_email=doc.reviewer.email,
            reviewer_name=doc.reviewer.name,
            author_name=user.name,
            doc_title=doc.title,
            doc_id=doc.id,
            frontend_url=settings.FRONTEND_URL,
        )
    doc.content = _sign_all_urls_in_content(doc.content) if doc.content else None
    doc.image_url = generate_signed_url(doc.image_url, expire_in_seconds=600) if doc.image_url else None
    return doc



@router.delete("/{document_id}")
def delete_document(document_id:int, db:Session=Depends(get_db), user=Depends(get_current_user)):
    doc=db.query(Document).get(document_id)
    if not doc: raise HTTPException(404)
    allow = False
    
    if user.role!=Role.viewer:
        if user.role==Role.admin and doc.status==ReviewStatus.approved:
            # admin can delete approved documents
            allow = True
        elif doc.author_id==user.id and doc.status not in [ReviewStatus.approved, ReviewStatus.pending_review]:
            # author can delete drafts or rejected documents
            allow = True
    
    if not allow:
        raise HTTPException(403, "You do not have permission to delete this document!")
   
    doc.status = ReviewStatus.deleted
    db.commit()
    return {"message":"Document soft-deleted"}

@router.post("/{document_id}/approve", response_model=DocumentRead)
def approve(document_id:int, db:Session=Depends(get_db), user=Depends(require_role(Role.reviewer, Role.admin))):
    doc=db.query(Document).get(document_id)
    if not doc or doc.reviewer_id!=user.id and user.role!=Role.admin: raise HTTPException(404)
    doc.status=ReviewStatus.approved; doc.reviewed_at=datetime.utcnow()
    db.commit(); db.refresh(doc)
    hist=DocumentHistory(document_id=doc.id, action='approved', actor_id=user.id)
    db.add(hist); db.commit()
    doc.content = _sign_all_urls_in_content(doc.content) if doc.content else None
    doc.image_url = generate_signed_url(doc.image_url, expire_in_seconds=600) if doc.image_url else None
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
    doc.content = _sign_all_urls_in_content(doc.content) if doc.content else None
    doc.image_url = generate_signed_url(doc.image_url, expire_in_seconds=600) if doc.image_url else None
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
    doc.content = _sign_all_urls_in_content(doc.content) if doc.content else None
    doc.image_url = generate_signed_url(doc.image_url, expire_in_seconds=600) if doc.image_url else None
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
    key = await upload_image(file)
    url = generate_signed_url(key, expire_in_seconds=600)
    return {"imageUrl": url}

def _process_image_url_to_path(image_url: str|None) -> str|None:
    """
    Process the image URL to S3 path without bucket name.
    """
    if not image_url:
        return None
    if image_url.startswith("https://"):
        image_url = image_url.replace("https://", "")
        # Get the path after the domain
        if "/" in image_url:
            image_url = image_url.split("/", 1)[1]
        if "?" in image_url: # Remove query parameters if present
            image_url = image_url.split("?")[0]
    return image_url

def _process_image_urls_in_content(content: str) -> str:
    """
    Find all CloudFront signed URLs in the content and replace them with S3 paths.
    """
    pattern = r'({}/[^"]+)'.format(settings.CLOUDFRONT_DOMAIN)
    matches = re.findall(pattern, content)
    for match in matches:
        # Replace the CloudFront URL with the S3 path
        s3_path = _process_image_url_to_path(match) + ')'
        content = content.replace(match, s3_path)
    
    return content

def _sign_all_urls_in_content(content: str) -> str:
    """
    Find all S3 image paths in the content and replace them with signed URLs.
    """
    pattern = re.compile(r"\(images/[^)]+\)")

    matches = re.findall(pattern, content)
    for match in matches:
        signed_url = generate_signed_url(match[1:-1], expire_in_seconds=600)
        content = content.replace(match, f"({signed_url})")
    return content