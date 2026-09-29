"""평가셋으로 judge 정확도를 측정해 reports/<평가셋 이름>_report.md를 만든다.

uv run --env-file .env python -m scripts.run_eval                        # data/eval_set.jsonl
uv run --env-file .env python -m scripts.run_eval data/holdout_set.jsonl
"""

import asyncio
import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path

from app import judges
from app.llm import LLMClient, LLMFailed, OpenAIClient, run_with_budget

ROOT = Path(__file__).parent.parent
TASKS = {  # task → (judge 함수, 요청 스키마)
    "hallucination": (judges.judge_hallucination, judges.HallucinationRequest),
    "resolution": (judges.judge_resolution, judges.ResolutionRequest),
}


async def predict(case: dict, llm: LLMClient) -> tuple[str, str]:
    """(예측 라벨, 판정 근거)"""
    judge, req_model = TASKS[case["task"]]
    req = req_model.model_validate(case["input"])
    try:
        result, _ = await run_with_budget(lambda: judge(req, llm))
    except (LLMFailed, TimeoutError) as e:  # 한 건 실패로 전체 실행을 버리지 않는다
        return f"error:{type(e).__name__}", str(e)
    if isinstance(result, judges.HallucinationResult):
        return result.verdict, "; ".join(c.reason for c in result.claims if not c.supported)
    return result.status, result.reason


def section(task: str, rows: list[tuple[dict, str, str]]) -> str:
    correct = sum(c["label"] == pred for c, pred, _ in rows)
    counts = Counter((c["label"], pred) for c, pred, _ in rows)
    labels = sorted({c["label"] for c, _, _ in rows} | {pred for _, pred, _ in rows})
    lines = [
        f"## {task} — {correct}/{len(rows)} ({correct / len(rows):.0%})",
        "",
        "행 = 정답 라벨, 열 = 예측",
        "",
        "| | " + " | ".join(labels) + " |",
        "|---" * (len(labels) + 1) + "|",
    ]
    lines += [
        f"| **{a}** | " + " | ".join(str(counts[a, p]) for p in labels) + " |" for a in labels
    ]
    return "\n".join(lines)


async def main() -> None:
    llm = OpenAIClient()
    data = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "data/eval_set.jsonl"
    cases = [json.loads(line) for line in data.open(encoding="utf-8")]
    rows = [(c, *await predict(c, llm)) for c in cases]  # 순차 실행. 건수가 늘면 gather로 병렬화

    wrong = [(c, pred, why) for c, pred, why in rows if c["label"] != pred]
    report = [
        "# Eval report",
        "",
        f"- 날짜: {date.today()}",
        f"- 모델: {llm.model}",
        f"- 프롬프트: {judges.HALLUCINATION_PROMPT}, {judges.RESOLUTION_PROMPT}",
        f"- 평가셋: {data.name} {len(cases)}건 (자체 라벨. 일반화된 정확도가 아니다)",
        "",
        *(section(t, [r for r in rows if r[0]["task"] == t]) + "\n" for t in TASKS),
        f"## 틀린 케이스 ({len(wrong)}건)",
        "",
        "| id | 정답 | 예측 | 판정 근거 | 케이스 의도 |",
        "|---|---|---|---|---|",
        *(f"| {c['id']} | {c['label']} | {p} | {w} | {c['note']} |" for c, p, w in wrong),
    ]
    text = "\n".join(report) + "\n"
    (ROOT / "reports" / f"{data.stem}_report.md").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    asyncio.run(main())
