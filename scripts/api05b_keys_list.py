"""API-05b: Management 키로 키 목록 조회 (GET /api/v1/keys)
조회(GET)만 사용 -> 생성/수정/삭제 요청 절대 하지 않음
공식 문서: https://openrouter.ai/docs/api-reference/keys/get-api-keys
"""
import json
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding="utf-8")

load_dotenv()
mgmt_key = os.environ["OPENROUTER_MANAGEMENT_KEY"]

URL = "https://openrouter.ai/api/v1/keys"

RAW_DIR = Path(__file__).resolve().parent.parent / "results" / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)

# 0. 이 계정은 기본 workspace가 없어서 workspace_id를 명시해야 함(400 에러 확인됨)
#    -> API-03에서 이미 받아둔 workspace_id를 재사용 (새로 추측한 값 아님)
api03_sample = json.loads((RAW_DIR / "api03_response_1st.json").read_text(encoding="utf-8"))
workspace_id = api03_sample["data"]["workspace_id"]
params = {"workspace_id": workspace_id}

# 1. 조회 (GET만, 생성/수정/삭제 요청 없음)
response = requests.get(
    URL, headers={"Authorization": f"Bearer {mgmt_key}"}, params=params, timeout=30
)
response.raise_for_status()
data = response.json()

# 2. 요청 저장 (키 제외)
request_record = {
    "method": "GET",
    "url": URL,
    "headers": {"Authorization": "<REDACTED>"},
    "params": params,
}
(RAW_DIR / "api05b_request.json").write_text(
    json.dumps(request_record, ensure_ascii=False, indent=2), encoding="utf-8"
)

# 3. 응답에 실제 키 값이 포함돼 있을 수 있으니, 저장 전에 각 항목에서 민감 필드 제거
safe_data = json.loads(json.dumps(data))
items = safe_data.get("data", [])
sensitive_fields = ("key", "api_key", "token", "hash", "label")
for item in items:
    if isinstance(item, dict):
        for field in sensitive_fields:
            if field in item:
                item[field] = "<REDACTED>"

(RAW_DIR / "api05b_response.json").write_text(
    json.dumps(safe_data, ensure_ascii=False, indent=2), encoding="utf-8"
)

# 4. 요약만 출력 (키 값은 절대 출력하지 않음)
print("등록된 키 개수:", len(items))
if items:
    print("첫 번째 항목 필드 목록:", list(items[0].keys()))
    print("첫 번째 항목 name/disabled/usage:", items[0].get("name"), items[0].get("disabled"), items[0].get("usage"))
