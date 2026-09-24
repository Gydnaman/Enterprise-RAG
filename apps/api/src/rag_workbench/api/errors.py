from __future__ import annotations

from dataclasses import dataclass

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


@dataclass
class ApiProblem(Exception):
    status: int
    code: str
    detail: str
    retryable: bool = False
    run_id: str | None = None


_CATALOG = {
    "invalid_request": (422, "Invalid request", False),
    "resource_not_found": (404, "Resource not found", False),
    "invalid_state_transition": (409, "Invalid state transition", False),
    "idempotency_key_conflict": (409, "Idempotency key conflict", False),
    "conversation_busy": (409, "Conversation busy", True),
    "file_too_large": (413, "File too large", False),
    "unsupported_file": (415, "Unsupported file", False),
    "file_signature_mismatch": (422, "File signature mismatch", False),
    "invalid_cursor": (422, "Invalid cursor", False),
    "invalid_sse_cursor": (400, "Invalid SSE cursor", False),
    "runner_busy": (503, "Run dispatcher busy", True),
    "storage_unavailable": (503, "Storage unavailable", True),
    "internal_error": (500, "Internal error", False),
}


def problem_response(request: Request, error: ApiProblem) -> JSONResponse:
    title = _CATALOG.get(error.code, _CATALOG["internal_error"])[1]
    body = {
        "type": "about:blank",
        "title": title,
        "status": error.status,
        "detail": error.detail,
        "code": error.code,
        "requestId": getattr(request.state, "request_id", "unknown"),
        "retryable": error.retryable,
        "runId": error.run_id,
    }
    return JSONResponse(
        status_code=error.status, content=body, media_type="application/problem+json"
    )


async def handle_api_problem(request: Request, exc: ApiProblem) -> JSONResponse:
    return problem_response(request, exc)


async def handle_validation_error(request: Request, _exc: RequestValidationError) -> JSONResponse:
    return problem_response(
        request, ApiProblem(422, "invalid_request", "The request did not pass validation.")
    )


async def handle_unexpected_error(request: Request, _exc: Exception) -> JSONResponse:
    return problem_response(
        request, ApiProblem(500, "internal_error", "The request could not be completed.")
    )
