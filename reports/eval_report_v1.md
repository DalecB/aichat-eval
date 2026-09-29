# Eval report

- 날짜: 2026-09-29
- 모델: gpt-4o-mini
- 프롬프트: hallucination_v1, resolution_v1
- 평가셋: data/eval_set.jsonl 20건 (자체 라벨. 일반화된 정확도가 아니다)

## hallucination — 9/10 (90%)

행 = 정답 라벨, 열 = 예측

| | grounded | hallucinated | insufficient_context |
|---|---|---|---|
| **grounded** | 4 | 0 | 0 |
| **hallucinated** | 1 | 4 | 0 |
| **insufficient_context** | 0 | 0 | 1 |

## resolution — 8/10 (80%)

행 = 정답 라벨, 열 = 예측

| | escalation_needed | needs_review | resolved | unresolved |
|---|---|---|---|---|
| **escalation_needed** | 2 | 0 | 0 | 0 |
| **needs_review** | 0 | 1 | 1 | 0 |
| **resolved** | 0 | 0 | 3 | 0 |
| **unresolved** | 0 | 0 | 1 | 2 |

## 틀린 케이스 (3건)

| id | 정답 | 예측 | 판정 근거 | 케이스 의도 |
|---|---|---|---|---|
| h09 | hallucinated | grounded |  | 근거의 조건(미개봉)을 빠뜨려 적용 대상이 넓어짐. 문장은 근거와 거의 같아 놓치기 쉬움 |
| r05 | unresolved | resolved | 챗봇이 적립금 유효기간에 대한 답변을 먼저 했고, 그 뒤에 고객이 추가 질문을 했으나 ended_reason이 timeout으로 종료되었다. | 마지막 턴이 사용자의 새 질문. 봇의 마지막 턴이 완결된 답이 아님 |
| r08 | needs_review | resolved | 고객이 '알겠어요 감사합니다'라고 말하며 챗봇의 답변을 수용했기 때문입니다. | 수용 신호로 끝났지만 재질문이 있었음. 우선순위 needs_review > resolved |
