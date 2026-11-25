import logging
import time
import uuid

from fastapi import FastAPI, Header, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

from .config import Settings
from .db import Database
from .llm import AllProvidersUnavailable, LLMGateway, parse_simulation

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("app")

settings = Settings()
db = Database(settings.db_path)
gateway = LLMGateway(settings)

app = FastAPI(title="LLM Chatbot", docs_url="/docs")
@app.middleware("http")
async def request_context(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or f"req_{uuid.uuid4().hex[:12]}"
    started = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    log.info("request_id=%s method=%s path=%s status=%s latency_ms=%s", request_id, request.method, request.url.path, response.status_code, int((time.perf_counter()-started)*1000))
    return response

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=128)
    message: str
    system_prompt: str | None = Field(default=None, max_length=4000)

    @field_validator("message")
    @classmethod
    def _message(cls, v: str) -> str:
        v = v.strip()
        if not 1 <= len(v) <= 4000:
            raise ValueError("message must be 1-4000 characters after trimming")
        return v


@app.exception_handler(RequestValidationError)
async def validation_handler(_: Request, exc: RequestValidationError):
    detail = [{"loc": list(e.get("loc", [])), "msg": str(e.get("msg", "")), "type": e.get("type", "")}
              for e in exc.errors()]
    return JSONResponse(status_code=422, content={"detail": detail})


@app.exception_handler(Exception)
async def unhandled_handler(_: Request, exc: Exception):
    log.exception("unhandled error")
    return JSONResponse(status_code=500, content={"detail": "internal server error"})


@app.get("/health")
def health():
    try:
        db.ping()
        ok = len(gateway.keys) >= 2
    except Exception:
        ok = False
    body = {"status": "ok" if ok else "error", "keys_configured": len(gateway.keys),
            "cache_enabled": gateway.cache_enabled}
    return JSONResponse(status_code=200 if ok else 503, content=body)


@app.post("/chat")
async def chat(req: ChatRequest, x_simulate_failure: str | None = Header(default=None)):
    started = time.perf_counter()
    sim = parse_simulation(x_simulate_failure) if settings.enable_failure_simulation else {}

    system_prompt = req.system_prompt.strip() if req.system_prompt and req.system_prompt.strip() else None
    effective_system = system_prompt or db.get_system_prompt(req.session_id) or settings.default_system_prompt
    messages = (
        [{"role": "system", "content": effective_system}]
        + db.get_history(req.session_id)
        + [{"role": "user", "content": req.message}]
    )

    try:
        result = await gateway.complete(messages, sim)
    except AllProvidersUnavailable:
        return JSONResponse(status_code=503, content={"detail": "all providers unavailable"})

    metadata = {
        "resolution_source": result.source,
        "model": result.model,
        "latency_ms": max(0, int((time.perf_counter() - started) * 1000)),
        "input_tokens": result.input_tokens,
        "output_tokens": result.output_tokens,
        "key_id": result.key_id,
        "fallback_attempts": result.fallback_attempts,
    }
    db.save_exchange(req.session_id, system_prompt, req.message, result.reply, metadata)
    return {"session_id": req.session_id, "reply": result.reply, "metadata": metadata}


@app.get("/sessions/{session_id}/messages")
def session_messages(session_id: str):
    msgs = db.get_messages(session_id)
    if msgs is None:
        return JSONResponse(status_code=404, content={"detail": "session not found"})
    return {"session_id": session_id, "messages": msgs}
