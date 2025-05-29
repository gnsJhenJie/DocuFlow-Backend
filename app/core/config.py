from pydantic import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str = ""
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    JWT_SECRET_KEY: str = ""
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_S3_BUCKET: str = ""
    FRONTEND_URL: str = ""
    CLOUDFRONT_DOMAIN: str = ""
    CLOUDFRONT_PRIVATE_KEY_PATH: str = ""
    CLOUDFRONT_KEY_PAIR_ID: str = ""

    class Config:
        env_file = ".env"

settings = Settings()