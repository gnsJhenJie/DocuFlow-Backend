from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import auth, users, documents, upload_router
from app.core.config import settings
from fastapi_proxiedheadersmiddleware import ProxiedHeadersMiddleware

app = FastAPI(title="DocuFlow API", redirect_slashes=False)
app.add_middleware(ProxiedHeadersMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.FRONTEND_URL,
        "http://localhost:3000",
        "https://localhost:3000",
        "http://localhost:9002",
        "http://localhost:8000",
        "http://localhost:8001",
        "https://docuflow.gnsjhenjie.ninja",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["health"])
async def health_check():
    return {"status": "ok"}


app.include_router(auth)
app.include_router(users)
app.include_router(documents)
app.include_router(upload_router)
