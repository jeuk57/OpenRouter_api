"""API-05a: 일반 키로 현재 키 사용량·한도 조회 (GET /api/v1/key)
공식 문서: https://openrouter.ai/docs/api-reference/limits
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

URL = "https://openrouter.ai/api/v1/key"

RAW_DIR = Path(__file__).resolve().parent.parent / "results" / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)

# 1. 조회 (GET만, 과금 없음)
response = requests.get(URL, headers={"Authorization": f"Bearer {api_key}"}, timeout=30)
response.raise_for_status()
data = response.json()

# 2. 요청 저장 (키 제외)
request_record = {"method": "GET", "url": URL, "headers": {"Authorization": "<REDACTED>"}}
(RAW_DIR / "api05a_request.json").write_text(
    json.dumps(request_record, ensure_ascii=False, indent=2), encoding="utf-8"
)

# 3. 응답 저장 전, 키 값이 포함된 필드가 있는지 확인하고 있으면 제거
safe_data = json.loads(json.dumps(data))
inner = safe_data.get("data", {})
for sensitive_field in ("key", "api_key", "token", "label"):
    if sensitive_field in inner:
        inner[sensitive_field] = "<REDACTED>"

(RAW_DIR / "api05a_response.json").write_text(
    json.dumps(safe_data, ensure_ascii=False, indent=2), encoding="utf-8"
)

# 4. 사용량/한도 관련 필드만 콘솔에 요약 출력 (키 값 자체는 출력하지 않음)
print("필드 목록:", list(inner.keys()))
print("usage:", inner.get("usage"))
print("limit:", inner.get("limit"))
print("limit_remaining:", inner.get("limit_remaining"))
print("is_free_tier:", inner.get("is_free_tier"))
print("rate_limit:", inner.get("rate_limit"))
