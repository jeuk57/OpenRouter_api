"""API-04: Reasoning·Cache Token 집계 방식 확인 (POST /api/v1/chat/completions)
같은 긴 프롬프트를 2번 보내서, 2번째 호출에서 cache 관련 토큰이 어떻게 집계되는지 비교.
공식 문서: https://openrouter.ai/docs/api-reference/chat-completion
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

URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "inclusionai/ling-3.0-flash"

RAW_DIR = Path(__file__).resolve().parent.parent / "results" / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)

# 1. 캐시가 걸릴 만큼 긴 프롬프트 준비 (같은 내용을 반복해 길이를 늘림)
long_text = (
    "다음 글을 읽고 핵심 내용을 한 문장으로 요약해줘. " * 200
)
body = {
    "model": MODEL,
    "messages": [{"role": "user", "content": long_text}],
    "max_tokens": 100,
}

# 2. 1차 호출 (아직 캐시 없음)
resp1 = requests.post(
    URL, headers={"Authorization": f"Bearer {api_key}"}, json=body, timeout=60
)
resp1.raise_for_status()
data1 = resp1.json()

# 3. 2차 호출 (완전히 동일한 body로 재호출 -> 캐시 적중 여부 확인용, 지시에 따른 의도적 반복)
resp2 = requests.post(
    URL, headers={"Authorization": f"Bearer {api_key}"}, json=body, timeout=60
)
resp2.raise_for_status()
data2 = resp2.json()

# 4. 요청/응답 저장 (키 제외)
request_record = {
    "method": "POST",
    "url": URL,
    "headers": {"Authorization": "<REDACTED>"},
    "body": body,
}
(RAW_DIR / "api04_request.json").write_text(
    json.dumps(request_record, ensure_ascii=False, indent=2), encoding="utf-8"
)
(RAW_DIR / "api04_response_1st.json").write_text(
    json.dumps(data1, ensure_ascii=False, indent=2), encoding="utf-8"
)
(RAW_DIR / "api04_response_2nd.json").write_text(
    json.dumps(data2, ensure_ascii=False, indent=2), encoding="utf-8"
)

# 5. 두 호출의 usage 필드 비교 출력 (cache/reasoning 토큰 중심)
usage1 = data1.get("usage", {})
usage2 = data2.get("usage", {})
print("1차 usage:", usage1)
print("2차 usage:", usage2)
print(
    "1차 cached_tokens:",
    usage1.get("prompt_tokens_details", {}).get("cached_tokens"),
)
print(
    "2차 cached_tokens:",
    usage2.get("prompt_tokens_details", {}).get("cached_tokens"),
)
print("1차 reasoning_tokens:", usage1.get("completion_tokens_details", {}).get("reasoning_tokens"))
print("2차 reasoning_tokens:", usage2.get("completion_tokens_details", {}).get("reasoning_tokens"))
