# Eval report

- 날짜: 2026-09-29
- 모델: gpt-6-luna
- 프롬프트: hallucination_v3, resolution_v4
- 평가셋: holdout_set.jsonl 10건 (자체 라벨. 일반화된 정확도가 아니다)

## hallucination — 4/5 (80%)

행 = 정답 라벨, 열 = 예측

| | grounded | hallucinated | no_claims |
|---|---|---|---|
| **grounded** | 1 | 0 | 0 |
| **hallucinated** | 1 | 2 | 0 |
| **no_claims** | 0 | 0 | 1 |

## resolution — 4/5 (80%)

행 = 정답 라벨, 열 = 예측

| | escalation_needed | needs_review | resolved | unresolved |
|---|---|---|---|---|
| **escalation_needed** | 1 | 0 | 0 | 0 |
| **needs_review** | 1 | 0 | 0 | 0 |
| **resolved** | 0 | 0 | 2 | 0 |
| **unresolved** | 0 | 0 | 0 | 1 |

## 틀린 케이스 (2건)

| id | 정답 | 예측 | 판정 근거 | 케이스 의도 |
|---|---|---|---|---|
| hh2 | hallucinated | grounded |  | 30일→한 달. 한 달의 기준은 사람마다 달라(28~31일) 범위가 같다고 볼 수 없음 |
| hr3 | needs_review | escalation_needed | 고객은 첫 메시지에서 배송지 변경을 요청했고, 두 번째 고객 메시지에서는 안내된 곳에 변경 버튼이 없다고 지적했습니다. 배송지 변경은 계정 정보 변경 요청에 해당해 escalation은 true이며, 챗봇은 같은 안내만 반복해 요청에 맞는 완결된 답을 하지 않았고 고객의 수용 신호도 없습니다. | 안내가 통하지 않아 다시 물었는데 봇이 같은 답을 반복함 |
