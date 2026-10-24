"""API-01: 모델 목록 및 가격정보 조회 (GET /api/v1/models)
공식 문서: https://openrouter.ai/docs/api-reference/list-available-models
"""
import json
import os
import sys
from pathlib import Path

import requests

# Windows 콘솔 한글 깨짐 방지 (저장 파일과 무관, 출력용)
sys.stdout.reconfigure(encoding="utf-8")

# 이 엔드포인트는 공개(public) 엔드포인트라 키가 필요 없음 -> 키를 아예 안 씀
URL = "https://openrouter.ai/api/v1/models"

# 저장 위치를 프로젝트 루트 기준으로 고정 (실행 위치 상관없이 동작하게)
RAW_DIR = Path(__file__).resolve().parent.parent / "results" / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)

# 1. 요청 보내기 (헤더 없음, 공개 엔드포인트)
response = requests.get(URL, timeout=30)
response.raise_for_status()
data = response.json()

# 2. 요청 정보 저장 (키/헤더가 없으므로 그대로 저장해도 안전)
request_record = {
    "method": "GET",
    "url": URL,
    "headers": {},
}
(RAW_DIR / "api01_request.json").write_text(
    json.dumps(request_record, ensure_ascii=False, indent=2), encoding="utf-8"
)

# 3. 응답 원본 저장 (민감정보 없음, 전체 모델 목록)
(RAW_DIR / "api01_response.json").write_text(
    json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
)

# 4. 콘솔에는 요약만 출력 (모델 수, 첫 번째 모델 예시 필드)
models = data.get("data", [])
print(f"총 모델 수: {len(models)}")
if models:
    sample = models[0]
    print("첫 번째 모델 id:", sample.get("id"))
    print("pricing 필드:", sample.get("pricing"))
    print("응답에 포함된 최상위 필드들:", list(sample.keys()))
