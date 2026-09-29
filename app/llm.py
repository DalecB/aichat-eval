import asyncio
import json
import os
from collections.abc import Awaitable, Callable
from typing import Protocol

import openai
from pydantic import ValidationError

TIMEOUT_S = 10.0  # 요청 전체 한도
MAX_ATTEMPTS = 3  # 최초 시도 포함


class LLMClient(Protocol):
    model: str

    async def complete_json(self, system: str, user: str, schema: dict) -> dict: ...


class LLMServerError(Exception):
    """LLM 5xx 또는 네트워크 오류. 재시도 대상."""


class LLMFailed(Exception):
    """재시도를 다 써도 실패 → 502."""


# 재시도는 스키마 오류, LLM 5xx, 네트워크 오류일 때만 한다
RETRYABLE = (ValidationError, json.JSONDecodeError, LLMServerError)


async def run_with_budget[T](
    attempt: Callable[[], Awaitable[T]],
    *,
    timeout: float = TIMEOUT_S,
    max_attempts: int = MAX_ATTEMPTS,
) -> tuple[T, int]:
    """attempt를 한도 안에서 최대 max_attempts회 실행한다. (결과, 시도 횟수)를 반환한다.

    한도를 넘기면 asyncio.timeout이 TimeoutError를 던진다 → 504.
    """
    async with asyncio.timeout(timeout):
        for n in range(1, max_attempts + 1):
            try:
                return await attempt(), n
            except RETRYABLE as e:
                if n == max_attempts:
                    raise LLMFailed(f"{max_attempts}회 시도 모두 실패") from e


class OpenAIClient:
    def __init__(self):
        self.model = os.environ.get("OPENAI_MODEL", "gpt-6-luna")
        # 추론 모델은 추론을 꺼야 temperature=0이 허용된다.
        # 비추론 모델(gpt-4o-mini 등)은 이 파라미터 자체를 거부하므로 빈 값으로 두면 보내지 않는다.
        self._reasoning_effort = os.environ.get("OPENAI_REASONING_EFFORT", "none") or openai.omit
        # SDK 기본 재시도(2회)를 끈다. 재시도는 run_with_budget이 정책대로 한다.
        # OPENAI_API_KEY는 SDK가 환경변수에서 직접 읽는다.
        self._client = openai.AsyncOpenAI(max_retries=0)

    async def complete_json(self, system: str, user: str, schema: dict) -> dict:
        try:
            res = await self._client.chat.completions.create(
                model=self.model,
                reasoning_effort=self._reasoning_effort,
                temperature=0,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": {"name": schema["title"], "schema": schema, "strict": True},
                },
            )
        except (openai.InternalServerError, openai.APIConnectionError) as e:  # 5xx, 네트워크
            raise LLMServerError(str(e)) from e
        return json.loads(res.choices[0].message.content or "")
