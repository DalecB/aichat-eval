# aichat-eval

CS 챗봇 답변을 채점하는 LLM judge 마이크로 API입니다.

- `POST /eval/hallucination`: 답변이 근거 문서로 뒷받침되는지 판정합니다.
- `POST /eval/resolution`: 대화가 고객 문제를 해결하고 끝났는지 판정합니다.

## 왜 만들었나

AI 에이전트를 운영하려면 「답이 맞았는가」와 「문제가 해결됐는가」를 자동으로 재야 합니다. 이 레포는 그 두 가지 판정을 작은 API로 만들고, 판정 기준을 직접 정의하고, 직접 라벨링한 평가셋으로 정확도를 측정한 기록입니다.

## API

### POST /eval/hallucination

```json
// request
{
  "context": [{"id": "doc1", "text": "환불은 결제 후 7일 이내 가능합니다."}],
  "question": "환불 기간이 어떻게 돼요?",
  "answer": "결제 후 7일 이내 환불 가능하고, 수수료는 없습니다."
}
// response
{
  "verdict": "hallucinated",            // grounded | hallucinated | insufficient_context | no_claims
  "score": 0.5,                          // 뒷받침된 주장 비율
  "claims": [
    {"claim": "결제 후 7일 이내 환불 가능", "answer_quote": "결제 후 7일 이내 환불 가능하고", "supported": true, "evidence_id": "doc1", "reason": "..."},
    {"claim": "환불 수수료 없음", "answer_quote": "수수료는 없습니다", "supported": false, "evidence_id": null, "reason": "근거에 언급 없음"}
  ],
  "model": "gpt-6-luna", "prompt_version": "hallucination_v2", "latency_ms": 2210
}
```

### POST /eval/resolution

```json
// request
{
  "messages": [
    {"role": "user", "content": "배송비 얼마예요?", "timestamp": "2026-09-29T15:00:00+09:00"},
    {"role": "assistant", "content": "5만 원 이상 무료입니다.", "timestamp": "2026-09-29T15:00:03+09:00"},
    {"role": "user", "content": "감사합니다!", "timestamp": "2026-09-29T15:00:10+09:00"}
  ],
  "ended_reason": "user_closed"          // user_closed | timeout
}
// response
{"status": "resolved", "confidence": 0.9, "reason": "...", "model": "gpt-6-luna", "prompt_version": "resolution_v3", "latency_ms": 1950}
// status: resolved | unresolved | needs_review | escalation_needed
```

### 에러

| 상황 | 응답 |
|---|---|
| 입력 검증 실패 | 422 |
| 요청 전체 10초 초과 | 504 (재시도 없음) |
| 스키마 오류·LLM 5xx·네트워크 오류가 3회 연속 발생 | 502 |
| 근거 문서가 비어 있음 | 200 + `insufficient_context` (에러가 아니라 판정 결과) |
| 답변에 확인할 사실·약속이 없음 (예: 「몰라」) | 200 + `no_claims`, score 0.0 |

## 실행

```bash
uv sync
uv run --env-file .env uvicorn app.main:app --reload     # http://localhost:8000/docs
uv run pytest                                             # 네트워크를 쓰지 않는다 (FakeLLM)
uv run --env-file .env python -m scripts.run_eval        # reports/eval_set_report.md 생성
uv run --env-file .env python -m scripts.run_eval data/holdout_set.jsonl  # held-out
```

환경변수 (`.env`에 넣고 `--env-file .env`로 읽는다):

| 이름 | 기본값 | 설명 |
|---|---|---|
| `OPENAI_API_KEY` | (필수) | OpenAI SDK가 직접 읽는다 |
| `OPENAI_MODEL` | `gpt-6-luna` | 판정 모델 |
| `OPENAI_REASONING_EFFORT` | `none` | 추론 모델은 `none`이어야 `temperature=0`을 쓸 수 있다. gpt-4o-mini 같은 비추론 모델은 이 파라미터를 거부하므로 빈 값(`OPENAI_REASONING_EFFORT=`)으로 둔다 |

Docker:

```bash
docker build -t aichat-eval .
docker run -p 8000:8000 --env-file .env aichat-eval
```

## 평가 결과

직접 작성·라벨링한 CS 대화 21건(hallucination 10, resolution 11) 기준입니다. 일반화된 정확도가 아닙니다. 아래 표의 처음 네 줄은 r11을 추가하기 전 20건 기준입니다. 마지막 줄 전까지는 gpt-4o-mini로 측정했습니다.

| 버전 | hallucination | resolution | 바꾼 것 |
|---|---|---|---|
| hallucination_v1 + resolution_v1 | 9/10 | 8/10 | 기준선 |
| resolution_v2 | — | 7/10 | 판정 순서를 프롬프트에 단계별로 명시 |
| resolution_v3 | 9/10 | 9/10 | LLM은 관찰값 4개만 답하고, 상태는 코드가 우선순위대로 결정 |
| hallucination_v2 + resolution_v3 | 9/10 | 9/10 | 주장마다 답변 원문 인용(`answer_quote`)을 받고 코드가 원문에 있는지 검증 |
| 같은 프롬프트, r11 추가 | 9/10 | 10/11 | 수동 테스트에서 찾은 경계 케이스 추가 (아래 참고) |
| 모델 교체: gpt-6-luna (현재) | 10/10 | 11/11 | 프롬프트는 그대로, 모델만 교체 (아래 참고) |

- **v1**: r05·r08이 틀렸습니다. 「감사합니다」나 timeout 같은 신호 하나만 보고 resolved로 판정했습니다. 우선순위 규칙을 적용하지 못했습니다.
- **v2**: 판정 순서를 글로 적어 줬지만 오히려 나빠졌습니다. 같은 실수에 r04가 더해졌습니다. 규칙을 문장으로 설명하는 것만으로는 모델이 그 규칙을 지키지 않았습니다.
- **v3**: 출력 스키마를 바꿨습니다. LLM은 `escalation`, `repeated_question`, `answered`, `accepted`를 각각 true/false로만 답합니다. 우선순위와 「마지막 메시지가 봇인가」처럼 입력에서 바로 알 수 있는 것은 코드가 판단합니다. r05·r08을 고쳤습니다. 2회 실행해 결과가 같았습니다.
- **hallucination_v2**: 평가셋 밖 수동 테스트에서 버그를 찾았습니다. 답변이 「환불 가능/불가능 가능/불가능」처럼 사실을 담지 않을 때, 모델이 답변 대신 **근거 문서의 문장**을 주장으로 뽑아 grounded로 판정했습니다. 이제 주장마다 답변 원문 구간을 인용하게 하고, 코드가 그 구간이 실제 답변에 있는지 확인합니다. 없으면 스키마 오류처럼 재시도합니다. 같은 입력에서 이제 주장이 추출되지 않습니다. 평가셋 정확도는 그대로입니다.
- **r11 추가**: 챗봇은 「확인 후 안내드리겠습니다」라고만 했는데 고객이 「오 된다」라고 한 대화입니다. 고객 문제는 저절로 풀렸지만 챗봇이 기여하지 않았으므로 `unresolved`로 라벨링했습니다. resolution은 「고객 문제가 풀렸는가」가 아니라 「챗봇이 해결했는가」를 잰다는 정의의 경계를 기록하는 케이스입니다. 챗봇 해결률이 부풀려지지 않게 하려는 선택입니다.
- **모델 교체**: gpt-4o-mini($0.15/$0.60 per 1M 토큰)에서 gpt-6-luna($0.10/$0.50)로 바꿨습니다. 같은 프롬프트로 gpt-4o-mini가 틀리던 h09(근거의 조건 「미개봉」 누락)와 r04(「확인 후 안내드리겠습니다」를 답으로 판정)를 맞혔습니다. 3회 실행해 모두 21/21이었습니다. 평가셋 1회 비용은 약 $0.0035에서 $0.0028로 줄었고, 건당 응답 시간은 1.5초에서 약 2.3초로 늘었습니다. 10초 한도 안입니다.
- **21/21의 의미**: 이 평가셋은 모델 교체 전에 이미 틀린 케이스를 보고 다듬은 것이라, 만점은 「이 21건에서 틀린 게 없다」는 뜻일 뿐입니다. 새 케이스를 추가해 계속 검증해야 합니다.

### held-out 검증 (10건)

위 개선은 모두 21건 평가셋의 틀린 케이스를 보고 한 것이라 낙관적입니다. 그래서 프롬프트 수정에 한 번도 쓰지 않은 10건([data/holdout_set.jsonl](data/holdout_set.jsonl))을 새로 만들었습니다. 입력을 먼저 쓰고, 모델 결과를 보기 전에 라벨을 확정했습니다. 결과를 본 뒤에는 코드와 프롬프트를 고치지 않았습니다.

| 실행 | hallucination | resolution | 틀린 케이스 |
|---|---|---|---|
| 1회 | 4/5 | 4/5 | hh5, hr5 |
| 2회 | 4/5 | 4/5 | hh2, hr5 |

- **평가셋 21/21 → held-out 8/10.** 튜닝에 쓴 케이스로 잰 정확도가 실제보다 높게 나온다는 것을 확인했습니다.
- **temperature 0이어도 결과가 흔들립니다.** hh2(「30일」→「한 달」)와 hh5(「확인해 보겠습니다」)는 실행마다 맞고 틀림이 바뀌었습니다. 둘 다 판단이 갈리는 경계 케이스입니다. hh5는 정의 자체도 모호합니다. 「확인해 보겠습니다」를 약속(판정 대상)으로 볼지, 사실이 없는 문장(`no_claims`)으로 볼지 정의가 가르지 못합니다.
- **hr5는 코드 로직의 구멍입니다.** 인사만 하고 질문 없이 timeout으로 끝난 대화입니다. LLM은 「답하지 못한 질문이 없다」며 `answered=true`로 답하고, 코드는 「답했고 봇의 말로 timeout」이니 resolved로 계산합니다. 질문이 없는 대화가 해결률에 들어갑니다. 고치려면 「고객 질문이 있었는가」라는 관찰값을 하나 더 받아야 합니다. held-out 결과를 보고 고치면 이 10건이 더 이상 held-out이 아니므로, 고친 뒤에는 새 held-out이 필요합니다.

상세 결과(혼동행렬, 틀린 케이스)는 [reports/eval_set_report.md](reports/eval_set_report.md)(평가셋, 현재), [reports/holdout_set_report.md](reports/holdout_set_report.md)(held-out, 2회차), [reports/eval_report_v1.md](reports/eval_report_v1.md)(기준선)에 있습니다. v1·v2 프롬프트는 v3 이전의 출력 스키마(`status`를 LLM이 직접 반환)를 전제로 합니다.

## 설계 결정

1. **전제는 기업 CS 챗봇이다.** CS에서는 고객이 물은 것에 정확히 답해야 하므로, 근거에 없는 주장은 그럴듯해도 실패로 본다. 아래 기준은 모두 이 전제에서 나온다.
2. **판정 단위는 주장(claim)이다.** 답변 전체를 한 번에 판정하고 다시 생성하게 하면, 멀쩡하던 부분에서 새 할루시네이션이 생길 수 있다. 문제가 된 주장만 골라 고칠 수 있어야 한다.
3. **verdict는 LLM이 아니라 코드가 집계한다.** 주장마다 답변 원문 인용(`answer_quote`)을 받아, 코드가 실제 답변에 있는 구간인지 검증한다. LLM은 주장별 `supported`만 판정한다. 하나라도 false면 `hallucinated`, `score`는 뒷받침된 비율이다. 일부만 틀렸다는 정보는 `partial` 라벨 대신 `claims`와 `score`로 전달한다. 주장이 0개면 `no_claims`다. 「틀린 말이 없다」를 grounded로 보고하면 「몰라」 같은 답변이 정상으로 읽히기 때문이다.
4. **바꿔 말하기는 숫자·조건·범위·주체가 같을 때만 정상이다.** 「7일」→「일주일」은 정상, 「7일」→「영업일 7일」은 할루시네이션이다. 조건은 그 조건이 붙은 주장 안에 남긴다.
5. **약속도 판정 대상이다.** 「환불 처리해 드렸습니다」처럼 봇 권한 밖의 약속은 할루시네이션이다. 사실도 약속도 없는 인사말만 판정에서 뺀다.
6. **해결됨은 「답이 먼저, 수용 신호가 뒤」다.** 「감사합니다」만으로는 해결로 보지 않는다. 봇의 마지막 턴이 완결된 답이고 타임아웃으로 끝난 경우도 해결로 본다.
7. **상태가 겹치면 `escalation_needed > needs_review > resolved > unresolved`.** 사람이 봐야 하는 신호일수록 놓쳤을 때 비용이 크다. 이 우선순위는 코드가 적용한다. 프롬프트로 적용하게 했을 때(v1·v2) 모델이 지키지 않았다. 3번과 같은 원칙이다. LLM은 관찰하고, 규칙은 코드가 적용한다.
8. **평가 API는 판정만 한다.** 상담원 연결 같은 라우팅은 호출하는 쪽의 정책이다. 근거 없음은 hallucination API가 `insufficient_context`로, 대화상 사람이 필요한 신호는 resolution API가 `escalation_needed`로 알려 주고, 둘을 합쳐 라우팅하는 것은 호출자가 한다.
9. **LLM 호출은 요청당 1회, 10초 안에서 최대 3회 시도한다.** 주장 분해와 판정을 한 번에 받는다. 주장마다 호출하면 10초 한도 안에 재시도할 여유가 없다. OpenAI SDK 자체 재시도(`max_retries`)는 껐다. 켜 두면 정책 밖에서 호출이 몇 배로 늘어난다.
10. **프롬프트는 파일로 버전을 관리한다.** 모든 응답과 로그에 `prompt_version`이 붙어서, 프롬프트를 바꿨을 때 결과를 버전별로 비교할 수 있다.
11. **이 hallucination API는 RAG 파이프라인의 검증 단계다.** RAG가 검색한 문서를 `context`로 받아 생성된 답변을 검증한다. 검색 자체는 범위 밖이다.
12. **LangChain을 쓰지 않았다.** LLM 호출 1회와 스키마 검증만 필요해서 추상화 계층을 들이지 않았다.
13. **모델은 가격표가 아니라 평가셋으로 골랐다.** 후보를 같은 평가셋으로 돌려 정확도·비용·지연을 비교했다. gpt-6-luna는 추론 모델이라 기본값으로는 `temperature=0`을 거부한다. `reasoning_effort="none"`으로 추론을 꺼서 temperature 0을 쓴다. 판정 결과가 실행마다 달라지지 않게 하는 쪽을 택했다.

## 한계

- 평가셋은 21건이고 판정 기준을 정한 사람이 직접 라벨링했다. 정확도 수치는 이 기준과 이 21건에 대한 것이다.
- 프롬프트와 평가셋을 같은 사람이 썼고, v2·v3는 v1의 틀린 케이스를 보고 고쳤다. 같은 평가셋으로 측정한 개선 폭은 낙관적이다. 개선을 검증하려면 프롬프트 수정에 쓰지 않은 별도 평가셋이 필요하다. v3 초안에 평가셋 문장이 그대로 들어갔을 때 resolution이 10/10으로 나왔고, 이를 일반적인 표현으로 바꾸자 9/10이 됐다. 표에는 9/10을 적었다.
- judge도 LLM이라 틀릴 수 있다. 특히 「같은 취지의 질문」이나 「봇 권한 밖」 같은 판단은 프롬프트의 정의에 의존한다.
- 답변 적합성(질문에 답했는가)은 판정하지 않는다. 사실이나 약속을 담지 않은 답변(「몰라」)은 `no_claims`로 표시만 하고, 질문의 일부에만 답한 경우(수수료를 물었는데 기간만 답함)는 잡지 못한다. 욕설·말투도 범위 밖이다.
- `confidence`는 LLM이 스스로 매긴 값이다. 보정(calibration)되지 않았다.
- 봇의 권한 범위를 별도 입력으로 받지 않는다. 권한은 근거 문서에 적힌 내용으로만 판단한다.
- 결과를 저장하지 않는다. 요청마다 JSON 로그 한 줄만 남긴다.

## 확장: 캐릭터 채팅용 `persona` 정책 (정의만)

할루시네이션의 정의는 도메인마다 다르다. 캐릭터 채팅에서는 근거 없는 창작이 오히려 대화의 가치다. 이 도메인에서의 실패는 다음과 같다.

- 설정(페르소나 시트)과 모순되는 말
- 앞선 대화와 모순되는 말
- 현실 사실(날짜·의료·금융 등)을 틀리게 말하는 것

판정 엔진(주장 단위 분해 → 근거 대조)은 그대로 쓴다. 바뀌는 것은 두 가지다. 무엇을 근거로 볼지(페르소나 시트 + 대화 이력)와, 근거가 없는 주장을 실패로 볼지(persona에서는 실패가 아니다)다.
