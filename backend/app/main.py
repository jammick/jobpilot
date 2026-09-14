import logging
import time
import uuid
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
app = FastAPI(title="JobPilot API", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

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
