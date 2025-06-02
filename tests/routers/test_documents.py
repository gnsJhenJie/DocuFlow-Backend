from fastapi import HTTPException
from tests.conftest import db_add, db_add_all
from app.db.models import Document, Role, User
from app.db.session import get_db
from app.schemas.document import DocumentCreate, ReviewStatus
from app.routers.documents import paginate, create_document, list_documents, get_document, update_document, delete_document, approve, reassign, upload_endpoint, _process_image_url_to_path, _process_image_urls_in_content, _sign_all_urls_in_content

def insert_documents(num=7):
    documents = []
    for i in range(num):
        doc = Document(
            title=f"Document {i}",
            content=f"Content of document {i}",
            author_id=1,
            author_name="user1"
        )
        documents.append(doc)
    db_add_all(documents)
    return documents


def test_paginate():
    insert_documents()
    
    db = next(get_db())
    query = db.query(Document)
    items, pages = paginate(query=query, page=1, limit=5)
    assert len(items) == 5
    assert pages == 2

    items, pages = paginate(query=query, page=2, limit=5)
    assert len(items) == 2
    assert pages == 2
