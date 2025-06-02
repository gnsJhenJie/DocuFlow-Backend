from sqlalchemy.orm import Session
from fastapi import HTTPException
from tests.conftest import db_add, db_add_all
from app.db.models import Document, Role, User
from app.db.session import engine
from app.schemas.document import DocumentCreate, DocumentUpdate, ReviewStatus
from app.routers.documents import (
    paginate,
    create_document,
    list_documents,
    get_document,
    update_document,
    delete_document,
    approve,
    reject,
    reassign,
    upload_endpoint,
    _process_image_url_to_path,
    _process_image_urls_in_content,
    _sign_all_urls_in_content,
)


def insert_documents(num=7):
    documents = []
    for i in range(num):
        doc = Document(
            title=f"Document {i}",
            content=f"Content of document {i}",
            author_id=1,
            author_name="user1",
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
    reviewer = User(
        id=1,
        name="Test Reviewer",
        email="reviewer@example.com",
        hashed_password="hashed_password",
        role=Role.reviewer,
    )
    creator = User(
        id=2,
        name="Test User",
        email="test@example.com",
        hashed_password="hashed_password",
        role=Role.editor,
    )
    db_add(reviewer)

    mock_doc = DocumentCreate(
        title="Test Document",
        content="Test Content",
        imageUrl="https://example.com/image.jpg",
        reviewerId=1,
        action="submit_for_review",
    )

    with Session(engine) as db:
        doc = create_document(
            data=mock_doc, background_tasks=background_tasks, db=db, user=creator
        )
        assert doc.title == mock_doc.title
        assert doc.content == mock_doc.content
        assert doc.author_id == creator.id
        assert doc.author_name == creator.name

        try:
            mock_doc.reviewerId = None
            create_document(
                data=mock_doc, background_tasks=background_tasks, db=db, user=creator
            )
            assert False, "Should raise HTTPException"
        except HTTPException as e:
            assert e.status_code == 400
            assert e.detail == "reviewerId required for submit"

        try:
            mock_doc.reviewerId = 3
            create_document(
                data=mock_doc, background_tasks=background_tasks, db=db, user=creator
            )
            assert False, "Should raise HTTPException"
        except HTTPException as e:
            assert e.status_code == 400
            assert e.detail == "Invalid reviewer"


def test_get_document(mocker):
    mock__sign_all_urls_in_content = mocker.patch(
        "app.routers.documents._sign_all_urls_in_content", side_effect=lambda x: x
    )
    mock_generate_signed_url = mocker.patch(
        "app.routers.documents.generate_signed_url", side_effect=lambda x: x
    )

    admin = User(
        id=1,
        name="Test Admin",
        email="admin@example.com",
        hashed_password="hashed_password",
        role=Role.admin,
    )
    user = User(
        id=2,
        name="Test User",
        email="test@example.com",
        hashed_password="hashed_password",
        role=Role.viewer,
    )
    documents = insert_documents()

    mock_doc = documents[0]

    with Session(engine) as db:
        doc = get_document(document_id=mock_doc.id, db=db, user=admin)
        assert doc.title == mock_doc.title
        assert doc.content == mock_doc.content

        try:
            doc = get_document(document_id=mock_doc.id, db=db, user=user)
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
    mock__process_image_url_to_path = mocker.patch(
        "app.routers.documents._sign_all_urls_in_content", side_effect=lambda x: x
    )
    mock__sign_all_urls_in_content = mocker.patch(
        "app.routers.documents._sign_all_urls_in_content", side_effect=lambda x: x
    )
    mock_generate_signed_url = mocker.patch(
        "app.routers.documents.generate_signed_url", side_effect=lambda x: x
    )

    editor = User(
        id=1,
        name="Test User",
        email="test@example.com",
        hashed_password="hashed_password",
        role=Role.editor,
    )
    viewer = User(
        id=2,
        name="Test User",
        email="test@example.com",
        hashed_password="hashed_password",
        role=Role.viewer,
    )
    documents = insert_documents()

    mock_doc = documents[0]
    new_content = "Updated Content"
    mock_doc_update = DocumentUpdate(
        title=mock_doc.title,
        content=new_content,
        imageUrl=mock_doc.imageUrl,
        reviewerId=mock_doc.reviewerId,
        newAuthorName=mock_doc.author_name,
        newAuthorId=mock_doc.author_id,
        action="save_draft",
    )

    with Session(engine) as db:
        doc = update_document(
            document_id=mock_doc.id,
            background_tasks=background_tasks,
            data=mock_doc_update,
            db=db,
            user=editor,
        )
        assert doc.title == mock_doc_update.title
        assert doc.content == mock_doc_update.content

        try:
            update_document(
                document_id=mock_doc.id,
                background_tasks=background_tasks,
                data=mock_doc_update,
                db=db,
                user=viewer,
            )
            assert False, "Should raise HTTPException"
        except HTTPException as e:
            assert e.status_code == 403


def test_delete_document():
    admin = User(
        id=1,
        name="Test Admin",
        email="admin@example.com",
        hashed_password="hashed_password",
        role=Role.admin,
    )
    viewer = User(
        id=2,
        name="Test User",
        email="test@example.com",
        hashed_password="hashed_password",
        role=Role.viewer,
    )
    documents = insert_documents()

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
    mock__sign_all_urls_in_content = mocker.patch(
        "app.routers.documents._sign_all_urls_in_content", side_effect=lambda x: x
    )
    mock_generate_signed_url = mocker.patch(
        "app.routers.documents.generate_signed_url", side_effect=lambda x: x
    )

    reviewer = User(
        id=1,
        name="Test Reviewer",
        email="reviewer@example.com",
        hashed_password="hashed_password",
        role=Role.reviewer,
    )

    documents = insert_documents()

    mock_dock = documents[0]

    with Session(engine) as db:
        db.query(Document).filter(Document.id == mock_dock.id).update(
            {"reviewer_id": reviewer.id}
        )

        doc = approve(document_id=mock_dock.id, db=db, user=reviewer)
        assert doc.status == ReviewStatus.approved

        db.query(Document).filter(Document.id == mock_dock.id).update(
            {"reviewer_id": 0}
        )
        try:
            approve(document_id=mock_dock.id, db=db, user=reviewer)
            assert False, "Should raise HTTPException"
        except HTTPException as e:
            assert e.status_code == 404


def test_reject(mocker):
    mock__sign_all_urls_in_content = mocker.patch(
        "app.routers.documents._sign_all_urls_in_content", side_effect=lambda x: x
    )
    mock_generate_signed_url = mocker.patch(
        "app.routers.documents.generate_signed_url", side_effect=lambda x: x
    )

    reviewer = User(
        id=1,
        name="Test Reviewer",
        email="reviewer@example.com",
        hashed_password="hashed_password",
        role=Role.reviewer,
    )

    documents = insert_documents()

    mock_dock = documents[0]
    payload = {"reason": "Reason for rejection"}

    with Session(engine) as db:
        db.query(Document).filter(Document.id == mock_dock.id).update(
            {"reviewer_id": reviewer.id}
        )

        doc = reject(document_id=mock_dock.id, payload=payload, db=db, user=reviewer)
        assert doc.status == ReviewStatus.rejected

        db.query(Document).filter(Document.id == mock_dock.id).update(
            {"reviewer_id": 0}
        )
        try:
            reject(document_id=mock_dock.id, payload=payload, db=db, user=reviewer)
            assert False, "Should raise HTTPException"
        except HTTPException as e:
            assert e.status_code == 404


def test_reassign(mocker):
    background_tasks = mocker.Mock()
    mock__sign_all_urls_in_content = mocker.patch(
        "app.routers.documents._sign_all_urls_in_content", side_effect=lambda x: x
    )
    mock_generate_signed_url = mocker.patch(
        "app.routers.documents.generate_signed_url", side_effect=lambda x: x
    )

    editor = User(
        id=1,
        name="Test User",
        email="test@example.com",
        hashed_password="hashed_password",
        role=Role.editor,
    )
    newReviewer = User(
        id=2,
        name="Test Reviewer",
        email="reviewer@example.com",
        hashed_password="hashed_password",
        role=Role.reviewer,
    )
    documents = insert_documents()

    mock_dock = documents[0]
    payload = {"newReviewerId": 2}

    with Session(engine) as db:
        db.add(newReviewer)
        doc = reassign(
            document_id=mock_dock.id,
            payload=payload,
            background_tasks=background_tasks,
            db=db,
            user=editor,
        )
        assert doc.reviewer_id == payload["newReviewerId"]

        try:
            reassign(
                document_id=0,
                payload=payload,
                background_tasks=background_tasks,
                db=db,
                user=editor,
            )
            assert False, "Should raise HTTPException"
        except HTTPException as e:
            assert e.status_code == 404
