# Eval report

- 날짜: 2026-09-29
- 모델: gpt-6-luna
- 프롬프트: hallucination_v2, resolution_v3
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
| **needs_review** | 0 | 1 | 0 | 0 |
| **resolved** | 0 | 0 | 2 | 0 |
| **unresolved** | 0 | 0 | 1 | 0 |

## 틀린 케이스 (2건)

| id | 정답 | 예측 | 판정 근거 | 케이스 의도 |
|---|---|---|---|---|
| hh2 | hallucinated | grounded |  | 30일→한 달. 한 달의 기준은 사람마다 달라(28~31일) 범위가 같다고 볼 수 없음 |
| hr5 | unresolved | resolved | 고객은 1번 메시지에서 인사만 했고 질문이나 요청은 없어, 답변 불가 인정·상담원 연결 요청·권한 밖 요청도 없습니다. 반복 질문과 답변 후 수용 신호도 없습니다. | 질문이 없었음. 해결한 것이 없으니 해결률에 넣지 않음 |
