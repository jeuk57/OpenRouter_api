"""API-02: 호출별 Input/Output Token 확인 (POST /api/v1/chat/completions)
공식 문서: https://openrouter.ai/docs/api-reference/chat-completion
"""
import json
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding="utf-8")

# 1. .env에서 키 읽기 (코드에 키를 직접 쓰지 않음, 절대 출력하지 않음)
load_dotenv()
api_key = os.environ["OPENROUTER_API_KEY"]

URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "mistralai/mistral-nemo"

RAW_DIR = Path(__file__).resolve().parent.parent / "results" / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)

# 2. 짧은 프롬프트 + max_tokens 제한 (비용 규칙: 저렴한 모델, 짧은 프롬프트)
body = {
    "model": MODEL,
    "messages": [{"role": "user", "content": "1+1은 몇이야? 숫자만 답해."}],
    "max_tokens": 100,
}

# 3. 실제 호출 (헤더에만 키 사용, 변수에 남기지 않고 바로 요청에만 사용)
response = requests.post(
    URL,
    headers={"Authorization": f"Bearer {api_key}"},
    json=body,
    timeout=30,
)
response.raise_for_status()
data = response.json()

# 4. 요청 저장용 레코드: Authorization 헤더는 절대 포함하지 않음
request_record = {
    "method": "POST",
    "url": URL,
    "headers": {"Authorization": "<REDACTED>"},
    "body": body,
}
(RAW_DIR / "api02_request.json").write_text(
    json.dumps(request_record, ensure_ascii=False, indent=2), encoding="utf-8"
)

# 5. 응답 원본 저장 (응답 바디에는 키가 들어있지 않음)
(RAW_DIR / "api02_response.json").write_text(
    json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
)

# 6. 다음 항목(API-03, API-07)에서 재사용할 generation id 별도 보관
generation_id = data.get("id")
(RAW_DIR / "api02_generation_id.json").write_text(
    json.dumps({"id": generation_id}, ensure_ascii=False, indent=2), encoding="utf-8"
)

# 7. 콘솔에는 usage 필드만 요약 출력
usage = data.get("usage", {})
print("generation id:", generation_id)
print("usage 필드:", usage)
print("provider/model:", data.get("provider"), "/", data.get("model"))
