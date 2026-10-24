"""API-08: Provider 고정 및 Fallback 비활성화 동작 확인
공식 문서: https://openrouter.ai/docs/features/provider-routing
"""
import json
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding="utf-8")

load_dotenv()
api_key = os.environ["OPENROUTER_API_KEY"]

CHAT_URL = "https://openrouter.ai/api/v1/chat/completions"
KEY_URL = "https://openrouter.ai/api/v1/key"
MODEL = "mistralai/mistral-nemo"

RAW_DIR = Path(__file__).resolve().parent.parent / "results" / "raw"


def call_key_info():
    # /key 조회 (사용량 비교용, 과금 없음)
    r = requests.get(KEY_URL, headers={"Authorization": f"Bearer {api_key}"}, timeout=30)
    r.raise_for_status()
    return r.json()["data"]["usage"]


# 1. 이 모델을 실제로 서빙하는 provider: DeepInfra (앞서 /endpoints 조회로 확인됨)
#    -> 고정 + fallback 비활성 시 정상 동작하는지 확인 (성공 케이스)
success_body = {
    "model": MODEL,
    "messages": [{"role": "user", "content": "1+1은 몇이야? 숫자만 답해."}],
    "max_tokens": 100,
    "provider": {"order": ["DeepInfra"], "allow_fallbacks": False},
}
resp_success = requests.post(
    CHAT_URL, headers={"Authorization": f"Bearer {api_key}"}, json=success_body, timeout=30
)
success_data = {
    "status_code": resp_success.status_code,
    "body": resp_success.json(),
}
print("성공 케이스 status:", resp_success.status_code)
print("성공 케이스 provider:", success_data["body"].get("provider"))

# 2. 이 모델을 서빙하지 않는 provider: Google (앞서 /endpoints 목록에 없음 확인됨)
#    -> 고정 + fallback 비활성 시 실패하는지 확인 (실패 케이스)
#    실패 케이스는 /key 사용량을 호출 전후로 비교
usage_before = call_key_info()

fail_body = {
    "model": MODEL,
    "messages": [{"role": "user", "content": "1+1은 몇이야? 숫자만 답해."}],
    "max_tokens": 100,
    "provider": {"order": ["Google"], "allow_fallbacks": False},
}
resp_fail = requests.post(
    CHAT_URL, headers={"Authorization": f"Bearer {api_key}"}, json=fail_body, timeout=30
)
fail_data = {
    "status_code": resp_fail.status_code,
    "body": resp_fail.json() if resp_fail.content else None,
}
print("실패 케이스 status:", resp_fail.status_code)
print("실패 케이스 응답:", fail_data["body"])

usage_after = call_key_info()

# 3. 저장 (키 제외)
request_record = {
    "success_case": {"method": "POST", "url": CHAT_URL, "headers": {"Authorization": "<REDACTED>"}, "body": success_body},
    "fail_case": {"method": "POST", "url": CHAT_URL, "headers": {"Authorization": "<REDACTED>"}, "body": fail_body},
}
(RAW_DIR / "api08_request.json").write_text(
    json.dumps(request_record, ensure_ascii=False, indent=2), encoding="utf-8"
)
(RAW_DIR / "api08_response.json").write_text(
    json.dumps(
        {
            "success_case": success_data,
            "fail_case": fail_data,
            "key_usage_before_fail_case": usage_before,
            "key_usage_after_fail_case": usage_after,
        },
        ensure_ascii=False,
        indent=2,
    ),
    encoding="utf-8",
)

print()
print("실패 케이스 전 usage:", usage_before)
print("실패 케이스 후 usage:", usage_after)
print("usage 변화 있음:", usage_before != usage_after)
