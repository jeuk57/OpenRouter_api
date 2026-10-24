"""API-10: 이미지 입력 지원 및 결과 확인 (POST /api/v1/chat/completions)
공식 문서: https://openrouter.ai/docs/features/multimodal/images
실제 사진 2장(보통 크기 / 대용량)으로 실사용에 가까운 검증을 함께 진행.
"""
import base64
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

# 테스트에 쓸 이미지 2장의 로컬 경로 (실행 전 본인 환경에 맞게 수정)
IMG_DIR = Path(r"<이미지가 있는 폴더 경로>")
NORMAL_IMG = IMG_DIR / "1.jpg"   # 보통 크기 사진 (예: 1~5MB, 텍스트 인식 테스트용)
LARGE_IMG = IMG_DIR / "2.png"    # 대용량 사진 (예: 10MB 이상, 용량 한계 테스트용)


def to_data_url(path: Path) -> str:
    # 1. 이미지를 base64로 인코딩해서 data URL로 변환 (외부 URL 없이 직접 전송)
    mime = "image/jpeg" if path.suffix.lower() == ".jpg" else "image/png"
    encoded = base64.b64encode(path.read_bytes()).decode("utf-8")
    return f"data:{mime};base64,{encoded}"


def call(model, image_path, prompt):
    # 2. 이미지 입력을 포함한 호출 (max_tokens 제한 적용)
    body = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": to_data_url(image_path)}},
                ],
            }
        ],
        "max_tokens": 100,
    }
    try:
        r = requests.post(URL, headers={"Authorization": f"Bearer {api_key}"}, json=body, timeout=90)
        status = r.status_code
        resp_body = r.json() if r.content else None
    except requests.exceptions.RequestException as e:
        status = None
        resp_body = {"client_error": str(e)}

    # 저장용 레코드에는 base64 원본 대신 크기 정보만 남김 (파일 용량 절약, 키는 별도로 이미 제외)
    safe_body = json.loads(json.dumps(body))
    safe_body["messages"][0]["content"][1]["image_url"]["url"] = (
        f"<BASE64_IMAGE_OMITTED file={image_path.name} bytes={image_path.stat().st_size}>"
    )
    return safe_body, status, resp_body


prompt = "이 사진에 뭐가 보여? 한 문장으로 설명해줘."

# 3. 지원 모델 + 보통 크기 이미지 (정상 케이스)
req_a, status_a, body_a = call("google/gemma-3-4b-it", NORMAL_IMG, prompt)
print("A) 지원모델+보통크기 status:", status_a)
if body_a:
    print("   응답:", body_a.get("choices", [{}])[0].get("message", {}).get("content") if status_a == 200 else body_a)

# 4. 지원 모델 + 대용량 이미지 (실사용 한계 케이스)
req_b, status_b, body_b = call("google/gemma-3-4b-it", LARGE_IMG, prompt)
print("B) 지원모델+대용량 status:", status_b)
if body_b:
    print("   응답:", body_b.get("choices", [{}])[0].get("message", {}).get("content") if status_b == 200 else body_b)

# 5. 이미지 미지원 모델 + 보통 크기 이미지
req_c, status_c, body_c = call("mistralai/mistral-nemo", NORMAL_IMG, prompt)
print("C) 미지원모델+보통크기 status:", status_c)
if body_c:
    print("   응답:", body_c.get("choices", [{}])[0].get("message", {}).get("content") if status_c == 200 else body_c)

# 6. 저장 (키 제외, 이미지 base64 본문은 크기 정보로 대체)
(RAW_DIR / "api10_request.json").write_text(
    json.dumps(
        {
            "A_support_normal": {"url": URL, "headers": {"Authorization": "<REDACTED>"}, "body": req_a},
            "B_support_large": {"url": URL, "headers": {"Authorization": "<REDACTED>"}, "body": req_b},
            "C_unsupported_normal": {"url": URL, "headers": {"Authorization": "<REDACTED>"}, "body": req_c},
        },
        ensure_ascii=False,
        indent=2,
    ),
    encoding="utf-8",
)
(RAW_DIR / "api10_response.json").write_text(
    json.dumps(
        {
            "A_support_normal": {"status_code": status_a, "body": body_a},
            "B_support_large": {"status_code": status_b, "body": body_b},
            "C_unsupported_normal": {"status_code": status_c, "body": body_c},
        },
        ensure_ascii=False,
        indent=2,
    ),
    encoding="utf-8",
)
