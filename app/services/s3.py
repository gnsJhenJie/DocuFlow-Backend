import boto3
from uuid import uuid4
from app.core.config import settings
from fastapi import UploadFile, HTTPException

s3_client = boto3.client(
    "s3",
    aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
)

async def upload_image(file: UploadFile) -> str:
    key = f"images/{uuid4()}_{file.filename}"
    try:
        s3_client.upload_fileobj(file.file, settings.AWS_S3_BUCKET, key)
        return f"https://{settings.AWS_S3_BUCKET}.s3.amazonaws.com/{key}"
    except Exception as e:
        raise HTTPException(status_code=500, detail="Image upload failed")
