import boto3
import rsa
from botocore.signers import CloudFrontSigner
from uuid import uuid4
from app.core.config import settings
from fastapi import UploadFile, HTTPException
from datetime import datetime, timedelta, timezone

if settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY:
    # local 開發 （或你把 credentials 寫在 .env）
    s3_client = boto3.client(
        "s3",
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name="ap-northeast-1",
    )
else:
    # 在 ECS/Fargate 上，boto3 會自動使用 Task Role 的暫時憑證
    s3_client = boto3.client(
        "s3",
        region_name="ap-northeast-1",
    )


async def upload_image(file: UploadFile) -> str:
    key = f"images/{uuid4()}_{file.filename}"
    try:
        s3_client.upload_fileobj(file.file, settings.AWS_S3_BUCKET, key)
        return key
    except Exception as e:
        print(f"Error uploading file to S3: {e}")
        raise HTTPException(status_code=500, detail="Image upload failed")
