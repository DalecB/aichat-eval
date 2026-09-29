# Eval report

- 날짜: 2026-09-29
- 모델: gpt-6-luna
- 프롬프트: hallucination_v3, resolution_v4
- 평가셋: holdout2_set.jsonl 10건 (자체 라벨. 일반화된 정확도가 아니다)

## hallucination — 5/5 (100%)

행 = 정답 라벨, 열 = 예측

| | grounded | hallucinated | no_claims |
|---|---|---|---|
| **grounded** | 2 | 0 | 0 |
| **hallucinated** | 0 | 2 | 0 |
| **no_claims** | 0 | 0 | 1 |

## resolution — 4/5 (80%)

행 = 정답 라벨, 열 = 예측

| | escalation_needed | needs_review | resolved | unresolved |
|---|---|---|---|---|
| **escalation_needed** | 0 | 0 | 0 | 0 |
| **needs_review** | 0 | 1 | 0 | 0 |
| **resolved** | 1 | 0 | 2 | 0 |
| **unresolved** | 0 | 0 | 0 | 1 |

## 틀린 케이스 (1건)

| id | 정답 | 예측 | 판정 근거 | 케이스 의도 |
|---|---|---|---|---|
| h2b5 | resolved | escalation_needed | 고객은 첫 메시지에서 계정을 가족 명의로 바꿀 수 있는지 물었고, 명의 변경 요청은 챗봇 권한 밖의 일에 해당해 escalation은 true입니다. 챗봇이 진행 방법을 안내했고 이후 고객이 “감사합니다”라고 했으므로 answered와 accepted는 true이며, 같은 질문의 반복은 없습니다. | 명의 변경 문의에 봇이 셀프 처리 방법을 안내하고 고객이 수용함 |
