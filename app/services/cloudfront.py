import os
from datetime import datetime, timedelta, timezone
from botocore.signers import CloudFrontSigner
import rsa
from app.core.config import settings

# 1) 讀入你的 private key
with open(settings.CLOUDFRONT_PRIVATE_KEY_PATH, "rb") as key_file:
    private_key = key_file.read()

def rsa_signer(message: bytes) -> bytes:
    # 使用 rsa 套件做 SHA1 簽章
    key = rsa.PrivateKey.load_pkcs1(private_key)
    return rsa.sign(message, key, "SHA-1")

# 2) 初始化 CloudFrontSigner
cf_signer = CloudFrontSigner(
    key_id=settings.CLOUDFRONT_KEY_PAIR_ID,  # Key Pair ID
    rsa_signer=rsa_signer
)

def generate_signed_url(
    path: str,
    expire_in_seconds: int = 3600
) -> str:
    """
    path: e.g. path/to/object
    expire_in_seconds: The number of seconds until the URL expires
    """
    expire_time = datetime.now(timezone.utc) + timedelta(seconds=expire_in_seconds)
    if path and not path.startswith("/"):
        path = "/" + path
    return cf_signer.generate_presigned_url(
        settings.CLOUDFRONT_DOMAIN + path,
        date_less_than=expire_time
    )