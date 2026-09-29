import asyncio
import json

import pytest
from fastapi.testclient import TestClient

from app import judges
from app.llm import LLMFailed, LLMServerError, run_with_budget
from app.main import app, get_llm


class FakeLLM:
    """미리 넣어둔 응답(dict) 또는 예외를 순서대로 돌려준다. 네트워크를 쓰지 않는다."""

    model = "fake"

    def __init__(self):
        self.responses: list[dict | Exception] = []
        self.calls = 0

    async def complete_json(self, system: str, user: str, schema: dict) -> dict:
        self.calls += 1
        r = self.responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


@pytest.fixture
def fake() -> FakeLLM:
    return FakeLLM()


@pytest.fixture
def client(fake: FakeLLM):
    app.dependency_overrides[get_llm] = lambda: fake
    yield TestClient(app)
    app.dependency_overrides.clear()


H_REQ = {
    "context": [{"id": "doc1", "text": "환불은 결제 후 7일 이내 가능합니다."}],
    "question": "환불 기간이 어떻게 돼요?",
    "answer": "결제 후 일주일 안에 환불돼요.",
}
R_REQ = {
    "messages": [
        {"role": "user", "content": "환불 기간?", "timestamp": "2026-09-29T15:00:00+09:00"},
        {"role": "assistant", "content": "7일입니다.", "timestamp": "2026-09-29T15:00:03+09:00"},
    ],
    "ended_reason": "timeout",
}


def claim(supported: bool, quote: str = "일주일 안에") -> dict:
    return {
        "claim": "c",
        "answer_quote": quote,
        "supported": supported,
        "evidence_id": None,
        "reason": "r",
    }


# --- API ---


def test_healthz(client):
    assert client.get("/healthz").json() == {"status": "ok"}


def test_hallucination_missing_answer_is_422(client):
    assert client.post("/eval/hallucination", json={**H_REQ, "answer": None}).status_code == 422


def test_resolution_bad_ended_reason_is_422(client):
    assert client.post("/eval/resolution", json={**R_REQ, "ended_reason": "x"}).status_code == 422


def test_resolution_empty_messages_is_422(client):
    assert client.post("/eval/resolution", json={**R_REQ, "messages": []}).status_code == 422


def test_all_claims_supported_is_grounded(client, fake):
    fake.responses.append({"claims": [claim(True), claim(True)]})
    body = client.post("/eval/hallucination", json=H_REQ).json()
    assert (body["verdict"], body["score"]) == ("grounded", 1.0)
    assert (body["model"], body["prompt_version"]) == ("fake", "hallucination_v3")
    assert isinstance(body["latency_ms"], int)


def test_one_unsupported_claim_makes_whole_answer_hallucinated(client, fake):
    fake.responses.append({"claims": [claim(True), claim(False)]})
    body = client.post("/eval/hallucination", json=H_REQ).json()
    assert (body["verdict"], body["score"]) == ("hallucinated", 0.5)


def test_answer_without_claims_is_no_claims(client, fake):
    fake.responses.append({"claims": []})
    body = client.post("/eval/hallucination", json={**H_REQ, "answer": "몰라"}).json()
    assert (body["verdict"], body["score"]) == ("no_claims", 0.0)


def test_claim_not_quoted_from_answer_is_retried(client, fake):
    from_context = claim(True, quote="환불은 결제 후 7일 이내 가능합니다.")
    fake.responses += [{"claims": [from_context]}] * 3
    assert client.post("/eval/hallucination", json=H_REQ).status_code == 502


def test_empty_context_skips_llm(client, fake):
    body = client.post("/eval/hallucination", json={**H_REQ, "context": []}).json()
    assert body["verdict"] == "insufficient_context"
    assert fake.calls == 0


def signals(escalation=False, repeated=False, answered=True, accepted=False, question=True) -> dict:
    return {
        "has_question": question,
        "escalation": escalation,
        "repeated_question": repeated,
        "answered": answered,
        "accepted": accepted,
        "confidence": 0.9,
        "reason": "r",
    }


@pytest.mark.parametrize(
    ("sig", "ended_reason", "expected"),
    [
        (
            signals(escalation=True, repeated=True, accepted=True),
            "user_closed",
            "escalation_needed",
        ),
        (signals(repeated=True, accepted=True), "user_closed", "needs_review"),
        (signals(accepted=True), "user_closed", "resolved"),
        (signals(), "timeout", "resolved"),  # 봇의 완결된 답으로 끝나고 timeout
        (signals(), "user_closed", "unresolved"),  # 답은 했지만 수용 신호 없이 고객이 닫음
        (signals(answered=False, accepted=True), "user_closed", "unresolved"),  # 답 없이 감사 인사
        (signals(question=False), "timeout", "unresolved"),  # 인사만 하고 timeout
    ],
)
def test_resolution_status_priority(client, fake, sig, ended_reason, expected):
    fake.responses.append(sig)
    body = client.post("/eval/resolution", json={**R_REQ, "ended_reason": ended_reason}).json()
    assert (body["status"], body["prompt_version"]) == (expected, "resolution_v4")


def test_schema_error_and_5xx_are_retried(client, fake):
    fake.responses += [{"claims": "not a list"}, LLMServerError("503"), {"claims": []}]
    assert client.post("/eval/hallucination", json=H_REQ).status_code == 200
    assert fake.calls == 3


def test_three_failures_is_502(client, fake):
    fake.responses += [{"escalation": "maybe"}] * 3
    assert client.post("/eval/resolution", json=R_REQ).status_code == 502


def test_timeout_is_504(client, monkeypatch):
    async def stub(req, llm):
        raise TimeoutError

    monkeypatch.setattr(judges, "judge_hallucination", stub)
    assert client.post("/eval/hallucination", json=H_REQ).status_code == 504


# --- run_with_budget ---


def run(attempt, **kw):
    return asyncio.run(run_with_budget(attempt, **kw))


def flaky(*outcomes):
    """outcomes를 순서대로 반환하거나 raise하는 attempt."""
    it = iter(outcomes)

    async def attempt():
        o = next(it)
        if isinstance(o, Exception):
            raise o
        return o

    return attempt


def test_budget_counts_attempts():
    assert run(flaky(json.JSONDecodeError("x", "", 0), "ok")) == ("ok", 2)


def test_budget_gives_up_after_3_attempts():
    with pytest.raises(LLMFailed):
        run(flaky(*[LLMServerError("500")] * 3, "never"))


def test_budget_does_not_retry_bugs():
    with pytest.raises(ValueError):
        run(flaky(ValueError("bug"), "ok"))


def test_budget_timeout_covers_whole_request():
    async def slow():
        await asyncio.sleep(1)

    with pytest.raises(TimeoutError):
        run(slow, timeout=0.05)
