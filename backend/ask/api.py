"""FastAPI router — POST /api/v1/ask (grounded contextual Ask).

One grounded question → one structured answer. This is not an autonomous
agent: the backend never executes actions, never mutates application state,
and never invents evidence. The flow is:

    validate request (FastAPI + Pydantic → structured 422)
      → verify the authenticated caller can access the referenced work
      → resolve client-selected Insight IDs to server-authoritative evidence
      → build the grounded prompt from canonical evidence
      → call the LLMProvider (finite timeout)
      → validate model output with Pydantic
      → deterministically drop ungrounded references/actions
      → return a schema-valid AskResponse
"""

import logging
import time

from fastapi import APIRouter, Depends, HTTPException, Request
from starlette.concurrency import run_in_threadpool

from auth_utils import limiter, verify_token
from domain.repositories import WorkRepo, get_supabase

from .config import LLMSettings, load_llm_settings
from .contracts import AskRequest, AskResponse
from .evidence import load_canonical_ask_context
from .grounding import build_grounded_prompts
from .providers import (
    AskModelOutputError,
    AskProviderConfigurationError,
    AskProviderError,
    AskProviderTimeoutError,
    AskProviderUnavailableError,
    LLMProvider,
    build_provider,
)
from .sanitize import sanitize_response

router = APIRouter(prefix="/api/v1")
logger = logging.getLogger("ask.api")


@router.post("/ask", response_model=AskResponse)
@limiter.limit(lambda: load_llm_settings().rate_limit)
async def create_ask(
    body: AskRequest,
    request: Request,
    auth=Depends(verify_token),
) -> AskResponse:
    settings: LLMSettings = load_llm_settings()
    started = time.perf_counter()
    req_id = request.headers.get("x-request-id") or "none"
    owner_id = auth.user.id
    sb = get_supabase()
    if not sb:
        raise HTTPException(status_code=500, detail="Supabase not configured")

    # Authorization: the client-supplied workId is never treated as
    # authorization. Reuse the existing ownership check exactly as the domain
    # API does — the caller must own the project the work belongs to.
    try:
        work = await run_in_threadpool(WorkRepo(sb).get, body.context.workId, owner_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail="Work access denied") from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Work not found") from exc
    if work is None:
        raise HTTPException(status_code=404, detail="Work not found")

    # The browser chooses which persisted Insight IDs are relevant to its
    # current view, but it is not authoritative for their claim/kind/span or
    # Work membership. Resolve those fields from server-owned persistence and
    # use the resulting context consistently for both prompting and sanitizing.
    canonical_context = await run_in_threadpool(load_canonical_ask_context, sb, body.context)

    provider: LLMProvider | None = build_provider(settings, client=request.app.state.http_client)
    if provider is None:
        logger.warning(
            "ask_provider_unconfigured",
            extra={
                "req_id": req_id,
                "duration_ms": round((time.perf_counter() - started) * 1000, 2),
            },
        )
        raise HTTPException(
            status_code=503,
            detail="Ask is not configured. Contact your administrator.",
        )

    system_prompt, user_prompt = build_grounded_prompts(body.question, canonical_context)
    provider_started = time.perf_counter()
    pre_provider_ms = round((provider_started - started) * 1000, 2)

    try:
        response = await provider.complete_structured(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_model=AskResponse,
        )
    except AskProviderConfigurationError as exc:
        logger.warning(
            "ask_provider_configuration_error",
            extra={"req_id": req_id, "model": settings.provider_identifier},
        )
        raise HTTPException(status_code=503, detail="Ask is not configured.") from exc
    except AskProviderTimeoutError as exc:
        logger.warning(
            "ask_provider_timeout",
            extra={
                "req_id": req_id,
                "model": settings.provider_identifier,
                "pre_provider_ms": pre_provider_ms,
                "provider_ms": round((time.perf_counter() - provider_started) * 1000, 2),
            },
        )
        raise HTTPException(status_code=504, detail="Ask timed out.") from exc
    except AskProviderUnavailableError as exc:
        logger.warning(
            "ask_provider_unavailable",
            extra={
                "req_id": req_id,
                "model": settings.provider_identifier,
                "pre_provider_ms": pre_provider_ms,
                "provider_ms": round((time.perf_counter() - provider_started) * 1000, 2),
            },
        )
        raise HTTPException(status_code=502, detail="Ask provider unavailable.") from exc
    except AskModelOutputError as exc:
        logger.warning(
            "ask_model_output_rejected",
            extra={
                "req_id": req_id,
                "model": settings.provider_identifier,
                "provider_ms": round((time.perf_counter() - provider_started) * 1000, 2),
            },
        )
        raise HTTPException(status_code=502, detail="Ask returned an invalid response.") from exc
    except AskProviderError as exc:
        logger.warning(
            "ask_provider_error",
            extra={
                "req_id": req_id,
                "model": settings.provider_identifier,
                "provider_ms": round((time.perf_counter() - provider_started) * 1000, 2),
            },
        )
        raise HTTPException(status_code=502, detail="Ask failed.") from exc

    provider_ms = round((time.perf_counter() - provider_started) * 1000, 2)

    # Deterministic sanitization — a single invalid optional reference/action
    # never fails the whole answer; it is dropped. Use the same canonical
    # evidence context the provider saw, never the untrusted request copy.
    safe = sanitize_response(response, canonical_context)

    logger.info(
        "ask_completed",
        extra={
            "req_id": req_id,
            "duration_ms": round((time.perf_counter() - started) * 1000, 2),
            "pre_provider_ms": pre_provider_ms,
            "provider_ms": provider_ms,
            "model": settings.provider_identifier,
            "references": len(safe.references),
            "actions": len(safe.suggestedActions or []),
        },
    )
    return safe
