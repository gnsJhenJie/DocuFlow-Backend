from sqlalchemy.orm import Session
from fastapi import HTTPException
from tests.conftest import db_add, db_add_all
from app.db.models import Document, Role, User
from app.db.session import engine
from app.schemas.document import DocumentCreate, DocumentUpdate, ReviewStatus
from app.routers.documents import paginate, create_document, list_documents, get_document, update_document, delete_document, approve, reject, reassign, _process_image_url_to_path, _process_image_urls_in_content, _sign_all_urls_in_content

def get_users():
    admin = User(
        id=1,
        name="user1",
        email="test@example.com",
        hashed_password="hashed_password",
        role=Role.admin
    )
    editor = User(
        id=2,
        name="user2",
        email="test@example.com",
        hashed_password="hashed_password",
        role=Role.editor
    )
    reviewer = User(
        id=3,
        name="user3",
        email="test@example.com",
        hashed_password="hashed_password",
        role=Role.reviewer
    )
    viewer = User(
        id=4,
        name="user4",
        email="test@example.com",
        hashed_password="hashed_password",
        role=Role.viewer
    )
    return {
        "admin": admin,
        "editor": editor,
        "reviewer": reviewer,
        "viewer": viewer
    }

def insert_documents(doc_param=None):
    documents = []
    if doc_param is None:
        doc_param = [
            {"author_id": 2, "author_name": "user2", "reviewer_id": 3, "reviewer_name": "user3", "status": ReviewStatus.approved},
            {"author_id": 1, "author_name": "user1", "reviewer_id": 3, "reviewer_name": "user3", "status": ReviewStatus.rejected},
            {"author_id": 1, "author_name": "user1", "reviewer_id": 3, "reviewer_name": "user3", "status": ReviewStatus.deleted},
            {"author_id": 1, "author_name": "user1", "reviewer_id": 3, "reviewer_name": "user3", "status": ReviewStatus.pending_review},
            {"author_id": 2, "author_name": "user2", "reviewer_id": 1, "reviewer_name": "user1", "status": ReviewStatus.pending_review},
            {"author_id": 1, "author_name": "user1", "reviewer_id": 3, "reviewer_name": "user3", "status": ReviewStatus.draft},
            {"author_id": 2, "author_name": "user2", "reviewer_id": 3, "reviewer_name": "user3", "status": ReviewStatus.draft},
        ]
    for i, param in enumerate(doc_param):
        doc = Document(
            title=f"Document {i}",
            content=f"Content of document {i}",
            author_id=param["author_id"],
            author_name=param["author_name"],
            reviewer_id=param["reviewer_id"],
            reviewer_name=param["reviewer_name"],
            status=param["status"],
        )
        documents.append(doc)
    db_add_all(documents)
    return documents


def test_paginate():
    insert_documents()
    
    with Session(engine) as db:
        query = db.query(Document)
        items, pages = paginate(query=query, page=1, limit=5)
        assert len(items) == 5
        assert pages == 2

        items, pages = paginate(query=query, page=2, limit=5)
        assert len(items) == 2
        assert pages == 2


def test_create_document(mocker):
    background_tasks = mocker.Mock()

    users = get_users()
    reviewer = users["reviewer"]
    editor = users["editor"]
    db_add(reviewer)
    mock_doc = DocumentCreate(
        title="Test Document",
        content="Test Content",
        imageUrl="https://example.com/image.jpg",
        reviewerId=reviewer.id,
        action="submit_for_review",
    )

    with Session(engine) as db:
        doc = create_document( data=mock_doc,
            background_tasks=background_tasks,
            db=db,
            user=editor
        )
        assert doc.title == mock_doc.title
        assert doc.content == mock_doc.content
        assert doc.author_id == editor.id
        assert doc.author_name == editor.name

        try:
            mock_doc.reviewerId = None
            create_document(
                data=mock_doc,
                background_tasks=background_tasks,
                db=db,
                user=editor
            )
            assert False, "Should raise HTTPException"
        except HTTPException as e:
            assert e.status_code == 400
            assert e.detail == "reviewerId required for submit"

        try:
            mock_doc.reviewerId = 5
            create_document(
                data=mock_doc,
                background_tasks=background_tasks,
                db=db,
                user=editor
            )
            assert False, "Should raise HTTPException"
        except HTTPException as e:
            assert e.status_code == 400
            assert e.detail == "Invalid reviewer"


def test_list_documents(mocker):
    mock_generate_signed_url = mocker.patch("app.routers.documents.generate_signed_url", side_effect=lambda x: x)
    
    documents = insert_documents()
    users = get_users()

    admin = users["admin"]
    editor = users["editor"]
    reviewer = users["reviewer"]
    viewer = users["viewer"]
    documents = [doc for doc in documents if doc.status != ReviewStatus.deleted]

    with Session(engine) as db:
        result = list_documents(page=1, limit=10, db=db, user=admin)
        items = result["documents"]
        assert len(items) == len(documents), f"There should be {len(documents)} documents"

        result = list_documents(page=1, limit=10, db=db, user=editor)
        items = result["documents"]
        doc_len = sum( 1 if doc.status == ReviewStatus.approved or doc.author_id == editor.id else 0 for doc in documents)
        assert len(items) == doc_len, f"There should be {doc_len} documents"

        result = list_documents(page=1, limit=10, db=db, user=reviewer)
        items = result["documents"]
        doc_len = sum( 1 if doc.status == ReviewStatus.approved or doc.author_id == reviewer.id or (doc.status in [ReviewStatus.pending_review, ReviewStatus.rejected] and doc.reviewer_id == reviewer.id) else 0 for doc in documents)
        assert len(items) == doc_len, f"There should be {doc_len} documents"

        result = list_documents(page=1, limit=10, db=db, user=viewer)
        items = result["documents"]
        doc_len = sum( 1 if doc.status == ReviewStatus.approved else 0 for doc in documents)
        assert len(items) == doc_len, f"There should be {doc_len} documents"


def test_get_document(mocker):
    mock__sign_all_urls_in_content = mocker.patch("app.routers.documents._sign_all_urls_in_content", side_effect=lambda x: x)
    mock_generate_signed_url = mocker.patch("app.routers.documents.generate_signed_url", side_effect=lambda x: x)

    users = get_users()
    documents = insert_documents()

    admin = users["admin"]
    viewer = users["viewer"]
    mock_doc = documents[2]

    with Session(engine) as db:
        doc = get_document(document_id=mock_doc.id, db=db, user=admin)
        assert doc.title == mock_doc.title
        assert doc.content == mock_doc.content

        try:
            doc = get_document(document_id=mock_doc.id, db=db, user=viewer)
            assert False, "Should raise HTTPException"
        except HTTPException as e:
            assert e.status_code == 403
        
        try:
            get_document(document_id=0, db=db, user=admin)
            assert False, "Should raise HTTPException"
        except HTTPException as e:
            assert e.status_code == 404


def test_update_document(mocker):
    background_tasks = mocker.Mock()
    mock__process_image_url_to_path = mocker.patch("app.routers.documents._sign_all_urls_in_content", side_effect=lambda x: x)
    mock__sign_all_urls_in_content = mocker.patch("app.routers.documents._sign_all_urls_in_content", side_effect=lambda x: x)
    mock_generate_signed_url = mocker.patch("app.routers.documents.generate_signed_url", side_effect=lambda x: x)

    users = get_users()
    documents = insert_documents()

    editor = users["editor"]
    viewer = users["viewer"]

    mock_doc = documents[0]
    new_content = "Updated Content"
    mock_doc_update = DocumentUpdate(
        title=mock_doc.title,
        content=new_content,
        imageUrl=mock_doc.imageUrl,
        reviewerId=mock_doc.reviewerId,
        newAuthorName=mock_doc.author_name,
        newAuthorId=mock_doc.author_id,
        action="save_draft"
    )

    with Session(engine) as db:
        doc = update_document(document_id=mock_doc.id, background_tasks=background_tasks, data=mock_doc_update, db=db, user=editor)
        assert doc.title == mock_doc_update.title
        assert doc.content == mock_doc_update.content

        try:
            update_document(document_id=mock_doc.id, background_tasks=background_tasks,  data=mock_doc_update, db=db, user=viewer)
            assert False, "Should raise HTTPException"
        except HTTPException as e:
            assert e.status_code == 403


def test_delete_document():
    users = get_users()
    documents = insert_documents()

    admin = users["admin"]
    viewer = users["viewer"]

    mock_doc = documents[0]

    with Session(engine) as db:
        delete_document(document_id=mock_doc.id, db=db, user=admin)
        doc = db.query(Document).get(mock_doc.id)
        assert doc.status == ReviewStatus.deleted

        try:
            delete_document(document_id=0, db=db, user=viewer)
            assert False, "Should raise HTTPException"
        except HTTPException as e:
            assert e.status_code == 404


def test_approve(mocker):
    mock__sign_all_urls_in_content = mocker.patch("app.routers.documents._sign_all_urls_in_content", side_effect=lambda x: x)
    mock_generate_signed_url = mocker.patch("app.routers.documents.generate_signed_url", side_effect=lambda x: x)

    
    users = get_users()
    documents = insert_documents()

    reviewer = users["reviewer"]
    mock_dock = documents[0]

    with Session(engine) as db:
        db.query(Document).filter(Document.id == mock_dock.id).update({"reviewer_id": reviewer.id})

        doc = approve(document_id=mock_dock.id, db=db, user=reviewer)
        assert doc.status == ReviewStatus.approved

        db.query(Document).filter(Document.id == mock_dock.id).update({"reviewer_id": 0})
        try:
            approve(document_id=mock_dock.id, db=db, user=reviewer)
            assert False, "Should raise HTTPException"
        except HTTPException as e:
            assert e.status_code == 404


def test_reject(mocker):
    mock__sign_all_urls_in_content = mocker.patch("app.routers.documents._sign_all_urls_in_content", side_effect=lambda x: x)
    mock_generate_signed_url = mocker.patch("app.routers.documents.generate_signed_url", side_effect=lambda x: x)

    users = get_users()
    documents = insert_documents()

    reviewer = users["reviewer"]
    mock_dock = documents[0]
    payload = {"reason": "Reason for rejection"}

    with Session(engine) as db:
        db.query(Document).filter(Document.id == mock_dock.id).update({"reviewer_id": reviewer.id})

        doc = reject(document_id=mock_dock.id, payload=payload, db=db, user=reviewer)
        assert doc.status == ReviewStatus.rejected

        db.query(Document).filter(Document.id == mock_dock.id).update({"reviewer_id": 0})
        try:
            reject(document_id=mock_dock.id, payload=payload, db=db, user=reviewer)
            assert False, "Should raise HTTPException"
        except HTTPException as e:
            assert e.status_code == 404

def test_reassign(mocker):
    background_tasks = mocker.Mock()
    mock__sign_all_urls_in_content = mocker.patch("app.routers.documents._sign_all_urls_in_content", side_effect=lambda x: x)
    mock_generate_signed_url = mocker.patch("app.routers.documents.generate_signed_url", side_effect=lambda x: x)

    users = get_users()
    documents = insert_documents()

    editor = users["editor"]
    newReviewer = users["admin"]
    mock_dock = documents[0]
    payload = {"newReviewerId": newReviewer.id}

    with Session(engine) as db:
        db.add(newReviewer)
        doc = reassign(document_id=mock_dock.id, payload=payload, background_tasks=background_tasks, db=db, user=editor)
        assert doc.reviewer_id == payload["newReviewerId"]

        try:
            reassign(document_id=0, payload=payload, background_tasks=background_tasks, db=db, user=editor)
            assert False, "Should raise HTTPException"
        except HTTPException as e:
            assert e.status_code == 404


def test__process_image_url_to_path():
    url = "http://example.com/dir/image.jpg"
    path = _process_image_url_to_path(url)
    assert path == "dir/image.jpg"
