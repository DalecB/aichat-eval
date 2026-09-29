import json
import logging
import time
from functools import cache
from typing import Annotated

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse

from app import judges
from app.judges import (
    HallucinationRequest,
    HallucinationResponse,
    ResolutionRequest,
    ResolutionResponse,
)
from app.llm import LLMClient, LLMFailed, OpenAIClient, run_with_budget

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("aichat_eval")

app = FastAPI(title="aichat-eval")


@cache
def get_llm() -> LLMClient:
    return OpenAIClient()


LLM = Annotated[LLMClient, Depends(get_llm)]


def _log(**fields) -> None:
    log.info(json.dumps(fields, ensure_ascii=False))


def _ms(start: float) -> int:
    return round((time.perf_counter() - start) * 1000)


@app.exception_handler(TimeoutError)
async def _timeout(request: Request, exc: TimeoutError) -> JSONResponse:
    _log(endpoint=request.url.path, error="timeout")
    return JSONResponse(status_code=504, content={"detail": "LLM timeout"})


@app.exception_handler(LLMFailed)
async def _failed(request: Request, exc: LLMFailed) -> JSONResponse:
    _log(endpoint=request.url.path, error="llm_failed", cause=repr(exc.__cause__))
    return JSONResponse(status_code=502, content={"detail": str(exc)})


@app.get("/healthz")
async def healthz() -> dict:
    return {"status": "ok"}


@app.post("/eval/hallucination")
async def eval_hallucination(req: HallucinationRequest, llm: LLM) -> HallucinationResponse:
    start = time.perf_counter()
    result, attempts = await run_with_budget(lambda: judges.judge_hallucination(req, llm))
    res = HallucinationResponse(
        **result.model_dump(),
        model=llm.model,
        prompt_version=judges.HALLUCINATION_PROMPT,
        latency_ms=_ms(start),
    )
    _log(
        endpoint="/eval/hallucination",
        model=res.model,
        prompt_version=res.prompt_version,
        verdict=res.verdict,
        latency_ms=res.latency_ms,
        attempts=attempts,
    )
    return res


@app.post("/eval/resolution")
async def eval_resolution(req: ResolutionRequest, llm: LLM) -> ResolutionResponse:
    start = time.perf_counter()
    result, attempts = await run_with_budget(lambda: judges.judge_resolution(req, llm))
    res = ResolutionResponse(
        **result.model_dump(),
        model=llm.model,
        prompt_version=judges.RESOLUTION_PROMPT,
        latency_ms=_ms(start),
    )
    _log(
        endpoint="/eval/resolution",
        model=res.model,
        prompt_version=res.prompt_version,
        status=res.status,
        latency_ms=res.latency_ms,
        attempts=attempts,
    )
    return res
