"""판정: 요청·응답 스키마, 프롬프트 로드, judge 함수.

judge 함수는 시도 1회분이다(프롬프트 → LLM 호출 → 파싱·검증 → 집계).
재시도·타임아웃은 호출하는 쪽이 run_with_budget으로 감싼다.
"""

import json
from datetime import datetime
from functools import cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator

from app.llm import LLMClient

HALLUCINATION_PROMPT = "hallucination_v3"
RESOLUTION_PROMPT = "resolution_v4"
PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


@cache
def load_prompt(version: str) -> str:
    return (PROMPTS_DIR / f"{version}.md").read_text(encoding="utf-8")


# --- hallucination ---


class ContextDoc(BaseModel):
    id: str
    text: str


class HallucinationRequest(BaseModel):
    context: list[ContextDoc]  # 비어 있으면 insufficient_context
    question: str
    answer: str


class Claim(BaseModel):
    model_config = ConfigDict(extra="forbid")  # OpenAI strict JSON schema 요구사항

    claim: str
    answer_quote: str  # 이 주장이 나온 답변 원문 구간
    supported: bool
    evidence_id: str | None
    reason: str

    @field_validator("answer_quote")
    @classmethod
    def _quote_must_be_in_answer(cls, v: str, info: ValidationInfo) -> str:
        # 답변이 아니라 근거 문서에서 주장을 뽑는 실수를 막는다. 실패하면 재시도된다.
        answer = (info.context or {}).get("answer")
        if answer is not None and "".join(v.split()) not in "".join(answer.split()):
            raise ValueError("answer_quote가 답변 원문에 없다")
        return v


class HallucinationJudgment(BaseModel):
    """LLM이 반환하는 형태. verdict는 LLM이 아니라 코드가 집계한다."""

    model_config = ConfigDict(extra="forbid")

    claims: list[Claim]


class HallucinationResult(BaseModel):
    verdict: Literal["grounded", "hallucinated", "insufficient_context", "no_claims"]
    score: float  # 뒷받침된 주장 비율
    claims: list[Claim]


class HallucinationResponse(HallucinationResult):
    model: str
    prompt_version: str
    latency_ms: int


async def judge_hallucination(req: HallucinationRequest, llm: LLMClient) -> HallucinationResult:
    if not req.context:  # 근거가 없으면 판정할 수 없다
        return HallucinationResult(verdict="insufficient_context", score=0.0, claims=[])

    raw = await llm.complete_json(
        load_prompt(HALLUCINATION_PROMPT),
        json.dumps(req.model_dump(), ensure_ascii=False),
        HallucinationJudgment.model_json_schema(),
    )
    # 스키마 또는 answer_quote 검증에 실패하면 재시도된다
    claims = HallucinationJudgment.model_validate(raw, context={"answer": req.answer}).claims

    if not claims:  # 확인할 사실이 없는 답변. 「틀린 말 없음」을 grounded로 보고하지 않는다
        return HallucinationResult(verdict="no_claims", score=0.0, claims=[])

    # 주장이 하나라도 뒷받침되지 않으면 답변 전체가 hallucinated
    supported = sum(c.supported for c in claims)
    return HallucinationResult(
        verdict="grounded" if supported == len(claims) else "hallucinated",
        score=supported / len(claims),
        claims=claims,
    )


# --- resolution ---


class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: str
    timestamp: datetime


class ResolutionRequest(BaseModel):
    messages: list[Message] = Field(min_length=1)
    ended_reason: Literal["user_closed", "timeout"]


class ResolutionSignals(BaseModel):
    """LLM이 반환하는 관찰값. 상태는 LLM이 아니라 코드가 우선순위대로 정한다."""

    model_config = ConfigDict(extra="forbid")

    has_question: bool  # 고객이 질문이나 요청을 했다
    escalation: bool  # 봇이 답을 못 한다고 인정 / 권한 밖 요청 / 상담원 요청
    repeated_question: bool  # 같은 취지의 질문을 2회 이상
    answered: bool  # 고객의 질문에 봇이 완결된 답을 했다 (마지막 질문 포함)
    accepted: bool  # 답을 받은 뒤 고객이 수용 신호를 보냈다
    confidence: float
    reason: str


class ResolutionResult(BaseModel):
    status: Literal["resolved", "unresolved", "needs_review", "escalation_needed"]
    confidence: float
    reason: str


class ResolutionResponse(ResolutionResult):
    model: str
    prompt_version: str
    latency_ms: int


async def judge_resolution(req: ResolutionRequest, llm: LLMClient) -> ResolutionResult:
    raw = await llm.complete_json(
        load_prompt(RESOLUTION_PROMPT),
        json.dumps(req.model_dump(mode="json"), ensure_ascii=False),
        ResolutionSignals.model_json_schema(),
    )
    s = ResolutionSignals.model_validate(raw)

    # 사람이 봐야 하는 신호일수록 먼저: escalation_needed > needs_review > resolved > unresolved
    bot_ended_by_timeout = req.ended_reason == "timeout" and req.messages[-1].role == "assistant"
    if s.escalation:
        status = "escalation_needed"
    elif s.repeated_question:
        status = "needs_review"
    elif s.has_question and s.answered and (s.accepted or bot_ended_by_timeout):
        status = "resolved"
    else:
        status = "unresolved"
    return ResolutionResult(status=status, confidence=s.confidence, reason=s.reason)
