# OpenRouter API 기능 검증 보고서

- 검증 목적: OpenRouter API가 CLAUDE.md에 정의된 11개 기능을 실제로 지원하는지 직접 호출로 검증
- 검증 기간: 2026-10-24 (단일 세션)
- 총 실제 발생 비용: **약 $0.00014** (키 사용량 기준, `GET /api/v1/key` 실측값)
- 사용한 모델: 모두 OpenRouter 등록 모델 중 해당 기능을 지원하는 모델 중 최저가 (선정 기준은 각 항목에 기재)
- 원본 요청/응답 전체는 `results/raw/`에 저장 (키/Authorization 헤더 제외, git에는 올리지 않음)
- 범례: **지원** / **부분 지원** / **미지원** / **추가 확인**(이번 테스트로 확정 불가)

---

## API-01. 모델 목록 및 가격정보 조회

**결과: 지원**

**확인 방법**
```
GET https://openrouter.ai/api/v1/models
```
공개 엔드포인트라 API 키 불필요, 과금 없음.

**실제 응답 예시 (일부)**
```json
{
  "data": [
    {
      "id": "moonshotai/kimi-k3.1-pro",
      "pricing": {
        "prompt": "0.000002",
        "completion": "0.00001",
        "input_cache_read": "0.0000002"
      },
      "architecture": { "input_modalities": ["text", "image"] },
      "supported_parameters": ["response_format", "reasoning", "..."]
    }
  ],
  "total_count": 469,
  "links": { "...": "..." }
}
```

**응답 필드명/타입**
- `data`: `list[dict]` (모델 469개), `total_count`: `int`, `links`: `dict`
- 모델 객체: `id`(str), `pricing`(dict, 값은 모두 **문자열**), `architecture.input_modalities`(list[str]), `supported_parameters`(list[str]), `context_length`(int), `reasoning`(dict/null)

**DB 설계에 미치는 영향**
- `pricing` 값이 숫자가 아니라 **문자열**로 옴 (`"0.000002"`) → 소수점 정밀도 손실 방지 목적으로 추정, 저장/연산 시 문자열→Decimal 변환 필요
- 모델마다 `pricing` 하위 필드 구성이 다름(예: `input_cache_read` 유무) → 고정 컬럼이 아니라 가변 구조 고려 필요
- `supported_parameters` 배열로 기능 지원 여부를 사전에 판별 가능 → API-09에서 이 필드를 이용해 지원/미지원 모델을 정확히 선별함

**출처**: https://openrouter.ai/docs/api/api-reference/models/list-all-models-and-their-properties.md

---

## API-02. 호출별 Input/Output Token

**결과: 지원**

**확인 방법**
```
POST https://openrouter.ai/api/v1/chat/completions
{
  "model": "mistralai/mistral-nemo",
  "messages": [{"role": "user", "content": "1+1은 몇이야? 숫자만 답해."}],
  "max_tokens": 100
}
```

**실제 응답 예시 (`usage` 필드)**
```json
{
  "prompt_tokens": 16,
  "completion_tokens": 2,
  "total_tokens": 18,
  "cost": 3.48e-07,
  "prompt_tokens_details": {
    "cached_tokens": 0, "cache_write_tokens": 0, "audio_tokens": 0, "video_tokens": 0
  },
  "completion_tokens_details": {
    "reasoning_tokens": 0, "image_tokens": 0, "audio_tokens": 0
  },
  "cost_details": {
    "upstream_inference_cost": 3.48e-07,
    "upstream_inference_prompt_cost": 2.88e-07,
    "upstream_inference_completions_cost": 6e-08
  }
}
```

**응답 필드명/타입**
- `usage.prompt_tokens`(int), `completion_tokens`(int), `total_tokens`(int), `cost`(float)
- 하위 상세 객체 2개: `prompt_tokens_details`(dict), `completion_tokens_details`(dict) — 각각 cache/audio/video, reasoning/image/audio로 세분화 (⚠️ 상위 값에 **포함된** 내역이며 별도 합산 값 아님 — 근거는 API-04 참고)
- `cost_details`(dict) — provider 원가 세부 분해

**DB 설계에 미치는 영향**
- 토큰 수가 단일 값이 아니라 **용도별로 세분화된 하위 객체**로 옴 → 단일 token 컬럼보다 유형별 분리 저장이 유의미
- `cost`와 `cost_details.upstream_inference_cost`가 동일한 값으로 중복 제공됨 → 하나만 저장해도 무방

**출처**: https://openrouter.ai/docs/api/api-reference/chat/create-a-chat-completion.md

---

## API-03. 호출별 실제 비용 및 확인 시점

**결과: 지원** (단, "즉시 반영 여부"는 **추가 확인**)

**확인 방법** (새 채팅 호출 없이 API-02의 generation id 재사용)
```
GET https://openrouter.ai/api/v1/generation?id=gen-...
```
15초 간격으로 2회 조회.

**실제 응답 예시 (`data` 하위, 일부)**
```json
{
  "id": "gen-...",
  "model": "mistralai/mistral-nemo",
  "provider_name": "DekaLLM",
  "total_cost": 3.48e-07,
  "upstream_inference_cost": 0,
  "tokens_prompt": 11,
  "tokens_completion": 1,
  "native_tokens_prompt": 16,
  "native_tokens_completion": 2,
  "cache_discount": null,
  "streamed": true,
  "provider_responses": [{"endpoint_id": "...", "status": 200, "provider_name": "DekaLLM"}]
}
```

**응답 필드명/타입**
- `total_cost`(float), `native_tokens_prompt`/`native_tokens_completion`(int, provider 실제 토큰 — **비용 계산과 일치, 아래 검증 참고**) vs `tokens_prompt`/`tokens_completion`(int, OpenRouter 자체 별도 집계로 추정, 비용과 불일치)
- `provider_responses`(list[dict]), `cache_discount`(float/null)

**DB 설계에 미치는 영향 (⚠️ 1차 검증 오류를 재검증으로 수정함)**

처음엔 `/models` 목록의 대표 가격으로 계산해서 "`/generation`의 `tokens_prompt`가 비용과 맞는다"고 결론 내렸는데, **실제 처리 provider(DekaLLM)의 개별 단가**(`GET /models/mistralai/mistral-nemo/endpoints`로 조회)로 다시 계산하니 결론이 **반대로** 나왔습니다:

- DekaLLM 실제 단가: prompt `$0.000000018`/토큰, completion `$0.00000003`/토큰 (`/models` 목록의 대표가 `$0.000000029`와 다름 — 그건 DeepInfra 단가였음)
- 채팅 완료 응답의 `prompt_tokens=16, completion_tokens=2`(=`native_tokens_*`)로 계산 → `16×0.000000018 + 2×0.00000003 = 3.48e-7` → **실제 청구액(3.48e-7)과 정확히 일치**
- `/generation`의 `tokens_prompt=11, tokens_completion=1`로 계산 → `2.28e-7` → **불일치**
- **API-04 호출(Novita, 긴 프롬프트)로 교차 검증**: `native_tokens_prompt=3622, completion=100`(캐시분 3584 포함)에 Novita 단가(prompt `$0.000000021`, completion `$0.000000063`, `input_cache_read` `$0.0000000042`)를 적용하면 1차 `8.2362e-05`, 2차 `2.21508e-05` 모두 **실제 청구액과 정확히 일치**. 반면 그 호출들의 `/generation` `tokens_prompt`는 `4450`으로 오히려 native보다 **더 큼** (API-02 때는 반대로 작았음 — 방향성이 일관되지 않음)

**정정된 결론**: **채팅 완료 응답 자체의 `usage.prompt_tokens`/`completion_tokens`(=native 토큰) + 실제 처리 provider의 개별 단가**를 쓰면 비용이 정확히 재계산됩니다. `/generation`의 `tokens_prompt`/`tokens_completion`은 방향성이 일관되지 않아 **OpenRouter 자체의 별도 집계(다른 토크나이저 등)로 추정되며, 비용 재계산용으로 쓰면 안 됩니다.**
→ **DB에는 채팅 완료 응답의 `usage.prompt_tokens`/`completion_tokens`를 비용 검증 기준 컬럼으로 저장**하고, 비용 재계산이 필요하면 **처리 provider명(`provider`)별로 `/endpoints`의 단가를 조인**해야 함 (모델 단위 대표가로는 안 됨)

- 1·2차 조회(15초 간격) 사이에는 `total_cost` 값이 변하지 않음을 확인

**추가 확인**
- 1차 조회 자체가 실제 호출 후 몇 분 지나서 이뤄져서, "호출 직후 즉시 반영되는지"는 이번 테스트로 확정 불가 (최소 수 분 내에는 반영되어 있음만 확인)
- 요청 시 `stream` 파라미터를 지정하지 않았는데도 응답의 `streamed` 필드가 `true`로 나옴 — 원인 미확인
- `upstream_inference_cost`가 채팅 완료 응답(`cost_details.upstream_inference_cost=3.48e-07`, `total_cost`와 동일)과 `/generation` 조회(`upstream_inference_cost=0`)에서 다름 — 공식 문서(필드 설명: "Cost charged by the upstream provider")를 확인했지만 두 값이 왜 다른지는 명시되어 있지 않아 **추가 확인**으로 남김 (마진/surcharge 차이로 추정되나 미확정)

**대체 동작**: provider별 단가 조인이 불가능한 환경(예: provider 목록 미캐싱)이라면, 재계산 없이 **응답에 포함된 `cost`/`usage.cost` 값을 그대로 신뢰해서 저장**하는 것으로 충분합니다 — 재계산은 감사(audit)용이지 필수가 아닙니다.

**PoC 완료조건에 미치는 영향**: 비용 필드 자체(`cost`)는 추가 검증 없이 그대로 저장해도 안전하다는 게 확인되어, PoC 단계에서는 "비용 재계산 로직"을 필수 구현 범위에서 제외해도 됩니다. 다만 "즉시 반영 여부"가 미확정이라, PoC가 "호출 직후 정확한 비용을 사용자에게 바로 보여줘야 한다"는 요구사항을 포함한다면 이 부분은 별도로 검증 후 범위에 넣어야 합니다.

**출처**: https://openrouter.ai/docs/api/api-reference/generations/get-request-&-usage-metadata-for-a-generation.md

---

## API-04. Reasoning·Cache Token 집계 방식

**결과: 지원**

**확인 방법**
동일한 긴 프롬프트(약 3,622 prompt tokens)를 모델 `inclusionai/ling-3.0-flash`로 2회 연속 호출.

**실제 응답 예시 (`usage`, 1차 vs 2차)**
```json
// 1차
{"prompt_tokens": 3622, "completion_tokens": 100, "cost": 8.2362e-05,
 "prompt_tokens_details": {"cached_tokens": 0},
 "completion_tokens_details": {"reasoning_tokens": 87}}

// 2차 (동일 프롬프트 재호출)
{"prompt_tokens": 3622, "completion_tokens": 100, "cost": 2.21508e-05,
 "prompt_tokens_details": {"cached_tokens": 3584},
 "completion_tokens_details": {"reasoning_tokens": 82}}
```

**응답 필드명/타입**
- `prompt_tokens_details.cached_tokens`(int), `cache_write_tokens`(int, 두 호출 모두 0으로 관측)
- `completion_tokens_details.reasoning_tokens`(int) — 별도 파라미터 없이 기본 집계됨

**⚠️ 토큰 포함 관계 (중요, DB 합산 시 주의)**
- `cached_tokens`는 `prompt_tokens`에 **포함된** 값이지, 별도로 추가되는 값이 아님
- `reasoning_tokens`는 `completion_tokens`에 **포함된** 값이지, 별도로 추가되는 값이 아님
- 근거: 캐시 적중 여부(1차 `cached_tokens=0` vs 2차 `cached_tokens=3584`)와 무관하게 `total_tokens`가 1차·2차 모두 동일하게 `3722`(=`3622+100`)로 유지됨. `cached_tokens`가 별도 합산되는 값이었다면 2차에서 `total_tokens`가 더 커졌어야 하는데 그렇지 않음 → 세부 필드는 상위 토큰 수의 "내역(breakdown)"이지 "추가분"이 아님
- **DB 설계 시 `prompt_tokens + cached_tokens`, `completion_tokens + reasoning_tokens`처럼 더해서 합산하면 토큰 수가 중복 계산됨** — 상위 값(`prompt_tokens`, `completion_tokens`)만 합계에 쓰고, 하위 필드는 "그중 얼마가 캐시/reasoning이었는지" 설명용 컬럼으로 별도 취급해야 함

**DB 설계에 미치는 영향**
- 캐시 적중 시(`cached_tokens: 3584` / 전체 3622) 비용이 **약 73% 절감**(8.24e-05 → 2.22e-05)됨 → 캐시 적중률과 절감액을 계산하려면 `cached_tokens`와 `cost`를 함께 저장해야 함
- `reasoning_tokens`는 모델에 따라 파라미터 지정 없이도 기본 발생 → reasoning 전용 플래그만으로는 발생 여부를 판단할 수 없음

**⚠️ max_tokens 주의사항**
- 이번 두 호출 모두 `finish_reason: "length"`로 끝남 (`max_tokens=100` 제한에 걸려 **응답이 문장 중간에 잘림** — 정상 종료 `"stop"`이 아님). 실제 응답 내용도 "요약할 글이 제공되지 않았습니다..."처럼 미완성 상태로 끝남
- reasoning을 하는 모델은 `completion_tokens` 안에서 **reasoning_tokens(87~82)가 먼저 소비되고 남은 토큰으로 실제 답변을 생성**하므로, `max_tokens`를 너무 작게 주면 reasoning만 하다가 답변이 잘릴 수 있음
- **DB/서비스 설계 시: reasoning 지원 모델을 호출할 때는 reasoning 소비분을 감안해 `max_tokens`를 넉넉히 설정해야 답이 안 잘림** (이번 테스트는 비용 절감을 위해 의도적으로 100으로 제한했던 것이라 실제 서비스 값은 아님)

**추가 확인**
- `cache_write_tokens`가 두 호출 모두 0으로 관측됨 — 캐시 쓰기 비용이 과금되는 모델/provider가 있는지는 이번 테스트로 미확인

**대체 동작**: 캐시를 지원하지 않는 모델/provider라면 `cached_tokens`가 항상 0으로만 나오고 나머지 응답 구조는 동일함 — 별도 분기 처리 없이 같은 코드 경로로 처리 가능

**PoC 완료조건에 미치는 영향**: 캐시는 선택적 최적화(비용 절감 지표)로 취급 가능하며 PoC 필수 요구사항은 아님. 다만 reasoning 모델을 PoC에서 실제로 쓴다면, `max_tokens`를 작게 잡았을 때 "응답이 잘렸는지"(`finish_reason`) 체크 로직은 필수로 넣어야 함 — 안 그러면 완성되지 않은 답을 사용자에게 그대로 보여줄 위험이 있음

**출처**: https://openrouter.ai/docs/guides/best-practices/prompt-caching.md

---

## API-05. API Key별 사용량·한도 조회

**결과: 지원** (05-a, 05-b 모두)

### 05-a. 일반 키 — 현재 키 정보
```
GET https://openrouter.ai/api/v1/key
```

**실제 응답 예시 (민감정보 제거)**
```json
{
  "label": "<REDACTED>",
  "is_management_key": false,
  "limit": 50,
  "limit_remaining": 49.999865881,
  "usage": 0.000134119,
  "usage_daily": 0.000134119,
  "is_free_tier": false,
  "workspace_id": "<REDACTED>",
  "rate_limit": {"requests": -1, "interval": "10s", "note": "deprecated, safe to ignore"}
}
```

### 05-b. Management 키 — 키 목록 (GET만 사용)
```
GET https://openrouter.ai/api/v1/keys?workspace_id=<workspace_id>
```
⚠️ **workspace_id 쿼리 파라미터가 필수**였음 (문서에 명시되지 않았던 제약을 에러 메시지로 발견: `"This account no longer has a default workspace. Pass workspace_id explicitly."`)

**실제 응답 예시 (민감정보 제거)**
```json
{
  "data": [
    {
      "hash": "<REDACTED>",
      "label": "<REDACTED>",
      "name": "<REDACTED>",
      "disabled": false,
      "limit": 50,
      "usage": 0.00010486,
      "created_at": "2026-10-23T07:34:55.562Z",
      "last_used_at": "2026-10-24T04:21:46.568012Z",
      "workspace_id": "<REDACTED>"
    }
  ]
}
```

**응답 필드명/타입**
- `usage`/`usage_daily`/`usage_weekly`/`usage_monthly`(float), `limit`/`limit_remaining`(float)
- `label`, `hash`: **마스킹된 키 일부를 포함하는 민감 필드** — 저장 시 반드시 레드액션 필요
- `created_at`/`updated_at`/`expires_at`/`last_used_at`: ISO8601 문자열 또는 null

**DB 설계에 미치는 영향**
- 계정에 기본 workspace가 없을 수 있어, 키 목록 조회 시 `workspace_id`가 선행 조건이 될 수 있음
- `label`/`hash` 필드는 키 일부를 담고 있어 **그대로 저장하면 안 됨** — 이번 작업 중 실제로 2차례 레드액션 누락 사고가 발생해 수정함

**출처**: 05-a https://openrouter.ai/docs/api/api-reference/api-keys/get-current-api-key.md , 05-b https://openrouter.ai/docs/api/api-reference/api-keys/list-api-keys.md

---

## API-06. 과거 호출(Generation) 조회 가능 범위

**결과: 지원** (세션 내 생성 id 기준), **장기 보존 기간은 추가 확인**

**확인 방법**
API-02/04에서 생성된 기존 id 3개 + 존재하지 않는 가짜 id 1개로 `GET /generation` 조회 (새 채팅 호출 없음).

**결과**
- 기존 id 3개(최근 1시간 이내 생성) → 모두 `200` 정상 조회
- 존재하지 않는 id → `404`

**DB 설계에 미치는 영향**
- 존재하지 않는/만료된 id에 대해 명확한 404를 반환 → 조회 실패를 코드로 구분 가능

**추가 확인**
- 이번 세션에서 만든 id들만 테스트 가능했음 (최대 1시간 이내) → 수일~수주 전 과거 호출까지 조회 가능한지는 확인 못함

**대체 동작**: 만료/미존재 id는 명확한 404라서, 애플리케이션은 이를 "데이터 없음"으로 처리하고 재시도하지 않으면 됨

**PoC 완료조건에 미치는 영향**: 장기 보존 기간이 불확실하므로, PoC가 "과거 호출을 몇 달 뒤에도 OpenRouter API로 직접 재조회"하는 걸 전제로 설계하면 위험함 — **호출 직후 받은 데이터를 자체 DB에 즉시 저장(미러링)하는 구조가 필요**하며, OpenRouter의 `/generation`을 장기 보관소로 의존하면 안 됨

**출처**: https://openrouter.ai/docs/api/api-reference/generations/get-request-&-usage-metadata-for-a-generation.md

---

## API-07. 실제 응답 Provider·Model 확인

**결과: 지원** (새 호출 없이 API-02/03 응답 재사용)

**확인 방법**: API-02 응답의 `model`/`provider` 필드와 API-03(`/generation`)의 `provider_name` 필드 비교

**결과**
- 요청 모델 `mistralai/mistral-nemo` = 응답 `model` 필드 → **일치**
- chat completion 응답의 `provider: "DekaLLM"` = `/generation` 조회의 `provider_name: "DekaLLM"` → **일치**

**DB 설계에 미치는 영향**
- 실제 처리 provider가 두 엔드포인트(채팅 완료 응답, generation 조회) 모두에서 일관되게 제공되므로, 둘 중 하나만 저장해도 무방

**출처**: https://openrouter.ai/docs/api/api-reference/chat/create-a-chat-completion.md

---

## API-08. Provider 고정 및 Fallback 비활성화 동작

**결과: 지원**

**확인 방법**
사전에 `GET /models/mistralai/mistral-nemo/endpoints`로 실제 서빙 provider 목록(Io Net, DekaLLM, DeepInfra, Parasail, Mistral) 확인 후:
- 성공 케이스: `provider: {"order": ["DeepInfra"], "allow_fallbacks": false}`
- 실패 케이스: `provider: {"order": ["Google"], "allow_fallbacks": false}` (이 모델을 서빙하지 않는 provider)

**실제 응답 예시 — 실패 케이스**
```json
{
  "error": {
    "message": "No endpoints found for mistralai/mistral-nemo. Every candidate endpoint was removed during routing: Filter by Regional Surcharge removed mistral/eu; Filter by Fallback removed io-net/fp16, dekallm/fp8, deepinfra/fp8, parasail/fp8.",
    "code": 404,
    "metadata": {
      "routing_funnel": [
        {"step": "Initial Endpoints", "endpoint_count": 5},
        {"step": "Filter by Regional Surcharge", "endpoint_count": 4},
        {"step": "Filter by Fallback", "endpoint_count": 0}
      ],
      "failed_routing_step": "Filter by Fallback"
    }
  }
}
```

**결과**
- 성공 케이스: `200`, 지정한 provider(`DeepInfra`) 그대로 사용됨
- 실패 케이스: `404`, 라우팅 단계별 필터링 과정을 상세히 보여주는 `routing_funnel` 포함
- 실패 케이스 호출 전후 `GET /key` 사용량 비교: **변화 없음 → 과금되지 않음을 실측 확인** (가정이 아님)

**DB 설계에 미치는 영향**
- `error.metadata.routing_funnel`, `failed_routing_step` 필드로 실패 원인을 구조화해서 기록 가능 (str/list[dict])
- Provider 고정 실패는 과금되지 않음이 확인됨

**출처**: https://openrouter.ai/docs/guides/routing/provider-selection.md

---

## API-09. JSON Schema 지원 및 미지원 모델 처리

**결과: 부분 지원** (기본값 기준) → **`provider.require_parameters: true` 사용 시 지원으로 전환 가능**

**확인 방법**
동일한 `response_format: json_schema`(필드: `answer` 정수 1개) 요청을 두 모델에 전송:
- 지원 모델: `mistralai/mistral-nemo`
- 미지원 모델: `amazon/nova-micro-v1`

**실제 응답 예시**
```json
// 지원 모델 - 정확히 스키마대로 응답
{"choices": [{"message": {"content": "{\"answer\": 2}"}}]}

// 미지원 모델 - 에러 없이 200, 그러나 스키마 무시하고 임의 형태로 응답
{"choices": [{"message": {"content": "{\n  \"두 개의 하나\": 2\n}"}}]}
```

**추가 테스트 — `require_parameters: true`로 재시도 (미지원 모델)**
```json
{
  "error": {
    "message": "No endpoints found that can handle the requested parameters.",
    "code": 404,
    "metadata": {"failed_routing_step": "Filter by Parameters"}
  }
}
```

**DB 설계에 미치는 영향**
- 기본값으로는 미지원 모델이 **에러 없이 조용히 무시**하고 임의 구조로 응답함 → 응답 스키마 일치 여부를 애플리케이션에서 별도 검증하지 않으면 잘못된 데이터가 그대로 저장될 위험
- `provider.require_parameters: true`를 사용하면 미지원 provider/모델을 라우팅 단계에서 걸러 **명시적 404 에러**로 전환됨 → 구조화된 응답이 필수인 기능에는 이 옵션을 기본값으로 사용 권장

**대체 동작**: `require_parameters: true`로 404를 받으면, 애플리케이션은 (1) 해당 모델을 호출 가능 목록에서 제외하거나 (2) 스키마 요구를 포기하고 자유 텍스트 응답을 받아 별도 파싱 로직으로 대체 — 둘 중 하나를 선택해야 함 (무시하고 재시도하면 같은 에러만 반복됨)

**PoC 완료조건에 미치는 영향**: 사용자가 임의의 모델을 고를 수 있는 PoC라면, "구조화 응답이 필요한 기능"에서는 **모델 선택지를 `supported_parameters`에 `response_format`/`structured_outputs`가 있는 모델로 제한**하거나, `require_parameters: true` + 에러 핸들링을 처음부터 구현 범위에 포함해야 함 — 나중에 추가하면 이미 저장된 잘못된 형식의 데이터를 정리해야 할 수 있음

**출처**: https://openrouter.ai/docs/guides/features/structured-outputs.md , https://openrouter.ai/docs/guides/routing/provider-selection.md

---

## API-10. 이미지 입력 지원 및 결과

**결과: 지원** (이미지 지원 모델 기준), 미지원 모델은 명확한 에러로 구분됨

**확인 방법**
실제 사진 2장(사용자 제공, Pixabay 무료 라이선스)으로 3가지 케이스 테스트:
- A: `google/gemma-3-4b-it` + 보통 크기 이미지(1.57MB JPG, 영수증·식료품 사진)
- B: `google/gemma-3-4b-it` + 대용량 이미지(32.5MB PNG, 풍경 사진)
- C: `mistralai/mistral-nemo`(이미지 미지원) + 보통 크기 이미지

**결과**
| 케이스 | 상태 | usage.prompt_tokens |
|---|---|---|
|A (1.57MB)|200, 정확히 인식|283|
|B (32.5MB)|200, 정확히 인식|283 (A와 동일)|
|C (미지원)|404|-|

**실제 응답 예시 — 미지원 모델**
```json
{
  "error": {
    "message": "No endpoints found that support image input",
    "code": 404,
    "metadata": {"failed_routing_step": "Filter by Image Support"}
  }
}
```

**응답 필드명/타입**
- `usage.completion_tokens_details.image_tokens`(int) — A, B 모두 `0`으로 관측됨 (이미지 토큰이 별도 집계되지 않고 `prompt_tokens`에 합산되는 것으로 추정)

**DB 설계에 미치는 영향**
- **원본 파일 용량(1.57MB vs 32.5MB, 약 20배 차이)과 무관하게 `prompt_tokens`가 동일(283)** → 서버 쪽에서 이미지를 일정 해상도로 리사이즈/타일링 후 토큰화하는 것으로 추정됨. 즉 원본 파일 용량이 비용에 비례하지 않음
- 미지원 모델은 API-08과 동일한 `routing_funnel` 구조의 404 에러로 명확히 구분됨

**추가 확인**
- `image_tokens` 필드가 이번 테스트 모델에서는 항상 0으로 나옴 — 다른 모델/provider에서 분리 집계되는지 미확인

**대체 동작**: 이미지 미지원 모델은 404로 명확히 구분되므로, 애플리케이션은 "이 모델은 이미지를 지원하지 않습니다" 같은 메시지로 바로 분기 처리 가능

**PoC 완료조건에 미치는 영향**: 원본 파일 용량이 비용에 비례하지 않는 것으로 보여, PoC에서 업로드 용량별 비용 추정 로직을 따로 만들 필요는 없어 보임 (다만 이번 테스트는 모델 1종 기준이라 다른 모델/provider에서도 동일한지는 확장 검증 필요)

**출처**: https://openrouter.ai/docs/guides/overview/multimodal/image-understanding.md

---

## API-11. 실패·Timeout 호출의 비용 대조 가능 여부

**결과: 부분 지원** (지연 과금 가능성은 확인됨, 그러나 **호출 단위로 비용을 대조하는 것까지는 안 됨**)

**확인 방법**
1. Baseline `GET /key` 사용량 확인
2. 즉시 실패: 존재하지 않는 모델 ID로 호출 → 직후 `/key` 재확인
3. Timeout: 클라이언트 타임아웃 0.01초로 강제 유도 → 직후 `/key` 재확인
4. 스트리밍 id 선취득: 공식 문서로 `X-Generation-Id` 응답 헤더가 본문 스트리밍 전에 먼저 전달됨을 확인 → 헤더만 받고 본문은 읽지 않고 즉시 연결 종료(abort) → 그 id로 `/generation` 조회
5. 90초 대기 후 `/key` 최종 재확인

**결과**
| 시점 | usage |
|---|---|
|baseline|0.000133855|
|즉시 실패 직후|0.000133855 (변화 없음 → 과금 안 됨)|
|timeout 직후|0.000133855 (변화 없음)|
|90초 후 최종|**0.000134119 (증가)**|

- 스트리밍 abort 후 `/generation` 조회: `404` (조회 시점엔 아직 레코드 생성 안 됨 또는 조회 불가)
- 즉시 실패(400)·timeout(클라이언트 레벨)은 **과금되지 않음이 즉시 확인**됨
- 그러나 90초 뒤 usage가 미세하게 증가(delta 약 2.64e-07) → **지연 과금이 실제로 존재함을 확인**

**⚠️ 왜 "부분 지원"으로 정정했는가**
- 계정 전체 사용량(`/key`)으로는 "뭔가 지연 과금이 있었다"는 **변화 감지는 가능**했음
- 그러나 **호출 단위(개별 call)로 어떤 호출이 그 비용을 발생시켰는지 대조는 안 됨**: 스트리밍 abort 건의 `/generation` 조회가 `404`라서, 계정 레벨 usage 증가분을 특정 호출 레코드와 연결할 방법이 없었음
- 즉 "지연 과금이 존재한다"는 알 수 있지만, "어떤 호출 때문에 얼마가 더 나갔다"를 영수증처럼 대조하는 것은 **이번 테스트로는 불가능** → 원래 질문("호출별 비용 대조 가능 여부")에 대해서는 **부분 지원**이 더 정확한 분류

**⚠️ Timeout 테스트(0.01초)의 한계**
- 클라이언트 타임아웃을 0.01초로 잡았는데, 이건 TLS 핸드셰이크·네트워크 왕복 시간보다도 짧을 수 있어서 **요청이 OpenRouter 서버에 실제로 도달하기도 전에 클라이언트가 먼저 끊었을 가능성이 있음**
- 즉 이번 timeout 테스트는 "서버가 처리를 시작한 뒤 끊긴 경우"를 재현한 게 아니라 "애초에 서버에 안 닿았을 가능성이 있는 경우"를 테스트했을 수 있어서, **"서버 처리 중 timeout" 시나리오를 제대로 검증했다고 보기 어려움**

**DB 설계에 미치는 영향**
- 실패/중단된 호출이라도 **지연되어 과금될 수 있음**이 실측으로 확인됨 → 호출 성공 여부와 무관하게 비용 필드는 "즉시 확정"이 아니라 **비동기로 재조회/정산해야 하는 값**으로 설계 필요
- key 사용량 집계(`/key`)와 generation 상세 조회(`/generation`)가 서로 다른 시점/기준으로 갱신될 수 있고, **개별 호출에 비용을 귀속시키지 못하는 경우가 실제로 있음** → 비용 원장(ledger) 테이블은 호출 시점에 `UNKNOWN` 상태로 먼저 기록하고, 이후 재조회로 금액이 확정되면 `reconciled_at` 같은 필드로 갱신하는 **비동기 정산 구조**가 필요함. 개별 호출에 끝내 귀속이 안 되는 금액(계정 레벨에서만 보이는 차액)이 생길 수 있다는 점도 설계에 반영 필요

**추가 확인**
- 지연 과금 증가분(2.64e-07)의 정확한 원인이 **timeout 케이스인지 스트리밍 abort 케이스인지는 이번 테스트로 분리되지 않음** (두 호출이 연속으로 이뤄져 개별 귀속 불가)
- 실제 Provider 서버 다운/네트워크 장애는 재현 불가 → **추가 확인**

**재테스트 계획 (실행은 보류, 계획만 기록)**
1. Timeout을 0.01초가 아니라 **2~3초**로 설정 — 서버가 요청을 받아 처리를 시작할 시간은 확보하되, 응답 전에 끊기도록 함
2. Timeout 케이스와 스트리밍 abort 케이스를 **완전히 분리된 시간대에 각각 단독으로** 테스트 (서로 영향 안 주도록)
3. 각 케이스마다 baseline → 호출 직후 → **1~2분 뒤** usage를 개별적으로 확인해서, 어느 케이스가 지연 과금을 유발하는지 분리
4. 위 결과가 나오면 본 보고서 업데이트 예정

**대체 동작**: 개별 호출 귀속이 실패하는 경우(계정 레벨 usage는 늘었는데 특정 generation을 못 찾는 경우), 애플리케이션은 그 차액을 "미귀속 비용"으로 별도 집계하고 주기적으로 사람이 확인하는 운영 프로세스를 두는 것을 대체 방안으로 고려할 수 있음

**PoC 완료조건에 미치는 영향**: 비용 원장 테이블 스키마에 `status`(UNKNOWN/CONFIRMED 등)와 `reconciled_at` 필드가 **처음부터** 포함되어야 함 — 나중에 추가하면 이미 쌓인 데이터를 마이그레이션해야 해서 설계 초기 단계에 반영돼야 하는 항목임. 또한 "모든 호출의 비용을 100% 개별 귀속시킨다"는 요구사항은 이번 테스트 결과상 **보장할 수 없는 목표**이므로, PoC 완료조건에서 이 부분은 "best-effort"로 조정하거나 미귀속분 처리 정책을 별도로 정해야 함

**출처**: https://openrouter.ai/docs/api_reference/streaming.md

---

## 전체 요약

| 항목 | 결과 |
|---|---|
|API-01 모델 목록·가격|지원|
|API-02 호출별 토큰|지원|
|API-03 비용 확인 시점|지원 (즉시반영 여부 추가확인)|
|API-04 Reasoning·Cache 토큰|지원|
|API-05 키 사용량·한도|지원|
|API-06 과거 호출 조회 범위|지원 (장기 보존기간 추가확인)|
|API-07 Provider·Model 확인|지원|
|API-08 Provider 고정·Fallback|지원|
|API-09 JSON Schema|부분 지원 (require_parameters로 보강 가능)|
|API-10 이미지 입력|지원|
|API-11 실패·Timeout 비용|**부분 지원** (지연 과금은 확인, 호출 단위 대조는 불가 — 재테스트 계획 수립됨)|

**총 검증 비용**: 약 $0.00014 (한도 $50 중)
