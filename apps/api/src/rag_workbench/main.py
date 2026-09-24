from __future__ import annotations

import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from starlette.exceptions import HTTPException as StarletteHTTPException

from rag_workbench.adapters.database import SessionFactory
from rag_workbench.adapters.files import LocalFileStore
from rag_workbench.adapters.fixtures import seed_fixtures
from rag_workbench.api.chat_routes import router as chat_router
from rag_workbench.api.errors import (
    ApiProblem,
    handle_api_problem,
    handle_unexpected_error,
    handle_validation_error,
    problem_response,
)
from rag_workbench.api.knowledge_routes import router as knowledge_router
from rag_workbench.api.retrieval_routes import router as retrieval_router
from rag_workbench.api.run_routes import router as run_router
from rag_workbench.api.schemas import Problem
from rag_workbench.application.dispatcher import InProcessRunDispatcher
from rag_workbench.application.recovery import fail_interrupted_dispatcher_runs, reconcile_uploads
from rag_workbench.config import settings

API_RESPONSES = {code: {"model": Problem} for code in (400, 404, 409, 413, 415, 422, 500, 503)}
MULTIPART_OVERHEAD_ALLOWANCE_BYTES = 64 * 1024


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.rag_mode != "mock":
        raise RuntimeError("Stage A supports only the validated mock provider profile")
    file_store = LocalFileStore(settings.upload_dir)
    app.state.settings = settings
    app.state.session_factory = SessionFactory
    app.state.file_store = file_store
    app.state.dispatcher = InProcessRunDispatcher(SessionFactory, capacity=32)
    with SessionFactory() as session:
        seed_fixtures(session)
    reconcile_uploads(SessionFactory, file_store)
    fail_interrupted_dispatcher_runs(SessionFactory)
    await app.state.dispatcher.start()
    try:
        yield
    finally:
        await app.state.dispatcher.shutdown()
        fail_interrupted_dispatcher_runs(SessionFactory)


app = FastAPI(
    title="Enterprise RAG Workbench API",
    version="0.1.0",
    description="Stage A DEMO / MOCK workbench API. User uploads are stored unprocessed.",
    openapi_url="/api/v1/openapi.json",
    lifespan=lifespan,
    responses=API_RESPONSES,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.web_origins),
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Idempotency-Key", "Last-Event-ID"],
    expose_headers=["X-Request-ID"],
)


@app.middleware("http")
async def request_context(request: Request, call_next):
    supplied = request.headers.get("X-Request-ID")
    request.state.request_id = (
        supplied[:128]
        if supplied and supplied.isascii() and supplied.isprintable()
        else str(uuid.uuid4())
    )
    path_parts = request.url.path.split("/")
    is_document_upload = (
        request.method == "POST"
        and len(path_parts) == 6
        and path_parts[1:3] == ["api", "v1"]
        and path_parts[3] == "knowledge-bases"
        and bool(path_parts[4])
        and path_parts[5] == "documents"
    )
    if is_document_upload:
        content_length = request.headers.get("content-length")
        if content_length is None or not content_length.isdecimal():
            response = problem_response(
                request,
                ApiProblem(
                    400, "invalid_request", "Upload requests must include a valid Content-Length."
                ),
            )
            response.headers["X-Request-ID"] = request.state.request_id
            return response
        request_limit = settings.upload_max_bytes + MULTIPART_OVERHEAD_ALLOWANCE_BYTES
        if int(content_length) > request_limit:
            response = problem_response(
                request,
                ApiProblem(
                    413, "file_too_large", "The multipart upload exceeds the allowed file size."
                ),
            )
            response.headers["X-Request-ID"] = request.state.request_id
            return response
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
    return response


app.add_exception_handler(ApiProblem, handle_api_problem)
app.add_exception_handler(RequestValidationError, handle_validation_error)


async def handle_http_exception(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    code = "resource_not_found" if exc.status_code == 404 else "invalid_request"
    error = ApiProblem(
        exc.status_code,
        code,
        "The requested resource was not found."
        if exc.status_code == 404
        else "The request could not be completed.",
    )
    return problem_response(request, error)


app.add_exception_handler(StarletteHTTPException, handle_http_exception)
app.add_exception_handler(Exception, handle_unexpected_error)


@app.get("/health/live", tags=["health"])
def health_live():
    return {"status": "alive"}


@app.get("/health/ready", tags=["health"])
def health_ready():
    try:
        with SessionFactory() as session:
            session.execute(text("SELECT 1"))
            current = session.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one_or_none()
        if current != "0001_stage_a":
            return JSONResponse(
                status_code=503,
                content={"status": "not_ready", "schemaRevision": current, "ready": False},
            )
        return {"status": "ready", "schemaRevision": current, "ready": True}
    except Exception:
        return JSONResponse(status_code=503, content={"status": "not_ready", "ready": False})


v1 = "/api/v1"
app.include_router(knowledge_router, prefix=v1, tags=["knowledge"])
app.include_router(retrieval_router, prefix=v1, tags=["retrieval"])
app.include_router(chat_router, prefix=v1, tags=["chat"])
app.include_router(run_router, prefix=v1, tags=["runs"])
