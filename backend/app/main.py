import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text

from .config import get_settings
from .db import engine
from .ratelimit import limiter
from .routers import auth, posts, users

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

settings = get_settings()
for sub in ("avatars", "posts"):
    (Path(settings.media_dir) / sub).mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Chirp API", docs_url="/api/docs", redoc_url=None, openapi_url="/api/openapi.json")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
# Allow multipart overhead on top of the image limit.
MAX_BODY_BYTES = settings.max_upload_bytes + 256 * 1024


@app.middleware("http")
async def guard_and_headers(request: Request, call_next):
    path = request.url.path
    if request.method in UNSAFE_METHODS and path.startswith("/api/"):
        # CSRF defence: browsers can't send custom headers cross-site without a CORS
        # preflight, and this API doesn't allow any cross-origin requests.
        if request.headers.get("x-requested-with") != "fetch":
            return JSONResponse({"detail": "Missing X-Requested-With header"}, status_code=403)
        length = request.headers.get("content-length")
        if length and length.isdigit() and int(length) > MAX_BODY_BYTES:
            return JSONResponse({"detail": f"Request too large (max {settings.max_upload_mb} MB)"}, status_code=413)

    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    if path.startswith("/media/") and response.status_code == 200:
        # File names are random and never reused, so they can be cached forever.
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    elif path.startswith("/api/"):
        response.headers.setdefault("Cache-Control", "no-store")
    return response


app.include_router(auth.router)
app.include_router(users.router)
app.include_router(posts.router)


@app.get("/api/health", tags=["meta"])
def health() -> dict:
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return {"status": "ok"}


app.mount("/media", StaticFiles(directory=settings.media_dir), name="media")
