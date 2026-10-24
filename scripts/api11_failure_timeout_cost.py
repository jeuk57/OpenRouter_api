"""API-11: 실패·Timeout 호출의 비용 대조 가능 여부 확인
공식 문서: https://openrouter.ai/docs/api-reference/streaming (X-Generation-Id 헤더 관련)
"과금 없음"을 가정하지 않고, /key 사용량을 호출 전후로 실측 비교한다.
"""
import json
import os
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding="utf-8")

load_dotenv()
api_key = os.environ["OPENROUTER_API_KEY"]

CHAT_URL = "https://openrouter.ai/api/v1/chat/completions"
KEY_URL = "https://openrouter.ai/api/v1/key"
GEN_URL = "https://openrouter.ai/api/v1/generation"
MODEL = "mistralai/mistral-nemo"

RAW_DIR = Path(__file__).resolve().parent.parent / "results" / "raw"
results = {}


def get_usage():
    r = requests.get(KEY_URL, headers={"Authorization": f"Bearer {api_key}"}, timeout=30)
    r.raise_for_status()
    return r.json()["data"]["usage"]


# 1. Baseline 사용량 (모든 테스트 시작 전)
usage_baseline = get_usage()
print("baseline usage:", usage_baseline)

# 2. 즉시 실패 케이스: 존재하지 않는 모델 ID
fail_body = {
    "model": "nonexistent/fake-model-xyz",
    "messages": [{"role": "user", "content": "1+1은 몇이야?"}],
    "max_tokens": 100,
}
r_fail = requests.post(CHAT_URL, headers={"Authorization": f"Bearer {api_key}"}, json=fail_body, timeout=30)
results["immediate_fail"] = {"status_code": r_fail.status_code, "body": r_fail.json() if r_fail.content else None}
print("즉시실패 status:", r_fail.status_code)

usage_after_fail_now = get_usage()
print("즉시실패 직후 usage:", usage_after_fail_now)

# 3. Timeout 케이스: 클라이언트 타임아웃을 극단적으로 짧게 설정해서 강제로 timeout 유도
#    (CLAUDE.md 예외: 이 케이스만 max_tokens 제한 없이 그대로 보냄 - 승인된 예외)
timeout_body = {
    "model": MODEL,
    "messages": [{"role": "user", "content": "1+1은 몇이야?"}],
}
try:
    r_timeout = requests.post(
        CHAT_URL, headers={"Authorization": f"Bearer {api_key}"}, json=timeout_body, timeout=0.01
    )
    results["timeout_case"] = {"status_code": r_timeout.status_code, "body": r_timeout.json() if r_timeout.content else None}
    print("timeout 케이스: 예상과 달리 타임아웃 없이 응답 받음, status:", r_timeout.status_code)
except requests.exceptions.Timeout as e:
    results["timeout_case"] = {"status_code": None, "client_error": "Timeout", "detail": str(e)}
    print("timeout 케이스: 클라이언트 타임아웃 발생 (의도된 결과)")

usage_after_timeout_now = get_usage()
print("timeout 직후 usage:", usage_after_timeout_now)

# 4. 스트리밍 id 선취득 + abort 테스트 (문서에서 X-Generation-Id 헤더 확인됨)
stream_body = {
    "model": MODEL,
    "messages": [{"role": "user", "content": "1부터 100까지 숫자를 나열해줘."}],
    "max_tokens": 100,
    "stream": True,
}
r_stream = requests.post(
    CHAT_URL, headers={"Authorization": f"Bearer {api_key}"}, json=stream_body, timeout=30, stream=True
)
stream_gen_id = r_stream.headers.get("X-Generation-Id")
print("스트리밍 응답 헤더의 X-Generation-Id:", stream_gen_id)
r_stream.close()  # 본문을 하나도 읽지 않고 바로 연결 종료 (abort)

stream_cost_lookup = None
if stream_gen_id:
    time.sleep(3)
    r_gen = requests.get(GEN_URL, headers={"Authorization": f"Bearer {api_key}"}, params={"id": stream_gen_id}, timeout=30)
    stream_cost_lookup = {"status_code": r_gen.status_code, "body": r_gen.json() if r_gen.content else None}
    print("abort된 스트리밍 요청의 /generation 조회 결과:", r_gen.status_code)

results["streaming_abort"] = {
    "generation_id_from_header": stream_gen_id,
    "generation_lookup": stream_cost_lookup,
}

# 5. 1~2분 뒤 재조회 (반영 지연 가능성 대비, 즉시실패+timeout 케이스 공통으로 한 번에 확인)
WAIT_SECONDS = 90
print(f"{WAIT_SECONDS}초 대기 후 최종 usage 재조회...")
time.sleep(WAIT_SECONDS)
usage_after_wait = get_usage()
print("1~2분 뒤 usage:", usage_after_wait)

# 6. 실제 Provider 서버 장애는 재현 불가 -> 추가 확인으로 기록 (코드로 테스트하지 않음)
results["provider_outage_note"] = "실제 Provider 서버 다운/네트워크 장애는 재현 불가 - 추가 확인"

results["usage_timeline"] = {
    "baseline": usage_baseline,
    "after_immediate_fail": usage_after_fail_now,
    "after_timeout_case": usage_after_timeout_now,
    "after_1to2min_wait": usage_after_wait,
}

# 7. 저장 (키 제외)
request_record = {
    "immediate_fail": {"method": "POST", "url": CHAT_URL, "headers": {"Authorization": "<REDACTED>"}, "body": fail_body},
    "timeout_case": {"method": "POST", "url": CHAT_URL, "headers": {"Authorization": "<REDACTED>"}, "body": timeout_body, "client_timeout_sec": 0.01},
    "streaming_abort": {"method": "POST", "url": CHAT_URL, "headers": {"Authorization": "<REDACTED>"}, "body": stream_body},
    "key_checks": {"method": "GET", "url": KEY_URL, "headers": {"Authorization": "<REDACTED>"}},
}
(RAW_DIR / "api11_request.json").write_text(
    json.dumps(request_record, ensure_ascii=False, indent=2), encoding="utf-8"
)
(RAW_DIR / "api11_response.json").write_text(
    json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
)

print()
print("=== usage 변화 요약 ===")
for k, v in results["usage_timeline"].items():
    print(k, ":", v)
