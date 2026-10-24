"""API-06: 과거 호출(Generation) 조회 가능 범위 확인 (GET /api/v1/generation)
새 채팅 호출 없이, 이미 만들어둔 generation id들을 재사용해서 조회 가능 여부만 확인.
공식 문서: https://openrouter.ai/docs/api-reference/get-a-generation
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

URL = "https://openrouter.ai/api/v1/generation"
RAW_DIR = Path(__file__).resolve().parent.parent / "results" / "raw"

# 1. 기존에 생성된 id들 모으기 (API-02, API-04 1차/2차) - 새 채팅 호출 없음
api02_id = json.loads((RAW_DIR / "api02_generation_id.json").read_text(encoding="utf-8"))["id"]
api04_1st = json.loads((RAW_DIR / "api04_response_1st.json").read_text(encoding="utf-8"))["id"]
api04_2nd = json.loads((RAW_DIR / "api04_response_2nd.json").read_text(encoding="utf-8"))["id"]

# 2. 존재하지 않는 가짜 id도 하나 넣어서, 범위를 벗어났을 때 에러 형태 확인
fake_id = "gen-0000000000-doesnotexist00000000"

targets = {
    "api02 (가장 오래됨)": api02_id,
    "api04_1st": api04_1st,
    "api04_2nd (가장 최근)": api04_2nd,
    "존재하지 않는 id": fake_id,
}

results = {}
for label, gen_id in targets.items():
    resp = requests.get(
        URL, headers={"Authorization": f"Bearer {api_key}"}, params={"id": gen_id}, timeout=30
    )
    results[label] = {
        "id": gen_id,
        "status_code": resp.status_code,
        "body": resp.json() if resp.headers.get("content-type", "").startswith("application/json") else resp.text,
    }
    print(label, "->", resp.status_code)

# 3. 결과 저장 (키 제외, id 값은 민감정보 아님)
request_record = {
    "method": "GET",
    "url": URL,
    "headers": {"Authorization": "<REDACTED>"},
    "targets": {label: gen_id for label, gen_id in targets.items()},
}
(RAW_DIR / "api06_request.json").write_text(
    json.dumps(request_record, ensure_ascii=False, indent=2), encoding="utf-8"
)
(RAW_DIR / "api06_response.json").write_text(
    json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
)

print()
print("참고: 이번 세션에서 만들어진 id들만 테스트 가능 (최대 몇 시간 이내).")
print("수일~수주 전 과거 호출 보존 기간은 이번 테스트로 확인 불가 -> 추가 확인 필요")
