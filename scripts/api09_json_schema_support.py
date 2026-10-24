"""API-09: JSON Schema 지원 및 미지원 모델 처리 확인 (POST /api/v1/chat/completions)
공식 문서: https://openrouter.ai/docs/features/structured-outputs
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
RAW_DIR = Path(__file__).resolve().parent.parent / "results" / "raw"

# 공통 json_schema 지정 (간단한 구조: 숫자 답만 받기)
response_format = {
    "type": "json_schema",
    "json_schema": {
        "name": "answer_schema",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {"answer": {"type": "integer"}},
            "required": ["answer"],
            "additionalProperties": False,
        },
    },
}
messages = [{"role": "user", "content": "1+1은 몇이야? JSON으로만 답해."}]


def call(model):
    body = {
        "model": model,
        "messages": messages,
        "max_tokens": 100,
        "response_format": response_format,
    }
    r = requests.post(URL, headers={"Authorization": f"Bearer {api_key}"}, json=body, timeout=30)
    return body, r.status_code, (r.json() if r.content else None)


# 1. 지원 모델: mistralai/mistral-nemo (supported_parameters에 response_format 있음)
support_body, support_status, support_resp = call("mistralai/mistral-nemo")
print("지원 모델 status:", support_status)
print("지원 모델 응답 message.content:", support_resp.get("choices", [{}])[0].get("message", {}).get("content") if support_resp else None)

# 2. 미지원 모델: amazon/nova-micro-v1 (supported_parameters에 response_format 없음)
unsupported_body, unsupported_status, unsupported_resp = call("amazon/nova-micro-v1")
print("미지원 모델 status:", unsupported_status)
print("미지원 모델 응답:", unsupported_resp)

# 3. 저장 (키 제외)
request_record = {
    "support_case": {"method": "POST", "url": URL, "headers": {"Authorization": "<REDACTED>"}, "body": support_body},
    "unsupported_case": {"method": "POST", "url": URL, "headers": {"Authorization": "<REDACTED>"}, "body": unsupported_body},
}
(RAW_DIR / "api09_request.json").write_text(
    json.dumps(request_record, ensure_ascii=False, indent=2), encoding="utf-8"
)
(RAW_DIR / "api09_response.json").write_text(
    json.dumps(
        {
            "support_case": {"status_code": support_status, "body": support_resp},
            "unsupported_case": {"status_code": unsupported_status, "body": unsupported_resp},
        },
        ensure_ascii=False,
        indent=2,
    ),
    encoding="utf-8",
)
