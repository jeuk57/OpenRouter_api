"""API-03: 호출별 실제 비용 및 확인 시점 (GET /api/v1/generation)
새 채팅 호출 없이, API-02에서 받은 generation id를 재사용해서 조회 시점만 비교.
공식 문서: https://openrouter.ai/docs/api-reference/get-a-generation
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

RAW_DIR = Path(__file__).resolve().parent.parent / "results" / "raw"

# 1. API-02에서 저장해둔 generation id 불러오기 (새 호출 아님, 재사용)
saved = json.loads((RAW_DIR / "api02_generation_id.json").read_text(encoding="utf-8"))
generation_id = saved["id"]
print("조회할 generation id:", generation_id)

URL = "https://openrouter.ai/api/v1/generation"

# 2. 1차 조회 (지금 시점)
resp1 = requests.get(
    URL,
    headers={"Authorization": f"Bearer {api_key}"},
    params={"id": generation_id},
    timeout=30,
)
resp1.raise_for_status()
data1 = resp1.json()

# 3. 짧게 기다렸다가 2차 조회 (비용 반영 시점에 변화가 있는지 비교)
WAIT_SECONDS = 15
print(f"{WAIT_SECONDS}초 대기 후 재조회...")
time.sleep(WAIT_SECONDS)

resp2 = requests.get(
    URL,
    headers={"Authorization": f"Bearer {api_key}"},
    params={"id": generation_id},
    timeout=30,
)
resp2.raise_for_status()
data2 = resp2.json()

# 4. 요청/응답 저장 (키 제외)
request_record = {
    "method": "GET",
    "url": URL,
    "headers": {"Authorization": "<REDACTED>"},
    "params": {"id": generation_id},
}
(RAW_DIR / "api03_request.json").write_text(
    json.dumps(request_record, ensure_ascii=False, indent=2), encoding="utf-8"
)
(RAW_DIR / "api03_response_1st.json").write_text(
    json.dumps(data1, ensure_ascii=False, indent=2), encoding="utf-8"
)
(RAW_DIR / "api03_response_2nd.json").write_text(
    json.dumps(data2, ensure_ascii=False, indent=2), encoding="utf-8"
)

# 5. 두 조회 결과의 비용 관련 필드만 비교 출력
cost1 = data1.get("data", {}).get("total_cost")
cost2 = data2.get("data", {}).get("total_cost")
print("1차 조회 total_cost:", cost1)
print("2차 조회 total_cost:", cost2)
print("값이 같은가:", cost1 == cost2)
