import logging
import time
import uuid
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import router
from app.core.config import get_settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
settings = get_settings()
app = FastAPI(title="JobPilot API", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.middleware("http")
async def request_log(request: Request, call_next):
    request_id, started = str(uuid.uuid4()), time.perf_counter()
    try: response = await call_next(request)
    except Exception:
        logging.exception("request failed id=%s path=%s", request_id, request.url.path)
        return JSONResponse(status_code=500, content={"detail": "服务器内部错误", "request_id": request_id})
    response.headers["X-Request-ID"] = request_id
    logging.info("request id=%s method=%s path=%s status=%s duration_ms=%d", request_id, request.method, request.url.path, response.status_code, (time.perf_counter()-started)*1000)
    return response

@app.get("/health")
def health(): return {"status": "ok"}

app.include_router(router, prefix="/api")

# Render runs the compiled React app and API from one origin. Local Compose
# still uses Nginx because SERVE_FRONTEND defaults to false.
static_dir = Path(settings.static_dir)
if settings.serve_frontend and (static_dir / "index.html").is_file():
    assets_dir = static_dir / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        candidate = (static_dir / path).resolve()
        if candidate.is_relative_to(static_dir.resolve()) and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(static_dir / "index.html")
