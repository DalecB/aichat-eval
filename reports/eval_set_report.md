# Eval report

- 날짜: 2026-09-29
- 모델: gpt-6-luna
- 프롬프트: hallucination_v3, resolution_v4
- 평가셋: eval_set.jsonl 21건 (자체 라벨. 일반화된 정확도가 아니다)

## hallucination — 10/10 (100%)

행 = 정답 라벨, 열 = 예측

| | grounded | hallucinated | insufficient_context |
|---|---|---|---|
| **grounded** | 4 | 0 | 0 |
| **hallucinated** | 0 | 5 | 0 |
| **insufficient_context** | 0 | 0 | 1 |

## resolution — 11/11 (100%)

행 = 정답 라벨, 열 = 예측

| | escalation_needed | needs_review | resolved | unresolved |
|---|---|---|---|---|
| **escalation_needed** | 2 | 0 | 0 | 0 |
| **needs_review** | 0 | 2 | 0 | 0 |
| **resolved** | 0 | 0 | 3 | 0 |
| **unresolved** | 0 | 0 | 0 | 4 |

## 틀린 케이스 (0건)

| id | 정답 | 예측 | 판정 근거 | 케이스 의도 |
|---|---|---|---|---|
